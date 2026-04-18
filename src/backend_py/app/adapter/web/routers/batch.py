"""/api/batch/collect — 관리자 권한 수동 수집."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.web._deps import get_krx_client, get_session, require_admin_key
from app.adapter.out.external import KrxClient
from app.application.dto.results import CollectionResult
from app.application.service import MarketDataCollectionService

router = APIRouter(prefix="/api/batch", tags=["batch"])


@router.post(
    "/collect",
    response_model=CollectionResult,
    dependencies=[Depends(require_admin_key)],
)
async def collect(
    target: date | None = Query(default=None, alias="date"),
    session: AsyncSession = Depends(get_session),
    krx: KrxClient = Depends(get_krx_client),
) -> CollectionResult:
    target_date = target or date.today()
    if target_date > date.today():
        raise HTTPException(status_code=400, detail="date 는 오늘 이전이어야 합니다")
    return await MarketDataCollectionService(krx, session).collect_all(target_date)
