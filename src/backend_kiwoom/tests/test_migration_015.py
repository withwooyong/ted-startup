"""Alembic Migration 015 — kiwoom.sector_price_daily 신규 (D-1).

설계: endpoint-13-ka20006.md § 12.
chunk = D-1, plan doc § 12 참조.

014 (yearly_krx/nxt) 패턴 1:1 응용. sector_id FK → kiwoom.sector(id).

검증:
- sector_price_daily 테이블 생성
- 컬럼 (sector_id + 4 centi BIGINT + volume/amount BIGINT + trading_date + timestamps)
- UNIQUE (sector_id, trading_date)
- FK sector_id → kiwoom.sector(id) ON DELETE CASCADE
- 인덱스 (trading_date / sector_id)
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

SECTOR_DAILY_TABLE = "sector_price_daily"

EXPECTED_COLUMNS = {
    "id",
    "sector_id",
    "trading_date",
    "open_index_centi",
    "high_index_centi",
    "low_index_centi",
    "close_index_centi",
    "trade_volume",
    "trade_amount",
    "fetched_at",
    "created_at",
    "updated_at",
}


@pytest.mark.asyncio
async def test_sector_price_daily_table_exists_after_upgrade(engine: AsyncEngine) -> None:
    """015 head 적용 후 sector_price_daily 테이블 존재 + 12 컬럼 일치."""
    async with engine.connect() as conn:

        def _list_columns(sync_conn) -> set[str]:  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            return {c["name"] for c in insp.get_columns(SECTOR_DAILY_TABLE, schema="kiwoom")}

        cols = await conn.run_sync(_list_columns)
        missing = EXPECTED_COLUMNS - cols
        extra = cols - EXPECTED_COLUMNS
        assert not missing, f"누락 컬럼: {missing}"
        assert not extra, f"예상 외 컬럼: {extra}"
        assert len(cols) == 12, f"컬럼 수 12 기대, 실제 {len(cols)}: {sorted(cols)}"


@pytest.mark.asyncio
async def test_sector_price_daily_unique_and_indexes(engine: AsyncEngine) -> None:
    """UNIQUE (sector_id, trading_date) + 인덱스 (trading_date / sector_id)."""
    async with engine.connect() as conn:

        def _check_table(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            uqs = insp.get_unique_constraints(SECTOR_DAILY_TABLE, schema="kiwoom")
            idxs = insp.get_indexes(SECTOR_DAILY_TABLE, schema="kiwoom")
            return uqs, idxs

        uqs, idxs = await conn.run_sync(_check_table)

        uq_cols = next((set(u["column_names"]) for u in uqs), set())
        assert uq_cols == {"sector_id", "trading_date"}, (
            f"UNIQUE (sector_id, trading_date) 부재: {uqs}"
        )

        idx_names = {i["name"] for i in idxs}
        assert "idx_sector_price_daily_trading_date" in idx_names, (
            f"trading_date 인덱스 부재: {idx_names}"
        )
        assert "idx_sector_price_daily_sector_id" in idx_names, (
            f"sector_id 인덱스 부재: {idx_names}"
        )


@pytest.mark.asyncio
async def test_sector_price_daily_fk_cascade(engine: AsyncEngine) -> None:
    """FK sector_id → kiwoom.sector(id) ON DELETE CASCADE."""
    async with engine.connect() as conn:

        def _fk(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            return insp.get_foreign_keys(SECTOR_DAILY_TABLE, schema="kiwoom")

        fks = await conn.run_sync(_fk)
        assert fks, "FK 부재"
        fk = fks[0]
        assert fk["constrained_columns"] == ["sector_id"]
        assert fk["referred_schema"] == "kiwoom"
        assert fk["referred_table"] == "sector"
        assert fk["referred_columns"] == ["id"]
        assert fk["options"].get("ondelete", "").upper() == "CASCADE", (
            f"ON DELETE CASCADE 부재: {fk['options']}"
        )


def test_migration_015_downgrade_with_data_raises(database_url: str) -> None:
    """downgrade 가드 — row 1건 이상이면 RAISE.

    head 상태에서 sector + sector_price_daily row 삽입 후 015 → 014 downgrade 시도 →
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
                    "INSERT INTO kiwoom.sector (market_code, sector_code, sector_name) "
                    "VALUES ('0', 'TST015', 'downgrade-guard')"
                )
            )
            sid = conn.execute(
                text("SELECT id FROM kiwoom.sector WHERE sector_code = 'TST015'")
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO kiwoom.sector_price_daily "
                    "(sector_id, trading_date) "
                    "VALUES (:sid, DATE '2025-01-02')"
                ).bindparams(sid=sid)
            )

        with pytest.raises(DBAPIError):
            command.downgrade(alembic_cfg, "014_stock_price_yearly")
    finally:
        try:
            with sync_engine.begin() as conn:
                conn.execute(text("DELETE FROM kiwoom.sector WHERE sector_code = 'TST015'"))
        except Exception:
            pass
        with sync_engine.connect() as conn:
            head_rev = conn.execute(
                text("SELECT version_num FROM kiwoom.alembic_version")
            ).scalar_one()
        sync_engine.dispose()
        assert head_rev != "014_stock_price_yearly", (
            f"015 가드 우회 — alembic_version 이 downgrade target 까지 진행됨: {head_rev}."
        )


def test_migration_015_downgrade_then_upgrade(database_url: str) -> None:
    """빈 테이블에서 015 → 014 downgrade → head upgrade 라운드트립 — 멱등성.

    Phase E (016) 추가 이후: `-1` 은 016→015 가 되어 sector_price_daily 가 그대로 남음.
    `014_stock_price_yearly` 타깃으로 명시 — 015 가 정말 제거되는지 검증.
    """
    import sqlalchemy as sa

    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    sync_engine = sa.create_engine(database_url.replace("+asyncpg", "+psycopg2"))
    try:
        command.downgrade(alembic_cfg, "014_stock_price_yearly")

        with sync_engine.connect() as conn:
            insp = inspect(conn)
            existing = set(insp.get_table_names(schema="kiwoom"))
        assert SECTOR_DAILY_TABLE not in existing, f"015 downgrade 후 {SECTOR_DAILY_TABLE} 잔존"

        command.upgrade(alembic_cfg, "head")

        with sync_engine.connect() as conn:
            insp = inspect(conn)
            after_upgrade = set(insp.get_table_names(schema="kiwoom"))
        assert SECTOR_DAILY_TABLE in after_upgrade, f"015 재적용 후 {SECTOR_DAILY_TABLE} 미생성"
    finally:
        sync_engine.dispose()
