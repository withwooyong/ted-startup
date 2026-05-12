"""LendingBalanceKwRepository — ka10068 + ka20068 대차거래 upsert/조회 (Phase E).

설계: endpoint-16-ka10068.md § 6.2 + endpoint-17-ka20068.md § 6.2 + endpoint-15-ka10014.md § 12.

sector_price (D-1) upsert_many 패턴 + scope 분기 = stock_daily_flow (C-2α) KRX/NXT
분리 패턴 응용.

책임:
- `upsert_market` — scope=MARKET 적재 (stock_id NULL). ON CONFLICT (scope, trading_date)
  WHERE scope='MARKET'.
- `upsert_stock` — scope=STOCK 적재 (stock_id FK). ON CONFLICT (scope, stock_id, trading_date)
  WHERE scope='STOCK'.
- `get_market_range` / `get_stock_range` — 시계열 조회 (ASC 정렬).
- `trading_date == date.min` 또는 STOCK scope 의 stock_id None 은 자동 skip.
- 명시 update_set — 미래 컬럼 추가 시 silent contract change 방지.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._records import LendingScope, NormalizedLendingMarket
from app.adapter.out.persistence.models.lending_balance_kw import LendingBalanceKw
from app.adapter.out.persistence.repositories._helpers import rowcount_of


class LendingBalanceKwRepository:
    """MARKET / STOCK 두 scope 통합 인터페이스 — lending_balance_kw 영속 계층."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_market(self, rows: Sequence[NormalizedLendingMarket]) -> int:
        """ka10068 — scope=MARKET 적재 (stock_id NULL).

        ON CONFLICT (scope, trading_date) WHERE scope='MARKET' AND stock_id IS NULL
        DO UPDATE — partial unique index 매핑.

        - `trading_date == date.min` 빈 응답 row 자동 skip
        - 명시 update_set — schema-drift 차단
        - 반환: 영향받은 row 수 (insert + update 합계)
        """
        if not rows:
            return 0

        values: list[dict[str, Any]] = [
            {
                "scope": LendingScope.MARKET.value,
                "stock_id": None,
                "trading_date": r.trading_date,
                "contracted_volume": r.contracted_volume,
                "repaid_volume": r.repaid_volume,
                "delta_volume": r.delta_volume,
                "balance_volume": r.balance_volume,
                "balance_amount": r.balance_amount,
            }
            for r in rows
            if r.trading_date != date.min
        ]
        if not values:
            return 0

        insert_stmt = pg_insert(LendingBalanceKw).values(values)

        # 명시 update_set — ON CONFLICT 키 (scope, trading_date) 의도적 제외.
        # `created_at` 의도적 제외 — 최초 insert 시각 보존.
        update_set: dict[str, Any] = {
            "contracted_volume": insert_stmt.excluded.contracted_volume,
            "repaid_volume": insert_stmt.excluded.repaid_volume,
            "delta_volume": insert_stmt.excluded.delta_volume,
            "balance_volume": insert_stmt.excluded.balance_volume,
            "balance_amount": insert_stmt.excluded.balance_amount,
            "fetched_at": func.now(),
            "updated_at": func.now(),
        }

        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=["scope", "trading_date"],
            index_where=text("scope = 'MARKET' AND stock_id IS NULL"),
            set_=update_set,
        )

        result = await self._session.execute(upsert_stmt)
        await self._session.flush()
        return rowcount_of(result)

    async def upsert_stock(self, rows: Sequence[NormalizedLendingMarket]) -> int:
        """ka20068 — scope=STOCK 적재 (stock_id FK).

        ON CONFLICT (scope, stock_id, trading_date) WHERE scope='STOCK' AND
        stock_id IS NOT NULL DO UPDATE — partial unique index 매핑.

        - `trading_date == date.min` 또는 `stock_id is None` 빈 응답 row 자동 skip
        - 명시 update_set — schema-drift 차단
        - 반환: 영향받은 row 수
        """
        if not rows:
            return 0

        values: list[dict[str, Any]] = [
            {
                "scope": LendingScope.STOCK.value,
                "stock_id": r.stock_id,
                "trading_date": r.trading_date,
                "contracted_volume": r.contracted_volume,
                "repaid_volume": r.repaid_volume,
                "delta_volume": r.delta_volume,
                "balance_volume": r.balance_volume,
                "balance_amount": r.balance_amount,
            }
            for r in rows
            if r.trading_date != date.min and r.stock_id is not None
        ]
        if not values:
            return 0

        insert_stmt = pg_insert(LendingBalanceKw).values(values)

        update_set: dict[str, Any] = {
            "contracted_volume": insert_stmt.excluded.contracted_volume,
            "repaid_volume": insert_stmt.excluded.repaid_volume,
            "delta_volume": insert_stmt.excluded.delta_volume,
            "balance_volume": insert_stmt.excluded.balance_volume,
            "balance_amount": insert_stmt.excluded.balance_amount,
            "fetched_at": func.now(),
            "updated_at": func.now(),
        }

        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=["scope", "stock_id", "trading_date"],
            index_where=text("scope = 'STOCK' AND stock_id IS NOT NULL"),
            set_=update_set,
        )

        result = await self._session.execute(upsert_stmt)
        await self._session.flush()
        return rowcount_of(result)

    async def get_market_range(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> Sequence[LendingBalanceKw]:
        """ka10068 — scope=MARKET 시계열 조회.

        start_date <= trading_date <= end_date 사이의 MARKET row, trading_date ASC 정렬.
        """
        if start_date > end_date:
            raise ValueError(f"start_date ({start_date}) must be <= end_date ({end_date})")
        stmt = (
            select(LendingBalanceKw)
            .where(
                LendingBalanceKw.scope == LendingScope.MARKET.value,
                LendingBalanceKw.trading_date >= start_date,
                LendingBalanceKw.trading_date <= end_date,
            )
            .order_by(LendingBalanceKw.trading_date.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_stock_range(
        self,
        stock_id: int,
        *,
        start_date: date,
        end_date: date,
    ) -> Sequence[LendingBalanceKw]:
        """ka20068 — scope=STOCK 시계열 조회 (특정 종목).

        해당 stock_id 의 STOCK row, trading_date ASC 정렬.
        다른 종목 row 는 포함되지 않음 (stock_id 필터).
        """
        if start_date > end_date:
            raise ValueError(f"start_date ({start_date}) must be <= end_date ({end_date})")
        stmt = (
            select(LendingBalanceKw)
            .where(
                LendingBalanceKw.scope == LendingScope.STOCK.value,
                LendingBalanceKw.stock_id == stock_id,
                LendingBalanceKw.trading_date >= start_date,
                LendingBalanceKw.trading_date <= end_date,
            )
            .order_by(LendingBalanceKw.trading_date.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


__all__ = ["LendingBalanceKwRepository"]
