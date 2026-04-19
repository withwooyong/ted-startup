"""/api/signals, /api/stocks/{code} 및 탐지 실행 라우터."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.repositories import (
    SignalRepository,
    StockPriceRepository,
    StockRepository,
)
from app.adapter.web._deps import get_session, require_admin_key
from app.adapter.web._schemas import (
    LatestSignalsResponse,
    SignalResponse,
    StockDetailResponse,
    StockPricePoint,
    StockSummary,
)
from app.application.dto.results import DetectionResult
from app.application.service import SignalDetectionService

router = APIRouter(prefix="/api", tags=["signals"])


@router.get("/signals", response_model=list[SignalResponse])
async def list_signals(
    signal_date: date | None = Query(default=None, alias="date"),
    signal_type: str | None = Query(default=None, alias="type"),
    session: AsyncSession = Depends(get_session),
) -> list[SignalResponse]:
    target = signal_date or date.today()
    signals = await SignalRepository(session).list_by_date(target)
    if signal_type:
        signals = [s for s in signals if s.signal_type == signal_type]

    if not signals:
        return []
    stock_ids = list({s.stock_id for s in signals})
    stocks = {s.id: s for s in await StockRepository(session).list_by_ids(stock_ids)}

    responses: list[SignalResponse] = []
    for sig in signals:
        stock = stocks.get(sig.stock_id)
        responses.append(
            SignalResponse(
                id=sig.id,
                stock_id=sig.stock_id,
                stock_code=stock.stock_code if stock else None,
                stock_name=stock.stock_name if stock else None,
                signal_date=sig.signal_date,
                signal_type=sig.signal_type,
                score=sig.score,
                grade=sig.grade,
                detail=sig.detail,
                return_5d=sig.return_5d,
                return_10d=sig.return_10d,
                return_20d=sig.return_20d,
            )
        )
    return responses


@router.get("/signals/latest", response_model=LatestSignalsResponse)
async def list_latest_signals(
    signal_type: str | None = Query(default=None, alias="type"),
    session: AsyncSession = Depends(get_session),
) -> LatestSignalsResponse:
    """가장 최근 탐지일의 시그널을 반환. 대시보드의 '오늘 빈 상태' 회피용."""
    signal_repo = SignalRepository(session)
    latest = await signal_repo.find_latest_signal_date()
    if latest is None:
        return LatestSignalsResponse(signal_date=None, signals=[])

    signals = await signal_repo.list_by_date(latest)
    if signal_type:
        signals = [s for s in signals if s.signal_type == signal_type]
    if not signals:
        return LatestSignalsResponse(signal_date=latest, signals=[])

    stock_ids = list({s.stock_id for s in signals})
    stocks = {s.id: s for s in await StockRepository(session).list_by_ids(stock_ids)}
    return LatestSignalsResponse(
        signal_date=latest,
        signals=[
            SignalResponse(
                id=sig.id,
                stock_id=sig.stock_id,
                stock_code=stocks.get(sig.stock_id).stock_code if stocks.get(sig.stock_id) else None,
                stock_name=stocks.get(sig.stock_id).stock_name if stocks.get(sig.stock_id) else None,
                signal_date=sig.signal_date,
                signal_type=sig.signal_type,
                score=sig.score,
                grade=sig.grade,
                detail=sig.detail,
                return_5d=sig.return_5d,
                return_10d=sig.return_10d,
                return_20d=sig.return_20d,
            )
            for sig in signals
        ],
    )


@router.get("/stocks/{stock_code}", response_model=StockDetailResponse)
async def get_stock_detail(
    stock_code: str = Path(pattern=r"^\d{6}$"),
    period_from: date | None = Query(default=None, alias="from"),
    period_to: date | None = Query(default=None, alias="to"),
    session: AsyncSession = Depends(get_session),
) -> StockDetailResponse:
    to_date = period_to or date.today()
    from_date = period_from or (to_date - timedelta(days=92))
    if from_date > to_date:
        raise HTTPException(status_code=400, detail="from 이 to 보다 미래일 수 없습니다")

    stock = await StockRepository(session).find_by_code(stock_code)
    if stock is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="종목을 찾을 수 없습니다")

    prices = await StockPriceRepository(session).list_between(stock.id, from_date, to_date)
    signals = await SignalRepository(session).list_by_stock(stock.id, limit=90)
    signals_in_range = [s for s in signals if from_date <= s.signal_date <= to_date]

    return StockDetailResponse(
        stock=StockSummary.model_validate(stock),
        prices=[StockPricePoint.model_validate(p) for p in prices],
        signals=[
            SignalResponse(
                id=s.id,
                stock_id=s.stock_id,
                stock_code=stock.stock_code,
                stock_name=stock.stock_name,
                signal_date=s.signal_date,
                signal_type=s.signal_type,
                score=s.score,
                grade=s.grade,
                detail=s.detail,
                return_5d=s.return_5d,
                return_10d=s.return_10d,
                return_20d=s.return_20d,
            )
            for s in signals_in_range
        ],
    )


@router.post(
    "/signals/detect",
    response_model=DetectionResult,
    dependencies=[Depends(require_admin_key)],
)
async def detect_signals(
    target: date | None = Query(default=None, alias="date"),
    session: AsyncSession = Depends(get_session),
) -> DetectionResult:
    target_date = target or date.today()
    if target_date > date.today():
        raise HTTPException(status_code=400, detail="date 는 오늘 이전이어야 합니다")
    return await SignalDetectionService(session).detect_all(target_date)
