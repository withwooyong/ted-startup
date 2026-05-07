"""Alembic Migration 001 양방향 검증 — upgrade head + downgrade 안전성.

검증:
- upgrade 후 kiwoom 스키마 + 3 테이블 (kiwoom_credential / kiwoom_token / raw_response) 존재
- 인덱스/제약 (alias UNIQUE, credential_id UNIQUE on kiwoom_token) 존재
- 빈 DB 에서 downgrade base 가능 (데이터 0건일 때만)
- 재 upgrade 가능 (멱등성)
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.asyncio
async def test_migration_creates_kiwoom_schema(engine: AsyncEngine) -> None:
    """kiwoom 스키마가 존재해야 함."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'kiwoom'")
        )
        assert result.scalar_one_or_none() == "kiwoom"


@pytest.mark.asyncio
async def test_migration_creates_three_tables(engine: AsyncEngine) -> None:
    """kiwoom 스키마에 kiwoom_credential, kiwoom_token, raw_response 3 테이블."""
    async with engine.connect() as conn:

        def _list_tables(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            return set(insp.get_table_names(schema="kiwoom"))

        tables = await conn.run_sync(_list_tables)

    assert "kiwoom_credential" in tables
    assert "kiwoom_token" in tables
    assert "raw_response" in tables


@pytest.mark.asyncio
async def test_kiwoom_credential_alias_unique_constraint(engine: AsyncEngine) -> None:
    """alias UNIQUE 제약."""
    async with engine.connect() as conn:

        def _has_unique(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            uniques = insp.get_unique_constraints("kiwoom_credential", schema="kiwoom")
            return any("alias" in u["column_names"] for u in uniques)

        # PostgreSQL 은 UNIQUE 를 일반 인덱스로도 노출 — UNIQUE constraint 또는 unique index 둘 다 검색
        def _has_unique_index(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            indexes = insp.get_indexes("kiwoom_credential", schema="kiwoom")
            return any(idx.get("unique") and "alias" in idx.get("column_names", []) for idx in indexes)

        ok = await conn.run_sync(_has_unique) or await conn.run_sync(_has_unique_index)
        assert ok, "kiwoom_credential.alias UNIQUE 제약이 없음"


@pytest.mark.asyncio
async def test_kiwoom_token_credential_id_unique(engine: AsyncEngine) -> None:
    """kiwoom_token.credential_id UNIQUE — 자격증명당 활성 토큰 1개."""
    async with engine.connect() as conn:

        def _check(sync_conn):  # type: ignore[no-untyped-def]
            insp = inspect(sync_conn)
            uniques = insp.get_unique_constraints("kiwoom_token", schema="kiwoom")
            unique_idx = insp.get_indexes("kiwoom_token", schema="kiwoom")
            has_uq = any("credential_id" in u["column_names"] for u in uniques)
            has_idx = any(idx.get("unique") and "credential_id" in idx.get("column_names", []) for idx in unique_idx)
            return has_uq or has_idx

        assert await conn.run_sync(_check)


@pytest.mark.asyncio
async def test_kiwoom_credential_bytea_columns(engine: AsyncEngine) -> None:
    """appkey_cipher, secretkey_cipher 가 BYTEA 타입."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'kiwoom' AND table_name = 'kiwoom_credential'
                  AND column_name IN ('appkey_cipher', 'secretkey_cipher')
                """
            )
        )
        rows = {r[0]: r[1] for r in result.fetchall()}
    assert rows.get("appkey_cipher") == "bytea"
    assert rows.get("secretkey_cipher") == "bytea"


@pytest.mark.asyncio
async def test_raw_response_jsonb_columns(engine: AsyncEngine) -> None:
    """request_payload, response_payload 가 jsonb 타입."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'kiwoom' AND table_name = 'raw_response'
                  AND column_name IN ('request_payload', 'response_payload')
                """
            )
        )
        rows = {r[0]: r[1] for r in result.fetchall()}
    assert rows.get("request_payload") == "jsonb"
    assert rows.get("response_payload") == "jsonb"


def test_migration_downgrade_then_upgrade_idempotent(database_url: str) -> None:
    """빈 DB 에서 downgrade base → upgrade head 멱등성."""
    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    # 데이터가 없는 상태이므로 downgrade 안전
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")

    # 후처리 없이 다음 테스트도 통과해야 함
