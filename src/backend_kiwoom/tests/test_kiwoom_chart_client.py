"""KiwoomChartClient.fetch_daily (ka10081) — C-1α 어댑터 + 정규화.

설계: endpoint-06-ka10081.md § 6.1.

검증:
1. 정상 호출 — 단일 페이지 응답 → DailyChartRow list
2. KRX 호출 — stk_cd 그대로
3. NXT 호출 — stk_cd 에 `_NX` suffix
4. SOR 호출 — `_AL` suffix
5. cont-yn 페이지네이션 — 2 페이지 합치기
6. return_code != 0 → KiwoomBusinessError
7. stock_code 6자리 검증 → ValueError
8. base_dt 형식 (YYYYMMDD)
9. upd_stkpc_tp adjusted=True/False → "1"/"0"
10. 빈 응답 list → 빈 list 반환
11. 응답 row 정규화 — _to_int / _to_decimal / _parse_yyyymmdd 재사용 (B-γ-1 가드 자동 적용)
12. NormalizedDailyOhlcv 의 stock_id / exchange / adjusted 인자
13. Pydantic extra 필드 무시
14. KiwoomCredentialRejectedError 401 전파
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
    KiwoomCredentialRejectedError,
    KiwoomResponseValidationError,
)
from app.adapter.out.kiwoom.chart import (
    DailyChartResponse,
    DailyChartRow,
    KiwoomChartClient,
    NormalizedDailyOhlcv,
)
from app.application.constants import ExchangeType

_SAMSUNG_DAILY_BODY: dict[str, Any] = {
    "stk_cd": "005930",
    "stk_dt_pole_chart_qry": [
        {
            "cur_prc": "70100",
            "trde_qty": "9263135",
            "trde_prica": "648525",
            "dt": "20250908",
            "open_pric": "69800",
            "high_pric": "70500",
            "low_pric": "69600",
            "pred_pre": "+600",
            "pred_pre_sig": "2",
            "trde_tern_rt": "+0.16",
        },
        {
            "cur_prc": "69500",
            "trde_qty": "8500000",
            "trde_prica": "590000",
            "dt": "20250905",
            "open_pric": "69200",
            "high_pric": "69900",
            "low_pric": "69100",
            "pred_pre": "-200",
            "pred_pre_sig": "5",
            "trde_tern_rt": "-0.14",
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


# ---------- 1. 정상 단일 페이지 ----------


@pytest.mark.asyncio
async def test_fetch_daily_returns_rows_for_single_page() -> None:
    captured_body: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        assert request.headers["api-id"] == "ka10081"
        assert request.url.path == "/api/dostk/chart"
        return httpx.Response(200, json=_SAMSUNG_DAILY_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        rows = await adapter.fetch_daily("005930", base_date=date(2025, 9, 8))

    assert len(rows) == 2
    assert isinstance(rows[0], DailyChartRow)
    assert rows[0].dt == "20250908"
    assert rows[0].cur_prc == "70100"
    assert captured_body == {"stk_cd": "005930", "base_dt": "20250908", "upd_stkpc_tp": "1"}


# ---------- 2-4. exchange 별 stk_cd suffix ----------


@pytest.mark.asyncio
async def test_fetch_daily_krx_uses_base_stock_code() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=_SAMSUNG_DAILY_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        await adapter.fetch_daily("005930", base_date=date(2025, 9, 8), exchange=ExchangeType.KRX)

    assert captured["stk_cd"] == "005930"


@pytest.mark.asyncio
async def test_fetch_daily_nxt_appends_nx_suffix() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=_SAMSUNG_DAILY_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        await adapter.fetch_daily("005930", base_date=date(2025, 9, 8), exchange=ExchangeType.NXT)

    assert captured["stk_cd"] == "005930_NX"


@pytest.mark.asyncio
async def test_fetch_daily_sor_appends_al_suffix() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=_SAMSUNG_DAILY_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        await adapter.fetch_daily("005930", base_date=date(2025, 9, 8), exchange=ExchangeType.SOR)

    assert captured["stk_cd"] == "005930_AL"


# ---------- 5. cont-yn 페이지네이션 ----------


@pytest.mark.asyncio
async def test_fetch_daily_paginates_with_cont_yn() -> None:
    """cont-yn=Y → 다음 페이지 자동 호출. 모든 row 합쳐짐."""
    page1_body = {**_SAMSUNG_DAILY_BODY}
    page2_rows = [
        {
            "cur_prc": "68000",
            "trde_qty": "7500000",
            "trde_prica": "510000",
            "dt": "20250901",
            "open_pric": "68100",
            "high_pric": "68500",
            "low_pric": "67800",
            "pred_pre": "-100",
            "pred_pre_sig": "5",
            "trde_tern_rt": "-0.10",
        }
    ]
    page2_body = {
        "stk_cd": "005930",
        "stk_dt_pole_chart_qry": page2_rows,
        "return_code": 0,
        "return_msg": "정상",
    }
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, json=page1_body, headers={"cont-yn": "Y", "next-key": "abc"})
        return httpx.Response(200, json=page2_body, headers={"cont-yn": "N"})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        rows = await adapter.fetch_daily("005930", base_date=date(2025, 9, 8))

    assert len(rows) == 3, f"page1 (2) + page2 (1) = 3 / call_count={call_count}"
    assert call_count == 2


# ---------- 6. KiwoomBusinessError ----------


@pytest.mark.asyncio
async def test_fetch_daily_propagates_business_error() -> None:
    """return_code != 0 → KiwoomBusinessError (트랜스포트가 raise)."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"return_code": 1, "return_msg": "조회 가능 일자가 아님"})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        with pytest.raises(KiwoomBusinessError) as exc_info:
            await adapter.fetch_daily("005930", base_date=date(1900, 1, 1))

    assert exc_info.value.return_code == 1


# ---------- 7. stock_code 사전 검증 ----------


@pytest.mark.asyncio
async def test_fetch_daily_rejects_invalid_stock_code() -> None:
    """6자리 영숫자 대문자 외 거부 (CHART 패턴, ADR § 32 chunk 2).

    영숫자 대문자 (`03473K`) 통과 — 우선주/ETF 호출 가능. lowercase / 특수문자 /
    suffix 박힌 입력은 그대로 거부.
    """
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=_SAMSUNG_DAILY_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        for invalid in ("00593", "005930_NX", "      ", "", "0000d0", "00ABC!"):
            with pytest.raises(ValueError):
                await adapter.fetch_daily(invalid, base_date=date(2025, 9, 8))

    assert call_count == 0


# ---------- 8. upd_stkpc_tp adjusted ----------


@pytest.mark.asyncio
async def test_fetch_daily_adjusted_true_sends_1() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=_SAMSUNG_DAILY_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        await adapter.fetch_daily("005930", base_date=date(2025, 9, 8), adjusted=True)

    assert captured["upd_stkpc_tp"] == "1"


@pytest.mark.asyncio
async def test_fetch_daily_adjusted_false_sends_0() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=_SAMSUNG_DAILY_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        await adapter.fetch_daily("005930", base_date=date(2025, 9, 8), adjusted=False)

    assert captured["upd_stkpc_tp"] == "0"


# ---------- 9. 빈 응답 ----------


@pytest.mark.asyncio
async def test_fetch_daily_returns_empty_list_for_empty_response() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"stk_cd": "005930", "stk_dt_pole_chart_qry": [], "return_code": 0, "return_msg": "정상"},
        )

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        rows = await adapter.fetch_daily("005930", base_date=date(2025, 9, 8))

    assert rows == []


# ---------- 10. 정규화 — DailyChartRow.to_normalized ----------


def test_daily_chart_row_to_normalized_with_signed_values() -> None:
    """`+600` / `-200` 부호 → int. `+0.16` → Decimal."""
    row = DailyChartRow(
        cur_prc="70100",
        trde_qty="9263135",
        trde_prica="648525",
        dt="20250908",
        open_pric="69800",
        high_pric="70500",
        low_pric="69600",
        pred_pre="+600",
        pred_pre_sig="2",
        trde_tern_rt="+0.16",
    )

    n: NormalizedDailyOhlcv = row.to_normalized(
        stock_id=42,
        exchange=ExchangeType.KRX,
        adjusted=True,
    )

    assert n.stock_id == 42
    assert n.trading_date == date(2025, 9, 8)
    assert n.exchange == ExchangeType.KRX
    assert n.adjusted is True
    assert n.open_price == 69800
    assert n.high_price == 70500
    assert n.low_price == 69600
    assert n.close_price == 70100
    assert n.trade_volume == 9263135
    assert n.trade_amount == 648525
    assert n.prev_compare_amount == 600
    assert n.prev_compare_sign == "2"
    assert n.turnover_rate == Decimal("0.16")


def test_daily_chart_row_to_normalized_with_negative_values() -> None:
    """음수 부호 보존."""
    row = DailyChartRow(
        cur_prc="69500",
        dt="20250905",
        open_pric="69200",
        high_pric="69900",
        low_pric="69100",
        pred_pre="-200",
        pred_pre_sig="5",
        trde_tern_rt="-0.14",
    )

    n = row.to_normalized(stock_id=42, exchange=ExchangeType.KRX, adjusted=True)
    assert n.prev_compare_amount == -200
    assert n.turnover_rate == Decimal("-0.14")


def test_daily_chart_row_to_normalized_handles_empty_values() -> None:
    """모든 필드 빈값 → trading_date=date.min (caller skip), 나머지 None."""
    row = DailyChartRow()
    n = row.to_normalized(stock_id=42, exchange=ExchangeType.KRX, adjusted=True)

    assert n.trading_date == date.min
    assert n.open_price is None
    assert n.close_price is None
    assert n.trade_volume is None
    assert n.prev_compare_sign is None
    assert n.turnover_rate is None


def test_daily_chart_row_to_normalized_rejects_bigint_overflow() -> None:
    """B-γ-1 _to_int BIGINT 가드 자동 적용 — overflow 시 None."""
    row = DailyChartRow(
        cur_prc="9" * 30,  # BIGINT max 초과
        dt="20250908",
    )
    n = row.to_normalized(stock_id=42, exchange=ExchangeType.KRX, adjusted=True)
    assert n.close_price is None


# ---------- 11. Pydantic extra 필드 무시 ----------


@pytest.mark.asyncio
async def test_fetch_daily_extra_fields_ignored() -> None:
    """키움이 신규 필드 추가해도 어댑터 안 깨짐."""

    def handler(_req: httpx.Request) -> httpx.Response:
        body = {**_SAMSUNG_DAILY_BODY, "newField2026": "value"}
        body["stk_dt_pole_chart_qry"][0]["extra_row_field"] = "X"  # type: ignore[index]
        return httpx.Response(200, json=body)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        rows = await adapter.fetch_daily("005930", base_date=date(2025, 9, 8))

    assert len(rows) == 2


# ---------- 12. 401 자격증명 ----------


@pytest.mark.asyncio
async def test_fetch_daily_propagates_credential_rejected() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        with pytest.raises(KiwoomCredentialRejectedError):
            await adapter.fetch_daily("005930", base_date=date(2025, 9, 8))


# ---------- 13. DailyChartResponse Pydantic ----------


def test_daily_chart_response_parses_full_body() -> None:
    resp = DailyChartResponse.model_validate(_SAMSUNG_DAILY_BODY)
    assert resp.stk_cd == "005930"
    assert resp.return_code == 0
    assert len(resp.stk_dt_pole_chart_qry) == 2


# =============================================================================
# 2R 회귀 — H-1 페이지네이션 cross-stock pollution 차단
# =============================================================================


@pytest.mark.asyncio
async def test_fetch_daily_rejects_page_with_mismatched_stk_cd() -> None:
    """C-1α 2R H-1 — page N 의 root.stk_cd 가 요청과 다르면 KiwoomResponseValidationError.

    공격 시나리오: 키움 백엔드 버그 / proxy 캐시 / MITM 으로 page1=정상 종목, page2=다른
    종목 silent merge → cross-stock pollution. 어댑터 단계 차단.
    """
    page1_body = {**_SAMSUNG_DAILY_BODY}  # stk_cd="005930"
    page2_body = {
        "stk_cd": "000660",  # 다른 종목 (SK하이닉스) silent 메아리
        "stk_dt_pole_chart_qry": [
            {"cur_prc": "120000", "dt": "20250901", "open_pric": "119000",
             "high_pric": "121000", "low_pric": "118500", "trde_qty": "5000000"}
        ],
        "return_code": 0,
        "return_msg": "정상",
    }
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, json=page1_body, headers={"cont-yn": "Y", "next-key": "abc"})
        return httpx.Response(200, json=page2_body, headers={"cont-yn": "N"})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        with pytest.raises(KiwoomResponseValidationError) as exc_info:
            await adapter.fetch_daily("005930", base_date=date(2025, 9, 8))

    err = exc_info.value
    # 메시지에 attacker-influenced 응답값 echo 안 되는지 (B-γ-2 M-1 패턴)
    msg = str(err)
    assert "000660" not in msg, f"응답 stk_cd echo 차단 위반: {msg}"
    assert "stk_cd 메아리 mismatch" in msg
    # __context__ leak 차단 (flag-then-raise 패턴)
    assert err.__context__ is None
    assert err.__cause__ is None


@pytest.mark.asyncio
async def test_fetch_daily_allows_empty_response_stk_cd() -> None:
    """C-1α 2R H-1 — root.stk_cd 가 빈 string 이면 통과 (응답 미동봉 허용).

    키움이 root 에 stk_cd 를 항상 동봉하지는 않을 가능성. 운영 검증 후 strict 으로 전환 검토.
    """
    body = {**_SAMSUNG_DAILY_BODY, "stk_cd": ""}

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        rows = await adapter.fetch_daily("005930", base_date=date(2025, 9, 8))

    assert len(rows) == 2  # 정상 통과


@pytest.mark.asyncio
async def test_fetch_daily_nxt_request_accepts_stripped_response_stk_cd() -> None:
    """C-1α 2R H-1 — base code 비교 정책 (계획서 § 4.3 운영 미검증).

    NXT 요청 (`005930_NX`) → 응답이 `005930` (suffix stripped) 또는 `005930_NX` (suffix
    동봉) 양쪽 수용. base code `005930` 가 일치하면 통과.
    """
    body = {**_SAMSUNG_DAILY_BODY}  # stk_cd="005930" (suffix stripped)

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        rows = await adapter.fetch_daily(
            "005930", base_date=date(2025, 9, 8), exchange=ExchangeType.NXT
        )

    assert len(rows) == 2, "NXT 요청에 응답 stk_cd=005930 (stripped) 정상 수용"


@pytest.mark.asyncio
async def test_fetch_daily_nxt_request_accepts_full_suffix_response() -> None:
    """NXT 요청 (`005930_NX`) → 응답 stk_cd 도 `005930_NX` (suffix 동봉) 양쪽 수용."""
    body = {**_SAMSUNG_DAILY_BODY, "stk_cd": "005930_NX"}

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        rows = await adapter.fetch_daily(
            "005930", base_date=date(2025, 9, 8), exchange=ExchangeType.NXT
        )

    assert len(rows) == 2


# ---------- since_date — 운영 차단 fix (max_pages 초과 방어) ----------


@pytest.mark.asyncio
async def test_fetch_daily_since_date_breaks_pagination_when_oldest_row_passes_threshold() -> None:
    """page 의 가장 오래된 row date <= since_date → 다음 page 요청 안 함.

    운영 차단 fix — ka10081 은 base_dt 만 받고 종료 범위 없음. 오래된 종목 (1980년대
    상장) 은 max_pages 도달로 fail. since_date guard 가 백필 하한일 도달 시 조기 break.
    """
    page1_body = {**_SAMSUNG_DAILY_BODY}  # 20250908 / 20250905 (since_date=20250906 보다 과거 1건)
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=page1_body, headers={"cont-yn": "Y", "next-key": "abc"})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        rows = await adapter.fetch_daily(
            "005930", base_date=date(2025, 9, 8), since_date=date(2025, 9, 6)
        )

    assert call_count == 1, "page1 의 oldest row (20250905) <= since_date (20250906) → break"
    # 20250905 row 는 since_date 미만이라 filter out, 20250908 만 남음
    assert len(rows) == 1
    assert rows[0].dt == "20250908"


@pytest.mark.asyncio
async def test_fetch_daily_empty_response_breaks_pagination() -> None:
    """빈 응답 + cont-yn=Y → 다음 페이지 요청 안 함 (sentinel 무한 루프 방어).

    mrkcond ka10086 NXT 010950 reproduce 와 동일 패턴. ka10081 도 일관성 + 잠재 위험 방어.
    """
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(
                200, json=_SAMSUNG_DAILY_BODY, headers={"cont-yn": "Y", "next-key": "abc"}
            )
        return httpx.Response(
            200,
            json={"stk_cd": "005930", "stk_dt_pole_chart_qry": [], "return_code": 0, "return_msg": "정상"},
            headers={"cont-yn": "Y", "next-key": "sentinel-loop"},
        )

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        rows = await adapter.fetch_daily("005930", base_date=date(2025, 9, 8))

    assert call_count == 2, "page2 빈 응답 → cont-yn=Y 무시하고 break"
    assert len(rows) == 2  # page 1 의 row 만


@pytest.mark.asyncio
async def test_fetch_daily_since_date_none_keeps_existing_pagination() -> None:
    """since_date=None (디폴트) → 기존 cont-yn 페이지네이션 동작 유지 (운영 cron 호환)."""
    page2_body = {
        "stk_cd": "005930",
        "stk_dt_pole_chart_qry": [
            {
                "cur_prc": "68000",
                "trde_qty": "7500000",
                "trde_prica": "510000",
                "dt": "20250901",
                "open_pric": "68100",
                "high_pric": "68500",
                "low_pric": "67800",
                "pred_pre": "-100",
                "pred_pre_sig": "5",
                "trde_tern_rt": "-0.10",
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
                200, json=_SAMSUNG_DAILY_BODY, headers={"cont-yn": "Y", "next-key": "abc"}
            )
        return httpx.Response(200, json=page2_body, headers={"cont-yn": "N"})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomChartClient(kc)
        rows = await adapter.fetch_daily("005930", base_date=date(2025, 9, 8))

    assert call_count == 2, "since_date 없으면 cont-yn=N 까지 모두 fetch"
    assert len(rows) == 3
