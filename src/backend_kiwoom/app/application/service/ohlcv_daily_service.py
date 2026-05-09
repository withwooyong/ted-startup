"""IngestDailyOhlcvUseCase — ka10081 일별 OHLCV 적재 (C-1β).

설계: endpoint-06-ka10081.md § 6.3 + ADR § 17.

Phase B-γ-2 SyncStockFundamentalUseCase 패턴 차용:
- per-stock try/except + KiwoomError catch + outcome.error 격리
- `_safe_for_log` 는 본 chunk 미적용 (2b-M3) — vendor 응답 string (stock_name 등) 을 logger
  로 노출 안 함. 인자는 DB 자체 stock_code/market_code/exception class 명만. 향후 vendor 응답
  을 logger 에 추가할 경우 B-γ-2 패턴 (control char strip) 차용 필요.

KRX/NXT 분리 ingest (사용자 결정):
- `nxt_collection_enabled=False` 디폴트 → KRX 만 적재
- True + `stock.nxt_enable=True` → KRX + NXT 둘 다 (독립 호출 — 한쪽 실패해도 다른쪽 진행)

base_date target_date_range (사용자 결정 — today - 365 ~ today):
- 미래 / 1년 초과 과거 → ValueError → 라우터 400 매핑

lazy fetch (c) batch fail-closed (사용자 결정, ADR § 13.4.1):
- active stock 만 대상, ensure_exists 호출 안 함
- 응답 stk_cd 메아리 mismatch 는 chart.py 가 raise → KiwoomResponseValidationError 격리

stock_id resolution invariant:
- response.stk_cd → strip_kiwoom_suffix → Stock.find_by_code → stock_id
- 본 chunk 는 caller 가 active stock row 의 id 직접 사용 (메아리 검증은 chart.py 가 책임)
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
from app.adapter.out.persistence.repositories.stock_price import StockPriceRepository
from app.application.constants import ExchangeType, StockListMarketType
from app.application.exceptions import StockMasterNotFoundError

logger = logging.getLogger(__name__)


# 사용자 결정: today - 365일 ~ today (1년 cap)
BASE_DATE_MAX_PAST_DAYS: int = 365


# 2b-M2 — only_market_codes 화이트리스트 (운영 진단 방해 차단).
# StockListMarketType StrEnum 의 value 집합 기반.
_VALID_MARKET_CODES: frozenset[str] = frozenset(m.value for m in StockListMarketType)


@dataclass(frozen=True, slots=True)
class OhlcvSyncOutcome:
    """단일 종목·거래소 sync 실패 outcome — error_class 만 보존 (응답 echo 차단)."""

    stock_code: str
    exchange: str
    error_class: str


@dataclass(frozen=True, slots=True)
class OhlcvSyncResult:
    """sync 실행 결과 — KRX/NXT 별 success counter + per-(stock,exchange) errors."""

    base_date: date
    total: int
    success_krx: int
    success_nxt: int
    failed: int
    errors: tuple[OhlcvSyncOutcome, ...] = field(default_factory=tuple)


class IngestDailyOhlcvUseCase:
    """ka10081 호출 → stock_price_krx/nxt 일별 적재.

    의존성 주입:
    - `session_provider`: `() -> AsyncContextManager[AsyncSession]` — DB 작업마다 새 세션
    - `chart_client`: KiwoomChartClient (alias 단위 lifespan factory 가 빌드)
    - `nxt_collection_enabled`: settings flag — False 면 NXT skip

    두 진입점:
    - `execute(*, base_date=None, only_market_codes=None)` — active stock 전체 sync
    - `refresh_one(stock_code, *, base_date)` — 단건 새로고침 (admin /refresh)
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
        base_date: date | None = None,
        only_market_codes: Sequence[str] | None = None,
        only_stock_codes: Sequence[str] | None = None,
        _skip_base_date_validation: bool = False,
    ) -> OhlcvSyncResult:
        """active stock 순회 → ka10081 호출 → KRX (+ 옵션 NXT) 적재.

        Parameters:
            base_date: 기준일자. None 이면 KST today.
            only_market_codes: 특정 시장만 sync. None 이면 전체.
            only_stock_codes: 특정 종목만 sync (CLI 디버그 / resume). None 이면 전체.
                둘 다 지정 시 AND 조건.
            _skip_base_date_validation: True 면 base_date 의 1년 cap 우회 (CLI backfill 전용).
                미래 가드는 유지 (오타 방어). 운영 라우터는 디폴트 False — R1 invariant 유지
                (C-backfill H-1).

        Raises:
            ValueError: base_date 가 미래 또는 (skip=False 시) today - 365일 초과 과거.

        Returns:
            OhlcvSyncResult — total / success_krx / success_nxt / failed + errors.
        """
        asof = base_date or date.today()
        self._validate_base_date(asof, skip_past_cap=_skip_base_date_validation)
        if only_market_codes is not None:
            self._validate_market_codes(only_market_codes)

        # 1. active stock 조회 (별도 세션)
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
            # 2-1. KRX (디폴트 항상 시도)
            try:
                await self._ingest_one(stock, base_date=asof, exchange=ExchangeType.KRX)
                success_krx += 1
            except KiwoomError as exc:
                failed += 1
                err_class = type(exc).__name__
                errors.append(
                    OhlcvSyncOutcome(
                        stock_code=stock.stock_code, exchange="KRX", error_class=err_class
                    )
                )
                logger.warning(
                    "ka10081 KRX sync 실패 stock_code=%s mrkt_tp=%s: %s",
                    stock.stock_code,
                    stock.market_code,
                    err_class,
                )
            except Exception as exc:  # noqa: BLE001 — DB/기타 예외도 종목 단위 격리
                failed += 1
                err_class = type(exc).__name__
                errors.append(
                    OhlcvSyncOutcome(
                        stock_code=stock.stock_code, exchange="KRX", error_class=err_class
                    )
                )
                logger.exception(
                    "ka10081 KRX sync 예상치 못한 예외 stock_code=%s",
                    stock.stock_code,
                )

            # 2-2. NXT (settings + stock.nxt_enable 둘 다 True 일 때만)
            if not (self._nxt_enabled and stock.nxt_enable):
                continue
            try:
                await self._ingest_one(stock, base_date=asof, exchange=ExchangeType.NXT)
                success_nxt += 1
            except KiwoomError as exc:
                failed += 1
                err_class = type(exc).__name__
                errors.append(
                    OhlcvSyncOutcome(
                        stock_code=stock.stock_code, exchange="NXT", error_class=err_class
                    )
                )
                logger.warning(
                    "ka10081 NXT sync 실패 stock_code=%s: %s",
                    stock.stock_code,
                    err_class,
                )
            except Exception as exc:  # noqa: BLE001
                failed += 1
                err_class = type(exc).__name__
                errors.append(
                    OhlcvSyncOutcome(
                        stock_code=stock.stock_code, exchange="NXT", error_class=err_class
                    )
                )
                logger.exception(
                    "ka10081 NXT sync 예상치 못한 예외 stock_code=%s",
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
        base_date: date,
        _skip_base_date_validation: bool = False,
    ) -> OhlcvSyncResult:
        """단건 새로고침 — admin POST /stocks/{code}/ohlcv/daily/refresh.

        Stock 마스터에 active 로 등록돼 있어야 함 (ensure_exists 미사용).
        없으면 StockMasterNotFoundError → 라우터가 404 매핑.

        KRX 호출 실패 → KiwoomError 그대로 raise (라우터가 4xx/5xx 매핑).
        NXT 호출 실패 → KRX 가 이미 적재된 상태이므로 errors 로 격리 (2a-M1 / 2b-L3).
            응답 200 + success_krx=1 + failed=1 — admin 이 "KRX 성공, NXT 실패" 인지.
            R1 (L-5): KiwoomError 외 비-Kiwoom 예외 (DB / network 등) 도 격리 — execute()
            의 NXT 경로와 일관 (partial-failure 모델). KRX 가 이미 성공했으므로 NXT 의
            unexpected exception 으로 전체 500 반환 시 admin 의 "KRX 적재 사실" 가시성
            손실. 격리하여 응답 200 + failed=1 + errors[NXT] 로 명시.

            `_skip_base_date_validation`: CLI backfill 전용 (C-backfill H-1).
        """
        self._validate_base_date(base_date, skip_past_cap=_skip_base_date_validation)

        async with self._session_provider() as session:
            stmt = select(Stock).where(
                Stock.stock_code == stock_code, Stock.is_active.is_(True)
            )
            stock = (await session.execute(stmt)).scalar_one_or_none()

        if stock is None:
            raise StockMasterNotFoundError(stock_code)

        # KRX 는 KiwoomError 그대로 propagate (라우터 매핑)
        await self._ingest_one(stock, base_date=base_date, exchange=ExchangeType.KRX)

        success_nxt = 0
        failed = 0
        errors: list[OhlcvSyncOutcome] = []
        if self._nxt_enabled and stock.nxt_enable:
            try:
                await self._ingest_one(stock, base_date=base_date, exchange=ExchangeType.NXT)
                success_nxt = 1
            except KiwoomError as exc:
                # 2a-M1 / 2b-L3 — NXT 격리. KRX 이미 적재됐으므로 전체 raise 대신 errors.
                failed = 1
                err_class = type(exc).__name__
                errors.append(
                    OhlcvSyncOutcome(
                        stock_code=stock.stock_code, exchange="NXT", error_class=err_class
                    )
                )
                logger.warning(
                    "ka10081 NXT refresh 실패 stock_code=%s: %s — KRX 는 이미 적재됨",
                    stock.stock_code,
                    err_class,
                )
            except Exception as exc:  # noqa: BLE001 — R1 L-5: execute() 와 일관 격리
                failed = 1
                err_class = type(exc).__name__
                errors.append(
                    OhlcvSyncOutcome(
                        stock_code=stock.stock_code, exchange="NXT", error_class=err_class
                    )
                )
                logger.exception(
                    "ka10081 NXT refresh 예상치 못한 예외 stock_code=%s — KRX 는 이미 적재됨",
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
        self, stock: Stock, *, base_date: date, exchange: ExchangeType
    ) -> int:
        """한 종목·한 거래소 sync — 키움 호출 + 정규화 + DB upsert. 영향 row 수 반환."""
        # 1. 키움 API 호출 (트랜잭션 밖 — DB 락 점유 시간 최소)
        rows: list[DailyChartRow] = await self._client.fetch_daily(
            stock.stock_code,
            base_date=base_date,
            exchange=exchange,
            adjusted=True,
        )

        # 2. 정규화 (chart.py to_normalized 가 BIGINT/NaN 가드 + date.min 표식 적용)
        normalized: list[NormalizedDailyOhlcv] = [
            row.to_normalized(stock_id=stock.id, exchange=exchange, adjusted=True)
            for row in rows
        ]

        # 3. DB upsert — 단건 트랜잭션 (Repository 가 date.min skip 자동 적용)
        async with self._session_provider() as session, session.begin():
            repo = StockPriceRepository(session)
            return await repo.upsert_many(normalized, exchange=exchange)

    def _validate_base_date(self, base_date: date, *, skip_past_cap: bool = False) -> None:
        """today - 365일 ~ today 외 → ValueError (사용자 승인).

        `skip_past_cap=True` 면 1년 cap 만 우회 (CLI backfill 전용 — C-backfill H-1). 미래
        가드는 항상 유지 (오타 방어).
        """
        today = date.today()
        if base_date > today:
            raise ValueError(f"base_date 가 미래: {base_date} > {today}")
        if skip_past_cap:
            return
        oldest_allowed = today - timedelta(days=BASE_DATE_MAX_PAST_DAYS)
        if base_date < oldest_allowed:
            raise ValueError(
                f"base_date 가 today - {BASE_DATE_MAX_PAST_DAYS}일 ~ today 범위 외: {base_date}"
            )

    def _validate_market_codes(self, codes: Sequence[str]) -> None:
        """미등록 시장 코드 → ValueError (2b-M2 silent no-op 차단).

        StockListMarketType.value 화이트리스트 비교 — 운영 진단 가시성 보호.
        """
        unknown = [c for c in codes if c not in _VALID_MARKET_CODES]
        if unknown:
            raise ValueError(f"unknown market_code(s): {unknown}")


__all__ = [
    "BASE_DATE_MAX_PAST_DAYS",
    "IngestDailyOhlcvUseCase",
    "OhlcvSyncOutcome",
    "OhlcvSyncResult",
]
