"""Testcontainers 기반 통합 테스트 공용 픽스처.

세션 스코프 PostgreSQL 16 컨테이너 1회 부팅 → Alembic `upgrade head` 적용 →
각 테스트는 자체 트랜잭션(SAVEPOINT) 안에서 실행 후 롤백.
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio

# Docker Desktop on macOS 는 소켓을 ~/.docker/run/docker.sock 로 두지만 docker SDK 는
# 기본적으로 /var/run/docker.sock 을 찾는다. testcontainers 가 컨테이너를 띄우기 전에
# DOCKER_HOST 를 강제 지정해 연결 실패를 회피.
if "DOCKER_HOST" not in os.environ:
    candidate = Path.home() / ".docker" / "run" / "docker.sock"
    if candidate.exists():
        os.environ["DOCKER_HOST"] = f"unix://{candidate}"
        # Ryuk(reaper) 컨테이너가 같은 소켓을 바인드할 때 필요
        os.environ.setdefault("TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE", str(candidate))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer  # noqa: E402


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """세션 스코프 PG16 컨테이너. testcontainers 기본 이미지는 최신이라 16 명시."""
    with PostgresContainer(
        image="postgres:16-alpine",
        username="test",
        password="test",
        dbname="signal_test",
        driver="asyncpg",
    ) as pg:
        yield pg


@pytest.fixture(scope="session")
def database_url(postgres_container: PostgresContainer) -> str:
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session", autouse=True)
def apply_migrations(database_url: str) -> None:
    """Alembic upgrade head — 테스트 DB URL을 alembic 설정에 직접 주입."""
    # env.py 가 config.get_main_option("sqlalchemy.url") 를 우선 사용하도록 함
    os.environ["DATABASE_URL"] = database_url
    # PR 3 KIS credential cipher — 테스트 세션에서 Fernet 마스터키가 없으면
    # `CredentialCipher` 초기화가 실패하므로 더미 키 주입. 실 운영 키와 무관.
    if "KIS_CREDENTIAL_MASTER_KEY" not in os.environ:
        from cryptography.fernet import Fernet
        os.environ["KIS_CREDENTIAL_MASTER_KEY"] = Fernet.generate_key().decode()
    from app.config.settings import get_settings

    get_settings.cache_clear()
    # get_credential_cipher 는 lru_cache 싱글톤 — 테스트 환경에서 더미 마스터키가
    # 주입된 뒤에도 이전 세션의 cipher 인스턴스가 살아있을 수 있어 명시 초기화.
    from app.adapter.web._deps import get_credential_cipher
    get_credential_cipher.cache_clear()

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
    """각 테스트마다 새 트랜잭션을 열고 끝에 무조건 롤백 — 테스트 간 격리."""
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        await s.begin()
        try:
            yield s
        finally:
            await s.rollback()
