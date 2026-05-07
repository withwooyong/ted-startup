"""KiwoomClient — 공통 트랜스포트 단위 테스트.

설계: master.md § 6.1 / 6.2 / 6.3 / 6.4.

httpx.MockTransport 주입으로 외부 호출 0. 시나리오:
1. 정상 호출 200 — body + headers + token_provider 호출
2. 헤더 자동 설정 (api-id / authorization / Content-Type / cont-yn / next-key)
3. cont_yn / next_key 응답 헤더 추출 → KiwoomResponse
4. 401/403 → KiwoomCredentialRejectedError (재시도 0회)
5. 429 → KiwoomRateLimitedError (재시도 후 fail)
6. 5xx → KiwoomUpstreamError (tenacity 재시도)
7. 네트워크 → KiwoomUpstreamError (재시도)
8. JSON 파싱 실패 → KiwoomUpstreamError
9. return_code != 0 → KiwoomBusinessError
10. call_paginated — 단일 페이지 (cont-yn=N)
11. call_paginated — 다중 페이지 (Y → N)
12. call_paginated — max_pages 한도 초과 → 도메인 예외
13. token_provider 매 호출 시 호출됨 (캐시 X — 캐시는 provider 책임)
14. 응답 본문 어떤 경로로도 logger 미전달 회귀
"""

from __future__ import annotations

import io
import logging
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.adapter.out.kiwoom._client import KiwoomClient, KiwoomMaxPagesExceededError, KiwoomResponse
from app.adapter.out.kiwoom._exceptions import (
    KiwoomBusinessError,
    KiwoomCredentialRejectedError,
    KiwoomRateLimitedError,
    KiwoomUpstreamError,
)
from app.observability.logging import reset_logging_for_tests, setup_logging


@pytest.fixture(autouse=True)
def _reset_logging() -> None:
    reset_logging_for_tests()


def _mock_transport(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


async def _const_token() -> str:
    return "FixedToken-" + "X" * 100


def _make_client(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    max_attempts: int = 3,
    concurrent_requests: int = 4,
    min_request_interval_seconds: float = 0.0,
) -> KiwoomClient:
    return KiwoomClient(
        base_url="https://api.kiwoom.com",
        token_provider=_const_token,
        transport=_mock_transport(handler),
        max_attempts=max_attempts,
        retry_min_wait=0.0,
        retry_max_wait=0.0,
        concurrent_requests=concurrent_requests,
        min_request_interval_seconds=min_request_interval_seconds,
    )


# -----------------------------------------------------------------------------
# 1. 정상 호출 + 헤더 자동 설정
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_returns_response_with_body_and_pagination_headers() -> None:
    captured_request: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["method"] = request.method
        captured_request["url"] = str(request.url)
        captured_request["headers"] = dict(request.headers)
        captured_request["body"] = request.content
        return httpx.Response(
            200,
            json={"return_code": 0, "data": "ok"},
            headers={"cont-yn": "Y", "next-key": "page-2"},
        )

    async with _make_client(handler) as client:
        resp = await client.call(
            api_id="ka10101",
            endpoint="/api/dostk/stkinfo",
            body={"mrkt_tp": "0"},
        )

    assert isinstance(resp, KiwoomResponse)
    assert resp.body == {"return_code": 0, "data": "ok"}
    assert resp.cont_yn == "Y"
    assert resp.next_key == "page-2"
    assert resp.status_code == 200

    # 헤더 자동 설정
    assert captured_request["headers"]["api-id"] == "ka10101"
    assert captured_request["headers"]["authorization"].startswith("Bearer ")
    assert captured_request["headers"]["content-type"].startswith("application/json")
    # 페이지네이션 헤더는 첫 호출엔 없음
    assert "cont-yn" not in captured_request["headers"] or captured_request["headers"]["cont-yn"] == ""


@pytest.mark.asyncio
async def test_call_passes_pagination_headers_when_provided() -> None:
    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(request.headers)
        return httpx.Response(200, json={"return_code": 0})

    async with _make_client(handler) as client:
        await client.call(
            api_id="ka10101",
            endpoint="/api/dostk/stkinfo",
            body={"mrkt_tp": "0"},
            cont_yn="Y",
            next_key="abc-123",
        )

    assert captured_headers["cont-yn"] == "Y"
    assert captured_headers["next-key"] == "abc-123"


@pytest.mark.asyncio
async def test_call_omits_pagination_headers_when_not_provided() -> None:
    captured_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_headers.update(request.headers)
        return httpx.Response(200, json={"return_code": 0})

    async with _make_client(handler) as client:
        await client.call(
            api_id="ka10101",
            endpoint="/api/dostk/stkinfo",
            body={"mrkt_tp": "0"},
        )

    assert "cont-yn" not in captured_headers
    assert "next-key" not in captured_headers


@pytest.mark.asyncio
async def test_call_returns_none_for_missing_pagination_headers() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"return_code": 0})

    async with _make_client(handler) as client:
        resp = await client.call(
            api_id="ka10101",
            endpoint="/api/dostk/stkinfo",
            body={"mrkt_tp": "0"},
        )

    assert resp.cont_yn is None
    assert resp.next_key is None


# -----------------------------------------------------------------------------
# 2. token_provider — 매 호출마다 호출됨
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_invokes_token_provider_each_call() -> None:
    """token_provider 는 KiwoomClient 가 매번 호출 — 캐시는 provider(TokenManager) 책임."""
    call_count = 0

    async def counting_provider() -> str:
        nonlocal call_count
        call_count += 1
        return f"Token-{call_count}"

    captured_tokens: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_tokens.append(request.headers["authorization"])
        return httpx.Response(200, json={"return_code": 0})

    client = KiwoomClient(
        base_url="https://api.kiwoom.com",
        token_provider=counting_provider,
        transport=_mock_transport(handler),
        max_attempts=1,
        retry_min_wait=0.0,
        retry_max_wait=0.0,
        min_request_interval_seconds=0.0,
    )
    async with client:
        await client.call(api_id="ka10101", endpoint="/x", body={})
        await client.call(api_id="ka10101", endpoint="/x", body={})
        await client.call(api_id="ka10101", endpoint="/x", body={})

    assert call_count == 3
    assert captured_tokens == ["Bearer Token-1", "Bearer Token-2", "Bearer Token-3"]


# -----------------------------------------------------------------------------
# 3. 401/403 → KiwoomCredentialRejectedError (재시도 X)
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_401_raises_credential_rejected_without_retry() -> None:
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(401)

    async with _make_client(handler, max_attempts=3) as client:
        with pytest.raises(KiwoomCredentialRejectedError):
            await client.call(api_id="ka10101", endpoint="/x", body={})

    assert call_count == 1, "401 은 재시도 없음"


@pytest.mark.asyncio
async def test_call_403_raises_credential_rejected_without_retry() -> None:
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(403)

    async with _make_client(handler, max_attempts=3) as client:
        with pytest.raises(KiwoomCredentialRejectedError):
            await client.call(api_id="ka10101", endpoint="/x", body={})

    assert call_count == 1


# -----------------------------------------------------------------------------
# 4. 429 → KiwoomRateLimitedError (재시도 후 fail)
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_429_retries_then_raises_rate_limited() -> None:
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(429)

    async with _make_client(handler, max_attempts=3) as client:
        with pytest.raises(KiwoomRateLimitedError):
            await client.call(api_id="ka10101", endpoint="/x", body={})

    assert call_count == 3, "429 는 tenacity 재시도 (RPS 회복 대기)"


# -----------------------------------------------------------------------------
# 5. 5xx + 네트워크 → KiwoomUpstreamError (재시도)
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_500_retries_then_raises_upstream() -> None:
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(500)

    async with _make_client(handler, max_attempts=3) as client:
        with pytest.raises(KiwoomUpstreamError):
            await client.call(api_id="ka10101", endpoint="/x", body={})

    assert call_count == 3


@pytest.mark.asyncio
async def test_call_network_error_retries_then_raises_upstream() -> None:
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        raise httpx.ConnectError("connection refused")

    async with _make_client(handler, max_attempts=3) as client:
        with pytest.raises(KiwoomUpstreamError):
            await client.call(api_id="ka10101", endpoint="/x", body={})

    assert call_count == 3


# -----------------------------------------------------------------------------
# 6. JSON 파싱 실패 → KiwoomUpstreamError
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_json_parse_failure_raises_upstream() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-a-json")

    async with _make_client(handler, max_attempts=1) as client:
        with pytest.raises(KiwoomUpstreamError):
            await client.call(api_id="ka10101", endpoint="/x", body={})


# -----------------------------------------------------------------------------
# 7. return_code != 0 → KiwoomBusinessError
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_business_error_on_nonzero_return_code() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"return_code": 7, "return_msg": "잘못된 요청"})

    async with _make_client(handler, max_attempts=1) as client:
        with pytest.raises(KiwoomBusinessError) as exc_info:
            await client.call(api_id="ka10101", endpoint="/x", body={})

    err = exc_info.value
    assert err.api_id == "ka10101"
    assert err.return_code == 7
    assert err.message == "잘못된 요청"


# -----------------------------------------------------------------------------
# 8. call_paginated — 단일 / 다중 페이지 / max_pages
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_paginated_single_page_when_no_cont_yn() -> None:
    """cont-yn 헤더 없거나 'N' → 1회 호출로 종료."""
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json={"return_code": 0, "data": "ok"})

    pages = []
    async with _make_client(handler, max_attempts=1) as client:
        async for page in client.call_paginated(
            api_id="ka10101",
            endpoint="/x",
            body={"mrkt_tp": "0"},
        ):
            pages.append(page)

    assert call_count == 1
    assert len(pages) == 1


@pytest.mark.asyncio
async def test_call_paginated_multiple_pages() -> None:
    """첫 응답 cont-yn=Y + next-key → 두 번째 호출 → 두 번째 응답 cont-yn=N → 종료."""
    call_count = 0
    captured_next_keys: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        captured_next_keys.append(request.headers.get("next-key", ""))
        if call_count == 1:
            return httpx.Response(
                200,
                json={"return_code": 0, "page": 1},
                headers={"cont-yn": "Y", "next-key": "key-2"},
            )
        return httpx.Response(
            200,
            json={"return_code": 0, "page": 2},
            headers={"cont-yn": "N"},
        )

    pages = []
    async with _make_client(handler, max_attempts=1) as client:
        async for page in client.call_paginated(
            api_id="ka10101",
            endpoint="/x",
            body={"mrkt_tp": "0"},
        ):
            pages.append(page)

    assert call_count == 2
    assert len(pages) == 2
    assert pages[0].body == {"return_code": 0, "page": 1}
    assert pages[1].body == {"return_code": 0, "page": 2}
    # 두 번째 호출은 next-key 헤더에 'key-2' 세팅
    assert captured_next_keys[0] == ""  # 첫 호출엔 next-key 없음
    assert captured_next_keys[1] == "key-2"


@pytest.mark.asyncio
async def test_call_paginated_raises_when_max_pages_exceeded() -> None:
    """무한 cont-yn=Y → max_pages 도달 시 KiwoomMaxPagesExceededError."""
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            200,
            json={"return_code": 0},
            headers={"cont-yn": "Y", "next-key": f"key-{call_count}"},
        )

    pages = []
    async with _make_client(handler, max_attempts=1) as client:
        with pytest.raises(KiwoomMaxPagesExceededError):
            async for page in client.call_paginated(
                api_id="ka10101",
                endpoint="/x",
                body={},
                max_pages=3,
            ):
                pages.append(page)

    assert call_count == 3, "max_pages 도달 시 그 이상 호출 안 함"


# -----------------------------------------------------------------------------
# 9. 응답 본문 logger 비전달 회귀
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_response_body_not_logged_on_401() -> None:
    """401 응답 본문이 어떤 경로로도 로그에 들어가지 않음 — α 정책 일관."""
    setup_logging(log_level="DEBUG", json_output=True)

    buf = io.StringIO()
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    for h in original_handlers:
        root.removeHandler(h)
    capture_handler = logging.StreamHandler(buf)
    if original_handlers:
        capture_handler.setFormatter(original_handlers[0].formatter)
    else:
        capture_handler.setFormatter(logging.Formatter())
    root.addHandler(capture_handler)

    leaky_token = "WQJCwyqInph" + "Z" * 140
    leaky_body = {"return_msg": f"이전: {leaky_token}", "return_code": 1}

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json=leaky_body)

    try:
        async with _make_client(handler, max_attempts=1) as client:
            with pytest.raises(KiwoomCredentialRejectedError):
                await client.call(api_id="ka10101", endpoint="/x", body={})
    finally:
        root.removeHandler(capture_handler)
        for h in original_handlers:
            root.addHandler(h)

    output = buf.getvalue()
    assert leaky_token not in output, "응답 본문이 로그에 노출됨 — KiwoomClient 회귀"


@pytest.mark.asyncio
async def test_call_business_error_message_does_not_leak_appkey() -> None:
    """KiwoomBusinessError str() 가 attacker-influenced return_msg 평문 미포함 (M1 정책 일관)."""
    leaky_msg = "appkey AppKey-LEAKY-12345 invalid"

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"return_code": 5, "return_msg": leaky_msg})

    async with _make_client(handler, max_attempts=1) as client:
        with pytest.raises(KiwoomBusinessError) as exc_info:
            await client.call(api_id="ka10101", endpoint="/x", body={})

    assert leaky_msg not in str(exc_info.value)
    assert "AppKey-LEAKY" not in str(exc_info.value)


# =============================================================================
# C-1 적대적 리뷰 — 토큰 헤더 인젝션 + __context__ leak 차단
# =============================================================================


@pytest.mark.asyncio
async def test_call_rejects_token_with_crlf_injection() -> None:
    """C-1: 토큰에 \\r\\n 가 들어가면 헤더 인젝션 → KiwoomCredentialRejectedError 즉시 fail.

    httpx h11 의 LocalProtocolError 가 토큰 평문을 메시지에 포함시키기 전 사전 검증 차단.
    """

    async def malicious_provider() -> str:
        return "Bearer-Injection\r\nX-Inject: evil"

    def handler(_req: httpx.Request) -> httpx.Response:
        # 도달 안 함
        return httpx.Response(200, json={"return_code": 0})

    client = KiwoomClient(
        base_url="https://api.kiwoom.com",
        token_provider=malicious_provider,
        transport=_mock_transport(handler),
        max_attempts=1,
        retry_min_wait=0.0,
        retry_max_wait=0.0,
        min_request_interval_seconds=0.0,
    )
    async with client:
        with pytest.raises(KiwoomCredentialRejectedError):
            await client.call(api_id="ka10101", endpoint="/x", body={})


@pytest.mark.asyncio
async def test_call_rejects_token_with_control_chars() -> None:
    """C-1: control character 토큰도 reject."""

    async def malicious_provider() -> str:
        return "Token-with-control-\x00-byte"

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"return_code": 0})

    client = KiwoomClient(
        base_url="https://api.kiwoom.com",
        token_provider=malicious_provider,
        transport=_mock_transport(handler),
        max_attempts=1,
        retry_min_wait=0.0,
        retry_max_wait=0.0,
        min_request_interval_seconds=0.0,
    )
    async with client:
        with pytest.raises(KiwoomCredentialRejectedError):
            await client.call(api_id="ka10101", endpoint="/x", body={})


@pytest.mark.asyncio
async def test_call_exception_context_is_cleared_on_network_error() -> None:
    """C-1: 네트워크 오류 wrap 시 `__context__` 가 None.

    `raise` 가 except 블록 밖에서 실행되도록 변수 캡처 패턴으로 리팩토링 — Python 자동
    `__context__` 설정 차단. Sentry/structlog 의 `walk_tb(__context__)` leak 차단.
    """

    def handler(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused: TOKEN_LEAK_HINT")

    async with _make_client(handler, max_attempts=1) as client:
        with pytest.raises(KiwoomUpstreamError) as exc_info:
            await client.call(api_id="ka10101", endpoint="/x", body={})

    err = exc_info.value
    assert err.__cause__ is None
    assert err.__context__ is None, "__context__ leak — except 밖 raise 패턴 회귀"
    # __context__ 가 None 이면 __suppress_context__ 값은 의미 없음 (suppress 할 대상 없음)


@pytest.mark.asyncio
async def test_call_exception_context_is_cleared_on_401() -> None:
    """C-1: 401 raise 시도 __context__ 정리 — 일관 정책."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"return_msg": "leaked-context-marker"})

    async with _make_client(handler, max_attempts=1) as client:
        with pytest.raises(KiwoomCredentialRejectedError) as exc_info:
            await client.call(api_id="ka10101", endpoint="/x", body={})

    err = exc_info.value
    assert err.__context__ is None
    assert err.__cause__ is None


# =============================================================================
# H-1 적대적 리뷰 — cont-yn / next-key 헤더 인젝션 차단
# =============================================================================


@pytest.mark.asyncio
async def test_call_rejects_invalid_cont_yn_value() -> None:
    """caller 가 잘못된 cont_yn 전달 시 fail-fast (헤더 인젝션 방어)."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"return_code": 0})

    async with _make_client(handler, max_attempts=1) as client:
        with pytest.raises(KiwoomUpstreamError):
            await client.call(
                api_id="ka10101",
                endpoint="/x",
                body={},
                cont_yn="Y\r\nX-Inject: evil",
            )


@pytest.mark.asyncio
async def test_call_rejects_next_key_with_crlf() -> None:
    """next_key 의 헤더 인젝션 차단."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"return_code": 0})

    async with _make_client(handler, max_attempts=1) as client:
        with pytest.raises(KiwoomUpstreamError):
            await client.call(
                api_id="ka10101",
                endpoint="/x",
                body={},
                next_key="abc\r\nAuthorization: Bearer evil",
            )


@pytest.mark.asyncio
async def test_call_rejects_response_cont_yn_invalid() -> None:
    """키움 응답의 cont-yn 헤더가 잘못된 값이면 reject — 다음 호출 헤더 인젝션 차단."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"return_code": 0},
            headers={"cont-yn": "X-Injected"},
        )

    async with _make_client(handler, max_attempts=1) as client:
        with pytest.raises(KiwoomUpstreamError):
            await client.call(api_id="ka10101", endpoint="/x", body={})


# =============================================================================
# M2 적대적 리뷰 — 어댑터 max_pages 회귀
# =============================================================================


@pytest.mark.asyncio
async def test_paginated_max_pages_3_via_client() -> None:
    """KiwoomClient.call_paginated max_pages 동작 단독 테스트."""
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            200,
            json={"return_code": 0},
            headers={"cont-yn": "Y", "next-key": f"k-{call_count}"},
        )

    async with _make_client(handler, max_attempts=1) as client:
        with pytest.raises(KiwoomMaxPagesExceededError):
            async for _page in client.call_paginated(api_id="ka10101", endpoint="/x", body={}, max_pages=2):
                pass

    assert call_count == 2
