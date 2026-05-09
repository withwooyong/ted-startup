"""IngestPeriodicOhlcvUseCase — ka10082/83 주/월봉 OHLCV 적재 (C-3β).

설계: phase-c-3-weekly-monthly-ohlcv.md § 3.2 + endpoint-07-ka10082.md § 6.3 + endpoint-08-ka10083.md.

ka10081 (IngestDailyOhlcvUseCase) ~95% 복제 + period dispatch:
- WEEKLY → KiwoomChartClient.fetch_weekly + StockPricePeriodicRepository(period=WEEKLY)
- MONTHLY → fetch_monthly + Repository(period=MONTHLY)
- YEARLY → NotImplementedError (P2 chunk 진입 시 활성화, H-3)
- DAILY → ValueError (별도 UseCase 사용 안내, H-3)

R1 정착 패턴 5종 전면 적용:
1. errors: tuple[OhlcvSyncOutcome, ...] (mutable list 노출 금지)
2. StockMasterNotFoundError(ValueError) raise
3. fetched_at: datetime non-Optional (ORM, 별도 조회 endpoint 가 추가될 때 적용)
4. only_market_codes max_length=2 (Router DTO 책임)
5. NXT path except Exception 격리 (R1 L-5)

OhlcvSyncOutcome / OhlcvSyncResult 는 ka10081 의 동명 타입과 **동일 구조 복제** (공통 추출은
별도 refactor chunk 로 연기 — 1R M-2). 두 모듈을 동시 import 할 때 namespace 충돌은 없으나
이름이 같으므로 import 시 모듈 경로 명시 필요.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._exceptions import KiwoomError
from app.adapter.out.kiwoom.chart import (
    DailyChartRow,
    KiwoomChartClient,
    NormalizedDailyOhlcv,
)
from app.adapter.out.persistence.models import Stock
from app.adapter.out.persistence.repositories.stock_price_periodic import (
    StockPricePeriodicRepository,
)
from app.application.constants import ExchangeType, Period, StockListMarketType
from app.application.exceptions import StockMasterNotFoundError

logger = logging.getLogger(__name__)


# 사용자 결정 (C-1β 와 동일): today - 365일 ~ today (1년 cap)
BASE_DATE_MAX_PAST_DAYS: int = 365


_VALID_MARKET_CODES: frozenset[str] = frozenset(m.value for m in StockListMarketType)


@dataclass(frozen=True, slots=True)
class OhlcvSyncOutcome:
    """단일 종목·거래소 sync 실패 outcome — error_class 만 보존 (응답 echo 차단)."""

    stock_code: str
    exchange: str
    error_class: str


@dataclass(frozen=True, slots=True)
class OhlcvSyncResult:
    """sync 실행 결과 — KRX/NXT 별 success counter + per-(stock,exchange) errors.

    R1 invariant — errors 는 tuple (mutable list 노출 금지).
    """

    base_date: date
    total: int
    success_krx: int
    success_nxt: int
    failed: int
    errors: tuple[OhlcvSyncOutcome, ...] = field(default_factory=tuple)


class IngestPeriodicOhlcvUseCase:
    """ka10082/83 호출 → stock_price_{weekly,monthly}_{krx,nxt} 적재 (C-3β).

    의존성 주입:
    - `session_provider`: `() -> AsyncContextManager[AsyncSession]`
    - `chart_client`: KiwoomChartClient (fetch_weekly / fetch_monthly 사용)
    - `nxt_collection_enabled`: settings flag — False 면 NXT skip

    두 진입점:
    - `execute(*, period, base_date=None, only_market_codes=None)` — active stock 전체 sync
    - `refresh_one(stock_code, *, period, base_date)` — 단건 새로고침
    """

    def __init__(
        self,
        *,
        session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
        chart_client: KiwoomChartClient,
        nxt_collection_enabled: bool,
    ) -> None:
        self._session_provider = session_provider
        self._client = chart_client
        self._nxt_enabled = nxt_collection_enabled

    async def execute(
        self,
        *,
        period: Period,
        base_date: date | None = None,
        only_market_codes: Sequence[str] | None = None,
        only_stock_codes: Sequence[str] | None = None,
        _skip_base_date_validation: bool = False,
    ) -> OhlcvSyncResult:
        """active stock 순회 → ka10082/83 호출 → KRX (+ 옵션 NXT) 적재.

        Parameters:
            period: WEEKLY 또는 MONTHLY. YEARLY → NotImplementedError. DAILY → ValueError.
            base_date: 기준일자. None 이면 KST today.
            only_market_codes: 특정 시장만 sync. None 이면 전체.
            _skip_base_date_validation: True 면 base_date 의 1년 cap 우회 (CLI backfill 전용).
                미래 가드는 유지. 운영 라우터는 디폴트 False (C-backfill H-1).

        Raises:
            ValueError: base_date 가 미래 또는 (skip=False 시) today - 365일 초과 과거 /
                unknown market_code
            NotImplementedError: period=YEARLY (P2 chunk 미구현) — `_skip_base_date_validation`
                와 무관 (period 검증은 항상 수행)
        """
        self._validate_period(period)
        asof = base_date or date.today()
        self._validate_base_date(asof, skip_past_cap=_skip_base_date_validation)
        if only_market_codes is not None:
            self._validate_market_codes(only_market_codes)

        # 1. active stock 조회
        async with self._session_provider() as session:
            stmt = select(Stock).where(Stock.is_active.is_(True))
            if only_market_codes:
                stmt = stmt.where(Stock.market_code.in_(only_market_codes))
            if only_stock_codes:
                stmt = stmt.where(Stock.stock_code.in_(only_stock_codes))
            stmt = stmt.order_by(Stock.market_code, Stock.stock_code)
            active_stocks = list((await session.execute(stmt)).scalars())

        success_krx = 0
        success_nxt = 0
        failed = 0
        errors: list[OhlcvSyncOutcome] = []

        # 2. per-stock per-exchange try/except — partial-failure 격리
        for stock in active_stocks:
            # 2-1. KRX
            try:
                await self._ingest_one(stock, period=period, base_date=asof, exchange=ExchangeType.KRX)
                success_krx += 1
            except KiwoomError as exc:
                failed += 1
                errors.append(
                    OhlcvSyncOutcome(
                        stock_code=stock.stock_code,
                        exchange="KRX",
                        error_class=type(exc).__name__,
                    )
                )
                logger.warning(
                    "%s KRX sync 실패 stock_code=%s mrkt_tp=%s: %s",
                    self._api_id_for(period),
                    stock.stock_code,
                    stock.market_code,
                    type(exc).__name__,
                )
            except Exception as exc:  # noqa: BLE001 — 종목 단위 격리
                failed += 1
                errors.append(
                    OhlcvSyncOutcome(
                        stock_code=stock.stock_code,
                        exchange="KRX",
                        error_class=type(exc).__name__,
                    )
                )
                logger.exception(
                    "%s KRX sync 예상치 못한 예외 stock_code=%s",
                    self._api_id_for(period),
                    stock.stock_code,
                )

            # 2-2. NXT (settings + stock.nxt_enable 둘 다 True)
            if not (self._nxt_enabled and stock.nxt_enable):
                continue
            try:
                await self._ingest_one(stock, period=period, base_date=asof, exchange=ExchangeType.NXT)
                success_nxt += 1
            except KiwoomError as exc:
                failed += 1
                errors.append(
                    OhlcvSyncOutcome(
                        stock_code=stock.stock_code,
                        exchange="NXT",
                        error_class=type(exc).__name__,
                    )
                )
                logger.warning(
                    "%s NXT sync 실패 stock_code=%s: %s",
                    self._api_id_for(period),
                    stock.stock_code,
                    type(exc).__name__,
                )
            except Exception as exc:  # noqa: BLE001 — R1 L-5
                failed += 1
                errors.append(
                    OhlcvSyncOutcome(
                        stock_code=stock.stock_code,
                        exchange="NXT",
                        error_class=type(exc).__name__,
                    )
                )
                logger.exception(
                    "%s NXT sync 예상치 못한 예외 stock_code=%s",
                    self._api_id_for(period),
                    stock.stock_code,
                )

        return OhlcvSyncResult(
            base_date=asof,
            total=len(active_stocks),
            success_krx=success_krx,
            success_nxt=success_nxt,
            failed=failed,
            errors=tuple(errors),
        )

    async def refresh_one(
        self,
        stock_code: str,
        *,
        period: Period,
        base_date: date,
        _skip_base_date_validation: bool = False,
    ) -> OhlcvSyncResult:
        """단건 새로고침 — admin POST /stocks/{code}/ohlcv/{period}/refresh.

        Raises:
            StockMasterNotFoundError: Stock 마스터 미존재 / 비활성 (R1 M-2)
            ValueError: base_date 범위 외 / period=DAILY
            NotImplementedError: period=YEARLY
            KiwoomError: KRX 호출 실패 (라우터 매핑)

        NXT 실패는 격리 (R1 L-5 — execute() 와 일관 partial-failure 모델).
        `_skip_base_date_validation`: CLI backfill 전용 (C-backfill H-1).
        """
        self._validate_period(period)
        self._validate_base_date(base_date, skip_past_cap=_skip_base_date_validation)

        async with self._session_provider() as session:
            stmt = select(Stock).where(Stock.stock_code == stock_code, Stock.is_active.is_(True))
            stock = (await session.execute(stmt)).scalar_one_or_none()

        if stock is None:
            raise StockMasterNotFoundError(stock_code)

        # KRX 는 KiwoomError 그대로 propagate (라우터 매핑)
        await self._ingest_one(stock, period=period, base_date=base_date, exchange=ExchangeType.KRX)

        success_nxt = 0
        failed = 0
        errors: list[OhlcvSyncOutcome] = []
        if self._nxt_enabled and stock.nxt_enable:
            try:
                await self._ingest_one(stock, period=period, base_date=base_date, exchange=ExchangeType.NXT)
                success_nxt = 1
            except KiwoomError as exc:
                failed = 1
                errors.append(
                    OhlcvSyncOutcome(
                        stock_code=stock.stock_code,
                        exchange="NXT",
                        error_class=type(exc).__name__,
                    )
                )
                logger.warning(
                    "%s NXT refresh 실패 stock_code=%s: %s — KRX 는 이미 적재됨",
                    self._api_id_for(period),
                    stock.stock_code,
                    type(exc).__name__,
                )
            except Exception as exc:  # noqa: BLE001 — R1 L-5
                failed = 1
                errors.append(
                    OhlcvSyncOutcome(
                        stock_code=stock.stock_code,
                        exchange="NXT",
                        error_class=type(exc).__name__,
                    )
                )
                logger.exception(
                    "%s NXT refresh 예상치 못한 예외 stock_code=%s — KRX 는 이미 적재됨",
                    self._api_id_for(period),
                    stock.stock_code,
                )

        return OhlcvSyncResult(
            base_date=base_date,
            total=1,
            success_krx=1,
            success_nxt=success_nxt,
            failed=failed,
            errors=tuple(errors),
        )

    async def _ingest_one(
        self,
        stock: Stock,
        *,
        period: Period,
        base_date: date,
        exchange: ExchangeType,
    ) -> int:
        """한 종목·한 거래소·한 period sync — 키움 호출 + 정규화 + DB upsert."""
        # 1. period 분기 — fetch_weekly / fetch_monthly
        rows: list[DailyChartRow]
        if period is Period.WEEKLY:
            rows = list(
                await self._client.fetch_weekly(
                    stock.stock_code,
                    base_date=base_date,
                    exchange=exchange,
                    adjusted=True,
                )
            )
        elif period is Period.MONTHLY:
            rows = list(
                await self._client.fetch_monthly(
                    stock.stock_code,
                    base_date=base_date,
                    exchange=exchange,
                    adjusted=True,
                )
            )
        else:
            # 본 메서드는 _validate_period 통과 후 호출 — 여기 도달 시 enum 추가/누락 의심
            raise NotImplementedError(f"period={period} 미구현 — _validate_period 검증 누락")

        # 2. 정규화 (chart.py to_normalized — 부모 클래스 메서드 재사용)
        normalized: list[NormalizedDailyOhlcv] = [
            row.to_normalized(stock_id=stock.id, exchange=exchange, adjusted=True) for row in rows
        ]

        # 3. DB upsert — period+exchange dispatch
        async with self._session_provider() as session, session.begin():
            repo = StockPricePeriodicRepository(session)
            return await repo.upsert_many(normalized, period=period, exchange=exchange)

    def _validate_period(self, period: Period) -> None:
        """H-3 — YEARLY → NotImplementedError.

        Period enum 은 WEEKLY/MONTHLY/YEARLY 3값 (DAILY 미포함). DAILY 분기는 enum 자체에서
        차단되므로 본 메서드는 YEARLY 만 검증. 향후 Period.DAILY 가 enum 에 추가되는 경우
        해당 시점에 ValueError 분기를 추가 (1R M-1 결정).
        """
        if period is Period.YEARLY:
            raise NotImplementedError("period=YEARLY (ka10094) 는 P2 chunk — Migration 미작성")

    def _validate_base_date(self, base_date: date, *, skip_past_cap: bool = False) -> None:
        """today - 365일 ~ today 외 → ValueError (C-1β 와 동일 정책).

        `skip_past_cap=True` 면 1년 cap 만 우회 (CLI backfill 전용 — C-backfill H-1).
        미래 가드는 항상 유지.
        """
        today = date.today()
        if base_date > today:
            raise ValueError(f"base_date 가 미래: {base_date} > {today}")
        if skip_past_cap:
            return
        oldest_allowed = today - timedelta(days=BASE_DATE_MAX_PAST_DAYS)
        if base_date < oldest_allowed:
            raise ValueError(f"base_date 가 today - {BASE_DATE_MAX_PAST_DAYS}일 ~ today 범위 외: {base_date}")

    def _validate_market_codes(self, codes: Sequence[str]) -> None:
        unknown = [c for c in codes if c not in _VALID_MARKET_CODES]
        if unknown:
            raise ValueError(f"unknown market_code(s): {unknown}")

    def _api_id_for(self, period: Period) -> str:
        """logger 메시지용 — period → api_id 매핑."""
        if period is Period.WEEKLY:
            return "ka10082"
        if period is Period.MONTHLY:
            return "ka10083"
        return f"period={period.value}"


__all__ = [
    "BASE_DATE_MAX_PAST_DAYS",
    "IngestPeriodicOhlcvUseCase",
    "OhlcvSyncOutcome",
    "OhlcvSyncResult",
]
