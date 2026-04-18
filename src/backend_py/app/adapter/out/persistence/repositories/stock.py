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
        stmt = (
            select(Stock)
            .where(Stock.is_active.is_(True), Stock.deleted_at.is_(None))
            .order_by(Stock.stock_code)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def upsert_by_code(self, stock_code: str, stock_name: str, market_type: str) -> Stock:
        """종목코드 기준 upsert — 활성 종목 목록을 수집 단계에서 유지."""
        existing = await self.find_by_code(stock_code)
        if existing is None:
            stock = Stock(stock_code=stock_code, stock_name=stock_name, market_type=market_type)
            self._session.add(stock)
            await self._session.flush()
            return stock
        if existing.stock_name != stock_name or existing.market_type != market_type:
            existing.stock_name = stock_name
            existing.market_type = market_type
            await self._session.flush()
        return existing
