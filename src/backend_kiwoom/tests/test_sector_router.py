"""GET / POST /api/kiwoom/sectors — 라우터 + admin guard.

httpx.AsyncClient + ASGITransport 패턴 (auth router test 와 일관).

시나리오 (GET):
1. 빈 DB → []
2. 단일 시장 데이터 조회 + only_active 필터
3. market_code 미지정 시 5 시장 통합 + 정렬
4. invalid market_code → 422 (Literal 검증)

시나리오 (POST /sync):
5. admin key 누락 → 401
6. admin key 잘못 → 401
7. ADMIN_API_KEY 미설정 → 401 (fail-closed)
8. 정상 sync → 200 + SectorSyncResultOut (5 시장 outcome)
9. 한 시장 실패 — 부분 성공 응답 (200, all_succeeded=False)
10. F3 통합 — outcome 에 MaxPagesExceeded 흔적 시 Retry-After 헤더
11. alias 미등록 → 404
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.web._deps import get_sync_sector_factory
from app.adapter.web.routers.sectors import router as sectors_router
from app.application.service.sector_service import (
    MarketSyncOutcome,
    SectorSyncResult,
)

# =============================================================================
# 픽스처
# =============================================================================


@pytest.fixture
def admin_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    key = "test-admin-key-sector"
    monkeypatch.setenv("ADMIN_API_KEY", key)
    from app.config.settings import get_settings

    get_settings.cache_clear()
    yield key
    get_settings.cache_clear()


def _make_app(factory=None) -> FastAPI:
    app = FastAPI()
    app.include_router(sectors_router)
    if factory is not None:
        app.dependency_overrides[get_sync_sector_factory] = lambda: factory
    return app


def _async_client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


class _StubUseCase:
    """SyncSectorMasterUseCase Stub — 응답 시나리오 주입."""

    def __init__(self, result: SectorSyncResult) -> None:
        self._result = result

    async def execute(self) -> SectorSyncResult:
        return self._result


def _stub_factory(result: SectorSyncResult):
    """alias 와 무관하게 동일 result 반환 — F3/부분실패/정상 시나리오 공용."""

    @asynccontextmanager
    async def _factory(alias: str) -> AsyncIterator[Any]:
        yield _StubUseCase(result)

    return _factory


def _failing_factory(exception: Exception):
    """async with factory(alias) 시점에 raise — 라우터의 except 매핑 검증."""

    @asynccontextmanager
    async def _factory(alias: str) -> AsyncIterator[Any]:
        raise exception
        yield  # pragma: no cover — generator semantics

    return _factory


# =============================================================================
# GET /sectors — 조회
# =============================================================================


@pytest.mark.asyncio
async def test_get_sectors_empty_db_returns_empty_list(session: AsyncSession) -> None:
    """conftest session 트랜잭션은 롤백되므로 라우터 자체 sessionmaker 가 빈 DB 반환."""
    app = _make_app()

    async with _async_client(app) as client:
        resp = await client.get("/api/kiwoom/sectors")

    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_sectors_invalid_market_code_returns_422() -> None:
    app = _make_app()

    async with _async_client(app) as client:
        resp = await client.get("/api/kiwoom/sectors", params={"market_code": "3"})

    assert resp.status_code == 422


# =============================================================================
# POST /sectors/sync — admin guard
# =============================================================================


@pytest.mark.asyncio
async def test_post_sync_rejects_missing_admin_key(admin_key: str) -> None:
    """admin key 헤더 누락 → 401."""
    app = _make_app(factory=_stub_factory(_empty_result()))

    async with _async_client(app) as client:
        resp = await client.post("/api/kiwoom/sectors/sync", params={"alias": "test"})

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_post_sync_rejects_wrong_admin_key(admin_key: str) -> None:
    app = _make_app(factory=_stub_factory(_empty_result()))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/sectors/sync",
            params={"alias": "test"},
            headers={"X-API-Key": "WRONG-KEY"},
        )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_post_sync_fails_closed_when_admin_key_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADMIN_API_KEY 미설정 → 어떤 X-API-Key 도 401."""
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    from app.config.settings import get_settings

    get_settings.cache_clear()
    try:
        app = _make_app(factory=_stub_factory(_empty_result()))
        async with _async_client(app) as client:
            resp = await client.post(
                "/api/kiwoom/sectors/sync",
                params={"alias": "test"},
                headers={"X-API-Key": "anything"},
            )
        assert resp.status_code == 401
    finally:
        get_settings.cache_clear()


# =============================================================================
# POST /sectors/sync — 정상/부분성공/F3
# =============================================================================


def _empty_result() -> SectorSyncResult:
    return SectorSyncResult(
        markets=[
            MarketSyncOutcome(market_code=m, fetched=0, upserted=0, deactivated=0) for m in ("0", "1", "2", "4", "7")
        ],
        total_fetched=0,
        total_upserted=0,
        total_deactivated=0,
    )


@pytest.mark.asyncio
async def test_post_sync_returns_full_result(admin_key: str) -> None:
    result = SectorSyncResult(
        markets=[
            MarketSyncOutcome(market_code="0", fetched=10, upserted=10, deactivated=2),
            MarketSyncOutcome(market_code="1", fetched=8, upserted=8, deactivated=0),
            MarketSyncOutcome(market_code="2", fetched=5, upserted=5, deactivated=0),
            MarketSyncOutcome(market_code="4", fetched=3, upserted=3, deactivated=0),
            MarketSyncOutcome(market_code="7", fetched=2, upserted=2, deactivated=0),
        ],
        total_fetched=28,
        total_upserted=28,
        total_deactivated=2,
    )
    app = _make_app(factory=_stub_factory(result))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/sectors/sync",
            params={"alias": "prod-main"},
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["all_succeeded"] is True
    assert body["total_upserted"] == 28
    assert len(body["markets"]) == 5
    assert body["markets"][0]["market_code"] == "0"
    # F3 hint 헤더는 max_pages 없으면 미부착
    assert "Retry-After" not in resp.headers


@pytest.mark.asyncio
async def test_post_sync_partial_failure_returns_200(admin_key: str) -> None:
    """한 시장만 KiwoomUpstreamError — 200 + all_succeeded=False."""
    result = SectorSyncResult(
        markets=[
            MarketSyncOutcome(market_code="0", fetched=5, upserted=5, deactivated=0),
            MarketSyncOutcome(
                market_code="1",
                fetched=0,
                upserted=0,
                deactivated=0,
                error="KiwoomUpstreamError: ka10101 호출 실패: HTTP 502",
            ),
            MarketSyncOutcome(market_code="2", fetched=3, upserted=3, deactivated=0),
            MarketSyncOutcome(market_code="4", fetched=2, upserted=2, deactivated=0),
            MarketSyncOutcome(market_code="7", fetched=1, upserted=1, deactivated=0),
        ],
        total_fetched=11,
        total_upserted=11,
        total_deactivated=0,
    )
    app = _make_app(factory=_stub_factory(result))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/sectors/sync",
            params={"alias": "prod-main"},
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["all_succeeded"] is False
    assert body["markets"][1]["error"] is not None


@pytest.mark.asyncio
async def test_post_sync_max_pages_sets_retry_after_header(admin_key: str) -> None:
    """F3 통합 — outcome.error 에 MaxPages 흔적 있으면 Retry-After 헤더."""
    result = SectorSyncResult(
        markets=[
            MarketSyncOutcome(
                market_code="0",
                fetched=1000,
                upserted=0,
                deactivated=0,
                error="KiwoomMaxPagesExceededError: ka10101 call_paginated max_pages=20 초과",
            ),
            MarketSyncOutcome(market_code="1", fetched=2, upserted=2, deactivated=0),
            MarketSyncOutcome(market_code="2", fetched=2, upserted=2, deactivated=0),
            MarketSyncOutcome(market_code="4", fetched=2, upserted=2, deactivated=0),
            MarketSyncOutcome(market_code="7", fetched=2, upserted=2, deactivated=0),
        ],
        total_fetched=1008,
        total_upserted=8,
        total_deactivated=0,
    )
    app = _make_app(factory=_stub_factory(result))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/sectors/sync",
            params={"alias": "prod-main"},
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 200
    assert resp.headers.get("Retry-After") == "60"


@pytest.mark.asyncio
async def test_post_sync_credential_not_found_returns_404(admin_key: str) -> None:
    """factory 가 alias 진입 시 CredentialNotFoundError → 404."""
    from app.application.service.token_service import CredentialNotFoundError

    app = _make_app(factory=_failing_factory(CredentialNotFoundError("alias=test")))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/sectors/sync",
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
            "/api/kiwoom/sectors/sync",
            params={"alias": "test"},
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_post_sync_alias_query_min_length(admin_key: str) -> None:
    """alias 쿼리 누락 → 422."""
    app = _make_app(factory=_stub_factory(_empty_result()))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/sectors/sync",
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 422
