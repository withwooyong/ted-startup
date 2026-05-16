"""FrgnOrgnConsecutiveRepository — Phase G ka10131 (기관/외국인 연속매매 ranking).

설계: phase-g-investor-flow.md § 5.3 + endpoint-25-ka10131.md § 6.2.

책임:
- bulk upsert (``upsert_many``) — ON CONFLICT (7 컬럼 UNIQUE) DO UPDATE.
- ``get_top_by_total_days`` — 합계 연속순매수 일수 상위 종목 (시그널 핵심).
  ``ORDER BY total_cont_days DESC NULLS LAST``.

rank == 0 row (빈 응답 표식) → 영속화 직전 skip.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import func, nulls_last, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._records import (
    ContinuousAmtQtyType,
    ContinuousPeriodType,
    InvestorMarketType,
    NormalizedFrgnOrgnConsecutive,
    RankingExchangeType,
    StockIndsType,
)
from app.adapter.out.persistence.models.frgn_orgn_consecutive import FrgnOrgnConsecutive
from app.adapter.out.persistence.repositories._helpers import _chunked_upsert


class FrgnOrgnConsecutiveRepository:
    """Phase G frgn_orgn_consecutive upsert + 조회 (ka10131, 15 metric)."""

    DEFAULT_GET_LIMIT: int = 50
    """get_top_by_total_days 기본 limit."""

    # 29 컬럼 (id 제외) — 200 × 29 = 5800 < 32767 안전.
    _UPSERT_CHUNK_SIZE: int = 200

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(
        self,
        rows: Sequence[NormalizedFrgnOrgnConsecutive],
    ) -> int:
        """bulk upsert — ON CONFLICT (7 컬럼 UNIQUE) DO UPDATE.

        rank == 0 row 는 빈 응답 표식 (``to_normalized`` 가 ``_to_int(self.rank) or 0``
        반환) — 영속화 직전 skip.
        """
        if not rows:
            return 0

        values: list[dict[str, Any]] = [
            {
                "as_of_date": r.as_of_date,
                "period_type": r.period_type.value,
                "market_type": r.market_type.value,
                "amt_qty_tp": r.amt_qty_tp.value,
                "stk_inds_tp": r.stk_inds_tp.value,
                "exchange_type": r.exchange_type.value,
                "rank": r.rank,
                "stock_id": r.stock_id,
                "stock_code_raw": r.stock_code_raw,
                "stock_name": r.stock_name or None,
                "period_stock_price_flu_rt": r.period_stock_price_flu_rt,
                "orgn_net_amount": r.orgn_net_amount,
                "orgn_net_volume": r.orgn_net_volume,
                "orgn_cont_days": r.orgn_cont_days,
                "orgn_cont_volume": r.orgn_cont_volume,
                "orgn_cont_amount": r.orgn_cont_amount,
                "frgnr_net_volume": r.frgnr_net_volume,
                "frgnr_net_amount": r.frgnr_net_amount,
                "frgnr_cont_days": r.frgnr_cont_days,
                "frgnr_cont_volume": r.frgnr_cont_volume,
                "frgnr_cont_amount": r.frgnr_cont_amount,
                "total_net_volume": r.total_net_volume,
                "total_net_amount": r.total_net_amount,
                "total_cont_days": r.total_cont_days,
                "total_cont_volume": r.total_cont_volume,
                "total_cont_amount": r.total_cont_amount,
            }
            for r in rows
            if r.rank > 0
        ]
        if not values:
            return 0

        def _statement_factory(chunk: list[dict[str, Any]]) -> Any:
            insert_stmt = pg_insert(FrgnOrgnConsecutive).values(chunk)
            update_set: dict[str, Any] = {
                "stock_id": insert_stmt.excluded.stock_id,
                "stock_code_raw": insert_stmt.excluded.stock_code_raw,
                "stock_name": insert_stmt.excluded.stock_name,
                "period_stock_price_flu_rt": insert_stmt.excluded.period_stock_price_flu_rt,
                "orgn_net_amount": insert_stmt.excluded.orgn_net_amount,
                "orgn_net_volume": insert_stmt.excluded.orgn_net_volume,
                "orgn_cont_days": insert_stmt.excluded.orgn_cont_days,
                "orgn_cont_volume": insert_stmt.excluded.orgn_cont_volume,
                "orgn_cont_amount": insert_stmt.excluded.orgn_cont_amount,
                "frgnr_net_volume": insert_stmt.excluded.frgnr_net_volume,
                "frgnr_net_amount": insert_stmt.excluded.frgnr_net_amount,
                "frgnr_cont_days": insert_stmt.excluded.frgnr_cont_days,
                "frgnr_cont_volume": insert_stmt.excluded.frgnr_cont_volume,
                "frgnr_cont_amount": insert_stmt.excluded.frgnr_cont_amount,
                "total_net_volume": insert_stmt.excluded.total_net_volume,
                "total_net_amount": insert_stmt.excluded.total_net_amount,
                "total_cont_days": insert_stmt.excluded.total_cont_days,
                "total_cont_volume": insert_stmt.excluded.total_cont_volume,
                "total_cont_amount": insert_stmt.excluded.total_cont_amount,
                "fetched_at": func.now(),
            }
            return insert_stmt.on_conflict_do_update(
                index_elements=[
                    "as_of_date",
                    "period_type",
                    "market_type",
                    "amt_qty_tp",
                    "stk_inds_tp",
                    "exchange_type",
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

    async def get_top_by_total_days(
        self,
        *,
        as_of_date: date,
        period_type: ContinuousPeriodType = ContinuousPeriodType.LATEST,
        market_type: InvestorMarketType = InvestorMarketType.KOSPI,
        amt_qty_tp: ContinuousAmtQtyType | None = None,
        stk_inds_tp: StockIndsType = StockIndsType.STOCK,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
        limit: int = DEFAULT_GET_LIMIT,
    ) -> list[FrgnOrgnConsecutive]:
        """합계 연속순매수 일수 상위 종목 — total_cont_days DESC NULLS LAST.

        ``amt_qty_tp`` None 이면 두 값 (AMOUNT/QUANTITY) 모두 — caller 결정.
        """
        stmt = (
            select(FrgnOrgnConsecutive)
            .where(
                FrgnOrgnConsecutive.as_of_date == as_of_date,
                FrgnOrgnConsecutive.period_type == period_type.value,
                FrgnOrgnConsecutive.market_type == market_type.value,
                FrgnOrgnConsecutive.stk_inds_tp == stk_inds_tp.value,
                FrgnOrgnConsecutive.exchange_type == exchange_type.value,
            )
            .order_by(nulls_last(FrgnOrgnConsecutive.total_cont_days.desc()))
            .limit(limit)
        )
        if amt_qty_tp is not None:
            stmt = stmt.where(FrgnOrgnConsecutive.amt_qty_tp == amt_qty_tp.value)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


__all__ = ["FrgnOrgnConsecutiveRepository"]
