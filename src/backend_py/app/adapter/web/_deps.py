"""FastAPI Depends 모음 — 세션·KRX 클라이언트·관리자 API Key 검증."""

from __future__ import annotations

import hmac
from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.ai import OpenAIProvider
from app.adapter.out.external import (
    DartClient,
    KisClient,
    KrxClient,
    TelegramClient,
)
from app.adapter.out.persistence.session import get_sessionmaker
from app.application.dto.kis import KisCredentials, KisEnvironment
from app.application.port.out.kis_port import KisRealFetcherFactory
from app.application.port.out.llm_provider import LLMProvider
from app.config.settings import Settings, get_settings
from app.security.credential_cipher import CredentialCipher


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


async def get_dart_client() -> AsyncIterator[DartClient]:
    """요청 스코프 DART 클라이언트."""
    client = DartClient()
    try:
        yield client
    finally:
        await client.close()


async def get_llm_provider() -> AsyncIterator[LLMProvider]:
    """요청 스코프 AI 공급자. settings.ai_report_provider 로 Plan A/B 분기 가능하게
    확장 예정(MVP 는 openai 고정)."""
    provider = OpenAIProvider()
    try:
        yield provider
    finally:
        await provider.close()


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


def get_kis_real_client_factory() -> KisRealFetcherFactory:
    """실 KIS 호출용 팩토리 — credential 주입으로 REAL 환경 fetcher 생성.

    Port 타입 `KisRealFetcherFactory = Callable[[KisCredentials], KisHoldingsFetcher]`
    를 반환. `KisClient` 는 structural typing 으로 Protocol 을 자동 만족 — 컴포지션 루트는
    concrete adapter 를 주입하지만 application 은 Protocol 만 보게 된다.

    각 요청마다 새 클라이언트 — 계좌마다 credential 이 다르므로 토큰 캐시를 공유하지
    않는다. 반환된 factory 는 use case 내부에서 `async with factory(creds) as client:`
    로 사용해 httpx 커넥션 풀을 요청 종료 시 정리.

    테스트는 `app.dependency_overrides[get_kis_real_client_factory]` 로 MockTransport
    주입한 factory 로 치환 (CI 외부 호출 0).
    """

    def factory(credentials: KisCredentials) -> KisClient:
        return KisClient(environment=KisEnvironment.REAL, credentials=credentials)

    return factory


@lru_cache(maxsize=1)
def get_credential_cipher() -> CredentialCipher:
    """프로세스 수명 공유 Fernet cipher — 마스터키가 빈 값이면 기동 시 즉시 실패.

    `lru_cache` 로 인스턴스 1개만 유지해 매 요청마다 Fernet 초기화 비용을 피한다.
    테스트는 `dependency_overrides` 또는 `get_credential_cipher.cache_clear()` 로 격리.
    """
    settings = get_settings()
    return CredentialCipher(settings.kis_credential_master_key)


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
