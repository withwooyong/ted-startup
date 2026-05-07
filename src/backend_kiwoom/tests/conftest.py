"""Testcontainers 기반 통합 테스트 공용 픽스처 (backend_kiwoom).

세션 스코프 PostgreSQL 16 컨테이너 1회 부팅 → Alembic `upgrade head` → kiwoom 스키마 + 3 테이블 생성.
각 테스트는 자체 트랜잭션 안에서 실행 후 무조건 롤백 → 테스트 간 격리.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio

if "DOCKER_HOST" not in os.environ:
    candidate = Path.home() / ".docker" / "run" / "docker.sock"
    if candidate.exists():
        os.environ["DOCKER_HOST"] = f"unix://{candidate}"
        os.environ.setdefault("TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE", str(candidate))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from cryptography.fernet import Fernet  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer  # noqa: E402


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """세션 스코프 PG16 컨테이너."""
    with PostgresContainer(
        image="postgres:16-alpine",
        username="test",
        password="test",
        dbname="kiwoom_test",
        driver="asyncpg",
    ) as pg:
        yield pg


@pytest.fixture(scope="session")
def database_url(postgres_container: PostgresContainer) -> str:
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session")
def master_key() -> str:
    """테스트 전용 Fernet 마스터키 — 운영과 무관."""
    return Fernet.generate_key().decode()


@pytest.fixture(scope="session", autouse=True)
def apply_migrations(database_url: str, master_key: str) -> None:
    """Alembic upgrade head — 테스트 DB URL과 마스터키를 환경변수로 주입."""
    os.environ["DATABASE_URL"] = database_url
    if "KIWOOM_CREDENTIAL_MASTER_KEY" not in os.environ:
        os.environ["KIWOOM_CREDENTIAL_MASTER_KEY"] = master_key

    from app.config.settings import get_settings

    get_settings.cache_clear()

    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_cfg, "head")


@pytest_asyncio.fixture
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(database_url, pool_pre_ping=True)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """각 테스트는 트랜잭션 안에서 실행 후 무조건 롤백."""
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        await s.begin()
        try:
            yield s
        finally:
            await s.rollback()
