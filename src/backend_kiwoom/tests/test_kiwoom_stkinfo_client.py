"""KiwoomStkInfoClient.fetch_sectors (ka10101) — 어댑터 단위 테스트.

KiwoomClient(공통 트랜스포트) 가 페이지네이션·재시도·rate-limit 위임 책임이라
어댑터 자체 테스트는 응답 파싱 + Pydantic 검증 + mrkt_tp 사전 검증에 집중.

httpx.MockTransport 주입으로 외부 호출 0.

시나리오:
1. fetch_sectors 정상 (mrkt_tp=0, 200 + 11 rows) — Excel 예시 그대로
2. mrkt_tp 잘못된 값 ("3"/"5"/"6") → ValueError (호출 전)
3. mrkt_tp Literal 외 ("xxx") → ValueError
4. 페이지네이션 — 두 페이지 합쳐짐
5. 빈 list — 정상
6. return_code != 0 → KiwoomBusinessError 전파 (KiwoomClient 가 raise)
7. 401 → KiwoomCredentialRejectedError 전파
8. 응답 row 검증 누락 (`code` 없음) → KiwoomResponseValidationError
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

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
    SectorListResponse,
    SectorRow,
)

_KOSPI_SECTOR_BODY = {
    "return_msg": "정상적으로 처리되었습니다",
    "return_code": 0,
    "list": [
        {"marketCode": "0", "code": "001", "name": "종합(KOSPI)", "group": "1"},
        {"marketCode": "0", "code": "002", "name": "대형주", "group": "2"},
        {"marketCode": "0", "code": "003", "name": "중형주", "group": "3"},
        {"marketCode": "0", "code": "004", "name": "소형주", "group": "4"},
        {"marketCode": "0", "code": "005", "name": "음식료업", "group": "5"},
        {"marketCode": "0", "code": "006", "name": "섬유의복", "group": "6"},
        {"marketCode": "0", "code": "007", "name": "종이목재", "group": "7"},
        {"marketCode": "0", "code": "008", "name": "화학", "group": "8"},
        {"marketCode": "0", "code": "009", "name": "의약품", "group": "9"},
        {"marketCode": "0", "code": "010", "name": "비금속광물", "group": "10"},
        {"marketCode": "0", "code": "011", "name": "철강금속", "group": "11"},
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
async def test_fetch_sectors_returns_response_for_kospi() -> None:
    captured_body: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured_body.update(json.loads(request.content))
        assert request.headers["api-id"] == "ka10101"
        assert request.url.path == "/api/dostk/stkinfo"
        return httpx.Response(200, json=_KOSPI_SECTOR_BODY)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        resp = await adapter.fetch_sectors("0")

    assert isinstance(resp, SectorListResponse)
    assert len(resp.items) == 11
    assert resp.items[0].code == "001"
    assert resp.items[0].name == "종합(KOSPI)"
    assert resp.items[0].marketCode == "0"
    assert resp.items[0].group == "1"
    assert resp.return_code == 0
    assert captured_body == {"mrkt_tp": "0"}


# -----------------------------------------------------------------------------
# 2-3. mrkt_tp 사전 검증
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_sectors_rejects_invalid_mrkt_tp_value() -> None:
    """mrkt_tp 유효값 (0/1/2/4/7) 외 — ValueError. 호출 자체 안 함."""
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json={"return_code": 0})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        for invalid in ("3", "5", "6", "8", "9"):
            # M2 안전망 검증: Literal 타입 우회 (런타임 가드 동작 확인)
            with pytest.raises(ValueError):
                await adapter.fetch_sectors(cast(Any, invalid))

    assert call_count == 0, "ValueError 시 키움 호출 안 함"


@pytest.mark.asyncio
async def test_fetch_sectors_rejects_non_digit_mrkt_tp() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"return_code": 0})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        with pytest.raises(ValueError):
            await adapter.fetch_sectors(cast(Any, "xxx"))


# -----------------------------------------------------------------------------
# 4. 페이지네이션
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_sectors_combines_paginated_responses() -> None:
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(
                200,
                json={
                    "return_code": 0,
                    "list": [
                        {"marketCode": "0", "code": "001", "name": "종합(KOSPI)", "group": "1"},
                        {"marketCode": "0", "code": "002", "name": "대형주", "group": "2"},
                    ],
                },
                headers={"cont-yn": "Y", "next-key": "page-2"},
            )
        return httpx.Response(
            200,
            json={
                "return_code": 0,
                "list": [
                    {"marketCode": "0", "code": "003", "name": "중형주", "group": "3"},
                ],
            },
            headers={"cont-yn": "N"},
        )

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        resp = await adapter.fetch_sectors("0")

    assert call_count == 2
    assert len(resp.items) == 3
    assert [r.code for r in resp.items] == ["001", "002", "003"]


# -----------------------------------------------------------------------------
# 5. 빈 list
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_sectors_empty_list_is_valid() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"return_code": 0, "list": []})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        resp = await adapter.fetch_sectors("7")

    assert resp.items == []
    assert resp.return_code == 0


# -----------------------------------------------------------------------------
# 6-7. 에러 전파
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_sectors_propagates_business_error() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"return_code": 1, "return_msg": "조회 실패"})

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        with pytest.raises(KiwoomBusinessError):
            await adapter.fetch_sectors("0")


@pytest.mark.asyncio
async def test_fetch_sectors_propagates_credential_rejected() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        with pytest.raises(KiwoomCredentialRejectedError):
            await adapter.fetch_sectors("0")


# -----------------------------------------------------------------------------
# 8. 응답 검증 실패
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_sectors_raises_validation_when_row_missing_code() -> None:
    """row 의 code 필드 누락 → KiwoomResponseValidationError (Pydantic).

    `__context__` 도 None — Pydantic ValidationError 가 row 평문 input 보존 차단 (C-1 일관).
    """

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "return_code": 0,
                "list": [
                    {"marketCode": "0", "name": "이름만"},  # code 누락
                ],
            },
        )

    async with _make_kiwoom_client(handler) as kc:
        adapter = KiwoomStkInfoClient(kc)
        with pytest.raises(KiwoomResponseValidationError) as exc_info:
            await adapter.fetch_sectors("0")

    err = exc_info.value
    assert err.__context__ is None, "Pydantic ValidationError context leak — except 밖 raise 회귀"
    assert err.__cause__ is None


# -----------------------------------------------------------------------------
# Pydantic 모델 단위
# -----------------------------------------------------------------------------


def test_sector_row_accepts_minimum_fields() -> None:
    row = SectorRow(marketCode="0", code="001", name="종합(KOSPI)")
    assert row.group == ""


def test_sector_row_extra_field_ignored() -> None:
    row = SectorRow.model_validate(
        {
            "marketCode": "0",
            "code": "001",
            "name": "종합",
            "group": "1",
            "future_field": "ignored",
        }
    )
    assert row.code == "001"


def test_sector_list_response_default_empty_list() -> None:
    resp = SectorListResponse.model_validate({"return_code": 0})
    assert resp.items == []


def test_sector_list_response_alias_list_supported() -> None:
    """JSON 키는 'list' (키움 응답 그대로) — alias 동작 검증."""
    resp = SectorListResponse.model_validate(
        {
            "list": [{"marketCode": "0", "code": "001", "name": "종합"}],
            "return_code": 0,
        }
    )
    assert len(resp.items) == 1
    assert resp.items[0].code == "001"


# -----------------------------------------------------------------------------
# M2 적대적 리뷰 — 어댑터 fetch_sectors 의 max_pages=20 동작 검증
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_sectors_propagates_max_pages_exceeded() -> None:
    """키움이 무한 cont-yn=Y 반환 시 어댑터 max_pages=20 도달 후 KiwoomMaxPagesExceededError."""
    from app.adapter.out.kiwoom._client import KiwoomMaxPagesExceededError

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
            await adapter.fetch_sectors("0")

    assert call_count == 20, "어댑터 max_pages=20 hard cap"
