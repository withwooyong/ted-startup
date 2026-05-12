"""ShortSellingKwRepository — short_selling_kw upsert + 시그널 조회 (Phase E, ka10014).

설계: endpoint-15-ka10014.md § 6.2 + § 12.

책임:
- bulk upsert (`upsert_many`) — ON CONFLICT (stock_id, trading_date, exchange) DO UPDATE
- `trading_date == date.min` 빈 응답 row 자동 skip (caller 안전망)
- 명시 update_set (B-γ-1 2R B-H3 패턴 일관) — schema-drift 차단
- 시그널 조회 (`get_high_weight_stocks`) — partial index
  `idx_short_selling_kw_weight_high` 활용. NULL 제외 + weight DESC NULLS LAST.

D-1 sector_price.py / C-2α stock_daily_flow.py 패턴 1:1 응용.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._records import NormalizedShortSelling
from app.adapter.out.persistence.models.short_selling_kw import ShortSellingKw
from app.adapter.out.persistence.repositories._helpers import rowcount_of


class ShortSellingKwRepository:
    """ka10014 short_selling_kw upsert + 시그널 조회 (Phase E)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, rows: Sequence[NormalizedShortSelling]) -> int:
        """bulk upsert — ON CONFLICT (stock_id, trading_date, exchange) DO UPDATE.

        반환: 영향받은 row 수 (insert + update 합계).

        - `trading_date == date.min` 빈 응답 row 자동 skip (caller 안전망)
        - 명시 update_set — 미래 컬럼 추가 시 silent contract change 방지 (B-γ-1 2R B-H3)
        - ON CONFLICT key (stock_id, trading_date, exchange) 제외 (변경 불가)
        - `created_at` 의도적 제외 — 최초 insert 시각 보존
        """
        valid_rows = [r for r in rows if r.trading_date != date.min]
        if not valid_rows:
            return 0

        values: list[dict[str, Any]] = [
            {
                "stock_id": r.stock_id,
                "trading_date": r.trading_date,
                "exchange": r.exchange.value,
                "close_price": r.close_price,
                "prev_compare_amount": r.prev_compare_amount,
                "prev_compare_sign": r.prev_compare_sign,
                "change_rate": r.change_rate,
                "trade_volume": r.trade_volume,
                "short_volume": r.short_volume,
                "cumulative_short_volume": r.cumulative_short_volume,
                "short_trade_weight": r.short_trade_weight,
                "short_trade_amount": r.short_trade_amount,
                "short_avg_price": r.short_avg_price,
            }
            for r in valid_rows
        ]

        insert_stmt = pg_insert(ShortSellingKw).values(values)

        # 명시 update_set — schema-drift 차단 (B-γ-1 2R B-H3 일관).
        # ON CONFLICT key (stock_id, trading_date, exchange) 제외.
        # `created_at` 제외 — 최초 insert 시각 보존.
        update_set: dict[str, Any] = {
            "close_price": insert_stmt.excluded.close_price,
            "prev_compare_amount": insert_stmt.excluded.prev_compare_amount,
            "prev_compare_sign": insert_stmt.excluded.prev_compare_sign,
            "change_rate": insert_stmt.excluded.change_rate,
            "trade_volume": insert_stmt.excluded.trade_volume,
            "short_volume": insert_stmt.excluded.short_volume,
            "cumulative_short_volume": insert_stmt.excluded.cumulative_short_volume,
            "short_trade_weight": insert_stmt.excluded.short_trade_weight,
            "short_trade_amount": insert_stmt.excluded.short_trade_amount,
            "short_avg_price": insert_stmt.excluded.short_avg_price,
            "fetched_at": func.now(),
            "updated_at": func.now(),
        }

        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=["stock_id", "trading_date", "exchange"],
            set_=update_set,
        )

        result = await self._session.execute(upsert_stmt)
        await self._session.flush()
        return rowcount_of(result)

    async def get_range(
        self,
        stock_id: int,
        *,
        exchange: str,
        start_date: date,
        end_date: date,
    ) -> Sequence[ShortSellingKw]:
        """[start_date, end_date] 시계열 조회 — exchange 필터 + trading_date asc.

        Raises:
            ValueError: start_date > end_date.
        """
        if start_date > end_date:
            raise ValueError(
                f"start_date ({start_date}) must be <= end_date ({end_date})"
            )
        stmt = (
            select(ShortSellingKw)
            .where(
                ShortSellingKw.stock_id == stock_id,
                ShortSellingKw.exchange == exchange,
                ShortSellingKw.trading_date >= start_date,
                ShortSellingKw.trading_date <= end_date,
            )
            .order_by(ShortSellingKw.trading_date.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_high_weight_stocks(
        self,
        on_date: date,
        *,
        min_weight: Decimal,
        limit: int = 50,
    ) -> Sequence[ShortSellingKw]:
        """일별 공매도 매매비중 상위 종목 시그널 — `idx_short_selling_kw_weight_high` 활용.

        partial index 가 NULL 제외 + weight DESC. 본 쿼리도 일관되게 NULLS LAST + DESC
        정렬 + limit.
        """
        stmt = (
            select(ShortSellingKw)
            .where(
                ShortSellingKw.trading_date == on_date,
                ShortSellingKw.short_trade_weight.is_not(None),
                ShortSellingKw.short_trade_weight >= min_weight,
            )
            .order_by(ShortSellingKw.short_trade_weight.desc().nulls_last())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


__all__ = ["ShortSellingKwRepository"]
