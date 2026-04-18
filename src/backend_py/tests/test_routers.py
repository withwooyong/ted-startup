"""FastAPI 라우터 통합 테스트.

구성:
- testcontainers PG16 + Alembic 마이그레이션(conftest 공유)
- FastAPI get_session 의존성을 테스트 세션 픽스처로 오버라이드해 각 테스트의
  트랜잭션 격리(rollback) 유지
- ASGITransport + httpx.AsyncClient 로 실제 라우팅·직렬화 경로 검증
"""
from __future__ import annotations

from datetime import date
from typing import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.web._deps import get_session as prod_get_session
from app.adapter.out.persistence.models import (
    BacktestResult,
    Signal,
    SignalType,
    Stock,
)
from app.adapter.out.persistence.repositories import (
    BacktestResultRepository,
    SignalRepository,
    StockRepository,
)
from app.config.settings import get_settings
from app.main import create_app


@pytest_asyncio.fixture
async def app_with_session(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[FastAPI]:
    """테스트 세션을 주입한 FastAPI 앱 — admin_api_key 고정."""
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")
    get_settings.cache_clear()

    app = create_app()

    async def _override() -> AsyncIterator[AsyncSession]:
        yield session  # 트랜잭션 커밋/롤백은 conftest 세션 픽스처가 담당

    app.dependency_overrides[prod_get_session] = _override
    try:
        yield app
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


@pytest_asyncio.fixture
async def client(app_with_session: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app_with_session)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# -----------------------------------------------------------------------------
# /api/signals
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_signals_filters_by_date_and_type(
    session: AsyncSession, client: httpx.AsyncClient
) -> None:
    stock = await StockRepository(session).add(
        Stock(stock_code="005930", stock_name="삼성전자", market_type="KOSPI")
    )
    sr = SignalRepository(session)
    await sr.add(
        Signal(
            stock_id=stock.id, signal_date=date(2026, 4, 17),
            signal_type=SignalType.RAPID_DECLINE.value, score=85, grade="A", detail={},
        )
    )
    await sr.add(
        Signal(
            stock_id=stock.id, signal_date=date(2026, 4, 17),
            signal_type=SignalType.SHORT_SQUEEZE.value, score=70, grade="B", detail={},
        )
    )

    resp = await client.get("/api/signals", params={"date": "2026-04-17"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert {b["signal_type"] for b in body} == {"RAPID_DECLINE", "SHORT_SQUEEZE"}
    assert body[0]["stock_code"] == "005930"

    resp = await client.get("/api/signals", params={"date": "2026-04-17", "type": "RAPID_DECLINE"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_stock_detail_returns_404_when_code_unknown(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/stocks/999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stock_detail_rejects_malformed_code(client: httpx.AsyncClient) -> None:
    # 6자리 숫자 패턴 위반 → 422 (FastAPI path validation)
    resp = await client.get("/api/stocks/ABC123")
    assert resp.status_code == 400 or resp.status_code == 422


# -----------------------------------------------------------------------------
# Admin auth guard
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detect_signals_without_api_key_returns_401(client: httpx.AsyncClient) -> None:
    resp = await client.post("/api/signals/detect")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_detect_signals_with_wrong_api_key_returns_401(client: httpx.AsyncClient) -> None:
    resp = await client.post("/api/signals/detect", headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_detect_signals_with_valid_api_key_returns_200(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/api/signals/detect",
        headers={"X-API-Key": "test-admin-key"},
        params={"date": date(2026, 4, 17).isoformat()},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert {"rapid_decline", "trend_reversal", "short_squeeze", "elapsed_ms"} <= set(body.keys())


# -----------------------------------------------------------------------------
# /api/backtest
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_latest_backtest_results_returns_one_per_type(
    session: AsyncSession, client: httpx.AsyncClient
) -> None:
    repo = BacktestResultRepository(session)
    # 같은 시그널 타입으로 2건(이전/최근) → 최근 1건만 반환돼야 함
    await repo.add(BacktestResult(
        signal_type=SignalType.RAPID_DECLINE.value,
        period_start=date(2025, 1, 1), period_end=date(2025, 6, 30),
        total_signals=50,
    ))
    await repo.add(BacktestResult(
        signal_type=SignalType.RAPID_DECLINE.value,
        period_start=date(2025, 7, 1), period_end=date(2025, 12, 31),
        total_signals=80,
    ))
    await repo.add(BacktestResult(
        signal_type=SignalType.TREND_REVERSAL.value,
        period_start=date(2025, 1, 1), period_end=date(2025, 12, 31),
        total_signals=30,
    ))

    resp = await client.get("/api/backtest")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2  # 2개 타입만 데이터 있으니 2건
    rapid = next(b for b in body if b["signal_type"] == "RAPID_DECLINE")
    # 최근 기간(2025-07~12)이 반환됐는지
    assert rapid["period_end"] == "2025-12-31"
    assert rapid["total_signals"] == 80


@pytest.mark.asyncio
async def test_backtest_run_rejects_future_end_date(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/api/backtest/run",
        headers={"X-API-Key": "test-admin-key"},
        params={"from": "2026-01-01", "to": "2099-01-01"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_backtest_run_rejects_inverted_range(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/api/backtest/run",
        headers={"X-API-Key": "test-admin-key"},
        params={"from": "2026-04-10", "to": "2026-04-01"},
    )
    assert resp.status_code == 400


# -----------------------------------------------------------------------------
# /api/notifications/preferences
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_notification_preferences_creates_singleton(
    client: httpx.AsyncClient,
) -> None:
    resp = await client.get("/api/notifications/preferences")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == 1
    assert body["min_score"] == 60
    assert set(body["signal_types"]) == {"RAPID_DECLINE", "TREND_REVERSAL", "SHORT_SQUEEZE"}


@pytest.mark.asyncio
async def test_update_notification_preferences_requires_admin_key(
    client: httpx.AsyncClient,
) -> None:
    resp = await client.put(
        "/api/notifications/preferences",
        json={
            "daily_summary_enabled": True,
            "urgent_alert_enabled": True,
            "batch_failure_enabled": True,
            "weekly_report_enabled": True,
            "min_score": 70,
            "signal_types": ["RAPID_DECLINE"],
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_notification_preferences_applies_changes(
    client: httpx.AsyncClient,
) -> None:
    resp = await client.put(
        "/api/notifications/preferences",
        headers={"X-API-Key": "test-admin-key"},
        json={
            "daily_summary_enabled": False,
            "urgent_alert_enabled": True,
            "batch_failure_enabled": False,
            "weekly_report_enabled": True,
            "min_score": 75,
            "signal_types": ["SHORT_SQUEEZE"],
        },
    )
    assert resp.status_code == 200, f"response body: {resp.text}"
    body = resp.json()
    assert body["daily_summary_enabled"] is False
    assert body["min_score"] == 75
    assert body["signal_types"] == ["SHORT_SQUEEZE"]


@pytest.mark.asyncio
async def test_update_notification_preferences_validates_min_score(
    client: httpx.AsyncClient,
) -> None:
    resp = await client.put(
        "/api/notifications/preferences",
        headers={"X-API-Key": "test-admin-key"},
        json={
            "daily_summary_enabled": True,
            "urgent_alert_enabled": True,
            "batch_failure_enabled": True,
            "weekly_report_enabled": True,
            "min_score": 150,  # 0-100 범위 초과
            "signal_types": ["RAPID_DECLINE"],
        },
    )
    assert resp.status_code == 400


# -----------------------------------------------------------------------------
# OpenAPI schema sanity
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_openapi_exposes_all_routes(client: httpx.AsyncClient) -> None:
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    paths = set(resp.json()["paths"].keys())
    expected = {
        "/api/signals",
        "/api/stocks/{stock_code}",
        "/api/signals/detect",
        "/api/backtest",
        "/api/backtest/run",
        "/api/notifications/preferences",
        "/api/batch/collect",
    }
    missing = expected - paths
    assert not missing, f"OpenAPI 에 누락된 경로: {missing}"
