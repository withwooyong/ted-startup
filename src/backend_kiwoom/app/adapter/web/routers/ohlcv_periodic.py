"""POST /api/kiwoom/ohlcv/{weekly|monthly}/sync + refresh path — C-3β 라우터.

설계: phase-c-3-weekly-monthly-ohlcv.md § 3.2 + endpoint-07-ka10082.md § 7.1.

ka10081 의 ohlcv.py (daily) 패턴 ~95% 복제 + period dispatch:
- POST /api/kiwoom/ohlcv/weekly/sync                              (admin)
- POST /api/kiwoom/ohlcv/monthly/sync                             (admin)
- POST /api/kiwoom/stocks/{code}/ohlcv/weekly/refresh             (admin)
- POST /api/kiwoom/stocks/{code}/ohlcv/monthly/refresh            (admin)

R1 정착 패턴 5종 전면 적용:
- DTO errors: tuple[OutcomeOut, ...]
- only_market_codes max_length=2 (pattern={1,2})
- StockMasterNotFoundError → 404 (subclass first 순서)
- KiwoomBusinessError → 400 (message echo 차단)

응답 정책 (ka10081 패턴 일관):
- POST sync 는 부분 성공 허용 — 200 + per-(stock,exchange) errors
- ValueError (base_date 범위) → 400
- YEARLY 는 KRX only (NXT skip) — UseCase 가드 (C-4 / b75334c)

GET 시계열 endpoint 는 본 chunk 범위 외 — 별도 chunk 또는 본 router 추가 시점에 결정.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.adapter.out.kiwoom._exceptions import (
    KiwoomBusinessError,
    KiwoomCredentialRejectedError,
    KiwoomError,
    KiwoomRateLimitedError,
    KiwoomResponseValidationError,
    KiwoomUpstreamError,
)
from app.adapter.out.kiwoom.stkinfo import STK_CD_LOOKUP_PATTERN
from app.adapter.web._deps import (
    IngestPeriodicOhlcvUseCaseFactory,
    get_ingest_periodic_ohlcv_factory,
    require_admin_key,
)
from app.application.constants import Period
from app.application.exceptions import StockMasterNotFoundError
from app.application.service.token_service import (
    AliasCapacityExceededError,
    CredentialInactiveError,
    CredentialNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kiwoom", tags=["kiwoom-ohlcv-periodic"])


def _api_id_for(period: Period) -> str:
    """logger 메시지용 — period → api_id 매핑 (C-3β/C-4)."""
    if period is Period.WEEKLY:
        return "ka10082"
    if period is Period.MONTHLY:
        return "ka10083"
    if period is Period.YEARLY:
        return "ka10094"
    return f"period={period.value}"


# =============================================================================
# Pydantic 응답 / 요청 DTO (R1 정착 패턴)
# =============================================================================


class OhlcvSyncOutcomeOut(BaseModel):
    """단일 (종목, 거래소) sync 실패 — error_class 만 (응답 echo 차단)."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    stock_code: str
    exchange: str
    error_class: str


class OhlcvPeriodicSyncResultOut(BaseModel):
    """주/월봉 sync 결과 응답 — R1 errors tuple."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    base_date: date
    total: int
    success_krx: int
    success_nxt: int
    failed: int
    errors: tuple[OhlcvSyncOutcomeOut, ...] = Field(default_factory=tuple)


class OhlcvPeriodicSyncRequestIn(BaseModel):
    """POST /sync body — R1 max_length=2 (pattern={1,2} 일치)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    base_date: date | None = Field(
        default=None,
        description="기준일자. None 이면 KST today. today - 365 ~ today 외는 400",
    )
    only_market_codes: list[Annotated[str, Field(min_length=1, max_length=2, pattern=r"^[0-9]{1,2}$")]] | None = Field(
        default=None,
        description="특정 시장만 sync (예: ['0', '10']). None 이면 전체 5 시장",
    )


# =============================================================================
# 공용 핸들러 (period 분기)
# =============================================================================


async def _do_sync(
    *,
    period: Period,
    alias: str,
    body: OhlcvPeriodicSyncRequestIn,
    factory: IngestPeriodicOhlcvUseCaseFactory,
) -> OhlcvPeriodicSyncResultOut:
    """sync 공용 핸들러 — period 만 caller 에서 결정."""
    try:
        async with factory(alias) as use_case:
            result = await use_case.execute(
                period=period,
                base_date=body.base_date,
                only_market_codes=body.only_market_codes,
            )
    except CredentialNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="등록되지 않은 alias",
        ) from None
    except CredentialInactiveError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="비활성 자격증명",
        ) from None
    except AliasCapacityExceededError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="alias 한도 초과 — 운영 문의",
        ) from None
    except ValueError as exc:
        # base_date 범위 외 / unknown market_code — 메시지 안전
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None
    except KiwoomBusinessError as exc:
        # 1R H-1 — factory(alias) 진입 시점 KiwoomError 누설 차단. message echo 차단.
        logger.warning(
            "%s sync business error api_id=%s return_code=%d msg=%s",
            _api_id_for(period),
            exc.api_id,
            exc.return_code,
            exc.message,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"return_code": exc.return_code, "error": "KiwoomBusinessError"},
        ) from None
    except KiwoomCredentialRejectedError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="키움 자격증명 거부") from None
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
    except KiwoomError as exc:
        # 1R H-1 — fallback (신규 KiwoomError subclass 안전망)
        logger.warning("ka10082/83/94 sync fallback %s api_id=%s", type(exc).__name__, _api_id_for(period))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="키움 호출 실패",
        ) from None

    return OhlcvPeriodicSyncResultOut(
        base_date=result.base_date,
        total=result.total,
        success_krx=result.success_krx,
        success_nxt=result.success_nxt,
        failed=result.failed,
        errors=tuple(OhlcvSyncOutcomeOut.model_validate(e) for e in result.errors),
    )


async def _do_refresh(
    *,
    period: Period,
    stock_code: str,
    alias: str,
    base_date: date | None,
    factory: IngestPeriodicOhlcvUseCaseFactory,
) -> OhlcvPeriodicSyncResultOut:
    """refresh 공용 핸들러 — period + stock_code 만 다름."""
    asof = base_date or date.today()
    try:
        async with factory(alias) as use_case:
            result = await use_case.refresh_one(stock_code, period=period, base_date=asof)
    except CredentialNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="등록되지 않은 alias") from None
    except CredentialInactiveError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="비활성 자격증명") from None
    except AliasCapacityExceededError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="alias 한도 초과 — 운영 문의",
        ) from None
    except StockMasterNotFoundError as exc:
        # R1 M-2 — subclass first 순서 (ValueError 분기 위)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None
    except ValueError as exc:
        # base_date 범위 외 — 메시지 안전
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None
    except KiwoomBusinessError as exc:
        # message echo 차단 (B-γ-2 / C-1β 패턴 일관). 로그는 운영 디버그용으로 message 포함.
        logger.warning(
            "%s refresh business error api_id=%s return_code=%d msg=%s",
            _api_id_for(period),
            exc.api_id,
            exc.return_code,
            exc.message,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"return_code": exc.return_code, "error": "KiwoomBusinessError"},
        ) from None
    except KiwoomCredentialRejectedError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="키움 자격증명 거부") from None
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
    except KiwoomError as exc:
        logger.warning("ka10082/83/94 fallback %s api_id=%s", type(exc).__name__, _api_id_for(period))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="키움 호출 실패",
        ) from None

    return OhlcvPeriodicSyncResultOut(
        base_date=result.base_date,
        total=result.total,
        success_krx=result.success_krx,
        success_nxt=result.success_nxt,
        failed=result.failed,
        errors=tuple(OhlcvSyncOutcomeOut.model_validate(e) for e in result.errors),
    )


# =============================================================================
# weekly endpoint (ka10082)
# =============================================================================


@router.post(
    "/ohlcv/weekly/sync",
    response_model=OhlcvPeriodicSyncResultOut,
    summary="active stock 전체 주봉 OHLCV 동기화 (admin, ka10082)",
    dependencies=[Depends(require_admin_key)],
)
async def sync_ohlcv_weekly(
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, description="키움 자격증명 alias"),
    ],
    body: OhlcvPeriodicSyncRequestIn = Body(default_factory=OhlcvPeriodicSyncRequestIn),
    factory: IngestPeriodicOhlcvUseCaseFactory = Depends(get_ingest_periodic_ohlcv_factory),
) -> OhlcvPeriodicSyncResultOut:
    return await _do_sync(period=Period.WEEKLY, alias=alias, body=body, factory=factory)


@router.post(
    "/stocks/{stock_code}/ohlcv/weekly/refresh",
    response_model=OhlcvPeriodicSyncResultOut,
    summary="단건 주봉 OHLCV 강제 새로고침 (admin, ka10082)",
    dependencies=[Depends(require_admin_key)],
)
async def refresh_ohlcv_weekly(
    stock_code: Annotated[
        str,
        Path(min_length=6, max_length=6, pattern=STK_CD_LOOKUP_PATTERN),
    ],
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, description="키움 자격증명 alias"),
    ],
    base_date: Annotated[
        date | None,
        Query(description="기준일자. None 이면 today"),
    ] = None,
    factory: IngestPeriodicOhlcvUseCaseFactory = Depends(get_ingest_periodic_ohlcv_factory),
) -> OhlcvPeriodicSyncResultOut:
    return await _do_refresh(
        period=Period.WEEKLY,
        stock_code=stock_code,
        alias=alias,
        base_date=base_date,
        factory=factory,
    )


# =============================================================================
# monthly endpoint (ka10083)
# =============================================================================


@router.post(
    "/ohlcv/monthly/sync",
    response_model=OhlcvPeriodicSyncResultOut,
    summary="active stock 전체 월봉 OHLCV 동기화 (admin, ka10083)",
    dependencies=[Depends(require_admin_key)],
)
async def sync_ohlcv_monthly(
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, description="키움 자격증명 alias"),
    ],
    body: OhlcvPeriodicSyncRequestIn = Body(default_factory=OhlcvPeriodicSyncRequestIn),
    factory: IngestPeriodicOhlcvUseCaseFactory = Depends(get_ingest_periodic_ohlcv_factory),
) -> OhlcvPeriodicSyncResultOut:
    return await _do_sync(period=Period.MONTHLY, alias=alias, body=body, factory=factory)


@router.post(
    "/stocks/{stock_code}/ohlcv/monthly/refresh",
    response_model=OhlcvPeriodicSyncResultOut,
    summary="단건 월봉 OHLCV 강제 새로고침 (admin, ka10083)",
    dependencies=[Depends(require_admin_key)],
)
async def refresh_ohlcv_monthly(
    stock_code: Annotated[
        str,
        Path(min_length=6, max_length=6, pattern=STK_CD_LOOKUP_PATTERN),
    ],
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, description="키움 자격증명 alias"),
    ],
    base_date: Annotated[
        date | None,
        Query(description="기준일자. None 이면 today"),
    ] = None,
    factory: IngestPeriodicOhlcvUseCaseFactory = Depends(get_ingest_periodic_ohlcv_factory),
) -> OhlcvPeriodicSyncResultOut:
    return await _do_refresh(
        period=Period.MONTHLY,
        stock_code=stock_code,
        alias=alias,
        base_date=base_date,
        factory=factory,
    )


# =============================================================================
# yearly endpoint (ka10094, C-4) — KRX only, NXT skip (plan § 12.2 #3)
# =============================================================================


@router.post(
    "/ohlcv/yearly/sync",
    response_model=OhlcvPeriodicSyncResultOut,
    summary="active stock 전체 년봉 OHLCV 동기화 (admin, ka10094, KRX only)",
    dependencies=[Depends(require_admin_key)],
)
async def sync_ohlcv_yearly(
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, description="키움 자격증명 alias"),
    ],
    body: OhlcvPeriodicSyncRequestIn = Body(default_factory=OhlcvPeriodicSyncRequestIn),
    factory: IngestPeriodicOhlcvUseCaseFactory = Depends(get_ingest_periodic_ohlcv_factory),
) -> OhlcvPeriodicSyncResultOut:
    return await _do_sync(period=Period.YEARLY, alias=alias, body=body, factory=factory)


@router.post(
    "/stocks/{stock_code}/ohlcv/yearly/refresh",
    response_model=OhlcvPeriodicSyncResultOut,
    summary="단건 년봉 OHLCV 강제 새로고침 (admin, ka10094, KRX only)",
    dependencies=[Depends(require_admin_key)],
)
async def refresh_ohlcv_yearly(
    stock_code: Annotated[
        str,
        Path(min_length=6, max_length=6, pattern=STK_CD_LOOKUP_PATTERN),
    ],
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, description="키움 자격증명 alias"),
    ],
    base_date: Annotated[
        date | None,
        Query(description="기준일자. None 이면 today"),
    ] = None,
    factory: IngestPeriodicOhlcvUseCaseFactory = Depends(get_ingest_periodic_ohlcv_factory),
) -> OhlcvPeriodicSyncResultOut:
    return await _do_refresh(
        period=Period.YEARLY,
        stock_code=stock_code,
        alias=alias,
        base_date=base_date,
        factory=factory,
    )


__all__ = [
    "OhlcvPeriodicSyncRequestIn",
    "OhlcvPeriodicSyncResultOut",
    "OhlcvSyncOutcomeOut",
    "router",
]
