"""POST/GET /api/kiwoom/investor/* + /api/kiwoom/foreign/continuous — Phase G 라우터 (~9 endpoint).

설계: phase-g-investor-flow.md § 5.7.

라우터 구성:
- /api/kiwoom/investor/daily — ka10058 (3 라우터: sync POST / bulk-sync POST / top GET)
- /api/kiwoom/investor/stock — ka10059 (3 라우터)
- /api/kiwoom/foreign/continuous — ka10131 (3 라우터)

응답 정책 (F-4 ranking_router 일관):
- POST sync — 단건 outcome (각 endpoint 의 IngestOutcome).
- POST bulk-sync — BulkResult (3종 dataclass).
- POST 모두 ``require_admin_key`` 의존성.
- GET top — admin 무관 (DB only).
- ``_invoke_single`` helper × 3 (G-3 패턴 미러).
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import date, datetime
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.adapter.out.kiwoom._exceptions import (
    KiwoomBusinessError,
    KiwoomCredentialRejectedError,
    KiwoomError,
    KiwoomRateLimitedError,
    KiwoomResponseValidationError,
    KiwoomUpstreamError,
)
from app.adapter.out.kiwoom._records import (
    AmountQuantityType,
    ContinuousAmtQtyType,
    ContinuousPeriodType,
    InvestorMarketType,
    InvestorTradeType,
    InvestorType,
    RankingExchangeType,
    StockIndsType,
    StockInvestorTradeType,
    UnitType,
)
from app.adapter.out.kiwoom.stkinfo import strip_kiwoom_suffix
from app.adapter.out.persistence.repositories.frgn_orgn_consecutive import (
    FrgnOrgnConsecutiveRepository,
)
from app.adapter.out.persistence.repositories.investor_flow_daily import (
    InvestorFlowDailyRepository,
)
from app.adapter.out.persistence.repositories.stock import StockRepository
from app.adapter.out.persistence.repositories.stock_investor_breakdown import (
    StockInvestorBreakdownRepository,
)
from app.adapter.out.persistence.session import get_sessionmaker
from app.adapter.web._deps import (
    IngestFrgnOrgnBulkUseCaseFactory,
    IngestFrgnOrgnUseCaseFactory,
    IngestInvestorDailyBulkUseCaseFactory,
    IngestInvestorDailyUseCaseFactory,
    IngestStockInvestorBreakdownBulkUseCaseFactory,
    IngestStockInvestorBreakdownUseCaseFactory,
    get_ingest_frgn_orgn_bulk_factory,
    get_ingest_frgn_orgn_factory,
    get_ingest_investor_daily_bulk_factory,
    get_ingest_investor_daily_factory,
    get_ingest_stock_investor_breakdown_bulk_factory,
    get_ingest_stock_investor_breakdown_factory,
    require_admin_key,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kiwoom", tags=["kiwoom-investor-flow"])

KST = ZoneInfo("Asia/Seoul")


# =============================================================================
# Pydantic DTO — request body / response
# =============================================================================


class InvestorDailySyncRequestIn(BaseModel):
    """ka10058 POST /daily/sync body — 단건 호출."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    strt_dt: Annotated[str, Field(pattern=r"^\d{8}$")]
    end_dt: Annotated[str, Field(pattern=r"^\d{8}$")]
    invsr_tp: Literal[
        "8000", "9000", "9999", "1000", "2000", "3000",
        "3100", "4000", "5000", "6000", "7000", "7100",
    ]
    trde_tp: Literal["1", "2"]
    mrkt_tp: Literal["001", "101"]
    stex_tp: Literal["1", "2", "3"] = "3"


class InvestorDailyBulkSyncRequestIn(BaseModel):
    """ka10058 POST /daily/bulk-sync body — 매트릭스 호출."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    strt_dt: Annotated[str, Field(pattern=r"^\d{8}$")]
    end_dt: Annotated[str, Field(pattern=r"^\d{8}$")]
    stex_tp: Literal["1", "2", "3"] = "3"


class StockInvestorBreakdownSyncRequestIn(BaseModel):
    """ka10059 POST /stock/sync body — 단건 호출."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dt: Annotated[str, Field(pattern=r"^\d{8}$")]
    stk_cd: Annotated[str, Field(min_length=6, max_length=20)]
    amt_qty_tp: Literal["1", "2"] = "2"
    trde_tp: Literal["0", "1", "2"] = "0"
    unit_tp: Literal["1", "1000"] = "1000"
    stex_tp: Literal["1", "2", "3"] = "3"


class StockInvestorBreakdownBulkSyncRequestIn(BaseModel):
    """ka10059 POST /stock/bulk-sync body — active 종목 ~3000 (3000 호출).

    Step 2 R1 C-6: ``stock_codes`` 필드 추가 — None 이면 ``StockRepository.list_by_filters
    (only_active=True)`` 의 active 종목 전체 사용 (D-7 a). 명시 list 시 그 종목만 호출.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    dt: Annotated[str, Field(pattern=r"^\d{8}$")]
    stock_codes: list[str] | None = Field(
        default=None,
        description=(
            "명시 종목 list (None 이면 active 종목 전체 ~3000 — D-7 a). "
            "각 항목은 6~20자 종목코드 (NXT _NX suffix 허용)."
        ),
    )
    amt_qty_tp: Literal["1", "2"] = "2"
    trde_tp: Literal["0", "1", "2"] = "0"
    unit_tp: Literal["1", "1000"] = "1000"
    stex_tp: Literal["1", "2", "3"] = "3"


class FrgnOrgnContinuousSyncRequestIn(BaseModel):
    """ka10131 POST /foreign/continuous/sync body — 단건 호출.

    Step 2 R1 H-1: Pydantic v2 ``Annotated[str | None, Field(...)] = None`` syntax.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    dt: Literal["1", "3", "5", "10", "20", "120", "0"]
    strt_dt: Annotated[str | None, Field(pattern=r"^\d{8}$")] = None
    end_dt: Annotated[str | None, Field(pattern=r"^\d{8}$")] = None
    mrkt_tp: Literal["001", "101"]
    stk_inds_tp: Literal["0", "1"] = "0"
    amt_qty_tp: Literal["0", "1"]
    stex_tp: Literal["1", "2", "3"] = "3"


class FrgnOrgnContinuousBulkSyncRequestIn(BaseModel):
    """ka10131 POST /foreign/continuous/bulk-sync body — 매트릭스 호출.

    Step 2 R1 M-1: ``extra="forbid"`` 로 변경 — 알 수 없는 필드 거부 (오타 방어).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    dt: Literal["1", "3", "5", "10", "20", "120", "0"] = "1"
    stk_inds_tp: Literal["0", "1"] = "0"
    stex_tp: Literal["1", "2", "3"] = "3"


class GenericOutcomeOut(BaseModel):
    """단건 / Bulk outcome 공통 응답 (간이)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    payload: dict[str, Any]


# =============================================================================
# 공통 helpers — _invoke_single × 3 (G-3 패턴)
# =============================================================================


def _kiwoom_error_to_http(exc: Exception) -> HTTPException:
    """KiwoomError → HTTPException 매핑."""
    if isinstance(exc, KiwoomBusinessError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"return_code": exc.return_code, "error": "KiwoomBusinessError"},
        )
    if isinstance(exc, KiwoomCredentialRejectedError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="키움 자격증명 거부",
        )
    if isinstance(exc, KiwoomRateLimitedError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="키움 RPS 초과",
        )
    if isinstance(exc, KiwoomUpstreamError | KiwoomResponseValidationError):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="키움 응답 오류",
        )
    if isinstance(exc, KiwoomError):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="키움 호출 실패",
        )
    return HTTPException(status_code=500, detail="internal error")


# =============================================================================
# ka10058 — /api/kiwoom/investor/daily
# =============================================================================


@router.post(
    "/investor/daily/sync",
    summary="ka10058 투자자별 일별 매매 종목 ranking 단건 (admin)",
    dependencies=[Depends(require_admin_key)],
)
async def sync_investor_daily(
    body: InvestorDailySyncRequestIn,
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_\-]{1,50}$"),
    ] = "prod-main",
    factory: IngestInvestorDailyUseCaseFactory = Depends(get_ingest_investor_daily_factory),
) -> dict[str, Any]:
    """ka10058 단건 — body 의 (invsr_tp, trde_tp, mrkt_tp, stex_tp) 1×1 (G-3)."""
    try:
        async with factory(alias) as use_case:
            fetched_at = datetime.now(KST)
            outcome = await use_case.execute(
                strt_dt=body.strt_dt,
                end_dt=body.end_dt,
                investor_type=InvestorType(body.invsr_tp),
                trade_type=InvestorTradeType(body.trde_tp),
                market_type=InvestorMarketType(body.mrkt_tp),
                exchange_type=RankingExchangeType(body.stex_tp),
                fetched_at=fetched_at,
            )
    except KiwoomError as exc:
        raise _kiwoom_error_to_http(exc) from None
    return asdict(outcome)


@router.post(
    "/investor/daily/bulk-sync",
    summary="ka10058 투자자별 일별 매매 종목 Bulk (admin)",
    dependencies=[Depends(require_admin_key)],
)
async def bulk_sync_investor_daily(
    body: InvestorDailyBulkSyncRequestIn,
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_\-]{1,50}$"),
    ] = "prod-main",
    factory: IngestInvestorDailyBulkUseCaseFactory = Depends(
        get_ingest_investor_daily_bulk_factory
    ),
) -> dict[str, Any]:
    """ka10058 Bulk — 2 mkt × 3 inv × 2 trde = 12 호출 default (D-3/D-4/D-5)."""
    try:
        async with factory(alias) as use_case:
            fetched_at = datetime.now(KST)
            result = await use_case.execute(
                strt_dt=body.strt_dt,
                end_dt=body.end_dt,
                exchange_type=RankingExchangeType(body.stex_tp),
                fetched_at=fetched_at,
            )
    except KiwoomError as exc:
        raise _kiwoom_error_to_http(exc) from None
    return {
        "total_calls": result.total_calls,
        "total_upserted": result.total_upserted,
        "total_failed": result.total_failed,
        "errors_above_threshold": list(result.errors_above_threshold),
        "outcomes": [asdict(o) for o in result.outcomes],
    }


@router.get(
    "/investor/daily/top",
    summary="ka10058 투자자별 일별 매매 상위 종목 조회 (DB only)",
)
async def get_investor_daily_top(
    as_of_date: Annotated[date, Query(description="조회 일자")],
    investor_type: Annotated[
        Literal[
            "8000", "9000", "9999", "1000", "2000", "3000",
            "3100", "4000", "5000", "6000", "7000", "7100",
        ],
        Query(),
    ] = "9000",
    trade_type: Annotated[Literal["1", "2"], Query()] = "2",
    market_type: Annotated[Literal["001", "101"], Query()] = "001",
    exchange_type: Annotated[Literal["1", "2", "3"], Query()] = "3",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict[str, Any]]:
    """투자자별 매매 종목 상위 N (rank ASC)."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        repo = InvestorFlowDailyRepository(session)
        rows = await repo.get_top_stocks(
            as_of_date=as_of_date,
            investor_type=InvestorType(investor_type),
            trade_type=InvestorTradeType(trade_type),
            market_type=InvestorMarketType(market_type),
            exchange_type=RankingExchangeType(exchange_type),
            limit=limit,
        )
    return [
        {
            "as_of_date": r.as_of_date.isoformat(),
            "rank": r.rank,
            "stock_code_raw": r.stock_code_raw,
            "stock_name": r.stock_name,
            "investor_type": r.investor_type,
            "trade_type": r.trade_type,
            "market_type": r.market_type,
            "exchange_type": r.exchange_type,
            "net_volume": r.net_volume,
            "net_amount": r.net_amount,
            "stock_id": r.stock_id,
        }
        for r in rows
    ]


# =============================================================================
# ka10059 — /api/kiwoom/investor/stock
# =============================================================================


@router.post(
    "/investor/stock/sync",
    summary="ka10059 종목별 투자자 wide breakdown 단건 (admin)",
    dependencies=[Depends(require_admin_key)],
)
async def sync_stock_investor_breakdown(
    body: StockInvestorBreakdownSyncRequestIn,
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_\-]{1,50}$"),
    ] = "prod-main",
    factory: IngestStockInvestorBreakdownUseCaseFactory = Depends(
        get_ingest_stock_investor_breakdown_factory
    ),
) -> dict[str, Any]:
    """ka10059 단건 — (stock_code, dt) 1쌍 (G-3).

    Step 2 R1 C-7 / H-6: ``StockRepository.find_by_codes([stk_cd])`` 로 stock_id lookup.
    miss 시 ``stock_id=None`` 으로 적재 (NULL row 보존, D-12 정책).
    """
    # 종목 코드 → stock_id lookup (R1 C-7 / H-6). lookup miss 면 None.
    code_clean = strip_kiwoom_suffix(body.stk_cd)
    sessionmaker = get_sessionmaker()
    resolved_stock_id: int | None = None
    async with sessionmaker() as session:
        stock_repo = StockRepository(session)
        stocks_by_code = await stock_repo.find_by_codes([code_clean])
        stock_obj = stocks_by_code.get(code_clean)
        if stock_obj is not None:
            resolved_stock_id = stock_obj.id

    try:
        async with factory(alias) as use_case:
            fetched_at = datetime.now(KST)
            outcome = await use_case.execute(
                stock_id=resolved_stock_id,
                stk_cd=body.stk_cd,
                dt=body.dt,
                amt_qty_tp=AmountQuantityType(body.amt_qty_tp),
                trade_type=StockInvestorTradeType(body.trde_tp),
                unit_tp=UnitType(body.unit_tp),
                exchange_type=RankingExchangeType(body.stex_tp),
                fetched_at=fetched_at,
            )
    except KiwoomError as exc:
        raise _kiwoom_error_to_http(exc) from None
    return asdict(outcome)


@router.post(
    "/investor/stock/bulk-sync",
    summary="ka10059 종목별 wide breakdown Bulk (active 종목 ~3000, admin)",
    dependencies=[Depends(require_admin_key)],
)
async def bulk_sync_stock_investor_breakdown(
    body: StockInvestorBreakdownBulkSyncRequestIn,
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_\-]{1,50}$"),
    ] = "prod-main",
    factory: IngestStockInvestorBreakdownBulkUseCaseFactory = Depends(
        get_ingest_stock_investor_breakdown_bulk_factory
    ),
) -> dict[str, Any]:
    """ka10059 Bulk — active 종목 ~3000 호출. 60분 sync 예상 (RPS 4 + 250ms).

    Step 2 R1 C-6: ``body.stock_codes`` None 이면 active 종목 전체 (~3000) 호출,
    명시 list 시 그 종목만 호출. ``stock_id_map`` 은 ``StockRepository.find_by_codes``
    로 빌드.
    """
    # 종목 list 빌드 (R1 C-6).
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        stock_repo = StockRepository(session)
        if body.stock_codes is None:
            # active 종목 전체 (D-7 a).
            active_stocks = await stock_repo.list_by_filters(only_active=True)
            stock_codes = [s.stock_code for s in active_stocks]
            stock_id_map = {s.stock_code: s.id for s in active_stocks}
        else:
            cleaned = [strip_kiwoom_suffix(c) for c in body.stock_codes]
            stocks_by_code = await stock_repo.find_by_codes(cleaned)
            stock_codes = list(body.stock_codes)
            stock_id_map = {
                strip_kiwoom_suffix(c): stocks_by_code[strip_kiwoom_suffix(c)].id
                for c in body.stock_codes
                if strip_kiwoom_suffix(c) in stocks_by_code
            }

    try:
        async with factory(alias) as use_case:
            fetched_at = datetime.now(KST)
            result = await use_case.execute(
                stock_codes=stock_codes,
                stock_id_map=stock_id_map,
                dt=body.dt,
                amt_qty_tp=AmountQuantityType(body.amt_qty_tp),
                trade_type=StockInvestorTradeType(body.trde_tp),
                unit_tp=UnitType(body.unit_tp),
                exchange_type=RankingExchangeType(body.stex_tp),
                fetched_at=fetched_at,
            )
    except KiwoomError as exc:
        raise _kiwoom_error_to_http(exc) from None
    return {
        "total_calls": result.total_calls,
        "total_upserted": result.total_upserted,
        "total_failed": result.total_failed,
        "errors_above_threshold": list(result.errors_above_threshold),
    }


@router.get(
    "/investor/stock/top",
    summary="ka10059 종목별 wide breakdown 기간 조회 (DB only)",
)
async def get_stock_investor_breakdown_range(
    start_date: Annotated[date, Query()],
    end_date: Annotated[date, Query()],
    stock_id: Annotated[int | None, Query(ge=1)] = None,
    amt_qty_tp: Annotated[Literal["1", "2"], Query()] = "2",
    trade_type: Annotated[Literal["0", "1", "2"], Query()] = "0",
    exchange_type: Annotated[Literal["1", "2", "3"], Query()] = "3",
) -> list[dict[str, Any]]:
    """단일 종목 기간 조회.

    Step 2 R1 H-2: ``stock_id`` 옵션화 — None 시 stock_id IS NULL row 조회 (lookup miss
    보존 데이터). 명시 시 그 종목만 조회 (기존 동작 유지).
    """
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        repo = StockInvestorBreakdownRepository(session)
        rows = await repo.get_range_optional_stock(
            stock_id=stock_id,
            start_date=start_date,
            end_date=end_date,
            amt_qty_tp=AmountQuantityType(amt_qty_tp),
            trade_type=StockInvestorTradeType(trade_type),
            exchange_type=RankingExchangeType(exchange_type),
        )
    return [
        {
            "stock_id": r.stock_id,
            "trading_date": r.trading_date.isoformat(),
            "amt_qty_tp": r.amt_qty_tp,
            "trade_type": r.trade_type,
            "unit_tp": r.unit_tp,
            "exchange_type": r.exchange_type,
            "change_rate": str(r.change_rate) if r.change_rate is not None else None,
            "net_individual": r.net_individual,
            "net_foreign": r.net_foreign,
            "net_institution_total": r.net_institution_total,
        }
        for r in rows
    ]


# =============================================================================
# ka10131 — /api/kiwoom/foreign/continuous
# =============================================================================


@router.post(
    "/foreign/continuous/sync",
    summary="ka10131 기관/외국인 연속매매 ranking 단건 (admin)",
    dependencies=[Depends(require_admin_key)],
)
async def sync_frgn_orgn_continuous(
    body: FrgnOrgnContinuousSyncRequestIn,
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_\-]{1,50}$"),
    ] = "prod-main",
    factory: IngestFrgnOrgnUseCaseFactory = Depends(get_ingest_frgn_orgn_factory),
) -> dict[str, Any]:
    """ka10131 단건 — (period, market, amt_qty) 1쌍 (G-3)."""
    try:
        async with factory(alias) as use_case:
            fetched_at = datetime.now(KST)
            outcome = await use_case.execute(
                dt=ContinuousPeriodType(body.dt),
                strt_dt=body.strt_dt or "",
                end_dt=body.end_dt or "",
                mrkt_tp=InvestorMarketType(body.mrkt_tp),
                stk_inds_tp=StockIndsType(body.stk_inds_tp),
                amt_qty_tp=ContinuousAmtQtyType(body.amt_qty_tp),
                stex_tp=RankingExchangeType(body.stex_tp),
                fetched_at=fetched_at,
                as_of_date=fetched_at.date(),
            )
    except KiwoomError as exc:
        raise _kiwoom_error_to_http(exc) from None
    return asdict(outcome)


@router.post(
    "/foreign/continuous/bulk-sync",
    summary="ka10131 기관/외국인 연속매매 Bulk (2 mkt × 2 amt_qty = 4 호출, admin)",
    dependencies=[Depends(require_admin_key)],
)
async def bulk_sync_frgn_orgn_continuous(
    body: FrgnOrgnContinuousBulkSyncRequestIn,
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_\-]{1,50}$"),
    ] = "prod-main",
    factory: IngestFrgnOrgnBulkUseCaseFactory = Depends(get_ingest_frgn_orgn_bulk_factory),
) -> dict[str, Any]:
    """ka10131 Bulk — 2 mkt × 2 amt_qty = 4 호출 (D-9/D-10)."""
    try:
        async with factory(alias) as use_case:
            fetched_at = datetime.now(KST)
            result = await use_case.execute(
                dt=ContinuousPeriodType(body.dt),
                stk_inds_tp=StockIndsType(body.stk_inds_tp),
                stex_tp=RankingExchangeType(body.stex_tp),
                fetched_at=fetched_at,
                as_of_date=fetched_at.date(),
            )
    except KiwoomError as exc:
        raise _kiwoom_error_to_http(exc) from None
    return {
        "total_calls": result.total_calls,
        "total_upserted": result.total_upserted,
        "total_failed": result.total_failed,
        "errors_above_threshold": list(result.errors_above_threshold),
        "outcomes": [asdict(o) for o in result.outcomes],
    }


@router.get(
    "/foreign/continuous/top",
    summary="ka10131 기관/외국인 연속순매수 일수 상위 종목 조회 (DB only)",
)
async def get_frgn_orgn_continuous_top(
    as_of_date: Annotated[date, Query()],
    market_type: Annotated[Literal["001", "101"], Query()] = "001",
    period_type: Annotated[
        Literal["1", "3", "5", "10", "20", "120", "0"], Query()
    ] = "1",
    stk_inds_tp: Annotated[Literal["0", "1"], Query()] = "0",
    exchange_type: Annotated[Literal["1", "2", "3"], Query()] = "3",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict[str, Any]]:
    """합계 연속순매수 일수 상위 종목 (시그널 핵심 — Phase H derived feature)."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        repo = FrgnOrgnConsecutiveRepository(session)
        rows = await repo.get_top_by_total_days(
            as_of_date=as_of_date,
            period_type=ContinuousPeriodType(period_type),
            market_type=InvestorMarketType(market_type),
            stk_inds_tp=StockIndsType(stk_inds_tp),
            exchange_type=RankingExchangeType(exchange_type),
            limit=limit,
        )
    return [
        {
            "as_of_date": r.as_of_date.isoformat(),
            "rank": r.rank,
            "stock_code_raw": r.stock_code_raw,
            "stock_name": r.stock_name,
            "period_type": r.period_type,
            "market_type": r.market_type,
            "amt_qty_tp": r.amt_qty_tp,
            "total_cont_days": r.total_cont_days,
            "orgn_cont_days": r.orgn_cont_days,
            "frgnr_cont_days": r.frgnr_cont_days,
            "stock_id": r.stock_id,
        }
        for r in rows
    ]


__all__ = [
    "FrgnOrgnContinuousBulkSyncRequestIn",
    "FrgnOrgnContinuousSyncRequestIn",
    "InvestorDailyBulkSyncRequestIn",
    "InvestorDailySyncRequestIn",
    "StockInvestorBreakdownBulkSyncRequestIn",
    "StockInvestorBreakdownSyncRequestIn",
    "router",
]
