from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.models import Signal


class SignalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, signal: Signal) -> Signal:
        self._session.add(signal)
        await self._session.flush()
        return signal

    async def list_by_date(self, signal_date: date) -> Sequence[Signal]:
        stmt = select(Signal).where(Signal.signal_date == signal_date).order_by(Signal.score.desc())
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_stock(self, stock_id: int, limit: int = 30) -> Sequence[Signal]:
        stmt = (
            select(Signal)
            .where(Signal.stock_id == stock_id)
            .order_by(Signal.signal_date.desc())
            .limit(limit)
        )
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
