"""KiwoomRkInfoClient — 5 ranking endpoint fetch (Phase F-4).

설계: endpoint-18-ka10027.md § 6.1 + endpoint-19~22 + phase-f-4-rankings.md § 5.4.

본 테스트는 import 실패가 red 의도 (Step 0 TDD red):
- `app.adapter.out.kiwoom.rkinfo.KiwoomRkInfoClient` 미존재
- `_records.py` 의 5 Row/Response + 4 enum 미존재
→ Step 1 에서 신규 구현 후 green.

검증 (24 시나리오):

fetch_flu_rt_upper (ka10027) — 8건:
1. 정상 단일 페이지 + body 9 필드 검증 + api-id ka10027 헤더
2. 페이지네이션 (cont-yn=Y → N)
3. 빈 list (pred_pre_flu_rt_upper=[])
4. return_code=1 → KiwoomBusinessError
5. 페이지네이션 폭주 → KiwoomMaxPagesExceededError
6. body 반환값 — used_filters dict (재현용)
7. RankingMarketType enum value 매핑 (KOSPI="001" / KOSDAQ="101")
8. FluRtSortType enum value 매핑 (UP_RATE="1" / DOWN_RATE="3")

fetch_today_volume_upper (ka10030) — 4건:
9. 정상 단일 페이지 + list key `tdy_trde_qty_upper`
10. 23 필드 (장중/장후/장전 분리) 응답 → row 보존
11. return_code=1 → KiwoomBusinessError
12. mrkt_open_tp body 필드 → "1" default

fetch_pred_volume_upper (ka10031) — 3건:
13. 정상 + list key `pred_trde_qty_upper`
14. 6 필드 단순 응답
15. qry_tp body 필드

fetch_trde_prica_upper (ka10032) — 3건:
16. 정상 + list key `trde_prica_upper`
17. now_rank / pred_rank 응답 보존
18. body 3 필드 (mrkt_tp / mang_stk_incls / stex_tp)

fetch_volume_sdnin (ka10023) — 3건:
19. 정상 + list key `trde_qty_sdnin`
20. sdnin_rt 부호 (`+38.04`) 보존
21. tm_tp / tm body 필드

공통 — 3건:
22. KRX rate limit (250ms) 우회 - mock 으로 즉시 진행
23. token provider 호출 검증 (Bearer header)
24. URL /api/dostk/rkinfo 검증
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.adapter.out.kiwoom._client import KiwoomClient, KiwoomMaxPagesExceededError
from app.adapter.out.kiwoom._exceptions import KiwoomBusinessError
from app.adapter.out.kiwoom._records import (  # type: ignore[import]  # Step 1
    FluRtSortType,
    FluRtUpperResponse,
    FluRtUpperRow,
    PredVolumeUpperRow,
    RankingExchangeType,
    RankingMarketType,
    TodayVolumeSortType,
    TodayVolumeUpperRow,
    TradeAmountUpperRow,
    VolumeSdninRow,
    VolumeSdninSortType,
    VolumeSdninTimeType,
)
from app.adapter.out.kiwoom.rkinfo import KiwoomRkInfoClient  # type: ignore[import]  # Step 1

# ---------------------------------------------------------------------------
# 공통 픽스처
# ---------------------------------------------------------------------------


_FLU_RT_BODY: dict[str, Any] = {
    "pred_pre_flu_rt_upper": [
        {
            "stk_cls": "0",
            "stk_cd": "005930",
            "stk_nm": "삼성전자",
            "cur_prc": "+74800",
            "pred_pre_sig": "1",
            "pred_pre": "+17200",
            "flu_rt": "+29.86",
            "sel_req": "207",
            "buy_req": "3820638",
            "now_trde_qty": "446203",
            "cntr_str": "346.54",
            "cnt": "4",
        },
        {
            "stk_cls": "0",
            "stk_cd": "000660",
            "stk_nm": "SK하이닉스",
            "cur_prc": "+12000",
            "pred_pre_sig": "2",
            "pred_pre": "+2380",
            "flu_rt": "+24.74",
            "sel_req": "54",
            "buy_req": "0",
            "now_trde_qty": "6",
            "cntr_str": "500.00",
            "cnt": "1",
        },
    ],
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다",
}


_TODAY_VOLUME_BODY: dict[str, Any] = {
    "tdy_trde_qty_upper": [
        {
            "stk_cd": "005930",
            "stk_nm": "삼성전자",
            "cur_prc": "+74800",
            "pred_pre_sig": "1",
            "pred_pre": "+17200",
            "flu_rt": "+29.86",
            "trde_qty": "446203",
            "pred_rt": "+15.23",
            "trde_tern_rt": "1.25",
            "opmr_trde_qty": "100000",
            "opmr_pred_rt": "+10.00",
            "opmr_trde_rt": "0.5",
            "opmr_trde_amt": "5000000",
            "af_mkrt_trde_qty": "0",
            "af_mkrt_pred_rt": "0.00",
            "af_mkrt_trde_rt": "0",
            "af_mkrt_trde_amt": "0",
            "bf_mkrt_trde_qty": "346203",
            "bf_mkrt_pred_rt": "+8.5",
            "bf_mkrt_trde_rt": "0.75",
            "bf_mkrt_trde_amt": "25900000",
        },
    ],
    "return_code": 0,
    "return_msg": "정상",
}


_PRED_VOLUME_BODY: dict[str, Any] = {
    "pred_trde_qty_upper": [
        {
            "stk_cd": "005930",
            "stk_nm": "삼성전자",
            "cur_prc": "+74800",
            "pred_pre_sig": "1",
            "pred_pre": "+17200",
            "trde_qty": "446203",
        },
    ],
    "return_code": 0,
    "return_msg": "정상",
}


_TRDE_PRICA_BODY: dict[str, Any] = {
    "trde_prica_upper": [
        {
            "stk_cd": "005930",
            "stk_nm": "삼성전자",
            "cur_prc": "+74800",
            "pred_pre_sig": "1",
            "pred_pre": "+17200",
            "flu_rt": "+29.86",
            "now_trde_qty": "446203",
            "trde_prica": "33380000",
            "now_rank": "1",
            "pred_rank": "5",
        },
    ],
    "return_code": 0,
    "return_msg": "정상",
}


_VOLUME_SDNIN_BODY: dict[str, Any] = {
    "trde_qty_sdnin": [
        {
            "stk_cd": "005930",
            "stk_nm": "삼성전자",
            "cur_prc": "+74800",
            "pred_pre_sig": "1",
            "pred_pre": "+17200",
            "flu_rt": "+29.86",
            "now_trde_qty": "446203",
            "sdnin_qty": "1500000",
            "sdnin_rt": "+38.04",
        },
    ],
    "return_code": 0,
    "return_msg": "정상",
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
# fetch_flu_rt_upper (ka10027) — 8건
# ===========================================================================


@pytest.mark.asyncio
async def test_fetch_flu_rt_upper_single_page_returns_rows() -> None:
    """200 + pred_pre_flu_rt_upper 2건 → FluRtUpperRow list 반환.

    api-id=ka10027 + URL /api/dostk/rkinfo + body 9 필드 검증.
    """
    captured_body: dict[str, Any] = {}
    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        captured_headers["api-id"] = request.headers.get("api-id", "")
        assert request.url.path == "/api/dostk/rkinfo"
        return httpx.Response(200, json=_FLU_RT_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomRkInfoClient(kc)
        rows, used_filters = await adapter.fetch_flu_rt_upper()

    assert len(rows) == 2
    assert isinstance(rows[0], FluRtUpperRow)
    assert rows[0].stk_cd == "005930"
    assert rows[0].flu_rt == "+29.86"
    assert rows[1].stk_cd == "000660"
    assert captured_headers["api-id"] == "ka10027"
    # body 9 필드 모두 포함
    for key in (
        "mrkt_tp",
        "sort_tp",
        "trde_qty_cnd",
        "stk_cnd",
        "crd_cnd",
        "updown_incls",
        "pric_cnd",
        "trde_prica_cnd",
        "stex_tp",
    ):
        assert key in captured_body, f"body 필드 {key!r} 누락"
    assert isinstance(used_filters, dict)


@pytest.mark.asyncio
async def test_fetch_flu_rt_upper_paginates_with_cont_yn() -> None:
    """cont-yn=Y → 다음 페이지 자동 호출."""
    page2_body: dict[str, Any] = {
        "pred_pre_flu_rt_upper": [
            {
                "stk_cls": "0",
                "stk_cd": "373220",
                "stk_nm": "LG에너지솔루션",
                "cur_prc": "+200000",
                "pred_pre_sig": "1",
                "pred_pre": "+10000",
                "flu_rt": "+5.26",
                "sel_req": "100",
                "buy_req": "200",
                "now_trde_qty": "5000",
                "cntr_str": "100.00",
                "cnt": "1",
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
                200, json=_FLU_RT_BODY, headers={"cont-yn": "Y", "next-key": "p2"}
            )
        return httpx.Response(200, json=page2_body, headers={"cont-yn": "N"})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomRkInfoClient(kc)
        rows, _ = await adapter.fetch_flu_rt_upper()

    assert len(rows) == 3
    assert call_count == 2


@pytest.mark.asyncio
async def test_fetch_flu_rt_upper_empty_list_returns_empty() -> None:
    """pred_pre_flu_rt_upper=[] → 빈 list (정상)."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"pred_pre_flu_rt_upper": [], "return_code": 0, "return_msg": "정상"}
        )

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomRkInfoClient(kc)
        rows, _ = await adapter.fetch_flu_rt_upper()

    assert rows == []


@pytest.mark.asyncio
async def test_fetch_flu_rt_upper_business_error_raises() -> None:
    """return_code=1 → KiwoomBusinessError."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "pred_pre_flu_rt_upper": [],
                "return_code": 1,
                "return_msg": "잘못된 요청",
            },
        )

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomRkInfoClient(kc)
        with pytest.raises(KiwoomBusinessError) as exc_info:
            await adapter.fetch_flu_rt_upper()

    assert exc_info.value.api_id == "ka10027"


@pytest.mark.asyncio
async def test_fetch_flu_rt_upper_max_pages_exceeded() -> None:
    """cont-yn=Y 무한 → KiwoomMaxPagesExceededError."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=_FLU_RT_BODY, headers={"cont-yn": "Y", "next-key": "p"}
        )

    async with _make_kiwoom_client(handler, max_pages=2) as kc:
        adapter = KiwoomRkInfoClient(kc)
        with pytest.raises(KiwoomMaxPagesExceededError):
            await adapter.fetch_flu_rt_upper(max_pages=2)


@pytest.mark.asyncio
async def test_fetch_flu_rt_upper_returns_used_filters() -> None:
    """반환의 두 번째 값 = body 그대로 (request_filters 재현용)."""
    captured_body: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        return httpx.Response(200, json=_FLU_RT_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomRkInfoClient(kc)
        _, used_filters = await adapter.fetch_flu_rt_upper(
            market_type=RankingMarketType.KOSDAQ,
            sort_tp=FluRtSortType.DOWN_RATE,
            exchange_type=RankingExchangeType.KRX,
        )

    assert used_filters["mrkt_tp"] == "101"
    assert used_filters["sort_tp"] == "3"
    assert used_filters["stex_tp"] == "1"
    # 캡쳐 body 와 일치 (재현 가능)
    assert used_filters["mrkt_tp"] == captured_body["mrkt_tp"]


@pytest.mark.asyncio
async def test_fetch_flu_rt_upper_market_type_enum_mapping() -> None:
    """RankingMarketType.KOSPI → mrkt_tp='001' / KOSDAQ → '101' / ALL → '000'."""
    captured: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json=_FLU_RT_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomRkInfoClient(kc)
        await adapter.fetch_flu_rt_upper(market_type=RankingMarketType.KOSPI)
        await adapter.fetch_flu_rt_upper(market_type=RankingMarketType.KOSDAQ)
        await adapter.fetch_flu_rt_upper(market_type=RankingMarketType.ALL)

    assert captured[0]["mrkt_tp"] == "001"
    assert captured[1]["mrkt_tp"] == "101"
    assert captured[2]["mrkt_tp"] == "000"


@pytest.mark.asyncio
async def test_fetch_flu_rt_upper_sort_tp_enum_mapping() -> None:
    """FluRtSortType — UP_RATE=1 / UP_AMOUNT=2 / DOWN_RATE=3 / DOWN_AMOUNT=4 / UNCHANGED=5."""
    captured: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json=_FLU_RT_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomRkInfoClient(kc)
        for sort in (
            FluRtSortType.UP_RATE,
            FluRtSortType.DOWN_RATE,
            FluRtSortType.UNCHANGED,
        ):
            await adapter.fetch_flu_rt_upper(sort_tp=sort)

    assert captured[0]["sort_tp"] == "1"
    assert captured[1]["sort_tp"] == "3"
    assert captured[2]["sort_tp"] == "5"


# ===========================================================================
# fetch_today_volume_upper (ka10030) — 4건
# ===========================================================================


@pytest.mark.asyncio
async def test_fetch_today_volume_upper_list_key_and_api_id() -> None:
    """200 + tdy_trde_qty_upper list 1건 → TodayVolumeUpperRow + api-id ka10030."""
    captured_api_id: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_api_id.append(request.headers.get("api-id", ""))
        return httpx.Response(200, json=_TODAY_VOLUME_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomRkInfoClient(kc)
        rows, _ = await adapter.fetch_today_volume_upper()

    assert len(rows) == 1
    assert isinstance(rows[0], TodayVolumeUpperRow)
    assert rows[0].stk_cd == "005930"
    assert captured_api_id[0] == "ka10030"


@pytest.mark.asyncio
async def test_fetch_today_volume_upper_23_field_response_preserved() -> None:
    """23 필드 (장중/장후/장전 분리) 모두 row 에 보존 — D-9 nested payload 의 source."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_TODAY_VOLUME_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomRkInfoClient(kc)
        rows, _ = await adapter.fetch_today_volume_upper()

    row = rows[0]
    # 장중 (opmr_*) 4 필드
    assert row.opmr_trde_qty == "100000"
    assert row.opmr_pred_rt == "+10.00"
    # 장후 (af_mkrt_*) 4 필드 — 0 값 정상
    assert row.af_mkrt_trde_qty == "0"
    # 장전 (bf_mkrt_*) 4 필드
    assert row.bf_mkrt_trde_qty == "346203"
    assert row.bf_mkrt_trde_amt == "25900000"
    # 본 endpoint 정렬 기준
    assert row.trde_qty == "446203"
    assert row.trde_tern_rt == "1.25"


@pytest.mark.asyncio
async def test_fetch_today_volume_upper_business_error_raises() -> None:
    """return_code=1 → KiwoomBusinessError(api_id=ka10030)."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"tdy_trde_qty_upper": [], "return_code": 1, "return_msg": "err"},
        )

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomRkInfoClient(kc)
        with pytest.raises(KiwoomBusinessError) as exc_info:
            await adapter.fetch_today_volume_upper()

    assert exc_info.value.api_id == "ka10030"


@pytest.mark.asyncio
async def test_fetch_today_volume_upper_sort_tp_enum_mapping() -> None:
    """TodayVolumeSortType — TRADE_VOLUME=1 / TURNOVER_RATE=2 / TRADE_AMOUNT=3."""
    captured: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json=_TODAY_VOLUME_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomRkInfoClient(kc)
        await adapter.fetch_today_volume_upper(sort_tp=TodayVolumeSortType.TRADE_VOLUME)
        await adapter.fetch_today_volume_upper(
            sort_tp=TodayVolumeSortType.TURNOVER_RATE
        )

    assert captured[0]["sort_tp"] == "1"
    assert captured[1]["sort_tp"] == "2"


# ===========================================================================
# fetch_pred_volume_upper (ka10031) — 3건
# ===========================================================================


@pytest.mark.asyncio
async def test_fetch_pred_volume_upper_list_key_and_api_id() -> None:
    """list key `pred_trde_qty_upper` + api-id ka10031 + 단순 6 필드."""
    captured_api_id: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_api_id.append(request.headers.get("api-id", ""))
        return httpx.Response(200, json=_PRED_VOLUME_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomRkInfoClient(kc)
        rows, _ = await adapter.fetch_pred_volume_upper()

    assert len(rows) == 1
    assert isinstance(rows[0], PredVolumeUpperRow)
    assert captured_api_id[0] == "ka10031"


@pytest.mark.asyncio
async def test_fetch_pred_volume_upper_6_field_response() -> None:
    """ka10031 응답은 6 필드 단순 — stk_cd/stk_nm/cur_prc/pred_pre_sig/pred_pre/trde_qty."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_PRED_VOLUME_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomRkInfoClient(kc)
        rows, _ = await adapter.fetch_pred_volume_upper()

    row = rows[0]
    assert row.stk_cd == "005930"
    assert row.stk_nm == "삼성전자"
    assert row.cur_prc == "+74800"
    assert row.trde_qty == "446203"


@pytest.mark.asyncio
async def test_fetch_pred_volume_upper_body_5_fields() -> None:
    """body 5 필드 (mrkt_tp/qry_tp/rank_strt/rank_end/stex_tp) 모두 전송."""
    captured_body: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        return httpx.Response(200, json=_PRED_VOLUME_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomRkInfoClient(kc)
        await adapter.fetch_pred_volume_upper()

    # 핵심 필터 mrkt_tp / stex_tp 는 반드시
    assert "mrkt_tp" in captured_body
    assert "stex_tp" in captured_body


# ===========================================================================
# fetch_trde_prica_upper (ka10032) — 3건
# ===========================================================================


@pytest.mark.asyncio
async def test_fetch_trde_prica_upper_list_key_and_api_id() -> None:
    """list key `trde_prica_upper` + api-id ka10032."""
    captured_api_id: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_api_id.append(request.headers.get("api-id", ""))
        return httpx.Response(200, json=_TRDE_PRICA_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomRkInfoClient(kc)
        rows, _ = await adapter.fetch_trde_prica_upper()

    assert len(rows) == 1
    assert isinstance(rows[0], TradeAmountUpperRow)
    assert captured_api_id[0] == "ka10032"


@pytest.mark.asyncio
async def test_fetch_trde_prica_upper_now_rank_pred_rank_preserved() -> None:
    """now_rank=1 / pred_rank=5 — 순위 변동 시그널 source."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_TRDE_PRICA_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomRkInfoClient(kc)
        rows, _ = await adapter.fetch_trde_prica_upper()

    row = rows[0]
    assert row.now_rank == "1"
    assert row.pred_rank == "5"
    assert row.trde_prica == "33380000"


@pytest.mark.asyncio
async def test_fetch_trde_prica_upper_body_3_fields_minimal() -> None:
    """body 3 필드 — 가장 단순 (mrkt_tp/mang_stk_incls/stex_tp)."""
    captured_body: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        return httpx.Response(200, json=_TRDE_PRICA_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomRkInfoClient(kc)
        await adapter.fetch_trde_prica_upper()

    assert "mrkt_tp" in captured_body
    assert "stex_tp" in captured_body


# ===========================================================================
# fetch_volume_sdnin (ka10023) — 3건
# ===========================================================================


@pytest.mark.asyncio
async def test_fetch_volume_sdnin_list_key_and_api_id() -> None:
    """list key `trde_qty_sdnin` + api-id ka10023."""
    captured_api_id: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_api_id.append(request.headers.get("api-id", ""))
        return httpx.Response(200, json=_VOLUME_SDNIN_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomRkInfoClient(kc)
        rows, _ = await adapter.fetch_volume_sdnin()

    assert len(rows) == 1
    assert isinstance(rows[0], VolumeSdninRow)
    assert captured_api_id[0] == "ka10023"


@pytest.mark.asyncio
async def test_fetch_volume_sdnin_sdnin_rt_sign_preserved() -> None:
    """sdnin_rt=+38.04 부호 그대로 보존 (Pydantic Row 는 string 유지)."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_VOLUME_SDNIN_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomRkInfoClient(kc)
        rows, _ = await adapter.fetch_volume_sdnin()

    row = rows[0]
    assert row.sdnin_rt == "+38.04"
    assert row.sdnin_qty == "1500000"


@pytest.mark.asyncio
async def test_fetch_volume_sdnin_sort_and_time_type_enums() -> None:
    """VolumeSdninSortType + VolumeSdninTimeType enum 매핑."""
    captured: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json=_VOLUME_SDNIN_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomRkInfoClient(kc)
        await adapter.fetch_volume_sdnin(
            sort_tp=VolumeSdninSortType.SUDDEN_VOLUME,
            tm_tp=VolumeSdninTimeType.MINUTES,
        )

    body = captured[0]
    assert body["sort_tp"] == "1"
    assert body["tm_tp"] == "1"


# ===========================================================================
# 공통 — 3건
# ===========================================================================


@pytest.mark.asyncio
async def test_token_provider_called_for_each_request() -> None:
    """매 호출마다 token_provider 가 호출되어 Bearer 헤더 세팅."""
    captured_auth: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_auth.append(request.headers.get("authorization", ""))
        return httpx.Response(200, json=_FLU_RT_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomRkInfoClient(kc)
        await adapter.fetch_flu_rt_upper()
        await adapter.fetch_today_volume_upper()

    assert all(a.startswith("Bearer ") for a in captured_auth)
    assert len(captured_auth) == 2


@pytest.mark.asyncio
async def test_url_path_consistent_across_5_endpoints() -> None:
    """5 endpoint 모두 URL = /api/dostk/rkinfo (공유 path)."""
    captured_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_paths.append(request.url.path)
        # 각 endpoint 의 응답 body 매칭 — api-id 헤더에 따라
        api_id = request.headers.get("api-id", "")
        if api_id == "ka10027":
            return httpx.Response(200, json=_FLU_RT_BODY)
        if api_id == "ka10030":
            return httpx.Response(200, json=_TODAY_VOLUME_BODY)
        if api_id == "ka10031":
            return httpx.Response(200, json=_PRED_VOLUME_BODY)
        if api_id == "ka10032":
            return httpx.Response(200, json=_TRDE_PRICA_BODY)
        return httpx.Response(200, json=_VOLUME_SDNIN_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomRkInfoClient(kc)
        await adapter.fetch_flu_rt_upper()
        await adapter.fetch_today_volume_upper()
        await adapter.fetch_pred_volume_upper()
        await adapter.fetch_trde_prica_upper()
        await adapter.fetch_volume_sdnin()

    assert all(p == "/api/dostk/rkinfo" for p in captured_paths), (
        f"5 endpoint 모두 /api/dostk/rkinfo 기대, 실제 paths: {captured_paths}"
    )
    assert len(captured_paths) == 5


@pytest.mark.asyncio
async def test_fetch_flu_rt_upper_response_pydantic_validation() -> None:
    """FluRtUpperResponse 가 model_validate 로 응답 dict 파싱 — extra='ignore' 으로 미지 필드 흡수."""
    body_with_extra = {
        "pred_pre_flu_rt_upper": [
            {
                "stk_cls": "0",
                "stk_cd": "005930",
                "stk_nm": "삼성전자",
                "cur_prc": "+74800",
                "pred_pre_sig": "1",
                "pred_pre": "+17200",
                "flu_rt": "+29.86",
                "sel_req": "207",
                "buy_req": "3820638",
                "now_trde_qty": "446203",
                "cntr_str": "346.54",
                "cnt": "4",
                "future_field": "vendor_added_later",  # 새 필드 — extra='ignore'
            }
        ],
        "return_code": 0,
        "return_msg": "정상",
    }

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body_with_extra)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomRkInfoClient(kc)
        rows, _ = await adapter.fetch_flu_rt_upper()

    # extra='ignore' — 신규 필드는 무시되고 알려진 필드만 추출
    assert len(rows) == 1
    assert rows[0].stk_cd == "005930"
    # extra 필드는 Row 에 없음
    assert not hasattr(rows[0], "future_field")


@pytest.mark.asyncio
async def test_fetch_flu_rt_upper_response_model_can_be_imported() -> None:
    """FluRtUpperResponse 가 정상 import 가능 — public API 보장."""
    # 빈 응답으로 model_validate 직접 호출 가능 (구조 검증)
    parsed = FluRtUpperResponse.model_validate(_FLU_RT_BODY)
    assert parsed.return_code == 0
    assert len(parsed.pred_pre_flu_rt_upper) == 2
    assert parsed.pred_pre_flu_rt_upper[0].stk_cd == "005930"
