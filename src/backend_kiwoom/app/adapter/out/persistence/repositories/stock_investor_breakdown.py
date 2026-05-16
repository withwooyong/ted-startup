"""StockInvestorBreakdownRepository — Phase G ka10059 (종목별 wide breakdown, 12 net).

설계: phase-g-investor-flow.md § 5.3 + endpoint-24-ka10059.md § 6.2.

책임:
- bulk upsert (``upsert_many``) — ON CONFLICT (6 컬럼 UNIQUE) DO UPDATE.
- ``get_range`` — 단일 종목 기간 조회 (백테 진입점).
- D-12 inh-1 부분 mitigate — ``_UPSERT_CHUNK_SIZE=50`` (3000 종목 / 60분 sync 부담 줄임).

ka10059 응답 ``trading_date == date.min`` 은 빈 응답 표식 — Repository 가 영속화 직전 skip.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._records import (
    AmountQuantityType,
    NormalizedStockInvestorBreakdown,
    RankingExchangeType,
    StockInvestorTradeType,
)
from app.adapter.out.persistence.models.stock_investor_breakdown import (
    StockInvestorBreakdown,
)
from app.adapter.out.persistence.repositories._helpers import _chunked_upsert


class StockInvestorBreakdownRepository:
    """Phase G stock_investor_breakdown upsert + 조회 (ka10059, wide 12 net)."""

    # 27 컬럼 (id 제외) — 200 × 27 = 5400 < 32767 안전.
    # D-12 inh-1 부분 mitigate — 3000 종목 60분 sync 의 partial fail 격리는 service layer.
    _UPSERT_CHUNK_SIZE: int = 200

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(
        self,
        rows: Sequence[NormalizedStockInvestorBreakdown],
    ) -> int:
        """bulk upsert — ON CONFLICT (6 컬럼 UNIQUE) DO UPDATE.

        ``trading_date == date.min`` row 는 빈 응답 표식 — 영속화 직전 skip.
        ``stock_id is None`` row 는 lookup miss — 정책상 본 테이블은 stock_id NOT NULL
        지향이지만 운영 데이터 보존 위해 NULL 허용 (Migration 019 ON DELETE SET NULL).
        단, UNIQUE 키에 stock_id 포함이라 NULL row 도 적재 가능.
        """
        if not rows:
            return 0

        values: list[dict[str, Any]] = [
            {
                "stock_id": r.stock_id,
                "trading_date": r.trading_date,
                "amt_qty_tp": r.amt_qty_tp.value,
                "trade_type": r.trade_type.value,
                "unit_tp": r.unit_tp.value,
                "exchange_type": r.exchange_type.value,
                "current_price": r.current_price,
                "prev_compare_sign": r.prev_compare_sign,
                "prev_compare_amount": r.prev_compare_amount,
                "change_rate": r.change_rate,
                "acc_trade_volume": r.acc_trade_volume,
                "acc_trade_amount": r.acc_trade_amount,
                "net_individual": r.net_individual,
                "net_foreign": r.net_foreign,
                "net_institution_total": r.net_institution_total,
                "net_financial_inv": r.net_financial_inv,
                "net_insurance": r.net_insurance,
                "net_investment_trust": r.net_investment_trust,
                "net_other_financial": r.net_other_financial,
                "net_bank": r.net_bank,
                "net_pension_fund": r.net_pension_fund,
                "net_private_fund": r.net_private_fund,
                "net_nation": r.net_nation,
                "net_other_corp": r.net_other_corp,
                "net_dom_for": r.net_dom_for,
            }
            for r in rows
            if r.trading_date != date.min
        ]
        if not values:
            return 0

        def _statement_factory(chunk: list[dict[str, Any]]) -> Any:
            insert_stmt = pg_insert(StockInvestorBreakdown).values(chunk)
            update_set: dict[str, Any] = {
                "current_price": insert_stmt.excluded.current_price,
                "prev_compare_sign": insert_stmt.excluded.prev_compare_sign,
                "prev_compare_amount": insert_stmt.excluded.prev_compare_amount,
                "change_rate": insert_stmt.excluded.change_rate,
                "acc_trade_volume": insert_stmt.excluded.acc_trade_volume,
                "acc_trade_amount": insert_stmt.excluded.acc_trade_amount,
                "net_individual": insert_stmt.excluded.net_individual,
                "net_foreign": insert_stmt.excluded.net_foreign,
                "net_institution_total": insert_stmt.excluded.net_institution_total,
                "net_financial_inv": insert_stmt.excluded.net_financial_inv,
                "net_insurance": insert_stmt.excluded.net_insurance,
                "net_investment_trust": insert_stmt.excluded.net_investment_trust,
                "net_other_financial": insert_stmt.excluded.net_other_financial,
                "net_bank": insert_stmt.excluded.net_bank,
                "net_pension_fund": insert_stmt.excluded.net_pension_fund,
                "net_private_fund": insert_stmt.excluded.net_private_fund,
                "net_nation": insert_stmt.excluded.net_nation,
                "net_other_corp": insert_stmt.excluded.net_other_corp,
                "net_dom_for": insert_stmt.excluded.net_dom_for,
                "fetched_at": func.now(),
            }
            return insert_stmt.on_conflict_do_update(
                index_elements=[
                    "stock_id",
                    "trading_date",
                    "amt_qty_tp",
                    "trade_type",
                    "unit_tp",
                    "exchange_type",
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

    async def get_range(
        self,
        *,
        stock_id: int,
        start_date: date,
        end_date: date,
        amt_qty_tp: AmountQuantityType = AmountQuantityType.QUANTITY,
        trade_type: StockInvestorTradeType = StockInvestorTradeType.NET_BUY,
        unit_tp: str | None = None,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
    ) -> list[StockInvestorBreakdown]:
        """단일 종목 기간 조회 — trading_date ASC."""
        stmt = (
            select(StockInvestorBreakdown)
            .where(
                StockInvestorBreakdown.stock_id == stock_id,
                StockInvestorBreakdown.amt_qty_tp == amt_qty_tp.value,
                StockInvestorBreakdown.trade_type == trade_type.value,
                StockInvestorBreakdown.exchange_type == exchange_type.value,
                StockInvestorBreakdown.trading_date >= start_date,
                StockInvestorBreakdown.trading_date <= end_date,
            )
            .order_by(StockInvestorBreakdown.trading_date.asc())
        )
        if unit_tp is not None:
            stmt = stmt.where(StockInvestorBreakdown.unit_tp == unit_tp)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_range_optional_stock(
        self,
        *,
        stock_id: int | None,
        start_date: date,
        end_date: date,
        amt_qty_tp: AmountQuantityType = AmountQuantityType.QUANTITY,
        trade_type: StockInvestorTradeType = StockInvestorTradeType.NET_BUY,
        unit_tp: str | None = None,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
    ) -> list[StockInvestorBreakdown]:
        """기간 조회 — ``stock_id`` None 시 ``IS NULL`` row (lookup miss 보존) 조회.

        Step 2 R1 H-2: 라우터에서 ``stock_id`` Query 옵션화. None 일 때 본 메서드가
        ``StockInvestorBreakdown.stock_id IS NULL`` 필터 적용.
        """
        stmt = (
            select(StockInvestorBreakdown)
            .where(
                StockInvestorBreakdown.amt_qty_tp == amt_qty_tp.value,
                StockInvestorBreakdown.trade_type == trade_type.value,
                StockInvestorBreakdown.exchange_type == exchange_type.value,
                StockInvestorBreakdown.trading_date >= start_date,
                StockInvestorBreakdown.trading_date <= end_date,
            )
            .order_by(
                StockInvestorBreakdown.trading_date.asc(),
                StockInvestorBreakdown.stock_id.asc().nulls_last(),
            )
        )
        if stock_id is None:
            stmt = stmt.where(StockInvestorBreakdown.stock_id.is_(None))
        else:
            stmt = stmt.where(StockInvestorBreakdown.stock_id == stock_id)
        if unit_tp is not None:
            stmt = stmt.where(StockInvestorBreakdown.unit_tp == unit_tp)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


__all__ = ["StockInvestorBreakdownRepository"]
