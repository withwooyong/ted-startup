"""SectorPriceDailyRepository — kiwoom.sector_price_daily upsert + 조회 (D-1).

설계: endpoint-13-ka20006.md § 6.2 + § 12.

ka10094 stock_price_periodic 의 upsert_many 패턴 1:1 응용 — 단, period dispatch 없음
(단일 ORM 테이블). 본 chunk 는 KRX only — NXT 미지원 (plan § 12.2 #4).

책임:
- bulk upsert (`upsert_many`) — ON CONFLICT (sector_id, trading_date) DO UPDATE
- `trading_date == date.min` 빈 응답 row 자동 skip (caller 안전망)
- 명시 update_set (B-γ-1 2R B-H3 패턴 일관) — schema-drift 차단
- FK 위반 시 IntegrityError 그대로 전파 (caller 가 sector_id 사전 검증 권고)
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom.chart import NormalizedSectorDailyOhlcv
from app.adapter.out.persistence.models.sector_price_daily import SectorPriceDaily
from app.adapter.out.persistence.repositories._helpers import rowcount_of


class SectorPriceDailyRepository:
    """업종 일봉 영속 계층 (D-1)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(
        self,
        rows: Sequence[NormalizedSectorDailyOhlcv | dict[str, Any]],
    ) -> int:
        """bulk upsert — ON CONFLICT (sector_id, trading_date) DO UPDATE.

        반환: 영향받은 row 수 (insert + update 합계).

        Parameters:
            rows: `NormalizedSectorDailyOhlcv` 또는 dict (테스트용). dict 의 경우 모든
                NormalizedSectorDailyOhlcv 필드 8개 (`sector_id`, `trading_date`,
                `open_index_centi`, `high_index_centi`, `low_index_centi`,
                `close_index_centi`, `trade_volume`, `trade_amount`) 가 필요.

        특징 (plan § 12):
        - `trading_date == date.min` 자동 skip — chart.py to_normalized 표식
        - 명시 update_set — 미래 컬럼 추가 시 silent contract change 방지 (B-γ-1 2R B-H3)
        - ON CONFLICT key (sector_id, trading_date) 는 index_elements 로 식별되는 키 컬럼이라
          update_set 에서 제외 (변경 불가)
        """
        if not rows:
            return 0

        # NormalizedSectorDailyOhlcv 또는 dict 양쪽 수용 — caller 편의
        normalized: list[dict[str, Any]] = []
        for r in rows:
            if isinstance(r, dict):
                if r.get("trading_date") == date.min:
                    continue
                normalized.append(
                    {
                        "sector_id": r["sector_id"],
                        "trading_date": r["trading_date"],
                        "open_index_centi": r.get("open_index_centi"),
                        "high_index_centi": r.get("high_index_centi"),
                        "low_index_centi": r.get("low_index_centi"),
                        "close_index_centi": r.get("close_index_centi"),
                        "trade_volume": r.get("trade_volume"),
                        "trade_amount": r.get("trade_amount"),
                    }
                )
            else:
                if r.trading_date == date.min:
                    continue
                normalized.append(
                    {
                        "sector_id": r.sector_id,
                        "trading_date": r.trading_date,
                        "open_index_centi": r.open_index_centi,
                        "high_index_centi": r.high_index_centi,
                        "low_index_centi": r.low_index_centi,
                        "close_index_centi": r.close_index_centi,
                        "trade_volume": r.trade_volume,
                        "trade_amount": r.trade_amount,
                    }
                )

        if not normalized:
            return 0

        insert_stmt = pg_insert(SectorPriceDaily).values(normalized)

        # 명시 update_set — schema-drift 차단 (B-γ-1 2R B-H3 일관).
        # ON CONFLICT key (sector_id, trading_date) 는 의도적 제외.
        update_set: dict[str, Any] = {
            "open_index_centi": insert_stmt.excluded.open_index_centi,
            "high_index_centi": insert_stmt.excluded.high_index_centi,
            "low_index_centi": insert_stmt.excluded.low_index_centi,
            "close_index_centi": insert_stmt.excluded.close_index_centi,
            "trade_volume": insert_stmt.excluded.trade_volume,
            "trade_amount": insert_stmt.excluded.trade_amount,
            "fetched_at": func.now(),
            "updated_at": func.now(),
        }

        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=["sector_id", "trading_date"],
            set_=update_set,
        )

        result = await self._session.execute(upsert_stmt)
        await self._session.flush()
        return rowcount_of(result)


__all__ = ["SectorPriceDailyRepository"]
