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
        stmt = select(Stock).where(Stock.is_active.is_(True), Stock.deleted_at.is_(None)).order_by(Stock.stock_code)
        return (await self._session.execute(stmt)).scalars().all()

    async def list_by_ids(self, stock_ids: Sequence[int]) -> Sequence[Stock]:
        if not stock_ids:
            return []
        stmt = select(Stock).where(Stock.id.in_(list(stock_ids)))
        return (await self._session.execute(stmt)).scalars().all()

    async def upsert_by_code(self, stock_code: str, stock_name: str, market_type: str) -> Stock:
        """종목코드 기준 upsert — 활성 종목 목록을 수집 단계에서 유지.

        pykrx 가 종목명을 반환하지 않는 배치 경로에서 `stock_name` 이 빈 문자열로
        들어오는 경우, 기존 row 의 이름을 덮어쓰지 않고 보존한다. β 가 시드한 5개
        핵심 종목 이름 등이 α 재실행으로 공백화되는 회귀를 방지.
        """
        existing = await self.find_by_code(stock_code)
        if existing is None:
            stock = Stock(stock_code=stock_code, stock_name=stock_name, market_type=market_type)
            self._session.add(stock)
            await self._session.flush()
            return stock
        # 빈 이름은 기존 값을 덮어쓰지 않음
        new_name = stock_name if stock_name.strip() else existing.stock_name
        if existing.stock_name != new_name or existing.market_type != market_type:
            existing.stock_name = new_name
            existing.market_type = market_type
            await self._session.flush()
        return existing
