"""StockDailyFlowRepository — ka10086 stock_daily_flow upsert + 조회 (C-2α).

설계: endpoint-10-ka10086.md § 6.2.

책임:
- bulk upsert (`upsert_many`) — ON CONFLICT (stock_id, trading_date, exchange) DO UPDATE
- `trading_date == date.min` 빈 응답 row 자동 skip (caller 안전망)
- 명시 update_set (B-γ-1 2R B-H3 패턴) — schema-drift 차단
- find_range — exchange 필터 + start <= trading_date <= end + asc 정렬
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._records import NormalizedDailyFlow
from app.adapter.out.persistence.models import StockDailyFlow
from app.adapter.out.persistence.repositories._helpers import rowcount_of
from app.application.constants import ExchangeType


class StockDailyFlowRepository:
    """ka10086 stock_daily_flow upsert + 조회."""

    # 2b-M1 — SOR 영속화 차단. ka10081 stock_price 와 일관 (KRX/NXT 만).
    # Phase D 에서 SOR 영속화 정책 확정 시 추가 마이그레이션 + 본 set 확장.
    _SUPPORTED_EXCHANGES: frozenset[ExchangeType] = frozenset(
        {ExchangeType.KRX, ExchangeType.NXT}
    )

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, rows: Sequence[NormalizedDailyFlow]) -> int:
        """bulk upsert — ON CONFLICT (stock_id, trading_date, exchange) DO UPDATE.

        반환: 영향받은 row 수 (insert + update 합계).

        - `trading_date == date.min` 빈 응답 row 자동 skip (caller 안전망)
        - 명시 update_set (B-γ-1 2R B-H3) — 미래 컬럼 추가 시 silent contract change 방지
        - SOR 거래소 차단 (2b-M1) — Phase D 까지 KRX/NXT 만 영속화
        """
        valid_rows = [r for r in rows if r.trading_date != date.min]
        if not valid_rows:
            return 0

        # 2b-M1 — SOR / 미래 거래소 silent 영속화 차단
        unsupported = {r.exchange for r in valid_rows if r.exchange not in self._SUPPORTED_EXCHANGES}
        if unsupported:
            raise ValueError(
                f"unsupported exchange for stock_daily_flow: {sorted(e.value for e in unsupported)} "
                "(KRX/NXT only — SOR 은 Phase D)"
            )

        values: list[dict[str, Any]] = [
            {
                "stock_id": r.stock_id,
                "trading_date": r.trading_date,
                "exchange": r.exchange.value,
                "indc_mode": r.indc_mode.value,
                "credit_rate": r.credit_rate,
                "credit_balance_rate": r.credit_balance_rate,
                "individual_net": r.individual_net,
                "institutional_net": r.institutional_net,
                "foreign_brokerage_net": r.foreign_brokerage_net,
                "program_net": r.program_net,
                "foreign_volume": r.foreign_volume,
                "foreign_rate": r.foreign_rate,
                "foreign_holdings": r.foreign_holdings,
                "foreign_weight": r.foreign_weight,
            }
            for r in valid_rows
        ]

        insert_stmt = pg_insert(StockDailyFlow).values(values)

        # B-γ-1 2R B-H3 — 명시 update_set. ON CONFLICT 키 (stock_id, trading_date, exchange) 제외.
        # 미래 NormalizedDailyFlow 필드 추가 시 본 list 도 수동 갱신 강제 (schema-drift 차단).
        # `created_at` 의도적 제외 — 최초 insert 시각 보존 (UPSERT 시에도 갱신하지 않음).
        update_set: dict[str, Any] = {
            "indc_mode": insert_stmt.excluded.indc_mode,
            "credit_rate": insert_stmt.excluded.credit_rate,
            "credit_balance_rate": insert_stmt.excluded.credit_balance_rate,
            "individual_net": insert_stmt.excluded.individual_net,
            "institutional_net": insert_stmt.excluded.institutional_net,
            "foreign_brokerage_net": insert_stmt.excluded.foreign_brokerage_net,
            "program_net": insert_stmt.excluded.program_net,
            "foreign_volume": insert_stmt.excluded.foreign_volume,
            "foreign_rate": insert_stmt.excluded.foreign_rate,
            "foreign_holdings": insert_stmt.excluded.foreign_holdings,
            "foreign_weight": insert_stmt.excluded.foreign_weight,
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

    async def find_range(
        self,
        stock_id: int,
        *,
        exchange: ExchangeType,
        start: date,
        end: date,
    ) -> Sequence[StockDailyFlow]:
        """[start, end] 시계열 조회 — exchange 필터 + trading_date asc.

        Raises:
            ValueError: start > end 또는 unsupported exchange (SOR).
        """
        if start > end:
            raise ValueError(f"start ({start}) must be <= end ({end})")
        if exchange not in self._SUPPORTED_EXCHANGES:
            raise ValueError(
                f"unsupported exchange for stock_daily_flow: {exchange.value!r} "
                "(KRX/NXT only — SOR 은 Phase D)"
            )
        stmt = (
            select(StockDailyFlow)
            .where(
                StockDailyFlow.stock_id == stock_id,
                StockDailyFlow.exchange == exchange.value,
                StockDailyFlow.trading_date >= start,
                StockDailyFlow.trading_date <= end,
            )
            .order_by(StockDailyFlow.trading_date.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


__all__ = ["StockDailyFlowRepository"]
