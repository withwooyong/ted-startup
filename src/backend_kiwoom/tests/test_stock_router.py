"""GET / POST /api/kiwoom/stocks 라우터 + admin guard.

httpx.AsyncClient + ASGITransport 패턴 (sector router test 와 일관).

시나리오 (GET):
1. 빈 DB → []
2. invalid market_code 패턴 → 422 (정규식 검증)
3. nxt-eligible 빈 DB → []

시나리오 (POST /sync):
4. admin key 누락 → 401
5. admin key 잘못 → 401
6. ADMIN_API_KEY 미설정 → 401 (fail-closed)
7. 정상 sync → 200 + StockMasterSyncResultOut (5 시장 outcome + nxt_enabled)
8. 한 시장 실패 — 부분 성공 응답 (200, all_succeeded=False)
9. F3 통합 — outcome 에 MaxPagesExceeded 시 Retry-After 헤더
10. alias 미등록 → 404
11. alias 비활성 → 400
12. alias 한도 초과 → 503
13. alias 쿼리 누락 → 422
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.web._deps import get_sync_stock_factory
from app.adapter.web.routers.stocks import router as stocks_router
from app.application.service.stock_master_service import (
    MarketStockOutcome,
    StockMasterSyncResult,
)

# =============================================================================
# 픽스처
# =============================================================================


@pytest.fixture
def admin_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    key = "test-admin-key-stock"
    monkeypatch.setenv("ADMIN_API_KEY", key)
    from app.config.settings import get_settings

    get_settings.cache_clear()
    yield key
    get_settings.cache_clear()


def _make_app(factory=None) -> FastAPI:
    app = FastAPI()
    app.include_router(stocks_router)
    if factory is not None:
        app.dependency_overrides[get_sync_stock_factory] = lambda: factory
    return app


def _async_client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


class _StubUseCase:
    """SyncStockMasterUseCase Stub — 응답 시나리오 주입."""

    def __init__(self, result: StockMasterSyncResult) -> None:
        self._result = result

    async def execute(self) -> StockMasterSyncResult:
        return self._result


def _stub_factory(result: StockMasterSyncResult):
    @asynccontextmanager
    async def _factory(alias: str) -> AsyncIterator[Any]:
        yield _StubUseCase(result)

    return _factory


def _failing_factory(exception: Exception):
    @asynccontextmanager
    async def _factory(alias: str) -> AsyncIterator[Any]:
        raise exception
        yield  # pragma: no cover

    return _factory


# =============================================================================
# GET /stocks — 조회
# =============================================================================


@pytest.mark.asyncio
async def test_get_stocks_endpoints_with_empty_db(session: AsyncSession) -> None:
    """빈 DB 에 대한 GET 두 케이스를 한 client lifetime 안에서 검증.

    분리 시 module-level get_engine() lru_cache 의 stale asyncpg connection 이
    다음 테스트의 다른 event loop 에서 close 되며 RuntimeError. 한 client 안에서
    연속 호출하면 같은 loop.
    """
    app = _make_app()

    async with _async_client(app) as client:
        list_resp = await client.get("/api/kiwoom/stocks")
        nxt_resp = await client.get("/api/kiwoom/stocks/nxt-eligible")

    assert list_resp.status_code == 200
    assert isinstance(list_resp.json(), list)
    assert nxt_resp.status_code == 200
    assert isinstance(nxt_resp.json(), list)


@pytest.mark.asyncio
async def test_get_stocks_invalid_market_code_pattern_returns_422() -> None:
    """market_code 가 숫자 패턴 외 (e.g. 'abc') → 422 (FastAPI 검증, DB 미접속)."""
    app = _make_app()

    async with _async_client(app) as client:
        resp = await client.get("/api/kiwoom/stocks", params={"market_code": "abc"})

    assert resp.status_code == 422


# =============================================================================
# POST /stocks/sync — admin guard
# =============================================================================


def _empty_result() -> StockMasterSyncResult:
    return StockMasterSyncResult(
        markets=[
            MarketStockOutcome(market_code=m, fetched=0, upserted=0, deactivated=0, nxt_enabled_count=0)
            for m in ("0", "10", "50", "60", "6")
        ],
        total_fetched=0,
        total_upserted=0,
        total_deactivated=0,
        total_nxt_enabled=0,
    )


@pytest.mark.asyncio
async def test_post_sync_rejects_missing_admin_key(admin_key: str) -> None:
    app = _make_app(factory=_stub_factory(_empty_result()))

    async with _async_client(app) as client:
        resp = await client.post("/api/kiwoom/stocks/sync", params={"alias": "test"})

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_post_sync_rejects_wrong_admin_key(admin_key: str) -> None:
    app = _make_app(factory=_stub_factory(_empty_result()))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/sync",
            params={"alias": "test"},
            headers={"X-API-Key": "WRONG-KEY"},
        )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_post_sync_fails_closed_when_admin_key_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    from app.config.settings import get_settings

    get_settings.cache_clear()
    try:
        app = _make_app(factory=_stub_factory(_empty_result()))
        async with _async_client(app) as client:
            resp = await client.post(
                "/api/kiwoom/stocks/sync",
                params={"alias": "test"},
                headers={"X-API-Key": "anything"},
            )
        assert resp.status_code == 401
    finally:
        get_settings.cache_clear()


# =============================================================================
# POST /stocks/sync — 정상/부분성공/F3
# =============================================================================


@pytest.mark.asyncio
async def test_post_sync_returns_full_result(admin_key: str) -> None:
    result = StockMasterSyncResult(
        markets=[
            MarketStockOutcome(market_code="0", fetched=900, upserted=900, deactivated=2, nxt_enabled_count=300),
            MarketStockOutcome(market_code="10", fetched=1700, upserted=1700, deactivated=0, nxt_enabled_count=1200),
            MarketStockOutcome(market_code="50", fetched=140, upserted=140, deactivated=0, nxt_enabled_count=0),
            MarketStockOutcome(market_code="60", fetched=50, upserted=50, deactivated=0, nxt_enabled_count=0),
            MarketStockOutcome(market_code="6", fetched=20, upserted=20, deactivated=0, nxt_enabled_count=0),
        ],
        total_fetched=2810,
        total_upserted=2810,
        total_deactivated=2,
        total_nxt_enabled=1500,
    )
    app = _make_app(factory=_stub_factory(result))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/sync",
            params={"alias": "prod-main"},
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["all_succeeded"] is True
    assert body["total_upserted"] == 2810
    assert body["total_nxt_enabled"] == 1500
    assert len(body["markets"]) == 5
    assert body["markets"][0]["nxt_enabled_count"] == 300
    assert "Retry-After" not in resp.headers


@pytest.mark.asyncio
async def test_post_sync_partial_failure_returns_200(admin_key: str) -> None:
    result = StockMasterSyncResult(
        markets=[
            MarketStockOutcome(market_code="0", fetched=10, upserted=10, deactivated=0, nxt_enabled_count=3),
            MarketStockOutcome(
                market_code="10",
                fetched=0,
                upserted=0,
                deactivated=0,
                nxt_enabled_count=0,
                error="KiwoomUpstreamError: ka10099 호출 실패: HTTP 502",
            ),
            MarketStockOutcome(market_code="50", fetched=2, upserted=2, deactivated=0, nxt_enabled_count=0),
            MarketStockOutcome(market_code="60", fetched=1, upserted=1, deactivated=0, nxt_enabled_count=0),
            MarketStockOutcome(market_code="6", fetched=1, upserted=1, deactivated=0, nxt_enabled_count=0),
        ],
        total_fetched=14,
        total_upserted=14,
        total_deactivated=0,
        total_nxt_enabled=3,
    )
    app = _make_app(factory=_stub_factory(result))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/sync",
            params={"alias": "prod-main"},
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["all_succeeded"] is False
    assert body["markets"][1]["error"] is not None


@pytest.mark.asyncio
async def test_post_sync_max_pages_sets_retry_after_header(admin_key: str) -> None:
    """F3 hint — outcome.error 에 MaxPages 흔적 → Retry-After 60."""
    result = StockMasterSyncResult(
        markets=[
            MarketStockOutcome(
                market_code="0",
                fetched=10000,
                upserted=0,
                deactivated=0,
                nxt_enabled_count=0,
                error="KiwoomMaxPagesExceededError: ka10099 call_paginated max_pages=100 초과",
            ),
            MarketStockOutcome(market_code="10", fetched=1, upserted=1, deactivated=0, nxt_enabled_count=0),
            MarketStockOutcome(market_code="50", fetched=1, upserted=1, deactivated=0, nxt_enabled_count=0),
            MarketStockOutcome(market_code="60", fetched=1, upserted=1, deactivated=0, nxt_enabled_count=0),
            MarketStockOutcome(market_code="6", fetched=1, upserted=1, deactivated=0, nxt_enabled_count=0),
        ],
        total_fetched=10004,
        total_upserted=4,
        total_deactivated=0,
        total_nxt_enabled=0,
    )
    app = _make_app(factory=_stub_factory(result))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/sync",
            params={"alias": "prod-main"},
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 200
    assert resp.headers.get("Retry-After") == "60"


@pytest.mark.asyncio
async def test_post_sync_credential_not_found_returns_404(admin_key: str) -> None:
    from app.application.service.token_service import CredentialNotFoundError

    app = _make_app(factory=_failing_factory(CredentialNotFoundError("alias=test")))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/sync",
            params={"alias": "missing"},
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_post_sync_credential_inactive_returns_400(admin_key: str) -> None:
    from app.application.service.token_service import CredentialInactiveError

    app = _make_app(factory=_failing_factory(CredentialInactiveError("alias=test")))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/sync",
            params={"alias": "test"},
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_post_sync_alias_capacity_exceeded_returns_503(admin_key: str) -> None:
    from app.application.service.token_service import AliasCapacityExceededError

    app = _make_app(factory=_failing_factory(AliasCapacityExceededError("max=5")))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/sync",
            params={"alias": "test"},
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_post_sync_alias_query_min_length(admin_key: str) -> None:
    """alias 쿼리 누락 → 422."""
    app = _make_app(factory=_stub_factory(_empty_result()))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/sync",
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 422
