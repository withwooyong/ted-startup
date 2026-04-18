"""FastAPI Depends 모음 — 세션·KRX 클라이언트·관리자 API Key 검증."""
from __future__ import annotations

import hmac
from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.external import KisClient, KrxClient, TelegramClient
from app.adapter.out.persistence.session import get_sessionmaker
from app.config.settings import Settings, get_settings


async def get_session() -> AsyncIterator[AsyncSession]:
    """요청 스코프 세션 — 정상 종료 시 커밋, 예외 시 롤백."""
    factory = get_sessionmaker()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@lru_cache(maxsize=1)
def get_krx_client() -> KrxClient:
    return KrxClient()


async def get_kis_client() -> AsyncIterator[KisClient]:
    """요청 스코프 KIS 클라이언트 — httpx 커넥션 풀은 요청 종료 시 정리.

    토큰 캐시는 인스턴스 단위라 요청마다 재발급되지만, /sync 가 저빈도 관리자
    엔드포인트라 수용 가능. 고빈도화 시점에 프로세스 공유 인스턴스로 전환.
    """
    client = KisClient()
    try:
        yield client
    finally:
        await client.close()


def get_telegram_client() -> TelegramClient:
    # 프로세스 수명 공유 가능하나 테스트 주입 용이성 위해 매 요청 생성(httpx 내부 커넥션 풀은 짧은 수명 허용).
    return TelegramClient()


def require_admin_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    settings: Settings = Depends(get_settings),
) -> None:
    """관리자 API Key 검증 — fail-closed + timing-safe 비교.

    signal.admin_api_key 가 빈 값이면 모든 요청을 401로 거부.
    """
    expected = settings.admin_api_key
    if not expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin API key 미설정")
    provided = x_api_key or ""
    # 길이 차이도 timing leak 을 피하기 위해 고정 길이 비교
    if not hmac.compare_digest(expected.encode("utf-8"), provided.encode("utf-8")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
