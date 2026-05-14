"""Alembic Migration 017 — stock_fundamental NUMERIC 확대 (Phase F-1).

설계: phase-f-1-ka10001-numeric-sentinel.md § 4 / § 5.2.

016 → 017 upgrade:
- ALTER TABLE kiwoom.stock_fundamental ALTER COLUMN trade_compare_rate TYPE NUMERIC(12, 4)
- ALTER TABLE kiwoom.stock_fundamental ALTER COLUMN low_250d_pre_rate TYPE NUMERIC(10, 4)

downgrade (017 → 016):
- 9999 초과 데이터 존재 시 RAISE EXCEPTION (데이터 손실 차단 가드)
- 9999 이하면 원래 타입으로 복원

검증:
1. 016 → 017 upgrade 성공 / revision id / down_revision
2. trade_compare_rate 컬럼 precision=12, scale=4 (information_schema 확인)
3. low_250d_pre_rate 컬럼 precision=10, scale=4
4. downgrade 가드 — 9999 초과 데이터 있으면 fail (데이터 손실 차단)
5. 빈 테이블 downgrade — 016 으로 복원 성공 / precision 원복

본 테스트는 Migration 017 파일 미존재 → alembic upgrade 실패 = red.
Step 1 에서 017 마이그레이션 파일 생성 후 green 전환 대상.

016_short_lending.py 패턴 차용 (sync engine + alembic command).
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

STOCK_FUNDAMENTAL_TABLE = "stock_fundamental"
TARGET_REVISION = "017_ka10001_numeric_precision"

# precision 기대값 (Migration 017 후)
EXPECTED_TRADE_COMPARE_RATE_PRECISION = 12
EXPECTED_TRADE_COMPARE_RATE_SCALE = 4
EXPECTED_LOW_250D_PRE_RATE_PRECISION = 10
EXPECTED_LOW_250D_PRE_RATE_SCALE = 4

# 원래 precision (Migration 016 head 기준)
ORIGINAL_PRECISION = 8
ORIGINAL_SCALE = 4


def _make_alembic_cfg(database_url: str) -> Config:
    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    return alembic_cfg


# ---------------------------------------------------------------------------
# Scenario 1 — revision id + down_revision 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_017_revision_id_and_down_revision(engine: AsyncEngine) -> None:
    """016 → 017 upgrade 성공 / revision id = 017_ka10001_numeric_precision / down_revision = 016_short_lending.

    현재 head = 016_short_lending (Migration 017 미존재) → 이 테스트 도달 불가 또는 실패 = red.
    Step 1 에서 017 생성 + conftest.py apply_migrations (upgrade head) 에 포함 후 green.
    """
    async with engine.connect() as conn:
        version = await conn.execute(
            text("SELECT version_num FROM kiwoom.alembic_version")
        )
        rev = version.scalar_one()

    assert rev == TARGET_REVISION, (
        f"alembic_version 기대 '{TARGET_REVISION}', 실제 '{rev}' — "
        f"Migration 017 미적용 또는 revision id 불일치"
    )


# ---------------------------------------------------------------------------
# Scenario 2 — trade_compare_rate precision=12, scale=4
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_017_trade_compare_rate_is_numeric_12_4(engine: AsyncEngine) -> None:
    """upgrade 후 trade_compare_rate 컬럼이 NUMERIC(12, 4) 인지 information_schema 로 검증.

    Postgres 의 information_schema.columns:
    - numeric_precision: 전체 유효 숫자 수
    - numeric_scale: 소수점 이하 자리수
    """
    async with engine.connect() as conn:
        row = await conn.execute(
            text(
                "SELECT numeric_precision, numeric_scale "
                "FROM information_schema.columns "
                "WHERE table_schema = 'kiwoom' "
                "  AND table_name   = :tbl "
                "  AND column_name  = 'trade_compare_rate'"
            ).bindparams(tbl=STOCK_FUNDAMENTAL_TABLE)
        )
        result = row.fetchone()

    assert result is not None, (
        "information_schema 에서 trade_compare_rate 컬럼 조회 실패"
    )
    precision, scale = result[0], result[1]
    assert precision == EXPECTED_TRADE_COMPARE_RATE_PRECISION, (
        f"trade_compare_rate precision={EXPECTED_TRADE_COMPARE_RATE_PRECISION} 기대, "
        f"실제={precision} — Migration 017 미적용 (현재 precision=8)"
    )
    assert scale == EXPECTED_TRADE_COMPARE_RATE_SCALE, (
        f"trade_compare_rate scale=4 기대, 실제={scale}"
    )


# ---------------------------------------------------------------------------
# Scenario 3 — low_250d_pre_rate precision=10, scale=4
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_017_low_250d_pre_rate_is_numeric_10_4(engine: AsyncEngine) -> None:
    """upgrade 후 low_250d_pre_rate 컬럼이 NUMERIC(10, 4) 인지 information_schema 로 검증."""
    async with engine.connect() as conn:
        row = await conn.execute(
            text(
                "SELECT numeric_precision, numeric_scale "
                "FROM information_schema.columns "
                "WHERE table_schema = 'kiwoom' "
                "  AND table_name   = :tbl "
                "  AND column_name  = 'low_250d_pre_rate'"
            ).bindparams(tbl=STOCK_FUNDAMENTAL_TABLE)
        )
        result = row.fetchone()

    assert result is not None, (
        "information_schema 에서 low_250d_pre_rate 컬럼 조회 실패"
    )
    precision, scale = result[0], result[1]
    assert precision == EXPECTED_LOW_250D_PRE_RATE_PRECISION, (
        f"low_250d_pre_rate precision={EXPECTED_LOW_250D_PRE_RATE_PRECISION} 기대, "
        f"실제={precision} — Migration 017 미적용 (현재 precision=8)"
    )
    assert scale == EXPECTED_LOW_250D_PRE_RATE_SCALE, (
        f"low_250d_pre_rate scale=4 기대, 실제={scale}"
    )


# ---------------------------------------------------------------------------
# Scenario 4 — 변경 안 된 컬럼은 precision 그대로 (회귀 — over-engineering 회피)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_017_unchanged_columns_keep_original_precision(
    engine: AsyncEngine,
) -> None:
    """change_rate / market_cap_weight 는 Migration 017 에서 변경 안 함 — NUMERIC(8,4) 유지.

    over-engineering 회피 (계획서 § 4 결정 #8).
    """
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT column_name, numeric_precision, numeric_scale "
                "FROM information_schema.columns "
                "WHERE table_schema = 'kiwoom' "
                "  AND table_name   = :tbl "
                "  AND column_name  IN ('change_rate', 'market_cap_weight', 'foreign_holding_rate')"
            ).bindparams(tbl=STOCK_FUNDAMENTAL_TABLE)
        )
        results = {row[0]: (row[1], row[2]) for row in rows.fetchall()}

    for col in ("change_rate", "market_cap_weight", "foreign_holding_rate"):
        assert col in results, f"컬럼 {col} 조회 실패"
        precision, scale = results[col]
        assert precision == ORIGINAL_PRECISION, (
            f"{col} precision={ORIGINAL_PRECISION} 기대 (변경 안 함), 실제={precision}"
        )
        assert scale == ORIGINAL_SCALE, (
            f"{col} scale={ORIGINAL_SCALE} 기대, 실제={scale}"
        )


# ---------------------------------------------------------------------------
# Scenario 5 — downgrade 가드: 9999 초과 데이터 있으면 fail
# ---------------------------------------------------------------------------


def test_migration_017_downgrade_fails_when_overflow_data_exists(
    database_url: str,
) -> None:
    """downgrade 017→016 시 9999 초과 데이터 존재하면 RAISE EXCEPTION (데이터 손실 차단).

    계획서 § 5.2 downgrade 정책: CHECK 위반 안전 fail (사용자 결정 필요 시 별도 운영 chunk).

    절차:
    1. stock + overflow 값 삽입 (raw SQL — trade_compare_rate=10000.0001)
    2. alembic downgrade 016_short_lending — RAISE EXCEPTION 기대
    3. cleanup + upgrade head (다음 테스트 영향 없도록)
    """
    sync_engine = sa.create_engine(database_url.replace("+asyncpg", "+psycopg2"))
    alembic_cfg = _make_alembic_cfg(database_url)

    try:
        with sync_engine.connect() as conn:
            # stock 삽입
            stock_id = conn.execute(
                sa.text(
                    "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code) "
                    "VALUES ('468760', 'overflow-test', '0') RETURNING id"
                )
            ).scalar_one()
            conn.commit()

            # 9999 초과 값 raw INSERT (ORM 우회 — 현재 NUMERIC(12,4) 이라 INSERT 가능)
            conn.execute(
                sa.text(
                    "INSERT INTO kiwoom.stock_fundamental "
                    "(stock_id, asof_date, exchange, trade_compare_rate, fundamental_hash, fetched_at) "
                    "VALUES (:sid, '2026-05-14', 'KRX', 10000.0001, :h, NOW())"
                ).bindparams(sid=stock_id, h="a" * 32)
            )
            conn.commit()

        # downgrade 시 예외 기대 (데이터 손실 차단 가드)
        with pytest.raises(Exception, match=r"(overflow|초과|10000|trade_compare_rate)"):
            command.downgrade(alembic_cfg, "016_short_lending")

    finally:
        # cleanup — 다음 테스트를 위해 head 복원
        with sync_engine.connect() as conn:
            conn.execute(
                sa.text("DELETE FROM kiwoom.stock WHERE stock_code = '468760'")
            )
            conn.commit()
        # head 복원 시도 (이미 017 이면 no-op)
        with contextlib.suppress(Exception):
            command.upgrade(alembic_cfg, "head")
        sync_engine.dispose()


# ---------------------------------------------------------------------------
# Scenario 6 — 빈 테이블 downgrade — 016 으로 복원 후 precision 원복
# ---------------------------------------------------------------------------


def test_migration_017_downgrade_restores_original_precision_when_no_overflow_data(
    database_url: str,
) -> None:
    """overflow 데이터 없을 때 downgrade 017→016 성공 + trade_compare_rate / low_250d_pre_rate precision 원복.

    downgrade 후 precision=8 (NUMERIC(8,4)) 임을 information_schema 로 검증.
    검증 후 upgrade head 로 복원 (다른 테스트 영향 없도록).
    """
    sync_engine = sa.create_engine(database_url.replace("+asyncpg", "+psycopg2"))
    alembic_cfg = _make_alembic_cfg(database_url)

    try:
        # stock_fundamental 데이터 없는 상태 확인 후 downgrade
        with sync_engine.connect() as conn:
            count = conn.execute(
                sa.text("SELECT COUNT(*) FROM kiwoom.stock_fundamental")
            ).scalar_one()

        if count > 0:
            pytest.skip(
                f"stock_fundamental 에 데이터 {count}건 — overflow 없어도 다른 테스트 데이터 있음. "
                "테스트 실행 순서 / 격리 확인 필요. downgrade 회귀 스킵."
            )

        command.downgrade(alembic_cfg, "016_short_lending")

        # precision 원복 확인
        with sync_engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT column_name, numeric_precision, numeric_scale "
                    "FROM information_schema.columns "
                    "WHERE table_schema = 'kiwoom' "
                    "  AND table_name = 'stock_fundamental' "
                    "  AND column_name IN ('trade_compare_rate', 'low_250d_pre_rate')"
                )
            ).fetchall()
            col_map = {row[0]: (row[1], row[2]) for row in rows}

        for col, expected_precision in [
            ("trade_compare_rate", ORIGINAL_PRECISION),
            ("low_250d_pre_rate", ORIGINAL_PRECISION),
        ]:
            assert col in col_map, f"downgrade 후 {col} 컬럼 조회 실패"
            precision, scale = col_map[col]
            assert precision == expected_precision, (
                f"downgrade 후 {col} precision={expected_precision} 기대, 실제={precision}"
            )
            assert scale == ORIGINAL_SCALE, (
                f"downgrade 후 {col} scale={ORIGINAL_SCALE} 기대, 실제={scale}"
            )

    finally:
        # head 로 복원 — 다른 테스트가 head 상태 기대
        command.upgrade(alembic_cfg, "head")
        sync_engine.dispose()
