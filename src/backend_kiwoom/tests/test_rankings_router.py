"""POST/GET /api/kiwoom/rankings/* — Phase F-4 라우터 (5 ranking endpoint).

설계: phase-f-4-rankings.md § 5.7 + § 5.12 #8.

가정 production 위치: app/adapter/web/routers/rankings.py (Step 1 에서 작성).

검증 시나리오 (~15 케이스):

5 endpoint × (POST 단건 / POST sync bulk / GET snapshot) 패턴:
1.  flu_rt — POST 단건 401 (admin key 없음)
2.  flu_rt — POST 단건 200 (admin key 있음)
3.  flu_rt — POST bulk 401 (admin key 없음)
4.  flu_rt — GET snapshot (admin 무관, DB only)
5.  today_volume — POST 단건 401 / 200 admin 회귀
6.  today_volume — GET snapshot Pydantic validation (mrkt_tp Literal)
7.  pred_volume — POST bulk 401 / 200 admin 회귀
8.  pred_volume — GET snapshot Pydantic validation (stex_tp Literal)
9.  trde_prica — POST 단건 401 / 200 admin 회귀
10. trde_prica — GET snapshot 정상 응답
11. volume_sdnin — POST 단건 401 / 200 admin 회귀
12. volume_sdnin — GET snapshot Pydantic validation (sort_tp Literal)
13. POST 단건 422 — mrkt_tp invalid ("999")
14. POST 단건 422 — stex_tp invalid (0)
15. GET snapshot — ranking_type 부재 → 422

TDD red 의도:
- `from app.adapter.web.routers.rankings import router` → ImportError (Step 1 미구현)
- Step 1 구현 후 green 전환.
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
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.adapter.web._deps import (  # type: ignore[import]  # Step 1
    get_ingest_flu_rt_bulk_factory,
    get_ingest_flu_rt_factory,
    get_ingest_pred_volume_bulk_factory,
    get_ingest_pred_volume_factory,
    get_ingest_today_volume_bulk_factory,
    get_ingest_today_volume_factory,
    get_ingest_trade_amount_bulk_factory,
    get_ingest_trade_amount_factory,
    get_ingest_volume_sdnin_bulk_factory,
    get_ingest_volume_sdnin_factory,
)
from app.adapter.web.routers.rankings import router as rankings_router  # type: ignore[import]  # Step 1
from app.application.dto.ranking import RankingBulkResult  # type: ignore[import]  # Step 1

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def _clear_global_engine_cache() -> Iterator[None]:
    """전역 get_engine/get_sessionmaker lru_cache stale event loop binding 해소."""
    from app.adapter.out.persistence.session import get_engine, get_sessionmaker

    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    yield
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s


@pytest_asyncio.fixture(autouse=True)
async def _cleanup(engine: AsyncEngine) -> AsyncIterator[None]:
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        await s.execute(text("TRUNCATE kiwoom.stock RESTART IDENTITY CASCADE"))
        await s.commit()
    yield
    async with factory() as s:
        await s.execute(text("TRUNCATE kiwoom.stock RESTART IDENTITY CASCADE"))
        await s.commit()


@pytest.fixture
def admin_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    key = "test-admin-key-rankings"
    monkeypatch.setenv("ADMIN_API_KEY", key)
    from app.config.settings import get_settings

    get_settings.cache_clear()
    yield key
    get_settings.cache_clear()


def _stub_bulk_factory(result: Any) -> Any:
    """BulkUseCase factory stub — execute → result 반환 (bulk-sync endpoint 용)."""

    @asynccontextmanager
    async def _factory(_alias: str) -> AsyncIterator[Any]:
        uc = AsyncMock()
        uc.execute = AsyncMock(return_value=result)
        yield uc

    return _factory


def _stub_single_factory(outcome: Any) -> Any:
    """단건 UseCase factory stub — execute → outcome 반환 (F-4 Step 2 fix G-3)."""

    @asynccontextmanager
    async def _factory(_alias: str) -> AsyncIterator[Any]:
        uc = AsyncMock()
        uc.execute = AsyncMock(return_value=outcome)
        yield uc

    return _factory


def _make_empty_bulk_result() -> RankingBulkResult:
    """빈 bulk result (테스트용)."""
    return RankingBulkResult(
        ranking_type=None,  # type: ignore[arg-type]
        total_calls=0,
        total_upserted=0,
        total_failed=0,
        outcomes=(),
        errors_above_threshold=(),
    )


def _make_empty_single_outcome() -> Any:
    """빈 단건 outcome (테스트용 — F-4 Step 2 fix G-3 sync endpoint)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.adapter.out.kiwoom._records import RankingType
    from app.application.dto.ranking import RankingIngestOutcome

    return RankingIngestOutcome(
        ranking_type=RankingType.FLU_RT,
        snapshot_at=datetime(2026, 5, 14, 19, 30, tzinfo=ZoneInfo("Asia/Seoul")),
        sort_tp="1",
        market_type="001",
        exchange_type="3",
        fetched=0,
        upserted=0,
    )


def _make_rankings_app(
    flu_rt_factory: Any = None,
    today_volume_factory: Any = None,
    pred_volume_factory: Any = None,
    trade_amount_factory: Any = None,
    volume_sdnin_factory: Any = None,
    # F-4 Step 2 fix G-3 — 5 단건 factory override (sync endpoint).
    # None 이면 default stub (empty outcome) 자동 주입 — 기존 admin 회귀 테스트 유지.
    flu_rt_single_factory: Any = None,
    today_volume_single_factory: Any = None,
    pred_volume_single_factory: Any = None,
    trade_amount_single_factory: Any = None,
    volume_sdnin_single_factory: Any = None,
) -> FastAPI:
    """별도 FastAPI 앱 — lifespan 진입 안 함."""
    app = FastAPI()
    app.include_router(rankings_router)

    if flu_rt_factory is not None:
        app.dependency_overrides[get_ingest_flu_rt_bulk_factory] = lambda: flu_rt_factory
    if today_volume_factory is not None:
        app.dependency_overrides[get_ingest_today_volume_bulk_factory] = lambda: today_volume_factory
    if pred_volume_factory is not None:
        app.dependency_overrides[get_ingest_pred_volume_bulk_factory] = lambda: pred_volume_factory
    if trade_amount_factory is not None:
        app.dependency_overrides[get_ingest_trade_amount_bulk_factory] = lambda: trade_amount_factory
    if volume_sdnin_factory is not None:
        app.dependency_overrides[get_ingest_volume_sdnin_bulk_factory] = lambda: volume_sdnin_factory

    # 단건 factory — 명시 주입 우선, 미주입 시 기존 admin 회귀 테스트 호환용 default stub.
    # 호출 도달성만 확인하는 케이스 (admin guard 검증 등) 가 503 으로 fail 하지 않도록.
    if flu_rt_single_factory is None and flu_rt_factory is not None:
        flu_rt_single_factory = _stub_single_factory(_make_empty_single_outcome())
    if today_volume_single_factory is None and today_volume_factory is not None:
        today_volume_single_factory = _stub_single_factory(_make_empty_single_outcome())
    if pred_volume_single_factory is None and pred_volume_factory is not None:
        pred_volume_single_factory = _stub_single_factory(_make_empty_single_outcome())
    if trade_amount_single_factory is None and trade_amount_factory is not None:
        trade_amount_single_factory = _stub_single_factory(_make_empty_single_outcome())
    if volume_sdnin_single_factory is None and volume_sdnin_factory is not None:
        volume_sdnin_single_factory = _stub_single_factory(_make_empty_single_outcome())

    if flu_rt_single_factory is not None:
        app.dependency_overrides[get_ingest_flu_rt_factory] = lambda: flu_rt_single_factory
    if today_volume_single_factory is not None:
        app.dependency_overrides[get_ingest_today_volume_factory] = lambda: today_volume_single_factory
    if pred_volume_single_factory is not None:
        app.dependency_overrides[get_ingest_pred_volume_factory] = lambda: pred_volume_single_factory
    if trade_amount_single_factory is not None:
        app.dependency_overrides[get_ingest_trade_amount_factory] = lambda: trade_amount_single_factory
    if volume_sdnin_single_factory is not None:
        app.dependency_overrides[get_ingest_volume_sdnin_factory] = lambda: volume_sdnin_single_factory

    return app


def _async_client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


# =============================================================================
# 1~4. flu_rt endpoint 4 케이스
# =============================================================================


@pytest.mark.asyncio
async def test_flu_rt_sync_single_returns_401_without_admin_key(admin_key: str) -> None:
    """POST /api/kiwoom/rankings/flu-rt/sync (단건) — admin key 없음 → 401."""
    app = _make_rankings_app()
    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/rankings/flu-rt/sync?alias=test",
            json={"mrkt_tp": "001", "sort_tp": "1", "stex_tp": "3"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_flu_rt_sync_single_returns_200_with_admin_key(admin_key: str) -> None:
    """POST /api/kiwoom/rankings/flu-rt/sync — admin key 있음 → 200."""
    factory = _stub_bulk_factory(_make_empty_bulk_result())
    app = _make_rankings_app(flu_rt_factory=factory)

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/rankings/flu-rt/sync?alias=test",
            headers={"X-API-Key": admin_key},
            json={"mrkt_tp": "001", "sort_tp": "1", "stex_tp": "3"},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_flu_rt_bulk_sync_returns_401_without_admin_key(admin_key: str) -> None:
    """POST /api/kiwoom/rankings/flu-rt/bulk-sync — admin key 없음 → 401."""
    app = _make_rankings_app()
    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/rankings/flu-rt/bulk-sync?alias=test",
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_flu_rt_snapshot_get_does_not_require_admin(admin_key: str) -> None:
    """GET /api/kiwoom/rankings/flu-rt/snapshot — DB only, admin 무관 → 200 or 422."""
    app = _make_rankings_app()
    async with _async_client(app) as client:
        # admin key 없어도 접근 가능 — 빈 결과 200 이거나 파라미터 부재로 422
        resp = await client.get(
            "/api/kiwoom/rankings/flu-rt/snapshot",
            params={"snapshot_date": "2026-05-14", "mrkt_tp": "001"},
        )
    # admin key 없이도 4xx (422 validation / 200 정상) — 401 이 아니어야 함
    assert resp.status_code != 401


# =============================================================================
# 5~8. today_volume / pred_volume endpoint — admin 회귀 + Pydantic validation
# =============================================================================


@pytest.mark.asyncio
async def test_today_volume_sync_admin_guard(admin_key: str) -> None:
    """POST /api/kiwoom/rankings/today-volume/sync — admin key 없음 → 401."""
    app = _make_rankings_app()
    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/rankings/today-volume/sync?alias=test",
            json={"mrkt_tp": "001", "stex_tp": "3"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_today_volume_snapshot_mrkt_tp_validation(admin_key: str) -> None:
    """GET /api/kiwoom/rankings/today-volume/snapshot — mrkt_tp Literal["000","001","101"] 외 → 422."""
    app = _make_rankings_app()
    async with _async_client(app) as client:
        resp = await client.get(
            "/api/kiwoom/rankings/today-volume/snapshot",
            params={
                "snapshot_date": "2026-05-14",
                "mrkt_tp": "999",  # invalid
            },
        )
    assert resp.status_code == 422, f"mrkt_tp='999' → 422 기대, 실제={resp.status_code}"


@pytest.mark.asyncio
async def test_pred_volume_bulk_sync_admin_guard(admin_key: str) -> None:
    """POST /api/kiwoom/rankings/pred-volume/bulk-sync — admin key 없음 → 401."""
    app = _make_rankings_app()
    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/rankings/pred-volume/bulk-sync?alias=test",
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_pred_volume_snapshot_stex_tp_validation(admin_key: str) -> None:
    """GET /api/kiwoom/rankings/pred-volume/snapshot — stex_tp Literal[1,2,3] 외 → 422."""
    app = _make_rankings_app()
    async with _async_client(app) as client:
        resp = await client.get(
            "/api/kiwoom/rankings/pred-volume/snapshot",
            params={
                "snapshot_date": "2026-05-14",
                "stex_tp": "0",  # invalid (0 은 지원 안 함)
            },
        )
    assert resp.status_code == 422, f"stex_tp=0 → 422 기대, 실제={resp.status_code}"


# =============================================================================
# 9~12. trde_prica / volume_sdnin — admin 회귀 + GET validation
# =============================================================================


@pytest.mark.asyncio
async def test_trde_prica_sync_admin_guard(admin_key: str) -> None:
    """POST /api/kiwoom/rankings/trde-prica/sync — admin key 없음 → 401."""
    app = _make_rankings_app()
    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/rankings/trde-prica/sync?alias=test",
            json={"mrkt_tp": "001", "stex_tp": "3"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_trde_prica_snapshot_get_accessible_without_admin(admin_key: str) -> None:
    """GET /api/kiwoom/rankings/trde-prica/snapshot — admin 무관 (401 아님)."""
    app = _make_rankings_app()
    async with _async_client(app) as client:
        resp = await client.get(
            "/api/kiwoom/rankings/trde-prica/snapshot",
            params={"snapshot_date": "2026-05-14", "mrkt_tp": "001"},
        )
    assert resp.status_code != 401


@pytest.mark.asyncio
async def test_volume_sdnin_sync_admin_guard(admin_key: str) -> None:
    """POST /api/kiwoom/rankings/volume-sdnin/sync — admin key 없음 → 401."""
    app = _make_rankings_app()
    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/rankings/volume-sdnin/sync?alias=test",
            json={"mrkt_tp": "001", "sort_tp": "1"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_volume_sdnin_snapshot_sort_tp_validation(admin_key: str) -> None:
    """GET /api/kiwoom/rankings/volume-sdnin/snapshot — sort_tp Literal[1,2] 외 → 422."""
    app = _make_rankings_app()
    async with _async_client(app) as client:
        resp = await client.get(
            "/api/kiwoom/rankings/volume-sdnin/snapshot",
            params={
                "snapshot_date": "2026-05-14",
                "sort_tp": "9",  # invalid
            },
        )
    assert resp.status_code == 422, f"sort_tp=9 → 422 기대, 실제={resp.status_code}"


# =============================================================================
# 13~15. Pydantic validation 추가 케이스
# =============================================================================


@pytest.mark.asyncio
async def test_sync_invalid_mrkt_tp_returns_422(admin_key: str) -> None:
    """POST 단건 — mrkt_tp="999" (Literal["000","001","101"] 외) → 422."""
    app = _make_rankings_app()
    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/rankings/flu-rt/sync?alias=test",
            headers={"X-API-Key": admin_key},
            json={"mrkt_tp": "999", "sort_tp": "1", "stex_tp": "3"},
        )
    assert resp.status_code == 422, f"mrkt_tp='999' → 422 기대, 실제={resp.status_code}"


@pytest.mark.asyncio
async def test_sync_invalid_stex_tp_returns_422(admin_key: str) -> None:
    """POST 단건 — stex_tp=0 (Literal[1,2,3] 외) → 422."""
    app = _make_rankings_app()
    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/rankings/flu-rt/sync?alias=test",
            headers={"X-API-Key": admin_key},
            json={"mrkt_tp": "001", "sort_tp": "1", "stex_tp": 0},
        )
    assert resp.status_code == 422, f"stex_tp=0 → 422 기대, 실제={resp.status_code}"


@pytest.mark.asyncio
async def test_snapshot_missing_snapshot_date_returns_422(admin_key: str) -> None:
    """GET snapshot — snapshot_date 파라미터 부재 → 422."""
    app = _make_rankings_app()
    async with _async_client(app) as client:
        # snapshot_date 없이 호출 → 422
        resp = await client.get(
            "/api/kiwoom/rankings/flu-rt/snapshot",
        )
    assert resp.status_code == 422, f"snapshot_date 부재 → 422 기대, 실제={resp.status_code}"


__all__: list[Any] = []
