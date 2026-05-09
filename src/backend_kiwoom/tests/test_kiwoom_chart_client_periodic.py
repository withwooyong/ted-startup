"""KiwoomChartClient.fetch_weekly + fetch_monthly (ka10082/83) — C-3α.

설계: phase-c-3-weekly-monthly-ohlcv.md § 3.1 + endpoint-07-ka10082.md § 6.1 + endpoint-08-ka10083.md § 6.1.

ka10081 (fetch_daily) 의 14 시나리오 중 차이점 + 핵심 시나리오만 복제. 공유 인프라
(KiwoomClient / build_stk_cd / cont-yn / KiwoomCredentialRejectedError) 는 ka10081
테스트 (test_kiwoom_chart_client.py) 가 이미 검증 — 회귀 0.

차이점:
- 응답 list 키: weekly = `stk_stk_pole_chart_qry` / monthly = `stk_mth_pole_chart_qry`
- api_id: weekly = "ka10082" / monthly = "ka10083"
- max_pages: 주봉/월봉은 백필 시 페이지 수 적음 (3년 = 156 주 / 36 월)

공유:
- WeeklyChartRow / MonthlyChartRow → DailyChartRow 상속 (필드 동일)
- to_normalized → NormalizedDailyOhlcv 반환 (기존 dataclass 재사용)
- stk_cd 메아리 검증 / KiwoomBusinessError 매핑 / Pydantic ValidationError → KiwoomResponseValidationError
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from typing import Any

import httpx
import pytest

from app.adapter.out.kiwoom._client import KiwoomClient
from app.adapter.out.kiwoom._exceptions import (
    KiwoomBusinessError,
    KiwoomResponseValidationError,
)
from app.adapter.out.kiwoom.chart import (
    DailyChartRow,
    KiwoomChartClient,
    MonthlyChartResponse,
    MonthlyChartRow,
    NormalizedDailyOhlcv,
    WeeklyChartResponse,
    WeeklyChartRow,
)
from app.application.constants import ExchangeType

_SAMSUNG_WEEKLY_BODY: dict[str, Any] = {
    "stk_cd": "005930",
    "stk_stk_pole_chart_qry": [
        {
            "cur_prc": "69500",
            "trde_qty": "56700518",
            "trde_prica": "3922030535087",
            "dt": "20250901",
            "open_pric": "68400",
            "high_pric": "70400",
            "low_pric": "67500",
            "pred_pre": "-200",
            "pred_pre_sig": "5",
            "trde_tern_rt": "+0.95",
        },
        {
            "cur_prc": "68500",
            "trde_qty": "45000000",
            "trde_prica": "3000000000000",
            "dt": "20250825",
            "open_pric": "68000",
            "high_pric": "69000",
            "low_pric": "67000",
            "pred_pre": "+500",
            "pred_pre_sig": "2",
            "trde_tern_rt": "+0.75",
        },
    ],
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다",
}


_SAMSUNG_MONTHLY_BODY: dict[str, Any] = {
    "stk_cd": "005930",
    "stk_mth_pole_chart_qry": [
        {
            "cur_prc": "78900",
            "trde_qty": "215040968",
            "trde_prica": "15774571011618",
            "dt": "20250901",
            "open_pric": "68400",
            "high_pric": "79500",
            "low_pric": "67500",
            "pred_pre": "+9200",
            "pred_pre_sig": "2",
            "trde_tern_rt": "+13.45",
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


# ---------- Pydantic 상속 / response 모델 ----------


def test_weekly_chart_row_inherits_daily_chart_row() -> None:
    """WeeklyChartRow 는 DailyChartRow 상속 — 필드 동일."""
    assert issubclass(WeeklyChartRow, DailyChartRow)


def test_monthly_chart_row_inherits_daily_chart_row() -> None:
    """MonthlyChartRow 는 DailyChartRow 상속."""
    assert issubclass(MonthlyChartRow, DailyChartRow)


def test_weekly_response_uses_stk_stk_pole_chart_qry_key() -> None:
    """ka10082 응답 list 키 = `stk_stk_pole_chart_qry`."""
    parsed = WeeklyChartResponse.model_validate(_SAMSUNG_WEEKLY_BODY)
    assert len(parsed.stk_stk_pole_chart_qry) == 2
    assert parsed.stk_stk_pole_chart_qry[0].dt == "20250901"
    assert parsed.return_code == 0


def test_monthly_response_uses_stk_mth_pole_chart_qry_key() -> None:
    """ka10083 응답 list 키 = `stk_mth_pole_chart_qry`."""
    parsed = MonthlyChartResponse.model_validate(_SAMSUNG_MONTHLY_BODY)
    assert len(parsed.stk_mth_pole_chart_qry) == 1
    assert parsed.stk_mth_pole_chart_qry[0].cur_prc == "78900"


def test_weekly_response_with_wrong_key_returns_empty() -> None:
    """다른 key (`stk_dt_pole_chart_qry`) 응답이면 빈 list — silent merge 차단."""
    body_with_daily_key = {
        "stk_cd": "005930",
        "stk_dt_pole_chart_qry": [
            {"dt": "20250901", "cur_prc": "70000"},
        ],
        "return_code": 0,
        "return_msg": "ok",
    }
    parsed = WeeklyChartResponse.model_validate(body_with_daily_key)
    assert parsed.stk_stk_pole_chart_qry == []


def test_monthly_response_with_wrong_key_returns_empty() -> None:
    """ka10083 도 동일 — 다른 키면 빈 list."""
    body_with_weekly_key = {
        "stk_cd": "005930",
        "stk_stk_pole_chart_qry": [{"dt": "20250901", "cur_prc": "70000"}],
        "return_code": 0,
        "return_msg": "ok",
    }
    parsed = MonthlyChartResponse.model_validate(body_with_weekly_key)
    assert parsed.stk_mth_pole_chart_qry == []


def test_weekly_chart_row_to_normalized_returns_normalized_daily_ohlcv() -> None:
    """WeeklyChartRow.to_normalized → NormalizedDailyOhlcv (재사용 — period 무관)."""
    row = WeeklyChartRow(
        cur_prc="69500",
        trde_qty="56700518",
        trde_prica="3922030535087",
        dt="20250901",
        open_pric="68400",
        high_pric="70400",
        low_pric="67500",
        pred_pre="-200",
        pred_pre_sig="5",
        trde_tern_rt="+0.95",
    )
    norm = row.to_normalized(stock_id=42, exchange=ExchangeType.KRX, adjusted=True)
    assert isinstance(norm, NormalizedDailyOhlcv)
    assert norm.stock_id == 42
    assert norm.trading_date == date(2025, 9, 1)
    assert norm.close_price == 69500
    assert norm.exchange == ExchangeType.KRX
    assert norm.adjusted is True


def test_monthly_chart_row_to_normalized_returns_normalized_daily_ohlcv() -> None:
    """MonthlyChartRow.to_normalized → NormalizedDailyOhlcv (재사용)."""
    row = MonthlyChartRow(
        cur_prc="78900",
        trde_qty="215040968",
        trde_prica="15774571011618",
        dt="20250901",
        open_pric="68400",
        high_pric="79500",
        low_pric="67500",
        pred_pre="+9200",
        pred_pre_sig="2",
        trde_tern_rt="+13.45",
    )
    norm = row.to_normalized(stock_id=99, exchange=ExchangeType.NXT, adjusted=False)
    assert isinstance(norm, NormalizedDailyOhlcv)
    assert norm.stock_id == 99
    assert norm.trading_date == date(2025, 9, 1)
    assert norm.high_price == 79500
    assert norm.exchange == ExchangeType.NXT
    assert norm.adjusted is False


# ---------- fetch_weekly ----------


@pytest.mark.asyncio
async def test_fetch_weekly_returns_rows_for_single_page() -> None:
    captured_body: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        assert request.headers["api-id"] == "ka10082"
        assert request.url.path == "/api/dostk/chart"
        return httpx.Response(200, json=_SAMSUNG_WEEKLY_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        rows = await adapter.fetch_weekly("005930", base_date=date(2025, 9, 8))

    assert len(rows) == 2
    assert isinstance(rows[0], WeeklyChartRow)
    assert isinstance(rows[0], DailyChartRow)
    assert rows[0].dt == "20250901"
    assert captured_body == {"stk_cd": "005930", "base_dt": "20250908", "upd_stkpc_tp": "1"}


@pytest.mark.asyncio
async def test_fetch_weekly_with_nxt_uses_nx_suffix() -> None:
    captured_body: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        # NXT 응답은 stk_cd 도 _NX 동봉
        body = {**_SAMSUNG_WEEKLY_BODY, "stk_cd": "005930_NX"}
        return httpx.Response(200, json=body)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        rows = await adapter.fetch_weekly(
            "005930",
            base_date=date(2025, 9, 8),
            exchange=ExchangeType.NXT,
        )

    assert len(rows) == 2
    assert captured_body["stk_cd"] == "005930_NX"


@pytest.mark.asyncio
async def test_fetch_weekly_adjusted_false_sets_upd_stkpc_tp_zero() -> None:
    captured_body: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        return httpx.Response(200, json=_SAMSUNG_WEEKLY_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        await adapter.fetch_weekly("005930", base_date=date(2025, 9, 8), adjusted=False)

    assert captured_body["upd_stkpc_tp"] == "0"


@pytest.mark.asyncio
async def test_fetch_weekly_business_error_raises() -> None:
    body = {**_SAMSUNG_WEEKLY_BODY, "return_code": 999, "return_msg": "권한 없음"}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        with pytest.raises(KiwoomBusinessError) as exc_info:
            await adapter.fetch_weekly("005930", base_date=date(2025, 9, 8))

    assert exc_info.value.api_id == "ka10082"


@pytest.mark.asyncio
async def test_fetch_weekly_invalid_stock_code_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_SAMSUNG_WEEKLY_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        with pytest.raises(ValueError):
            await adapter.fetch_weekly("ABC", base_date=date(2025, 9, 8))
        with pytest.raises(ValueError):
            await adapter.fetch_weekly("005930_NX", base_date=date(2025, 9, 8))


@pytest.mark.asyncio
async def test_fetch_weekly_stk_cd_echo_mismatch_raises() -> None:
    """C-1α 2R H-1 패턴 — 응답 stk_cd 가 다른 종목이면 cross-stock pollution 차단."""
    body_wrong_stock = {**_SAMSUNG_WEEKLY_BODY, "stk_cd": "000660"}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body_wrong_stock)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        with pytest.raises(KiwoomResponseValidationError):
            await adapter.fetch_weekly("005930", base_date=date(2025, 9, 8))


@pytest.mark.asyncio
async def test_fetch_weekly_empty_list_returns_empty() -> None:
    body_empty = {**_SAMSUNG_WEEKLY_BODY, "stk_stk_pole_chart_qry": []}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body_empty)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        rows = await adapter.fetch_weekly("005930", base_date=date(2025, 9, 8))

    assert rows == []


# ---------- fetch_monthly ----------


@pytest.mark.asyncio
async def test_fetch_monthly_returns_rows_for_single_page() -> None:
    captured_body: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        assert request.headers["api-id"] == "ka10083"
        assert request.url.path == "/api/dostk/chart"
        return httpx.Response(200, json=_SAMSUNG_MONTHLY_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        rows = await adapter.fetch_monthly("005930", base_date=date(2025, 9, 8))

    assert len(rows) == 1
    assert isinstance(rows[0], MonthlyChartRow)
    assert rows[0].dt == "20250901"
    assert captured_body == {"stk_cd": "005930", "base_dt": "20250908", "upd_stkpc_tp": "1"}


@pytest.mark.asyncio
async def test_fetch_monthly_with_nxt_uses_nx_suffix() -> None:
    captured_body: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        body = {**_SAMSUNG_MONTHLY_BODY, "stk_cd": "005930_NX"}
        return httpx.Response(200, json=body)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        await adapter.fetch_monthly(
            "005930",
            base_date=date(2025, 9, 8),
            exchange=ExchangeType.NXT,
        )

    assert captured_body["stk_cd"] == "005930_NX"


@pytest.mark.asyncio
async def test_fetch_monthly_business_error_raises() -> None:
    body = {**_SAMSUNG_MONTHLY_BODY, "return_code": 999}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        with pytest.raises(KiwoomBusinessError) as exc_info:
            await adapter.fetch_monthly("005930", base_date=date(2025, 9, 8))

    assert exc_info.value.api_id == "ka10083"


@pytest.mark.asyncio
async def test_fetch_monthly_stk_cd_echo_mismatch_raises() -> None:
    body_wrong_stock = {**_SAMSUNG_MONTHLY_BODY, "stk_cd": "000660"}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body_wrong_stock)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        with pytest.raises(KiwoomResponseValidationError):
            await adapter.fetch_monthly("005930", base_date=date(2025, 9, 8))


@pytest.mark.asyncio
async def test_fetch_monthly_empty_list_returns_empty() -> None:
    body_empty = {**_SAMSUNG_MONTHLY_BODY, "stk_mth_pole_chart_qry": []}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body_empty)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        rows = await adapter.fetch_monthly("005930", base_date=date(2025, 9, 8))

    assert rows == []


# ---------- 페이지네이션 (cont-yn) ----------


@pytest.mark.asyncio
async def test_fetch_weekly_paginates_with_cont_yn() -> None:
    """주봉 페이지네이션 — page1 cont-yn=Y → page2 합치기."""
    page2_body: dict[str, Any] = {
        "stk_cd": "005930",
        "stk_stk_pole_chart_qry": [
            {
                "cur_prc": "67000",
                "trde_qty": "30000000",
                "trde_prica": "2010000000000",
                "dt": "20250818",
                "open_pric": "67500",
                "high_pric": "68000",
                "low_pric": "66500",
                "pred_pre": "-1500",
                "pred_pre_sig": "5",
                "trde_tern_rt": "-2.18",
            },
        ],
        "return_code": 0,
        "return_msg": "ok",
    }
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return httpx.Response(
                200,
                json=_SAMSUNG_WEEKLY_BODY,
                headers={"cont-yn": "Y", "next-key": "PAGE2"},
            )
        return httpx.Response(200, json=page2_body)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        rows = await adapter.fetch_weekly("005930", base_date=date(2025, 9, 8))

    assert len(rows) == 3  # page1: 2 + page2: 1
    assert call_count["n"] == 2


# ---------- 클래스 상수 ----------


def test_weekly_and_monthly_api_id_constants() -> None:
    """클래스 상수 — api_id 명시."""
    assert KiwoomChartClient.WEEKLY_API_ID == "ka10082"
    assert KiwoomChartClient.MONTHLY_API_ID == "ka10083"


def test_weekly_and_monthly_max_pages_default() -> None:
    """주/월봉은 백필 시 페이지 수 적음 — daily 보다 cap 작거나 같음."""
    assert KiwoomChartClient.WEEKLY_MAX_PAGES >= 1
    assert KiwoomChartClient.MONTHLY_MAX_PAGES >= 1
    # 3년 = 156 주 / 36 월. 1 페이지 ~600 거래일 가정 시 1~2 페이지면 충분
    assert KiwoomChartClient.WEEKLY_MAX_PAGES <= KiwoomChartClient.DAILY_MAX_PAGES
    assert KiwoomChartClient.MONTHLY_MAX_PAGES <= KiwoomChartClient.DAILY_MAX_PAGES
