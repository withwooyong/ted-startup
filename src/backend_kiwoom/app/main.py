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

from app.adapter.out.kiwoom._client import KiwoomClient
from app.adapter.out.kiwoom.auth import KiwoomAuthClient
from app.adapter.out.kiwoom.stkinfo import KiwoomStkInfoClient
from app.adapter.out.persistence.session import get_engine, get_sessionmaker
from app.adapter.web._deps import (
    reset_lookup_stock_factory,
    reset_sync_sector_factory,
    reset_sync_stock_factory,
    set_lookup_stock_factory,
    set_revoke_use_case,
    set_sync_sector_factory,
    set_sync_stock_factory,
    set_token_manager,
)
from app.adapter.web.routers.auth import router as auth_router
from app.adapter.web.routers.sectors import router as sectors_router
from app.adapter.web.routers.stocks import router as stocks_router
from app.application.service.sector_service import SyncSectorMasterUseCase
from app.application.service.stock_master_service import (
    LookupStockUseCase,
    SyncStockMasterUseCase,
)
from app.application.service.token_service import (
    RevokeKiwoomTokenUseCase,
    TokenManager,
    revoke_all_aliases_best_effort,
)
from app.config.settings import get_settings
from app.observability.logging import setup_logging
from app.scheduler import SectorSyncScheduler, StockMasterScheduler
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

    # A3-β: SyncSectorUseCaseFactory — alias 단위 KiwoomClient 빌드 + close 보장.
    # `async with factory(alias) as use_case:` 패턴으로 라우터에서 사용.
    @asynccontextmanager
    async def _sync_sector_factory(alias: str) -> AsyncIterator[SyncSectorMasterUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        # alias 의 환경 (prod/mock) 결정 — 자격증명 row 의 env 컬럼 기반
        # 현재는 settings 의 default base_url_prod 사용 (mock 사용은 운영 dry-run 후 결정)
        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            stkinfo = KiwoomStkInfoClient(kiwoom_client)
            yield SyncSectorMasterUseCase(
                session_provider=_session_provider,
                stkinfo_client=stkinfo,
            )
        finally:
            await kiwoom_client.close()

    set_sync_sector_factory(_sync_sector_factory)

    # B-α: SyncStockMasterUseCaseFactory — sector factory 와 동일 패턴.
    #
    # mock_env 결정 정책 (1R H-1 적대적 리뷰):
    # - 운영 가정: **프로세스당 단일 env** (한 프로세스에서 prod alias + mock alias 혼용 안 함)
    # - settings.kiwoom_default_env 가 진실의 원천 — 프로세스 시작 시 lifespan 1회 결정
    # - 만약 향후 멀티 env 동시 운영이 필요하면, factory 안에서 alias 의 자격증명 row
    #   (kiwoom_credential.env 컬럼) 를 조회해 alias 단위로 mock_env 를 결정하도록 변경 필요
    # - 현재는 H-1 위험을 운영 가정으로 차단 (ADR-0001 § 운영 정책에 명시)
    stock_mock_env = settings.kiwoom_default_env == "mock"

    @asynccontextmanager
    async def _sync_stock_factory(alias: str) -> AsyncIterator[SyncStockMasterUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            stkinfo = KiwoomStkInfoClient(kiwoom_client)
            yield SyncStockMasterUseCase(
                session_provider=_session_provider,
                stkinfo_client=stkinfo,
                mock_env=stock_mock_env,
            )
        finally:
            await kiwoom_client.close()

    set_sync_stock_factory(_sync_stock_factory)

    # B-β: LookupStockUseCaseFactory — sync_stock factory 와 같은 패턴, 같은 mock_env 정책.
    # 단건 보강이므로 RPS 가 낮음 (admin 명시 호출 + Phase C 의 ensure_exists lazy fetch).
    @asynccontextmanager
    async def _lookup_stock_factory(alias: str) -> AsyncIterator[LookupStockUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            stkinfo = KiwoomStkInfoClient(kiwoom_client)
            yield LookupStockUseCase(
                session_provider=_session_provider,
                stkinfo_client=stkinfo,
                mock_env=stock_mock_env,
            )
        finally:
            await kiwoom_client.close()

    set_lookup_stock_factory(_lookup_stock_factory)

    # A3-γ: SectorSyncScheduler — settings.scheduler_enabled=True 일 때만 실제 cron 등록.
    # alias 미설정 + scheduler_enabled=True 면 fail-fast (운영 실수 방어).
    if settings.scheduler_enabled and not settings.scheduler_sector_sync_alias:
        raise RuntimeError("scheduler_enabled=True 인데 scheduler_sector_sync_alias 미설정 — 운영 실수 방어 fail-fast")
    if settings.scheduler_enabled and not settings.scheduler_stock_sync_alias:
        raise RuntimeError("scheduler_enabled=True 인데 scheduler_stock_sync_alias 미설정 — 운영 실수 방어 fail-fast")
    scheduler = SectorSyncScheduler(
        factory=_sync_sector_factory,
        alias=settings.scheduler_sector_sync_alias,
        enabled=settings.scheduler_enabled,
    )
    scheduler.start()

    stock_scheduler = StockMasterScheduler(
        factory=_sync_stock_factory,
        alias=settings.scheduler_stock_sync_alias,
        enabled=settings.scheduler_enabled,
    )
    stock_scheduler.start()

    try:
        yield
    finally:
        # A3-γ: scheduler 먼저 정지 — 실행 중 cron job 의 KiwoomClient 호출이
        # graceful token revoke 와 충돌하지 않도록 보장.
        # B-α: stock scheduler 도 같은 시점에 정지.
        stock_scheduler.shutdown(wait=True)
        scheduler.shutdown(wait=True)

        # 1R 2b M4: factory 싱글톤 unset — close 후 stale factory 가 라우터에 노출되지
        # 않도록 fail-closed 강화. teardown 직전 신규 요청은 503 (factory 미초기화) 반환.
        reset_lookup_stock_factory()
        reset_sync_stock_factory()
        reset_sync_sector_factory()

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
    app.include_router(sectors_router)
    app.include_router(stocks_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
