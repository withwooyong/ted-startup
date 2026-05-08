"""POST/GET /api/kiwoom/fundamentals* — B-γ-2 라우터.

설계: endpoint-05-ka10001.md § 7.1.

검증:
- POST /fundamentals/sync — admin 가드, factory 호출, 결과 응답, KiwoomError 매핑
- POST /stocks/{code}/fundamental/refresh — admin 가드, 단건 새로고침, KiwoomBusinessError → 400
- GET /stocks/{code}/fundamental/latest — DB only, 404 미존재, exchange 쿼리

라우터 패턴은 B-α (sync_stocks) / B-β (refresh_stock) 일관 — `_make_app()` 별도 FastAPI
인스턴스 + `app.dependency_overrides` 로 factory 주입. lifespan 진입 안 함.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import date
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.adapter.out.kiwoom._exceptions import (
    KiwoomBusinessError,
    KiwoomCredentialRejectedError,
    KiwoomRateLimitedError,
    KiwoomResponseValidationError,
    KiwoomUpstreamError,
)
from app.adapter.out.persistence.repositories.stock_fundamental import (
    StockFundamentalRepository,
)
from app.adapter.web._deps import get_sync_fundamental_factory
from app.adapter.web.routers.fundamentals import router as fundamentals_router
from app.application.service.stock_fundamental_service import (
    FundamentalSyncOutcome,
    FundamentalSyncResult,
    SyncStockFundamentalUseCase,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """conftest 의 트랜잭션+rollback session override — 본 테스트는 commit 필요."""
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_fundamental_tables(engine: AsyncEngine) -> AsyncIterator[None]:
    """매 테스트 시작·종료 시 stock + stock_fundamental TRUNCATE (FK CASCADE)."""
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
    key = "test-admin-key-fundamental"
    monkeypatch.setenv("ADMIN_API_KEY", key)
    from app.config.settings import get_settings

    get_settings.cache_clear()
    yield key
    get_settings.cache_clear()


def _stub_factory(uc: SyncStockFundamentalUseCase) -> Any:
    """SyncStockFundamentalUseCase 인스턴스를 yield 하는 factory."""

    @asynccontextmanager
    async def _factory(_alias: str) -> AsyncIterator[SyncStockFundamentalUseCase]:
        yield uc

    return _factory


def _make_app(factory: Any = None) -> FastAPI:
    """별도 FastAPI 앱 — lifespan 진입 안 함 (B-α/B-β test_stock_router 패턴 일관)."""
    app = FastAPI()
    app.include_router(fundamentals_router)
    if factory is not None:
        app.dependency_overrides[get_sync_fundamental_factory] = lambda: factory
    return app


def _async_client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


async def _create_stock(session: AsyncSession, code: str, name: str = "테스트", market: str = "0") -> int:
    res = await session.execute(
        text(
            "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code) "
            "VALUES (:c, :n, :m) RETURNING id"
        ).bindparams(c=code, n=name, m=market)
    )
    await session.commit()
    return int(res.scalar_one())


# =============================================================================
# POST /fundamentals/sync — admin
# =============================================================================


@pytest.mark.asyncio
async def test_sync_returns_401_without_admin_key(admin_key: str) -> None:
    app = _make_app()
    async with _async_client(app) as client:
        resp = await client.post("/api/kiwoom/fundamentals/sync?alias=test")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_sync_returns_result_for_admin(admin_key: str) -> None:
    uc = AsyncMock(spec=SyncStockFundamentalUseCase)
    uc.execute = AsyncMock(
        return_value=FundamentalSyncResult(
            asof_date=date(2026, 5, 8),
            total=3,
            success=2,
            failed=1,
            errors=[
                FundamentalSyncOutcome(stock_code="999999", error_class="KiwoomBusinessError"),
            ],
        )
    )
    app = _make_app(_stub_factory(uc))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/fundamentals/sync?alias=test",
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["success"] == 2
    assert body["failed"] == 1
    assert len(body["errors"]) == 1
    assert body["errors"][0]["stock_code"] == "999999"
    assert body["errors"][0]["error_class"] == "KiwoomBusinessError"


@pytest.mark.asyncio
async def test_sync_passes_target_date_and_market_codes(admin_key: str) -> None:
    captured: dict[str, Any] = {}

    async def _execute(
        *,
        target_date: date | None = None,
        only_market_codes: list[str] | None = None,
    ) -> FundamentalSyncResult:
        captured["target_date"] = target_date
        captured["only_market_codes"] = only_market_codes
        return FundamentalSyncResult(
            asof_date=target_date or date.today(),
            total=0,
            success=0,
            failed=0,
            errors=[],
        )

    uc = AsyncMock(spec=SyncStockFundamentalUseCase)
    uc.execute = _execute
    app = _make_app(_stub_factory(uc))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/fundamentals/sync?alias=test",
            headers={"X-API-Key": admin_key},
            json={"target_date": "2026-04-01", "only_market_codes": ["0", "10"]},
        )

    assert resp.status_code == 200
    assert captured["target_date"] == date(2026, 4, 1)
    assert captured["only_market_codes"] == ["0", "10"]


# =============================================================================
# POST /stocks/{code}/fundamental/refresh — admin
# =============================================================================


@pytest.mark.asyncio
async def test_refresh_fundamental_returns_401_without_admin(admin_key: str) -> None:
    app = _make_app()
    async with _async_client(app) as client:
        resp = await client.post("/api/kiwoom/stocks/005930/fundamental/refresh?alias=test")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_fundamental_returns_data_for_admin(
    admin_key: str, session: AsyncSession
) -> None:
    stock_id = await _create_stock(session, "005930", "삼성전자")

    from app.adapter.out.persistence.models import StockFundamental

    fake = StockFundamental(
        id=999,
        stock_id=stock_id,
        asof_date=date(2026, 5, 8),
        exchange="KRX",
        per_ratio=None,
        fundamental_hash="x" * 32,
    )

    uc = AsyncMock(spec=SyncStockFundamentalUseCase)
    uc.refresh_one = AsyncMock(return_value=fake)
    app = _make_app(_stub_factory(uc))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/005930/fundamental/refresh?alias=test",
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["stock_id"] == stock_id
    assert body["asof_date"] == "2026-05-08"
    assert body["exchange"] == "KRX"


@pytest.mark.asyncio
async def test_refresh_fundamental_maps_business_error_to_400(admin_key: str) -> None:
    """KiwoomBusinessError → 400. message echo 차단 (B-β M-2)."""
    uc = AsyncMock(spec=SyncStockFundamentalUseCase)
    uc.refresh_one = AsyncMock(
        side_effect=KiwoomBusinessError(api_id="ka10001", return_code=1, message="존재하지 않음")
    )
    app = _make_app(_stub_factory(uc))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/999999/fundamental/refresh?alias=test",
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 400
    body = resp.json()
    assert body["detail"]["return_code"] == 1
    assert body["detail"]["error"] == "KiwoomBusinessError"
    assert "존재하지 않음" not in resp.text


@pytest.mark.asyncio
async def test_refresh_fundamental_maps_credential_rejected_to_400(admin_key: str) -> None:
    uc = AsyncMock(spec=SyncStockFundamentalUseCase)
    uc.refresh_one = AsyncMock(side_effect=KiwoomCredentialRejectedError("401"))
    app = _make_app(_stub_factory(uc))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/005930/fundamental/refresh?alias=test",
            headers={"X-API-Key": admin_key},
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_refresh_fundamental_maps_rate_limit_to_503(admin_key: str) -> None:
    uc = AsyncMock(spec=SyncStockFundamentalUseCase)
    uc.refresh_one = AsyncMock(side_effect=KiwoomRateLimitedError("429"))
    app = _make_app(_stub_factory(uc))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/005930/fundamental/refresh?alias=test",
            headers={"X-API-Key": admin_key},
        )
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_refresh_fundamental_maps_upstream_to_502(admin_key: str) -> None:
    uc = AsyncMock(spec=SyncStockFundamentalUseCase)
    uc.refresh_one = AsyncMock(side_effect=KiwoomUpstreamError("5xx"))
    app = _make_app(_stub_factory(uc))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/005930/fundamental/refresh?alias=test",
            headers={"X-API-Key": admin_key},
        )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_refresh_fundamental_maps_validation_to_502(admin_key: str) -> None:
    uc = AsyncMock(spec=SyncStockFundamentalUseCase)
    uc.refresh_one = AsyncMock(side_effect=KiwoomResponseValidationError("Pydantic 위반"))
    app = _make_app(_stub_factory(uc))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/005930/fundamental/refresh?alias=test",
            headers={"X-API-Key": admin_key},
        )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_refresh_fundamental_value_error_for_missing_stock_master(admin_key: str) -> None:
    """Stock 마스터 미존재 → 404."""
    uc = AsyncMock(spec=SyncStockFundamentalUseCase)
    uc.refresh_one = AsyncMock(side_effect=ValueError("stock master not found: 005930"))
    app = _make_app(_stub_factory(uc))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/005930/fundamental/refresh?alias=test",
            headers={"X-API-Key": admin_key},
        )
    assert resp.status_code == 404


# =============================================================================
# GET /stocks/{code}/fundamental/latest — DB only
# =============================================================================


@pytest.mark.asyncio
async def test_get_latest_fundamental_three_scenarios_in_single_lifetime(session: AsyncSession) -> None:
    """Stock 미존재 / fundamental 미적재 / 데이터 있음 — 한 client lifetime 에서 검증.

    분리 시 module-level get_engine() lru_cache 의 stale asyncpg connection 이 다음
    테스트의 다른 event loop 에서 close 되며 RuntimeError (B-α stock_router 패턴 일관).
    """
    from app.adapter.out.kiwoom.stkinfo import NormalizedFundamental

    # 시나리오 1: Stock 미존재
    app = _make_app()
    async with _async_client(app) as client:
        resp1 = await client.get("/api/kiwoom/stocks/005930/fundamental/latest")
        assert resp1.status_code == 404

        # 시나리오 2: Stock 있지만 fundamental 미적재
        stock_id = await _create_stock(session, "005930", "삼성전자")
        resp2 = await client.get("/api/kiwoom/stocks/005930/fundamental/latest")
        assert resp2.status_code == 404

        # 시나리오 3: 데이터 있음
        n = NormalizedFundamental(
            stock_code="005930",
            exchange="KRX",
            asof_date=date(2026, 5, 8),
            stock_name="삼성전자",
            settlement_month="12",
            face_value=5000, face_value_unit="원", capital_won=1311, listed_shares=5969782,
            market_cap=4356400, market_cap_weight=None, foreign_holding_rate=None,
            replacement_price=None, credit_rate=None, circulating_shares=None, circulating_rate=None,
            per_ratio=None, eps_won=None, roe_pct=None, pbr_ratio=None, ev_ratio=None, bps_won=None,
            revenue_amount=None, operating_profit=None, net_profit=None,
            high_250d=None, high_250d_date=None, high_250d_pre_rate=None,
            low_250d=None, low_250d_date=None, low_250d_pre_rate=None,
            year_high=None, year_low=None,
            current_price=75800, prev_compare_sign=None, prev_compare_amount=None,
            change_rate=None, trade_volume=None, trade_compare_rate=None,
            open_price=None, high_price=None, low_price=None, upper_limit_price=None,
            lower_limit_price=None, base_price=None, expected_match_price=None, expected_match_volume=None,
        )
        repo = StockFundamentalRepository(session)
        await repo.upsert_one(n, stock_id=stock_id)
        await session.commit()

        resp3 = await client.get("/api/kiwoom/stocks/005930/fundamental/latest")
        assert resp3.status_code == 200
        body = resp3.json()
        assert body["stock_id"] == stock_id
        assert body["exchange"] == "KRX"
        assert body["current_price"] == 75800


@pytest.mark.asyncio
async def test_get_latest_rejects_invalid_stock_code() -> None:
    """5자리 / 영문 / suffix 거부 (Path pattern)."""
    app = _make_app()
    async with _async_client(app) as client:
        for invalid in ("00593", "005930_NX", "ABC123"):
            resp = await client.get(f"/api/kiwoom/stocks/{invalid}/fundamental/latest")
            assert resp.status_code == 422
