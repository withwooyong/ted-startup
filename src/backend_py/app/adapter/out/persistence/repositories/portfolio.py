"""포트폴리오 도메인 Repository — 계좌/보유/거래/스냅샷."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.models import (
    BrokerageAccount,
    PortfolioHolding,
    PortfolioSnapshot,
    PortfolioTransaction,
)


class BrokerageAccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, account: BrokerageAccount) -> BrokerageAccount:
        self._session.add(account)
        await self._session.flush()
        await self._session.refresh(account)
        return account

    async def get(self, account_id: int) -> BrokerageAccount | None:
        return await self._session.get(BrokerageAccount, account_id)

    async def find_by_alias(self, alias: str) -> BrokerageAccount | None:
        stmt = select(BrokerageAccount).where(BrokerageAccount.account_alias == alias)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_active(self) -> Sequence[BrokerageAccount]:
        stmt = (
            select(BrokerageAccount)
            .where(BrokerageAccount.is_active.is_(True))
            .order_by(BrokerageAccount.id)
        )
        return (await self._session.execute(stmt)).scalars().all()


class PortfolioHoldingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_account_and_stock(
        self, account_id: int, stock_id: int
    ) -> PortfolioHolding | None:
        stmt = select(PortfolioHolding).where(
            PortfolioHolding.account_id == account_id,
            PortfolioHolding.stock_id == stock_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_by_account(self, account_id: int, *, only_active: bool = True) -> Sequence[PortfolioHolding]:
        stmt = select(PortfolioHolding).where(PortfolioHolding.account_id == account_id)
        if only_active:
            stmt = stmt.where(PortfolioHolding.quantity > 0)
        stmt = stmt.order_by(PortfolioHolding.stock_id)
        return (await self._session.execute(stmt)).scalars().all()

    async def upsert(self, holding: PortfolioHolding) -> PortfolioHolding:
        self._session.add(holding)
        await self._session.flush()
        await self._session.refresh(holding)
        return holding


class PortfolioTransactionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, tx: PortfolioTransaction) -> PortfolioTransaction:
        self._session.add(tx)
        await self._session.flush()
        await self._session.refresh(tx)
        return tx

    async def list_by_account(
        self, account_id: int, *, limit: int = 100
    ) -> Sequence[PortfolioTransaction]:
        stmt = (
            select(PortfolioTransaction)
            .where(PortfolioTransaction.account_id == account_id)
            .order_by(PortfolioTransaction.executed_at.desc(), PortfolioTransaction.id.desc())
            .limit(limit)
        )
        return (await self._session.execute(stmt)).scalars().all()


class PortfolioSnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, snapshot: PortfolioSnapshot) -> PortfolioSnapshot:
        existing = await self.find_by_date(snapshot.account_id, snapshot.snapshot_date)
        if existing is None:
            self._session.add(snapshot)
            await self._session.flush()
            await self._session.refresh(snapshot)
            return snapshot
        existing.total_value = snapshot.total_value
        existing.total_cost = snapshot.total_cost
        existing.unrealized_pnl = snapshot.unrealized_pnl
        existing.realized_pnl = snapshot.realized_pnl
        existing.holdings_count = snapshot.holdings_count
        await self._session.flush()
        return existing

    async def find_by_date(self, account_id: int, snapshot_date: date) -> PortfolioSnapshot | None:
        stmt = select(PortfolioSnapshot).where(
            PortfolioSnapshot.account_id == account_id,
            PortfolioSnapshot.snapshot_date == snapshot_date,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_between(
        self, account_id: int, start: date, end: date
    ) -> Sequence[PortfolioSnapshot]:
        stmt = (
            select(PortfolioSnapshot)
            .where(
                PortfolioSnapshot.account_id == account_id,
                PortfolioSnapshot.snapshot_date >= start,
                PortfolioSnapshot.snapshot_date <= end,
            )
            .order_by(PortfolioSnapshot.snapshot_date)
        )
        return (await self._session.execute(stmt)).scalars().all()
