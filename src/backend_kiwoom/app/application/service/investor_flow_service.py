"""Phase G ingest 서비스 — ka10058 / ka10059 / ka10131 (3 단건 + 3 Bulk = 6 UseCase).

설계: phase-g-investor-flow.md § 5.6 + endpoint-23/24/25.

3 endpoint 가 같은 도메인 (투자자별 매매 흐름) 이라 서비스 모듈 1개 통합.
F-3 정착 패턴:
- ``SkipReason`` enum (sentinel skip 표식).
- ``errors_above_threshold: tuple[str, ...]`` (D-11 임계치 미도입 — 빈 tuple).
- 단건 ``SentinelStockCodeError`` catch (F-3 D-7 defense-in-depth).

inh-1 mitigate 정책 (Step 2 fix R1 C-8 옵션 A — D-12 분리):
- 본 모듈은 inh-1 (3000 종목 1 트랜잭션) 의 부분 mitigate (SAVEPOINT / flush 50) 를
  **구현하지 않는다**. 별도 chunk (D-12 후속) 로 분리. ka10059 Bulk 의 50 호출마다
  ``logger.debug`` 진행 로깅만 유지 (운영 가시화 — flush 효과 아님).
- 실제 inh-1 mitigate (begin_nested SAVEPOINT / flush per BATCH) 는 운영 dry-run 후
  별도 chunk 에서 D-12 결정에 따라 추가. 본 chunk 는 docstring 허위 광고 제거 (R1 C-8).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._exceptions import KiwoomBusinessError
from app.adapter.out.kiwoom._records import (
    AmountQuantityType,
    ContinuousAmtQtyType,
    ContinuousPeriodType,
    InvestorMarketType,
    InvestorTradeType,
    InvestorType,
    NormalizedFrgnOrgnConsecutive,
    NormalizedInvestorDailyTrade,
    NormalizedStockInvestorBreakdown,
    RankingExchangeType,
    StockIndsType,
    StockInvestorTradeType,
    UnitType,
)
from app.adapter.out.kiwoom.stkinfo import SentinelStockCodeError, strip_kiwoom_suffix
from app.application.dto._shared import SkipReason
from app.application.dto.investor_flow import (
    FrgnOrgnConsecutiveBulkResult,
    FrgnOrgnConsecutiveOutcome,
    InvestorFlowBulkResult,
    InvestorIngestOutcome,
    StockInvestorBreakdownBulkResult,
    StockInvestorBreakdownOutcome,
)

logger = logging.getLogger(__name__)


# ka10059 Bulk 의 진행 로깅 단위 (운영 가시화 전용 — flush/commit 효과 아님).
# 본 chunk 에서는 D-12 inh-1 mitigate 미구현 — 단순 ``logger.debug`` 진행 로깅 (R1 C-8 옵션 A).
_STOCK_INVESTOR_BREAKDOWN_BATCH = 50


class _StockLookupProtocol(Protocol):
    """``StockRepository.find_by_codes`` 의 최소 인터페이스 (테스트 mock 호환)."""

    async def find_by_codes(self, codes: Any) -> dict[str, Any]: ...


def _unwrap_client_rows(result: Any) -> list[Any]:
    """Adapter 응답이 ``(rows, used_filters)`` tuple 또는 ``rows`` list — 양쪽 지원.

    운영 코드 (``KiwoomStkInfoClient.fetch_investor_daily_trade_stocks`` /
    ``KiwoomStkInfoClient.fetch_stock_investor_breakdown`` /
    ``KiwoomForeignClient.fetch_continuous``) 는 모두 ``tuple[list[...], dict[str, Any]]`` 반환.
    테스트 mock 은 list 직접 반환 (간이성).

    Phase G inh-5 (ADR § 49.4 / § 49.8) — 휴리스틱 ``isinstance(result, tuple) and len == 2``
    + fallback ``list(result)`` 가 silent fail 위험 (예: dict 입력 시 keys 반환). 본 helper 는
    명시 분기 + 미지원 타입은 ``TypeError`` raise — 디버깅 가시화 + 향후 client 시그니처 변경 시
    조용히 깨지지 않게 가드.
    """
    if isinstance(result, tuple):
        if len(result) != 2:
            raise TypeError(
                f"Adapter 응답 tuple length 2 기대 (rows, used_filters), "
                f"실제 length={len(result)}"
            )
        rows, _used = result
        if rows is None:
            return []
        if not isinstance(rows, list):
            raise TypeError(
                f"Adapter 응답 tuple[0] (rows) list 기대, "
                f"실제 type={type(rows).__name__}"
            )
        return rows
    if isinstance(result, list):
        return result
    raise TypeError(
        f"Adapter 응답은 list 또는 (rows, used_filters) tuple 기대, "
        f"실제 type={type(result).__name__}"
    )


def _resolve_stock_id(value: Any) -> int | None:
    """``find_by_codes`` 결과의 dict 값 → stock_id 추출 (테스트 mock 호환).

    실제 운영: ``dict[str, Stock]`` — ``Stock.id`` 추출.
    테스트 mock: ``dict[str, int]`` — int 그대로 반환.
    None / 부재: None 반환.
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    # Stock-like — ``.id`` 속성
    stock_id = getattr(value, "id", None)
    if isinstance(stock_id, int):
        return stock_id
    return None


# ===========================================================================
# Empty BulkResult helpers (F-3 D-5 정착)
# ===========================================================================


def _empty_investor_flow_bulk_result() -> InvestorFlowBulkResult:
    """빈 호출 매트릭스 시 zero-value BulkResult."""
    return InvestorFlowBulkResult(
        outcomes=(),
        errors_above_threshold=(),
    )


def _empty_breakdown_bulk_result() -> StockInvestorBreakdownBulkResult:
    """빈 stock list 시 zero-value BulkResult."""
    return StockInvestorBreakdownBulkResult(
        outcomes=(),
        errors_above_threshold=(),
    )


def _empty_frgn_orgn_bulk_result() -> FrgnOrgnConsecutiveBulkResult:
    """빈 매트릭스 시 zero-value BulkResult."""
    return FrgnOrgnConsecutiveBulkResult(
        outcomes=(),
        errors_above_threshold=(),
    )


# ===========================================================================
# ka10058 — IngestInvestorDailyTradeUseCase + Bulk
# ===========================================================================


class IngestInvestorDailyTradeUseCase:
    """ka10058 단건 ingest — (investor_type, trade_type, market_type) 1쌍.

    F-3 D-7 defense-in-depth: SentinelStockCodeError catch.
    """

    def __init__(
        self,
        *,
        client: Any,
        repository: Any,
        stock_repository: _StockLookupProtocol,
        session: AsyncSession,
    ) -> None:
        self._client = client
        self._repository = repository
        self._stock_repository = stock_repository
        self._session = session

    async def execute(
        self,
        *,
        strt_dt: str,
        end_dt: str,
        investor_type: InvestorType,
        trade_type: InvestorTradeType = InvestorTradeType.NET_BUY,
        market_type: InvestorMarketType = InvestorMarketType.KOSPI,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
        fetched_at: datetime,
    ) -> InvestorIngestOutcome:
        try:
            client_result = await self._client.fetch_investor_daily_trade_stocks(
                strt_dt=strt_dt,
                end_dt=end_dt,
                trde_tp=trade_type,
                mrkt_tp=market_type,
                invsr_tp=investor_type,
                stex_tp=exchange_type,
            )
            raw_rows = _unwrap_client_rows(client_result)
        except SentinelStockCodeError:
            logger.info(
                "ka10058 sentinel skip inv=%s trde=%s mkt=%s",
                investor_type.value,
                trade_type.value,
                market_type.value,
            )
            return InvestorIngestOutcome(
                fetched_at=fetched_at,
                investor_type=investor_type.value,
                trade_type=trade_type.value,
                market_type=market_type.value,
                exchange_type=exchange_type.value,
                error=SkipReason.SENTINEL_SKIP.value,
            )
        except KiwoomBusinessError as exc:
            return InvestorIngestOutcome(
                fetched_at=fetched_at,
                investor_type=investor_type.value,
                trade_type=trade_type.value,
                market_type=market_type.value,
                exchange_type=exchange_type.value,
                error=f"business: {exc.return_code}",
            )

        if not raw_rows:
            return InvestorIngestOutcome(
                fetched_at=fetched_at,
                investor_type=investor_type.value,
                trade_type=trade_type.value,
                market_type=market_type.value,
                exchange_type=exchange_type.value,
                fetched=0,
                upserted=0,
            )

        # stock 매핑 — strip suffix 후 lookup.
        codes_clean = {strip_kiwoom_suffix(r.stk_cd) for r in raw_rows}
        stocks_by_code = await self._stock_repository.find_by_codes(codes_clean)

        # ka10058 응답의 ``as_of_date`` 는 응답 기간 종료일 (end_dt).
        from app.adapter.out.kiwoom.stkinfo import _parse_yyyymmdd  # circular import 회피
        as_of_date = _parse_yyyymmdd(end_dt) or _parse_yyyymmdd(strt_dt)
        if as_of_date is None:
            # 잘못된 날짜 입력 — error outcome.
            return InvestorIngestOutcome(
                fetched_at=fetched_at,
                investor_type=investor_type.value,
                trade_type=trade_type.value,
                market_type=market_type.value,
                exchange_type=exchange_type.value,
                error="invalid_date",
            )

        normalized: list[NormalizedInvestorDailyTrade] = []
        for rank_idx, raw_row in enumerate(raw_rows, start=1):
            code_clean = strip_kiwoom_suffix(raw_row.stk_cd)
            stock = stocks_by_code.get(code_clean)
            stock_id = _resolve_stock_id(stock)

            normalized.append(
                raw_row.to_normalized(
                    stock_id=stock_id,
                    as_of_date=as_of_date,
                    investor_type=investor_type,
                    trade_type=trade_type,
                    market_type=market_type,
                    exchange_type=exchange_type,
                    rank=rank_idx,
                )
            )

        upserted = await self._repository.upsert_many(normalized)
        return InvestorIngestOutcome(
            fetched_at=fetched_at,
            investor_type=investor_type.value,
            trade_type=trade_type.value,
            market_type=market_type.value,
            exchange_type=exchange_type.value,
            fetched=len(raw_rows),
            upserted=upserted,
        )


class IngestInvestorDailyTradeBulkUseCase:
    """ka10058 Bulk — 2 mkt × 3 inv × 2 trde = 12 호출 매트릭스 (D-3/D-4/D-5).

    inh-1 mitigate 는 D-12 후속 chunk 책임 (R1 C-8 옵션 A). 본 클래스는 단순 순차 호출 +
    try/except 격리만 수행. SAVEPOINT / flush 광고 제거.
    """

    DEFAULT_INVESTORS: tuple[InvestorType, ...] = (
        InvestorType.INDIVIDUAL,
        InvestorType.FOREIGN,
        InvestorType.INSTITUTION_TOTAL,
    )
    DEFAULT_TRADE_TYPES: tuple[InvestorTradeType, ...] = (
        InvestorTradeType.NET_BUY,
        InvestorTradeType.NET_SELL,
    )
    DEFAULT_MARKET_TYPES: tuple[InvestorMarketType, ...] = (
        InvestorMarketType.KOSPI,
        InvestorMarketType.KOSDAQ,
    )

    def __init__(self, *, single_use_case: IngestInvestorDailyTradeUseCase) -> None:
        self._single = single_use_case

    async def execute(
        self,
        *,
        strt_dt: str,
        end_dt: str,
        investor_types: Sequence[InvestorType] | None = None,
        trade_types: Sequence[InvestorTradeType] | None = None,
        market_types: Sequence[InvestorMarketType] | None = None,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
        fetched_at: datetime,
    ) -> InvestorFlowBulkResult:
        # Empty matrix → F-3 D-5 empty helper.
        if investor_types is not None and not investor_types:
            return _empty_investor_flow_bulk_result()
        if trade_types is not None and not trade_types:
            return _empty_investor_flow_bulk_result()
        if market_types is not None and not market_types:
            return _empty_investor_flow_bulk_result()

        targets_inv = list(investor_types) if investor_types is not None else list(self.DEFAULT_INVESTORS)
        targets_trd = list(trade_types) if trade_types is not None else list(self.DEFAULT_TRADE_TYPES)
        targets_mkt = list(market_types) if market_types is not None else list(self.DEFAULT_MARKET_TYPES)

        outcomes: list[InvestorIngestOutcome] = []
        for market in targets_mkt:
            for investor in targets_inv:
                for trade in targets_trd:
                    try:
                        outcome = await self._single.execute(
                            strt_dt=strt_dt,
                            end_dt=end_dt,
                            investor_type=investor,
                            trade_type=trade,
                            market_type=market,
                            exchange_type=exchange_type,
                            fetched_at=fetched_at,
                        )
                    except Exception as exc:  # noqa: BLE001 — partial 격리
                        logger.warning(
                            "ka10058 bulk 호출 실패 inv=%s trd=%s mkt=%s: %s",
                            investor.value,
                            trade.value,
                            market.value,
                            type(exc).__name__,
                        )
                        outcome = InvestorIngestOutcome(
                            fetched_at=fetched_at,
                            investor_type=investor.value,
                            trade_type=trade.value,
                            market_type=market.value,
                            exchange_type=exchange_type.value,
                            error=type(exc).__name__,
                        )
                    outcomes.append(outcome)

        return InvestorFlowBulkResult(
            outcomes=tuple(outcomes),
            errors_above_threshold=(),  # D-11 임계치 미도입
        )


# ===========================================================================
# ka10059 — IngestStockInvestorBreakdownUseCase + Bulk
# ===========================================================================


class IngestStockInvestorBreakdownUseCase:
    """ka10059 단건 ingest — (stock_code, dt) 1쌍 (wide format 12 net)."""

    def __init__(
        self,
        *,
        client: Any,
        repository: Any,
        session: AsyncSession,
    ) -> None:
        self._client = client
        self._repository = repository
        self._session = session

    async def execute(
        self,
        *,
        stock_id: int | None,
        stk_cd: str,
        dt: str,
        amt_qty_tp: AmountQuantityType = AmountQuantityType.QUANTITY,
        trade_type: StockInvestorTradeType = StockInvestorTradeType.NET_BUY,
        unit_tp: UnitType = UnitType.THOUSAND_SHARES,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
        fetched_at: datetime,
    ) -> StockInvestorBreakdownOutcome:
        try:
            client_result = await self._client.fetch_stock_investor_breakdown(
                dt=dt,
                stk_cd=stk_cd,
                amt_qty_tp=amt_qty_tp,
                trde_tp=trade_type,
                unit_tp=unit_tp,
                stex_tp=exchange_type,
            )
            raw_rows = _unwrap_client_rows(client_result)
        except SentinelStockCodeError:
            logger.info("ka10059 sentinel skip stk_cd=%s", stk_cd)
            return StockInvestorBreakdownOutcome(
                fetched_at=fetched_at,
                stock_code=stk_cd,
                trading_date=dt,
                error=SkipReason.SENTINEL_SKIP.value,
            )
        except KiwoomBusinessError as exc:
            return StockInvestorBreakdownOutcome(
                fetched_at=fetched_at,
                stock_code=stk_cd,
                trading_date=dt,
                error=f"business: {exc.return_code}",
            )

        if not raw_rows:
            return StockInvestorBreakdownOutcome(
                fetched_at=fetched_at,
                stock_code=stk_cd,
                trading_date=dt,
                fetched=0,
                upserted=0,
            )

        normalized: list[NormalizedStockInvestorBreakdown] = [
            raw_row.to_normalized(
                stock_id=stock_id,
                amt_qty_tp=amt_qty_tp,
                trade_type=trade_type,
                unit_tp=unit_tp,
                exchange_type=exchange_type,
            )
            for raw_row in raw_rows
        ]
        upserted = await self._repository.upsert_many(normalized)

        return StockInvestorBreakdownOutcome(
            fetched_at=fetched_at,
            stock_code=stk_cd,
            trading_date=dt,
            fetched=len(raw_rows),
            upserted=upserted,
        )


class IngestStockInvestorBreakdownBulkUseCase:
    """ka10059 Bulk — active 종목 ~3000 × 1조합 (D-8 default)."""

    def __init__(self, *, single_use_case: IngestStockInvestorBreakdownUseCase) -> None:
        self._single = single_use_case

    async def execute(
        self,
        *,
        stock_codes: Sequence[str],
        stock_id_map: dict[str, int],
        dt: str,
        amt_qty_tp: AmountQuantityType = AmountQuantityType.QUANTITY,
        trade_type: StockInvestorTradeType = StockInvestorTradeType.NET_BUY,
        unit_tp: UnitType = UnitType.THOUSAND_SHARES,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
        fetched_at: datetime,
    ) -> StockInvestorBreakdownBulkResult:
        if not stock_codes:
            return _empty_breakdown_bulk_result()

        outcomes: list[StockInvestorBreakdownOutcome] = []
        for stk_cd in stock_codes:
            base_code = strip_kiwoom_suffix(stk_cd)
            stock_id = stock_id_map.get(base_code)
            if stock_id is None:
                outcomes.append(
                    StockInvestorBreakdownOutcome(
                        fetched_at=fetched_at,
                        stock_code=stk_cd,
                        trading_date=dt,
                        error="stock_lookup_miss",
                    )
                )
                continue

            try:
                outcome = await self._single.execute(
                    stock_id=stock_id,
                    stk_cd=stk_cd,
                    dt=dt,
                    amt_qty_tp=amt_qty_tp,
                    trade_type=trade_type,
                    unit_tp=unit_tp,
                    exchange_type=exchange_type,
                    fetched_at=fetched_at,
                )
            except Exception as exc:  # noqa: BLE001 — partial 격리
                logger.warning(
                    "ka10059 bulk 호출 실패 stk_cd=%s: %s",
                    stk_cd,
                    type(exc).__name__,
                )
                outcome = StockInvestorBreakdownOutcome(
                    fetched_at=fetched_at,
                    stock_code=stk_cd,
                    trading_date=dt,
                    error=type(exc).__name__,
                )
            outcomes.append(outcome)

            # 50 호출마다 진행 로깅 — 운영 가시화 전용 (flush 효과 아님, R1 C-8 옵션 A).
            # D-12 inh-1 mitigate (begin_nested / flush) 는 별도 chunk 책임.
            if len(outcomes) % _STOCK_INVESTOR_BREAKDOWN_BATCH == 0:
                logger.debug(
                    "ka10059 bulk progress — completed=%d / total=%d",
                    len(outcomes),
                    len(stock_codes),
                )

        return StockInvestorBreakdownBulkResult(
            outcomes=tuple(outcomes),
            errors_above_threshold=(),  # D-11 임계치 미도입
        )


# ===========================================================================
# ka10131 — IngestFrgnOrgnConsecutiveUseCase + Bulk
# ===========================================================================


class IngestFrgnOrgnConsecutiveUseCase:
    """ka10131 단건 ingest — (period, market, amt_qty) 1쌍."""

    def __init__(
        self,
        *,
        client: Any,
        repository: Any,
        stock_repository: _StockLookupProtocol,
        session: AsyncSession,
    ) -> None:
        self._client = client
        self._repository = repository
        self._stock_repository = stock_repository
        self._session = session

    async def execute(
        self,
        *,
        dt: ContinuousPeriodType = ContinuousPeriodType.LATEST,
        strt_dt: str = "",
        end_dt: str = "",
        mrkt_tp: InvestorMarketType = InvestorMarketType.KOSPI,
        stk_inds_tp: StockIndsType = StockIndsType.STOCK,
        amt_qty_tp: ContinuousAmtQtyType = ContinuousAmtQtyType.AMOUNT,
        stex_tp: RankingExchangeType = RankingExchangeType.UNIFIED,
        fetched_at: datetime,
        as_of_date: Any,
    ) -> FrgnOrgnConsecutiveOutcome:
        try:
            client_result = await self._client.fetch_continuous(
                dt=dt,
                strt_dt=strt_dt,
                end_dt=end_dt,
                mrkt_tp=mrkt_tp,
                stk_inds_tp=stk_inds_tp,
                amt_qty_tp=amt_qty_tp,
                stex_tp=stex_tp,
            )
            raw_rows = _unwrap_client_rows(client_result)
        except SentinelStockCodeError:
            logger.info(
                "ka10131 sentinel skip period=%s mkt=%s amt_qty=%s",
                dt.value,
                mrkt_tp.value,
                amt_qty_tp.value,
            )
            return FrgnOrgnConsecutiveOutcome(
                fetched_at=fetched_at,
                period_type=dt.value,
                market_type=mrkt_tp.value,
                amt_qty_tp=amt_qty_tp.value,
                exchange_type=stex_tp.value,
                error=SkipReason.SENTINEL_SKIP.value,
            )
        except KiwoomBusinessError as exc:
            return FrgnOrgnConsecutiveOutcome(
                fetched_at=fetched_at,
                period_type=dt.value,
                market_type=mrkt_tp.value,
                amt_qty_tp=amt_qty_tp.value,
                exchange_type=stex_tp.value,
                error=f"business: {exc.return_code}",
            )

        if not raw_rows:
            return FrgnOrgnConsecutiveOutcome(
                fetched_at=fetched_at,
                period_type=dt.value,
                market_type=mrkt_tp.value,
                amt_qty_tp=amt_qty_tp.value,
                exchange_type=stex_tp.value,
                fetched=0,
                upserted=0,
            )

        # stock 매핑.
        codes_clean = {strip_kiwoom_suffix(r.stk_cd) for r in raw_rows}
        stocks_by_code = await self._stock_repository.find_by_codes(codes_clean)

        normalized: list[NormalizedFrgnOrgnConsecutive] = []
        for raw_row in raw_rows:
            code_clean = strip_kiwoom_suffix(raw_row.stk_cd)
            stock = stocks_by_code.get(code_clean)
            stock_id = _resolve_stock_id(stock)
            normalized.append(
                raw_row.to_normalized(
                    stock_id=stock_id,
                    as_of_date=as_of_date,
                    period_type=dt,
                    market_type=mrkt_tp,
                    amt_qty_tp=amt_qty_tp,
                    stk_inds_tp=stk_inds_tp,
                    exchange_type=stex_tp,
                )
            )

        upserted = await self._repository.upsert_many(normalized)
        return FrgnOrgnConsecutiveOutcome(
            fetched_at=fetched_at,
            period_type=dt.value,
            market_type=mrkt_tp.value,
            amt_qty_tp=amt_qty_tp.value,
            exchange_type=stex_tp.value,
            fetched=len(raw_rows),
            upserted=upserted,
        )


class IngestFrgnOrgnConsecutiveBulkUseCase:
    """ka10131 Bulk — 2 mkt × 2 amt_qty = 4 호출 (D-9/D-10)."""

    def __init__(self, *, single_use_case: IngestFrgnOrgnConsecutiveUseCase) -> None:
        self._single = single_use_case

    async def execute(
        self,
        *,
        dt: ContinuousPeriodType = ContinuousPeriodType.LATEST,
        strt_dt: str = "",
        end_dt: str = "",
        market_types: Sequence[InvestorMarketType] | None = None,
        amt_qty_types: Sequence[ContinuousAmtQtyType] | None = None,
        stk_inds_tp: StockIndsType = StockIndsType.STOCK,
        stex_tp: RankingExchangeType = RankingExchangeType.UNIFIED,
        fetched_at: datetime,
        as_of_date: Any,
    ) -> FrgnOrgnConsecutiveBulkResult:
        if market_types is not None and not market_types:
            return _empty_frgn_orgn_bulk_result()
        if amt_qty_types is not None and not amt_qty_types:
            return _empty_frgn_orgn_bulk_result()

        targets_mkt = (
            list(market_types)
            if market_types is not None
            else [InvestorMarketType.KOSPI, InvestorMarketType.KOSDAQ]
        )
        targets_aq = (
            list(amt_qty_types)
            if amt_qty_types is not None
            else [ContinuousAmtQtyType.AMOUNT, ContinuousAmtQtyType.QUANTITY]
        )

        outcomes: list[FrgnOrgnConsecutiveOutcome] = []
        for market in targets_mkt:
            for amt_qty in targets_aq:
                try:
                    outcome = await self._single.execute(
                        dt=dt,
                        strt_dt=strt_dt,
                        end_dt=end_dt,
                        mrkt_tp=market,
                        stk_inds_tp=stk_inds_tp,
                        amt_qty_tp=amt_qty,
                        stex_tp=stex_tp,
                        fetched_at=fetched_at,
                        as_of_date=as_of_date,
                    )
                except Exception as exc:  # noqa: BLE001 — partial 격리
                    logger.warning(
                        "ka10131 bulk 호출 실패 period=%s mkt=%s amt_qty=%s: %s",
                        dt.value,
                        market.value,
                        amt_qty.value,
                        type(exc).__name__,
                    )
                    outcome = FrgnOrgnConsecutiveOutcome(
                        fetched_at=fetched_at,
                        period_type=dt.value,
                        market_type=market.value,
                        amt_qty_tp=amt_qty.value,
                        exchange_type=stex_tp.value,
                        error=type(exc).__name__,
                    )
                outcomes.append(outcome)

        return FrgnOrgnConsecutiveBulkResult(
            outcomes=tuple(outcomes),
            errors_above_threshold=(),  # D-11 임계치 미도입
        )


__all__ = [
    "IngestFrgnOrgnConsecutiveBulkUseCase",
    "IngestFrgnOrgnConsecutiveUseCase",
    "IngestInvestorDailyTradeBulkUseCase",
    "IngestInvestorDailyTradeUseCase",
    "IngestStockInvestorBreakdownBulkUseCase",
    "IngestStockInvestorBreakdownUseCase",
]
