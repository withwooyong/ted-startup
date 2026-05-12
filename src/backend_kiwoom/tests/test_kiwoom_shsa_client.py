"""KiwoomShortSellingClient.fetch_trend (ka10014) — Phase E 어댑터 + 정규화.

설계: endpoint-15-ka10014.md § 6.1 / § 9.1.

검증:
1. 정상 단일 페이지 (200 + list 5건)
2. 페이지네이션 (첫 cont-yn=Y, 둘째 N)
3. 빈 list (공매도 없는 종목)
4. return_code=1 → KiwoomBusinessError
5. 401 → KiwoomCredentialRejectedError
6. stock_code "00593" 5자리 → ValueError
7. ExchangeType.NXT → stk_cd build "005930_NX"
8. tm_tp 분기 START_ONLY → body tm_tp="0"
9. dt="" row → 자동 skip (upsert_many 에서 처리 — 테스트는 row 반환 확인)
10. close_pric="-55800" → _to_int -55800
11. flu_rt="-1.76" → _to_decimal -1.76
12. trde_wght="+8.58" → _to_decimal 8.58
13. 페이지네이션 폭주 → KiwoomMaxPagesExceededError (max_pages=5)

NOTE: ShortSellingClient, ShortSellingRow, ShortSellingResponse, ShortSellingTimeType,
      NormalizedShortSelling 는 Step 1 에서 작성. 본 테스트는 import 실패가 red 의도.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest
from app.adapter.out.kiwoom.shsa import (  # type: ignore[import]  # Step 1 에서 작성
    KiwoomShortSellingClient,
    ShortSellingTimeType,
)

from app.adapter.out.kiwoom._client import KiwoomClient, KiwoomMaxPagesExceededError
from app.adapter.out.kiwoom._exceptions import (
    KiwoomBusinessError,
    KiwoomCredentialRejectedError,
)
from app.adapter.out.kiwoom._records import (  # type: ignore[import]  # Step 1 에서 추가
    NormalizedShortSelling,
    ShortSellingResponse,
    ShortSellingRow,
)
from app.application.constants import ExchangeType

# ---------------------------------------------------------------------------
# 공통 fixture
# ---------------------------------------------------------------------------

_SAMSUNG_SHSA_BODY: dict[str, Any] = {
    "shrts_trnsn": [
        {
            "dt": "20250519",
            "close_pric": "-55800",
            "pred_pre_sig": "5",
            "pred_pre": "-1000",
            "flu_rt": "-1.76",
            "trde_qty": "9802105",
            "shrts_qty": "841407",
            "ovr_shrts_qty": "6424755",
            "trde_wght": "+8.58",
            "shrts_trde_prica": "46985302",
            "shrts_avg_pric": "55841",
        },
        {
            "dt": "20250516",
            "close_pric": "-56800",
            "pred_pre_sig": "5",
            "pred_pre": "-500",
            "flu_rt": "-0.87",
            "trde_qty": "10385352",
            "shrts_qty": "487354",
            "ovr_shrts_qty": "5583348",
            "trde_wght": "+4.69",
            "shrts_trde_prica": "27725268",
            "shrts_avg_pric": "56889",
        },
        {
            "dt": "20250515",
            "close_pric": "57300",
            "pred_pre_sig": "2",
            "pred_pre": "+500",
            "flu_rt": "+0.88",
            "trde_qty": "8000000",
            "shrts_qty": "300000",
            "ovr_shrts_qty": "5095994",
            "trde_wght": "+3.75",
            "shrts_trde_prica": "17190000",
            "shrts_avg_pric": "57350",
        },
        {
            "dt": "20250514",
            "close_pric": "56800",
            "pred_pre_sig": "3",
            "pred_pre": "0",
            "flu_rt": "0.00",
            "trde_qty": "7500000",
            "shrts_qty": "200000",
            "ovr_shrts_qty": "4795994",
            "trde_wght": "+2.67",
            "shrts_trde_prica": "11360000",
            "shrts_avg_pric": "56820",
        },
        {
            "dt": "20250513",
            "close_pric": "56800",
            "pred_pre_sig": "3",
            "pred_pre": "0",
            "flu_rt": "0.00",
            "trde_qty": "7000000",
            "shrts_qty": "150000",
            "ovr_shrts_qty": "4595994",
            "trde_wght": "+2.14",
            "shrts_trde_prica": "8520000",
            "shrts_avg_pric": "56800",
        },
    ],
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다",
}


async def _const_token() -> str:
    return "FixedToken-" + "X" * 100


def _make_kiwoom_client(handler: Callable[[httpx.Request], httpx.Response]) -> KiwoomClient:
    return KiwoomClient(
        base_url="https://api.kiwoom.com",
        token_provider=_const_token,
        transport=httpx.MockTransport(handler),
        max_attempts=1,
        retry_min_wait=0.0,
        retry_max_wait=0.0,
        min_request_interval_seconds=0.0,
    )


# ---------------------------------------------------------------------------
# 1. 정상 단일 페이지
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_trend_returns_rows_for_single_page() -> None:
    """단일 페이지 응답 5건 → ShortSellingRow list 5건.

    api-id=ka10014, URL=/api/dostk/shsa, body stk_cd/tm_tp/strt_dt/end_dt 검증.
    """
    captured_body: dict[str, str] = {}
    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        captured_headers["api-id"] = request.headers.get("api-id", "")
        assert request.url.path == "/api/dostk/shsa"
        return httpx.Response(200, json=_SAMSUNG_SHSA_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomShortSellingClient(kc)
        rows = await adapter.fetch_trend(
            "005930",
            start_date=date(2025, 5, 13),
            end_date=date(2025, 5, 19),
        )

    assert len(rows) == 5
    assert isinstance(rows[0], ShortSellingRow)
    assert rows[0].dt == "20250519"
    assert captured_headers["api-id"] == "ka10014"
    assert captured_body.get("stk_cd") == "005930"
    assert captured_body.get("strt_dt") == "20250513"
    assert captured_body.get("end_dt") == "20250519"


# ---------------------------------------------------------------------------
# 2. cont-yn 페이지네이션
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_trend_paginates_with_cont_yn() -> None:
    """cont-yn=Y → 다음 페이지 자동 호출. 모든 row 합쳐짐."""
    page2_body: dict[str, Any] = {
        "shrts_trnsn": [
            {
                "dt": "20250512",
                "close_pric": "57000",
                "pred_pre_sig": "2",
                "pred_pre": "+200",
                "flu_rt": "+0.35",
                "trde_qty": "6500000",
                "shrts_qty": "100000",
                "ovr_shrts_qty": "4445994",
                "trde_wght": "+1.54",
                "shrts_trde_prica": "5700000",
                "shrts_avg_pric": "57000",
            }
        ],
        "return_code": 0,
        "return_msg": "정상",
    }
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, json=_SAMSUNG_SHSA_BODY, headers={"cont-yn": "Y", "next-key": "p2"})
        return httpx.Response(200, json=page2_body, headers={"cont-yn": "N"})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomShortSellingClient(kc)
        rows = await adapter.fetch_trend(
            "005930",
            start_date=date(2025, 5, 12),
            end_date=date(2025, 5, 19),
        )

    assert len(rows) == 6, f"page1 (5) + page2 (1) = 6 / call_count={call_count}"
    assert call_count == 2


# ---------------------------------------------------------------------------
# 3. 빈 list (공매도 없는 종목)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_trend_returns_empty_list_for_no_short_selling() -> None:
    """200 + shrts_trnsn=[] → 빈 list 반환 (정상 — 공매도 없는 종목)."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"shrts_trnsn": [], "return_code": 0, "return_msg": "정상"},
        )

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomShortSellingClient(kc)
        rows = await adapter.fetch_trend(
            "005930",
            start_date=date(2025, 5, 13),
            end_date=date(2025, 5, 19),
        )

    assert rows == []


# ---------------------------------------------------------------------------
# 4. return_code=1 → KiwoomBusinessError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_trend_propagates_business_error() -> None:
    """return_code != 0 → KiwoomBusinessError."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"return_code": 1, "return_msg": "조회 가능 일자가 아님"})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomShortSellingClient(kc)
        with pytest.raises(KiwoomBusinessError) as exc_info:
            await adapter.fetch_trend(
                "005930",
                start_date=date(2025, 5, 13),
                end_date=date(2025, 5, 19),
            )

    assert exc_info.value.return_code == 1


# ---------------------------------------------------------------------------
# 5. 401 → KiwoomCredentialRejectedError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_trend_propagates_credential_rejected() -> None:
    """401 → KiwoomCredentialRejectedError 전파."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomShortSellingClient(kc)
        with pytest.raises(KiwoomCredentialRejectedError):
            await adapter.fetch_trend(
                "005930",
                start_date=date(2025, 5, 13),
                end_date=date(2025, 5, 19),
            )


# ---------------------------------------------------------------------------
# 6. stock_code 5자리 → ValueError (호출 차단)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_trend_rejects_invalid_stock_code() -> None:
    """6자리 숫자 외 stock_code 거부 → ValueError, HTTP 호출 없음."""
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=_SAMSUNG_SHSA_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomShortSellingClient(kc)
        for invalid in ("00593", "0059300", "abcdef", "", "      "):
            with pytest.raises(ValueError):
                await adapter.fetch_trend(
                    invalid,
                    start_date=date(2025, 5, 13),
                    end_date=date(2025, 5, 19),
                )

    assert call_count == 0, "잘못된 stock_code 로 HTTP 호출 없어야 함"


# ---------------------------------------------------------------------------
# 7. ExchangeType.NXT → stk_cd build "005930_NX"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_trend_nxt_appends_nx_suffix() -> None:
    """ExchangeType.NXT → request body stk_cd="005930_NX"."""
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=_SAMSUNG_SHSA_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomShortSellingClient(kc)
        await adapter.fetch_trend(
            "005930",
            start_date=date(2025, 5, 13),
            end_date=date(2025, 5, 19),
            exchange=ExchangeType.NXT,
        )

    assert captured["stk_cd"] == "005930_NX"


# ---------------------------------------------------------------------------
# 8. tm_tp 분기 START_ONLY → body tm_tp="0"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_trend_tm_tp_start_only_sends_zero() -> None:
    """ShortSellingTimeType.START_ONLY → request body tm_tp='0'."""
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=_SAMSUNG_SHSA_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomShortSellingClient(kc)
        await adapter.fetch_trend(
            "005930",
            start_date=date(2025, 5, 13),
            end_date=date(2025, 5, 19),
            tm_tp=ShortSellingTimeType.START_ONLY,
        )

    assert captured["tm_tp"] == "0"


@pytest.mark.asyncio
async def test_fetch_trend_tm_tp_period_sends_one() -> None:
    """ShortSellingTimeType.PERIOD (default) → request body tm_tp='1'."""
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=_SAMSUNG_SHSA_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomShortSellingClient(kc)
        await adapter.fetch_trend(
            "005930",
            start_date=date(2025, 5, 13),
            end_date=date(2025, 5, 19),
            tm_tp=ShortSellingTimeType.PERIOD,
        )

    assert captured["tm_tp"] == "1"


# ---------------------------------------------------------------------------
# 9. dt="" row — ShortSellingRow 는 raw 그대로 반환, repository 가 skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_trend_returns_row_with_empty_dt() -> None:
    """dt='' row 포함 응답 → fetch_trend 는 raw row 그대로 반환 (skip 은 upsert_many 담당)."""
    body: dict[str, Any] = {
        "shrts_trnsn": [
            {
                "dt": "",
                "close_pric": "55800",
                "pred_pre_sig": "",
                "pred_pre": "",
                "flu_rt": "",
                "trde_qty": "",
                "shrts_qty": "",
                "ovr_shrts_qty": "",
                "trde_wght": "",
                "shrts_trde_prica": "",
                "shrts_avg_pric": "",
            },
        ]
        + _SAMSUNG_SHSA_BODY["shrts_trnsn"][:4],
        "return_code": 0,
        "return_msg": "정상",
    }

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomShortSellingClient(kc)
        rows = await adapter.fetch_trend(
            "005930",
            start_date=date(2025, 5, 13),
            end_date=date(2025, 5, 19),
        )

    assert len(rows) == 5
    assert rows[0].dt == ""  # dt="" row 는 raw 그대로
    assert isinstance(rows[0], ShortSellingRow)


# ---------------------------------------------------------------------------
# 10. close_pric="-55800" → _to_int → -55800
# ---------------------------------------------------------------------------


def test_short_selling_row_to_normalized_negative_close_price() -> None:
    """close_pric='-55800' → NormalizedShortSelling.close_price == -55800."""
    row = ShortSellingRow(
        dt="20250519",
        close_pric="-55800",
        pred_pre_sig="5",
        pred_pre="-1000",
        flu_rt="-1.76",
        trde_qty="9802105",
        shrts_qty="841407",
        ovr_shrts_qty="6424755",
        trde_wght="+8.58",
        shrts_trde_prica="46985302",
        shrts_avg_pric="55841",
    )

    n: NormalizedShortSelling = row.to_normalized(stock_id=42, exchange=ExchangeType.KRX)

    assert n.close_price == -55800
    assert n.stock_id == 42
    assert n.trading_date == date(2025, 5, 19)
    assert n.exchange == ExchangeType.KRX


# ---------------------------------------------------------------------------
# 11. flu_rt="-1.76" → _to_decimal → Decimal("-1.76")
# ---------------------------------------------------------------------------


def test_short_selling_row_to_normalized_negative_change_rate() -> None:
    """flu_rt='-1.76' → NormalizedShortSelling.change_rate == Decimal('-1.76')."""
    row = ShortSellingRow(
        dt="20250519",
        close_pric="-55800",
        flu_rt="-1.76",
        trde_wght="+8.58",
    )

    n = row.to_normalized(stock_id=1, exchange=ExchangeType.KRX)

    assert n.change_rate == Decimal("-1.76")


# ---------------------------------------------------------------------------
# 12. trde_wght="+8.58" → _to_decimal → Decimal("8.58")
# ---------------------------------------------------------------------------


def test_short_selling_row_to_normalized_positive_trade_weight() -> None:
    """trde_wght='+8.58' → NormalizedShortSelling.short_trade_weight == Decimal('8.58')."""
    row = ShortSellingRow(
        dt="20250519",
        close_pric="-55800",
        flu_rt="-1.76",
        trde_wght="+8.58",
    )

    n = row.to_normalized(stock_id=1, exchange=ExchangeType.KRX)

    assert n.short_trade_weight == Decimal("8.58")


# ---------------------------------------------------------------------------
# 13. 페이지네이션 폭주 → KiwoomMaxPagesExceededError (max_pages=5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_trend_raises_on_pagination_limit() -> None:
    """무한 cont-yn=Y → max_pages=5 도달 시 KiwoomMaxPagesExceededError."""
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            200, json=_SAMSUNG_SHSA_BODY, headers={"cont-yn": "Y", "next-key": f"p{call_count}"}
        )

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomShortSellingClient(kc)
        with pytest.raises(KiwoomMaxPagesExceededError):
            await adapter.fetch_trend(
                "005930",
                start_date=date(2025, 5, 1),
                end_date=date(2025, 5, 19),
                max_pages=5,
            )


# ---------------------------------------------------------------------------
# ShortSellingResponse Pydantic 파싱 검증
# ---------------------------------------------------------------------------


def test_short_selling_response_parses_full_body() -> None:
    """ShortSellingResponse.model_validate — return_code=0, shrts_trnsn 5건."""
    resp = ShortSellingResponse.model_validate(_SAMSUNG_SHSA_BODY)
    assert resp.return_code == 0
    assert len(resp.shrts_trnsn) == 5
    assert isinstance(resp.shrts_trnsn[0], ShortSellingRow)


def test_short_selling_row_empty_fields_returns_none_values() -> None:
    """모든 필드 빈값 → trading_date=date.min (dt=''), 나머지 None."""
    row = ShortSellingRow()
    n = row.to_normalized(stock_id=1, exchange=ExchangeType.KRX)

    assert n.trading_date == date.min
    assert n.close_price is None
    assert n.change_rate is None
    assert n.short_trade_weight is None
    assert n.short_volume is None
