"""POST/GET /api/kiwoom/fundamentals* — B-γ-2 라우터.

설계: endpoint-05-ka10001.md § 7.1 + ADR § 14.6.

라우터 구성:
- POST /api/kiwoom/fundamentals/sync                         (admin) — 전체 sync
- POST /api/kiwoom/stocks/{stock_code}/fundamental/refresh   (admin) — 단건 refresh
- GET  /api/kiwoom/stocks/{stock_code}/fundamental/latest             — DB only

응답 정책 (B-α/B-β 패턴 일관):
- POST sync 는 부분 성공 허용 — 200 + per-stock errors list
- KiwoomError 매핑: business→400 / credential→400 / rate→503 / upstream/validation→502
- KiwoomBusinessError.message 는 응답 echo 차단 (B-α/B-β M-2 패턴)
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._exceptions import (
    KiwoomBusinessError,
    KiwoomCredentialRejectedError,
    KiwoomError,
    KiwoomRateLimitedError,
    KiwoomResponseValidationError,
    KiwoomUpstreamError,
)
from app.adapter.out.kiwoom.stkinfo import STK_CD_LOOKUP_PATTERN, SentinelStockCodeError
from app.adapter.out.persistence.repositories.stock import StockRepository
from app.adapter.out.persistence.repositories.stock_fundamental import (
    StockFundamentalRepository,
)
from app.adapter.out.persistence.session import get_sessionmaker
from app.adapter.web._deps import (
    SyncStockFundamentalUseCaseFactory,
    get_sync_fundamental_factory,
    require_admin_key,
)
from app.application.exceptions import StockMasterNotFoundError
from app.application.service.token_service import (
    AliasCapacityExceededError,
    CredentialInactiveError,
    CredentialNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kiwoom", tags=["kiwoom-fundamentals"])


# =============================================================================
# Pydantic 응답 DTO
# =============================================================================


class StockFundamentalOut(BaseModel):
    """stock_fundamental row 응답 — 45 필드 + 메타."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    stock_id: int
    asof_date: date
    exchange: str
    settlement_month: str | None = None
    face_value: int | None = None
    face_value_unit: str | None = None
    capital_won: int | None = None
    listed_shares: int | None = None
    market_cap: int | None = None
    market_cap_weight: Decimal | None = None
    foreign_holding_rate: Decimal | None = None
    replacement_price: int | None = None
    credit_rate: Decimal | None = None
    circulating_shares: int | None = None
    circulating_rate: Decimal | None = None
    per_ratio: Decimal | None = None
    eps_won: int | None = None
    roe_pct: Decimal | None = None
    pbr_ratio: Decimal | None = None
    ev_ratio: Decimal | None = None
    bps_won: int | None = None
    revenue_amount: int | None = None
    operating_profit: int | None = None
    net_profit: int | None = None
    high_250d: int | None = None
    high_250d_date: date | None = None
    high_250d_pre_rate: Decimal | None = None
    low_250d: int | None = None
    low_250d_date: date | None = None
    low_250d_pre_rate: Decimal | None = None
    year_high: int | None = None
    year_low: int | None = None
    current_price: int | None = None
    prev_compare_sign: str | None = None
    prev_compare_amount: int | None = None
    change_rate: Decimal | None = None
    trade_volume: int | None = None
    trade_compare_rate: Decimal | None = None
    open_price: int | None = None
    high_price: int | None = None
    low_price: int | None = None
    upper_limit_price: int | None = None
    lower_limit_price: int | None = None
    base_price: int | None = None
    expected_match_price: int | None = None
    expected_match_volume: int | None = None
    fundamental_hash: str | None = None
    # ORM NOT NULL + server_default=now() — 항상 값 존재 (R1 L-2)
    fetched_at: datetime


class FundamentalSyncOutcomeOut(BaseModel):
    """단일 종목 sync 실패 응답 — 응답 본문 echo 차단."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    stock_code: str
    error_class: str


class FundamentalSyncResultOut(BaseModel):
    """전체 sync 결과 응답.

    Phase F-1 (§ 5.3):
    - ``skipped_count`` — sentinel 종목코드 의도된 skip 수 (``failed`` 분리).
    - ``skipped`` — sentinel 종목 list (운영자 가시성, plan § 5.3 2b M-1).
      운영 알람·임계치에서 _실제 실패_ ↔ _의도 skip_ 분리 목적.
      기본값 0 / 빈 tuple — 기존 호출자가 무시해도 동작 (backward compat).
    """

    model_config = ConfigDict(frozen=True, from_attributes=True)

    asof_date: date
    total: int
    success: int
    failed: int
    errors: tuple[FundamentalSyncOutcomeOut, ...] = Field(default_factory=tuple)
    skipped_count: int = 0
    skipped: tuple[FundamentalSyncOutcomeOut, ...] = Field(default_factory=tuple)


class FundamentalSyncRequestIn(BaseModel):
    """POST /sync body — 모두 옵션."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    target_date: date | None = Field(
        default=None,
        description="영속화 일자. None 이면 KST today (응답에 timestamp 부재, § 11.2)",
    )
    only_market_codes: list[
        Annotated[str, Field(min_length=1, max_length=2, pattern=r"^[0-9]{1,2}$")]
    ] | None = Field(
        default=None,
        description="특정 시장만 sync (예: ['0', '10']). None 이면 전체 5 시장",
    )


# =============================================================================
# POST /fundamentals/sync — admin
# =============================================================================


@router.post(
    "/fundamentals/sync",
    response_model=FundamentalSyncResultOut,
    summary="active stock 전체 펀더멘털 강제 동기화 (admin)",
    dependencies=[Depends(require_admin_key)],
)
async def sync_fundamentals(
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, description="키움 자격증명 alias"),
    ],
    body: FundamentalSyncRequestIn = Body(default_factory=FundamentalSyncRequestIn),
    factory: SyncStockFundamentalUseCaseFactory = Depends(get_sync_fundamental_factory),
) -> FundamentalSyncResultOut:
    """alias 의 자격증명으로 active stock 전체 펀더멘털 sync.

    per-stock try/except — 부분 실패 허용 (ADR § 14.6 (a)).

    예외 매핑 (B-α/B-β 패턴 일관):
    - alias 미등록 → 404
    - alias 비활성 → 400
    - alias 한도 초과 → 503
    - 키움 호출 실패는 종목별로 errors 격리 — 200 반환
    """
    try:
        async with factory(alias) as use_case:
            result = await use_case.execute(
                target_date=body.target_date,
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

    return FundamentalSyncResultOut(
        asof_date=result.asof_date,
        total=result.total,
        success=result.success,
        failed=result.failed,
        errors=tuple(FundamentalSyncOutcomeOut.model_validate(e) for e in result.errors),
        skipped_count=result.skipped_count,
        skipped=tuple(FundamentalSyncOutcomeOut.model_validate(s) for s in result.skipped),
    )


# =============================================================================
# POST /stocks/{code}/fundamental/refresh — admin (단건)
# =============================================================================


@router.post(
    "/stocks/{stock_code}/fundamental/refresh",
    response_model=StockFundamentalOut,
    summary="단건 펀더멘털 강제 새로고침 (admin)",
    dependencies=[Depends(require_admin_key)],
)
async def refresh_fundamental(
    stock_code: Annotated[
        str,
        Path(min_length=6, max_length=6, pattern=STK_CD_LOOKUP_PATTERN),
    ],
    alias: Annotated[
        str,
        Query(min_length=1, max_length=50, description="키움 자격증명 alias"),
    ],
    factory: SyncStockFundamentalUseCaseFactory = Depends(get_sync_fundamental_factory),
) -> StockFundamentalOut:
    """ka10001 호출 → DB upsert → 갱신된 row 반환.

    예외 매핑:
    - alias 미등록 → 404
    - alias 비활성 → 400
    - alias 한도 초과 → 503
    - Stock 마스터 미존재 (StockMasterNotFoundError) → 404
    - KiwoomBusinessError → 400 + detail{return_code, error} (message echo 차단)
    - KiwoomCredentialRejectedError → 400
    - KiwoomRateLimitedError → 503
    - KiwoomUpstreamError / KiwoomResponseValidationError → 502
    """
    try:
        async with factory(alias) as use_case:
            fundamental = await use_case.refresh_one(stock_code)
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
        # R1 M-2 — 전용 예외. ensure_exists 미사용 정책 (ADR § 14.6).
        # 메시지에 stock_code 만 포함 — 외부 입력 echo 위험 없음 (Path pattern 사전 검증됨)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from None
    except SentinelStockCodeError:
        # Phase F-1 2a M-1 — 안전망. Path pattern `STK_CD_LOOKUP_PATTERN` 가 우선 차단
        # 하므로 일반 입력에서는 발생 불가. 그러나 cron 등 master DB 에 sentinel 종목
        # 이 active 로 등록된 상태에서 admin 이 수동 refresh 호출 시 도달 가능.
        # 500 낙하 방지 위해 명시적 400 매핑.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="sentinel stock_code — 6자리 숫자만 허용 (운영 의도된 skip)",
        ) from None
    # 의도적 생략: ohlcv/daily_flow refresh 와 달리 본 핸들러는 base_date 파라미터를
    # 받지 않음 (refresh_one 내부에서 today 고정). base_date ValueError 가 발생하지
    # 않으므로 generic `except ValueError` 분기 불필요. 향후 base_date 파라미터 추가
    # 시 ohlcv.py / daily_flow.py 패턴과 일관 적용. (R1 L-4)
    except KiwoomBusinessError as exc:
        # B-β 패턴 일관 — return_msg echo 차단, 비식별 메타만
        logger.warning(
            "ka10001 business error api_id=%s return_code=%d msg=%s",
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
        # B-β M-5 패턴 — 신규 KiwoomError 서브클래스 안전망
        logger.warning("ka10001 fallback %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="키움 호출 실패",
        ) from None

    return StockFundamentalOut.model_validate(fundamental)


# =============================================================================
# GET /stocks/{code}/fundamental/latest — DB only
# =============================================================================


@router.get(
    "/stocks/{stock_code}/fundamental/latest",
    response_model=StockFundamentalOut,
    summary="저장된 가장 최근 펀더멘털 조회 (DB only)",
)
async def get_latest_fundamental(
    stock_code: Annotated[
        str,
        Path(min_length=6, max_length=6, pattern=STK_CD_LOOKUP_PATTERN),
    ],
    exchange: Annotated[
        str,
        Query(
            min_length=1,
            # exchange 코드 — KRX/NXT/SOR (3자). max_length=4 는 안전 마진. only_market_codes
            # (시장 코드, R1 max_length=2) 와는 다른 파라미터이므로 변경 대상 아님.
            max_length=4,
            pattern=r"^(KRX|NXT|SOR)$",
            description="거래소 (B-γ-1 KRX-only). NXT/SOR 은 Phase C 후 채워짐",
        ),
    ] = "KRX",
) -> StockFundamentalOut:
    """DB read only — 키움 호출 없음.

    Stock 마스터 미존재 → 404 / fundamental 미적재 → 404.
    """
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        stock_repo = StockRepository(session)
        stock = await stock_repo.find_by_code(stock_code)
        if stock is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"stock not found: {stock_code}",
            )

        fundamental_repo = StockFundamentalRepository(session)
        f = await fundamental_repo.find_latest(stock.id, exchange=exchange)

    if f is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no fundamental data for {stock_code}",
        )
    return StockFundamentalOut.model_validate(f)


__all__ = [
    "FundamentalSyncOutcomeOut",
    "FundamentalSyncRequestIn",
    "FundamentalSyncResultOut",
    "StockFundamentalOut",
    "router",
]


# Avoid unused-import warning on AsyncSession (used implicitly via repositories typing)
_AsyncSession = AsyncSession
