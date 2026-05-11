"""StockPriceRepository — KRX/NXT 일봉 OHLCV upsert + 조회 (C-1α).

설계: endpoint-06-ka10081.md § 6.2.

책임:
- exchange (KRX/NXT) 별로 다른 ORM 모델 분기 — caller 는 어느 테이블인지 신경 안 씀
- bulk upsert (`upsert_many`) — ON CONFLICT (stock_id, trading_date, adjusted) DO UPDATE
- `trading_date == date.min` 빈 응답 row 자동 skip (caller 안전망)
- 명시 update_set (B-γ-1 2R B-H3 패턴 일관) — schema-drift 차단

SOR 미지원: ka10081 응답이 SOR 도 가능하지만 본 chunk 는 KRX/NXT 만 영속화.
SOR 영속화는 Phase D 에서 결정.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom.chart import NormalizedDailyOhlcv
from app.adapter.out.persistence.models import StockPriceKrx, StockPriceNxt
from app.adapter.out.persistence.repositories._helpers import rowcount_of
from app.application.constants import ExchangeType


class StockPriceRepository:
    """KRX/NXT 두 테이블의 인터페이스 통일."""

    _MODEL_BY_EXCHANGE: dict[ExchangeType, type[StockPriceKrx] | type[StockPriceNxt]] = {
        ExchangeType.KRX: StockPriceKrx,
        ExchangeType.NXT: StockPriceNxt,
    }

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _model(self, exchange: ExchangeType) -> type[StockPriceKrx] | type[StockPriceNxt]:
        if exchange not in self._MODEL_BY_EXCHANGE:
            raise ValueError(
                f"unsupported exchange for stock_price: {exchange!r} (KRX/NXT only — SOR 은 Phase D)"
            )
        return self._MODEL_BY_EXCHANGE[exchange]

    async def upsert_many(
        self,
        rows: Sequence[NormalizedDailyOhlcv],
        *,
        exchange: ExchangeType,
    ) -> int:
        """bulk upsert — ON CONFLICT (stock_id, trading_date, adjusted) DO UPDATE.

        반환: 영향받은 row 수 (insert + update 합계).

        - `trading_date == date.min` 빈 응답 row 자동 skip (caller 안전망 — chart.py 의
          `to_normalized` 가 빈 dt 응답에 date.min 박는 정책 일관)
        - 명시 update_set (B-γ-1 2R B-H3) — 미래 컬럼 추가 시 silent contract change 방지
        """
        model = self._model(exchange)

        # 빈 dt 표식 (date.min) 자동 skip — chart.py to_normalized 가 빈 dt 응답에 박는 표식
        valid_rows = [r for r in rows if r.trading_date != date.min]
        if not valid_rows:
            return 0

        values: list[dict[str, Any]] = [
            {
                "stock_id": r.stock_id,
                "trading_date": r.trading_date,
                "adjusted": r.adjusted,
                "open_price": r.open_price,
                "high_price": r.high_price,
                "low_price": r.low_price,
                "close_price": r.close_price,
                "trade_volume": r.trade_volume,
                "trade_amount": r.trade_amount,
                "prev_compare_amount": r.prev_compare_amount,
                "prev_compare_sign": r.prev_compare_sign,
                "turnover_rate": r.turnover_rate,
            }
            for r in valid_rows
        ]

        insert_stmt = pg_insert(model).values(values)

        # B-γ-1 2R B-H3 — 명시 update_set. ON CONFLICT 키 (stock_id, trading_date, adjusted) 제외.
        # 미래 NormalizedDailyOhlcv 필드 추가 시 본 list 도 수동 갱신 강제 (schema-drift 차단).
        update_set: dict[str, Any] = {
            "open_price": insert_stmt.excluded.open_price,
            "high_price": insert_stmt.excluded.high_price,
            "low_price": insert_stmt.excluded.low_price,
            "close_price": insert_stmt.excluded.close_price,
            "trade_volume": insert_stmt.excluded.trade_volume,
            "trade_amount": insert_stmt.excluded.trade_amount,
            "prev_compare_amount": insert_stmt.excluded.prev_compare_amount,
            "prev_compare_sign": insert_stmt.excluded.prev_compare_sign,
            "turnover_rate": insert_stmt.excluded.turnover_rate,
            "fetched_at": func.now(),
            "updated_at": func.now(),
        }

        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=["stock_id", "trading_date", "adjusted"],
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
    ) -> Sequence[StockPriceKrx | StockPriceNxt]:
        """[start, end] 시계열 조회 — KRX/NXT 분기 + trading_date asc.

        Raises:
            ValueError: start > end 또는 unsupported exchange (SOR).
        """
        if start > end:
            raise ValueError(f"start ({start}) must be <= end ({end})")
        model = self._model(exchange)
        stmt = (
            select(model)
            .where(
                model.stock_id == stock_id,
                model.trading_date >= start,
                model.trading_date <= end,
            )
            .order_by(model.trading_date.asc())
        )
        result = await self._session.execute(stmt)
        # R2 M-3 — runtime 무영향 cast (model 은 KRX/NXT 한 가지로 분기됨)
        return cast(list[StockPriceKrx | StockPriceNxt], list(result.scalars().all()))
