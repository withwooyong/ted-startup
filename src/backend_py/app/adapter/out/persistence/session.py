from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config.settings import Settings, get_settings


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """프로세스당 1회 생성되는 async 엔진 싱글톤."""
    s: Settings = get_settings()
    return create_async_engine(
        s.database_url,
        echo=s.database_echo,
        pool_pre_ping=True,
        pool_size=s.database_pool_size,
        max_overflow=s.database_max_overflow,
    )


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=get_engine(), expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI Depends 용 세션 의존성. 요청 스코프 내 자동 commit/rollback."""
    factory = get_sessionmaker()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
