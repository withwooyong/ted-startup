"""Alembic Migration 009-012 — kiwoom.stock_price_{weekly,monthly}_{krx,nxt} (C-3α).

설계: phase-c-3-weekly-monthly-ohlcv.md § 3.1 + endpoint-07-ka10082.md § 5.1 + endpoint-08-ka10083.md § 5.1.

검증:
- 4 테이블 모두 생성 (weekly_krx, weekly_nxt, monthly_krx, monthly_nxt)
- UNIQUE(stock_id, trading_date, adjusted) 복합키 (4 테이블 동일)
- FK stock_id → kiwoom.stock(id) ON DELETE CASCADE (4 테이블)
- 2 인덱스 each (idx_*_trading_date / idx_*_stock_id)
- 컬럼 타입 (BIGINT / CHAR(1) / NUMERIC(8,4) / TIMESTAMPTZ) — _DailyOhlcvMixin 동일
- server_default — adjusted=true, fetched_at/created_at/updated_at = now()
- downgrade 012 → 011 → 010 → 009 → 008 멱등성 (H-1 검증)

ka10081 의 test_migration_005_006.py 와 같은 패턴 — 4 테이블 parametrize.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

_PERIODIC_TABLES = (
    "stock_price_weekly_krx",
    "stock_price_weekly_nxt",
    "stock_price_monthly_krx",
    "stock_price_monthly_nxt",
)


@pytest.mark.asyncio
async def test_all_periodic_tables_exist(engine: AsyncEngine) -> None:
    """4 테이블 모두 생성."""
    async with engine.connect() as conn:

        def _list_tables(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            return set(insp.get_table_names(schema="kiwoom"))

        tables = await conn.run_sync(_list_tables)

    for t in _PERIODIC_TABLES:
        assert t in tables, f"테이블 부재: {t}"


@pytest.mark.asyncio
@pytest.mark.parametrize("table", _PERIODIC_TABLES)
async def test_unique_constraint_composite(engine: AsyncEngine, table: str) -> None:
    async with engine.connect() as conn:

        def _check(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            uniques = insp.get_unique_constraints(table, schema="kiwoom")
            unique_idx = insp.get_indexes(table, schema="kiwoom")
            target = {"stock_id", "trading_date", "adjusted"}
            has_uq = any(set(u["column_names"]) == target for u in uniques)
            has_idx = any(idx.get("unique") and set(idx.get("column_names", [])) == target for idx in unique_idx)
            return has_uq or has_idx

        assert await conn.run_sync(_check), f"{table} UNIQUE(stock_id, trading_date, adjusted) 부재"


@pytest.mark.asyncio
@pytest.mark.parametrize("table", _PERIODIC_TABLES)
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
        cc == ["stock_id"] and rt == "stock" and opt.get("ondelete", "").upper() == "CASCADE" for cc, rt, opt in fks
    ), f"{table} FK CASCADE 부재: {fks}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("table", "expected"),
    [
        (
            "stock_price_weekly_krx",
            {"idx_price_weekly_krx_trading_date", "idx_price_weekly_krx_stock_id"},
        ),
        (
            "stock_price_weekly_nxt",
            {"idx_price_weekly_nxt_trading_date", "idx_price_weekly_nxt_stock_id"},
        ),
        (
            "stock_price_monthly_krx",
            {"idx_price_monthly_krx_trading_date", "idx_price_monthly_krx_stock_id"},
        ),
        (
            "stock_price_monthly_nxt",
            {"idx_price_monthly_nxt_trading_date", "idx_price_monthly_nxt_stock_id"},
        ),
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
@pytest.mark.parametrize("table", _PERIODIC_TABLES)
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
        assert rows[col][0] == "bigint", f"{table}.{col} BIGINT 부재"

    assert rows["prev_compare_sign"][0] == "character"
    assert rows["prev_compare_sign"][1] == 1

    assert rows["turnover_rate"][0] == "numeric"
    assert rows["turnover_rate"][2] == 8 and rows["turnover_rate"][3] == 4

    for col in ("fetched_at", "created_at", "updated_at"):
        assert rows[col][0] == "timestamp with time zone"


@pytest.mark.asyncio
@pytest.mark.parametrize("table", _PERIODIC_TABLES)
async def test_default_values(engine: AsyncEngine, table: str) -> None:
    """adjusted server_default=true + 타임스탬프 default now()."""
    async with engine.connect() as conn, conn.begin():
        await conn.execute(
            text(
                "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code) "
                "VALUES ('TST090', 'periodic-default', '0')"
            )
        )
        result = await conn.execute(text("SELECT id FROM kiwoom.stock WHERE stock_code = 'TST090'"))
        sid = result.scalar_one()

        await conn.execute(
            text(f"INSERT INTO kiwoom.{table} (stock_id, trading_date) VALUES (:sid, DATE '2025-09-01')").bindparams(
                sid=sid
            )
        )
        result = await conn.execute(
            text(
                f"SELECT adjusted, fetched_at, created_at, updated_at FROM kiwoom.{table} WHERE stock_id = :sid"
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
@pytest.mark.parametrize("table", _PERIODIC_TABLES)
async def test_cascade_delete_with_stock(engine: AsyncEngine, table: str) -> None:
    """stock 삭제 시 4 periodic 테이블 모두 CASCADE."""
    async with engine.connect() as conn, conn.begin():
        await conn.execute(
            text(
                "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code) "
                "VALUES ('TST091', 'periodic-cascade', '0')"
            )
        )
        result = await conn.execute(text("SELECT id FROM kiwoom.stock WHERE stock_code = 'TST091'"))
        sid = result.scalar_one()

        await conn.execute(
            text(f"INSERT INTO kiwoom.{table} (stock_id, trading_date) VALUES (:sid, DATE '2025-09-01')").bindparams(
                sid=sid
            )
        )

        await conn.execute(text("DELETE FROM kiwoom.stock WHERE id = :sid").bindparams(sid=sid))
        result = await conn.execute(
            text(f"SELECT COUNT(*) FROM kiwoom.{table} WHERE stock_id = :sid").bindparams(sid=sid)
        )
        assert result.scalar_one() == 0
        await conn.rollback()


def test_migration_012_downgrade_then_upgrade_idempotent(database_url: str) -> None:
    """빈 테이블에서 downgrade 012 → 011 → 010 → 009 → 008 → upgrade head 멱등 (H-1)."""
    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    command.downgrade(alembic_cfg, "008_drop_daily_flow_dup_columns")
    command.upgrade(alembic_cfg, "head")
