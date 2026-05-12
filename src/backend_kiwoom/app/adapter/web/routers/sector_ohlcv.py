"""POST /api/kiwoom/sectors/{id}/ohlcv/daily/refresh + sync — D-1 라우터.

설계: endpoint-13-ka20006.md § 7.1 + § 12.

ka10094 ohlcv_periodic.py 의 sync 전체 + refresh 단건 패턴 응용 — period dispatch 없음
(단일 endpoint). admin API key 보호.

특징 (plan § 12):
- #5 sector_master_missing → 404 매핑
- #4 NXT skip → 200 + skipped=True (UseCase 가드)
- ValueError → 400 매핑 (base_date 범위 외 / inds_cd 사전 검증)
- KiwoomBusinessError → 400 (message echo 차단)
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.adapter.out.kiwoom._exceptions import (
    KiwoomBusinessError,
    KiwoomCredentialRejectedError,
    KiwoomError,
    KiwoomRateLimitedError,
    KiwoomResponseValidationError,
    KiwoomUpstreamError,
)
from app.adapter.web._deps import (
    IngestSectorDailyBulkUseCaseFactory,
    IngestSectorDailySingleUseCaseFactory,
    get_ingest_sector_daily_factory,
    get_ingest_sector_single_factory,
    require_admin_key,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kiwoom/sectors", tags=["kiwoom-sector-ohlcv"])


# =============================================================================
# Pydantic 응답 DTO
# =============================================================================


class SectorIngestOutcomeOut(BaseModel):
    """단일 sector ingest 결과 응답."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    upserted: int = 0
    skipped: bool = False
    reason: str | None = None
    sector_id: int | None = None
    sector_code: str | None = None


class SectorBulkSyncResultOut(BaseModel):
    """bulk sync 결과 응답."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    total: int
    success: int
    failed: int
    errors: tuple[str, ...] = Field(default_factory=tuple)


# =============================================================================
# POST /sectors/ohlcv/daily/sync — bulk admin
# =============================================================================


@router.post(
    "/ohlcv/daily/sync",
    response_model=SectorBulkSyncResultOut,
    summary="active sector 전체 일봉 OHLCV 동기화 (admin, ka20006)",
    dependencies=[Depends(require_admin_key)],
)
async def sync_sector_daily(
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, description="키움 자격증명 alias"),
    ],
    base_date: Annotated[
        date | None,
        Query(description="기준일자. None 이면 today"),
    ] = None,
    factory: IngestSectorDailyBulkUseCaseFactory = Depends(get_ingest_sector_daily_factory),
) -> SectorBulkSyncResultOut:
    """active sector 전체 일봉 sync (D-1).

    plan § 12.2 #4 — active sector 전체 iterate. NXT skip / sector_master_missing 은
    UseCase 가드.
    """
    asof = base_date or date.today()
    try:
        async with factory(alias) as use_case:
            result = await use_case.execute(base_date=asof)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None
    except KiwoomBusinessError as exc:
        logger.warning(
            "ka20006 sync business error api_id=%s return_code=%d",
            exc.api_id,
            exc.return_code,
        )
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
            detail="키움 RPS 초과 — 잠시 후 재시도",
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

    return SectorBulkSyncResultOut(
        total=result.total,
        success=result.success,
        failed=result.failed,
        errors=tuple(result.errors),
    )


# =============================================================================
# POST /sectors/{sector_id}/ohlcv/daily/refresh — 단건 admin
# =============================================================================


@router.post(
    "/{sector_id}/ohlcv/daily/refresh",
    response_model=SectorIngestOutcomeOut,
    summary="단건 sector 일봉 OHLCV 강제 새로고침 (admin, ka20006)",
    dependencies=[Depends(require_admin_key)],
)
async def refresh_sector_daily(
    sector_id: Annotated[int, Path(ge=1, description="kiwoom.sector(id) PK")],
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, description="키움 자격증명 alias"),
    ],
    base_date: Annotated[
        date | None,
        Query(description="기준일자. None 이면 today"),
    ] = None,
    factory: IngestSectorDailySingleUseCaseFactory = Depends(get_ingest_sector_single_factory),
) -> SectorIngestOutcomeOut:
    """단건 sector 일봉 새로고침 (D-1).

    plan § 12.2:
    - #5 sector_master_missing → 404
    - #4 NXT 가드는 UseCase 측 (본 라우터는 디폴트 KRX)
    """
    asof = base_date or date.today()
    try:
        async with factory(alias) as use_case:
            outcome = await use_case.execute(sector_id=sector_id, base_date=asof)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None
    except KiwoomBusinessError as exc:
        logger.warning(
            "ka20006 refresh business error api_id=%s return_code=%d",
            exc.api_id,
            exc.return_code,
        )
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
            detail="키움 RPS 초과 — 잠시 후 재시도",
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

    # sector_master_missing → 404 매핑 (plan § 12.2 #5)
    if outcome.skipped and outcome.reason == "sector_master_missing":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"sector_master_missing: sector_id={sector_id}",
        )

    return SectorIngestOutcomeOut(
        upserted=outcome.upserted,
        skipped=outcome.skipped,
        reason=outcome.reason,
        sector_id=outcome.sector_id,
        sector_code=outcome.sector_code,
    )


__all__ = [
    "SectorBulkSyncResultOut",
    "SectorIngestOutcomeOut",
    "router",
]
