"""POST/GET /api/kiwoom/lending* — Phase E 라우터.

설계: endpoint-16-ka10068.md § 7.1 + endpoint-17-ka20068.md § 7.1 + endpoint-15-ka10014.md § 12.

라우터 구성:
- POST /api/kiwoom/lending/market               (admin) — ka10068 시장 단위 단일 호출
- GET  /api/kiwoom/lending/market               — scope=MARKET 시계열 조회
- POST /api/kiwoom/lending/stock/{stock_code}   (admin) — ka20068 단건 종목
- POST /api/kiwoom/lending/stock/sync           (admin, body) — bulk active 종목 iterate
- GET  /api/kiwoom/lending/stock/{stock_code}   — scope=STOCK 시계열 조회 (DB only)

예외 매핑 정책 (C-2β + D-1 패턴 일관):
- KiwoomBusinessError → 400 (message echo 차단)
- KiwoomCredentialRejectedError → 400
- KiwoomRateLimitedError → 503
- KiwoomUpstreamError / KiwoomResponseValidationError → 502
- KiwoomError fallback → 502

factory dependency 시그니처:
- `get_ingest_lending_market_factory` — alias → AsyncContextManager[IngestLendingMarketUseCase]
- `get_ingest_lending_stock_factory` — alias → AsyncContextManager[IngestLendingStockUseCase]
- `get_ingest_lending_stock_bulk_factory` — alias → AsyncContextManager[IngestLendingStockBulkUseCase]

위 dependency 함수는 `app.adapter.web._deps` 에서 set_/get_/reset_ 트리오로 lifespan
에서 주입 (Agent Z 가 추가). 본 라우터는 import 만 — set/get/reset 본체는 _deps.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
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
from app.adapter.out.persistence.repositories.lending_balance import (
    LendingBalanceKwRepository,
)
from app.adapter.out.persistence.repositories.stock import StockRepository
from app.adapter.out.persistence.session import get_sessionmaker
from app.adapter.web._deps import require_admin_key
from app.application.service.lending_service import (
    IngestLendingMarketUseCase,
    IngestLendingStockBulkUseCase,
    IngestLendingStockUseCase,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kiwoom/lending", tags=["kiwoom-lending"])


# GET range cap — 1년 + 안전 마진 (C-2β 패턴 일관, DoS amplification 차단).
GET_RANGE_MAX_DAYS: int = 400


# =============================================================================
# Dependency factory types — Agent Z 의 _deps.py 에서 실제 함수 등록
# =============================================================================


IngestLendingMarketUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestLendingMarketUseCase]
]
"""alias → AsyncContextManager[IngestLendingMarketUseCase] factory (Phase E)."""


IngestLendingStockUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestLendingStockUseCase]
]
"""alias → AsyncContextManager[IngestLendingStockUseCase] factory (Phase E)."""


IngestLendingStockBulkUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestLendingStockBulkUseCase]
]
"""alias → AsyncContextManager[IngestLendingStockBulkUseCase] factory (Phase E)."""


# 본 라우터의 factory dependency 는 _deps 모듈의 set_/get_ 트리오에서 주입.
# Agent Z 가 다음 함수들을 _deps.py 에 추가:
#   - get_ingest_lending_market_factory / set_/reset_
#   - get_ingest_lending_stock_factory  / set_/reset_
#   - get_ingest_lending_stock_bulk_factory / set_/reset_


def get_ingest_lending_market_factory() -> IngestLendingMarketUseCaseFactory:  # pragma: no cover
    """Placeholder — Agent Z 가 _deps.py 에서 실제 구현 제공."""
    from app.adapter.web import _deps  # 늦은 import — _deps 의 신규 함수 호출

    fn = getattr(_deps, "get_ingest_lending_market_factory", None)
    if fn is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="lending market UseCase factory 미초기화",
        )
    return fn()  # type: ignore[no-any-return]


def get_ingest_lending_stock_factory() -> IngestLendingStockUseCaseFactory:  # pragma: no cover
    """Placeholder — Agent Z 가 _deps.py 에서 실제 구현 제공."""
    from app.adapter.web import _deps

    fn = getattr(_deps, "get_ingest_lending_stock_single_factory", None)
    if fn is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="lending stock UseCase factory 미초기화",
        )
    return fn()  # type: ignore[no-any-return]


def get_ingest_lending_stock_bulk_factory() -> IngestLendingStockBulkUseCaseFactory:  # pragma: no cover
    """Placeholder — Agent Z 가 _deps.py 에서 실제 구현 제공."""
    from app.adapter.web import _deps

    fn = getattr(_deps, "get_ingest_lending_stock_bulk_factory", None)
    if fn is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="lending stock bulk UseCase factory 미초기화",
        )
    return fn()  # type: ignore[no-any-return]


# =============================================================================
# Pydantic 응답 DTO
# =============================================================================


class LendingMarketOutcomeOut(BaseModel):
    """ka10068 시장 단위 적재 결과."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    start_date: date | None = None
    end_date: date | None = None
    fetched: int = 0
    upserted: int = 0
    error: str | None = None


class LendingStockOutcomeOut(BaseModel):
    """ka20068 종목 단건 적재 결과."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    stock_code: str
    start_date: date | None = None
    end_date: date | None = None
    fetched: int = 0
    upserted: int = 0
    skipped: bool = False
    reason: str | None = None
    error: str | None = None


class LendingStockBulkRequestIn(BaseModel):
    """POST /stock/sync body — bulk sync 입력."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    start_date: date
    end_date: date
    only_market_codes: list[
        Annotated[str, Field(min_length=1, max_length=2, pattern=r"^[0-9]{1,2}$")]
    ] | None = Field(default=None, max_length=10)
    only_stock_codes: list[
        Annotated[str, Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")]
    ] | None = Field(default=None, max_length=5000)


class LendingStockBulkResultOut(BaseModel):
    """ka20068 bulk sync 응답."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    start_date: date
    end_date: date
    total_stocks: int
    total_fetched: int = 0
    total_upserted: int = 0
    total_skipped: int = 0
    total_failed: int = 0
    warnings: tuple[str, ...] = Field(default_factory=tuple)
    errors_above_threshold: tuple[str, ...] = Field(default_factory=tuple)


class LendingBalanceRowOut(BaseModel):
    """lending_balance_kw row 응답 — GET 조회 결과."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    scope: str
    trading_date: date
    contracted_volume: int | None = None
    repaid_volume: int | None = None
    delta_volume: int | None = None
    balance_volume: int | None = None
    balance_amount: int | None = None


# =============================================================================
# POST /market — admin (ka10068 시장 단위 적재)
# =============================================================================


@router.post(
    "/market",
    response_model=LendingMarketOutcomeOut,
    summary="ka10068 시장 단위 대차 적재 (admin)",
    dependencies=[Depends(require_admin_key)],
)
async def ingest_lending_market(
    alias: Annotated[
        str,
        Query(
            min_length=1,
            max_length=50,
            pattern=r"^[A-Za-z0-9_\-]{1,50}$",
            description="키움 자격증명 alias",
        ),
    ],
    start: Annotated[
        date | None,
        Query(description="시작일자 (옵션)"),
    ] = None,
    end: Annotated[
        date | None,
        Query(description="종료일자 (옵션)"),
    ] = None,
    factory: IngestLendingMarketUseCaseFactory = Depends(get_ingest_lending_market_factory),
) -> LendingMarketOutcomeOut:
    """ka10068 시장 단위 단일 호출 → scope=MARKET 적재.

    plan § 12.2 #4 — NXT 분기 없음 (시장 단위 단일 응답).
    """
    try:
        async with factory(alias) as use_case:
            outcome = await use_case.execute(start_date=start, end_date=end)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None
    except KiwoomBusinessError as exc:
        logger.warning(
            "ka10068 business error api_id=%s return_code=%d",
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

    return LendingMarketOutcomeOut.model_validate(outcome)


# =============================================================================
# POST /stock/{stock_code} — admin (ka20068 단건)
# =============================================================================


@router.post(
    "/stock/{stock_code}",
    response_model=LendingStockOutcomeOut,
    summary="ka20068 종목 단건 대차 적재 (admin, KRX only)",
    dependencies=[Depends(require_admin_key)],
)
async def ingest_lending_stock(
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
    start: Annotated[
        date | None,
        Query(description="시작일자 (옵션)"),
    ] = None,
    end: Annotated[
        date | None,
        Query(description="종료일자 (옵션)"),
    ] = None,
    factory: IngestLendingStockUseCaseFactory = Depends(get_ingest_lending_stock_factory),
) -> LendingStockOutcomeOut:
    """ka20068 단건 종목 호출 → scope=STOCK 적재.

    plan § 12.2 #4 — KRX only (Length=6 명세). NXT suffix 시도 안 함.
    """
    try:
        async with factory(alias) as use_case:
            outcome = await use_case.execute(stock_code, start_date=start, end_date=end)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from None
    except KiwoomBusinessError as exc:
        logger.warning(
            "ka20068 business error api_id=%s return_code=%d",
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

    # stock_not_found → 404 매핑 (UseCase 측 skipped=True + reason)
    if outcome.skipped and outcome.reason == "stock_not_found":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"stock not found: {stock_code}",
        )

    return LendingStockOutcomeOut.model_validate(outcome)


# =============================================================================
# POST /stock/sync — admin (ka20068 bulk)
# =============================================================================


@router.post(
    "/stock/sync",
    response_model=LendingStockBulkResultOut,
    summary="active 종목 ka20068 일괄 적재 (admin)",
    dependencies=[Depends(require_admin_key)],
)
async def sync_lending_stock_bulk(
    alias: Annotated[
        str,
        Query(
            min_length=1,
            max_length=50,
            pattern=r"^[A-Za-z0-9_\-]{1,50}$",
            description="키움 자격증명 alias",
        ),
    ],
    body: LendingStockBulkRequestIn = Body(...),
    factory: IngestLendingStockBulkUseCaseFactory = Depends(
        get_ingest_lending_stock_bulk_factory
    ),
) -> LendingStockBulkResultOut:
    """active 종목 iterate + scope=STOCK 적재.

    plan § 12.2 #10 — 5% / 15% partial 임계치 (warnings / errors_above_threshold).
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
    except KiwoomCredentialRejectedError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="키움 자격증명 거부",
        ) from None
    except KiwoomBusinessError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"return_code": exc.return_code, "error": "KiwoomBusinessError"},
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

    return LendingStockBulkResultOut(
        start_date=result.start_date,
        end_date=result.end_date,
        total_stocks=result.total_stocks,
        total_fetched=result.total_fetched,
        total_upserted=result.total_upserted,
        total_skipped=result.total_skipped,
        total_failed=result.total_failed,
        warnings=tuple(result.warnings),
        errors_above_threshold=tuple(result.errors_above_threshold),
    )


# =============================================================================
# GET /market — DB only
# =============================================================================


@router.get(
    "/market",
    response_model=list[LendingBalanceRowOut],
    summary="저장된 scope=MARKET 시계열 조회 (DB only)",
)
async def get_lending_market_range(
    start: Annotated[date, Query(description="시작일 (포함)")],
    end: Annotated[date, Query(description="종료일 (포함)")],
) -> list[LendingBalanceRowOut]:
    """scope=MARKET 시계열 조회.

    start > end → 400. range > GET_RANGE_MAX_DAYS → 400.
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
        repo = LendingBalanceKwRepository(session)
        rows = await repo.get_market_range(start_date=start, end_date=end)

    return [LendingBalanceRowOut.model_validate(r) for r in rows]


# =============================================================================
# GET /stock/{stock_code} — DB only
# =============================================================================


@router.get(
    "/stock/{stock_code}",
    response_model=list[LendingBalanceRowOut],
    summary="저장된 scope=STOCK 시계열 조회 (DB only)",
)
async def get_lending_stock_range(
    stock_code: Annotated[
        str,
        Path(min_length=6, max_length=6, pattern=r"^[0-9]{6}$"),
    ],
    start: Annotated[date, Query(description="시작일 (포함)")],
    end: Annotated[date, Query(description="종료일 (포함)")],
) -> list[LendingBalanceRowOut]:
    """scope=STOCK 시계열 조회.

    Stock 마스터 미존재 → 404. start > end → 400. range > GET_RANGE_MAX_DAYS → 400.
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

        repo = LendingBalanceKwRepository(session)
        rows = await repo.get_stock_range(stock.id, start_date=start, end_date=end)

    return [LendingBalanceRowOut.model_validate(r) for r in rows]


__all__ = [
    "GET_RANGE_MAX_DAYS",
    "IngestLendingMarketUseCaseFactory",
    "IngestLendingStockBulkUseCaseFactory",
    "IngestLendingStockUseCaseFactory",
    "LendingBalanceRowOut",
    "LendingMarketOutcomeOut",
    "LendingStockBulkRequestIn",
    "LendingStockBulkResultOut",
    "LendingStockOutcomeOut",
    "get_ingest_lending_market_factory",
    "get_ingest_lending_stock_bulk_factory",
    "get_ingest_lending_stock_factory",
    "router",
]
