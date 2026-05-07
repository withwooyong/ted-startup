"""FastAPI 진입점 — α chunk 발급 라우터만 포함.

β chunk 에서 lifespan graceful shutdown + revoke 라우터 추가 예정.

세션 라이프사이클 (H4 적대적 리뷰):
- TokenManager 가 session_provider 주입 받아 매 발급마다 session 생성 + close 보장
- sessionmaker() 호출은 AsyncSession 반환 — 이는 자체로 async context manager
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom.auth import KiwoomAuthClient
from app.adapter.out.persistence.session import get_engine, get_sessionmaker
from app.adapter.web._deps import set_token_manager
from app.adapter.web.routers.auth import router as auth_router
from app.application.service.token_service import TokenManager
from app.config.settings import get_settings
from app.observability.logging import setup_logging
from app.security.kiwoom_credential_cipher import KiwoomCredentialCipher


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(
        log_level=settings.log_level,
        json_output=settings.app_env != "local",
    )
    cipher = KiwoomCredentialCipher(master_key=settings.kiwoom_credential_master_key)
    sessionmaker = get_sessionmaker()

    def _session_provider() -> AbstractAsyncContextManager[AsyncSession]:
        # AsyncSession 자체가 async context manager — `async with` 로 자동 close
        return sessionmaker()

    def _auth_client_factory(base_url: str) -> KiwoomAuthClient:
        return KiwoomAuthClient(base_url=base_url)

    manager = TokenManager(
        session_provider=_session_provider,
        cipher=cipher,
        auth_client_factory=_auth_client_factory,
    )
    set_token_manager(manager)

    yield

    # β 에서 graceful shutdown — 활성 토큰 폐기. 현재 α 는 engine dispose 만.
    await get_engine().dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        lifespan=_lifespan,
    )
    app.include_router(auth_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
