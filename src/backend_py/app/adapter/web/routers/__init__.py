"""모든 라우터 모음."""
from __future__ import annotations

from fastapi import APIRouter

from app.adapter.web.routers.backtest import router as backtest_router
from app.adapter.web.routers.batch import router as batch_router
from app.adapter.web.routers.notifications import router as notifications_router
from app.adapter.web.routers.signals import router as signals_router

api_router = APIRouter()
api_router.include_router(signals_router)
api_router.include_router(backtest_router)
api_router.include_router(notifications_router)
api_router.include_router(batch_router)

__all__ = ["api_router"]
