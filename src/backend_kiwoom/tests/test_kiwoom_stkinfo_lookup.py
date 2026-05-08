"""KiwoomStkInfoClient.lookup_stock (ka10100) — B-β 어댑터 단위 테스트.

KiwoomClient(공통 트랜스포트) 가 토큰/재시도/rate-limit 위임 책임이라 어댑터 자체
테스트는 단건 호출 + Pydantic 검증 + stk_cd 사전 검증 + zero-padded 정규화 + return_code 처리
+ ka10099 의 NormalizedStock 변환 일관성에 집중.

httpx.MockTransport 주입으로 외부 호출 0.

시나리오 (§9.1):
1. 정상 단건 — 200 + 14 필드 응답 → StockLookupResponse 정상 파싱
2. 응답 nxtEnable="Y" → to_normalized().nxt_enable=True
3. 응답 nxtEnable="" → to_normalized().nxt_enable=False
4. 응답 nxtEnable="N" → to_normalized().nxt_enable=False
5. return_code=1 → KiwoomBusinessError (트랜스포트가 raise)
6. 401 → KiwoomCredentialRejectedError
7. stk_cd="00593" (5자리) → ValueError, httpx 호출 안 함
8. stk_cd="005930_NX" (suffix) → ValueError
9. stk_cd="ABC123" (영문 포함) → ValueError
10. 응답 code="" → KiwoomResponseValidationError (Pydantic min_length=1)
11. 응답 regDay="invalid" → to_normalized().listed_date=None
12. mock_env=True + nxtEnable="Y" → to_normalized().nxt_enable=False (강제)
13. zero-padded listCount → int 정규화
14. Pydantic extra 필드 무시
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.adapter.out.kiwoom._client import KiwoomClient
from app.adapter.out.kiwoom._exceptions import (
    KiwoomBusinessError,
    KiwoomCredentialRejectedError,
    KiwoomResponseValidationError,
)
from app.adapter.out.kiwoom.stkinfo import (
    KiwoomStkInfoClient,
    NormalizedStock,
    StockLookupResponse,
)

# ka10100 응답 예시 — Excel R45 기반 (14 필드 + return_code/msg).
_SAMSUNG_BODY: dict[str, Any] = {
    "code": "005930",
    "name": "삼성전자",
    "listCount": "0000000026034239",
    "auditInfo": "정상",
    "regDay": "20090803",
    "lastPrice": "00136000",
    "state": "증거금20%|담보대출|신용가능",
    "marketCode": "0",
    "marketName": "거래소",
    "upName": "금융업",
    "upSizeName": "대형주",
    "companyClassName": "",
    "orderWarning": "0",
    "nxtEnable": "Y",
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


# -----------------------------------------------------------------------------
# 1. 정상 단건 호출
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lookup_stock_returns_response_for_samsung() -> None:
    captured_body: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured_body.update(json.loads(request.content))
        assert request.headers["api-id"] == "ka10100"
        assert request.url.path == "/api/dostk/stkinfo"
        return httpx.Response(200, json=_SAMSUNG_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        resp = await adapter.lookup_stock("005930")

    assert isinstance(resp, StockLookupResponse)
    assert resp.code == "005930"
    assert resp.name == "삼성전자"
    assert resp.marketCode == "0"
    assert resp.nxtEnable == "Y"
    assert resp.return_code == 0
    assert captured_body == {"stk_cd": "005930"}


# -----------------------------------------------------------------------------
# 2-4. nxtEnable 정규화
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lookup_stock_nxt_enable_y_normalizes_to_true() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={**_SAMSUNG_BODY, "nxtEnable": "Y"})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        resp = await adapter.lookup_stock("005930")

    n: NormalizedStock = resp.to_normalized()
    assert n.nxt_enable is True


@pytest.mark.asyncio
async def test_lookup_stock_nxt_enable_empty_normalizes_to_false() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={**_SAMSUNG_BODY, "nxtEnable": ""})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        resp = await adapter.lookup_stock("005930")

    n = resp.to_normalized()
    assert n.nxt_enable is False


@pytest.mark.asyncio
async def test_lookup_stock_nxt_enable_n_normalizes_to_false() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={**_SAMSUNG_BODY, "nxtEnable": "N"})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        resp = await adapter.lookup_stock("005930")

    n = resp.to_normalized()
    assert n.nxt_enable is False


# -----------------------------------------------------------------------------
# 5-6. 에러 전파
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lookup_stock_propagates_business_error() -> None:
    """return_code=1 (존재하지 않는 종목 등) — 트랜스포트가 KiwoomBusinessError raise."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"return_code": 1, "return_msg": "존재하지 않는 종목"},
        )

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        with pytest.raises(KiwoomBusinessError) as exc_info:
            await adapter.lookup_stock("999999")

    assert exc_info.value.return_code == 1


@pytest.mark.asyncio
async def test_lookup_stock_propagates_credential_rejected() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        with pytest.raises(KiwoomCredentialRejectedError):
            await adapter.lookup_stock("005930")


# -----------------------------------------------------------------------------
# 7-9. stk_cd 사전 검증 — 호출 자체 차단
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lookup_stock_rejects_short_stk_cd() -> None:
    """5자리 stk_cd → ValueError. 호출 안 함."""
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=_SAMSUNG_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        with pytest.raises(ValueError):
            await adapter.lookup_stock("00593")

    assert call_count == 0, "ValueError 시 키움 호출 안 함"


@pytest.mark.asyncio
async def test_lookup_stock_rejects_nx_suffix() -> None:
    """`_NX` suffix 거부 (Excel R22 Length=6 강제) — `_NX` 는 ka10081 차트 endpoint 전용."""
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=_SAMSUNG_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        with pytest.raises(ValueError):
            await adapter.lookup_stock("005930_NX")

    assert call_count == 0


@pytest.mark.asyncio
async def test_lookup_stock_rejects_alpha_chars() -> None:
    """영문/숫자 혼합 거부."""
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=_SAMSUNG_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        for invalid in ("ABC123", "00593a", "      ", ""):
            with pytest.raises(ValueError):
                await adapter.lookup_stock(invalid)

    assert call_count == 0


# -----------------------------------------------------------------------------
# 10. 응답 검증 실패 — Pydantic
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lookup_stock_raises_validation_when_code_empty() -> None:
    """code 필드가 빈 문자열 → KiwoomResponseValidationError + __context__ None.

    StockLookupResponse 의 code 는 min_length=1 — 빈값은 Pydantic 검증 실패.
    """

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={**_SAMSUNG_BODY, "code": ""},
        )

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        with pytest.raises(KiwoomResponseValidationError) as exc_info:
            await adapter.lookup_stock("005930")

    err = exc_info.value
    assert err.__context__ is None, "Pydantic ValidationError context leak — except 밖 raise 회귀"
    assert err.__cause__ is None


# -----------------------------------------------------------------------------
# 11. regDay invalid → listed_date=None
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lookup_stock_invalid_reg_day_normalizes_to_none() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={**_SAMSUNG_BODY, "regDay": "invalid"})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        resp = await adapter.lookup_stock("005930")

    n = resp.to_normalized()
    assert n.listed_date is None


# -----------------------------------------------------------------------------
# 12. mock_env 강제 false
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lookup_stock_mock_env_forces_nxt_enable_false() -> None:
    """mock_env=True 면 응답 nxtEnable="Y" 무시 + 강제 False (mock 도메인 NXT 미지원)."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={**_SAMSUNG_BODY, "nxtEnable": "Y"})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        resp = await adapter.lookup_stock("005930")

    n = resp.to_normalized(mock_env=True)
    assert n.nxt_enable is False


# -----------------------------------------------------------------------------
# 13. zero-padded 정규화
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lookup_stock_zero_padded_list_count_normalized() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={**_SAMSUNG_BODY, "listCount": "0000005969782550"},
        )

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        resp = await adapter.lookup_stock("005930")

    n = resp.to_normalized()
    assert n.list_count == 5969782550


@pytest.mark.asyncio
async def test_lookup_stock_zero_padded_last_price_normalized() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={**_SAMSUNG_BODY, "lastPrice": "00075800"})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        resp = await adapter.lookup_stock("005930")

    n = resp.to_normalized()
    assert n.last_price == 75800


# -----------------------------------------------------------------------------
# 14. Pydantic extra 필드 무시
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lookup_stock_extra_fields_ignored() -> None:
    """키움이 신규 필드 추가해도 어댑터 안 깨짐."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={**_SAMSUNG_BODY, "newField2026": "value", "anotherField": 42},
        )

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        resp = await adapter.lookup_stock("005930")

    assert resp.code == "005930"
    assert resp.name == "삼성전자"


# -----------------------------------------------------------------------------
# Pydantic 모델 단위 — to_normalized 의 market_code 정책
# -----------------------------------------------------------------------------


def test_to_normalized_uses_response_market_code_directly() -> None:
    """ka10100 은 단건 — 응답의 marketCode 를 그대로 사용 (ka10099 의 requested_market_code 와 다름).

    이유: ka10100 은 stk_cd 만으로 호출하므로 요청에 mrkt_tp 가 없음. 응답 marketCode 가
    유일한 신뢰 source.
    """
    resp = StockLookupResponse(
        code="005930",
        name="삼성전자",
        marketCode="0",
        marketName="거래소",
        nxtEnable="Y",
    )
    n = resp.to_normalized()
    assert n.market_code == "0"
    assert n.requested_market_type == "0"


def test_to_normalized_business_error_response_is_unparseable_at_business_layer() -> None:
    """본 어댑터 메서드는 트랜스포트가 return_code != 0 시 KiwoomBusinessError raise 의존.

    pure to_normalized 는 어쨌거나 여기까지 오면 정상 데이터로 가정 — 메타 검증은 별도.
    """
    resp = StockLookupResponse(code="000001", name="X")
    n = resp.to_normalized()
    assert n.stock_code == "000001"
    assert n.list_count is None  # 빈 listCount
