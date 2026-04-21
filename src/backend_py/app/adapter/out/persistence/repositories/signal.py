from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.models import Signal


class SignalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, signal: Signal) -> Signal:
        self._session.add(signal)
        await self._session.flush()
        return signal

    async def list_by_date(self, signal_date: date, *, limit: int | None = None) -> Sequence[Signal]:
        """특정일 시그널을 score 내림차순으로 반환.

        limit=None 이면 전량(SignalDetectionService 의 중복 검사 경로).
        API 로 노출되는 라우터는 항상 명시 limit 을 주입한다.
        """
        stmt = select(Signal).where(Signal.signal_date == signal_date).order_by(Signal.score.desc())
        if limit is not None:
            stmt = stmt.limit(limit)
        return (await self._session.execute(stmt)).scalars().all()

    async def find_latest_signal_date(self) -> date | None:
        """탐지된 시그널 중 가장 최근 signal_date. 행 없음이면 None."""
        stmt = select(func.max(Signal.signal_date))
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_stock(self, stock_id: int, limit: int = 30) -> Sequence[Signal]:
        stmt = select(Signal).where(Signal.stock_id == stock_id).order_by(Signal.signal_date.desc()).limit(limit)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_between(self, start: date, end: date) -> Sequence[Signal]:
        stmt = (
            select(Signal)
            .where(Signal.signal_date >= start, Signal.signal_date <= end)
            .order_by(Signal.signal_date, Signal.stock_id)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def add_many(self, signals: Sequence[Signal]) -> int:
        if not signals:
            return 0
        self._session.add_all(list(signals))
        await self._session.flush()
        return len(signals)

    async def list_by_stocks_between(
        self,
        stock_ids: Sequence[int],
        start: date,
        end: date,
        *,
        min_score: int = 0,
    ) -> Sequence[Signal]:
        """여러 종목의 기간 시그널을 한 번에 조회 (P12 정합도용, N+1 방지)."""
        if not stock_ids:
            return []
        stmt = (
            select(Signal)
            .where(
                Signal.stock_id.in_(list(stock_ids)),
                Signal.signal_date >= start,
                Signal.signal_date <= end,
                Signal.score >= min_score,
            )
            .order_by(Signal.signal_date.desc(), Signal.score.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()
