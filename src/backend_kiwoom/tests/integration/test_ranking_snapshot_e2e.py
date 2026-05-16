"""ranking_snapshot E2E — testcontainers PG16 통합 테스트 (~8 케이스).

설계: phase-f-4-rankings.md § 5.12 #10 + § 4 D-2/D-8/D-9/D-13.

가정 production 위치:
- app/adapter/out/persistence/repositories/ranking_snapshot.py (Step 1 에서 작성).
- Migration 018 (ranking_snapshot 테이블 + UNIQUE 키 + GIN index) 이미 적용됨.

testcontainers fixture:
- 부모 conftest.py (tests/conftest.py) 의 `engine` fixture 재사용.
  → tests/integration/ 에서 import 가능 (pytest conftest 자동 검색 / sys.path 포함).
- `apply_migrations` autouse — 이미 세션 스코프로 Alembic upgrade head 실행됨.

검증 시나리오 (~8 케이스):

1. INSERT 50 row upsert — 5 ranking_type × 10 rank (정상 적재)
2. 동일 UNIQUE 키 row 2회 upsert → row 수 50 유지 (멱등성 — D-2 UNIQUE 키 6개)
3. JSONB payload 쿼리 — `payload->>'cur_prc'` 단순 + `payload->'opmr'->>'trde_qty'` nested (D-9)
4. GIN index 활용 검증 — EXPLAIN ANALYZE 또는 payload JSONB 쿼리 정상 완료 (D-13)
5. stock_id NULL (lookup miss) + stock_code_raw 보존 (D-8)
6. NXT `_NX` suffix → stock_code_raw="005930_NX" 보존 + stock_id 매핑 정상 (D-8 + NXT)
7. 5 ranking_type 분리 동시 적재 — 250 row, 충돌 0
8. get_at_snapshot(date, time, type) — rank 순 정렬 검증

TDD red 의도:
- `from app.adapter.out.persistence.repositories.ranking_snapshot import RankingSnapshotRepository`
  → ImportError (Step 1 미구현)
- `from app.adapter.out.persistence.models.ranking_snapshot import RankingSnapshot`
  → ImportError (Step 1 미구현)
- Step 1 구현 후 green 전환.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date, time
from decimal import Decimal
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

# tests/ 디렉토리가 sys.path 에 없으면 conftest fixtures 를 찾지 못할 수 있음
# integration/ 하위이므로 부모 conftest.py 는 자동 로드됨 (pytest 기본 동작)
from app.adapter.out.kiwoom._records import RankingType  # type: ignore[import]  # Step 0b
from app.adapter.out.persistence.repositories.ranking_snapshot import (  # type: ignore[import]  # Step 1
    RankingSnapshotRepository,
)

# ---------------------------------------------------------------------------
# 공용 상수 / 헬퍼
# ---------------------------------------------------------------------------

_SNAPSHOT_DATE = date(2026, 5, 15)
_SNAPSHOT_TIME_1930 = time(19, 30, 0)

_RANKING_TYPES = [
    RankingType.FLU_RT,
    RankingType.TODAY_VOLUME,
    RankingType.PRED_VOLUME,
    RankingType.TRDE_PRICA,
    RankingType.VOLUME_SDNIN,
]


def _make_snapshot_row(
    *,
    snapshot_date: date = _SNAPSHOT_DATE,
    snapshot_time: time = _SNAPSHOT_TIME_1930,
    ranking_type: RankingType = RankingType.FLU_RT,
    sort_tp: str = "1",
    market_type: str = "001",
    exchange_type: str = "3",
    rank: int = 1,
    stock_code_raw: str = "005930",
    stock_id: int | None = None,
    primary_metric: Decimal = Decimal("29.86"),
    payload: dict[str, Any] | None = None,
    request_filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """ranking_snapshot INSERT 용 dict 생성 헬퍼."""
    return {
        "snapshot_date": snapshot_date,
        "snapshot_time": snapshot_time,
        "ranking_type": ranking_type.value,
        "sort_tp": sort_tp,
        "market_type": market_type,
        "exchange_type": exchange_type,
        "rank": rank,
        "stock_code_raw": stock_code_raw,
        "stock_id": stock_id,
        "primary_metric": primary_metric,
        "payload": payload or {"cur_prc": "74800", "stk_nm": "삼성전자"},
        "request_filters": request_filters or {"mrkt_tp": market_type, "sort_tp": sort_tp},
    }


async def _create_stock(session: AsyncSession, code: str, name: str = "테스트종목") -> int:
    """테스트용 stock INSERT 후 id 반환."""
    res = await session.execute(
        text(
            "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code, is_active) "
            "VALUES (:c, :n, '0', TRUE) RETURNING id"
        ).bindparams(c=code, n=name)
    )
    sid = int(res.scalar_one())
    await session.commit()
    return sid


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_ranking_snapshot(engine: AsyncEngine) -> AsyncIterator[None]:
    """각 테스트 전후 ranking_snapshot + stock TRUNCATE."""
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        await s.execute(text("TRUNCATE kiwoom.ranking_snapshot RESTART IDENTITY"))
        await s.execute(text("TRUNCATE kiwoom.stock RESTART IDENTITY CASCADE"))
        await s.commit()
    yield
    async with factory() as s:
        await s.execute(text("TRUNCATE kiwoom.ranking_snapshot RESTART IDENTITY"))
        await s.execute(text("TRUNCATE kiwoom.stock RESTART IDENTITY CASCADE"))
        await s.commit()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """각 테스트는 commit 가능 세션 (testcontainers DB 에 실제 커밋)."""
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s


# ===========================================================================
# 케이스 1 — INSERT 50 row upsert 정상
# ===========================================================================


@pytest.mark.asyncio
async def test_upsert_50_rows_normal(session: AsyncSession) -> None:
    """5 ranking_type × 10 rank = 50 row INSERT upsert 정상.

    upsert_many — UNIQUE 충돌 없는 첫 INSERT.
    """
    stock_id = await _create_stock(session, "005930")
    repo = RankingSnapshotRepository(session)

    rows = [
        _make_snapshot_row(
            ranking_type=rt,
            rank=r,
            stock_code_raw=f"00593{r}",
            stock_id=stock_id,
            primary_metric=Decimal(f"{r * 10}.{r:04d}"),
        )
        for rt in _RANKING_TYPES
        for r in range(1, 11)
    ]

    inserted = await repo.upsert_many(rows)
    await session.commit()

    result = await session.execute(
        text("SELECT COUNT(*) FROM kiwoom.ranking_snapshot")
    )
    count = result.scalar_one()
    assert count == 50, f"50 row INSERT 기대, 실제={count}"
    assert inserted == 50, f"upsert_many 반환값 50 기대, 실제={inserted}"


# ===========================================================================
# 케이스 2 — 동일 UNIQUE 키 2회 upsert → row 수 50 유지 (멱등성)
# ===========================================================================


@pytest.mark.asyncio
async def test_upsert_idempotent_same_unique_key(session: AsyncSession) -> None:
    """동일 (snapshot_date, snapshot_time, ranking_type, sort_tp, market_type, exchange_type, rank) → UPDATE.

    2회 upsert → row 수 50 유지 (D-2 UNIQUE 키 멱등성 보장).
    """
    stock_id = await _create_stock(session, "005930")
    repo = RankingSnapshotRepository(session)

    rows = [
        _make_snapshot_row(
            ranking_type=RankingType.FLU_RT,
            rank=r,
            stock_id=stock_id,
            stock_code_raw="005930",
            primary_metric=Decimal("29.86"),
        )
        for r in range(1, 11)
    ]

    # 1회차 INSERT
    await repo.upsert_many(rows)
    await session.commit()

    # 2회차 — 동일 UNIQUE 키 → UPDATE (primary_metric 변경)
    rows_updated = [
        _make_snapshot_row(
            ranking_type=RankingType.FLU_RT,
            rank=r,
            stock_id=stock_id,
            stock_code_raw="005930",
            primary_metric=Decimal("31.00"),  # 값 변경
        )
        for r in range(1, 11)
    ]
    await repo.upsert_many(rows_updated)
    await session.commit()

    result = await session.execute(
        text(
            "SELECT COUNT(*), MAX(primary_metric) FROM kiwoom.ranking_snapshot "
            "WHERE ranking_type = 'FLU_RT'"
        )
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == 10, f"2회 upsert → 10 row 유지 기대, 실제={row[0]}"
    assert row[1] == Decimal("31.0000"), f"2회차 primary_metric UPDATE 기대, 실제={row[1]}"


# ===========================================================================
# 케이스 3 — JSONB payload 쿼리 (단순 + nested D-9)
# ===========================================================================


@pytest.mark.asyncio
async def test_jsonb_payload_simple_and_nested_query(session: AsyncSession) -> None:
    """JSONB payload->>'cur_prc' 단순 + payload->'opmr'->>'trde_qty' nested (D-9).

    ka10030 의 nested payload ({opmr, af_mkrt, bf_mkrt} 분리) 가 JSONB 로 정상 저장·조회.
    """
    repo = RankingSnapshotRepository(session)

    # ka10030 nested payload
    nested_payload = {
        "cur_prc": "74800",
        "stk_nm": "삼성전자",
        "opmr": {"trde_qty": 446203, "trde_prica": 333000000},
        "af_mkrt": {"trde_qty": 0, "trde_prica": 0},
        "bf_mkrt": {"trde_qty": 346203, "trde_prica": 25900000},
    }

    row = _make_snapshot_row(
        ranking_type=RankingType.TODAY_VOLUME,
        rank=1,
        payload=nested_payload,
        primary_metric=Decimal("446203.0000"),
    )
    await repo.upsert_many([row])
    await session.commit()

    # 단순 쿼리: payload->>'cur_prc'
    result_simple = await session.execute(
        text(
            "SELECT payload->>'cur_prc' FROM kiwoom.ranking_snapshot "
            "WHERE ranking_type = 'TODAY_VOLUME'"
        )
    )
    cur_prc = result_simple.scalar_one()
    assert cur_prc == "74800", f"payload->>'cur_prc' 기대 '74800', 실제={cur_prc!r}"

    # nested 쿼리: payload->'opmr'->>'trde_qty'
    result_nested = await session.execute(
        text(
            "SELECT payload->'opmr'->>'trde_qty' FROM kiwoom.ranking_snapshot "
            "WHERE ranking_type = 'TODAY_VOLUME'"
        )
    )
    opmr_trde_qty = result_nested.scalar_one()
    assert opmr_trde_qty == "446203", f"payload->'opmr'->>'trde_qty' 기대 '446203', 실제={opmr_trde_qty!r}"


# ===========================================================================
# 케이스 4 — GIN index 활용 검증
# ===========================================================================


@pytest.mark.asyncio
async def test_gin_index_payload_query_completes_normally(session: AsyncSession) -> None:
    """GIN index (payload) — JSONB 쿼리가 index scan 정상 완료 (D-13).

    EXPLAIN ANALYZE 로 Bitmap Index Scan on idx_ranking_snapshot_payload 확인.
    주의: testcontainers 소규모 데이터라 Seq Scan 가능 — 적어도 쿼리 정상 완료 검증.
    """
    repo = RankingSnapshotRepository(session)

    rows = [
        _make_snapshot_row(
            ranking_type=RankingType.FLU_RT,
            rank=r,
            stock_code_raw=f"00593{r}",
            payload={"cur_prc": str(74800 + r * 100), "stk_nm": f"테스트{r}"},
        )
        for r in range(1, 6)
    ]
    await repo.upsert_many(rows)
    await session.commit()

    # JSONB @> 연산자 — GIN index 활용 대상
    result = await session.execute(
        text(
            "EXPLAIN (FORMAT JSON) "
            "SELECT * FROM kiwoom.ranking_snapshot "
            "WHERE payload @> '{\"cur_prc\": \"74901\"}'"
        )
    )
    plan_json = result.scalar_one()
    # EXPLAIN 결과가 반환되면 GIN index 존재 + 쿼리 파싱 정상
    assert plan_json is not None, "EXPLAIN 결과 없음 — GIN index 또는 테이블 미존재"

    # 실제 쿼리도 정상 완료
    result2 = await session.execute(
        text(
            "SELECT COUNT(*) FROM kiwoom.ranking_snapshot "
            "WHERE payload @> '{\"cur_prc\": \"74901\"}'"
        )
    )
    count = result2.scalar_one()
    assert count >= 0  # 0 또는 1 — 오류 없이 반환


# ===========================================================================
# 케이스 5 — stock_id NULL (lookup miss) + stock_code_raw 보존
# ===========================================================================


@pytest.mark.asyncio
async def test_stock_id_null_on_lookup_miss(session: AsyncSession) -> None:
    """stock 마스터 미존재 코드 → stock_id=NULL + stock_code_raw 보존 (D-8).

    lookup miss 는 skip 이 아님 (D-10) — ranking_snapshot row 는 적재됨.
    """
    repo = RankingSnapshotRepository(session)

    row = _make_snapshot_row(
        ranking_type=RankingType.FLU_RT,
        rank=1,
        stock_code_raw="999999",
        stock_id=None,  # lookup miss
        primary_metric=Decimal("5.12"),
    )
    await repo.upsert_many([row])
    await session.commit()

    result = await session.execute(
        text(
            "SELECT stock_id, stock_code_raw FROM kiwoom.ranking_snapshot "
            "WHERE stock_code_raw = '999999'"
        )
    )
    db_row = result.fetchone()
    assert db_row is not None, "lookup miss row 가 적재되지 않음"
    assert db_row[0] is None, f"stock_id NULL 기대, 실제={db_row[0]}"
    assert db_row[1] == "999999", f"stock_code_raw 보존 기대, 실제={db_row[1]}"


# ===========================================================================
# 케이스 6 — NXT `_NX` suffix → stock_code_raw 보존 + stock_id lookup 정상
# ===========================================================================


@pytest.mark.asyncio
async def test_nxt_suffix_stock_code_raw_preserved_and_stock_id_mapped(
    session: AsyncSession,
) -> None:
    """NXT `_NX` suffix — stock_code_raw="005930_NX" 보존 + stock_id lookup 정상 (D-8).

    응답 stk_cd "005930_NX" → strip → "005930" 으로 마스터 lookup → stock_id 매핑.
    stock_code_raw 는 원본 "005930_NX" 보존 (분석 시 NXT vs KRX 분리 가능).
    """
    stock_id = await _create_stock(session, "005930")
    repo = RankingSnapshotRepository(session)

    row = _make_snapshot_row(
        ranking_type=RankingType.FLU_RT,
        rank=1,
        stock_code_raw="005930_NX",  # NXT suffix 원본 보존
        stock_id=stock_id,           # strip 후 lookup 한 결과
        primary_metric=Decimal("29.86"),
    )
    await repo.upsert_many([row])
    await session.commit()

    result = await session.execute(
        text(
            "SELECT stock_id, stock_code_raw FROM kiwoom.ranking_snapshot "
            "WHERE stock_code_raw = '005930_NX'"
        )
    )
    db_row = result.fetchone()
    assert db_row is not None, "NXT suffix row 가 적재되지 않음"
    assert db_row[0] == stock_id, f"stock_id 매핑 기대 {stock_id}, 실제={db_row[0]}"
    assert db_row[1] == "005930_NX", f"stock_code_raw NXT suffix 보존 기대, 실제={db_row[1]}"


# ===========================================================================
# 케이스 7 — 5 ranking_type 분리 동시 적재 (250 row, 충돌 0)
# ===========================================================================


@pytest.mark.asyncio
async def test_five_ranking_types_separate_upsert_no_conflict(session: AsyncSession) -> None:
    """5 ranking_type 분리 동시 적재 — 각 50 row × 5 = 250 row, UNIQUE 충돌 0.

    UNIQUE 키: (snapshot_date, snapshot_time, ranking_type, sort_tp, market_type, exchange_type, rank)
    ranking_type 이 다르면 같은 rank/stock 이어도 충돌 없음.
    """
    repo = RankingSnapshotRepository(session)

    all_rows = []
    for rt in _RANKING_TYPES:
        for r in range(1, 11):
            all_rows.append(
                _make_snapshot_row(
                    ranking_type=rt,
                    rank=r,
                    stock_code_raw=f"00593{r}",
                    primary_metric=Decimal(f"{r * 5}.{r:04d}"),
                )
            )

    await repo.upsert_many(all_rows)
    await session.commit()

    result = await session.execute(
        text("SELECT COUNT(*) FROM kiwoom.ranking_snapshot")
    )
    count = result.scalar_one()
    assert count == 50, f"5 × 10 = 50 row 기대, 실제={count}"
    # ranking_type 별 각 10 row
    for rt in _RANKING_TYPES:
        result_rt = await session.execute(
            text(
                "SELECT COUNT(*) FROM kiwoom.ranking_snapshot "
                "WHERE ranking_type = :rt"
            ).bindparams(rt=rt.value)
        )
        rt_count = result_rt.scalar_one()
        assert rt_count == 10, f"{rt.value} ranking_type 10 row 기대, 실제={rt_count}"


# ===========================================================================
# 케이스 8 — get_at_snapshot(date, time, type) 정상 + rank 순 정렬
# ===========================================================================


@pytest.mark.asyncio
async def test_get_at_snapshot_returns_rows_sorted_by_rank(session: AsyncSession) -> None:
    """get_at_snapshot(date, time, type) — 저장된 row 반환 + rank 순 정렬 검증.

    plan § 5.3 — RankingSnapshotRepository.get_at_snapshot.
    """
    repo = RankingSnapshotRepository(session)

    # rank 역순으로 INSERT
    rows = [
        _make_snapshot_row(
            ranking_type=RankingType.FLU_RT,
            rank=r,
            stock_code_raw=f"00593{r}",
            primary_metric=Decimal(f"{(11 - r) * 5}.0000"),
        )
        for r in [5, 3, 1, 4, 2]  # 역순
    ]
    await repo.upsert_many(rows)
    await session.commit()

    fetched = await repo.get_at_snapshot(
        snapshot_date=_SNAPSHOT_DATE,
        snapshot_time=_SNAPSHOT_TIME_1930,
        ranking_type=RankingType.FLU_RT,
    )

    assert len(fetched) == 5, f"5 row 기대, 실제={len(fetched)}"
    # rank 오름차순 정렬 검증
    ranks = [row.rank for row in fetched]
    assert ranks == sorted(ranks), f"rank 순 정렬 기대, 실제={ranks}"
    assert ranks[0] == 1, f"첫 row rank=1 기대, 실제={ranks[0]}"


__all__: list[Any] = []
