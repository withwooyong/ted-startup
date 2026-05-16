"""POST/GET /api/kiwoom/rankings/* — Phase F-4 5 ranking endpoint (ka10027/30/31/32/23).

설계: phase-f-4-rankings.md § 5.7.

라우터 구성 (5 endpoint × 3 라우터 = 15):
- POST /api/kiwoom/rankings/{endpoint}/sync?alias=...        (admin) — 단건 호출
- POST /api/kiwoom/rankings/{endpoint}/bulk-sync?alias=...   (admin) — 4-호출 매트릭스
- GET  /api/kiwoom/rankings/{endpoint}/snapshot              (DB only)

endpoint 슬러그: flu-rt / today-volume / pred-volume / trde-prica / volume-sdnin.

응답 정책 (short_selling 일관):
- POST sync / bulk-sync — RankingBulkResult 응답 (단건도 bulk factory 호출)
- POST 모두 require_admin_key 의존성
- GET snapshot — admin 무관 (DB only)
- Pydantic validation (Literal) — invalid mrkt_tp/sort_tp/stex_tp → 422
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time
from decimal import Decimal
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
    FluRtSortType,
    RankingExchangeType,
    RankingMarketType,
    RankingType,
    TodayVolumeSortType,
    VolumeSdninSortType,
)
from app.adapter.out.persistence.repositories.ranking_snapshot import (
    RankingSnapshotRepository,
)
from app.adapter.out.persistence.session import get_sessionmaker
from app.adapter.web._deps import (
    IngestFluRtBulkUseCaseFactory,
    IngestFluRtUseCaseFactory,
    IngestPredVolumeBulkUseCaseFactory,
    IngestPredVolumeUseCaseFactory,
    IngestTodayVolumeBulkUseCaseFactory,
    IngestTodayVolumeUseCaseFactory,
    IngestTradeAmountBulkUseCaseFactory,
    IngestTradeAmountUseCaseFactory,
    IngestVolumeSdninBulkUseCaseFactory,
    IngestVolumeSdninUseCaseFactory,
    get_ingest_flu_rt_bulk_factory,
    get_ingest_flu_rt_factory,
    get_ingest_pred_volume_bulk_factory,
    get_ingest_pred_volume_factory,
    get_ingest_today_volume_bulk_factory,
    get_ingest_today_volume_factory,
    get_ingest_trade_amount_bulk_factory,
    get_ingest_trade_amount_factory,
    get_ingest_volume_sdnin_bulk_factory,
    get_ingest_volume_sdnin_factory,
    require_admin_key,
)
from app.application.dto.ranking import RankingBulkResult, RankingIngestOutcome

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kiwoom/rankings", tags=["kiwoom-rankings"])

KST = ZoneInfo("Asia/Seoul")


# =============================================================================
# Pydantic DTO — request body / response
# =============================================================================


class RankingSyncRequestIn(BaseModel):
    """POST /sync body — 단건 호출 파라미터 (5 endpoint 공통, optional)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mrkt_tp: Literal["000", "001", "101"] | None = Field(
        default=None,
        description="시장 구분 — 000=전체 / 001=KOSPI / 101=KOSDAQ",
    )
    sort_tp: str | None = Field(
        default=None,
        max_length=2,
        description="정렬 구분 (endpoint 별 다름)",
    )
    stex_tp: Literal["1", "2", "3"] | None = Field(
        default=None,
        description="거래소 구분 — 1=KRX / 2=NXT / 3=통합",
    )


class RankingIngestOutcomeOut(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    ranking_type: str
    sort_tp: str
    market_type: str
    exchange_type: str
    fetched: int = 0
    upserted: int = 0
    error: str | None = None


class RankingBulkResultOut(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    ranking_type: str | None
    total_calls: int
    total_upserted: int
    total_failed: int
    outcomes: tuple[RankingIngestOutcomeOut, ...] = Field(default_factory=tuple)
    errors_above_threshold: tuple[str, ...] = Field(default_factory=tuple)


class RankingSnapshotRowOut(BaseModel):
    """ranking_snapshot row 응답 — GET snapshot."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    snapshot_date: date
    snapshot_time: time
    ranking_type: str
    sort_tp: str
    market_type: str
    exchange_type: str
    rank: int
    stock_id: int | None = None
    stock_code_raw: str
    primary_metric: Decimal | None = None
    payload: dict[str, Any]
    request_filters: dict[str, Any]


# =============================================================================
# 공통 helpers
# =============================================================================


def _bulk_result_to_out(result: Any) -> RankingBulkResultOut:
    """RankingBulkResult → response model 변환."""
    ranking_type_value = (
        result.ranking_type.value if result.ranking_type is not None else None
    )
    outcomes_out = tuple(
        RankingIngestOutcomeOut(
            ranking_type=o.ranking_type.value if o.ranking_type is not None else "",
            sort_tp=o.sort_tp,
            market_type=o.market_type,
            exchange_type=o.exchange_type,
            fetched=o.fetched,
            upserted=o.upserted,
            error=o.error,
        )
        for o in result.outcomes
    )
    return RankingBulkResultOut(
        ranking_type=ranking_type_value,
        total_calls=result.total_calls,
        total_upserted=result.total_upserted,
        total_failed=result.total_failed,
        outcomes=outcomes_out,
        errors_above_threshold=tuple(result.errors_above_threshold),
    )


async def _invoke_bulk(factory: Any, alias: str) -> RankingBulkResultOut:
    """공통 factory 호출 + KiwoomError 매핑."""
    try:
        async with factory(alias) as use_case:
            snapshot_at = datetime.now(KST)
            result = await use_case.execute(snapshot_at=snapshot_at)
    except KiwoomBusinessError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"return_code": exc.return_code, "error": "KiwoomBusinessError"},
        ) from None
    except KiwoomCredentialRejectedError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="키움 자격증명 거부",
        ) from None
    except KiwoomRateLimitedError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="키움 RPS 초과",
        ) from None
    except (KiwoomUpstreamError, KiwoomResponseValidationError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="키움 응답 오류",
        ) from None
    except KiwoomError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="키움 호출 실패",
        ) from None
    return _bulk_result_to_out(result)


async def _invoke_single(
    factory: Any,
    alias: str,
    *,
    ranking_type: RankingType,
    execute_kwargs: dict[str, Any],
) -> RankingBulkResultOut:
    """단건 호출 — body 의 mrkt_tp/sort_tp/stex_tp 로 1×1 (F-4 Step 2 fix G-3).

    Single UseCase.execute → RankingIngestOutcome 반환 → RankingBulkResult 1-outcome 래핑
    → router 응답 모델 RankingBulkResultOut 으로 직렬화 (sync/bulk-sync 응답 모델 통일).
    """
    try:
        async with factory(alias) as use_case:
            snapshot_at = datetime.now(KST)
            outcome: RankingIngestOutcome = await use_case.execute(
                snapshot_at=snapshot_at,
                **execute_kwargs,
            )
    except KiwoomBusinessError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"return_code": exc.return_code, "error": "KiwoomBusinessError"},
        ) from None
    except KiwoomCredentialRejectedError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="키움 자격증명 거부",
        ) from None
    except KiwoomRateLimitedError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="키움 RPS 초과",
        ) from None
    except (KiwoomUpstreamError, KiwoomResponseValidationError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="키움 응답 오류",
        ) from None
    except KiwoomError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="키움 호출 실패",
        ) from None

    result = RankingBulkResult(
        ranking_type=ranking_type,
        outcomes=(outcome,),
    )
    return _bulk_result_to_out(result)


async def _get_snapshot(
    *,
    snapshot_date_param: date,
    snapshot_time_param: time | None,
    ranking_type: RankingType,
    sort_tp: str,
    market_type: str,
    exchange_type: str,
    limit: int,
) -> list[RankingSnapshotRowOut]:
    """공통 snapshot GET — Repository.get_at_snapshot 위임."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        repo = RankingSnapshotRepository(session)
        # snapshot_time 미명시 시 default 19:30:00 — 운영 단일 시점 가정.
        st = snapshot_time_param or time(19, 30, 0)
        rows = await repo.get_at_snapshot(
            snapshot_date=snapshot_date_param,
            snapshot_time=st,
            ranking_type=ranking_type,
            sort_tp=sort_tp,
            market_type=market_type,
            exchange_type=exchange_type,
            limit=limit,
        )
    return [RankingSnapshotRowOut.model_validate(r) for r in rows]


# =============================================================================
# ka10027 — flu-rt
# =============================================================================


@router.post(
    "/flu-rt/sync",
    response_model=RankingBulkResultOut,
    summary="ka10027 등락률 ranking 단건 호출 (admin)",
    dependencies=[Depends(require_admin_key)],
)
async def sync_flu_rt(
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_\-]{1,50}$"),
    ],
    body: RankingSyncRequestIn,
    factory: IngestFluRtUseCaseFactory = Depends(get_ingest_flu_rt_factory),
) -> RankingBulkResultOut:
    """단건 호출 — body 의 mrkt_tp/sort_tp/stex_tp 로 1×1 (F-4 Step 2 fix G-3).

    default: mrkt_tp="001" / sort_tp="1" (UP_RATE) / stex_tp="3" (UNIFIED).
    body validation 으로 invalid 값은 422 (Literal 검증).
    """
    market = RankingMarketType(body.mrkt_tp) if body.mrkt_tp else RankingMarketType.KOSPI
    sort = FluRtSortType(body.sort_tp) if body.sort_tp else FluRtSortType.UP_RATE
    exch = (
        RankingExchangeType(body.stex_tp) if body.stex_tp else RankingExchangeType.UNIFIED
    )
    return await _invoke_single(
        factory,
        alias,
        ranking_type=RankingType.FLU_RT,
        execute_kwargs={
            "market_type": market,
            "sort_tp": sort,
            "exchange_type": exch,
        },
    )


@router.post(
    "/flu-rt/bulk-sync",
    response_model=RankingBulkResultOut,
    summary="ka10027 등락률 ranking Bulk 4-호출 매트릭스 (admin)",
    dependencies=[Depends(require_admin_key)],
)
async def bulk_sync_flu_rt(
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_\-]{1,50}$"),
    ],
    factory: IngestFluRtBulkUseCaseFactory = Depends(get_ingest_flu_rt_bulk_factory),
) -> RankingBulkResultOut:
    """Bulk 매트릭스 — 2 market × 2 sort = 4 호출 (D-3/D-5)."""
    return await _invoke_bulk(factory, alias)


@router.get(
    "/flu-rt/snapshot",
    response_model=list[RankingSnapshotRowOut],
    summary="ka10027 등락률 snapshot 조회 (DB only)",
)
async def get_flu_rt_snapshot(
    snapshot_date: Annotated[date, Query(description="스냅샷 일자 (YYYY-MM-DD)")],
    mrkt_tp: Annotated[
        Literal["000", "001", "101"], Query(description="시장 구분")
    ] = "001",
    sort_tp: Annotated[Literal["1", "2", "3", "4", "5"], Query()] = "1",
    stex_tp: Annotated[Literal["1", "2", "3"], Query()] = "3",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[RankingSnapshotRowOut]:
    return await _get_snapshot(
        snapshot_date_param=snapshot_date,
        snapshot_time_param=None,
        ranking_type=RankingType.FLU_RT,
        sort_tp=sort_tp,
        market_type=mrkt_tp,
        exchange_type=stex_tp,
        limit=limit,
    )


# =============================================================================
# ka10030 — today-volume
# =============================================================================


@router.post(
    "/today-volume/sync",
    response_model=RankingBulkResultOut,
    summary="ka10030 당일 거래량 ranking 단건 (admin)",
    dependencies=[Depends(require_admin_key)],
)
async def sync_today_volume(
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_\-]{1,50}$"),
    ],
    body: RankingSyncRequestIn,
    factory: IngestTodayVolumeUseCaseFactory = Depends(get_ingest_today_volume_factory),
) -> RankingBulkResultOut:
    """단건 호출 — body 의 mrkt_tp/sort_tp/stex_tp 로 1×1 (F-4 Step 2 fix G-3).

    default: mrkt_tp="001" / sort_tp="1" (TRADE_VOLUME) / stex_tp="3" (UNIFIED).
    """
    market = RankingMarketType(body.mrkt_tp) if body.mrkt_tp else RankingMarketType.KOSPI
    sort = (
        TodayVolumeSortType(body.sort_tp)
        if body.sort_tp
        else TodayVolumeSortType.TRADE_VOLUME
    )
    exch = (
        RankingExchangeType(body.stex_tp) if body.stex_tp else RankingExchangeType.UNIFIED
    )
    return await _invoke_single(
        factory,
        alias,
        ranking_type=RankingType.TODAY_VOLUME,
        execute_kwargs={
            "market_type": market,
            "sort_tp": sort,
            "exchange_type": exch,
        },
    )


@router.post(
    "/today-volume/bulk-sync",
    response_model=RankingBulkResultOut,
    summary="ka10030 당일 거래량 ranking Bulk (admin)",
    dependencies=[Depends(require_admin_key)],
)
async def bulk_sync_today_volume(
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_\-]{1,50}$"),
    ],
    factory: IngestTodayVolumeBulkUseCaseFactory = Depends(
        get_ingest_today_volume_bulk_factory
    ),
) -> RankingBulkResultOut:
    return await _invoke_bulk(factory, alias)


@router.get(
    "/today-volume/snapshot",
    response_model=list[RankingSnapshotRowOut],
    summary="ka10030 당일 거래량 snapshot 조회 (DB only)",
)
async def get_today_volume_snapshot(
    snapshot_date: Annotated[date, Query(description="스냅샷 일자 (YYYY-MM-DD)")],
    mrkt_tp: Annotated[
        Literal["000", "001", "101"], Query(description="시장 구분")
    ] = "001",
    sort_tp: Annotated[Literal["1", "2", "3"], Query()] = "1",
    stex_tp: Annotated[Literal["1", "2", "3"], Query()] = "3",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[RankingSnapshotRowOut]:
    return await _get_snapshot(
        snapshot_date_param=snapshot_date,
        snapshot_time_param=None,
        ranking_type=RankingType.TODAY_VOLUME,
        sort_tp=sort_tp,
        market_type=mrkt_tp,
        exchange_type=stex_tp,
        limit=limit,
    )


# =============================================================================
# ka10031 — pred-volume
# =============================================================================


@router.post(
    "/pred-volume/sync",
    response_model=RankingBulkResultOut,
    summary="ka10031 전일 거래량 ranking 단건 (admin)",
    dependencies=[Depends(require_admin_key)],
)
async def sync_pred_volume(
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_\-]{1,50}$"),
    ],
    body: RankingSyncRequestIn,
    factory: IngestPredVolumeUseCaseFactory = Depends(get_ingest_pred_volume_factory),
) -> RankingBulkResultOut:
    """단건 호출 — body 의 mrkt_tp/stex_tp 로 1×1 (F-4 Step 2 fix G-3).

    ka10031 은 sort_tp 단일 ("0") — body.sort_tp 는 무시 (UseCase 시그니처에 없음).
    default: mrkt_tp="001" / stex_tp="3" (UNIFIED).
    """
    market = RankingMarketType(body.mrkt_tp) if body.mrkt_tp else RankingMarketType.KOSPI
    exch = (
        RankingExchangeType(body.stex_tp) if body.stex_tp else RankingExchangeType.UNIFIED
    )
    return await _invoke_single(
        factory,
        alias,
        ranking_type=RankingType.PRED_VOLUME,
        execute_kwargs={
            "market_type": market,
            "exchange_type": exch,
        },
    )


@router.post(
    "/pred-volume/bulk-sync",
    response_model=RankingBulkResultOut,
    summary="ka10031 전일 거래량 ranking Bulk (admin)",
    dependencies=[Depends(require_admin_key)],
)
async def bulk_sync_pred_volume(
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_\-]{1,50}$"),
    ],
    factory: IngestPredVolumeBulkUseCaseFactory = Depends(
        get_ingest_pred_volume_bulk_factory
    ),
) -> RankingBulkResultOut:
    return await _invoke_bulk(factory, alias)


@router.get(
    "/pred-volume/snapshot",
    response_model=list[RankingSnapshotRowOut],
    summary="ka10031 전일 거래량 snapshot 조회 (DB only)",
)
async def get_pred_volume_snapshot(
    snapshot_date: Annotated[date, Query(description="스냅샷 일자 (YYYY-MM-DD)")],
    mrkt_tp: Annotated[
        Literal["000", "001", "101"], Query(description="시장 구분")
    ] = "001",
    sort_tp: Annotated[Literal["0", "1"], Query()] = "0",
    stex_tp: Annotated[Literal["1", "2", "3"], Query()] = "3",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[RankingSnapshotRowOut]:
    return await _get_snapshot(
        snapshot_date_param=snapshot_date,
        snapshot_time_param=None,
        ranking_type=RankingType.PRED_VOLUME,
        sort_tp=sort_tp,
        market_type=mrkt_tp,
        exchange_type=stex_tp,
        limit=limit,
    )


# =============================================================================
# ka10032 — trde-prica
# =============================================================================


@router.post(
    "/trde-prica/sync",
    response_model=RankingBulkResultOut,
    summary="ka10032 거래대금 ranking 단건 (admin)",
    dependencies=[Depends(require_admin_key)],
)
async def sync_trde_prica(
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_\-]{1,50}$"),
    ],
    body: RankingSyncRequestIn,
    factory: IngestTradeAmountUseCaseFactory = Depends(get_ingest_trade_amount_factory),
) -> RankingBulkResultOut:
    """단건 호출 — body 의 mrkt_tp/stex_tp 로 1×1 (F-4 Step 2 fix G-3).

    ka10032 는 sort_tp 단일 ("0") — body.sort_tp 는 무시 (UseCase 시그니처에 없음).
    default: mrkt_tp="001" / stex_tp="3" (UNIFIED).
    """
    market = RankingMarketType(body.mrkt_tp) if body.mrkt_tp else RankingMarketType.KOSPI
    exch = (
        RankingExchangeType(body.stex_tp) if body.stex_tp else RankingExchangeType.UNIFIED
    )
    return await _invoke_single(
        factory,
        alias,
        ranking_type=RankingType.TRDE_PRICA,
        execute_kwargs={
            "market_type": market,
            "exchange_type": exch,
        },
    )


@router.post(
    "/trde-prica/bulk-sync",
    response_model=RankingBulkResultOut,
    summary="ka10032 거래대금 ranking Bulk (admin)",
    dependencies=[Depends(require_admin_key)],
)
async def bulk_sync_trde_prica(
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_\-]{1,50}$"),
    ],
    factory: IngestTradeAmountBulkUseCaseFactory = Depends(
        get_ingest_trade_amount_bulk_factory
    ),
) -> RankingBulkResultOut:
    return await _invoke_bulk(factory, alias)


@router.get(
    "/trde-prica/snapshot",
    response_model=list[RankingSnapshotRowOut],
    summary="ka10032 거래대금 snapshot 조회 (DB only)",
)
async def get_trde_prica_snapshot(
    snapshot_date: Annotated[date, Query(description="스냅샷 일자 (YYYY-MM-DD)")],
    mrkt_tp: Annotated[
        Literal["000", "001", "101"], Query(description="시장 구분")
    ] = "001",
    sort_tp: Annotated[Literal["0", "1"], Query()] = "0",
    stex_tp: Annotated[Literal["1", "2", "3"], Query()] = "3",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[RankingSnapshotRowOut]:
    return await _get_snapshot(
        snapshot_date_param=snapshot_date,
        snapshot_time_param=None,
        ranking_type=RankingType.TRDE_PRICA,
        sort_tp=sort_tp,
        market_type=mrkt_tp,
        exchange_type=stex_tp,
        limit=limit,
    )


# =============================================================================
# ka10023 — volume-sdnin
# =============================================================================


@router.post(
    "/volume-sdnin/sync",
    response_model=RankingBulkResultOut,
    summary="ka10023 거래량 급증 ranking 단건 (admin)",
    dependencies=[Depends(require_admin_key)],
)
async def sync_volume_sdnin(
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_\-]{1,50}$"),
    ],
    body: RankingSyncRequestIn,
    factory: IngestVolumeSdninUseCaseFactory = Depends(get_ingest_volume_sdnin_factory),
) -> RankingBulkResultOut:
    """단건 호출 — body 의 mrkt_tp/sort_tp/stex_tp 로 1×1 (F-4 Step 2 fix G-3).

    ka10023 — sort_tp default "1" (SUDDEN_VOLUME). tm_tp 는 UseCase default 사용.
    default: mrkt_tp="001" / sort_tp="1" / stex_tp="3".
    """
    market = RankingMarketType(body.mrkt_tp) if body.mrkt_tp else RankingMarketType.KOSPI
    sort = (
        VolumeSdninSortType(body.sort_tp)
        if body.sort_tp
        else VolumeSdninSortType.SUDDEN_VOLUME
    )
    exch = (
        RankingExchangeType(body.stex_tp) if body.stex_tp else RankingExchangeType.UNIFIED
    )
    return await _invoke_single(
        factory,
        alias,
        ranking_type=RankingType.VOLUME_SDNIN,
        execute_kwargs={
            "market_type": market,
            "sort_tp": sort,
            "exchange_type": exch,
        },
    )


@router.post(
    "/volume-sdnin/bulk-sync",
    response_model=RankingBulkResultOut,
    summary="ka10023 거래량 급증 ranking Bulk (admin)",
    dependencies=[Depends(require_admin_key)],
)
async def bulk_sync_volume_sdnin(
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_\-]{1,50}$"),
    ],
    factory: IngestVolumeSdninBulkUseCaseFactory = Depends(
        get_ingest_volume_sdnin_bulk_factory
    ),
) -> RankingBulkResultOut:
    return await _invoke_bulk(factory, alias)


@router.get(
    "/volume-sdnin/snapshot",
    response_model=list[RankingSnapshotRowOut],
    summary="ka10023 거래량 급증 snapshot 조회 (DB only)",
)
async def get_volume_sdnin_snapshot(
    snapshot_date: Annotated[date, Query(description="스냅샷 일자 (YYYY-MM-DD)")],
    mrkt_tp: Annotated[
        Literal["000", "001", "101"], Query(description="시장 구분")
    ] = "001",
    sort_tp: Annotated[Literal["1", "2"], Query()] = "1",
    stex_tp: Annotated[Literal["1", "2", "3"], Query()] = "3",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[RankingSnapshotRowOut]:
    return await _get_snapshot(
        snapshot_date_param=snapshot_date,
        snapshot_time_param=None,
        ranking_type=RankingType.VOLUME_SDNIN,
        sort_tp=sort_tp,
        market_type=mrkt_tp,
        exchange_type=stex_tp,
        limit=limit,
    )


__all__ = [
    "RankingBulkResultOut",
    "RankingIngestOutcomeOut",
    "RankingSnapshotRowOut",
    "RankingSyncRequestIn",
    "router",
]
