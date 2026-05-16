"""RankingSnapshotRepository — Phase F-4 (ka10027/30/31/32/23 통합 스냅샷).

설계: phase-f-4-rankings.md § 5.3 + endpoint-18-ka10027.md § 6.2.

책임:
- bulk upsert (`upsert_many`) — ON CONFLICT (snapshot_date+time+type+sort+market+exchange+rank)
  DO UPDATE. 멱등 키 7컬럼.
- `get_at_snapshot` — 6 조건 (date+time+ranking_type+sort+market+exchange) 필터 + rank ASC.
- 명시 update_set (B-γ-1 2R B-H3 패턴 일관) — schema-drift 차단.

D-1 short_selling / sector_price 패턴 1:1 응용.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._records import RankingType
from app.adapter.out.persistence.models.ranking_snapshot import RankingSnapshot
from app.adapter.out.persistence.repositories._helpers import _chunked_upsert
from app.application.dto.ranking import NormalizedRanking


class RankingSnapshotRepository:
    """Phase F-4 ranking_snapshot upsert + 조회 (5 ranking endpoint 통합)."""

    DEFAULT_GET_LIMIT: int = 50
    """get_at_snapshot 기본 limit — endpoint-18 § 6.2 (상위 50종)."""

    # F-4 Step 2 fix C-3 — PostgreSQL wire protocol int16 한도 (32767) 방어.
    # 13 col × 2000 = 26000 < 32767 안전 마진 (Phase D-1 follow-up 패턴 일관).
    _UPSERT_CHUNK_SIZE: int = 2000

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(
        self, rows: Sequence[NormalizedRanking] | Sequence[dict[str, Any]]
    ) -> int:
        """bulk upsert — ON CONFLICT (7컬럼 UNIQUE) DO UPDATE.

        반환: 영향받은 row 수 (insert + update 합계).

        - 빈 입력 → 0 반환 (early return).
        - 명시 update_set — 미래 컬럼 추가 시 silent contract change 방지.
        - ON CONFLICT key 7컬럼 (snapshot_date+time+ranking_type+sort+market+exchange+rank) 제외.
        - `created_at` 의도적 제외 — 최초 insert 시각 보존.
        - 입력은 `NormalizedRanking` dataclass 또는 dict 두 형태 모두 허용 (integration test 호환).

        F-4 Step 2 fix C-3 — ``_chunked_upsert`` helper 호출 (PostgreSQL wire protocol
        int16 한도 32767 / column 13 = 최대 2520 row/chunk). ``chunk_size=2000`` 적용.
        ``stock_daily_flow`` Repository (Phase D-1 follow-up) 와 동일 패턴.
        """
        if not rows:
            return 0

        def _to_values(r: Any) -> dict[str, Any]:
            if isinstance(r, dict):
                rt = r["ranking_type"]
                ranking_type_value = rt.value if hasattr(rt, "value") else rt
                return {
                    "snapshot_date": r["snapshot_date"],
                    "snapshot_time": r["snapshot_time"],
                    "ranking_type": ranking_type_value,
                    "sort_tp": r["sort_tp"],
                    "market_type": r["market_type"],
                    "exchange_type": r["exchange_type"],
                    "rank": r["rank"],
                    "stock_id": r.get("stock_id"),
                    "stock_code_raw": r["stock_code_raw"],
                    "primary_metric": r.get("primary_metric"),
                    "payload": r.get("payload", {}),
                    "request_filters": r.get("request_filters", {}),
                }
            return {
                "snapshot_date": r.snapshot_date,
                "snapshot_time": r.snapshot_time,
                "ranking_type": r.ranking_type.value,
                "sort_tp": r.sort_tp,
                "market_type": r.market_type,
                "exchange_type": r.exchange_type,
                "rank": r.rank,
                "stock_id": r.stock_id,
                "stock_code_raw": r.stock_code_raw,
                "primary_metric": r.primary_metric,
                "payload": r.payload,
                "request_filters": r.request_filters,
            }

        values: list[dict[str, Any]] = [_to_values(r) for r in rows]

        def _statement_factory(chunk: list[dict[str, Any]]) -> Any:
            """stateless statement factory — chunk 단위 ``excluded`` 재바인딩 (helper docstring § M-2)."""
            insert_stmt = pg_insert(RankingSnapshot).values(chunk)
            update_set: dict[str, Any] = {
                "stock_id": insert_stmt.excluded.stock_id,
                "stock_code_raw": insert_stmt.excluded.stock_code_raw,
                "primary_metric": insert_stmt.excluded.primary_metric,
                "payload": insert_stmt.excluded.payload,
                "request_filters": insert_stmt.excluded.request_filters,
                "fetched_at": func.now(),
            }
            return insert_stmt.on_conflict_do_update(
                index_elements=[
                    "snapshot_date",
                    "snapshot_time",
                    "ranking_type",
                    "sort_tp",
                    "market_type",
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

    async def get_at_snapshot(
        self,
        *,
        snapshot_date: date,
        snapshot_time: time,
        ranking_type: RankingType,
        sort_tp: str | None = None,
        market_type: str | None = None,
        exchange_type: str | None = None,
        limit: int = DEFAULT_GET_LIMIT,
    ) -> list[RankingSnapshot]:
        """특정 시점의 ranking row list — rank ASC 정렬 + limit.

        snapshot_date + snapshot_time + ranking_type 은 필수, 나머지 3 조건은 optional.
        Optional 조건 None 이면 WHERE 절에서 제외 (해당 조건 무관 조회).
        """
        stmt = (
            select(RankingSnapshot)
            .where(
                RankingSnapshot.snapshot_date == snapshot_date,
                RankingSnapshot.snapshot_time == snapshot_time,
                RankingSnapshot.ranking_type == ranking_type.value,
            )
        )
        if sort_tp is not None:
            stmt = stmt.where(RankingSnapshot.sort_tp == sort_tp)
        if market_type is not None:
            stmt = stmt.where(RankingSnapshot.market_type == market_type)
        if exchange_type is not None:
            stmt = stmt.where(RankingSnapshot.exchange_type == exchange_type)
        stmt = stmt.order_by(RankingSnapshot.rank.asc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


__all__ = ["RankingSnapshotRepository"]
