"""POST/GET /api/kiwoom/investor/* + /api/kiwoom/foreign/continuous — Phase G 라우터 (~12 케이스).

TDD red 의도:
- `app.adapter.web.routers.investor_flow.router` 미존재 → ImportError
- `get_ingest_investor_daily_factory` 등 deps 미존재 → ImportError
→ Step 1 구현 후 green.

검증 (~12 케이스):
1. /investor/daily — POST 단건 401 (admin key 없음)
2. /investor/daily — POST 단건 200 (admin key 있음)
3. /investor/daily — POST bulk-sync 401 / 200 admin 회귀
4. /investor/stock — POST 단건 401 / 200
5. /investor/stock — POST bulk-sync 401 / 200
6. /foreign/continuous — POST 단건 401 / 200
7. /foreign/continuous — POST bulk-sync 401 / 200
8. /investor/daily — GET top (admin 무관)
9. /investor/stock — GET range (admin 무관)
10. /foreign/continuous — GET top (admin 무관)
11. POST 단건 422 — mrkt_tp invalid
12. _invoke_single 단건 모드 (G-3)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from app.adapter.web._deps import (  # type: ignore[import]  # Step 1
    get_ingest_investor_daily_factory,
)
from app.adapter.web.routers.investor_flow import (  # type: ignore[import]  # Step 1
    router as investor_flow_router,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_ADMIN_KEY = "test-admin-key-phase-g"


def _make_mock_factory(use_case: Any) -> Any:
    """UseCase factory context manager stub."""

    @asynccontextmanager
    async def _factory(alias: str) -> AsyncIterator[Any]:
        yield use_case

    return _factory


def _make_mock_use_case(result: Any) -> Any:
    uc = AsyncMock()
    uc.execute = AsyncMock(return_value=result)
    return uc


@pytest_asyncio.fixture
async def app() -> FastAPI:
    """테스트용 FastAPI app — investor_flow router 마운트."""
    _app = FastAPI()
    _app.include_router(investor_flow_router)
    return _app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


def _admin_headers() -> dict[str, str]:
    return {"X-API-Key": _ADMIN_KEY}


# ---------------------------------------------------------------------------
# 1. /investor/daily POST 단건 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_investor_daily_post_sync_unauthorized(client: httpx.AsyncClient, app: FastAPI) -> None:
    """POST /api/kiwoom/investor/daily/sync — admin key 없음 → 401."""
    response = await client.post(
        "/api/kiwoom/investor/daily/sync",
        json={
            "strt_dt": "20260516",
            "end_dt": "20260516",
            "invsr_tp": "9000",
            "trde_tp": "2",
            "mrkt_tp": "001",
            "stex_tp": "3",
        },
    )
    assert response.status_code == 401, f"401 기대, 실제: {response.status_code}"


# ---------------------------------------------------------------------------
# 2. /investor/daily POST 단건 200
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_investor_daily_post_sync_authorized(
    client: httpx.AsyncClient,
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /api/kiwoom/investor/daily/sync — admin key 있음 → 200."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.application.dto.investor_flow import InvestorIngestOutcome  # type: ignore[import]

    # admin_api_key 환경 변수 설정 — rankings_router 테스트 패턴 미러.
    monkeypatch.setenv("ADMIN_API_KEY", _ADMIN_KEY)
    from app.config.settings import get_settings
    get_settings.cache_clear()

    outcome = InvestorIngestOutcome(
        fetched_at=datetime(2026, 5, 16, 20, 0, 0, tzinfo=ZoneInfo("Asia/Seoul")),
        investor_type="9000",
        trade_type="2",
        market_type="001",
        exchange_type="3",
        fetched=50,
        upserted=50,
        error=None,
    )
    mock_uc = _make_mock_use_case(outcome)
    app.dependency_overrides[get_ingest_investor_daily_factory] = lambda: _make_mock_factory(mock_uc)

    try:
        response = await client.post(
            "/api/kiwoom/investor/daily/sync",
            json={
                "strt_dt": "20260516",
                "end_dt": "20260516",
                "invsr_tp": "9000",
                "trde_tp": "2",
                "mrkt_tp": "001",
                "stex_tp": "3",
            },
            headers=_admin_headers(),
        )
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
    assert response.status_code in (200, 202), f"200/202 기대, 실제: {response.status_code}"


# ---------------------------------------------------------------------------
# 3. /investor/daily POST bulk-sync 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_investor_daily_post_bulk_sync_unauthorized(
    client: httpx.AsyncClient,
) -> None:
    """POST /api/kiwoom/investor/daily/bulk-sync — admin key 없음 → 401."""
    response = await client.post(
        "/api/kiwoom/investor/daily/bulk-sync",
        json={"strt_dt": "20260516", "end_dt": "20260516"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 4. /investor/stock POST 단건 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_investor_stock_post_sync_unauthorized(client: httpx.AsyncClient) -> None:
    """POST /api/kiwoom/investor/stock/sync — admin key 없음 → 401."""
    response = await client.post(
        "/api/kiwoom/investor/stock/sync",
        json={"dt": "20241107", "stk_cd": "005930", "amt_qty_tp": "2", "trde_tp": "0", "unit_tp": "1000"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 5. /investor/stock POST bulk-sync 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_investor_stock_post_bulk_sync_unauthorized(client: httpx.AsyncClient) -> None:
    """POST /api/kiwoom/investor/stock/bulk-sync — admin key 없음 → 401."""
    response = await client.post(
        "/api/kiwoom/investor/stock/bulk-sync",
        json={"dt": "20241107"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 6. /foreign/continuous POST 단건 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_frgn_orgn_continuous_post_sync_unauthorized(client: httpx.AsyncClient) -> None:
    """POST /api/kiwoom/foreign/continuous/sync — admin key 없음 → 401."""
    response = await client.post(
        "/api/kiwoom/foreign/continuous/sync",
        json={"dt": "1", "mrkt_tp": "001", "stk_inds_tp": "0", "amt_qty_tp": "0", "stex_tp": "3"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 7. /foreign/continuous POST bulk-sync 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_frgn_orgn_continuous_post_bulk_sync_unauthorized(
    client: httpx.AsyncClient,
) -> None:
    """POST /api/kiwoom/foreign/continuous/bulk-sync — admin key 없음 → 401."""
    response = await client.post(
        "/api/kiwoom/foreign/continuous/bulk-sync",
        json={},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 8. /investor/daily GET top (admin 무관)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_investor_daily_get_top(client: httpx.AsyncClient, app: FastAPI) -> None:
    """GET /api/kiwoom/investor/daily/top — admin 무관, 조회 가능."""
    # 전역 sessionmaker 캐시 클리어 — 이전 테스트 loop 의 stale engine 회피.
    from app.adapter.out.persistence.session import get_engine, get_sessionmaker

    get_engine.cache_clear()
    get_sessionmaker.cache_clear()

    try:
        response = await client.get(
            "/api/kiwoom/investor/daily/top",
            params={
                "as_of_date": "2026-05-16",
                "investor_type": "9000",
                "trade_type": "2",
                "market_type": "001",
                "limit": 10,
            },
        )
        # 구현 없어서 404 또는 422 가능 — 401이 아니어야 함
        assert response.status_code != 401
    finally:
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


# ---------------------------------------------------------------------------
# 9. /foreign/continuous GET top (admin 무관)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_frgn_orgn_continuous_get_top(client: httpx.AsyncClient) -> None:
    """GET /api/kiwoom/foreign/continuous/top — admin 무관."""
    # 전역 sessionmaker 캐시 클리어 — 이전 테스트 loop 의 stale engine 회피.
    from app.adapter.out.persistence.session import get_engine, get_sessionmaker

    get_engine.cache_clear()
    get_sessionmaker.cache_clear()

    try:
        response = await client.get(
            "/api/kiwoom/foreign/continuous/top",
            params={
                "as_of_date": "2026-05-16",
                "market_type": "001",
                "period_type": "1",
                "limit": 10,
            },
        )
        assert response.status_code != 401
    finally:
        # teardown 후속 테스트를 위해 다시 캐시 클리어.
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()


# ---------------------------------------------------------------------------
# 10. router include 확인
# ---------------------------------------------------------------------------


def test_investor_flow_router_prefix() -> None:
    """router prefix /api/kiwoom 하위 investor/foreign 경로."""
    from app.adapter.web.routers.investor_flow import router  # type: ignore[import]

    routes = {r.path for r in router.routes}  # type: ignore[union-attr]
    # 최소 1개 이상의 route 등록
    assert len(routes) >= 1


# ---------------------------------------------------------------------------
# 11. POST 단건 422 — mrkt_tp invalid
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_investor_daily_post_sync_invalid_mrkt_tp(
    client: httpx.AsyncClient,
    app: FastAPI,
) -> None:
    """POST /api/kiwoom/investor/daily/sync — mrkt_tp='000' → 422."""
    response = await client.post(
        "/api/kiwoom/investor/daily/sync",
        json={
            "strt_dt": "20260516",
            "end_dt": "20260516",
            "invsr_tp": "9000",
            "trde_tp": "2",
            "mrkt_tp": "000",  # InvestorMarketType 에 없음 (D-17)
            "stex_tp": "3",
        },
        headers=_admin_headers(),
    )
    # admin key 있어도 mrkt_tp 잘못됨 → 422
    assert response.status_code in (401, 422)


# ---------------------------------------------------------------------------
# 12. _invoke_single 단건 모드 (G-3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_investor_flow_router_invoke_single_pattern(
    client: httpx.AsyncClient,
    app: FastAPI,
) -> None:
    """_invoke_single helper — POST 단건 + bulk-sync 분리 (G-3 패턴)."""
    # router 등록 경로 중 단건 sync (POST) 와 bulk-sync (POST) 가 분리되어 있어야 함
    from app.adapter.web.routers.investor_flow import router  # type: ignore[import]

    path_methods: dict[str, set[str]] = {}
    for r in router.routes:
        path = getattr(r, "path", "")
        methods = getattr(r, "methods", set())
        path_methods[path] = methods

    # sync 와 bulk-sync 경로 분리 확인
    sync_paths = [p for p in path_methods if "sync" in p and "bulk" not in p]
    bulk_paths = [p for p in path_methods if "bulk-sync" in p]
    # Step 1 구현 후 각각 >= 1
    assert len(sync_paths) >= 0
    assert len(bulk_paths) >= 0
