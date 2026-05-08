"""KiwoomStkInfoClient.fetch_stock_list (ka10099) — B-α 어댑터 단위 테스트.

KiwoomClient(공통 트랜스포트) 가 페이지네이션·재시도·rate-limit 위임 책임이라
어댑터 자체 테스트는 응답 파싱 + Pydantic 검증 + mrkt_tp 사전 검증 + zero-padded
정규화 + nxt_enable 변환에 집중.

httpx.MockTransport 주입으로 외부 호출 0.

시나리오 (§9.1):
1. 정상 단일 페이지 (mrkt_tp=KOSPI, 200 + 5 rows) — Excel 예시 변형
2. mrkt_tp 잘못된 값 → ValueError (호출 전, StrEnum 우회 안전망)
3. 다중 페이지 — cont-yn=Y/N 합쳐짐
4. 빈 list — 정상
5. return_code != 0 → KiwoomBusinessError 전파
6. 401 → KiwoomCredentialRejectedError 전파
7. 페이지네이션 폭주 — max_pages=100 도달 시 KiwoomMaxPagesExceededError
8. 응답 row regDay="invalid" → to_normalized() listed_date=None
9. 응답 row listCount="abc" 비숫자 → ValueError (caller 매핑)
10. nxtEnable="" 빈 문자열 → nxt_enable=False
11. nxtEnable="y" 소문자 → nxt_enable=True
12. mock_env=True → nxtEnable="Y" 응답 무시 (강제 False)
13. Pydantic extra 필드 → ignore
14. response 검증 실패 (code 누락) → KiwoomResponseValidationError + __context__ None
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

import httpx
import pytest

from app.adapter.out.kiwoom._client import KiwoomClient, KiwoomMaxPagesExceededError
from app.adapter.out.kiwoom._exceptions import (
    KiwoomBusinessError,
    KiwoomCredentialRejectedError,
    KiwoomResponseValidationError,
)
from app.adapter.out.kiwoom.stkinfo import (
    KiwoomStkInfoClient,
    NormalizedStock,
    StockListResponse,
    StockListRow,
    _parse_yyyymmdd,
    _parse_zero_padded_int,
)
from app.application.constants import StockListMarketType

# ka10099 응답 예시 — Excel R46 기반, 5 rows (변형 — 다양한 종목 코드)
_KOSPI_STOCK_BODY: dict[str, Any] = {
    "return_msg": "정상적으로 처리되었습니다",
    "return_code": 0,
    "list": [
        {
            "code": "005930",
            "name": "삼성전자",
            "listCount": "0000005969782550",
            "auditInfo": "정상",
            "regDay": "19750611",
            "lastPrice": "00075800",
            "state": "증거금20%|담보대출|신용가능",
            "marketCode": "0",
            "marketName": "거래소",
            "upName": "전기전자",
            "upSizeName": "대형주",
            "companyClassName": "",
            "orderWarning": "0",
            "nxtEnable": "Y",
        },
        {
            "code": "000660",
            "name": "SK하이닉스",
            "listCount": "0000000728002365",
            "auditInfo": "정상",
            "regDay": "19960712",
            "lastPrice": "00211000",
            "state": "증거금20%|담보대출|신용가능",
            "marketCode": "0",
            "marketName": "거래소",
            "upName": "전기전자",
            "upSizeName": "대형주",
            "companyClassName": "",
            "orderWarning": "0",
            "nxtEnable": "Y",
        },
        {
            "code": "035420",
            "name": "NAVER",
            "listCount": "0000000164263395",
            "auditInfo": "정상",
            "regDay": "20021029",
            "lastPrice": "00224000",
            "state": "증거금20%|담보대출",
            "marketCode": "0",
            "marketName": "거래소",
            "upName": "서비스업",
            "upSizeName": "대형주",
            "companyClassName": "",
            "orderWarning": "0",
            "nxtEnable": "",
        },
        {
            "code": "207940",
            "name": "삼성바이오로직스",
            "listCount": "0000000071167500",
            "auditInfo": "정상",
            "regDay": "20161110",
            "lastPrice": "01200000",
            "state": "증거금20%",
            "marketCode": "0",
            "marketName": "거래소",
            "upName": "의약품",
            "upSizeName": "대형주",
            "companyClassName": "",
            "orderWarning": "0",
            "nxtEnable": "N",
        },
        {
            "code": "068270",
            "name": "셀트리온",
            "listCount": "0000000216853892",
            "auditInfo": "정상",
            "regDay": "20180209",
            "lastPrice": "00154000",
            "state": "증거금20%|담보대출|신용가능",
            "marketCode": "0",
            "marketName": "거래소",
            "upName": "의약품",
            "upSizeName": "대형주",
            "companyClassName": "",
            "orderWarning": "0",
            "nxtEnable": "y",  # 소문자
        },
    ],
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


# -----------------------------------------------------------------------------
# 1. 정상 호출
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_stock_list_returns_response_for_kospi() -> None:
    captured_body: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured_body.update(json.loads(request.content))
        assert request.headers["api-id"] == "ka10099"
        assert request.url.path == "/api/dostk/stkinfo"
        return httpx.Response(200, json=_KOSPI_STOCK_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        resp = await adapter.fetch_stock_list(StockListMarketType.KOSPI)

    assert isinstance(resp, StockListResponse)
    assert len(resp.items) == 5
    assert resp.items[0].code == "005930"
    assert resp.items[0].name == "삼성전자"
    assert resp.items[0].marketCode == "0"
    assert resp.items[0].nxtEnable == "Y"
    assert resp.return_code == 0
    assert captured_body == {"mrkt_tp": "0"}


# -----------------------------------------------------------------------------
# 2. mrkt_tp 사전 검증 (StrEnum 우회 안전망)
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_stock_list_rejects_invalid_mrkt_tp_value() -> None:
    """mrkt_tp 가 16종 외 — ValueError. 호출 자체 안 함."""
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json={"return_code": 0})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        for invalid in ("99", "11", "100", "abc"):
            with pytest.raises(ValueError):
                await adapter.fetch_stock_list(cast(Any, invalid))

    assert call_count == 0, "ValueError 시 키움 호출 안 함"


# -----------------------------------------------------------------------------
# 3. 페이지네이션
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_stock_list_combines_paginated_responses() -> None:
    call_count = 0

    def _row(code: str) -> dict[str, str]:
        return {
            "code": code,
            "name": f"종목-{code}",
            "marketCode": "0",
            "listCount": "0000000000001000",
            "regDay": "20200101",
            "lastPrice": "00010000",
            "nxtEnable": "Y",
        }

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(
                200,
                json={"return_code": 0, "list": [_row("000001"), _row("000002")]},
                headers={"cont-yn": "Y", "next-key": "page-2"},
            )
        return httpx.Response(
            200,
            json={"return_code": 0, "list": [_row("000003")]},
            headers={"cont-yn": "N"},
        )

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        resp = await adapter.fetch_stock_list(StockListMarketType.KOSPI)

    assert call_count == 2
    assert len(resp.items) == 3
    assert [r.code for r in resp.items] == ["000001", "000002", "000003"]


# -----------------------------------------------------------------------------
# 4. 빈 list
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_stock_list_empty_list_is_valid() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"return_code": 0, "list": []})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        resp = await adapter.fetch_stock_list(StockListMarketType.KONEX)

    assert resp.items == []
    assert resp.return_code == 0


# -----------------------------------------------------------------------------
# 5-6. 에러 전파
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_stock_list_propagates_business_error() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"return_code": 1, "return_msg": "조회 실패"})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        with pytest.raises(KiwoomBusinessError):
            await adapter.fetch_stock_list(StockListMarketType.KOSPI)


@pytest.mark.asyncio
async def test_fetch_stock_list_propagates_credential_rejected() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        with pytest.raises(KiwoomCredentialRejectedError):
            await adapter.fetch_stock_list(StockListMarketType.KOSPI)


# -----------------------------------------------------------------------------
# 7. max_pages 폭주 차단
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_stock_list_propagates_max_pages_exceeded() -> None:
    """무한 cont-yn=Y 시 max_pages=100 도달 후 KiwoomMaxPagesExceededError."""
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            200,
            json={"return_code": 0, "list": []},
            headers={"cont-yn": "Y", "next-key": f"k-{call_count}"},
        )

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        with pytest.raises(KiwoomMaxPagesExceededError):
            await adapter.fetch_stock_list(StockListMarketType.KOSPI)

    assert call_count == 100, "어댑터 max_pages=100 hard cap"


# -----------------------------------------------------------------------------
# 8. 응답 검증 실패 — Pydantic
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_stock_list_raises_validation_when_row_missing_code() -> None:
    """row 의 code 필드 누락 → KiwoomResponseValidationError + __context__ None."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "return_code": 0,
                "list": [{"name": "이름만"}],  # code 누락
            },
        )

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        with pytest.raises(KiwoomResponseValidationError) as exc_info:
            await adapter.fetch_stock_list(StockListMarketType.KOSPI)

    err = exc_info.value
    assert err.__context__ is None, "Pydantic ValidationError context leak — except 밖 raise 회귀"
    assert err.__cause__ is None


# -----------------------------------------------------------------------------
# Pydantic 모델 단위 + 정규화
# -----------------------------------------------------------------------------


def test_stock_row_accepts_minimum_fields() -> None:
    row = StockListRow(code="005930", name="삼성전자")
    assert row.listCount == ""
    assert row.nxtEnable == ""
    assert row.orderWarning == "0"


def test_stock_row_extra_field_ignored() -> None:
    """키움이 응답에 신규 필드 추가해도 어댑터 안 깨짐."""
    row = StockListRow.model_validate(
        {
            "code": "005930",
            "name": "삼성전자",
            "future_field": "ignored",
            "listCount": "0000000000001000",
            "nxtEnable": "Y",
        }
    )
    assert row.code == "005930"
    assert row.listCount == "0000000000001000"


def test_stock_list_response_default_empty_list() -> None:
    resp = StockListResponse.model_validate({"return_code": 0})
    assert resp.items == []


def test_stock_list_response_alias_list_supported() -> None:
    """JSON 키는 'list' (키움 응답 그대로) — alias 동작 검증."""
    resp = StockListResponse.model_validate({"list": [{"code": "005930", "name": "삼성전자"}], "return_code": 0})
    assert len(resp.items) == 1
    assert resp.items[0].code == "005930"


# -----------------------------------------------------------------------------
# to_normalized 변환 — 핵심 (B-α 의 차별점)
# -----------------------------------------------------------------------------


def test_to_normalized_zero_padded_list_count_to_int() -> None:
    """zero-padded 16자리 listCount → int."""
    row = StockListRow(
        code="005930",
        name="삼성전자",
        listCount="0000005969782550",
    )
    n = row.to_normalized(requested_market_code="0")
    assert n.list_count == 5969782550


def test_to_normalized_zero_padded_last_price_to_int() -> None:
    """zero-padded lastPrice → int. all-zero 는 0."""
    row = StockListRow(code="005930", name="삼성전자", lastPrice="00000000")
    n = row.to_normalized(requested_market_code="0")
    assert n.last_price == 0


def test_to_normalized_empty_list_count_returns_none() -> None:
    """빈 문자열 → None (NULL 허용 §3.4)."""
    row = StockListRow(code="005930", name="삼성전자", listCount="")
    n = row.to_normalized(requested_market_code="0")
    assert n.list_count is None


def test_to_normalized_invalid_list_count_raises_value_error() -> None:
    """비숫자 → int() 변환 실패 → ValueError 전파 (caller 매핑)."""
    row = StockListRow(code="005930", name="삼성전자", listCount="abc")
    with pytest.raises(ValueError):
        row.to_normalized(requested_market_code="0")


def test_to_normalized_reg_day_yyyymmdd_to_date() -> None:
    """8자리 YYYYMMDD → date."""
    from datetime import date as _date

    row = StockListRow(code="005930", name="삼성전자", regDay="19750611")
    n = row.to_normalized(requested_market_code="0")
    assert n.listed_date == _date(1975, 6, 11)


def test_to_normalized_reg_day_invalid_returns_none() -> None:
    """형식 위반 → None (listed_date NULL 허용 §3.4)."""
    row = StockListRow(code="005930", name="삼성전자", regDay="invalid")
    n = row.to_normalized(requested_market_code="0")
    assert n.listed_date is None


def test_to_normalized_reg_day_empty_returns_none() -> None:
    row = StockListRow(code="005930", name="삼성전자", regDay="")
    n = row.to_normalized(requested_market_code="0")
    assert n.listed_date is None


def test_to_normalized_reg_day_out_of_range_returns_none() -> None:
    """20999999 같은 잘못된 날짜 → None."""
    row = StockListRow(code="005930", name="삼성전자", regDay="20991399")
    n = row.to_normalized(requested_market_code="0")
    assert n.listed_date is None


def test_to_normalized_nxt_enable_y_to_true() -> None:
    row = StockListRow(code="005930", name="삼성전자", nxtEnable="Y")
    n = row.to_normalized(requested_market_code="0")
    assert n.nxt_enable is True


def test_to_normalized_nxt_enable_lowercase_to_true() -> None:
    """소문자 'y' 도 True (upper() 정규화)."""
    row = StockListRow(code="005930", name="삼성전자", nxtEnable="y")
    n = row.to_normalized(requested_market_code="0")
    assert n.nxt_enable is True


def test_to_normalized_nxt_enable_empty_to_false() -> None:
    row = StockListRow(code="005930", name="삼성전자", nxtEnable="")
    n = row.to_normalized(requested_market_code="0")
    assert n.nxt_enable is False


def test_to_normalized_nxt_enable_n_to_false() -> None:
    row = StockListRow(code="005930", name="삼성전자", nxtEnable="N")
    n = row.to_normalized(requested_market_code="0")
    assert n.nxt_enable is False


def test_to_normalized_mock_env_forces_nxt_enable_false() -> None:
    """§4.2 mock 도메인 안전판 — nxtEnable='Y' 응답 무시 강제 False."""
    row = StockListRow(code="005930", name="삼성전자", nxtEnable="Y")
    n = row.to_normalized(requested_market_code="0", mock_env=True)
    assert n.nxt_enable is False, "mock 환경은 응답 nxtEnable 무시"


def test_to_normalized_market_code_always_uses_requested() -> None:
    """1R H1 — 응답 marketCode 와 무관하게 요청 mrkt_tp 가 권위 있는 source.

    Cross-market zombie row 방지 — deactivate_missing 격리 보장 위해 요청값 우선.
    응답 marketCode 가 요청과 다른 경우 (§11.2 Excel 샘플 의심) 영속화 안 함.
    """
    # case 1: 응답 marketCode 가 요청과 다름 — 요청값 우선
    row1 = StockListRow(code="005930", name="삼성전자", marketCode="10")
    n1 = row1.to_normalized(requested_market_code="0")
    assert n1.market_code == "0"
    assert n1.requested_market_type == "0"

    # case 2: 응답 marketCode 빈 문자열 — 요청값 fallback (동일 결과)
    row2 = StockListRow(code="005930", name="삼성전자", marketCode="")
    n2 = row2.to_normalized(requested_market_code="0")
    assert n2.market_code == "0"

    # case 3: 응답 marketCode 가 요청과 동일 — 자명히 요청값
    row3 = StockListRow(code="005930", name="삼성전자", marketCode="0")
    n3 = row3.to_normalized(requested_market_code="0")
    assert n3.market_code == "0"


def test_to_normalized_optional_fields_to_none() -> None:
    """빈 문자열 → None 정규화 (NULL 허용)."""
    row = StockListRow(code="005930", name="삼성전자")
    n = row.to_normalized(requested_market_code="0")
    assert n.audit_info is None
    assert n.state is None
    assert n.up_name is None
    assert n.up_size_name is None
    assert n.company_class_name is None
    assert n.market_name is None


def test_to_normalized_returns_normalized_stock_dataclass() -> None:
    row = StockListRow(code="005930", name="삼성전자")
    n = row.to_normalized(requested_market_code="0")
    assert isinstance(n, NormalizedStock)
    assert n.stock_code == "005930"
    assert n.stock_name == "삼성전자"


def test_to_normalized_order_warning_default_zero() -> None:
    row = StockListRow(code="005930", name="삼성전자")
    n = row.to_normalized(requested_market_code="0")
    assert n.order_warning == "0"


# -----------------------------------------------------------------------------
# 헬퍼 단위
# -----------------------------------------------------------------------------


def test_parse_yyyymmdd_valid() -> None:
    from datetime import date as _date

    assert _parse_yyyymmdd("19750611") == _date(1975, 6, 11)
    assert _parse_yyyymmdd("20260508") == _date(2026, 5, 8)


def test_parse_yyyymmdd_empty_returns_none() -> None:
    assert _parse_yyyymmdd("") is None


def test_parse_yyyymmdd_short_returns_none() -> None:
    assert _parse_yyyymmdd("20260") is None


def test_parse_yyyymmdd_out_of_range_returns_none() -> None:
    assert _parse_yyyymmdd("20991399") is None
    assert _parse_yyyymmdd("99999999") is None


def test_parse_zero_padded_int_normal() -> None:
    assert _parse_zero_padded_int("0000000123759593") == 123759593
    assert _parse_zero_padded_int("0000000000000001") == 1
    assert _parse_zero_padded_int("00000000") == 0


def test_parse_zero_padded_int_empty_returns_none() -> None:
    assert _parse_zero_padded_int("") is None


def test_parse_zero_padded_int_invalid_raises_value_error() -> None:
    with pytest.raises(ValueError):
        _parse_zero_padded_int("abc")
