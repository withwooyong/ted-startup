from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.adapter.web._error_handler import register_exception_handlers
from app.adapter.web.routers import api_router
from app.config.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
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

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "UP", "app": settings.app_name, "env": settings.app_env}

    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
