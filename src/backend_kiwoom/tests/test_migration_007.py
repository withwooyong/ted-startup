"""Alembic Migration 007 — kiwoom.stock_daily_flow (C-2α).

설계: endpoint-10-ka10086.md § 5.1.

검증 (conftest 가 head 까지 적용 — C-2γ Migration 008 반영 후 상태):
- 테이블 생성 + 10 도메인 컬럼 (신용 2 + 투자자별 4 + 외인 4, 008 D-E 중복 3 DROP 후) + 메타 5
- UNIQUE(stock_id, trading_date, exchange)
- FK stock_id → kiwoom.stock(id) ON DELETE CASCADE
- 인덱스 3개 (trading_date / stock_id / exchange)
- 컬럼 타입 (BIGINT / NUMERIC(8,4) / VARCHAR(4) / CHAR(1) / TIMESTAMPTZ)
- server_default — fetched_at/created_at/updated_at = now()
- exchange CHECK 또는 enum 검증 (KRX/NXT)
- downgrade 멱등성 (head → 006 → head 라운드트립)
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.asyncio
async def test_stock_daily_flow_table_exists(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:

        def _list_tables(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            return set(insp.get_table_names(schema="kiwoom"))

        tables = await conn.run_sync(_list_tables)

    assert "stock_daily_flow" in tables


@pytest.mark.asyncio
async def test_unique_constraint_composite(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:

        def _check(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            uniques = insp.get_unique_constraints("stock_daily_flow", schema="kiwoom")
            indexes = insp.get_indexes("stock_daily_flow", schema="kiwoom")
            target = {"stock_id", "trading_date", "exchange"}
            has_uq = any(set(u["column_names"]) == target for u in uniques)
            has_idx = any(
                idx.get("unique") and set(idx.get("column_names", [])) == target
                for idx in indexes
            )
            return has_uq or has_idx

        assert await conn.run_sync(_check)


@pytest.mark.asyncio
async def test_foreign_key_cascade(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:

        def _check(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            return [
                (fk["constrained_columns"], fk["referred_table"], fk.get("options", {}))
                for fk in insp.get_foreign_keys("stock_daily_flow", schema="kiwoom")
            ]

        fks = await conn.run_sync(_check)

    assert any(
        cc == ["stock_id"] and rt == "stock" and opt.get("ondelete", "").upper() == "CASCADE"
        for cc, rt, opt in fks
    )


@pytest.mark.asyncio
async def test_indexes_created(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:

        def _check(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            return {idx["name"] for idx in insp.get_indexes("stock_daily_flow", schema="kiwoom")}

        names = await conn.run_sync(_check)

    expected = {
        "idx_daily_flow_trading_date",
        "idx_daily_flow_stock_id",
        "idx_daily_flow_exchange",
    }
    assert expected.issubset(names), f"누락: {expected - names}"


@pytest.mark.asyncio
async def test_columns_types(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT column_name, data_type, character_maximum_length, "
                "numeric_precision, numeric_scale "
                "FROM information_schema.columns "
                "WHERE table_schema = 'kiwoom' AND table_name = 'stock_daily_flow'"
            )
        )
        rows = {r[0]: (r[1], r[2], r[3], r[4]) for r in result.fetchall()}

    # 메타 / FK
    assert rows["id"][0] == "bigint"
    assert rows["stock_id"][0] == "bigint"
    assert rows["trading_date"][0] == "date"

    # exchange / indc_mode
    assert rows["exchange"][0] == "character varying"
    assert rows["exchange"][1] == 4
    assert rows["indc_mode"][0] == "character"
    assert rows["indc_mode"][1] == 1

    # BIGINT 6개 (투자자별 4 + 외인 BIGINT 2 — foreign_rate 는 NUMERIC, foreign_weight 는 C-2δ DROP)
    # C-2γ Migration 008: D-E 중복 3 컬럼 DROP. C-2δ Migration 013: C/E 중복 2 컬럼 DROP.
    # conftest 가 head 까지 적용하므로 013 적용 후 상태 검증.
    bigint_cols = [
        "individual_net",
        "institutional_net",
        "foreign_brokerage_net",
        "program_net",
        "foreign_volume",
        "foreign_holdings",
    ]
    for col in bigint_cols:
        assert rows[col][0] == "bigint", f"{col} BIGINT 부재"

    # C-2γ — DROP 대상 3 컬럼은 head 적용 후 부재해야 함
    for dropped in ("individual_net_purchase", "institutional_net_purchase", "foreign_net_purchase"):
        assert dropped not in rows, f"{dropped} 가 008 적용 후에도 남아 있음"

    # C-2δ — DROP 대상 2 컬럼은 head 적용 후 부재해야 함
    for dropped in ("credit_balance_rate", "foreign_weight"):
        assert dropped not in rows, f"{dropped} 가 013 적용 후에도 남아 있음"

    # NUMERIC(8,4) 2개 (잔존 신용 1 + 외인비 1 — credit_balance_rate / foreign_weight 는 C-2δ DROP)
    numeric_cols = ["credit_rate", "foreign_rate"]
    for col in numeric_cols:
        assert rows[col][0] == "numeric"
        assert rows[col][2] == 8 and rows[col][3] == 4, f"{col} NUMERIC(8,4) 부재"

    # 타임스탬프
    for col in ("fetched_at", "created_at", "updated_at"):
        assert rows[col][0] == "timestamp with time zone"


@pytest.mark.asyncio
async def test_server_defaults_now_on_insert(engine: AsyncEngine) -> None:
    """fetched_at/created_at/updated_at default now()."""
    async with engine.connect() as conn, conn.begin():
        await conn.execute(
            text(
                "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code) "
                "VALUES ('TST007', 'flow-default', '0')"
            )
        )
        result = await conn.execute(text("SELECT id FROM kiwoom.stock WHERE stock_code = 'TST007'"))
        sid = result.scalar_one()

        await conn.execute(
            text(
                "INSERT INTO kiwoom.stock_daily_flow "
                "(stock_id, trading_date, exchange, indc_mode) "
                "VALUES (:sid, DATE '2025-09-08', 'KRX', '0')"
            ).bindparams(sid=sid)
        )
        result = await conn.execute(
            text(
                "SELECT fetched_at, created_at, updated_at "
                "FROM kiwoom.stock_daily_flow WHERE stock_id = :sid"
            ).bindparams(sid=sid)
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] is not None
        assert row[1] is not None
        assert row[2] is not None
        await conn.rollback()


@pytest.mark.asyncio
async def test_cascade_delete_with_stock(engine: AsyncEngine) -> None:
    async with engine.connect() as conn, conn.begin():
        await conn.execute(
            text(
                "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code) "
                "VALUES ('TST008', 'cascade', '0')"
            )
        )
        result = await conn.execute(text("SELECT id FROM kiwoom.stock WHERE stock_code = 'TST008'"))
        sid = result.scalar_one()

        await conn.execute(
            text(
                "INSERT INTO kiwoom.stock_daily_flow "
                "(stock_id, trading_date, exchange, indc_mode) "
                "VALUES (:sid, DATE '2025-09-08', 'KRX', '0')"
            ).bindparams(sid=sid)
        )

        await conn.execute(text("DELETE FROM kiwoom.stock WHERE id = :sid").bindparams(sid=sid))
        result = await conn.execute(
            text(
                "SELECT COUNT(*) FROM kiwoom.stock_daily_flow WHERE stock_id = :sid"
            ).bindparams(sid=sid)
        )
        assert result.scalar_one() == 0
        await conn.rollback()


def test_migration_007_downgrade_then_upgrade_idempotent(database_url: str) -> None:
    """downgrade 007 → 006 → upgrade head 멱등."""
    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    command.downgrade(alembic_cfg, "006_kiwoom_stock_price_nxt")
    command.upgrade(alembic_cfg, "head")
