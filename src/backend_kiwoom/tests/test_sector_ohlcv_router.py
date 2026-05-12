"""POST /api/kiwoom/sectors/{id}/ohlcv/daily/refresh + POST /api/kiwoom/sectors/ohlcv/daily/sync (D-1).

chunk = D-1, plan doc § 12 참조.

test_ohlcv_router.py 의 sync 전체 + refresh 단건 + admin API key 검증 패턴 1:1 응용.

검증:
- POST /sectors/ohlcv/daily/sync — admin 인증 + 정상 응답
- POST /sectors/ohlcv/daily/sync — 401 without admin
- POST /sectors/{id}/ohlcv/daily/refresh — admin 인증 + 정상 응답
- POST /sectors/{id}/ohlcv/daily/refresh — 401 without admin
- admin API key 비교 (X-API-Key 헤더)
- ValueError → 400 매핑
- sector_master_missing → 404 매핑
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.adapter.web._deps import get_ingest_sector_daily_factory
from app.adapter.web.routers.sector_ohlcv import router as sector_ohlcv_router
from app.application.service.sector_ohlcv_service import (
    IngestSectorDailyBulkUseCase,
    SectorBulkSyncResult,
    SectorIngestOutcome,
)


@pytest.fixture(autouse=True)
def _clear_global_engine_cache() -> Iterator[None]:
    """stale event loop binding 해소."""
    from app.adapter.out.persistence.session import get_engine, get_sessionmaker

    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    yield
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()


@pytest.fixture
def admin_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """ADMIN_API_KEY 환경변수 주입."""
    key = "test-admin-key-sector-ohlcv"
    monkeypatch.setenv("ADMIN_API_KEY", key)
    from app.config.settings import get_settings

    get_settings.cache_clear()
    yield key
    get_settings.cache_clear()


@pytest_asyncio.fixture(autouse=True)
async def _cleanup(engine: AsyncEngine) -> AsyncIterator[None]:
    """테스트 전후 sector 정리."""
    from sqlalchemy import text

    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        await s.execute(text("TRUNCATE kiwoom.sector RESTART IDENTITY CASCADE"))
        await s.commit()
    yield
    async with factory() as s:
        await s.execute(text("TRUNCATE kiwoom.sector RESTART IDENTITY CASCADE"))
        await s.commit()


def _make_bulk_result(total: int = 3, success: int = 3, failed: int = 0) -> SectorBulkSyncResult:
    """테스트용 bulk result stub."""
    return SectorBulkSyncResult(
        total=total,
        success=success,
        failed=failed,
        errors=(),
    )


def _stub_factory(uc: IngestSectorDailyBulkUseCase) -> Any:
    @asynccontextmanager
    async def _factory(_alias: str) -> AsyncIterator[IngestSectorDailyBulkUseCase]:
        yield uc

    return _factory


def _make_app(factory: Any = None) -> FastAPI:
    app = FastAPI()
    app.include_router(sector_ohlcv_router)
    if factory is not None:
        app.dependency_overrides[get_ingest_sector_daily_factory] = lambda: factory
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


# =============================================================================
# POST /sectors/ohlcv/daily/sync — bulk admin
# =============================================================================


@pytest.mark.asyncio
async def test_sync_returns_401_without_admin(admin_key: str) -> None:
    """admin 키 없이 sync → 401."""
    app = _make_app()
    async with _client(app) as cl:
        resp = await cl.post("/api/kiwoom/sectors/ohlcv/daily/sync?alias=test")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_sync_returns_200_for_admin(admin_key: str) -> None:
    """admin 키 포함 sync → 200 + 결과 반환."""
    uc = AsyncMock(spec=IngestSectorDailyBulkUseCase)
    uc.execute = AsyncMock(return_value=_make_bulk_result())
    app = _make_app(_stub_factory(uc))

    async with _client(app) as cl:
        resp = await cl.post(
            "/api/kiwoom/sectors/ohlcv/daily/sync?alias=test",
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["success"] == 3


@pytest.mark.asyncio
async def test_sync_maps_value_error_to_400(admin_key: str) -> None:
    """ValueError → 400 매핑."""
    uc = AsyncMock(spec=IngestSectorDailyBulkUseCase)
    uc.execute = AsyncMock(side_effect=ValueError("invalid base_date"))
    app = _make_app(_stub_factory(uc))

    async with _client(app) as cl:
        resp = await cl.post(
            "/api/kiwoom/sectors/ohlcv/daily/sync?alias=test",
            headers={"X-API-Key": admin_key},
        )
    assert resp.status_code == 400


# =============================================================================
# POST /sectors/{id}/ohlcv/daily/refresh — 단건 admin
# =============================================================================


@pytest.mark.asyncio
async def test_refresh_returns_401_without_admin(admin_key: str) -> None:
    """admin 키 없이 refresh → 401."""
    app = _make_app()
    async with _client(app) as cl:
        resp = await cl.post("/api/kiwoom/sectors/1/ohlcv/daily/refresh?alias=test")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_returns_200_for_admin(admin_key: str) -> None:
    """admin 키 포함 단건 refresh → 200."""
    from app.application.service.sector_ohlcv_service import IngestSectorDailyUseCase

    uc = AsyncMock(spec=IngestSectorDailyUseCase)
    uc.execute = AsyncMock(
        return_value=SectorIngestOutcome(skipped=False, upserted=1, reason=None)
    )

    @asynccontextmanager
    async def _single_factory(_alias: str) -> AsyncIterator[IngestSectorDailyUseCase]:
        yield uc

    app = FastAPI()
    app.include_router(sector_ohlcv_router)
    from app.adapter.web._deps import get_ingest_sector_single_factory

    app.dependency_overrides[get_ingest_sector_single_factory] = lambda: _single_factory

    async with _client(app) as cl:
        resp = await cl.post(
            "/api/kiwoom/sectors/1/ohlcv/daily/refresh?alias=test",
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["skipped"] is False
    assert body["upserted"] == 1


@pytest.mark.asyncio
async def test_refresh_sector_master_missing_returns_404(admin_key: str) -> None:
    """sector_master_missing skip → 404."""
    from app.application.service.sector_ohlcv_service import IngestSectorDailyUseCase

    uc = AsyncMock(spec=IngestSectorDailyUseCase)
    uc.execute = AsyncMock(
        return_value=SectorIngestOutcome(skipped=True, reason="sector_master_missing")
    )

    @asynccontextmanager
    async def _single_factory(_alias: str) -> AsyncIterator[IngestSectorDailyUseCase]:
        yield uc

    app = FastAPI()
    app.include_router(sector_ohlcv_router)
    from app.adapter.web._deps import get_ingest_sector_single_factory

    app.dependency_overrides[get_ingest_sector_single_factory] = lambda: _single_factory

    async with _client(app) as cl:
        resp = await cl.post(
            "/api/kiwoom/sectors/9999999/ohlcv/daily/refresh?alias=test",
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 404
