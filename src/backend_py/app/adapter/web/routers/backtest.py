"""/api/backtest 결과 조회 + 실행."""
from __future__ import annotations

from datetime import date
from dateutil.relativedelta import relativedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.web._deps import get_session, require_admin_key
from app.adapter.web._schemas import BacktestResultResponse
from app.adapter.out.persistence.models import BacktestResult, SignalType
from app.application.dto.results import BacktestExecutionResult
from app.application.service import BacktestEngineService

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.get("", response_model=list[BacktestResultResponse])
async def list_latest_results(
    session: AsyncSession = Depends(get_session),
) -> list[BacktestResultResponse]:
    """각 SignalType 별 최신 1건씩 반환 (Java GetBacktestResultsUseCase 동등)."""
    out: list[BacktestResult] = []
    for sig_type in SignalType:
        stmt = (
            select(BacktestResult)
            .where(BacktestResult.signal_type == sig_type.value)
            .order_by(BacktestResult.period_end.desc(), BacktestResult.id.desc())
            .limit(1)
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is not None:
            out.append(row)
    return [BacktestResultResponse.model_validate(r) for r in out]


@router.post(
    "/run",
    response_model=BacktestExecutionResult,
    dependencies=[Depends(require_admin_key)],
)
async def run_backtest(
    period_from: date | None = Query(default=None, alias="from"),
    period_to: date | None = Query(default=None, alias="to"),
    session: AsyncSession = Depends(get_session),
) -> BacktestExecutionResult:
    today = date.today()
    end = period_to or today
    start = period_from or (end - relativedelta(years=3))

    if end > today:
        raise HTTPException(status_code=400, detail="to 는 오늘 이후일 수 없습니다")
    if start > end:
        raise HTTPException(status_code=400, detail="from 이 to 보다 미래일 수 없습니다")
    if start < end - relativedelta(years=3):
        raise HTTPException(status_code=400, detail="백테스트 최대 기간은 3년 입니다")

    return await BacktestEngineService(session).execute(start, end)
