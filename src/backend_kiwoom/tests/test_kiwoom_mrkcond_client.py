"""KiwoomMarketCondClient.fetch_daily_market (ka10086) — C-2α 어댑터 + 정규화.

설계: endpoint-10-ka10086.md § 6.1.

검증:
1. 정상 호출 — 단일 페이지 응답 → DailyMarketRow list, body { stk_cd, qry_dt, indc_tp }
2. KRX/NXT/SOR exchange suffix
3. cont-yn 페이지네이션 (2 페이지 합치기)
4. return_code != 0 → KiwoomBusinessError + message echo 차단
5. stock_code 6자리 ASCII 검증 → ValueError (호출 차단)
6. indc_mode QUANTITY → "0", AMOUNT → "1"
7. 빈 응답 → 빈 list
8. 22 필드 정규화 — _to_int / _to_decimal / _strip_double_sign_int / _parse_yyyymmdd
9. 이중 부호 응답 → -714 (가설 B)
10. Pydantic extra="ignore"
11. 페이지 응답 stk_cd 메아리 mismatch (chart.py 패턴 일관) → KiwoomResponseValidationError
12. NormalizedDailyFlow 의 stock_id / exchange / indc_mode 인자
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest

from app.adapter.out.kiwoom._client import KiwoomClient
from app.adapter.out.kiwoom._exceptions import (
    KiwoomBusinessError,
    KiwoomResponseValidationError,
)
from app.adapter.out.kiwoom._records import (
    DailyMarketResponse,
    DailyMarketRow,
    NormalizedDailyFlow,
)
from app.adapter.out.kiwoom.mrkcond import KiwoomMarketCondClient
from app.application.constants import DailyMarketDisplayMode, ExchangeType

_SAMSUNG_FLOW_BODY: dict[str, Any] = {
    "stk_cd": "005930",
    "daly_stkpc": [
        {
            "date": "20241125",
            "open_pric": "+78800",
            "high_pric": "+101100",
            "low_pric": "-54500",
            "close_pric": "-55000",
            "pred_rt": "-22800",
            "flu_rt": "-29.31",
            "trde_qty": "20278",
            "amt_mn": "1179",
            "crd_rt": "0.50",
            "crd_remn_rt": "0.30",
            "ind": "--714",
            "orgn": "+693",
            "frgn": "0",
            "prm": "0",
            "for_qty": "--266783",
            "for_rt": "12.34",
            "for_poss": "1234567",
            "for_wght": "50.10",
            "for_netprps": "-200",
            "orgn_netprps": "+300",
            "ind_netprps": "-100",
        }
    ],
    "return_code": 0,
    "return_msg": "정상",
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


# ---------- 1. 정상 단일 페이지 ----------


@pytest.mark.asyncio
async def test_fetch_daily_market_single_page() -> None:
    captured_body: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        assert request.headers["api-id"] == "ka10086"
        assert request.url.path == "/api/dostk/mrkcond"
        return httpx.Response(200, json=_SAMSUNG_FLOW_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomMarketCondClient(kc)
        rows = await adapter.fetch_daily_market("005930", query_date=date(2024, 11, 25))

    assert len(rows) == 1
    assert isinstance(rows[0], DailyMarketRow)
    assert rows[0].date == "20241125"
    assert rows[0].ind == "--714"
    assert captured_body == {"stk_cd": "005930", "qry_dt": "20241125", "indc_tp": "0"}


# ---------- 2. exchange suffix ----------


@pytest.mark.asyncio
async def test_fetch_daily_market_nxt_appends_nx() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={**_SAMSUNG_FLOW_BODY, "stk_cd": "005930_NX"})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomMarketCondClient(kc)
        await adapter.fetch_daily_market(
            "005930", query_date=date(2024, 11, 25), exchange=ExchangeType.NXT
        )

    assert captured["stk_cd"] == "005930_NX"


@pytest.mark.asyncio
async def test_fetch_daily_market_sor_appends_al() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={**_SAMSUNG_FLOW_BODY, "stk_cd": "005930_AL"})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomMarketCondClient(kc)
        await adapter.fetch_daily_market(
            "005930", query_date=date(2024, 11, 25), exchange=ExchangeType.SOR
        )

    assert captured["stk_cd"] == "005930_AL"


# ---------- 3. 페이지네이션 ----------


@pytest.mark.asyncio
async def test_fetch_daily_market_paginates_with_cont_yn() -> None:
    page2_body = {
        "stk_cd": "005930",
        "daly_stkpc": [
            {
                "date": "20241124",
                "open_pric": "+78000",
                "close_pric": "+78500",
                "ind": "+100",
                "for_netprps": "+50",
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
                200, json=_SAMSUNG_FLOW_BODY, headers={"cont-yn": "Y", "next-key": "abc"}
            )
        return httpx.Response(200, json=page2_body, headers={"cont-yn": "N"})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomMarketCondClient(kc)
        rows = await adapter.fetch_daily_market("005930", query_date=date(2024, 11, 25))

    assert len(rows) == 2
    assert call_count == 2


# ---------- 4. KiwoomBusinessError + echo 차단 ----------


@pytest.mark.asyncio
async def test_fetch_daily_market_business_error() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"return_code": 1, "return_msg": "조회 가능 일자가 아닙니다"}
        )

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomMarketCondClient(kc)
        with pytest.raises(KiwoomBusinessError) as exc_info:
            await adapter.fetch_daily_market("005930", query_date=date(1900, 1, 1))

    assert exc_info.value.return_code == 1
    # message echo 차단 — 응답 string 이 exception 의 default str 에 포함되지 않게 (B-α/B-β M-2)
    # message 는 attribute 로 보존하지만 caller 가 응답 본문에 echo 안 함


# ---------- 5. stock_code 검증 ----------


@pytest.mark.asyncio
async def test_fetch_daily_market_rejects_invalid_stock_code() -> None:
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=_SAMSUNG_FLOW_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomMarketCondClient(kc)
        for invalid in ("00593", "ABC123", "005930_NX", "      ", ""):
            with pytest.raises(ValueError):
                await adapter.fetch_daily_market(invalid, query_date=date(2024, 11, 25))

    assert call_count == 0


# ---------- 6. indc_mode AMOUNT ----------


@pytest.mark.asyncio
async def test_fetch_daily_market_indc_mode_amount_sends_1() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=_SAMSUNG_FLOW_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomMarketCondClient(kc)
        await adapter.fetch_daily_market(
            "005930",
            query_date=date(2024, 11, 25),
            indc_mode=DailyMarketDisplayMode.AMOUNT,
        )

    assert captured["indc_tp"] == "1"


# ---------- 7. 빈 응답 ----------


@pytest.mark.asyncio
async def test_fetch_daily_market_empty_list() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"stk_cd": "005930", "daly_stkpc": [], "return_code": 0, "return_msg": "정상"},
        )

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomMarketCondClient(kc)
        rows = await adapter.fetch_daily_market("005930", query_date=date(2024, 11, 25))

    assert rows == []


# ---------- 8. 정규화 ----------


def test_to_normalized_full_field_mapping() -> None:
    """22 필드 응답 → NormalizedDailyFlow (OHLCV 8 필드 무시)."""
    raw = DailyMarketRow.model_validate(_SAMSUNG_FLOW_BODY["daly_stkpc"][0])
    normalized = raw.to_normalized(
        stock_id=42,
        exchange=ExchangeType.KRX,
        indc_mode=DailyMarketDisplayMode.QUANTITY,
    )

    assert isinstance(normalized, NormalizedDailyFlow)
    assert normalized.stock_id == 42
    assert normalized.exchange is ExchangeType.KRX
    assert normalized.indc_mode is DailyMarketDisplayMode.QUANTITY
    assert normalized.trading_date == date(2024, 11, 25)

    # 신용
    assert normalized.credit_rate == Decimal("0.50")
    assert normalized.credit_balance_rate == Decimal("0.30")

    # 투자자별 — 가설 B 적용
    assert normalized.individual_net == -714  # "--714" → -714
    assert normalized.institutional_net == 693
    assert normalized.foreign_brokerage_net == 0
    assert normalized.program_net == 0

    # 외인
    assert normalized.foreign_volume == -266783  # "--266783" → -266783
    assert normalized.foreign_rate == Decimal("12.34")
    assert normalized.foreign_holdings == 1234567
    assert normalized.foreign_weight == Decimal("50.10")

    # 순매수 (R15: 항상 수량)
    assert normalized.foreign_net_purchase == -200
    assert normalized.institutional_net_purchase == 300
    assert normalized.individual_net_purchase == -100


def test_to_normalized_empty_date_yields_date_min() -> None:
    """빈 date 응답 → date.min 표식 (Repository skip 안전망)."""
    raw = DailyMarketRow.model_validate({"date": ""})
    normalized = raw.to_normalized(
        stock_id=1,
        exchange=ExchangeType.KRX,
        indc_mode=DailyMarketDisplayMode.QUANTITY,
    )
    assert normalized.trading_date == date.min


# ---------- 9. Pydantic extra="ignore" ----------


def test_pydantic_response_ignores_extra_fields() -> None:
    body = {**_SAMSUNG_FLOW_BODY, "unexpected_new_field": "ignored"}
    parsed = DailyMarketResponse.model_validate(body)
    assert len(parsed.daly_stkpc) == 1


# ---------- 10. 페이지 응답 stk_cd cross-stock pollution 차단 (C-1α 2R H-1 패턴) ----------


@pytest.mark.asyncio
async def test_fetch_daily_market_rejects_response_stk_cd_mismatch() -> None:
    """페이지 응답 root.stk_cd 가 다른 종목으로 박혀와도 차단."""

    def handler(_req: httpx.Request) -> httpx.Response:
        body = {**_SAMSUNG_FLOW_BODY, "stk_cd": "999999"}
        return httpx.Response(200, json=body)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomMarketCondClient(kc)
        with pytest.raises(KiwoomResponseValidationError):
            await adapter.fetch_daily_market("005930", query_date=date(2024, 11, 25))


@pytest.mark.asyncio
async def test_fetch_daily_market_accepts_suffix_stripped_response() -> None:
    """응답 stk_cd 가 suffix stripped (`005930` for NXT 요청) 도 통과 — base 비교 정책."""

    def handler(_req: httpx.Request) -> httpx.Response:
        body = {**_SAMSUNG_FLOW_BODY, "stk_cd": "005930"}
        return httpx.Response(200, json=body)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomMarketCondClient(kc)
        # NXT 요청 + 응답이 suffix 없는 005930 → base code 일치이므로 통과
        rows = await adapter.fetch_daily_market(
            "005930", query_date=date(2024, 11, 25), exchange=ExchangeType.NXT
        )
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_fetch_daily_market_accepts_empty_stk_cd_response() -> None:
    """응답 stk_cd 빈 string → 통과 (계획서 운영 미검증, C-1α 정책 일관)."""

    def handler(_req: httpx.Request) -> httpx.Response:
        body = {**_SAMSUNG_FLOW_BODY, "stk_cd": ""}
        return httpx.Response(200, json=body)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomMarketCondClient(kc)
        rows = await adapter.fetch_daily_market("005930", query_date=date(2024, 11, 25))
    assert len(rows) == 1


# ---------- 11. Pydantic ValidationError → KiwoomResponseValidationError ----------


@pytest.mark.asyncio
async def test_fetch_daily_market_pydantic_validation_error() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        # daly_stkpc 가 list 가 아닌 string → Pydantic ValidationError
        return httpx.Response(200, json={"stk_cd": "005930", "daly_stkpc": "broken", "return_code": 0})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomMarketCondClient(kc)
        with pytest.raises(KiwoomResponseValidationError):
            await adapter.fetch_daily_market("005930", query_date=date(2024, 11, 25))
