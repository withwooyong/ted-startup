from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.models import LendingBalance


class LendingBalanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, rows: Sequence[dict]) -> int:
        if not rows:
            return 0
        stmt = pg_insert(LendingBalance).values(list(rows))
        stmt = stmt.on_conflict_do_update(
            index_elements=["stock_id", "trading_date"],
            set_={
                "balance_quantity": stmt.excluded.balance_quantity,
                "balance_amount": stmt.excluded.balance_amount,
                "change_rate": stmt.excluded.change_rate,
                "change_quantity": stmt.excluded.change_quantity,
                "consecutive_decrease_days": stmt.excluded.consecutive_decrease_days,
            },
        )
        result = await self._session.execute(stmt)
        return result.rowcount or 0

    async def list_by_trading_date(self, trading_date: date) -> Sequence[LendingBalance]:
        stmt = select(LendingBalance).where(LendingBalance.trading_date == trading_date)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_stocks_between(
        self, stock_ids: Sequence[int], start: date, end: date
    ) -> Sequence[LendingBalance]:
        if not stock_ids:
            return []
        stmt = (
            select(LendingBalance)
            .where(
                LendingBalance.stock_id.in_(list(stock_ids)),
                LendingBalance.trading_date >= start,
                LendingBalance.trading_date <= end,
            )
            .order_by(LendingBalance.stock_id, LendingBalance.trading_date)
        )
        return (await self._session.execute(stmt)).scalars().all()
