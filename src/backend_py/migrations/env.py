"""Alembic env — 마이그레이션은 동기 psycopg2 로 실행(앱 런타임만 asyncpg).

이 분리가 표준 패턴인 이유:
- asyncpg 는 한 번의 execute 에 다중 SQL 문(DO $$ ... $$; CREATE TABLE ...)을 허용하지 않음
- 마이그레이션은 배포 시 1회성이라 동기 드라이버가 도리어 단순·안정
- 앱 워크로드(요청 처리, 배치)만 asyncpg 로 고성능 이점 유지
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.adapter.out.persistence.base import Base
from app.adapter.out.persistence.models import *  # noqa: F401, F403  — 메타데이터 등록
from app.config.settings import get_settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _resolve_sync_url() -> str:
    """테스트에서 set_main_option 한 URL이 있으면 우선, 없으면 Settings 기본값.
    어느 쪽이든 asyncpg → psycopg2 로 드라이버 치환."""
    url = config.get_main_option("sqlalchemy.url") or ""
    if not url or "signal_db" in url:
        url = get_settings().database_url
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
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
