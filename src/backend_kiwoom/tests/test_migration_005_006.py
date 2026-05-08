"""Alembic Migration 005 + 006 — kiwoom.stock_price_krx + stock_price_nxt (C-1α).

설계: endpoint-06-ka10081.md § 5.1.

검증:
- 두 테이블 모두 생성
- UNIQUE(stock_id, trading_date, adjusted) 복합키 (KRX/NXT 동일)
- FK stock_id → kiwoom.stock(id) ON DELETE CASCADE (양쪽)
- 2 인덱스 each (idx_*_trading_date / idx_*_stock_id)
- 컬럼 타입 (BIGINT/CHAR(1)/NUMERIC(8,4)/TIMESTAMPTZ)
- server_default — adjusted=true, fetched_at/created_at/updated_at = now()
- downgrade 006 → 005 → 004 멱등성
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.asyncio
async def test_both_price_tables_exist(engine: AsyncEngine) -> None:
    """stock_price_krx + stock_price_nxt 두 테이블 모두 생성."""
    async with engine.connect() as conn:

        def _list_tables(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            return set(insp.get_table_names(schema="kiwoom"))

        tables = await conn.run_sync(_list_tables)

    assert "stock_price_krx" in tables
    assert "stock_price_nxt" in tables


@pytest.mark.asyncio
@pytest.mark.parametrize("table", ["stock_price_krx", "stock_price_nxt"])
async def test_unique_constraint_composite(engine: AsyncEngine, table: str) -> None:
    async with engine.connect() as conn:

        def _check(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            uniques = insp.get_unique_constraints(table, schema="kiwoom")
            unique_idx = insp.get_indexes(table, schema="kiwoom")
            target = {"stock_id", "trading_date", "adjusted"}
            has_uq = any(set(u["column_names"]) == target for u in uniques)
            has_idx = any(
                idx.get("unique") and set(idx.get("column_names", [])) == target
                for idx in unique_idx
            )
            return has_uq or has_idx

        assert await conn.run_sync(_check), f"{table} UNIQUE 부재"


@pytest.mark.asyncio
@pytest.mark.parametrize("table", ["stock_price_krx", "stock_price_nxt"])
async def test_foreign_key_cascade(engine: AsyncEngine, table: str) -> None:
    async with engine.connect() as conn:

        def _check(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            return [
                (fk["constrained_columns"], fk["referred_table"], fk.get("options", {}))
                for fk in insp.get_foreign_keys(table, schema="kiwoom")
            ]

        fks = await conn.run_sync(_check)

    assert any(
        cc == ["stock_id"] and rt == "stock" and opt.get("ondelete", "").upper() == "CASCADE"
        for cc, rt, opt in fks
    ), f"{table} FK CASCADE 부재: {fks}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("table", "expected"),
    [
        ("stock_price_krx", {"idx_price_krx_trading_date", "idx_price_krx_stock_id"}),
        ("stock_price_nxt", {"idx_price_nxt_trading_date", "idx_price_nxt_stock_id"}),
    ],
)
async def test_indexes_created(engine: AsyncEngine, table: str, expected: set[str]) -> None:
    async with engine.connect() as conn:

        def _check(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            return {idx["name"] for idx in insp.get_indexes(table, schema="kiwoom")}

        names = await conn.run_sync(_check)

    assert expected.issubset(names), f"{table} 인덱스 누락: {expected - names}"


@pytest.mark.asyncio
@pytest.mark.parametrize("table", ["stock_price_krx", "stock_price_nxt"])
async def test_columns_types(engine: AsyncEngine, table: str) -> None:
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT column_name, data_type, character_maximum_length, "
                "numeric_precision, numeric_scale "
                "FROM information_schema.columns "
                "WHERE table_schema = 'kiwoom' AND table_name = :tn"
            ).bindparams(tn=table)
        )
        rows = {r[0]: (r[1], r[2], r[3], r[4]) for r in result.fetchall()}

    assert rows["id"][0] == "bigint"
    assert rows["stock_id"][0] == "bigint"
    assert rows["trading_date"][0] == "date"
    assert rows["adjusted"][0] == "boolean"

    for col in (
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "trade_volume",
        "trade_amount",
        "prev_compare_amount",
    ):
        assert rows[col][0] == "bigint", f"{col} BIGINT 부재"

    assert rows["prev_compare_sign"][0] == "character"
    assert rows["prev_compare_sign"][1] == 1

    assert rows["turnover_rate"][0] == "numeric"
    assert rows["turnover_rate"][2] == 8 and rows["turnover_rate"][3] == 4

    for col in ("fetched_at", "created_at", "updated_at"):
        assert rows[col][0] == "timestamp with time zone"


@pytest.mark.asyncio
@pytest.mark.parametrize("table", ["stock_price_krx", "stock_price_nxt"])
async def test_default_values(engine: AsyncEngine, table: str) -> None:
    """adjusted server_default=true + 타임스탬프 default now()."""
    async with engine.connect() as conn, conn.begin():
        # stock 1행 INSERT 후 price 최소 컬럼 INSERT
        await conn.execute(
            text(
                "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code) "
                "VALUES ('TST005', 'test-default', '0')"
            )
        )
        result = await conn.execute(text("SELECT id FROM kiwoom.stock WHERE stock_code = 'TST005'"))
        sid = result.scalar_one()

        await conn.execute(
            text(
                f"INSERT INTO kiwoom.{table} (stock_id, trading_date) "
                "VALUES (:sid, DATE '2025-09-08')"
            ).bindparams(sid=sid)
        )
        result = await conn.execute(
            text(
                f"SELECT adjusted, fetched_at, created_at, updated_at "
                f"FROM kiwoom.{table} WHERE stock_id = :sid"
            ).bindparams(sid=sid)
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] is True
        assert row[1] is not None
        assert row[2] is not None
        assert row[3] is not None
        await conn.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize("table", ["stock_price_krx", "stock_price_nxt"])
async def test_cascade_delete_with_stock(engine: AsyncEngine, table: str) -> None:
    async with engine.connect() as conn, conn.begin():
        await conn.execute(
            text(
                "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code) "
                "VALUES ('TST006', 'cascade-test', '0')"
            )
        )
        result = await conn.execute(text("SELECT id FROM kiwoom.stock WHERE stock_code = 'TST006'"))
        sid = result.scalar_one()

        await conn.execute(
            text(
                f"INSERT INTO kiwoom.{table} (stock_id, trading_date) "
                "VALUES (:sid, DATE '2025-09-08')"
            ).bindparams(sid=sid)
        )

        # CASCADE
        await conn.execute(text("DELETE FROM kiwoom.stock WHERE id = :sid").bindparams(sid=sid))
        result = await conn.execute(
            text(f"SELECT COUNT(*) FROM kiwoom.{table} WHERE stock_id = :sid").bindparams(sid=sid)
        )
        assert result.scalar_one() == 0
        await conn.rollback()


def test_migration_006_downgrade_then_upgrade_idempotent(database_url: str) -> None:
    """빈 테이블에서 downgrade 006 → 005 → 004 → upgrade head 멱등."""
    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    command.downgrade(alembic_cfg, "004_kiwoom_stock_fundamental")
    command.upgrade(alembic_cfg, "head")
