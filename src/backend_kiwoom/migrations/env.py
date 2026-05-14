"""Alembic env — 마이그레이션은 동기 psycopg2 (앱 런타임만 asyncpg).

asyncpg 가 한 번의 execute 에 다중 SQL (DO $$ ... $$; CREATE TABLE ...) 을 허용하지 않으므로
마이그레이션 단계만 psycopg2 로 분리. 운영 워크로드는 asyncpg.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.adapter.out.persistence.base import Base
from app.adapter.out.persistence.models import *  # noqa: F401, F403 — 메타데이터 등록
from app.config.settings import get_settings

config = context.config
if config.config_file_name is not None:
    # Phase F-2: disable_existing_loggers=False — fileConfig 기본값(True)이
    # 기존 로거 ("app" 등) 를 disabled=True 로 만들어 후속 테스트의 caplog
    # 캡처가 깨지는 회귀 차단 (test_migration_*.py 가 alembic 재호출 시 영향).
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def _resolve_sync_url() -> str:
    """set_main_option 우선, 없으면 Settings. asyncpg → psycopg2 치환."""
    url = config.get_main_option("sqlalchemy.url") or ""
    if not url:
        url = get_settings().kiwoom_database_url
    return url.replace("+asyncpg", "+psycopg2")


sync_url = _resolve_sync_url()
config.set_main_option("sqlalchemy.url", sync_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=sync_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table_schema="kiwoom",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # kiwoom 스키마가 존재하지 않을 수 있어 alembic_version 위치 결정 전 생성.
        from sqlalchemy import text

        connection.execute(text("CREATE SCHEMA IF NOT EXISTS kiwoom"))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table_schema="kiwoom",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
