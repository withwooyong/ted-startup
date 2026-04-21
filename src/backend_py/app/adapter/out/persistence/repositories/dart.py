"""DART 기업코드 매핑 Repository."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.models import DartCorpMapping
from app.adapter.out.persistence.repositories._helpers import rowcount_of


class DartCorpMappingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_stock_code(self, stock_code: str) -> DartCorpMapping | None:
        # populate_existing: 직전 on_conflict upsert 로 갱신된 DB 값을 identity map 위에 덮어쓰기.
        stmt = (
            select(DartCorpMapping)
            .where(DartCorpMapping.stock_code == stock_code)
            .execution_options(populate_existing=True)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def find_by_corp_code(self, corp_code: str) -> DartCorpMapping | None:
        stmt = select(DartCorpMapping).where(DartCorpMapping.corp_code == corp_code)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def upsert_many(self, rows: Iterable[tuple[str, str, str]]) -> int:
        """(stock_code, corp_code, corp_name) 튜플을 일괄 upsert."""
        payload = [{"stock_code": s, "corp_code": c, "corp_name": n} for s, c, n in rows if s and c]
        if not payload:
            return 0
        stmt = pg_insert(DartCorpMapping).values(payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=["stock_code"],
            set_={
                "corp_code": stmt.excluded.corp_code,
                "corp_name": stmt.excluded.corp_name,
            },
        )
        result = await self._session.execute(stmt)
        return rowcount_of(result)

    async def list_all(self) -> Sequence[DartCorpMapping]:
        stmt = select(DartCorpMapping).order_by(DartCorpMapping.stock_code)
        return (await self._session.execute(stmt)).scalars().all()
