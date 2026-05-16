"""Alembic Migration 019 — kiwoom.investor_flow_daily / stock_investor_breakdown / frgn_orgn_consecutive (Phase G).

TDD red 의도:
- Migration 019_investor_flow 미존재 → upgrade head 후 version 검증 실패
- 3 테이블 미존재 → 컬럼/UNIQUE/INDEX 검증 실패
- Step 1 구현 후 green 전환.

검증 (~10 케이스):
1. 019 revision id 존재 + down_revision = 018_ranking_snapshot
2. investor_flow_daily 테이블 + 컬럼 + UNIQUE + INDEX
3. stock_investor_breakdown 테이블 + 컬럼 + UNIQUE + INDEX
4. frgn_orgn_consecutive 테이블 + 컬럼 + UNIQUE + INDEX
5. 3 테이블 모두 stock_id FK ON DELETE SET NULL
6. investor_flow_daily — idx_ifd_date_investor 인덱스
7. stock_investor_breakdown — idx_sib_stock_date partial index
8. frgn_orgn_consecutive — idx_foc_date_market + idx_foc_total_cont_days DESC
9. downgrade 019 → 018: 3 테이블 DROP + ranking_snapshot 유지
10. 019 upgrade smoke — alembic_version = 019_investor_flow
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

INVESTOR_FLOW_DAILY_TABLE = "investor_flow_daily"
STOCK_INVESTOR_BREAKDOWN_TABLE = "stock_investor_breakdown"
FRGN_ORGN_CONSECUTIVE_TABLE = "frgn_orgn_consecutive"

EXPECTED_IFD_COLUMNS = {
    "id",
    "as_of_date",
    "stock_id",
    "stock_code_raw",
    "investor_type",
    "trade_type",
    "market_type",
    "exchange_type",
    "rank",
    "net_volume",
    "net_amount",
    "estimated_avg_price",
    "current_price",
    "prev_compare_sign",
    "prev_compare_amount",
    "avg_price_compare",
    "prev_compare_rate",
    "period_volume",
    "stock_name",
    "fetched_at",
    "created_at",
}

EXPECTED_SIB_COLUMNS = {
    "id",
    "stock_id",
    "trading_date",
    "amt_qty_tp",
    "trade_type",
    "unit_tp",
    "exchange_type",
    "current_price",
    "prev_compare_sign",
    "prev_compare_amount",
    "change_rate",
    "acc_trade_volume",
    "acc_trade_amount",
    "net_individual",
    "net_foreign",
    "net_institution_total",
    "net_financial_inv",
    "net_insurance",
    "net_investment_trust",
    "net_other_financial",
    "net_bank",
    "net_pension_fund",
    "net_private_fund",
    "net_nation",
    "net_other_corp",
    "net_dom_for",
    "fetched_at",
    "created_at",
}

EXPECTED_FOC_COLUMNS = {
    "id",
    "as_of_date",
    "stock_id",
    "stock_code_raw",
    "stock_name",
    "period_type",
    "market_type",
    "amt_qty_tp",
    "stk_inds_tp",
    "exchange_type",
    "rank",
    "period_stock_price_flu_rt",
    "orgn_net_amount",
    "orgn_net_volume",
    "orgn_cont_days",
    "orgn_cont_volume",
    "orgn_cont_amount",
    "frgnr_net_volume",
    "frgnr_net_amount",
    "frgnr_cont_days",
    "frgnr_cont_volume",
    "frgnr_cont_amount",
    "total_net_volume",
    "total_net_amount",
    "total_cont_days",
    "total_cont_volume",
    "total_cont_amount",
    "fetched_at",
    "created_at",
}


# ---------------------------------------------------------------------------
# Scenario 1 — 019 revision id + down_revision
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_019_revision_id(engine: AsyncEngine) -> None:
    """upgrade head 후 alembic_version = 019_investor_flow (또는 이후 head).

    018 까지만 적용된 상태면 fail — 019 미적용 의도된 red.
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
        "018_ranking_snapshot",
    ), f"019 미적용 — alembic_version='{rev}' (019 또는 이후 head 기대)"


# ---------------------------------------------------------------------------
# Scenario 2 — investor_flow_daily 테이블 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_investor_flow_daily_columns(engine: AsyncEngine) -> None:
    """investor_flow_daily 컬럼 존재 + FK (stock_id → kiwoom.stock(id) ON DELETE SET NULL)."""
    async with engine.connect() as conn:

        def _inspect(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            cols = {c["name"] for c in insp.get_columns(INVESTOR_FLOW_DAILY_TABLE, schema="kiwoom")}
            fks = insp.get_foreign_keys(INVESTOR_FLOW_DAILY_TABLE, schema="kiwoom")
            uqs = insp.get_unique_constraints(INVESTOR_FLOW_DAILY_TABLE, schema="kiwoom")
            return cols, fks, uqs

        cols, fks, uqs = await conn.run_sync(_inspect)

    missing = EXPECTED_IFD_COLUMNS - cols
    assert not missing, f"investor_flow_daily 누락 컬럼: {missing}"

    # FK 검증
    assert fks, "investor_flow_daily FK 부재"
    stock_fk = next((f for f in fks if "stock_id" in f.get("constrained_columns", [])), None)
    assert stock_fk is not None, f"stock_id FK 부재: {fks}"
    assert stock_fk["options"].get("ondelete", "").upper() == "SET NULL", (
        f"ON DELETE SET NULL 부재: {stock_fk['options']}"
    )

    # UNIQUE 검증 — (as_of_date, investor_type, trade_type, market_type, exchange_type, stock_code_raw)
    uq_col_sets = [frozenset(u["column_names"]) for u in uqs]
    assert len(uq_col_sets) >= 1, f"investor_flow_daily UNIQUE 부재: {uqs}"


# ---------------------------------------------------------------------------
# Scenario 3 — stock_investor_breakdown 테이블 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stock_investor_breakdown_columns(engine: AsyncEngine) -> None:
    """stock_investor_breakdown 컬럼 존재 + UNIQUE."""
    async with engine.connect() as conn:

        def _inspect(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            cols = {c["name"] for c in insp.get_columns(STOCK_INVESTOR_BREAKDOWN_TABLE, schema="kiwoom")}
            uqs = insp.get_unique_constraints(STOCK_INVESTOR_BREAKDOWN_TABLE, schema="kiwoom")
            return cols, uqs

        cols, uqs = await conn.run_sync(_inspect)

    missing = EXPECTED_SIB_COLUMNS - cols
    assert not missing, f"stock_investor_breakdown 누락 컬럼: {missing}"
    assert len(uqs) >= 1, f"stock_investor_breakdown UNIQUE 부재: {uqs}"


# ---------------------------------------------------------------------------
# Scenario 4 — frgn_orgn_consecutive 테이블 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_frgn_orgn_consecutive_columns(engine: AsyncEngine) -> None:
    """frgn_orgn_consecutive 컬럼 존재 + UNIQUE."""
    async with engine.connect() as conn:

        def _inspect(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            cols = {c["name"] for c in insp.get_columns(FRGN_ORGN_CONSECUTIVE_TABLE, schema="kiwoom")}
            uqs = insp.get_unique_constraints(FRGN_ORGN_CONSECUTIVE_TABLE, schema="kiwoom")
            return cols, uqs

        cols, uqs = await conn.run_sync(_inspect)

    missing = EXPECTED_FOC_COLUMNS - cols
    assert not missing, f"frgn_orgn_consecutive 누락 컬럼: {missing}"
    assert len(uqs) >= 1, f"frgn_orgn_consecutive UNIQUE 부재: {uqs}"


# ---------------------------------------------------------------------------
# Scenario 5 — 3 테이블 모두 fetched_at / created_at server_default
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_three_tables_exist(engine: AsyncEngine) -> None:
    """3 테이블 동시 존재 확인."""
    async with engine.connect() as conn:

        def _get_tables(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            return set(insp.get_table_names(schema="kiwoom"))

        tables = await conn.run_sync(_get_tables)

    assert INVESTOR_FLOW_DAILY_TABLE in tables, f"investor_flow_daily 미존재: {tables}"
    assert STOCK_INVESTOR_BREAKDOWN_TABLE in tables, f"stock_investor_breakdown 미존재: {tables}"
    assert FRGN_ORGN_CONSECUTIVE_TABLE in tables, f"frgn_orgn_consecutive 미존재: {tables}"


# ---------------------------------------------------------------------------
# Scenario 6 — investor_flow_daily 인덱스 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_investor_flow_daily_index(engine: AsyncEngine) -> None:
    """idx_ifd_date_investor — (as_of_date, investor_type, trade_type, market_type) 복합 인덱스."""
    async with engine.connect() as conn:
        row = await conn.execute(
            text(
                "SELECT indexdef FROM pg_indexes"
                " WHERE schemaname = 'kiwoom'"
                " AND tablename = :tbl"
                " AND indexname LIKE 'idx_ifd_%'"
            ).bindparams(tbl=INVESTOR_FLOW_DAILY_TABLE)
        )
        results = row.fetchall()

    assert len(results) >= 1, "investor_flow_daily 인덱스 미존재"


# ---------------------------------------------------------------------------
# Scenario 7 — stock_investor_breakdown 인덱스
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stock_investor_breakdown_index(engine: AsyncEngine) -> None:
    """stock_investor_breakdown — 인덱스 존재 확인."""
    async with engine.connect() as conn:
        row = await conn.execute(
            text(
                "SELECT indexdef FROM pg_indexes"
                " WHERE schemaname = 'kiwoom'"
                " AND tablename = :tbl"
                " AND indexname LIKE 'idx_sib_%'"
            ).bindparams(tbl=STOCK_INVESTOR_BREAKDOWN_TABLE)
        )
        results = row.fetchall()

    assert len(results) >= 1, "stock_investor_breakdown 인덱스 미존재"


# ---------------------------------------------------------------------------
# Scenario 8 — frgn_orgn_consecutive total_cont_days DESC 인덱스
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_frgn_orgn_consecutive_total_cont_days_index(engine: AsyncEngine) -> None:
    """frgn_orgn_consecutive — total_cont_days DESC 인덱스 존재."""
    async with engine.connect() as conn:
        row = await conn.execute(
            text(
                "SELECT indexdef FROM pg_indexes"
                " WHERE schemaname = 'kiwoom'"
                " AND tablename = :tbl"
                " AND (indexdef ILIKE '%total_cont_days%' OR indexname LIKE 'idx_foc_%')"
            ).bindparams(tbl=FRGN_ORGN_CONSECUTIVE_TABLE)
        )
        results = row.fetchall()

    assert len(results) >= 1, "frgn_orgn_consecutive 인덱스 미존재"


# ---------------------------------------------------------------------------
# Scenario 9 — downgrade 019 → 018
# ---------------------------------------------------------------------------


def test_migration_019_downgrade_drops_three_tables_keeps_ranking(
    database_url: str,
) -> None:
    """019 → 018 downgrade 시 3 테이블 DROP + ranking_snapshot 유지."""
    import sqlalchemy as sa

    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    sync_engine = sa.create_engine(database_url.replace("+asyncpg", "+psycopg2"))
    try:
        command.downgrade(alembic_cfg, "018_ranking_snapshot")

        with sync_engine.connect() as conn:
            insp = inspect(conn)
            existing = set(insp.get_table_names(schema="kiwoom"))

        assert INVESTOR_FLOW_DAILY_TABLE not in existing, (
            f"019 downgrade 후 {INVESTOR_FLOW_DAILY_TABLE} 잔존"
        )
        assert STOCK_INVESTOR_BREAKDOWN_TABLE not in existing, (
            f"019 downgrade 후 {STOCK_INVESTOR_BREAKDOWN_TABLE} 잔존"
        )
        assert FRGN_ORGN_CONSECUTIVE_TABLE not in existing, (
            f"019 downgrade 후 {FRGN_ORGN_CONSECUTIVE_TABLE} 잔존"
        )
        # 018 테이블은 유지
        assert "ranking_snapshot" in existing, (
            "019 downgrade 후 ranking_snapshot 삭제됨 (비파괴 보장 실패)"
        )

        # 복원
        command.upgrade(alembic_cfg, "head")

        with sync_engine.connect() as conn2:
            insp2 = inspect(conn2)
            restored = set(insp2.get_table_names(schema="kiwoom"))

        assert INVESTOR_FLOW_DAILY_TABLE in restored, (
            f"019 재적용 후 {INVESTOR_FLOW_DAILY_TABLE} 미생성"
        )
    finally:
        sync_engine.dispose()


# ---------------------------------------------------------------------------
# Scenario 10 — investor_flow_daily raw INSERT smoke
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_investor_flow_daily_raw_insert_smoke(engine: AsyncEngine) -> None:
    """investor_flow_daily — raw SQL INSERT + SELECT smoke."""
    from datetime import date

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO kiwoom.investor_flow_daily "
                "(as_of_date, stock_id, stock_code_raw, investor_type, trade_type, "
                " market_type, exchange_type, rank, net_volume, stock_name) "
                "VALUES (:d, NULL, :code, :inv, :tr, :mk, :ex, :rk, :nv, :nm)"
            ).bindparams(
                d=date(2026, 5, 16),
                code="005930",
                inv="9000",
                tr="2",
                mk="001",
                ex="3",
                rk=1,
                nv=4464,
                nm="삼성전자",
            )
        )
        row = await conn.execute(
            text(
                "SELECT investor_type, trade_type, net_volume, stock_name "
                "FROM kiwoom.investor_flow_daily "
                "WHERE stock_code_raw = '005930' AND as_of_date = '2026-05-16' "
                "LIMIT 1"
            )
        )
        result = row.fetchone()
        await conn.execute(
            text(
                "DELETE FROM kiwoom.investor_flow_daily "
                "WHERE stock_code_raw = '005930' AND as_of_date = '2026-05-16'"
            )
        )

    assert result is not None, "investor_flow_daily INSERT 실패"
    assert result[0] == "9000", f"investor_type 미일치: {result[0]!r}"
    assert result[2] == 4464, f"net_volume 미일치: {result[2]!r}"
