"""GET / POST /api/kiwoom/stocks — 종목 마스터 조회 + 동기화 + NXT 큐.

설계: endpoint-03-ka10099.md § 7.1.

라우터 구성:
- GET  /stocks                     — 저장된 종목 마스터 조회 (DB only, admin 불필요)
                                     filter: market_code, nxt_enable, only_active
- GET  /stocks/nxt-eligible        — Phase C 가 사용할 NXT 호출 큐 (admin 불필요)
- POST /stocks/sync                — 5 시장 강제 동기화 (admin only, alias 명시)

응답 정책 (sector 패턴 일관):
- DB read 만 — 키움 호출 없음 (GET)
- POST sync 는 부분 성공 허용 — 200 + per-market outcomes
- F3 hint: outcome.error 에 KiwoomMaxPagesExceededError 흔적 시 Retry-After: 60 헤더
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
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
from app.adapter.out.persistence.session import get_sessionmaker
from app.adapter.web._deps import (
    LookupStockUseCaseFactory,
    SyncStockMasterUseCaseFactory,
    get_lookup_stock_factory,
    get_sync_stock_factory,
    require_admin_key,
)
from app.application.service.stock_master_service import StockMasterSyncResult
from app.application.service.token_service import (
    AliasCapacityExceededError,
    CredentialInactiveError,
    CredentialNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kiwoom", tags=["kiwoom-stocks"])


# =============================================================================
# Pydantic 응답 DTO — ORM/dataclass → API 응답
# =============================================================================


class StockOut(BaseModel):
    """stock 테이블 row 의 외부 응답 표현."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    stock_code: str
    stock_name: str
    list_count: int | None
    audit_info: str | None
    listed_date: date | None
    last_price: int | None
    state: str | None
    market_code: str
    market_name: str | None
    up_name: str | None
    up_size_name: str | None
    company_class_name: str | None
    order_warning: str
    nxt_enable: bool
    is_active: bool
    fetched_at: datetime


class MarketStockOutcomeOut(BaseModel):
    """시장 단위 동기화 결과 응답."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    market_code: str
    fetched: int
    upserted: int
    deactivated: int
    nxt_enabled_count: int
    error: str | None = None


class StockMasterSyncResultOut(BaseModel):
    """5 시장 전체 동기화 결과 응답."""

    model_config = ConfigDict(frozen=True)

    markets: list[MarketStockOutcomeOut]
    total_fetched: int
    total_upserted: int
    total_deactivated: int
    total_nxt_enabled: int
    all_succeeded: bool = Field(description="모든 시장이 error 없이 완료됐는지")


# =============================================================================
# GET /stocks — 조회 (admin 불필요)
# =============================================================================


@router.get(
    "/stocks",
    response_model=list[StockOut],
    summary="저장된 종목 마스터 조회",
)
async def list_stocks(
    market_code: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=4,
            pattern=r"^[0-9]{1,2}$",
            description=(
                "시장 코드 — ka10099 mrkt_tp 16종 중 하나 (`0`/`10`/`50`/`60`/`6` 외 등). 미지정 시 16 시장 통합 조회."
            ),
        ),
    ] = None,
    nxt_enable: Annotated[
        bool | None,
        Query(description="True 면 NXT 가능, False 면 NXT 불가, None 이면 둘 다"),
    ] = None,
    only_active: Annotated[
        bool,
        Query(description="활성 종목만 (기본 True)"),
    ] = True,
) -> list[StockOut]:
    """DB read only — 키움 호출 없음.

    정렬: market_code → stock_code. populate_existing 으로 stale 방지.
    """
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        repo = StockRepository(session)
        rows = await repo.list_by_filters(
            market_code=market_code,
            nxt_enable=nxt_enable,
            only_active=only_active,
        )

    return [StockOut.model_validate(r) for r in rows]


@router.get(
    "/stocks/nxt-eligible",
    response_model=list[StockOut],
    summary="NXT 가능 활성 종목 — Phase C 호출 큐 source",
)
async def list_nxt_eligible_stocks() -> list[StockOut]:
    """Phase C 의 NXT 호출 큐 — `nxt_enable=true AND is_active=true`.

    DB only. 운영에서 NXT 일봉 적재 직전 호출되어 어떤 종목에 `_NX` suffix 를
    붙일지 결정.
    """
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        repo = StockRepository(session)
        rows = await repo.list_nxt_enabled(only_active=True)

    return [StockOut.model_validate(r) for r in rows]


# =============================================================================
# POST /stocks/sync — 강제 동기화 (admin)
# =============================================================================


def _mark_max_pages_hint(response: Response, result: StockMasterSyncResult) -> None:
    """F3 hint — 한 시장 이상이 max_pages 한도 도달 시 Retry-After 헤더 (sector 일관)."""
    if any(m.error is not None and "MaxPages" in m.error for m in result.markets):
        response.headers["Retry-After"] = "60"
        logger.warning(
            "stock sync max_pages hint — markets=%s",
            [m.market_code for m in result.markets if m.error and "MaxPages" in m.error],
        )


@router.post(
    "/stocks/sync",
    response_model=StockMasterSyncResultOut,
    summary="5 시장 종목 마스터 강제 동기화 (admin)",
    dependencies=[Depends(require_admin_key)],
)
async def sync_stocks(
    response: Response,
    alias: Annotated[
        str,
        Query(
            min_length=1,
            max_length=50,
            description="사용할 키움 자격증명 alias (kiwoom_credential.alias)",
        ),
    ],
    factory: SyncStockMasterUseCaseFactory = Depends(get_sync_stock_factory),
) -> StockMasterSyncResultOut:
    """alias 의 자격증명으로 5 시장 sync. 시장 단위 격리 — 부분 실패 허용.

    예외 매핑 (sector 패턴 일관):
    - alias 미등록 → 404
    - alias 비활성 → 400
    - alias 한도 초과 → 503
    - 키움 호출 실패는 시장별로 outcome.error 격리 — 200 반환
    """
    try:
        async with factory(alias) as use_case:
            result = await use_case.execute()
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

    _mark_max_pages_hint(response, result)

    return StockMasterSyncResultOut(
        markets=[MarketStockOutcomeOut.model_validate(m) for m in result.markets],
        total_fetched=result.total_fetched,
        total_upserted=result.total_upserted,
        total_deactivated=result.total_deactivated,
        total_nxt_enabled=result.total_nxt_enabled,
        all_succeeded=result.all_succeeded,
    )


# =============================================================================
# GET /stocks/{stock_code} — 단건 조회 (B-β, DB only)
# =============================================================================


@router.get(
    "/stocks/{stock_code}",
    response_model=StockOut,
    summary="저장된 종목 단건 조회 (DB only)",
)
async def get_stock_by_code(
    stock_code: Annotated[
        str,
        Path(
            min_length=6,
            max_length=6,
            pattern=STK_CD_LOOKUP_PATTERN,
            description="6자리 숫자 종목코드 (`_NX`/`_AL` suffix 미허용)",
        ),
    ],
) -> StockOut:
    """DB read only — 키움 호출 없음.

    미존재 → 404. lazy fetch 가 필요한 경우 admin 의 POST /refresh 사용.
    """
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        repo = StockRepository(session)
        stock = await repo.find_by_code(stock_code)

    if stock is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"stock not found: {stock_code}",
        )
    return StockOut.model_validate(stock)


# =============================================================================
# POST /stocks/{stock_code}/refresh — 단건 강제 재조회 (B-β, admin)
# =============================================================================


@router.post(
    "/stocks/{stock_code}/refresh",
    response_model=StockOut,
    summary="단건 종목 마스터 강제 재조회 + DB upsert (admin)",
    dependencies=[Depends(require_admin_key)],
)
async def refresh_stock(
    stock_code: Annotated[
        str,
        Path(
            min_length=6,
            max_length=6,
            pattern=STK_CD_LOOKUP_PATTERN,
            description="6자리 숫자 종목코드 (`_NX`/`_AL` suffix 미허용)",
        ),
    ],
    alias: Annotated[
        str,
        Query(
            min_length=1,
            max_length=50,
            description="사용할 키움 자격증명 alias (kiwoom_credential.alias)",
        ),
    ],
    factory: LookupStockUseCaseFactory = Depends(get_lookup_stock_factory),
) -> StockOut:
    """ka10100 호출 → DB upsert → 갱신된 row 반환.

    예외 매핑 (sector/B-α 패턴 일관):
    - alias 미등록 → 404
    - alias 비활성 → 400
    - alias 한도 초과 → 503
    - KiwoomBusinessError (존재하지 않는 종목 등) → 400 + detail{return_code, return_msg}
    - KiwoomCredentialRejectedError → 400
    - KiwoomRateLimitedError → 503
    - KiwoomUpstreamError / 기타 KiwoomError → 502
    - KiwoomResponseValidationError → 502
    - ValueError (어댑터 stk_cd 사전 검증) → 400 (라우터 patten 으로 사전 차단되지만 안전망)
    """
    try:
        async with factory(alias) as use_case:
            stock = await use_case.execute(stock_code)
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
    except KiwoomBusinessError as exc:
        # 1R 2b H1 / B-α M-2 정책 — return_msg 는 attacker-influenced (키움 에코) 라
        # 응답 본문 echo 금지. detail 에는 비식별 메타 (return_code + 클래스명) 만 노출.
        # 키움 본문은 logger 경로로만 노출 (서버 사이드 운영 디버깅).
        logger.warning(
            "ka10100 business error api_id=%s return_code=%d msg=%s",
            exc.api_id,
            exc.return_code,
            exc.message,
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
        # 1R 2b M5 — 향후 신규 KiwoomError 서브클래스 안전망 + 운영 가시성.
        # detail 에 클래스명 / 메시지 echo 안 함. logger 로만 노출 (B-α M-2 패턴 일관).
        logger.warning("ka10100 fallback %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="키움 호출 실패",
        ) from None

    return StockOut.model_validate(stock)


__all__ = [
    "MarketStockOutcomeOut",
    "StockMasterSyncResultOut",
    "StockOut",
    "router",
]
