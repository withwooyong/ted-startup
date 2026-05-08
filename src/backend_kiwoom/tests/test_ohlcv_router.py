"""POST/GET /api/kiwoom/ohlcv* — C-1β 라우터.

설계: endpoint-06-ka10081.md § 7.1.

검증:
- POST /ohlcv/daily/sync — admin, base_date + only_market_codes 옵션
- POST /stocks/{code}/ohlcv/daily/refresh — admin, KiwoomError 매핑, ValueError → 404
- GET /stocks/{code}/ohlcv/daily?exchange=&start=&end= — DB only
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
from app.adapter.out.persistence.repositories.stock_price import StockPriceRepository
from app.adapter.web._deps import get_ingest_ohlcv_factory
from app.adapter.web.routers.ohlcv import router as ohlcv_router
from app.application.constants import ExchangeType
from app.application.service.ohlcv_daily_service import (
    IngestDailyOhlcvUseCase,
    OhlcvSyncResult,
)


@pytest.fixture(autouse=True)
def _clear_global_engine_cache() -> Iterator[None]:
    """전역 get_engine/get_sessionmaker lru_cache 의 stale event loop binding 해소.

    test_stock_lookup_router.py 패턴 일관 — fundamental/ohlcv 테스트가 다른 파일에서
    캐시된 engine 을 받아 다른 event loop 에 바인딩될 때 RuntimeError 차단.
    """
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
    key = "test-admin-key-ohlcv"
    monkeypatch.setenv("ADMIN_API_KEY", key)
    from app.config.settings import get_settings

    get_settings.cache_clear()
    yield key
    get_settings.cache_clear()


def _stub_factory(uc: IngestDailyOhlcvUseCase) -> Any:
    @asynccontextmanager
    async def _factory(_alias: str) -> AsyncIterator[IngestDailyOhlcvUseCase]:
        yield uc

    return _factory


def _make_app(factory: Any = None) -> FastAPI:
    app = FastAPI()
    app.include_router(ohlcv_router)
    if factory is not None:
        app.dependency_overrides[get_ingest_ohlcv_factory] = lambda: factory
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


async def _create_stock(session: AsyncSession, code: str = "005930") -> int:
    res = await session.execute(
        text(
            "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code) "
            "VALUES (:c, :n, '0') RETURNING id"
        ).bindparams(c=code, n=f"테스트-{code}")
    )
    await session.commit()
    return int(res.scalar_one())


# =============================================================================
# POST /ohlcv/daily/sync — admin
# =============================================================================


@pytest.mark.asyncio
async def test_sync_returns_401_without_admin(admin_key: str) -> None:
    app = _make_app()
    async with _client(app) as cl:
        resp = await cl.post("/api/kiwoom/ohlcv/daily/sync?alias=test")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_sync_returns_result_for_admin(admin_key: str) -> None:
    uc = AsyncMock(spec=IngestDailyOhlcvUseCase)
    uc.execute = AsyncMock(
        return_value=OhlcvSyncResult(
            base_date=date(2025, 9, 8),
            total=2,
            success_krx=2,
            success_nxt=1,
            failed=0,
            errors=[],
        )
    )
    app = _make_app(_stub_factory(uc))

    async with _client(app) as cl:
        resp = await cl.post(
            "/api/kiwoom/ohlcv/daily/sync?alias=test",
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["base_date"] == "2025-09-08"
    assert body["total"] == 2
    assert body["success_krx"] == 2
    assert body["success_nxt"] == 1


@pytest.mark.asyncio
async def test_sync_passes_optional_body(admin_key: str) -> None:
    captured: dict[str, Any] = {}

    async def _execute(*, base_date: date | None = None, only_market_codes: list[str] | None = None) -> OhlcvSyncResult:
        captured["base_date"] = base_date
        captured["only_market_codes"] = only_market_codes
        return OhlcvSyncResult(
            base_date=base_date or date.today(),
            total=0, success_krx=0, success_nxt=0, failed=0, errors=[],
        )

    uc = AsyncMock(spec=IngestDailyOhlcvUseCase)
    uc.execute = _execute
    app = _make_app(_stub_factory(uc))

    async with _client(app) as cl:
        resp = await cl.post(
            "/api/kiwoom/ohlcv/daily/sync?alias=test",
            headers={"X-API-Key": admin_key},
            json={"base_date": "2025-09-08", "only_market_codes": ["0", "10"]},
        )

    assert resp.status_code == 200
    assert captured["base_date"] == date(2025, 9, 8)
    assert captured["only_market_codes"] == ["0", "10"]


@pytest.mark.asyncio
async def test_sync_maps_value_error_to_400(admin_key: str) -> None:
    """target_date_range 위반 → ValueError → 400."""
    uc = AsyncMock(spec=IngestDailyOhlcvUseCase)
    uc.execute = AsyncMock(side_effect=ValueError("base_date 가 today - 365일 ~ today 범위 외"))
    app = _make_app(_stub_factory(uc))

    async with _client(app) as cl:
        resp = await cl.post(
            "/api/kiwoom/ohlcv/daily/sync?alias=test",
            headers={"X-API-Key": admin_key},
            json={"base_date": "1900-01-01"},
        )
    assert resp.status_code == 400


# =============================================================================
# POST /stocks/{code}/ohlcv/daily/refresh — admin
# =============================================================================


@pytest.mark.asyncio
async def test_refresh_returns_401_without_admin(admin_key: str) -> None:
    app = _make_app()
    async with _client(app) as cl:
        resp = await cl.post("/api/kiwoom/stocks/005930/ohlcv/daily/refresh?alias=test")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_returns_result_for_admin(admin_key: str) -> None:
    uc = AsyncMock(spec=IngestDailyOhlcvUseCase)
    uc.refresh_one = AsyncMock(
        return_value=OhlcvSyncResult(
            base_date=date(2025, 9, 8),
            total=1, success_krx=1, success_nxt=0, failed=0, errors=[],
        )
    )
    app = _make_app(_stub_factory(uc))

    async with _client(app) as cl:
        resp = await cl.post(
            "/api/kiwoom/stocks/005930/ohlcv/daily/refresh?alias=test",
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success_krx"] == 1


@pytest.mark.asyncio
async def test_refresh_maps_business_error_to_400(admin_key: str) -> None:
    """KiwoomBusinessError → 400. message echo 차단."""
    uc = AsyncMock(spec=IngestDailyOhlcvUseCase)
    uc.refresh_one = AsyncMock(
        side_effect=KiwoomBusinessError(api_id="ka10081", return_code=1, message="존재하지 않음")
    )
    app = _make_app(_stub_factory(uc))

    async with _client(app) as cl:
        resp = await cl.post(
            "/api/kiwoom/stocks/999999/ohlcv/daily/refresh?alias=test",
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 400
    assert "존재하지 않음" not in resp.text


@pytest.mark.asyncio
async def test_refresh_maps_credential_to_400(admin_key: str) -> None:
    uc = AsyncMock(spec=IngestDailyOhlcvUseCase)
    uc.refresh_one = AsyncMock(side_effect=KiwoomCredentialRejectedError("401"))
    app = _make_app(_stub_factory(uc))

    async with _client(app) as cl:
        resp = await cl.post(
            "/api/kiwoom/stocks/005930/ohlcv/daily/refresh?alias=test",
            headers={"X-API-Key": admin_key},
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_refresh_maps_rate_limit_to_503(admin_key: str) -> None:
    uc = AsyncMock(spec=IngestDailyOhlcvUseCase)
    uc.refresh_one = AsyncMock(side_effect=KiwoomRateLimitedError("429"))
    app = _make_app(_stub_factory(uc))

    async with _client(app) as cl:
        resp = await cl.post(
            "/api/kiwoom/stocks/005930/ohlcv/daily/refresh?alias=test",
            headers={"X-API-Key": admin_key},
        )
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_refresh_maps_upstream_to_502(admin_key: str) -> None:
    uc = AsyncMock(spec=IngestDailyOhlcvUseCase)
    uc.refresh_one = AsyncMock(side_effect=KiwoomUpstreamError("5xx"))
    app = _make_app(_stub_factory(uc))

    async with _client(app) as cl:
        resp = await cl.post(
            "/api/kiwoom/stocks/005930/ohlcv/daily/refresh?alias=test",
            headers={"X-API-Key": admin_key},
        )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_refresh_maps_validation_to_502(admin_key: str) -> None:
    uc = AsyncMock(spec=IngestDailyOhlcvUseCase)
    uc.refresh_one = AsyncMock(side_effect=KiwoomResponseValidationError("Pydantic 위반"))
    app = _make_app(_stub_factory(uc))

    async with _client(app) as cl:
        resp = await cl.post(
            "/api/kiwoom/stocks/005930/ohlcv/daily/refresh?alias=test",
            headers={"X-API-Key": admin_key},
        )
    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_refresh_value_error_for_missing_stock_or_invalid_date(admin_key: str) -> None:
    """Stock 마스터 미존재 또는 base_date 범위 외 → 404 / 400."""
    uc = AsyncMock(spec=IngestDailyOhlcvUseCase)
    uc.refresh_one = AsyncMock(side_effect=ValueError("stock master not found: 005930"))
    app = _make_app(_stub_factory(uc))

    async with _client(app) as cl:
        resp = await cl.post(
            "/api/kiwoom/stocks/005930/ohlcv/daily/refresh?alias=test",
            headers={"X-API-Key": admin_key},
        )
    assert resp.status_code == 404


# =============================================================================
# GET /stocks/{code}/ohlcv/daily — DB only
# =============================================================================


@pytest.mark.asyncio
async def test_get_ohlcv_three_scenarios_in_single_lifetime(session: AsyncSession) -> None:
    """Stock 미존재 / 빈 시계열 / 데이터 있음 — 한 client lifetime 안 (B-α/B-β/B-γ-2 패턴 일관)."""
    from decimal import Decimal

    from app.adapter.out.kiwoom.chart import NormalizedDailyOhlcv

    app = _make_app()
    async with _client(app) as cl:
        # 1. Stock 미존재
        resp1 = await cl.get(
            "/api/kiwoom/stocks/005930/ohlcv/daily?start=2025-09-01&end=2025-09-30"
        )
        assert resp1.status_code == 404

        # 2. Stock 있지만 시계열 없음
        stock_id = await _create_stock(session, "005930")
        resp2 = await cl.get(
            "/api/kiwoom/stocks/005930/ohlcv/daily?start=2025-09-01&end=2025-09-30"
        )
        assert resp2.status_code == 200
        assert resp2.json() == []

        # 3. 데이터 있음
        n = NormalizedDailyOhlcv(
            stock_id=stock_id,
            trading_date=date(2025, 9, 8),
            exchange=ExchangeType.KRX,
            adjusted=True,
            open_price=69800, high_price=70500, low_price=69600, close_price=70100,
            trade_volume=9263135, trade_amount=648525, prev_compare_amount=600,
            prev_compare_sign="2", turnover_rate=Decimal("0.16"),
        )
        repo = StockPriceRepository(session)
        await repo.upsert_many([n], exchange=ExchangeType.KRX)
        await session.commit()

        resp3 = await cl.get(
            "/api/kiwoom/stocks/005930/ohlcv/daily?start=2025-09-01&end=2025-09-30"
        )
        assert resp3.status_code == 200
        body = resp3.json()
        assert len(body) == 1
        assert body[0]["close_price"] == 70100
        assert body[0]["trading_date"] == "2025-09-08"
        assert body[0]["exchange"] == "KRX"


@pytest.mark.asyncio
async def test_get_ohlcv_rejects_inverted_window() -> None:
    """start > end → 400."""
    app = _make_app()
    async with _client(app) as cl:
        resp = await cl.get(
            "/api/kiwoom/stocks/005930/ohlcv/daily?start=2025-09-30&end=2025-09-01"
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_ohlcv_rejects_invalid_stock_code() -> None:
    """5자리 / 영문 → 422."""
    app = _make_app()
    async with _client(app) as cl:
        for invalid in ("00593", "005930_NX", "ABC123"):
            resp = await cl.get(
                f"/api/kiwoom/stocks/{invalid}/ohlcv/daily?start=2025-09-01&end=2025-09-30"
            )
            assert resp.status_code == 422


# 2b-M1 회귀 — date range cap (DoS amplification 차단)


@pytest.mark.asyncio
async def test_get_ohlcv_rejects_oversized_range() -> None:
    """date range > 400일 → 400 (DoS 차단)."""
    app = _make_app()
    async with _client(app) as cl:
        resp = await cl.get(
            "/api/kiwoom/stocks/005930/ohlcv/daily?start=1900-01-01&end=2099-12-31"
        )
    assert resp.status_code == 400
    assert "400일 초과" in resp.text or "분할" in resp.text
