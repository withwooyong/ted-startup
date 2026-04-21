from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.adapter.web._error_handler import register_exception_handlers
from app.adapter.web._rate_limit import limiter
from app.adapter.web.routers import api_router
from app.batch.scheduler import build_scheduler
from app.config.settings import get_settings
from app.observability.logging import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    scheduler = None
    if settings.scheduler_enabled:
        scheduler = build_scheduler(settings)
        scheduler.start()
        logger.info(
            "배치 스케줄러 기동: market_data KST %02d:%02d 월~금 / backtest KST %02d:%02d %s (enabled=%s)",
            settings.scheduler_hour_kst,
            settings.scheduler_minute_kst,
            settings.backtest_cron_hour_kst,
            settings.backtest_cron_minute_kst,
            settings.backtest_cron_day_of_week,
            settings.backtest_enabled,
        )
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
            logger.info("배치 스케줄러 종료")


def create_app() -> FastAPI:
    settings = get_settings()
    # PR 6: 민감 데이터 마스킹 processor 포함 구조화 로깅 활성화. idempotent 이므로
    # 테스트 가 create_app() 을 여러 번 호출해도 핸들러가 누적되지 않는다.
    # 로컬 개발은 색상·읽기 쉬운 ConsoleRenderer, 운영은 JSONRenderer (로그 집계기 연동).
    setup_logging(log_level=settings.log_level, json_output=settings.app_env != "local")
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

    # slowapi 등록 — limiter.limit 데코레이터가 달린 라우트에서만 쿼터 검사.
    # 초과 시 RateLimitExceeded → 429 + Retry-After 헤더.
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    @app.exception_handler(RateLimitExceeded)
    def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"detail": f"rate limit exceeded: {exc.detail}"},
            headers={"Retry-After": "60"},
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
