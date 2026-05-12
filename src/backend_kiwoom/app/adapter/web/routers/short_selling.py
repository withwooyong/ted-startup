"""POST/GET /api/kiwoom/short-selling* — Phase E 라우터 (ka10014).

설계: endpoint-15-ka10014.md § 7.1 + § 12.

라우터 구성:
- POST /api/kiwoom/short-selling/stock/{stock_code}/refresh             (admin) — 단건 refresh
- POST /api/kiwoom/short-selling/stock/sync                             (admin) — bulk
- GET  /api/kiwoom/short-selling/stock/{stock_code}/range?start=&end=&exchange=  (DB only)
- GET  /api/kiwoom/short-selling/high-weight?date=&min_weight=          (DB only, signal)

응답 정책 (C-2β daily_flow + D-1 sector_ohlcv 일관):
- POST refresh 단건 — 결과 outcome 그대로 반환
- POST sync bulk — 부분 성공 허용 — 200 + per-outcome errors
- KiwoomError 매핑: business→400 / credential→400 / rate→503 / upstream/validation→502
- KiwoomBusinessError.message 는 응답 echo 차단
- ValueError → 400 (base_date 범위, stock_code 사전 검증 등)
- stock master 미존재 → 404
"""

from __future__ import annotations

import logging
from datetime import date
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
from app.adapter.out.persistence.repositories.short_selling import (
    ShortSellingKwRepository,
)
from app.adapter.out.persistence.repositories.stock import StockRepository
from app.adapter.out.persistence.session import get_sessionmaker
from app.adapter.web._deps import (
    IngestShortSellingBulkUseCaseFactory,
    IngestShortSellingUseCaseFactory,
    get_ingest_short_selling_bulk_factory,
    get_ingest_short_selling_single_factory,
    require_admin_key,
)
from app.application.constants import ExchangeType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kiwoom/short-selling", tags=["kiwoom-short-selling"])

# range GET cap — daily_flow.py 의 GET_RANGE_MAX_DAYS 일관 (DoS amplification 차단).
GET_RANGE_MAX_DAYS: int = 400


# =============================================================================
# Pydantic DTO
# =============================================================================


class ShortSellingIngestOutcomeOut(BaseModel):
    """단일 종목·거래소 ingest 결과 응답."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    stock_code: str
    exchange: ExchangeType
    upserted: int = 0
    fetched: int = 0
    skipped: bool = False
    reason: str | None = None
    error: str | None = None


class ShortSellingBulkResultOut(BaseModel):
    """bulk sync 결과 응답."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    total_stocks: int
    krx_outcomes: tuple[ShortSellingIngestOutcomeOut, ...] = Field(default_factory=tuple)
    nxt_outcomes: tuple[ShortSellingIngestOutcomeOut, ...] = Field(default_factory=tuple)
    warnings: tuple[str, ...] = Field(default_factory=tuple)
    errors_above_threshold: bool = False
    total_upserted: int
    total_failed: int


class ShortSellingBulkRequestIn(BaseModel):
    """POST /stock/sync body."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    start_date: date = Field(description="시작일 (포함, YYYY-MM-DD)")
    end_date: date = Field(description="종료일 (포함, YYYY-MM-DD)")
    only_market_codes: list[
        Annotated[str, Field(min_length=1, max_length=2, pattern=r"^[0-9]{1,2}$")]
    ] | None = Field(
        default=None,
        max_length=10,
        description="특정 시장만 (예: ['0','10']). None 이면 전체",
    )
    only_stock_codes: list[
        Annotated[str, Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")]
    ] | None = Field(
        default=None,
        max_length=5000,
        description="특정 종목만 (CLI 디버그). None 이면 전체. cap 5000 (DoS 방어)",
    )


class ShortSellingRowOut(BaseModel):
    """short_selling_kw row 응답 — 시계열 GET 결과."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    trading_date: date
    exchange: str
    close_price: int | None = None
    prev_compare_amount: int | None = None
    prev_compare_sign: str | None = None
    change_rate: Decimal | None = None
    trade_volume: int | None = None
    short_volume: int | None = None
    cumulative_short_volume: int | None = None
    short_trade_weight: Decimal | None = None
    short_trade_amount: int | None = None
    short_avg_price: int | None = None


# =============================================================================
# POST /stock/{stock_code}/refresh — 단건 admin
# =============================================================================


@router.post(
    "/stock/{stock_code}/refresh",
    response_model=ShortSellingIngestOutcomeOut,
    summary="단건 공매도 추이 강제 새로고침 (admin, ka10014)",
    dependencies=[Depends(require_admin_key)],
)
async def refresh_short_selling(
    stock_code: Annotated[
        str,
        Path(min_length=6, max_length=6, pattern=r"^[0-9]{6}$"),
    ],
    alias: Annotated[
        str,
        Query(
            min_length=1,
            max_length=50,
            pattern=r"^[A-Za-z0-9_\-]{1,50}$",
            description="키움 자격증명 alias",
        ),
    ],
    start: Annotated[date, Query(description="시작일 (포함)")],
    end: Annotated[date, Query(description="종료일 (포함)")],
    exchange: Annotated[
        str,
        Query(
            min_length=3,
            max_length=3,
            pattern=r"^(KRX|NXT)$",
            description="거래소. KRX (default) / NXT",
        ),
    ] = "KRX",
    factory: IngestShortSellingUseCaseFactory = Depends(
        get_ingest_short_selling_single_factory
    ),
) -> ShortSellingIngestOutcomeOut:
    """ka10014 호출 → DB upsert → 결과 outcome 반환.

    예외 매핑:
    - ValueError (stock_code 6자리 외) → 400
    - KiwoomBusinessError → 400 (message echo 차단)
    - KiwoomCredentialRejectedError → 400
    - KiwoomRateLimitedError → 503
    - KiwoomUpstreamError / KiwoomResponseValidationError → 502

    stock_code 미존재 / inactive / nxt_disabled 는 outcome.skipped 로 반환 (200).
    """
    if start > end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"start ({start}) must be <= end ({end})",
        )

    try:
        async with factory(alias) as use_case:
            outcome = await use_case.execute(
                stock_code,
                start_date=start,
                end_date=end,
                exchange=ExchangeType(exchange),
            )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None
    except KiwoomBusinessError as exc:
        logger.warning(
            "ka10014 refresh business error api_id=%s return_code=%d",
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
    except KiwoomError as exc:
        logger.warning("ka10014 fallback %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="키움 호출 실패",
        ) from None

    return ShortSellingIngestOutcomeOut.model_validate(outcome)


# =============================================================================
# POST /stock/sync — bulk admin
# =============================================================================


@router.post(
    "/stock/sync",
    response_model=ShortSellingBulkResultOut,
    summary="active 종목 공매도 추이 일괄 동기화 (admin, ka10014)",
    dependencies=[Depends(require_admin_key)],
)
async def sync_short_selling_bulk(
    alias: Annotated[
        str,
        Query(
            min_length=1,
            max_length=50,
            pattern=r"^[A-Za-z0-9_\-]{1,50}$",
            description="키움 자격증명 alias",
        ),
    ],
    body: ShortSellingBulkRequestIn = Body(...),
    factory: IngestShortSellingBulkUseCaseFactory = Depends(
        get_ingest_short_selling_bulk_factory
    ),
) -> ShortSellingBulkResultOut:
    """alias 의 자격증명으로 active 종목 전체 공매도 추이 sync.

    per-(stock,exchange) try/except — 부분 실패 허용.

    partial 임계치 (결정 #10):
    - 실패율 5% 초과 → result.warnings + logger.warning
    - 실패율 15% 초과 → result.errors_above_threshold=True
    """
    if body.start_date > body.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"start_date ({body.start_date}) must be <= end_date ({body.end_date})",
        )

    try:
        async with factory(alias) as use_case:
            result = await use_case.execute(
                start_date=body.start_date,
                end_date=body.end_date,
                only_market_codes=body.only_market_codes,
                only_stock_codes=body.only_stock_codes,
            )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None
    except KiwoomBusinessError as exc:
        logger.warning(
            "ka10014 bulk business error api_id=%s return_code=%d",
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
    except KiwoomError as exc:
        logger.warning("ka10014 bulk fallback %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="키움 호출 실패",
        ) from None

    return ShortSellingBulkResultOut(
        total_stocks=result.total_stocks,
        krx_outcomes=tuple(
            ShortSellingIngestOutcomeOut.model_validate(o) for o in result.krx_outcomes
        ),
        nxt_outcomes=tuple(
            ShortSellingIngestOutcomeOut.model_validate(o) for o in result.nxt_outcomes
        ),
        warnings=tuple(result.warnings),
        errors_above_threshold=result.errors_above_threshold,
        total_upserted=result.total_upserted,
        total_failed=result.total_failed,
    )


# =============================================================================
# GET /stock/{stock_code}/range — DB only
# =============================================================================


@router.get(
    "/stock/{stock_code}/range",
    response_model=list[ShortSellingRowOut],
    summary="저장된 공매도 추이 시계열 조회 (DB only)",
)
async def get_short_selling_range(
    stock_code: Annotated[
        str,
        Path(min_length=6, max_length=6, pattern=r"^[0-9]{6}$"),
    ],
    start: Annotated[date, Query(description="시작일 (포함)")],
    end: Annotated[date, Query(description="종료일 (포함)")],
    exchange: Annotated[
        str,
        Query(
            min_length=3,
            max_length=3,
            pattern=r"^(KRX|NXT)$",
            description="거래소. KRX (default) / NXT",
        ),
    ] = "KRX",
) -> list[ShortSellingRowOut]:
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

        repo = ShortSellingKwRepository(session)
        rows = await repo.get_range(
            stock.id,
            exchange=exchange,
            start_date=start,
            end_date=end,
        )

    return [ShortSellingRowOut.model_validate(r) for r in rows]


# =============================================================================
# GET /high-weight — DB only signal
# =============================================================================


@router.get(
    "/high-weight",
    response_model=list[ShortSellingRowOut],
    summary="일별 공매도 매매비중 상위 종목 시그널 (DB only)",
)
async def get_high_weight_signal(
    on_date: Annotated[date, Query(alias="date", description="조회 일자")],
    min_weight: Annotated[
        Decimal,
        Query(description="매매비중 임계치 (%), 디폴트 5.0", ge=0),
    ] = Decimal("5.0"),
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[ShortSellingRowOut]:
    """`idx_short_selling_kw_weight_high` partial index 활용 — NULL 제외 + weight DESC.

    백테스팅 시그널 — 매매비중 상위 N 종목.
    """
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        repo = ShortSellingKwRepository(session)
        rows = await repo.get_high_weight_stocks(
            on_date,
            min_weight=min_weight,
            limit=limit,
        )

    return [ShortSellingRowOut.model_validate(r) for r in rows]


__all__ = [
    "ShortSellingBulkRequestIn",
    "ShortSellingBulkResultOut",
    "ShortSellingIngestOutcomeOut",
    "ShortSellingRowOut",
    "router",
]
