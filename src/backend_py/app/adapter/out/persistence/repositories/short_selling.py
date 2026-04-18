from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.models import ShortSelling


class ShortSellingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, rows: Sequence[dict]) -> int:
        if not rows:
            return 0
        stmt = pg_insert(ShortSelling).values(list(rows))
        stmt = stmt.on_conflict_do_update(
            index_elements=["stock_id", "trading_date"],
            set_={
                "short_volume": stmt.excluded.short_volume,
                "short_amount": stmt.excluded.short_amount,
                "short_ratio": stmt.excluded.short_ratio,
            },
        )
        result = await self._session.execute(stmt)
        return result.rowcount or 0
