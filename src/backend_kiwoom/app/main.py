"""FastAPI 진입점 — α (발급) + β (폐기 + lifespan graceful shutdown).

세션 라이프사이클 (H4 α 적대적 리뷰):
- TokenManager 가 session_provider 주입 받아 매 발급마다 session 생성 + close 보장

Graceful shutdown (β):
- lifespan yield 후 활성 alias 전부 폐기 시도 (best-effort, asyncio.wait_for 타임아웃)
- 한 alias 실패해도 다른 alias 진행 — `revoke_all_aliases_best_effort`
- 종료 직전 invalidate_all — 모든 캐시 비움
- engine.dispose() 는 revoke hang 시에도 도달 보장 (분리된 try/finally — H-3 적대적 리뷰)

ValidationError 핸들러 (β C-1 적대적 리뷰):
- 민감 경로(`/revoke-raw`)에서 422 응답 본문에 token 평문이 echo 되지 않도록
  loc/type/msg 만 노출하고 input/ctx 제거.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any, Final

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom.auth import KiwoomAuthClient
from app.adapter.out.persistence.session import get_engine, get_sessionmaker
from app.adapter.web._deps import set_revoke_use_case, set_token_manager
from app.adapter.web.routers.auth import router as auth_router
from app.application.service.token_service import (
    RevokeKiwoomTokenUseCase,
    TokenManager,
    revoke_all_aliases_best_effort,
)
from app.config.settings import get_settings
from app.observability.logging import setup_logging
from app.security.kiwoom_credential_cipher import KiwoomCredentialCipher

logger = logging.getLogger(__name__)

# β C-1 — 422 응답에 input 평문 echo 차단 대상 경로.
# /revoke-raw body 가 token 평문을 담음 — ValidationError input 노출 시 민감 정보 누설.
_SENSITIVE_VALIDATION_PATHS: Final[frozenset[str]] = frozenset({"/api/kiwoom/auth/tokens/revoke-raw"})

SHUTDOWN_REVOKE_TIMEOUT_SECONDS: Final[float] = 20.0
"""shutdown 일괄 폐기 글로벌 타임아웃 — k8s SIGKILL 30s grace 전 안전 마진."""


def _scrubbed_validation_error(exc: RequestValidationError) -> list[dict[str, Any]]:
    """ValidationError errors 에서 input/ctx 제거 — 토큰/비밀 echo 차단."""
    safe: list[dict[str, Any]] = []
    for err in exc.errors():
        safe.append(
            {
                "type": err.get("type", "validation_error"),
                "loc": err.get("loc", []),
                "msg": err.get("msg", ""),
            }
        )
    return safe


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
        return sessionmaker()

    def _auth_client_factory(base_url: str) -> KiwoomAuthClient:
        return KiwoomAuthClient(base_url=base_url)

    manager = TokenManager(
        session_provider=_session_provider,
        cipher=cipher,
        auth_client_factory=_auth_client_factory,
    )
    revoke_uc = RevokeKiwoomTokenUseCase(
        session_provider=_session_provider,
        cipher=cipher,
        auth_client_factory=_auth_client_factory,
        token_manager=manager,
    )
    set_token_manager(manager)
    set_revoke_use_case(revoke_uc)

    try:
        yield
    finally:
        # H-3 적대적 리뷰: revoke 실패/hang/cancel 와 무관하게 engine.dispose() 도달 보장
        try:
            await asyncio.wait_for(
                revoke_all_aliases_best_effort(manager=manager, revoke_use_case=revoke_uc),
                timeout=SHUTDOWN_REVOKE_TIMEOUT_SECONDS,
            )
        except (TimeoutError, asyncio.TimeoutError):  # noqa: UP041 — Py3.11+ alias
            logger.warning(
                "graceful shutdown 일괄 폐기 timeout — %s초 초과, 잔여 alias 미폐기",
                SHUTDOWN_REVOKE_TIMEOUT_SECONDS,
            )
            manager.invalidate_all()
        except asyncio.CancelledError:
            logger.warning("graceful shutdown cancelled — 잔여 alias 미폐기")
            manager.invalidate_all()
            raise
        except Exception as exc:  # noqa: BLE001 — shutdown 은 모든 예외 swallow
            logger.warning("graceful shutdown 일괄 폐기 실패: %s", type(exc).__name__)
            manager.invalidate_all()
        finally:
            await get_engine().dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        lifespan=_lifespan,
    )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # 민감 경로는 input/ctx 필드 제거 — 토큰 평문 echo 차단 (C-1 적대적 리뷰)
        if request.url.path in _SENSITIVE_VALIDATION_PATHS:
            return JSONResponse(
                status_code=422,
                content={"detail": _scrubbed_validation_error(exc)},
            )
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    app.include_router(auth_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
