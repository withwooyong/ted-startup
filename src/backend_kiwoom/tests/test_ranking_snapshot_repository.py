"""RankingSnapshotRepository — upsert_many + get_at_snapshot 단위 테스트 (Phase F-4).

설계: endpoint-18-ka10027.md § 6.2 + phase-f-4-rankings.md § 5.3.

본 테스트는 import 실패가 red 의도 (Step 0 TDD red):
- `app.adapter.out.persistence.repositories.ranking_snapshot.RankingSnapshotRepository` 미존재
- `app.application.dto.ranking.NormalizedRanking` 미존재
- `app.adapter.out.kiwoom._records.RankingType` 미존재
→ Step 1 에서 신규 구현 후 green.

테스트 시나리오:
1. upsert_many INSERT — 5 row + ranking_type 컬럼 값 검증
2. upsert_many UPDATE 멱등성 — 같은 UNIQUE 키 재호출 시 fetched_at 만 갱신
3. upsert_many 빈 입력 → 0 반환
4. lookup miss → stock_id=NULL + stock_code_raw 보존
5. NXT `_NX` suffix → stock_code_raw 보존 + stock_id 매핑 (strip 후)
6. JSONB payload round-trip — nested dict (D-9 ka10030 패턴) 보존
7. JSONB request_filters round-trip
8. get_at_snapshot — 6 조건 필터 (date+time+ranking_type+sort_tp+market_type+exchange_type)
9. get_at_snapshot — rank ASC 정렬
10. get_at_snapshot limit
11. get_at_snapshot 미일치 → 빈 list
12. 5 ranking_type 같은 시점 분리 — FLU_RT / TODAY_VOLUME / PRED_VOLUME / TRDE_PRICA / VOLUME_SDNIN
13. primary_metric Decimal 정확성 (D-12 NUMERIC(20,4))
14. ON DELETE SET NULL — stock 삭제 시 stock_id=NULL 보존
"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._records import RankingType  # type: ignore[import]  # Step 1
from app.adapter.out.persistence.repositories.ranking_snapshot import (  # type: ignore[import]  # Step 1
    RankingSnapshotRepository,
)
from app.application.dto.ranking import NormalizedRanking  # type: ignore[import]  # Step 1

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


async def _insert_test_stock(session: AsyncSession, code: str = "005930") -> int:
    """test stock 1개 INSERT — returning id."""
    result = await session.execute(
        text(
            "INSERT INTO kiwoom.stock "
            "(stock_code, stock_name, market_code, market_name, is_active) "
            "VALUES (:code, '삼성전자', '0', 'KOSPI', TRUE) "
            "ON CONFLICT (stock_code) DO UPDATE SET is_active=TRUE "
            "RETURNING id"
        ).bindparams(code=code)
    )
    stock_id_row = result.fetchone()
    assert stock_id_row is not None
    return int(stock_id_row[0])


def _make_normalized_row(
    *,
    snapshot_date: date = date(2026, 5, 14),
    snapshot_time: time = time(19, 30, 0),
    ranking_type: RankingType = RankingType.FLU_RT,
    sort_tp: str = "1",
    market_type: str = "001",
    exchange_type: str = "3",
    rank: int = 1,
    stock_id: int | None = None,
    stock_code_raw: str = "005930",
    primary_metric: Decimal | None = Decimal("29.8600"),
    payload: dict | None = None,
    request_filters: dict | None = None,
) -> NormalizedRanking:
    """NormalizedRanking 빌더 — defaults 는 ka10027 첫 row."""
    return NormalizedRanking(
        snapshot_date=snapshot_date,
        snapshot_time=snapshot_time,
        ranking_type=ranking_type,
        sort_tp=sort_tp,
        market_type=market_type,
        exchange_type=exchange_type,
        rank=rank,
        stock_id=stock_id,
        stock_code_raw=stock_code_raw,
        primary_metric=primary_metric,
        payload=payload or {"stk_nm": "삼성전자", "cur_prc": 74800},
        request_filters=request_filters
        or {"mrkt_tp": "001", "sort_tp": "1", "stex_tp": "3"},
    )


# ---------------------------------------------------------------------------
# Scenario 1 — upsert_many INSERT (빈 DB + N row)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_many_inserts_rows(session: AsyncSession) -> None:
    """upsert_many — 빈 DB + 5 row → 5 row INSERT."""
    stock_id = await _insert_test_stock(session)
    repo = RankingSnapshotRepository(session)

    rows = [
        _make_normalized_row(rank=i, stock_id=stock_id) for i in range(1, 6)
    ]
    upserted = await repo.upsert_many(rows)

    assert upserted == 5

    # DB 검증
    result = await session.execute(
        text(
            "SELECT COUNT(*) FROM kiwoom.ranking_snapshot "
            "WHERE snapshot_date = '2026-05-14' AND ranking_type = 'FLU_RT'"
        )
    )
    count = result.scalar_one()
    assert count == 5


# ---------------------------------------------------------------------------
# Scenario 2 — upsert_many UPDATE 멱등성 (같은 UNIQUE 키 재호출)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_many_on_conflict_updates(session: AsyncSession) -> None:
    """같은 (date+time+type+sort+market+exchange+rank) UPDATE — fetched_at 갱신."""
    stock_id = await _insert_test_stock(session)
    repo = RankingSnapshotRepository(session)

    # 1차 INSERT — primary_metric 29.86
    rows1 = [_make_normalized_row(rank=1, stock_id=stock_id)]
    await repo.upsert_many(rows1)

    # 2차 — 같은 UNIQUE 키, primary_metric 변경
    rows2 = [
        _make_normalized_row(
            rank=1,
            stock_id=stock_id,
            primary_metric=Decimal("30.1234"),
            payload={"stk_nm": "삼성전자", "cur_prc": 74900},
        )
    ]
    await repo.upsert_many(rows2)

    # row 1개만 존재 — 멱등성 보장
    result = await session.execute(
        text(
            "SELECT COUNT(*), MAX(primary_metric), payload->>'cur_prc' "
            "FROM kiwoom.ranking_snapshot "
            "WHERE snapshot_date = '2026-05-14' AND rank = 1 "
            "GROUP BY payload"
        )
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == 1, f"멱등성 깨짐 — row {row[0]}개"
    assert row[1] == Decimal("30.1234"), f"UPDATE primary_metric 미반영: {row[1]}"
    assert row[2] == "74900", f"UPDATE payload 미반영: {row[2]}"


# ---------------------------------------------------------------------------
# Scenario 3 — 빈 입력 → 0 반환
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_many_empty_rows_returns_zero(session: AsyncSession) -> None:
    """빈 list 입력 → 0 반환 (early return, DB 호출 없음)."""
    repo = RankingSnapshotRepository(session)
    upserted = await repo.upsert_many([])
    assert upserted == 0


# ---------------------------------------------------------------------------
# Scenario 4 — lookup miss stock_id=NULL + stock_code_raw 보존
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_many_lookup_miss_stock_id_null(session: AsyncSession) -> None:
    """stock 마스터 부재 → stock_id=NULL + stock_code_raw 보존 (D-8)."""
    repo = RankingSnapshotRepository(session)

    rows = [_make_normalized_row(stock_id=None, stock_code_raw="999999")]
    upserted = await repo.upsert_many(rows)

    assert upserted == 1

    result = await session.execute(
        text(
            "SELECT stock_id, stock_code_raw FROM kiwoom.ranking_snapshot "
            "WHERE stock_code_raw = '999999'"
        )
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] is None, f"stock_id NULL 기대, 실제: {row[0]}"
    assert row[1] == "999999"


# ---------------------------------------------------------------------------
# Scenario 5 — NXT `_NX` suffix stock_code_raw 보존
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_many_nxt_suffix_preserved(session: AsyncSession) -> None:
    """NXT 응답 `005930_NX` → stock_code_raw 보존 + stock_id 매핑은 strip 후 (caller 책임)."""
    stock_id = await _insert_test_stock(session, code="005930")
    repo = RankingSnapshotRepository(session)

    # caller (UseCase) 가 strip_kiwoom_suffix 후 stock_id 결정 — Repository 는 raw 만 보관
    rows = [
        _make_normalized_row(
            stock_id=stock_id,
            stock_code_raw="005930_NX",  # NXT suffix 보존
        )
    ]
    await repo.upsert_many(rows)

    result = await session.execute(
        text(
            "SELECT stock_code_raw FROM kiwoom.ranking_snapshot "
            "WHERE stock_id = :sid AND snapshot_date = '2026-05-14'"
        ).bindparams(sid=stock_id)
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == "005930_NX", f"NXT suffix 미보존: {row[0]!r}"


# ---------------------------------------------------------------------------
# Scenario 6 — JSONB payload round-trip (D-9 nested 패턴)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_many_jsonb_nested_payload(session: AsyncSession) -> None:
    """ka10030 nested payload (D-9) — {opmr, af_mkrt, bf_mkrt} 분리 보존."""
    stock_id = await _insert_test_stock(session)
    repo = RankingSnapshotRepository(session)

    nested = {
        "stk_nm": "삼성전자",
        "cur_prc": 74800,
        "opmr": {"trde_qty": 446203, "trde_prica": 333000000},
        "af_mkrt": {"trde_qty": 0, "trde_prica": 0},
        "bf_mkrt": {"trde_qty": 12345, "trde_prica": 9000000},
    }
    rows = [
        _make_normalized_row(
            ranking_type=RankingType.TODAY_VOLUME,
            stock_id=stock_id,
            payload=nested,
        )
    ]
    await repo.upsert_many(rows)

    result = await session.execute(
        text(
            "SELECT payload->'opmr'->>'trde_qty', "
            "       payload->'bf_mkrt'->>'trde_prica' "
            "FROM kiwoom.ranking_snapshot "
            "WHERE ranking_type = 'TODAY_VOLUME' "
            "  AND snapshot_date = '2026-05-14'"
        )
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == "446203", f"nested opmr.trde_qty 미보존: {row[0]!r}"
    assert row[1] == "9000000", f"nested bf_mkrt.trde_prica 미보존: {row[1]!r}"


# ---------------------------------------------------------------------------
# Scenario 7 — JSONB request_filters round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_many_jsonb_request_filters(session: AsyncSession) -> None:
    """request_filters JSONB — 호출 시 8 필터 (재현용) 보관."""
    stock_id = await _insert_test_stock(session)
    repo = RankingSnapshotRepository(session)

    filters = {
        "mrkt_tp": "001",
        "sort_tp": "1",
        "trde_qty_cnd": "0000",
        "stk_cnd": "0",
        "crd_cnd": "0",
        "updown_incls": "1",
        "pric_cnd": "0",
        "trde_prica_cnd": "0",
        "stex_tp": "3",
    }
    rows = [_make_normalized_row(stock_id=stock_id, request_filters=filters)]
    await repo.upsert_many(rows)

    result = await session.execute(
        text(
            "SELECT request_filters->>'mrkt_tp', request_filters->>'stex_tp', "
            "       request_filters->>'trde_qty_cnd' "
            "FROM kiwoom.ranking_snapshot "
            "WHERE snapshot_date = '2026-05-14' AND ranking_type = 'FLU_RT'"
        )
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == "001"
    assert row[1] == "3"
    assert row[2] == "0000"


# ---------------------------------------------------------------------------
# Scenario 8 — get_at_snapshot 6 조건 필터
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_at_snapshot_filters_by_all_keys(session: AsyncSession) -> None:
    """get_at_snapshot — 6 조건 정확히 매칭하는 row 만 반환."""
    stock_id = await _insert_test_stock(session)
    repo = RankingSnapshotRepository(session)

    # 같은 시점 + 다른 sort_tp 두 종류
    rows = [
        _make_normalized_row(rank=1, sort_tp="1", stock_id=stock_id),
        _make_normalized_row(rank=2, sort_tp="1", stock_id=stock_id),
        _make_normalized_row(rank=1, sort_tp="3", stock_id=stock_id),
        _make_normalized_row(rank=2, sort_tp="3", stock_id=stock_id),
    ]
    await repo.upsert_many(rows)

    # sort_tp=1 만 조회 — 2 row 기대
    result = await repo.get_at_snapshot(
        snapshot_date=date(2026, 5, 14),
        snapshot_time=time(19, 30, 0),
        ranking_type=RankingType.FLU_RT,
        sort_tp="1",
        market_type="001",
        exchange_type="3",
    )
    assert len(result) == 2
    assert all(r.sort_tp == "1" for r in result)


# ---------------------------------------------------------------------------
# Scenario 9 — get_at_snapshot rank ASC 정렬
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_at_snapshot_order_by_rank_asc(session: AsyncSession) -> None:
    """get_at_snapshot — rank ASC 정렬 (1, 2, 3, ...)."""
    stock_id = await _insert_test_stock(session)
    repo = RankingSnapshotRepository(session)

    # 5 row 역순 INSERT — 정렬 검증
    rows = [_make_normalized_row(rank=r, stock_id=stock_id) for r in [5, 3, 1, 4, 2]]
    await repo.upsert_many(rows)

    result = await repo.get_at_snapshot(
        snapshot_date=date(2026, 5, 14),
        snapshot_time=time(19, 30, 0),
        ranking_type=RankingType.FLU_RT,
        sort_tp="1",
        market_type="001",
        exchange_type="3",
    )
    ranks = [r.rank for r in result]
    assert ranks == [1, 2, 3, 4, 5], f"rank ASC 정렬 깨짐: {ranks}"


# ---------------------------------------------------------------------------
# Scenario 10 — get_at_snapshot limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_at_snapshot_limit(session: AsyncSession) -> None:
    """get_at_snapshot — limit 적용 (default 50, 명시 가능)."""
    stock_id = await _insert_test_stock(session)
    repo = RankingSnapshotRepository(session)

    rows = [_make_normalized_row(rank=r, stock_id=stock_id) for r in range(1, 11)]
    await repo.upsert_many(rows)

    # limit=3
    result = await repo.get_at_snapshot(
        snapshot_date=date(2026, 5, 14),
        snapshot_time=time(19, 30, 0),
        ranking_type=RankingType.FLU_RT,
        sort_tp="1",
        market_type="001",
        exchange_type="3",
        limit=3,
    )
    assert len(result) == 3
    assert [r.rank for r in result] == [1, 2, 3]


# ---------------------------------------------------------------------------
# Scenario 11 — get_at_snapshot 미일치 → 빈 list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_at_snapshot_no_match_returns_empty(session: AsyncSession) -> None:
    """get_at_snapshot — 미일치 (다른 날짜) → 빈 list."""
    repo = RankingSnapshotRepository(session)

    result = await repo.get_at_snapshot(
        snapshot_date=date(2025, 1, 1),  # 데이터 없는 날짜
        snapshot_time=time(19, 30, 0),
        ranking_type=RankingType.FLU_RT,
        sort_tp="1",
        market_type="001",
        exchange_type="3",
    )
    assert result == []


# ---------------------------------------------------------------------------
# Scenario 12 — 5 ranking_type 같은 시점 분리
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_many_5_ranking_types_isolated(session: AsyncSession) -> None:
    """같은 (date+time+sort+market+exchange+rank) 라도 ranking_type 분리 시 5 row 공존."""
    stock_id = await _insert_test_stock(session)
    repo = RankingSnapshotRepository(session)

    rows = [
        _make_normalized_row(ranking_type=rt, stock_id=stock_id)
        for rt in (
            RankingType.FLU_RT,
            RankingType.TODAY_VOLUME,
            RankingType.PRED_VOLUME,
            RankingType.TRDE_PRICA,
            RankingType.VOLUME_SDNIN,
        )
    ]
    upserted = await repo.upsert_many(rows)
    assert upserted == 5

    result = await session.execute(
        text(
            "SELECT DISTINCT ranking_type FROM kiwoom.ranking_snapshot "
            "WHERE snapshot_date = '2026-05-14' AND rank = 1 "
            "ORDER BY ranking_type"
        )
    )
    types = [row[0] for row in result.fetchall()]
    assert set(types) == {
        "FLU_RT",
        "PRED_VOLUME",
        "TODAY_VOLUME",
        "TRDE_PRICA",
        "VOLUME_SDNIN",
    }


# ---------------------------------------------------------------------------
# Scenario 13 — primary_metric Decimal 정확성 (NUMERIC(20,4))
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_many_primary_metric_decimal_precision(
    session: AsyncSession,
) -> None:
    """NUMERIC(20, 4) — 큰 거래대금 + 작은 등락률 모두 정확히 round-trip."""
    stock_id = await _insert_test_stock(session)
    repo = RankingSnapshotRepository(session)

    # 큰 거래대금 (ka10032 백만원 단위 — 16자리)
    big_amount = Decimal("9999999999999999.9999")
    # 작은 등락률
    small_rate = Decimal("0.0001")

    rows = [
        _make_normalized_row(
            ranking_type=RankingType.TRDE_PRICA,
            sort_tp="1",
            rank=1,
            stock_id=stock_id,
            primary_metric=big_amount,
        ),
        _make_normalized_row(
            ranking_type=RankingType.FLU_RT,
            sort_tp="1",
            rank=2,
            stock_id=stock_id,
            primary_metric=small_rate,
        ),
    ]
    await repo.upsert_many(rows)

    result = await session.execute(
        text(
            "SELECT ranking_type, primary_metric "
            "FROM kiwoom.ranking_snapshot "
            "WHERE snapshot_date = '2026-05-14' "
            "ORDER BY rank"
        )
    )
    metrics = {row[0]: row[1] for row in result.fetchall()}
    assert metrics["TRDE_PRICA"] == big_amount, (
        f"큰 NUMERIC 정확성 손실: {metrics['TRDE_PRICA']}"
    )
    assert metrics["FLU_RT"] == small_rate, (
        f"작은 NUMERIC 정확성 손실: {metrics['FLU_RT']}"
    )


# ---------------------------------------------------------------------------
# Scenario 14 — ON DELETE SET NULL 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_on_delete_set_null_preserves_ranking_row(
    session: AsyncSession,
) -> None:
    """stock 삭제 → ranking_snapshot.stock_id=NULL 으로 SET NULL (row 보존)."""
    stock_id = await _insert_test_stock(session, code="009999")
    repo = RankingSnapshotRepository(session)

    rows = [_make_normalized_row(stock_id=stock_id, stock_code_raw="009999")]
    await repo.upsert_many(rows)

    # stock 삭제
    await session.execute(
        text("DELETE FROM kiwoom.stock WHERE id = :sid").bindparams(sid=stock_id)
    )

    # ranking_snapshot row 보존 + stock_id=NULL
    result = await session.execute(
        text(
            "SELECT stock_id, stock_code_raw FROM kiwoom.ranking_snapshot "
            "WHERE stock_code_raw = '009999'"
        )
    )
    row = result.fetchone()
    assert row is not None, "ON DELETE SET NULL 실패 — ranking_snapshot row 도 삭제됨"
    assert row[0] is None, f"stock_id 가 NULL 되어야: {row[0]}"
    assert row[1] == "009999"
