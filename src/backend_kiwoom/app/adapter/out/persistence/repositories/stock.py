"""StockRepository — kiwoom.stock CRUD + 디액티베이션 + nxt-eligible 조회.

설계: endpoint-03-ka10099.md § 6.2.

책임:
- list_by_filters(market_code, nxt_enable, only_active) — 라우터 GET /stocks 의 query
- list_nxt_enabled(only_active) — Phase C 가 사용할 NXT 호출 큐
- find_by_code(stock_code) — 단건 조회
- upsert_many(rows) — PG ON CONFLICT (stock_code) upsert. 응답에 등장하면 is_active=TRUE 강제
- deactivate_missing(market_code, present_codes) — 같은 market_code 범위 내에서만 비활성화
  (다른 시장 row 영향 없음 — KOSPI sync 가 KOSDAQ 종목 비활성화 사고 방지)

빈 응답 보호 (§5.3 디액티베이션 정책 d):
- present_codes 가 빈 set 이면 그 시장 비활성화 SKIP — UseCase 가 호출 자체를 skip 함.
  본 메서드는 호출되면 정직하게 비활성화 (sector 패턴 일관 — 안전장치 동작 확인 테스트 필요).
"""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.models import Stock
from app.adapter.out.persistence.repositories._helpers import rowcount_of

if TYPE_CHECKING:
    from app.adapter.out.kiwoom.stkinfo import NormalizedStock


class StockRepository:
    """종목 마스터 영속 계층."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_filters(
        self,
        *,
        market_code: str | None = None,
        nxt_enable: bool | None = None,
        only_active: bool = True,
    ) -> list[Stock]:
        """다중 필터 조회.

        모든 필터가 None/False 면 전체 active 종목. 정렬: market_code → stock_code.
        sector pattern 일관 — populate_existing 으로 identity map stale 방지.
        """
        stmt = select(Stock)
        if market_code is not None:
            stmt = stmt.where(Stock.market_code == market_code)
        if nxt_enable is not None:
            stmt = stmt.where(Stock.nxt_enable.is_(nxt_enable))
        if only_active:
            stmt = stmt.where(Stock.is_active.is_(True))
        stmt = stmt.order_by(Stock.market_code, Stock.stock_code).execution_options(populate_existing=True)
        return list((await self._session.execute(stmt)).scalars())

    async def list_nxt_enabled(self, *, only_active: bool = True) -> list[Stock]:
        """Phase C 가 사용할 NXT 호출 큐."""
        return await self.list_by_filters(nxt_enable=True, only_active=only_active)

    async def find_by_code(self, stock_code: str) -> Stock | None:
        stmt = select(Stock).where(Stock.stock_code == stock_code).execution_options(populate_existing=True)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    # asyncpg bind parameter 16-bit 한도 (32767) 회피 — 14 컬럼 기준 2340 row 가 이론 한도.
    # 안전 마진 + 향후 컬럼 추가 대비 1000 per batch (실측 KOSPI 2440 / KOSDAQ ~1500 종목).
    _UPSERT_BATCH = 1000

    async def upsert_many(self, rows: list[dict[str, Any]]) -> int:
        """PG ON CONFLICT (stock_code) upsert. 큰 배치는 자동 chunk 분할.

        rows 각 dict 는 NormalizedStock 의 14개 도메인 필드 + market_code (필수).
        응답에 등장한 stock_code 는 is_active=TRUE 강제 — 재등장 복원 (sector 일관).

        반환: 영향받은 row 수 (insert + update 합계).
        """
        if not rows:
            return 0
        total = 0
        for start in range(0, len(rows), self._UPSERT_BATCH):
            batch = rows[start : start + self._UPSERT_BATCH]
            stmt = pg_insert(Stock).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=["stock_code"],
                set_={
                    "stock_name": stmt.excluded.stock_name,
                    "list_count": stmt.excluded.list_count,
                    "audit_info": stmt.excluded.audit_info,
                    "listed_date": stmt.excluded.listed_date,
                    "last_price": stmt.excluded.last_price,
                    "state": stmt.excluded.state,
                    "market_code": stmt.excluded.market_code,
                    "market_name": stmt.excluded.market_name,
                    "up_name": stmt.excluded.up_name,
                    "up_size_name": stmt.excluded.up_size_name,
                    "company_class_name": stmt.excluded.company_class_name,
                    "order_warning": stmt.excluded.order_warning,
                    "nxt_enable": stmt.excluded.nxt_enable,
                    "is_active": True,
                    "fetched_at": func.now(),
                    "updated_at": func.now(),
                },
            )
            result = await self._session.execute(stmt)
            total += rowcount_of(result)
        await self._session.flush()
        return total

    async def upsert_one(self, row: NormalizedStock) -> Stock:
        """단건 upsert (B-β) — RETURNING 으로 갱신된 row 반환.

        ka10100 lazy fetch / refresh 흐름이 caller 에 즉시 Stock(.id, .fetched_at,
        .updated_at) 을 돌려주기 위함. upsert_many 와 같은 ON CONFLICT (stock_code)
        DO UPDATE 정책을 단건에 그대로 적용.

        디액티베이션 없음 — 단건은 활성화만 한다 (응답에 등장 = 살아있음).
        디액티베이션은 ka10099 의 시장 단위 sync 책임.
        """
        values = asdict(row)
        # `requested_market_type` 은 영속화 안 함 (응답 검증/디버깅용 메타).
        values.pop("requested_market_type", None)

        insert_stmt = pg_insert(Stock).values(**values)
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=["stock_code"],
            set_={
                "stock_name": insert_stmt.excluded.stock_name,
                "list_count": insert_stmt.excluded.list_count,
                "audit_info": insert_stmt.excluded.audit_info,
                "listed_date": insert_stmt.excluded.listed_date,
                "last_price": insert_stmt.excluded.last_price,
                "state": insert_stmt.excluded.state,
                "market_code": insert_stmt.excluded.market_code,
                "market_name": insert_stmt.excluded.market_name,
                "up_name": insert_stmt.excluded.up_name,
                "up_size_name": insert_stmt.excluded.up_size_name,
                "company_class_name": insert_stmt.excluded.company_class_name,
                "order_warning": insert_stmt.excluded.order_warning,
                "nxt_enable": insert_stmt.excluded.nxt_enable,
                "is_active": True,
                "fetched_at": func.now(),
                "updated_at": func.now(),
            },
        ).returning(Stock)
        # populate_existing — UPDATE 시 session identity map 의 stale row 를 RETURNING
        # 값으로 덮어씀. 미설정 시 같은 PK 의 캐시된 ORM row 가 갱신 전 값 그대로 반환됨
        # (sector list_by_filters 패턴 일관).
        result = await self._session.execute(upsert_stmt, execution_options={"populate_existing": True})
        await self._session.flush()
        stock: Stock = result.scalar_one()
        return stock

    async def deactivate_missing(self, market_code: str, present_codes: set[str]) -> int:
        """`market_code` 시장에서 응답에 없는 stock_code 들을 is_active=FALSE.

        주의: 다른 시장의 row 는 절대 건드리지 않음 — `Stock.market_code == market_code`
        WHERE 절 강제. KOSPI sync 가 KOSDAQ 종목을 비활성화하면 사고.

        present_codes 가 빈 set 이면 그 시장 전체 활성 row 비활성화.
        UseCase 는 빈 응답 시 호출 자체를 skip — 본 메서드는 호출되면 정직하게 실행.
        """
        stmt = update(Stock).where(Stock.market_code == market_code).where(Stock.is_active.is_(True))
        if present_codes:
            stmt = stmt.where(Stock.stock_code.notin_(present_codes))
        stmt = stmt.values(is_active=False, updated_at=func.now())
        result = await self._session.execute(stmt)
        await self._session.flush()
        return rowcount_of(result)
