"""POST/GET /api/kiwoom/daily-flow* — C-2β 라우터.

설계: endpoint-10-ka10086.md § 7.1 + ADR § 18 (C-1β ohlcv 라우터 패턴 일관).

라우터 구성:
- POST /api/kiwoom/daily-flow/sync                                          (admin) — 전체 sync
- POST /api/kiwoom/stocks/{stock_code}/daily-flow/refresh                   (admin) — 단건 refresh
- GET  /api/kiwoom/stocks/{stock_code}/daily-flow?start=&end=&exchange=     (DB only)

응답 정책 (B-α/B-β/B-γ-2/C-1β 패턴 일관):
- POST sync 는 부분 성공 허용 — 200 + per-(stock,exchange) errors list
- KiwoomError 매핑: business→400 / credential→400 / rate→503 / upstream/validation→502
- KiwoomBusinessError.message 는 응답 echo 차단
- ValueError (base_date 범위 / stock master not found) → 400 / 404
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
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
from app.adapter.out.persistence.repositories.stock import StockRepository
from app.adapter.out.persistence.repositories.stock_daily_flow import (
    StockDailyFlowRepository,
)
from app.adapter.out.persistence.session import get_sessionmaker
from app.adapter.web._deps import (
    IngestDailyFlowUseCaseFactory,
    get_ingest_daily_flow_factory,
    require_admin_key,
)
from app.application.constants import ExchangeType
from app.application.service.token_service import (
    AliasCapacityExceededError,
    CredentialInactiveError,
    CredentialNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kiwoom", tags=["kiwoom-daily-flow"])

# C-1β 2b-M1 일관 — GET /daily-flow date range cap (DoS amplification 차단).
# 1년 sync target_date_range + 안전 마진. 단일 호출 메모리 보호.
GET_RANGE_MAX_DAYS: int = 400


# =============================================================================
# Pydantic 응답 DTO
# =============================================================================


class DailyFlowSyncOutcomeOut(BaseModel):
    """단일 (종목, 거래소) sync 실패 — error_class 만 (응답 echo 차단)."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    stock_code: str
    exchange: str
    error_class: str


class DailyFlowSyncResultOut(BaseModel):
    """전체 sync 결과 응답."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    base_date: date
    total: int
    success_krx: int
    success_nxt: int
    failed: int
    errors: list[DailyFlowSyncOutcomeOut] = Field(default_factory=list)


class DailyFlowSyncRequestIn(BaseModel):
    """POST /sync body — 모두 옵션."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    base_date: date | None = Field(
        default=None,
        description="기준일자. None 이면 KST today. today - 365 ~ today 외는 400",
    )
    only_market_codes: list[
        Annotated[str, Field(min_length=1, max_length=4, pattern=r"^[0-9]{1,2}$")]
    ] | None = Field(
        default=None,
        description="특정 시장만 sync (예: ['0', '10']). None 이면 전체 5 시장",
    )


class DailyFlowRowOut(BaseModel):
    """stock_daily_flow row 응답 — 시계열 GET 결과 (13 영속 필드)."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    trading_date: date
    exchange: str
    indc_mode: str
    # C. 신용
    credit_rate: Decimal | None = None
    credit_balance_rate: Decimal | None = None
    # D. 투자자별 net
    individual_net: int | None = None
    institutional_net: int | None = None
    foreign_brokerage_net: int | None = None
    program_net: int | None = None
    # E. 외인 + 순매수
    foreign_volume: int | None = None
    foreign_rate: Decimal | None = None
    foreign_holdings: int | None = None
    foreign_weight: Decimal | None = None
    foreign_net_purchase: int | None = None
    institutional_net_purchase: int | None = None
    individual_net_purchase: int | None = None
    fetched_at: datetime | None = None


# =============================================================================
# POST /daily-flow/sync — admin
# =============================================================================


@router.post(
    "/daily-flow/sync",
    response_model=DailyFlowSyncResultOut,
    summary="active stock 전체 일별 수급 동기화 (admin)",
    dependencies=[Depends(require_admin_key)],
)
async def sync_daily_flow(
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, description="키움 자격증명 alias"),
    ],
    body: DailyFlowSyncRequestIn = Body(default_factory=DailyFlowSyncRequestIn),
    factory: IngestDailyFlowUseCaseFactory = Depends(get_ingest_daily_flow_factory),
) -> DailyFlowSyncResultOut:
    """alias 의 자격증명으로 active stock 전체 일별 수급 sync.

    per-(stock,exchange) try/except — 부분 실패 허용.

    예외 매핑 (C-1β 패턴 일관):
    - alias 미등록 → 404 / 비활성 → 400 / 한도 초과 → 503
    - base_date 범위 외 (ValueError) → 400
    - 키움 호출 실패는 종목별로 errors 격리 — 200 반환
    """
    try:
        async with factory(alias) as use_case:
            result = await use_case.execute(
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
        # base_date 범위 외 (UseCase._validate_base_date) — 메시지 안전 (외부 입력 echo 없음)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None

    return DailyFlowSyncResultOut(
        base_date=result.base_date,
        total=result.total,
        success_krx=result.success_krx,
        success_nxt=result.success_nxt,
        failed=result.failed,
        errors=[DailyFlowSyncOutcomeOut.model_validate(e) for e in result.errors],
    )


# =============================================================================
# POST /stocks/{code}/daily-flow/refresh — admin (단건)
# =============================================================================


@router.post(
    "/stocks/{stock_code}/daily-flow/refresh",
    response_model=DailyFlowSyncResultOut,
    summary="단건 일별 수급 강제 새로고침 (admin)",
    dependencies=[Depends(require_admin_key)],
)
async def refresh_daily_flow(
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
    factory: IngestDailyFlowUseCaseFactory = Depends(get_ingest_daily_flow_factory),
) -> DailyFlowSyncResultOut:
    """ka10086 호출 → DB upsert → 결과 반환.

    예외 매핑 (C-1β 패턴 일관):
    - alias 미등록 → 404 / 비활성 → 400 / 한도 초과 → 503
    - Stock 마스터 미존재 (ValueError "stock master not found") → 404
    - base_date 범위 외 (ValueError "base_date") → 400
    - KiwoomBusinessError → 400 (message echo 차단)
    - KiwoomCredentialRejectedError → 400
    - KiwoomRateLimitedError → 503
    - KiwoomUpstreamError / KiwoomResponseValidationError → 502
    """
    asof = base_date or date.today()
    try:
        async with factory(alias) as use_case:
            result = await use_case.refresh_one(stock_code, base_date=asof)
    except CredentialNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="등록되지 않은 alias") from None
    except CredentialInactiveError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="비활성 자격증명") from None
    except AliasCapacityExceededError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="alias 한도 초과 — 운영 문의",
        ) from None
    except ValueError as exc:
        # 두 가지 ValueError — "stock master not found" → 404, "base_date" → 400
        msg = str(exc)
        if "stock master not found" in msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            ) from None
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        ) from None
    except KiwoomBusinessError as exc:
        # C-1β 패턴 일관 — return_msg echo 차단
        logger.warning(
            "ka10086 business error api_id=%s return_code=%d msg=%s",
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
        # C-1β 패턴 일관 — 신규 KiwoomError 서브클래스 안전망
        logger.warning("ka10086 fallback %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="키움 호출 실패",
        ) from None

    return DailyFlowSyncResultOut(
        base_date=result.base_date,
        total=result.total,
        success_krx=result.success_krx,
        success_nxt=result.success_nxt,
        failed=result.failed,
        errors=[DailyFlowSyncOutcomeOut.model_validate(e) for e in result.errors],
    )


# =============================================================================
# GET /stocks/{code}/daily-flow — DB only
# =============================================================================


@router.get(
    "/stocks/{stock_code}/daily-flow",
    response_model=list[DailyFlowRowOut],
    summary="저장된 일별 수급 시계열 조회 (DB only)",
)
async def get_daily_flow(
    stock_code: Annotated[
        str,
        Path(min_length=6, max_length=6, pattern=STK_CD_LOOKUP_PATTERN),
    ],
    start: Annotated[date, Query(description="시작일 (포함)")],
    end: Annotated[date, Query(description="종료일 (포함)")],
    exchange: Annotated[
        str,
        Query(
            min_length=3,
            max_length=3,
            pattern=r"^(KRX|NXT)$",
            description="거래소. SOR 미지원 (Phase D 결정)",
        ),
    ] = "KRX",
) -> list[DailyFlowRowOut]:
    """DB read only — 키움 호출 없음.

    Stock 마스터 미존재 → 404. start > end → 400. range > 400일 → 400.
    """
    if start > end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"start ({start}) must be <= end ({end})",
        )
    if (end - start).days > GET_RANGE_MAX_DAYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"date range 가 {GET_RANGE_MAX_DAYS}일 초과 — 분할 조회 필요",
        )

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        stock_repo = StockRepository(session)
        stock = await stock_repo.find_by_code(stock_code)
        if stock is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"stock not found: {stock_code}",
            )

        flow_repo = StockDailyFlowRepository(session)
        rows = await flow_repo.find_range(
            stock.id,
            exchange=ExchangeType(exchange),
            start=start,
            end=end,
        )

    return [DailyFlowRowOut.model_validate(r) for r in rows]


__all__ = [
    "DailyFlowRowOut",
    "DailyFlowSyncOutcomeOut",
    "DailyFlowSyncRequestIn",
    "DailyFlowSyncResultOut",
    "router",
]
