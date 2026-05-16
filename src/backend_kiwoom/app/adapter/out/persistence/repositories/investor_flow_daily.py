"""InvestorFlowDailyRepository — Phase G ka10058 (투자자별 일별 매매 종목 ranking).

설계: phase-g-investor-flow.md § 5.3 + endpoint-23-ka10058.md § 6.2.

책임:
- bulk upsert (``upsert_many``) — ON CONFLICT (6 컬럼 UNIQUE) DO UPDATE.
- ``get_top_stocks`` — (date, investor_type, trade_type, market_type, exchange_type) 필터 + rank ASC.
- 명시 update_set (B-γ-1 2R B-H3 패턴) — schema-drift 차단.

F-4 ``RankingSnapshotRepository`` 패턴 1:1 응용 — ``_chunked_upsert`` helper 활용.
``NormalizedInvestorDailyTrade`` enum 값을 ``.value`` 로 풀어 영속화.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._records import (
    InvestorMarketType,
    InvestorTradeType,
    InvestorType,
    NormalizedInvestorDailyTrade,
    RankingExchangeType,
)
from app.adapter.out.persistence.models.investor_flow_daily import InvestorFlowDaily
from app.adapter.out.persistence.repositories._helpers import _chunked_upsert


class InvestorFlowDailyRepository:
    """Phase G investor_flow_daily upsert + 조회 (ka10058)."""

    DEFAULT_GET_LIMIT: int = 50
    """get_top_stocks 기본 limit (endpoint-23 § 6.2)."""

    # 14 도메인 + 메타 = 15 col. 200 × 15 = 3000 < 32767 (PostgreSQL wire protocol 한도).
    # ka10058 의 default 12 호출 매트릭스 × ~150 row = ~1,800 row/sync — 200 chunk 충분.
    _UPSERT_CHUNK_SIZE: int = 200

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(
        self,
        rows: Sequence[NormalizedInvestorDailyTrade],
    ) -> int:
        """bulk upsert — ON CONFLICT (6 컬럼 UNIQUE) DO UPDATE.

        반환: 영향받은 row 수 (insert + update 합계).
        - 빈 입력 → 0 (early return).
        - ``_chunked_upsert`` helper — PostgreSQL int16 한도 32767 안전.
        - ``created_at`` 의도적 제외 — 최초 insert 시각 보존.
        """
        if not rows:
            return 0

        values: list[dict[str, Any]] = [
            {
                "as_of_date": r.as_of_date,
                "market_type": r.market_type.value,
                "exchange_type": r.exchange_type.value,
                "investor_type": r.investor_type.value,
                "trade_type": r.trade_type.value,
                "rank": r.rank,
                "stock_id": r.stock_id,
                "stock_code_raw": r.stock_code_raw,
                "stock_name": r.stock_name or None,
                "net_volume": r.net_volume,
                "net_amount": r.net_amount,
                "estimated_avg_price": r.estimated_avg_price,
                "current_price": r.current_price,
                "prev_compare_sign": r.prev_compare_sign,
                "prev_compare_amount": r.prev_compare_amount,
                "avg_price_compare": r.avg_price_compare,
                "prev_compare_rate": r.prev_compare_rate,
                "period_volume": r.period_volume,
            }
            for r in rows
        ]

        def _statement_factory(chunk: list[dict[str, Any]]) -> Any:
            insert_stmt = pg_insert(InvestorFlowDaily).values(chunk)
            update_set: dict[str, Any] = {
                "stock_id": insert_stmt.excluded.stock_id,
                "stock_code_raw": insert_stmt.excluded.stock_code_raw,
                "stock_name": insert_stmt.excluded.stock_name,
                "net_volume": insert_stmt.excluded.net_volume,
                "net_amount": insert_stmt.excluded.net_amount,
                "estimated_avg_price": insert_stmt.excluded.estimated_avg_price,
                "current_price": insert_stmt.excluded.current_price,
                "prev_compare_sign": insert_stmt.excluded.prev_compare_sign,
                "prev_compare_amount": insert_stmt.excluded.prev_compare_amount,
                "avg_price_compare": insert_stmt.excluded.avg_price_compare,
                "prev_compare_rate": insert_stmt.excluded.prev_compare_rate,
                "period_volume": insert_stmt.excluded.period_volume,
                "fetched_at": func.now(),
            }
            return insert_stmt.on_conflict_do_update(
                index_elements=[
                    "as_of_date",
                    "market_type",
                    "exchange_type",
                    "investor_type",
                    "trade_type",
                    "rank",
                ],
                set_=update_set,
            )

        total = await _chunked_upsert(
            self._session,
            _statement_factory,
            values,
            chunk_size=self._UPSERT_CHUNK_SIZE,
        )
        await self._session.flush()
        return total

    async def get_top_stocks(
        self,
        *,
        as_of_date: date,
        investor_type: InvestorType,
        trade_type: InvestorTradeType,
        market_type: InvestorMarketType = InvestorMarketType.KOSPI,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
        limit: int = DEFAULT_GET_LIMIT,
    ) -> list[InvestorFlowDaily]:
        """투자자별 일별 매매 종목 상위 N — rank ASC."""
        stmt = (
            select(InvestorFlowDaily)
            .where(
                InvestorFlowDaily.as_of_date == as_of_date,
                InvestorFlowDaily.investor_type == investor_type.value,
                InvestorFlowDaily.trade_type == trade_type.value,
                InvestorFlowDaily.market_type == market_type.value,
                InvestorFlowDaily.exchange_type == exchange_type.value,
            )
            .order_by(InvestorFlowDaily.rank.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


__all__ = ["InvestorFlowDailyRepository"]
