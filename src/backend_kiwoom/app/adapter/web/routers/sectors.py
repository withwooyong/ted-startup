"""GET / POST /api/kiwoom/sectors — 업종 마스터 조회 + 동기화.

설계: endpoint-14-ka10101.md § 7.1.

라우터 구성:
- GET  /sectors                — 저장된 업종 마스터 조회 (DB only, admin 불필요)
- POST /sectors/sync           — 5 시장 강제 동기화 (admin only, alias 명시)

응답 정책:
- DB read 만 — 키움 호출 없음 (GET)
- POST sync 는 부분 성공 허용 — 200 + per-market outcomes
- F3 통합 (가벼운 hint): outcome.error 에 KiwoomMaxPagesExceededError 흔적 있으면
  응답 헤더 `Retry-After: 60` 추가 — 모니터링 hint, 응답 본문은 그대로 반환

세션 라이프사이클:
- GET: get_sessionmaker() 직접 호출 — 단일 read 세션
- POST: SyncSectorUseCaseFactory(alias) AsyncContextManager — 매 호출마다 새
  KiwoomClient 빌드 + close. UseCase 가 시장 단위로 자체 트랜잭션 관리.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app.adapter.out.persistence.repositories.sector import SectorRepository
from app.adapter.out.persistence.session import get_sessionmaker
from app.adapter.web._deps import (
    SyncSectorUseCaseFactory,
    get_sync_sector_factory,
    require_admin_key,
)
from app.application.service.sector_service import SectorSyncResult
from app.application.service.token_service import (
    AliasCapacityExceededError,
    CredentialInactiveError,
    CredentialNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kiwoom", tags=["kiwoom-sectors"])


# =============================================================================
# Pydantic 응답 DTO — ORM/dataclass → API 응답 변환
# =============================================================================


class SectorOut(BaseModel):
    """sector 테이블 row 의 외부 응답 표현."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    market_code: str
    sector_code: str
    sector_name: str
    group_no: str | None
    is_active: bool
    fetched_at: datetime


class MarketSyncOutcomeOut(BaseModel):
    """시장 단위 동기화 결과."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    market_code: str
    fetched: int
    upserted: int
    deactivated: int
    error: str | None = None


class SectorSyncResultOut(BaseModel):
    """5 시장 전체 동기화 결과."""

    model_config = ConfigDict(frozen=True)

    markets: list[MarketSyncOutcomeOut]
    total_fetched: int
    total_upserted: int
    total_deactivated: int
    all_succeeded: bool = Field(description="모든 시장이 error 없이 완료됐는지")


# =============================================================================
# GET /sectors — 조회 (admin 불필요)
# =============================================================================


@router.get(
    "/sectors",
    response_model=list[SectorOut],
    summary="저장된 업종 마스터 조회",
)
async def list_sectors(
    market_code: Annotated[
        Literal["0", "1", "2", "4", "7"] | None,
        Query(description="시장 코드. 미지정 시 5 시장 통합 조회"),
    ] = None,
    only_active: Annotated[
        bool,
        Query(description="활성 업종만 (기본 True)"),
    ] = True,
) -> list[SectorOut]:
    """DB read only — 키움 호출 없음.

    `market_code` 미지정 시 5 시장 통합. 정렬: market_code → sector_code.
    """
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        repo = SectorRepository(session)
        if market_code is None:
            rows = await repo.list_all(only_active=only_active)
        else:
            rows = await repo.list_by_market(market_code, only_active=only_active)

    return [SectorOut.model_validate(r) for r in rows]


# =============================================================================
# POST /sectors/sync — 강제 동기화 (admin)
# =============================================================================


def _mark_max_pages_hint(response: Response, result: SectorSyncResult) -> None:
    """F3 통합 — 한 시장 이상이 max_pages 한도 도달 시 Retry-After 헤더 hint.

    응답 코드/본문은 변경 없음 (200 + 부분 성공). 모니터링/oncall 알람용.
    """
    if any(m.error is not None and "MaxPages" in m.error for m in result.markets):
        response.headers["Retry-After"] = "60"
        logger.warning(
            "sector sync max_pages hint — markets=%s",
            [m.market_code for m in result.markets if m.error and "MaxPages" in m.error],
        )


@router.post(
    "/sectors/sync",
    response_model=SectorSyncResultOut,
    summary="5 시장 업종 마스터 강제 동기화 (admin)",
    dependencies=[Depends(require_admin_key)],
)
async def sync_sectors(
    response: Response,
    alias: Annotated[
        str,
        Query(
            min_length=1,
            max_length=50,
            description="사용할 키움 자격증명 alias (kiwoom_credential.alias)",
        ),
    ],
    factory: SyncSectorUseCaseFactory = Depends(get_sync_sector_factory),
) -> SectorSyncResultOut:
    """alias 의 자격증명으로 5 시장 sync. 시장 단위 격리 — 부분 실패 허용.

    예외 매핑:
    - alias 미등록 / 비활성 → 4xx (factory 가 token_provider 통해 raise)
    - 키움 호출 실패는 시장별로 outcome.error 에 격리 — 라우터는 200 반환
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

    return SectorSyncResultOut(
        markets=[MarketSyncOutcomeOut.model_validate(m) for m in result.markets],
        total_fetched=result.total_fetched,
        total_upserted=result.total_upserted,
        total_deactivated=result.total_deactivated,
        all_succeeded=result.all_succeeded,
    )


__all__ = [
    "MarketSyncOutcomeOut",
    "SectorOut",
    "SectorSyncResultOut",
    "router",
]
