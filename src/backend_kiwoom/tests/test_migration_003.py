"""Alembic Migration 003 양방향 검증 — kiwoom.stock 테이블.

검증:
- upgrade head 후 stock 테이블 + UNIQUE(stock_code) + 4 인덱스 존재
- 빈 DB 에서 downgrade 003 → 002 가능 (stock 테이블 drop)
- 재 upgrade head 가능 (멱등성)
- 컬럼 타입 검증 (BIGINT/VARCHAR/BOOLEAN/DATE/TIMESTAMPTZ)
- partial 인덱스 (idx_stock_nxt_enable / idx_stock_active / idx_stock_up_name) 의 WHERE 조건
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.asyncio
async def test_migration_creates_stock_table(engine: AsyncEngine) -> None:
    """kiwoom.stock 테이블 존재."""
    async with engine.connect() as conn:

        def _list_tables(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            return set(insp.get_table_names(schema="kiwoom"))

        tables = await conn.run_sync(_list_tables)

    assert "stock" in tables


@pytest.mark.asyncio
async def test_stock_unique_constraint_stock_code(engine: AsyncEngine) -> None:
    """UNIQUE(stock_code) 단일키 — sector 의 복합키와 차이."""
    async with engine.connect() as conn:

        def _check(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            uniques = insp.get_unique_constraints("stock", schema="kiwoom")
            unique_idx = insp.get_indexes("stock", schema="kiwoom")
            has_uq = any(set(u["column_names"]) == {"stock_code"} for u in uniques)
            has_idx = any(
                idx.get("unique") and set(idx.get("column_names", [])) == {"stock_code"} for idx in unique_idx
            )
            return has_uq or has_idx

        assert await conn.run_sync(_check), "stock UNIQUE(stock_code) 부재"


@pytest.mark.asyncio
async def test_stock_indexes_created(engine: AsyncEngine) -> None:
    """4 인덱스 존재 — market_code / nxt_enable partial / active partial / up_name partial."""
    async with engine.connect() as conn:

        def _check(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            return {idx["name"] for idx in insp.get_indexes("stock", schema="kiwoom")}

        names = await conn.run_sync(_check)

    assert "idx_stock_market_code" in names
    assert "idx_stock_nxt_enable" in names
    assert "idx_stock_active" in names
    assert "idx_stock_up_name" in names


@pytest.mark.asyncio
async def test_stock_partial_indexes_have_where_clause(engine: AsyncEngine) -> None:
    """partial 인덱스의 WHERE 조건이 pg_indexes 에 노출되는지 — 성능 핵심."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'kiwoom' AND tablename = 'stock'
                """
            )
        )
        rows = {r[0]: r[1] for r in result.fetchall()}

    nxt_def = rows["idx_stock_nxt_enable"]
    active_def = rows["idx_stock_active"]
    up_name_def = rows["idx_stock_up_name"]

    # PostgreSQL 정규화 — 'true' lowercase / 'IS NOT NULL' 체크
    assert "nxt_enable = true" in nxt_def.lower()
    assert "is_active = true" in active_def.lower()
    assert "up_name is not null" in up_name_def.lower()


@pytest.mark.asyncio
async def test_stock_columns_types(engine: AsyncEngine) -> None:
    """주요 컬럼 타입 검증."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT column_name, data_type, character_maximum_length
                FROM information_schema.columns
                WHERE table_schema = 'kiwoom' AND table_name = 'stock'
                """
            )
        )
        rows = {r[0]: (r[1], r[2]) for r in result.fetchall()}

    # 길이 체크
    assert rows["stock_code"][0] == "character varying"
    assert rows["stock_code"][1] == 20
    assert rows["stock_name"][1] == 40
    assert rows["market_code"][1] == 4
    assert rows["state"][1] == 255  # 1R M-1 — 키움 다중값 상태 안전 마진
    assert rows["order_warning"][1] == 1

    # 타입 체크
    assert rows["list_count"][0] == "bigint"
    assert rows["last_price"][0] == "bigint"
    assert rows["listed_date"][0] == "date"
    assert rows["nxt_enable"][0] == "boolean"
    assert rows["is_active"][0] == "boolean"
    assert rows["fetched_at"][0] == "timestamp with time zone"
    assert rows["created_at"][0] == "timestamp with time zone"
    assert rows["updated_at"][0] == "timestamp with time zone"


@pytest.mark.asyncio
async def test_stock_default_values(engine: AsyncEngine) -> None:
    """server_default 검증 — order_warning='0', nxt_enable=false, is_active=true."""
    async with engine.connect() as conn, conn.begin():
        # 최소 컬럼만 INSERT — server_default 가 적용되는지
        await conn.execute(
            text("INSERT INTO kiwoom.stock (stock_code, stock_name, market_code) VALUES ('TST001', 'test', '0')")
        )
        result = await conn.execute(
            text("SELECT order_warning, nxt_enable, is_active FROM kiwoom.stock WHERE stock_code = 'TST001'")
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "0"
        assert row[1] is False
        assert row[2] is True
        await conn.rollback()


def test_migration_003_downgrade_then_upgrade_idempotent(database_url: str) -> None:
    """빈 stock 테이블에서 downgrade 003 → upgrade head 멱등성."""
    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    command.downgrade(alembic_cfg, "002_kiwoom_sector")
    command.upgrade(alembic_cfg, "head")
