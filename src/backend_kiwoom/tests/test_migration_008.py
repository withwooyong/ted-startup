"""Alembic Migration 008 — kiwoom.stock_daily_flow D-E 중복 컬럼 DROP (C-2γ).

설계: endpoint-10-ka10086.md § 12.

배경 (운영 dry-run § 20.2 #1):
- D 카테고리 ↔ E 카테고리 3 컬럼 쌍이 1,200/1,200 row 100% 동일값
  - `individual_net` ≡ `individual_net_purchase`
  - `institutional_net` ≡ `institutional_net_purchase`
  - `foreign_volume` ≡ `foreign_net_purchase`
- D 카테고리 6 컬럼 (개인/기관/외국계/프로그램 + 외인 + 외인보유) 만 의미 있음
- E 카테고리 3 컬럼 (개인/기관/외인 순매수) 은 D 의 중복 → DROP

검증:
- UPGRADE 후 stock_daily_flow 컬럼 셋 = 기존 - {individual_net_purchase, institutional_net_purchase, foreign_net_purchase}
- DOWNGRADE 시 데이터 가드 — row 1건 이상이면 RAISE
- DOWNGRADE — 빈 테이블에서 3 컬럼 BIGINT NULL 로 복원
- 멱등 — head → 007 downgrade → head upgrade 라운드트립
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
    "individual_net_purchase",
    "institutional_net_purchase",
    "foreign_net_purchase",
}


@pytest.mark.asyncio
async def test_dropped_columns_absent_after_upgrade(engine: AsyncEngine) -> None:
    """008 적용 후 head 상태에서 D-E 중복 3 컬럼이 부재."""
    async with engine.connect() as conn:

        def _list_columns(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            return {c["name"] for c in insp.get_columns("stock_daily_flow", schema="kiwoom")}

        cols = await conn.run_sync(_list_columns)

    assert DROPPED_COLUMNS.isdisjoint(cols), f"008 적용 후에도 DROP 대상 컬럼 잔존: {DROPPED_COLUMNS & cols}"


@pytest.mark.asyncio
async def test_remaining_d_category_columns_intact(engine: AsyncEngine) -> None:
    """008 + 013 적용 후 유지되어야 할 8 도메인 컬럼 (C-2γ 후 10 - C-2δ 2 = 8).

    conftest 가 head 까지 적용하므로 013 (C-2δ) 까지 적용된 상태에서 검증.
    `credit_balance_rate` / `foreign_weight` 는 C-2δ Migration 013 에서 추가 DROP.
    """
    async with engine.connect() as conn:

        def _list_columns(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            return {c["name"] for c in insp.get_columns("stock_daily_flow", schema="kiwoom")}

        cols = await conn.run_sync(_list_columns)

    expected_remaining = {
        # C. 신용 (C-2δ — credit_balance_rate DROP)
        "credit_rate",
        # D. 투자자별 net
        "individual_net",
        "institutional_net",
        "foreign_brokerage_net",
        "program_net",
        # 외인 (C-2δ — foreign_weight DROP)
        "foreign_volume",
        "foreign_rate",
        "foreign_holdings",
    }
    missing = expected_remaining - cols
    assert not missing, f"008 후 유지되어야 할 컬럼 누락: {missing}"


def test_migration_008_downgrade_with_data_raises(database_url: str) -> None:
    """downgrade 가드 — 데이터 1건 이상이면 RAISE (007 downgrade 와 동일 패턴).

    head 상태에서 stock + stock_daily_flow row 삽입 후 008 → 007 downgrade 시도 →
    DBAPIError (PostgreSQL RAISE EXCEPTION) 발생해야 함.
    """
    import sqlalchemy as sa

    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    sync_engine = sa.create_engine(database_url.replace("+asyncpg", "+psycopg2"))
    try:
        with sync_engine.begin() as conn:
            # head 상태 (008 적용 완료) — stock + stock_daily_flow 1건 삽입
            conn.execute(
                text(
                    "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code) "
                    "VALUES ('TST008G', 'downgrade-guard', '0')"
                )
            )
            sid = conn.execute(text("SELECT id FROM kiwoom.stock WHERE stock_code = 'TST008G'")).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO kiwoom.stock_daily_flow "
                    "(stock_id, trading_date, exchange, indc_mode) "
                    "VALUES (:sid, DATE '2025-09-08', 'KRX', '0')"
                ).bindparams(sid=sid)
            )

        with pytest.raises(DBAPIError):
            command.downgrade(alembic_cfg, "007_kiwoom_stock_daily_flow")
    finally:
        # M-1 — RAISE EXCEPTION 후 008 가드 작동 검증. 다음 chunk 가 head 위에 마이그레이션을
        # 추가해도 영향 없게 동적 검증 — alembic_version 이 downgrade target (007) 으로 가지
        # 않은 것만 확인 (transactional DDL 환경에서 전체 rollback 보장).
        # CASCADE 로 stock_daily_flow row 정리 먼저 — assert fail 해도 다음 테스트 격리.
        try:
            with sync_engine.begin() as conn:
                conn.execute(text("DELETE FROM kiwoom.stock WHERE stock_code = 'TST008G'"))
        except Exception:
            pass
        with sync_engine.begin() as conn:
            head_rev = conn.execute(text("SELECT version_num FROM kiwoom.alembic_version")).scalar_one()
        sync_engine.dispose()
        assert head_rev != "007_kiwoom_stock_daily_flow", (
            f"008 가드 우회 — alembic_version 이 downgrade target 까지 진행됨: {head_rev}. "
            "DO $$ 블록 RAISE 후 trans rollback 가정 위반."
        )


def test_migration_008_downgrade_then_upgrade_restores_columns(database_url: str) -> None:
    """빈 테이블에서 008 → 007 downgrade → head upgrade 라운드트립 — 컬럼 복원·재제거 + BIGINT 타입 검증."""
    import sqlalchemy as sa

    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    sync_engine = sa.create_engine(database_url.replace("+asyncpg", "+psycopg2"))
    try:
        # downgrade 008 → 007 (빈 테이블이라 가드 통과)
        command.downgrade(alembic_cfg, "007_kiwoom_stock_daily_flow")

        with sync_engine.connect() as conn:
            insp = inspect(conn)
            cols_info = {c["name"]: c["type"] for c in insp.get_columns("stock_daily_flow", schema="kiwoom")}
        # M-2 — 컬럼 카운트 + BIGINT 타입 단언 (007 = 13 도메인 + 5 메타 = 18)
        assert DROPPED_COLUMNS.issubset(cols_info.keys()), (
            f"007 상태에서 D-E 컬럼 복원 실패: {DROPPED_COLUMNS - cols_info.keys()}"
        )
        for dropped in DROPPED_COLUMNS:
            assert "BIGINT" in str(cols_info[dropped]).upper(), (
                f"{dropped} BIGINT 가 아닌 타입으로 복원됨: {cols_info[dropped]}"
            )
        # 007 = 13 도메인 + 5 키/메타 (id, stock_id, trading_date, exchange, indc_mode) + 3 timestamp = 21
        assert len(cols_info) == 21, f"007 상태 컬럼 수 21 기대, 실제 {len(cols_info)}: {sorted(cols_info)}"

        # upgrade head — 다시 008 적용
        command.upgrade(alembic_cfg, "head")

        with sync_engine.connect() as conn:
            insp = inspect(conn)
            cols_after_upgrade = {c["name"] for c in insp.get_columns("stock_daily_flow", schema="kiwoom")}
        assert DROPPED_COLUMNS.isdisjoint(cols_after_upgrade), (
            f"008 재적용 후에도 DROP 대상 잔존: {DROPPED_COLUMNS & cols_after_upgrade}"
        )
        # head = 8 도메인 (C-2γ 후 10 - C-2δ 2) + 5 키/메타 + 3 timestamp = 16
        assert len(cols_after_upgrade) == 16, (
            f"head 상태 컬럼 수 16 기대, 실제 {len(cols_after_upgrade)}: {sorted(cols_after_upgrade)}"
        )
    finally:
        sync_engine.dispose()
