"""Alembic Migration 013 — kiwoom.stock_daily_flow C/E 중복 컬럼 2개 DROP (C-2δ).

설계: endpoint-10-ka10086.md § 13.

배경 (운영 실측 § 5.6 IS DISTINCT FROM SQL — 2,879,500 rows):
- C 페어: `credit_rate` ≡ `credit_balance_rate` (`credit_diff=0`)
- E 페어: `foreign_rate` ≡ `foreign_weight` (`foreign_diff=0`)
- vendor 가 두 raw 필드를 동일값으로 채움 → 어댑터가 두 컬럼 동일 적재
- 잔존 (`credit_rate` / `foreign_rate`) 만 의미 있음 → 중복 2 컬럼 DROP

검증 (008 패턴 1:1 응용):
- UPGRADE 후 stock_daily_flow 컬럼 셋 = (008 head) - {credit_balance_rate, foreign_weight}
- DOWNGRADE 시 데이터 가드 — row 1건 이상이면 RAISE
- DOWNGRADE — 빈 테이블에서 2 컬럼 NUMERIC(8,4) NULL 로 복원
- 멱등 — head → 012 downgrade → head upgrade 라운드트립
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

DROPPED_COLUMNS = {
    "credit_balance_rate",
    "foreign_weight",
}


@pytest.mark.asyncio
async def test_dropped_columns_absent_after_upgrade(engine: AsyncEngine) -> None:
    """013 적용 후 head 상태에서 C/E 중복 2 컬럼이 부재."""
    async with engine.connect() as conn:

        def _list_columns(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            return {c["name"] for c in insp.get_columns("stock_daily_flow", schema="kiwoom")}

        cols = await conn.run_sync(_list_columns)

    assert DROPPED_COLUMNS.isdisjoint(cols), f"013 적용 후에도 DROP 대상 컬럼 잔존: {DROPPED_COLUMNS & cols}"


@pytest.mark.asyncio
async def test_remaining_domain_columns_intact(engine: AsyncEngine) -> None:
    """잔존 8 도메인 컬럼 (C 신용 1 + D 투자자별 4 + E 외인 3) 은 그대로 유지."""
    async with engine.connect() as conn:

        def _list_columns(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            return {c["name"] for c in insp.get_columns("stock_daily_flow", schema="kiwoom")}

        cols = await conn.run_sync(_list_columns)

    expected_remaining = {
        # C. 신용 (1 — credit_balance_rate DROP)
        "credit_rate",
        # D. 투자자별 net (4 — 008 후 그대로)
        "individual_net",
        "institutional_net",
        "foreign_brokerage_net",
        "program_net",
        # E. 외인 (3 — foreign_weight DROP)
        "foreign_volume",
        "foreign_rate",
        "foreign_holdings",
    }
    missing = expected_remaining - cols
    assert not missing, f"013 후 유지되어야 할 컬럼 누락: {missing}"


def test_migration_013_downgrade_with_data_raises(database_url: str) -> None:
    """downgrade 가드 — 데이터 1건 이상이면 RAISE (007/008 downgrade 와 동일 패턴).

    head 상태에서 stock + stock_daily_flow row 삽입 후 013 → 012 downgrade 시도 →
    DBAPIError (PostgreSQL RAISE EXCEPTION) 발생해야 함.
    """
    import sqlalchemy as sa

    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    sync_engine = sa.create_engine(database_url.replace("+asyncpg", "+psycopg2"))
    try:
        with sync_engine.begin() as conn:
            # head 상태 (013 적용 완료) — stock + stock_daily_flow 1건 삽입
            conn.execute(
                text(
                    "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code) "
                    "VALUES ('TST013G', 'downgrade-guard', '0')"
                )
            )
            sid = conn.execute(text("SELECT id FROM kiwoom.stock WHERE stock_code = 'TST013G'")).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO kiwoom.stock_daily_flow "
                    "(stock_id, trading_date, exchange, indc_mode) "
                    "VALUES (:sid, DATE '2025-09-08', 'KRX', '0')"
                ).bindparams(sid=sid)
            )

        with pytest.raises(DBAPIError):
            command.downgrade(alembic_cfg, "012_stock_price_monthly_nxt")
    finally:
        # 008 패턴 1:1 — RAISE EXCEPTION 후 013 가드 작동 검증. transactional DDL rollback 보장.
        try:
            with sync_engine.begin() as conn:
                conn.execute(text("DELETE FROM kiwoom.stock WHERE stock_code = 'TST013G'"))
        except Exception:
            pass
        with sync_engine.begin() as conn:
            head_rev = conn.execute(text("SELECT version_num FROM kiwoom.alembic_version")).scalar_one()
        sync_engine.dispose()
        # 014 head 진입 후엔 command.downgrade(012) 가 014 → 013 → 012 다단계 진행.
        # alembic 의 단일 transaction 안에서 RAISE → 전체 rollback → alembic_version 014 유지
        # (test_migration_013 verification 발견 — 014 시점 head 유지).
        # 핵심 검증: 가드 우회로 downgrade target (012) 까지 진행되지 않았음.
        assert head_rev != "012_stock_price_monthly_nxt", (
            f"013 가드 우회 — alembic_version 이 downgrade target 까지 진행됨: {head_rev}. "
            "DO $$ 블록 RAISE 후 trans rollback 가정 위반."
        )


def test_migration_013_downgrade_then_upgrade_restores_columns(database_url: str) -> None:
    """빈 테이블에서 013 → 012 downgrade → head upgrade 라운드트립.

    NUMERIC(8,4) 타입 복원 검증 — 008 (BIGINT) 패턴과 다른 점.
    """
    import sqlalchemy as sa

    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    sync_engine = sa.create_engine(database_url.replace("+asyncpg", "+psycopg2"))
    try:
        # downgrade 013 → 012 (빈 테이블이라 가드 통과)
        command.downgrade(alembic_cfg, "012_stock_price_monthly_nxt")

        with sync_engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT column_name, data_type, numeric_precision, numeric_scale "
                    "FROM information_schema.columns "
                    "WHERE table_schema = 'kiwoom' AND table_name = 'stock_daily_flow'"
                )
            )
            cols_info = {r[0]: (r[1], r[2], r[3]) for r in result.fetchall()}

        # 012 상태 (= 008 head) — DROP 2 컬럼 복원 + NUMERIC(8,4) 타입 단언
        assert DROPPED_COLUMNS.issubset(cols_info.keys()), (
            f"012 상태에서 C/E 컬럼 복원 실패: {DROPPED_COLUMNS - cols_info.keys()}"
        )
        for dropped in DROPPED_COLUMNS:
            data_type, precision, scale = cols_info[dropped]
            assert data_type == "numeric", f"{dropped} numeric 가 아닌 타입으로 복원됨: {data_type}"
            assert precision == 8 and scale == 4, f"{dropped} NUMERIC(8,4) 부재 (실제: {precision},{scale})"
        # 012 (= 008 head) = 10 도메인 + 5 키/메타 + 3 timestamp = 18
        assert len(cols_info) == 18, f"012 상태 컬럼 수 18 기대, 실제 {len(cols_info)}: {sorted(cols_info)}"

        # upgrade head — 다시 013 적용
        command.upgrade(alembic_cfg, "head")

        with sync_engine.connect() as conn:
            insp = inspect(conn)
            cols_after_upgrade = {c["name"] for c in insp.get_columns("stock_daily_flow", schema="kiwoom")}
        assert DROPPED_COLUMNS.isdisjoint(cols_after_upgrade), (
            f"013 재적용 후에도 DROP 대상 잔존: {DROPPED_COLUMNS & cols_after_upgrade}"
        )
        # head = 8 도메인 + 5 키/메타 + 3 timestamp = 16
        assert len(cols_after_upgrade) == 16, (
            f"head 상태 컬럼 수 16 기대, 실제 {len(cols_after_upgrade)}: {sorted(cols_after_upgrade)}"
        )
    finally:
        sync_engine.dispose()
