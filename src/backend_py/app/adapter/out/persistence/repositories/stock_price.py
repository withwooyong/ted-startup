from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.models import StockPrice
from app.adapter.out.persistence.repositories._helpers import rowcount_of


class StockPriceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, rows: Sequence[dict[str, Any]]) -> int:
        """(stock_id, trading_date) 충돌 시 시세 컬럼 업데이트."""
        if not rows:
            return 0
        stmt = pg_insert(StockPrice).values(list(rows))
        update_cols = {
            "close_price": stmt.excluded.close_price,
            "open_price": stmt.excluded.open_price,
            "high_price": stmt.excluded.high_price,
            "low_price": stmt.excluded.low_price,
            "volume": stmt.excluded.volume,
            "market_cap": stmt.excluded.market_cap,
            "change_rate": stmt.excluded.change_rate,
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["stock_id", "trading_date"], set_=update_cols
        )
        result = await self._session.execute(stmt)
        return rowcount_of(result)

    async def find_by_stock_and_date(self, stock_id: int, trading_date: date) -> StockPrice | None:
        stmt = select(StockPrice).where(
            StockPrice.stock_id == stock_id, StockPrice.trading_date == trading_date
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_between(
        self, stock_id: int, start: date, end: date
    ) -> Sequence[StockPrice]:
        stmt = (
            select(StockPrice)
            .where(
                StockPrice.stock_id == stock_id,
                StockPrice.trading_date >= start,
                StockPrice.trading_date <= end,
            )
            .order_by(StockPrice.trading_date)
        )
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_trading_date(self, trading_date: date) -> Sequence[StockPrice]:
        stmt = select(StockPrice).where(StockPrice.trading_date == trading_date)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_stocks_between(
        self, stock_ids: Sequence[int], start: date, end: date
    ) -> Sequence[StockPrice]:
        if not stock_ids:
            return []
        stmt = (
            select(StockPrice)
            .where(
                StockPrice.stock_id.in_(list(stock_ids)),
                StockPrice.trading_date >= start,
                StockPrice.trading_date <= end,
            )
            .order_by(StockPrice.stock_id, StockPrice.trading_date)
        )
        return (await self._session.execute(stmt)).scalars().all()
