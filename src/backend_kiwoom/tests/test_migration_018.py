"""Alembic Migration 018 — kiwoom.ranking_snapshot 신규 (Phase F-4).

설계: endpoint-18-ka10027.md § 5.1 + phase-f-4-rankings.md § 5.1.
사용자 확정 (default 일괄 채택):
    D-2 단일 테이블 + JSONB payload + ranking_type 컬럼
    D-7 snapshot_time 초 단위 (HH:MM:SS)
    D-12 primary_metric NUMERIC(20, 4)
    D-13 GIN index payload 1개

> plan doc 의 "007_ranking_snapshot" 은 stale — 실제 head 가 017 이라
> revision id = 018_ranking_snapshot. ADR § 48 정정 기록.

016 / 017 패턴 1:1 응용:
- 016 = 2 테이블 1 마이그레이션 + partial unique
- 017 = 단일 ALTER (NUMERIC 확대)
- 018 = 1 테이블 1 마이그레이션 + GIN + partial index

검증:
- 017 → 018 upgrade 성공 / revision id / down_revision
- ranking_snapshot 컬럼 15개 (id + 13 도메인 + 메타 2 fetched_at/created_at)
- FK (stock_id → kiwoom.stock(id) ON DELETE SET NULL)
- UNIQUE 7컬럼 (snapshot_date, snapshot_time, ranking_type, sort_tp,
              market_type, exchange_type, rank)
- 컬럼 타입 (TIME / VARCHAR(16) / VARCHAR(3) / VARCHAR(1) / NUMERIC(20,4) / JSONB)
- 일반 인덱스 idx_ranking_date_type
- partial index idx_ranking_stock (WHERE stock_id IS NOT NULL)
- GIN index idx_ranking_payload_gin USING GIN
- 018 → 017 downgrade — ranking_snapshot DROP / stock_fundamental 유지
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

RANKING_TABLE = "ranking_snapshot"

EXPECTED_RANKING_COLUMNS = {
    "id",
    "snapshot_date",
    "snapshot_time",
    "ranking_type",
    "sort_tp",
    "market_type",
    "exchange_type",
    "rank",
    "stock_id",
    "stock_code_raw",
    "primary_metric",
    "payload",
    "request_filters",
    "fetched_at",
    "created_at",
}


# ---------------------------------------------------------------------------
# Scenario 1 — 마이그레이션 적용 (revision id + down_revision)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_018_revision_id_and_down_revision(engine: AsyncEngine) -> None:
    """017 → 018 upgrade 성공 — alembic_version 이 018 이상.

    018 미적용 시 fail — pre-018 revision 거부.
    """
    async with engine.connect() as conn:
        version = await conn.execute(
            text("SELECT version_num FROM kiwoom.alembic_version")
        )
        rev = version.scalar_one()
    assert rev not in (
        "014_stock_price_yearly",
        "015_sector_price_daily",
        "016_short_lending",
        "017_ka10001_numeric_precision",
    ), (
        f"018 미적용 — alembic_version='{rev}' (018 또는 이후 head 기대)"
    )


# ---------------------------------------------------------------------------
# Scenario 2 — ranking_snapshot 테이블 검증 (컬럼 + FK + UNIQUE)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ranking_snapshot_columns_and_fk(engine: AsyncEngine) -> None:
    """ranking_snapshot 컬럼 15개 + FK (stock_id → kiwoom.stock(id) ON DELETE SET NULL)
    + UNIQUE 7컬럼 (snapshot_date, snapshot_time, ranking_type, sort_tp,
                   market_type, exchange_type, rank)."""
    async with engine.connect() as conn:

        def _inspect(sync_conn) -> tuple[set[str], list[dict], list[dict]]:  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            cols = {c["name"] for c in insp.get_columns(RANKING_TABLE, schema="kiwoom")}
            fks = insp.get_foreign_keys(RANKING_TABLE, schema="kiwoom")
            uqs = insp.get_unique_constraints(RANKING_TABLE, schema="kiwoom")
            return cols, fks, uqs

        cols, fks, uqs = await conn.run_sync(_inspect)

    missing = EXPECTED_RANKING_COLUMNS - cols
    extra = cols - EXPECTED_RANKING_COLUMNS
    assert not missing, f"ranking_snapshot 누락 컬럼: {missing}"
    assert not extra, f"ranking_snapshot 예상 외 컬럼: {extra}"
    assert len(cols) == 15, f"컬럼 수 15 기대, 실제 {len(cols)}: {sorted(cols)}"

    # FK 검증 — stock_id → kiwoom.stock(id) ON DELETE SET NULL
    assert fks, "ranking_snapshot FK 부재"
    stock_fk = next((f for f in fks if f["constrained_columns"] == ["stock_id"]), None)
    assert stock_fk is not None, f"stock_id FK 부재: {fks}"
    assert stock_fk["referred_schema"] == "kiwoom"
    assert stock_fk["referred_table"] == "stock"
    assert stock_fk["referred_columns"] == ["id"]
    assert stock_fk["options"].get("ondelete", "").upper() == "SET NULL", (
        f"ON DELETE SET NULL 부재 (lookup miss 후 stock 삭제 시 NULL 보존): {stock_fk['options']}"
    )

    # UNIQUE 7컬럼 검증
    uq_col_sets = [set(u["column_names"]) for u in uqs]
    expected_uq = {
        "snapshot_date",
        "snapshot_time",
        "ranking_type",
        "sort_tp",
        "market_type",
        "exchange_type",
        "rank",
    }
    assert expected_uq in uq_col_sets, (
        f"UNIQUE 7컬럼 부재 (uq_ranking_snapshot): {uqs}"
    )


# ---------------------------------------------------------------------------
# Scenario 3 — 컬럼 타입 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ranking_snapshot_column_types(engine: AsyncEngine) -> None:
    """컬럼 타입 검증 — snapshot_date DATE / snapshot_time TIME / VARCHAR 길이 / NUMERIC(20,4) / JSONB."""
    async with engine.connect() as conn:

        def _col_types(sync_conn) -> dict[str, dict]:  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            return {c["name"]: c for c in insp.get_columns(RANKING_TABLE, schema="kiwoom")}

        col_map = await conn.run_sync(_col_types)

    # snapshot_date — DATE
    snapshot_date_type = str(col_map["snapshot_date"]["type"]).upper()
    assert "DATE" in snapshot_date_type, (
        f"snapshot_date 타입 DATE 기대, 실제: {snapshot_date_type}"
    )

    # snapshot_time — TIME (D-7 초 단위 precision 은 PG TIME default = microsecond)
    snapshot_time_type = str(col_map["snapshot_time"]["type"]).upper()
    assert "TIME" in snapshot_time_type, (
        f"snapshot_time 타입 TIME 기대, 실제: {snapshot_time_type}"
    )

    # ranking_type — VARCHAR(16)
    rt_col = col_map["ranking_type"]
    rt_type = str(rt_col["type"]).upper()
    assert "VARCHAR" in rt_type or "CHARACTER VARYING" in rt_type, (
        f"ranking_type 타입 VARCHAR 기대, 실제: {rt_type}"
    )
    rt_length = getattr(rt_col["type"], "length", None)
    assert rt_length == 16, f"ranking_type VARCHAR 길이 16 기대, 실제: {rt_length}"

    # market_type — VARCHAR(3) (000/001/101)
    mt_col = col_map["market_type"]
    mt_length = getattr(mt_col["type"], "length", None)
    assert mt_length == 3, f"market_type VARCHAR 길이 3 기대, 실제: {mt_length}"

    # exchange_type — VARCHAR(1) (1/2/3)
    et_col = col_map["exchange_type"]
    et_length = getattr(et_col["type"], "length", None)
    assert et_length == 1, f"exchange_type VARCHAR 길이 1 기대, 실제: {et_length}"

    # sort_tp — VARCHAR(2)
    sort_col = col_map["sort_tp"]
    sort_length = getattr(sort_col["type"], "length", None)
    assert sort_length == 2, f"sort_tp VARCHAR 길이 2 기대, 실제: {sort_length}"

    # stock_code_raw — VARCHAR(20) (NXT _NX 보존)
    scr_col = col_map["stock_code_raw"]
    scr_length = getattr(scr_col["type"], "length", None)
    assert scr_length == 20, f"stock_code_raw VARCHAR 길이 20 기대, 실제: {scr_length}"

    # primary_metric — NUMERIC(20,4) (D-12)
    pm_col = col_map["primary_metric"]
    pm_type = str(pm_col["type"]).upper()
    assert "NUMERIC" in pm_type or "DECIMAL" in pm_type, (
        f"primary_metric 타입 NUMERIC 기대, 실제: {pm_type}"
    )
    pm_precision = getattr(pm_col["type"], "precision", None)
    pm_scale = getattr(pm_col["type"], "scale", None)
    assert pm_precision == 20, f"primary_metric NUMERIC precision 20 기대, 실제: {pm_precision}"
    assert pm_scale == 4, f"primary_metric NUMERIC scale 4 기대, 실제: {pm_scale}"

    # stock_id — BIGINT, nullable (lookup miss → NULL)
    stock_id_col = col_map["stock_id"]
    stock_id_type = str(stock_id_col["type"]).upper()
    assert "BIGINT" in stock_id_type or "INT" in stock_id_type, (
        f"stock_id 타입 BIGINT 기대, 실제: {stock_id_type}"
    )
    assert stock_id_col["nullable"] is True, (
        f"stock_id nullable=True 기대 (lookup miss 처리), 실제: {stock_id_col['nullable']}"
    )

    # payload — JSONB
    payload_col = col_map["payload"]
    payload_type = str(payload_col["type"]).upper()
    assert "JSONB" in payload_type or "JSON" in payload_type, (
        f"payload 타입 JSONB 기대, 실제: {payload_type}"
    )
    assert payload_col["nullable"] is False, (
        f"payload NOT NULL 기대, 실제 nullable: {payload_col['nullable']}"
    )

    # request_filters — JSONB
    rf_col = col_map["request_filters"]
    rf_type = str(rf_col["type"]).upper()
    assert "JSONB" in rf_type or "JSON" in rf_type, (
        f"request_filters 타입 JSONB 기대, 실제: {rf_type}"
    )

    # rank — INTEGER NOT NULL
    rank_col = col_map["rank"]
    rank_type = str(rank_col["type"]).upper()
    assert "INT" in rank_type, f"rank 타입 INTEGER 기대, 실제: {rank_type}"
    assert rank_col["nullable"] is False, "rank NOT NULL 기대"


# ---------------------------------------------------------------------------
# Scenario 4 — 일반 인덱스 idx_ranking_date_type 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ranking_snapshot_idx_date_type(engine: AsyncEngine) -> None:
    """idx_ranking_date_type — (snapshot_date, ranking_type, market_type, exchange_type) 복합 인덱스."""
    async with engine.connect() as conn:
        row = await conn.execute(
            text(
                "SELECT indexdef FROM pg_indexes"
                " WHERE schemaname = 'kiwoom'"
                " AND tablename = :tbl"
                " AND indexname = 'idx_ranking_date_type'"
            ).bindparams(tbl=RANKING_TABLE)
        )
        result = row.fetchone()

    assert result is not None, "idx_ranking_date_type 인덱스 부재"
    indexdef = result[0].lower()
    # 복합 키 — 4 컬럼 모두 포함
    for col in ("snapshot_date", "ranking_type", "market_type", "exchange_type"):
        assert col in indexdef, (
            f"idx_ranking_date_type 컬럼 '{col}' 부재: {indexdef}"
        )


# ---------------------------------------------------------------------------
# Scenario 5 — partial index idx_ranking_stock (WHERE stock_id IS NOT NULL)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ranking_snapshot_partial_index_stock(engine: AsyncEngine) -> None:
    """idx_ranking_stock partial index — WHERE stock_id IS NOT NULL.

    lookup miss row (stock_id=NULL) 는 본 index 진입 안 함 — index 크기 절감.
    """
    async with engine.connect() as conn:
        row = await conn.execute(
            text(
                "SELECT indexdef FROM pg_indexes"
                " WHERE schemaname = 'kiwoom'"
                " AND tablename = :tbl"
                " AND indexname = 'idx_ranking_stock'"
            ).bindparams(tbl=RANKING_TABLE)
        )
        result = row.fetchone()

    assert result is not None, "idx_ranking_stock 인덱스 부재"
    indexdef = result[0].lower()
    assert "where" in indexdef, (
        f"partial index WHERE 절 부재: {indexdef}"
    )
    assert "stock_id" in indexdef, (
        f"partial index 조건에 stock_id 부재: {indexdef}"
    )
    assert "is not null" in indexdef, (
        f"partial index 조건 'IS NOT NULL' 부재: {indexdef}"
    )


# ---------------------------------------------------------------------------
# Scenario 6 — GIN index idx_ranking_payload_gin (D-13)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ranking_snapshot_gin_index_payload(engine: AsyncEngine) -> None:
    """idx_ranking_payload_gin — USING GIN (payload) (D-13).

    ad-hoc 쿼리 (`payload->>'cur_prc'`, `payload @> '{"stk_cls": "0"}'`) 가속.
    """
    async with engine.connect() as conn:
        row = await conn.execute(
            text(
                "SELECT indexdef FROM pg_indexes"
                " WHERE schemaname = 'kiwoom'"
                " AND tablename = :tbl"
                " AND indexname = 'idx_ranking_payload_gin'"
            ).bindparams(tbl=RANKING_TABLE)
        )
        result = row.fetchone()

    assert result is not None, "idx_ranking_payload_gin GIN 인덱스 부재 (D-13)"
    indexdef = result[0].lower()
    assert "using gin" in indexdef, (
        f"GIN access method 부재: {indexdef}"
    )
    assert "payload" in indexdef, (
        f"GIN index 컬럼 payload 부재: {indexdef}"
    )


# ---------------------------------------------------------------------------
# Scenario 7 — created_at / fetched_at server_default = now() 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ranking_snapshot_timestamp_defaults(engine: AsyncEngine) -> None:
    """fetched_at + created_at — TIMESTAMPTZ NOT NULL DEFAULT now()."""
    async with engine.connect() as conn:

        def _col_types(sync_conn) -> dict[str, dict]:  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            return {c["name"]: c for c in insp.get_columns(RANKING_TABLE, schema="kiwoom")}

        col_map = await conn.run_sync(_col_types)

    for tname in ("fetched_at", "created_at"):
        col = col_map[tname]
        col_type = str(col["type"]).upper()
        assert "TIMESTAMP" in col_type, (
            f"{tname} 타입 TIMESTAMPTZ 기대, 실제: {col_type}"
        )
        assert col["nullable"] is False, f"{tname} NOT NULL 기대"
        # server_default 가 now() / CURRENT_TIMESTAMP 둘 다 호환
        default = col.get("default")
        assert default is not None, f"{tname} server_default 미설정"
        default_str = str(default).lower()
        assert "now" in default_str or "current_timestamp" in default_str, (
            f"{tname} server_default = now()/CURRENT_TIMESTAMP 기대, 실제: {default!r}"
        )


# ---------------------------------------------------------------------------
# Scenario 8 — downgrade 검증 (018 → 017)
# ---------------------------------------------------------------------------


def test_migration_018_downgrade_drops_ranking_keeps_fundamental(
    database_url: str,
) -> None:
    """018 → 017 downgrade 시 ranking_snapshot DROP / stock_fundamental 유지.

    빈 테이블 상태 전제 — 018 teardown 후 017 target 까지만 downgrade.
    016 패턴 (downgrade test) 1:1.
    """
    import sqlalchemy as sa

    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    sync_engine = sa.create_engine(database_url.replace("+asyncpg", "+psycopg2"))
    try:
        command.downgrade(alembic_cfg, "017_ka10001_numeric_precision")

        with sync_engine.connect() as conn:
            insp = inspect(conn)
            existing = set(insp.get_table_names(schema="kiwoom"))

        assert RANKING_TABLE not in existing, (
            f"018 downgrade 후 {RANKING_TABLE} 잔존"
        )
        # 017 이전 테이블은 유지 — 비파괴 보장
        assert "stock_fundamental" in existing, (
            "018 downgrade 후 stock_fundamental 삭제됨 (비파괴 보장 실패)"
        )
        assert "short_selling_kw" in existing, (
            "018 downgrade 후 short_selling_kw 삭제됨 (016 비파괴 보장 실패)"
        )

        # 복원 — 다른 테스트가 head 상태 기대
        command.upgrade(alembic_cfg, "head")

        with sync_engine.connect() as conn2:
            insp2 = inspect(conn2)
            restored = set(insp2.get_table_names(schema="kiwoom"))

        assert RANKING_TABLE in restored, (
            f"018 재적용 후 {RANKING_TABLE} 미생성"
        )
    finally:
        sync_engine.dispose()


# ---------------------------------------------------------------------------
# Scenario 9 — JSONB payload 멱등 INSERT smoke
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ranking_snapshot_jsonb_payload_round_trip(engine: AsyncEngine) -> None:
    """JSONB payload + request_filters round trip — 직접 INSERT + SELECT.

    NormalizedRanking dataclass 가 도입 전이라 raw SQL 로 검증 (smoke).
    Repository 단위 테스트는 test_ranking_snapshot_repository.py 에서 별도.
    """
    import json
    from datetime import date, time

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO kiwoom.ranking_snapshot "
                "(snapshot_date, snapshot_time, ranking_type, sort_tp, "
                " market_type, exchange_type, rank, stock_id, stock_code_raw, "
                " primary_metric, payload, request_filters) "
                "VALUES "
                "(:sd, :st, :rt, :sortt, :mt, :et, :rk, :sid, :scr, "
                " :pm, CAST(:payload AS JSONB), CAST(:rf AS JSONB))"
            ).bindparams(
                sd=date(2026, 5, 14),
                st=time(19, 30, 0),
                rt="FLU_RT",
                sortt="1",
                mt="001",
                et="3",
                rk=1,
                sid=None,
                scr="005930",
                pm=29.86,
                payload=json.dumps({"stk_nm": "삼성전자", "cur_prc": 74800}),
                rf=json.dumps({"mrkt_tp": "001", "sort_tp": "1", "stex_tp": "3"}),
            )
        )

        row = await conn.execute(
            text(
                "SELECT ranking_type, payload->>'stk_nm' AS nm, "
                "       request_filters->>'mrkt_tp' AS mt "
                "FROM kiwoom.ranking_snapshot "
                "WHERE stock_code_raw = '005930' "
                "  AND snapshot_date = '2026-05-14' "
                "ORDER BY id DESC LIMIT 1"
            )
        )
        result = row.fetchone()

        # 정리 — 다른 테스트 영향 차단
        await conn.execute(
            text(
                "DELETE FROM kiwoom.ranking_snapshot "
                "WHERE stock_code_raw = '005930' "
                "  AND snapshot_date = '2026-05-14'"
            )
        )

    assert result is not None, "JSONB payload INSERT 실패"
    assert result[0] == "FLU_RT", f"ranking_type 미일치: {result[0]!r}"
    assert result[1] == "삼성전자", f"payload JSONB 추출 실패: {result[1]!r}"
    assert result[2] == "001", f"request_filters JSONB 추출 실패: {result[2]!r}"
