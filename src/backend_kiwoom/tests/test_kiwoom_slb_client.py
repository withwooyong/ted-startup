"""KiwoomLendingClient — fetch_market_trend (ka10068) + fetch_stock_trend (ka20068).

설계: endpoint-16-ka10068.md § 6.1 + endpoint-17-ka20068.md § 6.1.
chunk = Phase E, plan doc endpoint-15-ka10014.md § 12 참조.

검증 (12 시나리오):

fetch_market_trend (ka10068) — 7건:
1. 정상 단일 페이지 (200 + dbrt_trde_trnsn 5건)
2. 페이지네이션 (cont-yn=Y → N)
3. 빈 list (dbrt_trde_trnsn=[])
4. return_code=1 → KiwoomBusinessError
5. dt="" row 자동 skip (to_normalized → date.min)
6. delta_volume 부호 (dbrt_trde_irds="-13717978" → -13717978)
7. 페이지네이션 폭주 → KiwoomMaxPagesExceededError

fetch_stock_trend (ka20068) — 5건:
8. 정상 단일 페이지
9. stock_code 7자리 → ValueError (Length=6 검증)
10. 빈 list (대차 없는 종목)
11. return_code=1 → KiwoomBusinessError
12. dt="" row skip (to_normalized → date.min)
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from typing import Any

import httpx
import pytest
from app.adapter.out.kiwoom.slb import KiwoomLendingClient

from app.adapter.out.kiwoom._client import KiwoomClient, KiwoomMaxPagesExceededError
from app.adapter.out.kiwoom._exceptions import KiwoomBusinessError
from app.adapter.out.kiwoom._records import (
    LendingMarketResponse,
    LendingMarketRow,
    LendingScope,
    LendingStockResponse,
    LendingStockRow,
    NormalizedLendingMarket,
)

# ---------------------------------------------------------------------------
# 공통 픽스처
# ---------------------------------------------------------------------------

_MARKET_BODY: dict[str, Any] = {
    "dbrt_trde_trnsn": [
        {
            "dt": "20250430",
            "dbrt_trde_cntrcnt": "35330036",
            "dbrt_trde_rpy": "25217364",
            "dbrt_trde_irds": "10112672",
            "rmnd": "2460259444",
            "remn_amt": "73956254",
        },
        {
            "dt": "20250428",
            "dbrt_trde_cntrcnt": "17165250",
            "dbrt_trde_rpy": "30883228",
            "dbrt_trde_irds": "-13717978",
            "rmnd": "2276180199",
            "remn_amt": "68480718",
        },
    ],
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다",
}

_STOCK_BODY: dict[str, Any] = {
    "dbrt_trde_trnsn": [
        {
            "dt": "20250430",
            "dbrt_trde_cntrcnt": "1210354",
            "dbrt_trde_rpy": "2693108",
            "dbrt_trde_irds": "-1482754",
            "rmnd": "98242435",
            "remn_amt": "5452455",
        },
        {
            "dt": "20250428",
            "dbrt_trde_cntrcnt": "958772",
            "dbrt_trde_rpy": "3122807",
            "dbrt_trde_irds": "-2164035",
            "rmnd": "100245885",
            "remn_amt": "5593720",
        },
    ],
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다",
}


async def _const_token() -> str:
    return "FixedToken-" + "X" * 100


def _make_kiwoom_client(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    max_pages: int = 5,
) -> KiwoomClient:
    return KiwoomClient(
        base_url="https://api.kiwoom.com",
        token_provider=_const_token,
        transport=httpx.MockTransport(handler),
        max_attempts=1,
        retry_min_wait=0.0,
        retry_max_wait=0.0,
        min_request_interval_seconds=0.0,
    )


# ===========================================================================
# fetch_market_trend (ka10068)
# ===========================================================================

# ---------- 1. 정상 단일 페이지 ----------


@pytest.mark.asyncio
async def test_fetch_market_trend_single_page_returns_rows() -> None:
    """200 + dbrt_trde_trnsn 2건 → LendingMarketRow list 반환.

    api-id=ka10068 헤더 + URL /api/dostk/slb + body all_tp=1 확인.
    """
    captured_body: dict[str, Any] = {}
    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        captured_headers["api-id"] = request.headers.get("api-id", "")
        assert request.url.path == "/api/dostk/slb"
        return httpx.Response(200, json=_MARKET_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomLendingClient(kc)
        rows = await adapter.fetch_market_trend()

    assert len(rows) == 2
    assert isinstance(rows[0], LendingMarketRow)
    assert rows[0].dt == "20250430"
    assert rows[1].dbrt_trde_irds == "-13717978"
    assert captured_headers["api-id"] == "ka10068"
    assert captured_body.get("all_tp") == "1"


# ---------- 2. 페이지네이션 (cont-yn=Y → N) ----------


@pytest.mark.asyncio
async def test_fetch_market_trend_paginates_with_cont_yn() -> None:
    """cont-yn=Y → 다음 페이지 자동 호출. 모든 row 합쳐짐."""
    page2_body: dict[str, Any] = {
        "dbrt_trde_trnsn": [
            {
                "dt": "20250425",
                "dbrt_trde_cntrcnt": "20000000",
                "dbrt_trde_rpy": "15000000",
                "dbrt_trde_irds": "5000000",
                "rmnd": "2200000000",
                "remn_amt": "66000000",
            }
        ],
        "return_code": 0,
        "return_msg": "정상",
    }
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(
                200, json=_MARKET_BODY, headers={"cont-yn": "Y", "next-key": "p2"}
            )
        return httpx.Response(200, json=page2_body, headers={"cont-yn": "N"})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomLendingClient(kc)
        rows = await adapter.fetch_market_trend()

    assert len(rows) == 3, f"page1 (2) + page2 (1) = 3 / call_count={call_count}"
    assert call_count == 2


# ---------- 3. 빈 list ----------


@pytest.mark.asyncio
async def test_fetch_market_trend_empty_list_returns_empty() -> None:
    """dbrt_trde_trnsn=[] → 빈 list 반환 (정상)."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"dbrt_trde_trnsn": [], "return_code": 0, "return_msg": "정상"},
        )

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomLendingClient(kc)
        rows = await adapter.fetch_market_trend()

    assert rows == []


# ---------- 4. return_code=1 → KiwoomBusinessError ----------


@pytest.mark.asyncio
async def test_fetch_market_trend_business_error_on_nonzero_return_code() -> None:
    """return_code=1 → KiwoomBusinessError (api_id=ka10068, return_code=1)."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"return_code": 1, "return_msg": "조회 가능 일자가 아닙니다"}
        )

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomLendingClient(kc)
        with pytest.raises(KiwoomBusinessError) as exc_info:
            await adapter.fetch_market_trend(
                start_date=date(1900, 1, 1),
                end_date=date(1900, 1, 2),
            )

    assert exc_info.value.return_code == 1


# ---------- 5. dt="" row → date.min (to_normalized skip 대상) ----------


def test_lending_market_row_empty_dt_yields_date_min() -> None:
    """dt="" → to_normalized → trading_date=date.min (repository skip 안전망)."""
    row = LendingMarketRow(
        dt="",
        dbrt_trde_cntrcnt="35330036",
        dbrt_trde_rpy="25217364",
        dbrt_trde_irds="10112672",
        rmnd="2460259444",
        remn_amt="73956254",
    )
    normalized: NormalizedLendingMarket = row.to_normalized(scope=LendingScope.MARKET)
    assert normalized.trading_date == date.min
    assert normalized.scope == LendingScope.MARKET
    assert normalized.stock_id is None


# ---------- 6. delta_volume 부호 ----------


def test_lending_market_row_negative_delta_volume() -> None:
    """dbrt_trde_irds="-13717978" → delta_volume=-13717978 (부호 보존).

    endpoint-16 § 3.1 / § 11.2 H-8 확인.
    """
    row = LendingMarketRow(
        dt="20250428",
        dbrt_trde_cntrcnt="17165250",
        dbrt_trde_rpy="30883228",
        dbrt_trde_irds="-13717978",
        rmnd="2276180199",
        remn_amt="68480718",
    )
    normalized: NormalizedLendingMarket = row.to_normalized(scope=LendingScope.MARKET)

    assert normalized.delta_volume == -13717978
    assert normalized.contracted_volume == 17165250
    assert normalized.repaid_volume == 30883228
    assert normalized.balance_volume == 2276180199
    assert normalized.balance_amount == 68480718
    assert normalized.stock_id is None
    assert normalized.scope == LendingScope.MARKET
    assert normalized.trading_date == date(2025, 4, 28)


# ---------- 7. 페이지네이션 폭주 → KiwoomMaxPagesExceededError ----------


@pytest.mark.asyncio
async def test_fetch_market_trend_raises_on_pagination_limit() -> None:
    """cont-yn=Y 무한 → max_pages 도달 시 KiwoomMaxPagesExceededError.

    endpoint-16 § 9.1 폭주 시나리오.
    """

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=_MARKET_BODY, headers={"cont-yn": "Y", "next-key": "infinite"}
        )

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomLendingClient(kc)
        with pytest.raises(KiwoomMaxPagesExceededError):
            await adapter.fetch_market_trend(max_pages=3)


# ===========================================================================
# fetch_stock_trend (ka20068)
# ===========================================================================

# ---------- 8. 정상 단일 페이지 ----------


@pytest.mark.asyncio
async def test_fetch_stock_trend_single_page_returns_rows() -> None:
    """200 + dbrt_trde_trnsn 2건 → LendingStockRow list 반환.

    api-id=ka20068 헤더 + body stk_cd=005930 + all_tp=0 확인.
    """
    captured_body: dict[str, Any] = {}
    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        captured_headers["api-id"] = request.headers.get("api-id", "")
        assert request.url.path == "/api/dostk/slb"
        return httpx.Response(200, json=_STOCK_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomLendingClient(kc)
        rows = await adapter.fetch_stock_trend("005930")

    assert len(rows) == 2
    assert isinstance(rows[0], LendingStockRow)
    assert rows[0].dt == "20250430"
    assert captured_headers["api-id"] == "ka20068"
    assert captured_body.get("stk_cd") == "005930"
    assert captured_body.get("all_tp") == "0"


# ---------- 9. stock_code 7자리 → ValueError ----------


@pytest.mark.asyncio
async def test_fetch_stock_trend_rejects_seven_digit_code() -> None:
    """stk_cd 7자리 → ValueError (Length=6 검증).

    endpoint-17 § 2.2 ★ stk_cd Length=6 / § 12.2 결정 #4 KRX only.
    NXT suffix `005930_NX` (8자리) 도 거부.
    """
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=_STOCK_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomLendingClient(kc)
        for invalid in ("0059301", "005930_NX", "00593", "", "12345678"):
            with pytest.raises(ValueError):
                await adapter.fetch_stock_trend(invalid)

    assert call_count == 0, "검증 실패 시 HTTP 호출 없어야 함"


# ---------- 10. 빈 list (대차 없는 종목) ----------


@pytest.mark.asyncio
async def test_fetch_stock_trend_empty_list_for_no_lending_stock() -> None:
    """대차 거래 없는 종목 → 빈 list (정상, endpoint-17 § 11.2 ETF/우선주)."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"dbrt_trde_trnsn": [], "return_code": 0, "return_msg": "정상"},
        )

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomLendingClient(kc)
        rows = await adapter.fetch_stock_trend("005930")

    assert rows == []


# ---------- 11. return_code=1 → KiwoomBusinessError ----------


@pytest.mark.asyncio
async def test_fetch_stock_trend_business_error_on_nonzero_return_code() -> None:
    """return_code=1 → KiwoomBusinessError (api_id=ka20068)."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"return_code": 1, "return_msg": "조회 가능 일자가 아닙니다"}
        )

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomLendingClient(kc)
        with pytest.raises(KiwoomBusinessError) as exc_info:
            await adapter.fetch_stock_trend("005930")

    assert exc_info.value.return_code == 1


# ---------- 12. dt="" row → date.min (to_normalized skip) ----------


def test_lending_stock_row_empty_dt_yields_date_min() -> None:
    """dt="" → to_normalized → trading_date=date.min (repository skip 안전망).

    endpoint-17 § 9.1 dt="" row skip 시나리오.
    """
    row = LendingStockRow(
        dt="",
        dbrt_trde_cntrcnt="1210354",
        dbrt_trde_rpy="2693108",
        dbrt_trde_irds="-1482754",
        rmnd="98242435",
        remn_amt="5452455",
    )
    normalized: NormalizedLendingMarket = row.to_normalized(stock_id=42)
    assert normalized.trading_date == date.min
    assert normalized.scope == LendingScope.STOCK
    assert normalized.stock_id == 42


# ---------------------------------------------------------------------------
# 추가: LendingMarketResponse / LendingStockResponse Pydantic 검증
# ---------------------------------------------------------------------------


def test_lending_market_response_parses_full_body() -> None:
    """LendingMarketResponse — 전체 body Pydantic 파싱."""
    resp = LendingMarketResponse.model_validate(_MARKET_BODY)
    assert resp.return_code == 0
    assert len(resp.dbrt_trde_trnsn) == 2


def test_lending_stock_response_parses_full_body() -> None:
    """LendingStockResponse — 전체 body Pydantic 파싱."""
    resp = LendingStockResponse.model_validate(_STOCK_BODY)
    assert resp.return_code == 0
    assert len(resp.dbrt_trde_trnsn) == 2
