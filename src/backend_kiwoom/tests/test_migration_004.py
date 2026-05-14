"""Alembic Migration 004 양방향 검증 — kiwoom.stock_fundamental 테이블.

검증:
- upgrade head 후 stock_fundamental 테이블 + UNIQUE(stock_id, asof_date, exchange) + 2 인덱스 존재
- FK stock_id → kiwoom.stock(id) ON DELETE CASCADE
- 빈 DB 에서 downgrade 004 → 003 가능 (테이블 drop)
- 재 upgrade head 가능 (멱등성)
- 컬럼 타입 검증 (BIGINT/NUMERIC/DATE/TIMESTAMPTZ/CHAR)
- A/B/C/D/E 5 카테고리 + fundamental_hash + 타임스탬프 — 총 ~50 컬럼

설계: endpoint-05-ka10001.md § 5.1.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.asyncio
async def test_migration_creates_stock_fundamental_table(engine: AsyncEngine) -> None:
    """kiwoom.stock_fundamental 테이블 존재."""
    async with engine.connect() as conn:

        def _list_tables(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            return set(insp.get_table_names(schema="kiwoom"))

        tables = await conn.run_sync(_list_tables)

    assert "stock_fundamental" in tables


@pytest.mark.asyncio
async def test_stock_fundamental_unique_constraint_composite(engine: AsyncEngine) -> None:
    """UNIQUE(stock_id, asof_date, exchange) 복합키 — 같은 종목/일자/거래소 1행."""
    async with engine.connect() as conn:

        def _check(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            uniques = insp.get_unique_constraints("stock_fundamental", schema="kiwoom")
            unique_idx = insp.get_indexes("stock_fundamental", schema="kiwoom")
            target = {"stock_id", "asof_date", "exchange"}
            has_uq = any(set(u["column_names"]) == target for u in uniques)
            has_idx = any(
                idx.get("unique") and set(idx.get("column_names", [])) == target for idx in unique_idx
            )
            return has_uq or has_idx

        assert await conn.run_sync(_check), "stock_fundamental UNIQUE(stock_id, asof_date, exchange) 부재"


@pytest.mark.asyncio
async def test_stock_fundamental_foreign_key_cascade(engine: AsyncEngine) -> None:
    """FK stock_id → kiwoom.stock(id) ON DELETE CASCADE."""
    async with engine.connect() as conn:

        def _check(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            fks = insp.get_foreign_keys("stock_fundamental", schema="kiwoom")
            return [
                (fk["constrained_columns"], fk["referred_schema"], fk["referred_table"], fk.get("options", {}))
                for fk in fks
            ]

        fks = await conn.run_sync(_check)

    assert any(
        cc == ["stock_id"] and rs == "kiwoom" and rt == "stock" and opt.get("ondelete", "").upper() == "CASCADE"
        for cc, rs, rt, opt in fks
    ), f"FK stock_id → kiwoom.stock(id) ON DELETE CASCADE 부재: {fks}"


@pytest.mark.asyncio
async def test_stock_fundamental_indexes_created(engine: AsyncEngine) -> None:
    """2 인덱스 — asof_date / stock_id."""
    async with engine.connect() as conn:

        def _check(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            return {idx["name"] for idx in insp.get_indexes("stock_fundamental", schema="kiwoom")}

        names = await conn.run_sync(_check)

    assert "idx_fundamental_asof_date" in names
    assert "idx_fundamental_stock_id" in names


@pytest.mark.asyncio
async def test_stock_fundamental_columns_types(engine: AsyncEngine) -> None:
    """주요 컬럼 타입 검증 — A/B/C/D/E 5 카테고리."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT column_name, data_type, character_maximum_length, numeric_precision, numeric_scale
                FROM information_schema.columns
                WHERE table_schema = 'kiwoom' AND table_name = 'stock_fundamental'
                """
            )
        )
        rows = {r[0]: (r[1], r[2], r[3], r[4]) for r in result.fetchall()}

    # PK / FK
    assert rows["id"][0] == "bigint"
    assert rows["stock_id"][0] == "bigint"

    # 핵심 키
    assert rows["asof_date"][0] == "date"
    assert rows["exchange"][0] == "character varying"
    assert rows["exchange"][1] == 4

    # A. 기본
    assert rows["settlement_month"][0] == "character"
    assert rows["settlement_month"][1] == 2

    # B. 자본 (BIGINT 9개)
    for col in (
        "face_value",
        "capital_won",
        "listed_shares",
        "market_cap",
        "replacement_price",
        "circulating_shares",
    ):
        assert rows[col][0] == "bigint", f"{col} BIGINT 부재"

    # B/C/D/E NUMERIC 검증 (8,4) — Migration 017 후 trade_compare_rate (12,4) /
    # low_250d_pre_rate (10,4) 로 확대 (Phase F-1 ka10001 overflow 대응).
    for col in (
        "market_cap_weight",
        "foreign_holding_rate",
        "credit_rate",
        "circulating_rate",
        "high_250d_pre_rate",
        "change_rate",
    ):
        assert rows[col][0] == "numeric", f"{col} NUMERIC 부재"
        assert rows[col][2] == 8 and rows[col][3] == 4, f"{col} (8,4) 부재"

    # Phase F-1 (Migration 017) — 확대된 컬럼 검증
    assert rows["trade_compare_rate"][0] == "numeric"
    assert rows["trade_compare_rate"][2] == 12 and rows["trade_compare_rate"][3] == 4, (
        "trade_compare_rate (12,4) 부재 — Migration 017 미적용"
    )
    assert rows["low_250d_pre_rate"][0] == "numeric"
    assert rows["low_250d_pre_rate"][2] == 10 and rows["low_250d_pre_rate"][3] == 4, (
        "low_250d_pre_rate (10,4) 부재 — Migration 017 미적용"
    )

    # C/PER PBR EV (10,2)
    for col in ("per_ratio", "pbr_ratio", "ev_ratio"):
        assert rows[col][0] == "numeric", f"{col} NUMERIC 부재"
        assert rows[col][2] == 10 and rows[col][3] == 2, f"{col} (10,2) 부재"

    # ROE (8,2)
    assert rows["roe_pct"][2] == 8 and rows["roe_pct"][3] == 2

    # C/손익 BIGINT
    for col in ("eps_won", "bps_won", "revenue_amount", "operating_profit", "net_profit"):
        assert rows[col][0] == "bigint", f"{col} BIGINT 부재"

    # D. 250일 / 연중 통계
    assert rows["high_250d_date"][0] == "date"
    assert rows["low_250d_date"][0] == "date"
    for col in ("high_250d", "low_250d", "year_high", "year_low"):
        assert rows[col][0] == "bigint"

    # E. 일중 시세 BIGINT
    for col in (
        "current_price",
        "prev_compare_amount",
        "trade_volume",
        "open_price",
        "high_price",
        "low_price",
        "upper_limit_price",
        "lower_limit_price",
        "base_price",
        "expected_match_price",
        "expected_match_volume",
    ):
        assert rows[col][0] == "bigint", f"{col} BIGINT 부재"
    assert rows["prev_compare_sign"][0] == "character"
    assert rows["prev_compare_sign"][1] == 1

    # 변경 감지 hash
    assert rows["fundamental_hash"][0] == "character"
    assert rows["fundamental_hash"][1] == 32

    # 타임스탬프
    assert rows["fetched_at"][0] == "timestamp with time zone"
    assert rows["created_at"][0] == "timestamp with time zone"
    assert rows["updated_at"][0] == "timestamp with time zone"


@pytest.mark.asyncio
async def test_stock_fundamental_default_values(engine: AsyncEngine) -> None:
    """server_default 검증 — exchange='KRX', timestamps=now()."""
    async with engine.connect() as conn, conn.begin():
        # stock 1행 INSERT 후 stock_fundamental 최소 컬럼 INSERT
        await conn.execute(
            text(
                "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code) "
                "VALUES ('TST001', 'test', '0') RETURNING id"
            )
        )
        result = await conn.execute(
            text("SELECT id FROM kiwoom.stock WHERE stock_code = 'TST001'")
        )
        stock_id = result.scalar_one()

        await conn.execute(
            text(
                "INSERT INTO kiwoom.stock_fundamental (stock_id, asof_date) "
                f"VALUES ({stock_id}, DATE '2026-05-08')"
            )
        )
        result = await conn.execute(
            text(
                "SELECT exchange, fetched_at, created_at, updated_at "
                "FROM kiwoom.stock_fundamental WHERE stock_id = :sid"
            ).bindparams(sid=stock_id)
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "KRX"
        assert row[1] is not None
        assert row[2] is not None
        assert row[3] is not None
        await conn.rollback()


@pytest.mark.asyncio
async def test_stock_fundamental_cascade_delete_with_stock(engine: AsyncEngine) -> None:
    """ON DELETE CASCADE — stock 삭제 시 stock_fundamental row 도 삭제."""
    async with engine.connect() as conn, conn.begin():
        await conn.execute(
            text(
                "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code) "
                "VALUES ('TST002', 'cascade-test', '0')"
            )
        )
        result = await conn.execute(text("SELECT id FROM kiwoom.stock WHERE stock_code = 'TST002'"))
        stock_id = result.scalar_one()

        await conn.execute(
            text(
                "INSERT INTO kiwoom.stock_fundamental (stock_id, asof_date) "
                f"VALUES ({stock_id}, DATE '2026-05-08')"
            )
        )
        # 사전 검증
        result = await conn.execute(
            text(
                "SELECT COUNT(*) FROM kiwoom.stock_fundamental WHERE stock_id = :sid"
            ).bindparams(sid=stock_id)
        )
        assert result.scalar_one() == 1

        # stock 삭제 → CASCADE
        await conn.execute(text("DELETE FROM kiwoom.stock WHERE id = :sid").bindparams(sid=stock_id))

        result = await conn.execute(
            text(
                "SELECT COUNT(*) FROM kiwoom.stock_fundamental WHERE stock_id = :sid"
            ).bindparams(sid=stock_id)
        )
        assert result.scalar_one() == 0, "ON DELETE CASCADE 미동작"
        await conn.rollback()


def test_migration_004_downgrade_then_upgrade_idempotent(database_url: str) -> None:
    """빈 stock_fundamental 테이블에서 downgrade 004 → upgrade head 멱등성."""
    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    command.downgrade(alembic_cfg, "003_kiwoom_stock")
    command.upgrade(alembic_cfg, "head")
