"""SectorRepository — kiwoom.sector CRUD + 디액티베이션.

설계: endpoint-14-ka10101.md § 6.2.

책임:
- list_by_market(market_code, *, only_active) — 시장별 조회 + 활성 필터
- list_all(only_active) — 전체 조회 (라우터의 market 미지정 케이스)
- upsert_many(rows) — PG ON CONFLICT (market_code, sector_code) 복합키 upsert
  - 응답에 등장하면 is_active=TRUE 강제 (재등장 복원)
  - sector_name / group_no / fetched_at / updated_at 갱신
- deactivate_missing(market_code, present_codes) — 응답에서 빠진 sector 들을 is_active=FALSE
  - 시장 단위 — 다른 시장 row 영향 없음
  - 빈 set 이면 그 시장 전체 비활성화 (sync 응답이 빈 list 인 비정상 케이스 — UseCase 가
    호출 자체를 건너뛰므로 실제로 도달 안 하지만 안전장치)

트랜잭션 경계: caller (UseCase) 가 세션 commit 책임. Repository 는 flush 만.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.models import Sector
from app.adapter.out.persistence.repositories._helpers import rowcount_of


class SectorRepository:
    """업종 마스터 영속 계층."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_market(self, market_code: str, *, only_active: bool = True) -> list[Sector]:
        """단일 시장의 업종 조회.

        `populate_existing=True` — `upsert_many` / `deactivate_missing` 이 bulk SQL 로
        DB 를 갱신한 직후 같은 세션에서 SELECT 하면 identity map 의 stale 객체가
        반환되는 문제 회피. 항상 최신 DB 상태 반환 보장.
        """
        stmt = select(Sector).where(Sector.market_code == market_code)
        if only_active:
            stmt = stmt.where(Sector.is_active.is_(True))
        stmt = stmt.order_by(Sector.sector_code).execution_options(populate_existing=True)
        return list((await self._session.execute(stmt)).scalars())

    async def list_all(self, *, only_active: bool = True) -> list[Sector]:
        """전체 시장 통합 조회 — 라우터의 market 필터 미지정 응답."""
        stmt = select(Sector)
        if only_active:
            stmt = stmt.where(Sector.is_active.is_(True))
        stmt = stmt.order_by(Sector.market_code, Sector.sector_code).execution_options(populate_existing=True)
        return list((await self._session.execute(stmt)).scalars())

    async def upsert_many(self, rows: list[dict[str, Any]]) -> int:
        """PG ON CONFLICT (market_code, sector_code) upsert.

        rows 각 dict 는 keys: market_code / sector_code / sector_name / group_no.
        충돌 시 sector_name / group_no / fetched_at / updated_at / is_active=TRUE 갱신
        — 응답에 등장한 sector 는 무조건 활성화 (재등장 복원).

        반환: 영향받은 row 수 (insert + update 합계).
        """
        if not rows:
            return 0
        stmt = pg_insert(Sector).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["market_code", "sector_code"],
            set_={
                "sector_name": stmt.excluded.sector_name,
                "group_no": stmt.excluded.group_no,
                "is_active": True,
                "fetched_at": func.now(),
                "updated_at": func.now(),
            },
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return rowcount_of(result)

    async def deactivate_missing(self, market_code: str, present_codes: set[str]) -> int:
        """`market_code` 시장에서 응답에 없는 sector_code 들을 is_active=FALSE.

        주의: `present_codes` 가 빈 set 이면 그 시장 전체 활성 row 가 비활성화됨.
        UseCase 는 이 호출 자체를 건너뛰는 게 안전 — 본 메서드는 호출되면 정직하게 실행.
        """
        stmt = update(Sector).where(Sector.market_code == market_code).where(Sector.is_active.is_(True))
        if present_codes:
            stmt = stmt.where(Sector.sector_code.notin_(present_codes))
        stmt = stmt.values(is_active=False, updated_at=func.now())
        result = await self._session.execute(stmt)
        await self._session.flush()
        return rowcount_of(result)
