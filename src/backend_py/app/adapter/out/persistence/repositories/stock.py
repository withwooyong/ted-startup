from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.models import Stock


class StockRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, stock: Stock) -> Stock:
        self._session.add(stock)
        await self._session.flush()
        return stock

    async def get(self, stock_id: int) -> Stock | None:
        return await self._session.get(Stock, stock_id)

    async def find_by_code(self, stock_code: str) -> Stock | None:
        stmt = select(Stock).where(Stock.stock_code == stock_code)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_active(self) -> Sequence[Stock]:
        stmt = select(Stock).where(Stock.is_active.is_(True)).order_by(Stock.stock_code)
        return (await self._session.execute(stmt)).scalars().all()
