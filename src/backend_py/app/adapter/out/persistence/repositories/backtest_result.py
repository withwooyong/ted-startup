from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.models import BacktestResult


class BacktestResultRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, result: BacktestResult) -> BacktestResult:
        self._session.add(result)
        await self._session.flush()
        return result

    async def list_by_signal_type(self, signal_type: str) -> Sequence[BacktestResult]:
        stmt = (
            select(BacktestResult)
            .where(BacktestResult.signal_type == signal_type)
            .order_by(BacktestResult.period_end.desc())
        )
        return (await self._session.execute(stmt)).scalars().all()
