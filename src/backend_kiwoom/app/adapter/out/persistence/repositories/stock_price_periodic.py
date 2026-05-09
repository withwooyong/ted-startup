"""StockPricePeriodicRepository — 주봉/월봉 KRX/NXT upsert + 조회 (C-3α).

설계: phase-c-3-weekly-monthly-ohlcv.md § 3.1 + endpoint-07-ka10082.md § 6.2.

ka10081 의 StockPriceRepository 와 분리된 이유:
- 일봉은 호출 빈도 + row 수가 압도적 → 별도 hot path
- 주/월봉은 통합 인터페이스 (period dispatch) — ka10082/83/94 가 같은 계열

책임:
- (period, exchange) 별로 다른 ORM 모델 분기 — caller 는 어느 테이블인지 신경 안 씀
- bulk upsert (`upsert_many`) — ON CONFLICT (stock_id, trading_date, adjusted) DO UPDATE
- `trading_date == date.min` 빈 응답 row 자동 skip (caller 안전망)
- 명시 update_set (B-γ-1 2R B-H3 패턴 일관) — schema-drift 차단

YEARLY 미지원 (Migration 미작성, P2 chunk):
- ka10094 진입 시 `_MODEL_BY_PERIOD_AND_EXCHANGE` 에 2 매핑 추가
- 본 chunk 는 호출 시 ValueError

SOR 미지원: 일봉 Repository 와 동일 정책 (Phase D 결정).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom.chart import NormalizedDailyOhlcv
from app.adapter.out.persistence.models.stock_price_periodic import (
    StockPriceMonthlyKrx,
    StockPriceMonthlyNxt,
    StockPriceWeeklyKrx,
    StockPriceWeeklyNxt,
)
from app.adapter.out.persistence.repositories._helpers import rowcount_of
from app.application.constants import ExchangeType, Period

PeriodicModel = (
    type[StockPriceWeeklyKrx] | type[StockPriceWeeklyNxt] | type[StockPriceMonthlyKrx] | type[StockPriceMonthlyNxt]
)


class StockPricePeriodicRepository:
    """주봉/월봉 4 테이블의 인터페이스 통일 — period+exchange dispatch."""

    _MODEL_BY_PERIOD_AND_EXCHANGE: dict[tuple[Period, ExchangeType], PeriodicModel] = {
        (Period.WEEKLY, ExchangeType.KRX): StockPriceWeeklyKrx,
        (Period.WEEKLY, ExchangeType.NXT): StockPriceWeeklyNxt,
        (Period.MONTHLY, ExchangeType.KRX): StockPriceMonthlyKrx,
        (Period.MONTHLY, ExchangeType.NXT): StockPriceMonthlyNxt,
    }

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _model(self, period: Period, exchange: ExchangeType) -> PeriodicModel:
        key = (period, exchange)
        if key not in self._MODEL_BY_PERIOD_AND_EXCHANGE:
            raise ValueError(
                f"unsupported (period, exchange) for stock_price_periodic: "
                f"{period.value}/{exchange.value} "
                "(WEEKLY/MONTHLY × KRX/NXT only — YEARLY 는 P2, SOR 은 Phase D)"
            )
        return self._MODEL_BY_PERIOD_AND_EXCHANGE[key]

    async def upsert_many(
        self,
        rows: Sequence[NormalizedDailyOhlcv],
        *,
        period: Period,
        exchange: ExchangeType,
    ) -> int:
        """bulk upsert — ON CONFLICT (stock_id, trading_date, adjusted) DO UPDATE.

        반환: 영향받은 row 수 (insert + update 합계).

        - `NormalizedDailyOhlcv` 는 일봉 도메인에서 정의된 dataclass 지만 컬럼 구조가
          period 무관 — 주/월봉도 같은 필드 사용 (Daily 접두는 도메인 출처 표시).
        - `trading_date == date.min` 빈 응답 row 자동 skip (chart.py to_normalized 표식)
        - 명시 update_set (B-γ-1 2R B-H3) — 미래 컬럼 추가 시 silent contract change 방지
        - YEARLY / SOR 호출 시 ValueError (지원 매핑 외)
        """
        model = self._model(period, exchange)

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

        # ON CONFLICT key (stock_id, trading_date, adjusted) 는 update_set 에서 의도적
        # 제외 — index_elements 로 식별되는 키 컬럼이라 변경 불가. 미래 컬럼 추가 시 본
        # update_set 에 명시 추가 필요 (silent contract change 차단 — B-γ-1 2R B-H3).
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
        period: Period,
        exchange: ExchangeType,
        start: date,
        end: date,
    ) -> Sequence[StockPriceWeeklyKrx | StockPriceWeeklyNxt | StockPriceMonthlyKrx | StockPriceMonthlyNxt]:
        """[start, end] 시계열 조회 — period+exchange 분기 + trading_date asc.

        Raises:
            ValueError: start > end 또는 unsupported (period, exchange).
        """
        if start > end:
            raise ValueError(f"start ({start}) must be <= end ({end})")
        model = self._model(period, exchange)
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
        return list(result.scalars().all())  # type: ignore[arg-type]
