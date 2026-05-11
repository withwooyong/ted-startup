"""IngestDailyFlowUseCase — ka10086 일별 수급 적재 (C-2β).

설계: endpoint-10-ka10086.md § 6.3 + ADR § 17 (C-1β 패턴 일관 + indc_mode 추가).

C-1β IngestDailyOhlcvUseCase 패턴 차용:
- per-stock try/except + KiwoomError catch + outcome.error 격리
- KRX/NXT 분리 ingest (settings flag 게이팅)
- base_date target_date_range 검증 (today - 365 ~ today)
- only_market_codes 화이트리스트 (silent no-op 차단)
- lazy fetch (c) batch fail-closed — active stock 만 대상, ensure_exists 호출 안 함

C-2β 변경점:
- chart → mrkcond client (KiwoomMarketCondClient.fetch_daily_market)
- StockPriceRepository → StockDailyFlowRepository
- adjusted (ka10081) → indc_mode (ka10086 표시 단위 — QUANTITY/AMOUNT)
- adapter parameter `query_date` 로 base_date 전달

indc_mode (계획서 § 6.3 + 사용자 결정):
- 프로세스당 단일 정책 — lifespan 에서 settings 기반 묶음
- 디폴트 QUANTITY (수량) — 백테스팅 시그널 단위 일관성 (계획서 § 2.3 권장)
- 같은 (stock_id, trading_date, exchange) 에 다른 indc_mode 적재 시 단위 mismatch 위험 →
  운영 정책 변경은 별도 deactivate 후 재호출 (ADR-recordable)

stock_id resolution invariant:
- response.stk_cd → strip_kiwoom_suffix → Stock.find_by_code → stock_id (mrkcond.py 책임)
- 본 chunk 는 caller 가 active stock row 의 id 직접 사용 (메아리 검증은 mrkcond.py 가 책임)
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._exceptions import KiwoomError
from app.adapter.out.kiwoom._records import (
    DailyMarketRow,
    NormalizedDailyFlow,
)
from app.adapter.out.kiwoom.mrkcond import KiwoomMarketCondClient
from app.adapter.out.kiwoom.stkinfo import STK_CD_CHART_PATTERN
from app.adapter.out.persistence.models import Stock
from app.adapter.out.persistence.repositories.stock_daily_flow import (
    StockDailyFlowRepository,
)
from app.application.constants import (
    DailyMarketDisplayMode,
    ExchangeType,
    StockListMarketType,
)
from app.application.exceptions import StockMasterNotFoundError

# ka10086 호환 stock_code 패턴 — daily/weekly OHLCV 와 동일 (build_stk_cd 공유).
# CHART (`^[0-9A-Z]{6}$`, ADR § 32) — 우선주 (`*K`) 통과.
_KA10086_COMPATIBLE_RE = re.compile(STK_CD_CHART_PATTERN)

logger = logging.getLogger(__name__)


# 사용자 결정 (C-1β 일관): today - 365일 ~ today (1년 cap)
BASE_DATE_MAX_PAST_DAYS: int = 365


# C-1β 2b-M2 일관 — only_market_codes 화이트리스트 (silent no-op 차단).
_VALID_MARKET_CODES: frozenset[str] = frozenset(m.value for m in StockListMarketType)


@dataclass(frozen=True, slots=True)
class DailyFlowSyncOutcome:
    """단일 종목·거래소 sync 실패 outcome — error_class 만 보존 (응답 echo 차단)."""

    stock_code: str
    exchange: str
    error_class: str


@dataclass(frozen=True, slots=True)
class DailyFlowSyncResult:
    """sync 실행 결과 — KRX/NXT 별 success counter + per-(stock,exchange) errors."""

    base_date: date
    total: int
    success_krx: int
    success_nxt: int
    failed: int
    errors: tuple[DailyFlowSyncOutcome, ...] = field(default_factory=tuple)


class IngestDailyFlowUseCase:
    """ka10086 호출 → stock_daily_flow 일별 수급 적재.

    의존성 주입:
    - `session_provider`: `() -> AsyncContextManager[AsyncSession]` — DB 작업마다 새 세션
    - `mrkcond_client`: KiwoomMarketCondClient (alias 단위 lifespan factory 가 빌드)
    - `nxt_collection_enabled`: settings flag — False 면 NXT skip
    - `indc_mode`: 표시 단위 — 프로세스당 단일 정책. 디폴트 QUANTITY

    두 진입점:
    - `execute(*, base_date=None, only_market_codes=None)` — active stock 전체 sync
    - `refresh_one(stock_code, *, base_date)` — 단건 새로고침 (admin /refresh)
    """

    def __init__(
        self,
        *,
        session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
        mrkcond_client: KiwoomMarketCondClient,
        nxt_collection_enabled: bool,
        indc_mode: DailyMarketDisplayMode = DailyMarketDisplayMode.QUANTITY,
    ) -> None:
        self._session_provider = session_provider
        self._client = mrkcond_client
        self._nxt_enabled = nxt_collection_enabled
        self._indc_mode = indc_mode

    async def execute(
        self,
        *,
        base_date: date | None = None,
        only_market_codes: Sequence[str] | None = None,
        only_stock_codes: Sequence[str] | None = None,
        _skip_base_date_validation: bool = False,
        since_date: date | None = None,
    ) -> DailyFlowSyncResult:
        """active stock 순회 → ka10086 호출 → KRX (+ 옵션 NXT) 적재.

        Parameters:
            base_date: 기준일자. None 이면 KST today.
            only_market_codes: 특정 시장만 sync. None 이면 전체.
            only_stock_codes: 특정 종목만 sync (CLI 디버그 / resume). None 이면 전체.
                둘 다 지정 시 AND 조건. C-1β 일관.
            _skip_base_date_validation: True 면 base_date 의 1년 cap 우회 (CLI backfill 전용).
                미래 가드는 유지. 운영 라우터는 디폴트 False (C-backfill H-1).
            since_date: ka10086 페이지네이션 하한일 (CLI backfill 전용). None 이면 운영
                cron 기존 동작.

        Raises:
            ValueError: base_date 가 미래 또는 (skip=False 시) today - 365일 초과 과거,
                또는 unknown market_code (silent no-op 차단).

        Returns:
            DailyFlowSyncResult — total / success_krx / success_nxt / failed + errors.
        """
        asof = base_date or date.today()
        self._validate_base_date(asof, skip_past_cap=_skip_base_date_validation)
        if only_market_codes is not None:
            self._validate_market_codes(only_market_codes)

        async with self._session_provider() as session:
            stmt = select(Stock).where(Stock.is_active.is_(True))
            if only_market_codes:
                stmt = stmt.where(Stock.market_code.in_(only_market_codes))
            if only_stock_codes:
                stmt = stmt.where(Stock.stock_code.in_(only_stock_codes))
            stmt = stmt.order_by(Stock.market_code, Stock.stock_code)
            raw_stocks = list((await session.execute(stmt)).scalars())

        # ka10086 호환 stock_code 만 keep — OHLCV daily/weekly 와 동일 정책 (ETF/ETN/우선주
        # skip + 가시성 로깅). build_stk_cd ValueError 로 호출 차단되어 errors 누적되던 것을
        # 사전 필터.
        active_stocks = [s for s in raw_stocks if _KA10086_COMPATIBLE_RE.fullmatch(s.stock_code)]
        skipped_count = len(raw_stocks) - len(active_stocks)
        if skipped_count > 0:
            sample = [
                s.stock_code for s in raw_stocks if not _KA10086_COMPATIBLE_RE.fullmatch(s.stock_code)
            ][:5]
            logger.info(
                "ka10086 호환 가드 — active %d 중 %d 종목 skip (ETF/ETN/우선주 추정), sample=%s",
                len(raw_stocks),
                skipped_count,
                sample,
            )

        success_krx = 0
        success_nxt = 0
        failed = 0
        errors: list[DailyFlowSyncOutcome] = []

        for stock in active_stocks:
            try:
                await self._ingest_one(
                    stock, base_date=asof, exchange=ExchangeType.KRX, since_date=since_date
                )
                success_krx += 1
            except KiwoomError as exc:
                failed += 1
                err_class = type(exc).__name__
                errors.append(
                    DailyFlowSyncOutcome(
                        stock_code=stock.stock_code, exchange="KRX", error_class=err_class
                    )
                )
                logger.warning(
                    "ka10086 KRX sync 실패 stock_code=%s mrkt_tp=%s: %s",
                    stock.stock_code,
                    stock.market_code,
                    err_class,
                )
            except Exception as exc:  # noqa: BLE001 — DB/기타 예외도 종목 단위 격리
                failed += 1
                err_class = type(exc).__name__
                errors.append(
                    DailyFlowSyncOutcome(
                        stock_code=stock.stock_code, exchange="KRX", error_class=err_class
                    )
                )
                logger.exception(
                    "ka10086 KRX sync 예상치 못한 예외 stock_code=%s",
                    stock.stock_code,
                )

            if not (self._nxt_enabled and stock.nxt_enable):
                continue
            try:
                await self._ingest_one(
                    stock, base_date=asof, exchange=ExchangeType.NXT, since_date=since_date
                )
                success_nxt += 1
            except KiwoomError as exc:
                failed += 1
                err_class = type(exc).__name__
                errors.append(
                    DailyFlowSyncOutcome(
                        stock_code=stock.stock_code, exchange="NXT", error_class=err_class
                    )
                )
                logger.warning(
                    "ka10086 NXT sync 실패 stock_code=%s: %s",
                    stock.stock_code,
                    err_class,
                )
            except Exception as exc:  # noqa: BLE001
                failed += 1
                err_class = type(exc).__name__
                errors.append(
                    DailyFlowSyncOutcome(
                        stock_code=stock.stock_code, exchange="NXT", error_class=err_class
                    )
                )
                logger.exception(
                    "ka10086 NXT sync 예상치 못한 예외 stock_code=%s",
                    stock.stock_code,
                )

        return DailyFlowSyncResult(
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
    ) -> DailyFlowSyncResult:
        """단건 새로고침 — admin POST /stocks/{code}/daily-flow/refresh.

        Stock 마스터에 active 로 등록돼 있어야 함 (ensure_exists 미사용).
        없으면 StockMasterNotFoundError → 라우터가 404 매핑.

        KRX 호출 실패 → KiwoomError 그대로 raise (라우터가 4xx/5xx 매핑).
        NXT 호출 실패 → KRX 가 이미 적재된 상태이므로 errors 로 격리 (C-1β 2a-M1 / 2b-L3 일관).
            응답 200 + success_krx=1 + failed=1 — admin 이 "KRX 성공, NXT 실패" 인지.
            R1 (L-5): KiwoomError 외 비-Kiwoom 예외 (DB / network 등) 도 격리 — execute()
            의 NXT 경로와 일관 (partial-failure 모델).

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
        errors: list[DailyFlowSyncOutcome] = []
        if self._nxt_enabled and stock.nxt_enable:
            try:
                await self._ingest_one(stock, base_date=base_date, exchange=ExchangeType.NXT)
                success_nxt = 1
            except KiwoomError as exc:
                # C-1β 2a-M1 / 2b-L3 일관 — NXT 격리. KRX 이미 적재됐으므로 전체 raise 대신 errors.
                failed = 1
                err_class = type(exc).__name__
                errors.append(
                    DailyFlowSyncOutcome(
                        stock_code=stock.stock_code, exchange="NXT", error_class=err_class
                    )
                )
                logger.warning(
                    "ka10086 NXT refresh 실패 stock_code=%s: %s — KRX 는 이미 적재됨",
                    stock.stock_code,
                    err_class,
                )
            except Exception as exc:  # noqa: BLE001 — R1 L-5: execute() 와 일관 격리
                failed = 1
                err_class = type(exc).__name__
                errors.append(
                    DailyFlowSyncOutcome(
                        stock_code=stock.stock_code, exchange="NXT", error_class=err_class
                    )
                )
                logger.exception(
                    "ka10086 NXT refresh 예상치 못한 예외 stock_code=%s — KRX 는 이미 적재됨",
                    stock.stock_code,
                )

        return DailyFlowSyncResult(
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
        base_date: date,
        exchange: ExchangeType,
        since_date: date | None = None,
    ) -> int:
        """한 종목·한 거래소 sync — 키움 호출 + 정규화 + DB upsert. 영향 row 수 반환."""
        rows: list[DailyMarketRow] = await self._client.fetch_daily_market(
            stock.stock_code,
            query_date=base_date,
            exchange=exchange,
            indc_mode=self._indc_mode,
            since_date=since_date,
        )

        normalized: list[NormalizedDailyFlow] = [
            row.to_normalized(stock_id=stock.id, exchange=exchange, indc_mode=self._indc_mode)
            for row in rows
        ]

        async with self._session_provider() as session, session.begin():
            repo = StockDailyFlowRepository(session)
            return await repo.upsert_many(normalized)

    def _validate_base_date(self, base_date: date, *, skip_past_cap: bool = False) -> None:
        """미래 가드는 항상 적용. skip_past_cap=True 면 1년 cap 우회 (CLI backfill 전용).

        C-1β 일관 — 운영 라우터는 디폴트 False 로 1년 cap 유지.
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
        """미등록 시장 코드 → ValueError (C-1β 2b-M2 일관, silent no-op 차단)."""
        unknown = [c for c in codes if c not in _VALID_MARKET_CODES]
        if unknown:
            raise ValueError(f"unknown market_code(s): {unknown}")


__all__ = [
    "BASE_DATE_MAX_PAST_DAYS",
    "DailyFlowSyncOutcome",
    "DailyFlowSyncResult",
    "IngestDailyFlowUseCase",
]
