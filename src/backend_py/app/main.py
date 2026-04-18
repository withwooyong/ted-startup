from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.adapter.web._error_handler import register_exception_handlers
from app.adapter.web.routers import api_router
from app.batch.scheduler import build_scheduler
from app.config.settings import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    scheduler = None
    if settings.scheduler_enabled:
        scheduler = build_scheduler(settings)
        scheduler.start()
        logger.info(
            "배치 스케줄러 기동: KST %02d:%02d 월~금",
            settings.scheduler_hour_kst, settings.scheduler_minute_kst,
        )
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
            logger.info("배치 스케줄러 종료")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
        lifespan=_lifespan,
    )

    # 명시 화이트리스트에 있을 때만 CORS 활성화. 와일드카드(["*"])는 credentials와 함께 금지.
    allowed_origins = [o for o in settings.cors_allow_origins if o and o != "*"]
    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Admin-Api-Key", "X-API-Key"],
            max_age=600,
        )

    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    # 외부 공개용 — 상태 코드만 반환. app/env 같은 런타임 메타는 노출하지 않는다.
    # Caddyfile 은 /metrics 와 /internal/* 를 404 로 막으므로, 상세 진단은
    # Docker 내부에서 `curl backend:8000/internal/info` 로 접근한다.
    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "UP"}

    @app.get("/internal/info", tags=["meta"], include_in_schema=False)
    def internal_info() -> dict[str, str]:
        return {"status": "UP", "app": settings.app_name, "env": settings.app_env}

    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
