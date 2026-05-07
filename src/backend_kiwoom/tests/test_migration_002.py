"""Alembic Migration 002 양방향 검증 — kiwoom.sector 테이블.

검증:
- upgrade head 후 sector 테이블 + UNIQUE(market_code, sector_code) + CHECK + 2 인덱스 존재
- 빈 DB 에서 downgrade 002 → 001 가능 (sector 테이블 drop)
- 재 upgrade head 가능 (멱등성)
- market_code CHECK constraint 강제 — '3' 같은 무효값 거부
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.asyncio
async def test_migration_creates_sector_table(engine: AsyncEngine) -> None:
    """kiwoom.sector 테이블 존재."""
    async with engine.connect() as conn:

        def _list_tables(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            return set(insp.get_table_names(schema="kiwoom"))

        tables = await conn.run_sync(_list_tables)

    assert "sector" in tables


@pytest.mark.asyncio
async def test_sector_unique_constraint_market_code_sector_code(engine: AsyncEngine) -> None:
    """UNIQUE(market_code, sector_code) 제약."""
    async with engine.connect() as conn:

        def _check(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            uniques = insp.get_unique_constraints("sector", schema="kiwoom")
            unique_idx = insp.get_indexes("sector", schema="kiwoom")
            has_uq = any(set(u["column_names"]) == {"market_code", "sector_code"} for u in uniques)
            has_idx = any(
                idx.get("unique") and set(idx.get("column_names", [])) == {"market_code", "sector_code"}
                for idx in unique_idx
            )
            return has_uq or has_idx

        assert await conn.run_sync(_check), "sector UNIQUE(market_code, sector_code) 부재"


@pytest.mark.asyncio
async def test_sector_market_code_check_constraint(engine: AsyncEngine) -> None:
    """CHECK (market_code IN ('0','1','2','4','7')) — 무효값 INSERT 거부."""
    async with engine.connect() as conn:
        async with conn.begin():
            await conn.execute(
                text(
                    "INSERT INTO kiwoom.sector (market_code, sector_code, sector_name) "
                    "VALUES ('0', '001', '코스피 정상')"
                )
            )
            # 정상 insert 후 rollback (다른 테스트 영향 없게)
            await conn.rollback()

        # 무효값 — '3' 은 CHECK 거부
        with pytest.raises(IntegrityError):
            async with conn.begin():
                await conn.execute(
                    text(
                        "INSERT INTO kiwoom.sector (market_code, sector_code, sector_name) "
                        "VALUES ('3', '001', '무효시장')"
                    )
                )


@pytest.mark.asyncio
async def test_sector_indexes_created(engine: AsyncEngine) -> None:
    """idx_sector_market + idx_sector_active 인덱스 존재."""
    async with engine.connect() as conn:

        def _check(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            idx_names = {idx["name"] for idx in insp.get_indexes("sector", schema="kiwoom")}
            return idx_names

        names = await conn.run_sync(_check)

    assert "idx_sector_market" in names
    assert "idx_sector_active" in names


@pytest.mark.asyncio
async def test_sector_columns_types(engine: AsyncEngine) -> None:
    """주요 컬럼 타입 — market_code/sector_code VARCHAR, is_active BOOLEAN, fetched_at TIMESTAMPTZ."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT column_name, data_type, character_maximum_length
                FROM information_schema.columns
                WHERE table_schema = 'kiwoom' AND table_name = 'sector'
                """
            )
        )
        rows = {r[0]: (r[1], r[2]) for r in result.fetchall()}

    assert rows["market_code"][0] == "character varying"
    assert rows["market_code"][1] == 2
    assert rows["sector_code"][0] == "character varying"
    assert rows["sector_code"][1] == 10
    assert rows["sector_name"][1] == 100
    assert rows["is_active"][0] == "boolean"
    assert rows["fetched_at"][0] == "timestamp with time zone"


def test_migration_002_downgrade_then_upgrade_idempotent(database_url: str) -> None:
    """빈 sector 테이블에서 downgrade 002 → upgrade head 멱등성."""
    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    # 데이터가 없는 상태에서만 안전 — 통합 테스트 컨테이너는 테스트 끝나면 폐기되지만,
    # 본 테스트가 이전 케이스 데이터를 남기지 않게 conftest session 트랜잭션 롤백 필수.
    command.downgrade(alembic_cfg, "001_init_kiwoom_schema")
    command.upgrade(alembic_cfg, "head")
