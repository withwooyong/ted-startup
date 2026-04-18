"""End-to-End: /api/batch/collect → /api/signals/detect → GET /api/signals 연결 흐름.

KrxClient 는 Fake 로 대체(pykrx/KRX 네트워크 제거)하고 나머지 경로(HTTP →
Router → Service → Repository → PG → Router → 응답)는 실제 구현 그대로 사용.
Phase 7 목표인 "collect 결과가 실제로 signals 엔드포인트에 노출되는가" 검증.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.external import KrxClient
from app.adapter.out.external._records import (
    LendingBalanceRow,
    ShortSellingRow,
    StockPriceRow,
)
from app.adapter.web._deps import get_krx_client, get_session as prod_get_session
from app.config.settings import get_settings
from app.main import create_app


class _StubKrxClient(KrxClient):
    """고정 응답을 주는 KRX 클라이언트 스텁. 부모 __init__ 호출 안 함(network·env 접근 회피)."""

    def __init__(self) -> None:  # type: ignore[no-untyped-def]
        self._stub_prices = [
            StockPriceRow(
                stock_code="005930", stock_name="삼성전자", market_type="KOSPI",
                close_price=78_500, open_price=78_000, high_price=79_200, low_price=77_800,
                volume=15_234_567, market_cap=468_500_000_000_000, change_rate=Decimal("0.64"),
            ),
            StockPriceRow(
                stock_code="000660", stock_name="SK하이닉스", market_type="KOSPI",
                close_price=245_000, open_price=243_500, high_price=247_000, low_price=242_000,
                volume=3_456_789, market_cap=178_300_000_000_000, change_rate=Decimal("-1.21"),
            ),
        ]
        self._stub_shorts = [
            ShortSellingRow(
                stock_code="005930", stock_name="삼성전자",
                short_volume=1_200_000, short_amount=94_000_000_000, short_ratio=Decimal("7.88"),
            )
        ]
        self._stub_lendings = [
            # 삼성전자에 RAPID_DECLINE 임계(-10%) 초과하는 change_rate 주입은 어댑터 레코드엔 없음.
            # 수집 단계에선 balance_quantity/amount 만 upsert 되므로 change_rate 는 0 으로 저장됨.
            # 따라서 이 E2E 는 squeeze 는 안 뜨고 RAPID_DECLINE 도 안 뜰 수 있다 — 수집→탐지 체인 자체 검증이 목적.
            LendingBalanceRow(
                stock_code="005930", stock_name="삼성전자",
                balance_quantity=12_345_678, balance_amount=987_654_321_000,
            )
        ]

    async def fetch_stock_prices(self, _: date):  # type: ignore[override]
        return list(self._stub_prices)

    async def fetch_short_selling(self, _: date):  # type: ignore[override]
        return list(self._stub_shorts)

    async def fetch_lending_balance(self, _: date):  # type: ignore[override]
        return list(self._stub_lendings)


@pytest_asyncio.fixture
async def e2e_app(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[FastAPI]:
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")
    get_settings.cache_clear()
    app = create_app()

    async def _override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[prod_get_session] = _override_session
    app.dependency_overrides[get_krx_client] = _StubKrxClient
    try:
        yield app
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


@pytest_asyncio.fixture
async def e2e_client(e2e_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=e2e_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_collect_then_detect_then_list_signals_chain(
    e2e_client: httpx.AsyncClient,
) -> None:
    target = date(2026, 4, 17)
    params = {"date": target.isoformat()}
    admin = {"X-API-Key": "test-admin-key"}

    # 1) 수집 — KRX 스텁 → DB 에 2종목 가격/공매도/대차 upsert
    resp = await e2e_client.post("/api/batch/collect", params=params, headers=admin)
    assert resp.status_code == 200, resp.text
    collect = resp.json()
    assert collect["stocks_upserted"] == 2
    assert collect["stock_prices_upserted"] == 2
    assert collect["short_selling_upserted"] == 1
    assert collect["lending_balance_upserted"] == 1

    # 2) 탐지 — 수집된 데이터 기반으로 시그널 탐지 (데이터 조건상 0건도 허용)
    resp = await e2e_client.post("/api/signals/detect", params=params, headers=admin)
    assert resp.status_code == 200, resp.text
    detect = resp.json()
    assert {"rapid_decline", "trend_reversal", "short_squeeze", "elapsed_ms"} <= set(detect.keys())

    # 3) 조회 — 당일 시그널 목록. 데이터가 없더라도 빈 배열이 반환되어야 한다.
    resp = await e2e_client.get("/api/signals", params=params)
    assert resp.status_code == 200, resp.text
    signals = resp.json()
    assert isinstance(signals, list)


@pytest.mark.asyncio
async def test_stock_detail_returns_upserted_stock_after_collect(
    e2e_client: httpx.AsyncClient,
) -> None:
    target = date(2026, 4, 17)
    admin = {"X-API-Key": "test-admin-key"}

    # 수집 후 /api/stocks/005930 에서 종목 정보 + 시세 확인
    resp = await e2e_client.post("/api/batch/collect", params={"date": target.isoformat()}, headers=admin)
    assert resp.status_code == 200

    resp = await e2e_client.get(
        "/api/stocks/005930", params={"from": "2026-04-01", "to": target.isoformat()}
    )
    assert resp.status_code == 200, resp.text
    detail = resp.json()
    assert detail["stock"]["stock_code"] == "005930"
    assert detail["stock"]["stock_name"] == "삼성전자"
    assert len(detail["prices"]) == 1
    price = detail["prices"][0]
    assert price["close_price"] == 78_500
    assert price["trading_date"] == target.isoformat()
