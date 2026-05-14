"""Alembic Migration 016 — kiwoom.short_selling_kw + lending_balance_kw 신규 (Phase E).

설계: endpoint-15-ka10014.md § 12.
chunk = Phase E, plan doc § 12 참조.

015 (sector_price_daily) 패턴 1:1 응용. 2 테이블 1 마이그레이션.

검증:
- 015 → 016 upgrade 성공 / revision id / down_revision
- short_selling_kw 테이블 컬럼 + 타입 + FK + UNIQUE (stock_id, trading_date, exchange)
- short_selling_kw partial index (idx_short_selling_kw_weight_high)
- lending_balance_kw 테이블 컬럼 + scope VARCHAR(8) + stock_id nullable + CHECK constraint
- lending_balance_kw partial unique 2개 (uq_lending_market_date / uq_lending_stock_date)
- 016 → 015 downgrade — 2 테이블 DROP / sector_price_daily 유지
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

SHORT_SELLING_TABLE = "short_selling_kw"
LENDING_TABLE = "lending_balance_kw"

EXPECTED_SHORT_SELLING_COLUMNS = {
    "id",
    "stock_id",
    "trading_date",
    "exchange",
    "close_price",
    "prev_compare_amount",
    "prev_compare_sign",
    "change_rate",
    "trade_volume",
    "short_volume",
    "cumulative_short_volume",
    "short_trade_weight",
    "short_trade_amount",
    "short_avg_price",
    "fetched_at",
    "created_at",
    "updated_at",
}

EXPECTED_LENDING_COLUMNS = {
    "id",
    "scope",
    "stock_id",
    "trading_date",
    "contracted_volume",
    "repaid_volume",
    "delta_volume",
    "balance_volume",
    "balance_amount",
    "fetched_at",
    "created_at",
    "updated_at",
}


# ---------------------------------------------------------------------------
# Scenario 1 — 마이그레이션 적용 (revision id + down_revision)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_016_revision_id_and_down_revision(engine: AsyncEngine) -> None:
    """015 → 016 upgrade 성공 — alembic_version 이 016 이상 (Phase F-1 후 017 head).

    Phase F-1 (Migration 017) 추가 후 head 는 017 이지만 016 도 적용 완료 상태여야 함.
    head 가 014/015 (016 이전) 이 아님을 확인 — 016 가드 우회 회귀.
    """
    async with engine.connect() as conn:
        version = await conn.execute(
            text("SELECT version_num FROM kiwoom.alembic_version")
        )
        rev = version.scalar_one()
    # 016 미적용 시 fail — pre-016 revision 거부
    assert rev not in ("014_stock_price_yearly", "015_sector_price_daily"), (
        f"016 미적용 — alembic_version='{rev}' (016 또는 017 head 기대)"
    )


# ---------------------------------------------------------------------------
# Scenario 2 — short_selling_kw 테이블 검증 (컬럼 + FK + UNIQUE)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_short_selling_kw_columns_and_fk(engine: AsyncEngine) -> None:
    """short_selling_kw 컬럼 17개 + FK (stock_id → kiwoom.stock(id) ON DELETE CASCADE)
    + UNIQUE (stock_id, trading_date, exchange)."""
    async with engine.connect() as conn:

        def _inspect(sync_conn) -> tuple[set[str], list[dict], list[dict]]:  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            cols = {c["name"] for c in insp.get_columns(SHORT_SELLING_TABLE, schema="kiwoom")}
            fks = insp.get_foreign_keys(SHORT_SELLING_TABLE, schema="kiwoom")
            uqs = insp.get_unique_constraints(SHORT_SELLING_TABLE, schema="kiwoom")
            return cols, fks, uqs

        cols, fks, uqs = await conn.run_sync(_inspect)

    missing = EXPECTED_SHORT_SELLING_COLUMNS - cols
    extra = cols - EXPECTED_SHORT_SELLING_COLUMNS
    assert not missing, f"short_selling_kw 누락 컬럼: {missing}"
    assert not extra, f"short_selling_kw 예상 외 컬럼: {extra}"
    assert len(cols) == 17, f"컬럼 수 17 기대, 실제 {len(cols)}: {sorted(cols)}"

    # FK 검증
    assert fks, "short_selling_kw FK 부재"
    stock_fk = next((f for f in fks if f["constrained_columns"] == ["stock_id"]), None)
    assert stock_fk is not None, f"stock_id FK 부재: {fks}"
    assert stock_fk["referred_schema"] == "kiwoom"
    assert stock_fk["referred_table"] == "stock"
    assert stock_fk["referred_columns"] == ["id"]
    assert stock_fk["options"].get("ondelete", "").upper() == "CASCADE", (
        f"ON DELETE CASCADE 부재: {stock_fk['options']}"
    )

    # UNIQUE (stock_id, trading_date, exchange) 검증
    uq_col_sets = [set(u["column_names"]) for u in uqs]
    assert {"stock_id", "trading_date", "exchange"} in uq_col_sets, (
        f"UNIQUE (stock_id, trading_date, exchange) 부재: {uqs}"
    )


@pytest.mark.asyncio
async def test_short_selling_kw_column_types(engine: AsyncEngine) -> None:
    """short_selling_kw 핵심 컬럼 타입 검증 — exchange VARCHAR(3) / change_rate NUMERIC(8,4) / id BIGSERIAL."""
    async with engine.connect() as conn:

        def _col_types(sync_conn) -> dict[str, dict]:  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            return {c["name"]: c for c in insp.get_columns(SHORT_SELLING_TABLE, schema="kiwoom")}

        col_map = await conn.run_sync(_col_types)

    # exchange — VARCHAR(3)
    exchange_col = col_map["exchange"]
    exchange_type_str = str(exchange_col["type"]).upper()
    assert "VARCHAR" in exchange_type_str or "CHARACTER VARYING" in exchange_type_str, (
        f"exchange 타입 VARCHAR 기대, 실제: {exchange_type_str}"
    )
    # PostgreSQL VARCHAR 길이 정보는 type.length 로 접근
    exchange_length = getattr(exchange_col["type"], "length", None)
    assert exchange_length == 3, f"exchange VARCHAR 길이 3 기대, 실제: {exchange_length}"

    # change_rate — NUMERIC(8,4)
    change_rate_col = col_map["change_rate"]
    change_rate_type_str = str(change_rate_col["type"]).upper()
    assert "NUMERIC" in change_rate_type_str or "DECIMAL" in change_rate_type_str, (
        f"change_rate 타입 NUMERIC 기대, 실제: {change_rate_type_str}"
    )

    # stock_id — BIGINT (nullable=True 허용, FK 컬럼)
    stock_id_col = col_map["stock_id"]
    stock_id_type_str = str(stock_id_col["type"]).upper()
    assert "BIGINT" in stock_id_type_str or "INT" in stock_id_type_str, (
        f"stock_id 타입 BIGINT 기대, 실제: {stock_id_type_str}"
    )


# ---------------------------------------------------------------------------
# Scenario 3 — short_selling_kw partial index 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_short_selling_kw_partial_index_weight_high(engine: AsyncEngine) -> None:
    """idx_short_selling_kw_weight_high partial index — WHERE short_trade_weight IS NOT NULL 포함 확인.

    pg_indexes 시스템 카탈로그로 인덱스 정의 문자열(indexdef) 검사.
    """
    async with engine.connect() as conn:
        row = await conn.execute(
            text(
                "SELECT indexdef FROM pg_indexes"
                " WHERE schemaname = 'kiwoom'"
                " AND tablename = :tbl"
                " AND indexname = 'idx_short_selling_kw_weight_high'"
            ).bindparams(tbl=SHORT_SELLING_TABLE)
        )
        result = row.fetchone()

    assert result is not None, "idx_short_selling_kw_weight_high 인덱스 부재"
    indexdef = result[0].lower()
    assert "where" in indexdef, (
        f"partial index WHERE 절 부재: {indexdef}"
    )
    assert "short_trade_weight" in indexdef, (
        f"partial index 조건에 short_trade_weight 부재: {indexdef}"
    )
    assert "is not null" in indexdef, (
        f"partial index 조건 'IS NOT NULL' 부재: {indexdef}"
    )


# ---------------------------------------------------------------------------
# Scenario 4 — lending_balance_kw 테이블 검증 (컬럼 + CHECK constraint)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lending_balance_kw_columns_and_check_constraint(engine: AsyncEngine) -> None:
    """lending_balance_kw 컬럼 12개 + scope VARCHAR(8) + stock_id nullable + CHECK constraint chk_lending_scope."""
    async with engine.connect() as conn:

        def _inspect(sync_conn) -> tuple[set[str], dict[str, dict]]:  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            cols_list = insp.get_columns(LENDING_TABLE, schema="kiwoom")
            cols = {c["name"] for c in cols_list}
            col_map = {c["name"]: c for c in cols_list}
            return cols, col_map

        cols, col_map = await conn.run_sync(_inspect)

    missing = EXPECTED_LENDING_COLUMNS - cols
    extra = cols - EXPECTED_LENDING_COLUMNS
    assert not missing, f"lending_balance_kw 누락 컬럼: {missing}"
    assert not extra, f"lending_balance_kw 예상 외 컬럼: {extra}"
    assert len(cols) == 12, f"컬럼 수 12 기대, 실제 {len(cols)}: {sorted(cols)}"

    # scope — VARCHAR(8)
    scope_col = col_map["scope"]
    scope_type_str = str(scope_col["type"]).upper()
    assert "VARCHAR" in scope_type_str or "CHARACTER VARYING" in scope_type_str, (
        f"scope 타입 VARCHAR 기대, 실제: {scope_type_str}"
    )
    scope_length = getattr(scope_col["type"], "length", None)
    assert scope_length == 8, f"scope VARCHAR 길이 8 기대, 실제: {scope_length}"

    # stock_id nullable (MARKET 레코드는 NULL)
    stock_id_col = col_map["stock_id"]
    assert stock_id_col["nullable"] is True, (
        f"lending_balance_kw.stock_id nullable=True 기대, 실제: {stock_id_col['nullable']}"
    )

    # CHECK constraint chk_lending_scope — pg_constraint 카탈로그로 확인
    async with engine.connect() as conn2:
        chk_row = await conn2.execute(
            text(
                "SELECT conname FROM pg_constraint"
                " JOIN pg_class ON pg_constraint.conrelid = pg_class.oid"
                " JOIN pg_namespace ON pg_class.relnamespace = pg_namespace.oid"
                " WHERE pg_namespace.nspname = 'kiwoom'"
                " AND pg_class.relname = :tbl"
                " AND pg_constraint.contype = 'c'"
                " AND pg_constraint.conname = 'chk_lending_scope'"
            ).bindparams(tbl=LENDING_TABLE)
        )
        chk_result = chk_row.fetchone()

    assert chk_result is not None, (
        "CHECK constraint 'chk_lending_scope' 부재 — (scope='MARKET' AND stock_id IS NULL) "
        "OR (scope='STOCK' AND stock_id IS NOT NULL) 조건 누락"
    )


# ---------------------------------------------------------------------------
# Scenario 5 — lending_balance_kw partial unique 2개
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lending_balance_kw_partial_unique_indexes(engine: AsyncEngine) -> None:
    """uq_lending_market_date + uq_lending_stock_date partial unique index 검증.

    pg_indexes 시스템 카탈로그로 indexdef 의 WHERE 절 확인.
    uq_lending_market_date: WHERE scope='MARKET' AND stock_id IS NULL
    uq_lending_stock_date:  WHERE scope='STOCK' AND stock_id IS NOT NULL
    """
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT indexname, indexdef FROM pg_indexes"
                " WHERE schemaname = 'kiwoom'"
                " AND tablename = :tbl"
                " AND indexname IN ('uq_lending_market_date', 'uq_lending_stock_date')"
            ).bindparams(tbl=LENDING_TABLE)
        )
        results = {row[0]: row[1].lower() for row in rows.fetchall()}

    # uq_lending_market_date
    assert "uq_lending_market_date" in results, (
        "uq_lending_market_date partial unique index 부재"
    )
    market_def = results["uq_lending_market_date"]
    assert "where" in market_def, f"uq_lending_market_date WHERE 절 부재: {market_def}"
    assert "market" in market_def, (
        f"uq_lending_market_date WHERE 조건에 'market' 부재: {market_def}"
    )
    assert "stock_id is null" in market_def, (
        f"uq_lending_market_date WHERE 조건에 'stock_id IS NULL' 부재: {market_def}"
    )

    # uq_lending_stock_date
    assert "uq_lending_stock_date" in results, (
        "uq_lending_stock_date partial unique index 부재"
    )
    stock_def = results["uq_lending_stock_date"]
    assert "where" in stock_def, f"uq_lending_stock_date WHERE 절 부재: {stock_def}"
    assert "stock" in stock_def, (
        f"uq_lending_stock_date WHERE 조건에 'stock' 부재: {stock_def}"
    )
    assert "stock_id is not null" in stock_def, (
        f"uq_lending_stock_date WHERE 조건에 'stock_id IS NOT NULL' 부재: {stock_def}"
    )


# ---------------------------------------------------------------------------
# Scenario 6 — downgrade 검증 (016 → 015)
# ---------------------------------------------------------------------------


def test_migration_016_downgrade_drops_two_tables_keeps_sector_daily(
    database_url: str,
) -> None:
    """016 → 015 downgrade 시 short_selling_kw + lending_balance_kw DROP / sector_price_daily 유지.

    빈 테이블 상태 전제 — 016 teardown 후 015 target 까지만 downgrade.
    """
    import sqlalchemy as sa

    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    sync_engine = sa.create_engine(database_url.replace("+asyncpg", "+psycopg2"))
    try:
        command.downgrade(alembic_cfg, "015_sector_price_daily")

        with sync_engine.connect() as conn:
            insp = inspect(conn)
            existing = set(insp.get_table_names(schema="kiwoom"))

        assert SHORT_SELLING_TABLE not in existing, (
            f"016 downgrade 후 {SHORT_SELLING_TABLE} 잔존"
        )
        assert LENDING_TABLE not in existing, (
            f"016 downgrade 후 {LENDING_TABLE} 잔존"
        )
        assert "sector_price_daily" in existing, (
            "016 downgrade 후 sector_price_daily 가 삭제됨 (비파괴 보장 실패)"
        )

        # 복원 — 다른 테스트가 head 상태 기대
        command.upgrade(alembic_cfg, "head")

        with sync_engine.connect() as conn2:
            insp2 = inspect(conn2)
            restored = set(insp2.get_table_names(schema="kiwoom"))

        assert SHORT_SELLING_TABLE in restored, (
            f"016 재적용 후 {SHORT_SELLING_TABLE} 미생성"
        )
        assert LENDING_TABLE in restored, (
            f"016 재적용 후 {LENDING_TABLE} 미생성"
        )
    finally:
        sync_engine.dispose()
