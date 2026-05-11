"""Alembic Migration 014 — kiwoom.stock_price_yearly_{krx,nxt} 신규 (C-4).

설계: endpoint-09-ka10094.md § 12.

011 (월봉 KRX) + 012 (월봉 NXT) 패턴 1:1 응용. 컬럼 구조 4 테이블 동일 (`_DailyOhlcvMixin`).

검증:
- yearly_krx / yearly_nxt 테이블 생성
- 11 도메인 컬럼 + 3 메타 (id + stock_id + trading_date) + adjusted + 3 timestamp
- UNIQUE (stock_id, trading_date, adjusted)
- FK stock_id → kiwoom.stock(id) ON DELETE CASCADE
- 인덱스 (trading_date / stock_id)
- DOWNGRADE 가드 — row 1건 이상이면 RAISE
- 멱등 라운드트립
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

YEARLY_TABLES = ("stock_price_yearly_krx", "stock_price_yearly_nxt")
EXPECTED_COLUMNS = {
    # OHLCV mixin (11)
    "id",
    "stock_id",
    "trading_date",
    "adjusted",
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "trade_volume",
    "trade_amount",
    "prev_compare_amount",
    "prev_compare_sign",
    "turnover_rate",
    # timestamps
    "fetched_at",
    "created_at",
    "updated_at",
}


@pytest.mark.asyncio
async def test_yearly_tables_exist_after_upgrade(engine: AsyncEngine) -> None:
    """014 head 적용 후 yearly_krx + yearly_nxt 테이블 둘 다 존재 + 16 컬럼 일치."""
    async with engine.connect() as conn:

        def _list_columns(sync_conn, table_name: str):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            return {c["name"] for c in insp.get_columns(table_name, schema="kiwoom")}

        for table in YEARLY_TABLES:
            cols = await conn.run_sync(lambda c, t=table: _list_columns(c, t))
            missing = EXPECTED_COLUMNS - cols
            extra = cols - EXPECTED_COLUMNS
            assert not missing, f"{table} 누락 컬럼: {missing}"
            assert not extra, f"{table} 예상 외 컬럼: {extra}"
            assert len(cols) == 16, f"{table} 컬럼 수 16 기대, 실제 {len(cols)}: {sorted(cols)}"


@pytest.mark.asyncio
async def test_yearly_tables_unique_and_indexes(engine: AsyncEngine) -> None:
    """UNIQUE (stock_id, trading_date, adjusted) + 인덱스 (trading_date / stock_id)."""
    async with engine.connect() as conn:

        def _check_table(sync_conn, table_name: str):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            uqs = insp.get_unique_constraints(table_name, schema="kiwoom")
            idxs = insp.get_indexes(table_name, schema="kiwoom")
            return uqs, idxs

        for table in YEARLY_TABLES:
            uqs, idxs = await conn.run_sync(lambda c, t=table: _check_table(c, t))

            uq_cols = next((set(u["column_names"]) for u in uqs), set())
            assert uq_cols == {"stock_id", "trading_date", "adjusted"}, (
                f"{table} UNIQUE (stock_id, trading_date, adjusted) 부재: {uqs}"
            )

            idx_names = {i["name"] for i in idxs}
            # 인덱스 명명 — 011/012 패턴 (`idx_price_yearly_{krx,nxt}_{trading_date,stock_id}`)
            short = table.replace("stock_price_", "")
            assert f"idx_price_{short}_trading_date" in idx_names, f"{table} trading_date 인덱스 부재: {idx_names}"
            assert f"idx_price_{short}_stock_id" in idx_names, f"{table} stock_id 인덱스 부재: {idx_names}"


@pytest.mark.asyncio
async def test_yearly_tables_fk_cascade(engine: AsyncEngine) -> None:
    """FK stock_id → kiwoom.stock(id) ON DELETE CASCADE."""
    async with engine.connect() as conn:

        def _fk(sync_conn, table_name: str):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            return insp.get_foreign_keys(table_name, schema="kiwoom")

        for table in YEARLY_TABLES:
            fks = await conn.run_sync(lambda c, t=table: _fk(c, t))
            assert fks, f"{table} FK 부재"
            fk = fks[0]
            assert fk["constrained_columns"] == ["stock_id"]
            assert fk["referred_schema"] == "kiwoom"
            assert fk["referred_table"] == "stock"
            assert fk["referred_columns"] == ["id"]
            assert fk["options"].get("ondelete", "").upper() == "CASCADE", (
                f"{table} ON DELETE CASCADE 부재: {fk['options']}"
            )


def test_migration_014_downgrade_with_data_raises(database_url: str) -> None:
    """downgrade 가드 — 011/012/013 동일 패턴. row 1건 이상이면 RAISE.

    head 상태에서 stock + stock_price_yearly_krx row 삽입 후 014 → 013 downgrade 시도 →
    DBAPIError (PostgreSQL RAISE EXCEPTION) 발생해야 함.
    """
    import sqlalchemy as sa

    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    sync_engine = sa.create_engine(database_url.replace("+asyncpg", "+psycopg2"))
    try:
        with sync_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code) "
                    "VALUES ('TST014G', 'downgrade-guard', '0')"
                )
            )
            sid = conn.execute(text("SELECT id FROM kiwoom.stock WHERE stock_code = 'TST014G'")).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO kiwoom.stock_price_yearly_krx "
                    "(stock_id, trading_date, adjusted) "
                    "VALUES (:sid, DATE '2025-01-02', TRUE)"
                ).bindparams(sid=sid)
            )

        with pytest.raises(DBAPIError):
            command.downgrade(alembic_cfg, "013_drop_daily_flow_dup_2")
    finally:
        try:
            with sync_engine.begin() as conn:
                conn.execute(text("DELETE FROM kiwoom.stock WHERE stock_code = 'TST014G'"))
        except Exception:
            pass
        with sync_engine.begin() as conn:
            head_rev = conn.execute(text("SELECT version_num FROM kiwoom.alembic_version")).scalar_one()
        sync_engine.dispose()
        # transactional DDL rollback — head 유지. 핵심: downgrade target 미도달 검증.
        assert head_rev != "013_drop_daily_flow_dup_2", (
            f"014 가드 우회 — alembic_version 이 downgrade target 까지 진행됨: {head_rev}. "
            "DO $$ 블록 RAISE 후 trans rollback 가정 위반."
        )


def test_migration_014_downgrade_then_upgrade(database_url: str) -> None:
    """빈 테이블에서 014 → 013 downgrade → head upgrade 라운드트립 — 멱등성."""
    import sqlalchemy as sa

    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    sync_engine = sa.create_engine(database_url.replace("+asyncpg", "+psycopg2"))
    try:
        command.downgrade(alembic_cfg, "013_drop_daily_flow_dup_2")

        with sync_engine.connect() as conn:
            insp = inspect(conn)
            existing = set(insp.get_table_names(schema="kiwoom"))
        for table in YEARLY_TABLES:
            assert table not in existing, f"013 downgrade 후 {table} 잔존"

        command.upgrade(alembic_cfg, "head")

        with sync_engine.connect() as conn:
            insp = inspect(conn)
            after_upgrade = set(insp.get_table_names(schema="kiwoom"))
        for table in YEARLY_TABLES:
            assert table in after_upgrade, f"014 재적용 후 {table} 미생성"
    finally:
        sync_engine.dispose()
