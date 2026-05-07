"""KiwoomAuthClient.issue_token (au10001) — Adapter 단위 테스트.

httpx.MockTransport 주입으로 외부 호출 0. 9개 시나리오:
1. 200 정상 발급 → TokenIssueResponse 반환
2. 200 + return_code != 0 → KiwoomBusinessError
3. 200 + token 빈 문자열 → KiwoomResponseValidationError (Pydantic)
4. 200 + expires_dt 형식 오류 → KiwoomResponseValidationError
5. 401 → KiwoomCredentialRejectedError (재시도 0회)
6. 403 → KiwoomCredentialRejectedError (재시도 0회)
7. 500 → tenacity 재시도 후 KiwoomUpstreamError
8. 네트워크 오류 → tenacity 재시도 후 KiwoomUpstreamError
9. 응답 본문 디버그 로그 마스킹 회귀
"""

from __future__ import annotations

import io
import json
import logging
from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.adapter.out.kiwoom._exceptions import (
    KiwoomBusinessError,
    KiwoomCredentialRejectedError,
    KiwoomResponseValidationError,
    KiwoomUpstreamError,
)
from app.adapter.out.kiwoom.auth import KiwoomAuthClient, TokenIssueResponse
from app.application.dto.kiwoom_auth import KiwoomCredentials
from app.observability.logging import reset_logging_for_tests, setup_logging

KST = ZoneInfo("Asia/Seoul")

_VALID_TOKEN_BODY = {
    "expires_dt": "20260507083713",
    "token_type": "bearer",
    "token": "X" * 150,
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다",
}

_VALID_CREDS = KiwoomCredentials(
    appkey="AxserEsdcredca12345678",
    secretkey="SEefdcwcforehDre2fdvc12345678",
)


def _mock_transport(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.MockTransport:
    """MockTransport 헬퍼."""
    return httpx.MockTransport(handler)


@pytest.fixture(autouse=True)
def _reset_logging() -> None:
    reset_logging_for_tests()


# -----------------------------------------------------------------------------
# 1. 정상 발급
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issue_token_returns_response_on_200() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/oauth2/token"
        body = json.loads(request.content)
        assert body == {
            "grant_type": "client_credentials",
            "appkey": _VALID_CREDS.appkey,
            "secretkey": _VALID_CREDS.secretkey,
        }
        assert request.headers["api-id"] == "au10001"
        assert request.headers["content-type"].startswith("application/json")
        return httpx.Response(200, json=_VALID_TOKEN_BODY)

    async with KiwoomAuthClient(base_url="https://api.kiwoom.com", transport=_mock_transport(handler)) as client:
        resp = await client.issue_token(_VALID_CREDS)

    assert isinstance(resp, TokenIssueResponse)
    assert resp.token == "X" * 150
    assert resp.token_type == "bearer"
    assert resp.expires_dt == "20260507083713"
    assert resp.return_code == 0


@pytest.mark.asyncio
async def test_issue_token_response_expires_at_kst_is_tz_aware() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_VALID_TOKEN_BODY)

    async with KiwoomAuthClient(base_url="https://api.kiwoom.com", transport=_mock_transport(handler)) as client:
        resp = await client.issue_token(_VALID_CREDS)

    expires = resp.expires_at_kst()
    assert isinstance(expires, datetime)
    assert expires.tzinfo is not None
    assert expires == datetime(2026, 5, 7, 8, 37, 13, tzinfo=KST)


# -----------------------------------------------------------------------------
# 2. return_code != 0 → KiwoomBusinessError
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issue_token_raises_business_error_on_nonzero_return_code() -> None:
    body = {**_VALID_TOKEN_BODY, "return_code": 7, "return_msg": "잘못된 요청"}

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    async with KiwoomAuthClient(base_url="https://api.kiwoom.com", transport=_mock_transport(handler)) as client:
        with pytest.raises(KiwoomBusinessError) as exc_info:
            await client.issue_token(_VALID_CREDS)

    err = exc_info.value
    assert err.api_id == "au10001"
    assert err.return_code == 7
    assert "잘못된 요청" in err.message


# -----------------------------------------------------------------------------
# 3-4. Pydantic 검증 실패 → KiwoomResponseValidationError
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issue_token_raises_validation_error_on_empty_token() -> None:
    body = {**_VALID_TOKEN_BODY, "token": ""}

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    async with KiwoomAuthClient(base_url="https://api.kiwoom.com", transport=_mock_transport(handler)) as client:
        with pytest.raises(KiwoomResponseValidationError):
            await client.issue_token(_VALID_CREDS)


@pytest.mark.asyncio
async def test_issue_token_raises_validation_error_on_malformed_expires_dt() -> None:
    body = {**_VALID_TOKEN_BODY, "expires_dt": "abcd"}

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    async with KiwoomAuthClient(base_url="https://api.kiwoom.com", transport=_mock_transport(handler)) as client:
        with pytest.raises(KiwoomResponseValidationError):
            await client.issue_token(_VALID_CREDS)


# -----------------------------------------------------------------------------
# 5-6. 401/403 → KiwoomCredentialRejectedError (재시도 금지)
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issue_token_401_raises_credential_rejected_without_retry() -> None:
    """401 은 자격증명 무차별 시도 timing leak 방지 — 재시도 0회."""
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(401, json={"return_code": 1, "return_msg": "인증 실패"})

    async with KiwoomAuthClient(base_url="https://api.kiwoom.com", transport=_mock_transport(handler)) as client:
        with pytest.raises(KiwoomCredentialRejectedError) as exc_info:
            await client.issue_token(_VALID_CREDS)

    assert call_count == 1, "401 은 재시도하면 안 됨"
    assert "401" in str(exc_info.value)


@pytest.mark.asyncio
async def test_issue_token_403_raises_credential_rejected_without_retry() -> None:
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(403, json={"return_code": 1})

    async with KiwoomAuthClient(base_url="https://api.kiwoom.com", transport=_mock_transport(handler)) as client:
        with pytest.raises(KiwoomCredentialRejectedError):
            await client.issue_token(_VALID_CREDS)

    assert call_count == 1, "403 은 재시도하면 안 됨"


@pytest.mark.asyncio
async def test_issue_token_credential_rejected_message_does_not_leak_body() -> None:
    """401 응답 본문에 자격증명 힌트 (메시지에 appkey 일부) 포함 시 예외 메시지로 누설 금지."""
    leaky_body = {"return_msg": "key=AxserEsdcredca-leaked", "return_code": 1}

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json=leaky_body)

    async with KiwoomAuthClient(base_url="https://api.kiwoom.com", transport=_mock_transport(handler)) as client:
        with pytest.raises(KiwoomCredentialRejectedError) as exc_info:
            await client.issue_token(_VALID_CREDS)

    assert "AxserEsdcredca-leaked" not in str(exc_info.value)


# -----------------------------------------------------------------------------
# 7-8. 5xx + 네트워크 오류 → 재시도 후 KiwoomUpstreamError
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issue_token_500_retries_then_raises_upstream() -> None:
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(500)

    async with KiwoomAuthClient(
        base_url="https://api.kiwoom.com",
        transport=_mock_transport(handler),
        # tenacity wait 단축 (테스트 속도)
        max_attempts=3,
        retry_min_wait=0.0,
        retry_max_wait=0.0,
    ) as client:
        with pytest.raises(KiwoomUpstreamError):
            await client.issue_token(_VALID_CREDS)

    assert call_count == 3, "5xx 는 tenacity 가 3회 재시도"


@pytest.mark.asyncio
async def test_issue_token_network_error_retries_then_raises_upstream() -> None:
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        raise httpx.ConnectError("connection refused")

    async with KiwoomAuthClient(
        base_url="https://api.kiwoom.com",
        transport=_mock_transport(handler),
        max_attempts=3,
        retry_min_wait=0.0,
        retry_max_wait=0.0,
    ) as client:
        with pytest.raises(KiwoomUpstreamError):
            await client.issue_token(_VALID_CREDS)

    assert call_count == 3


# -----------------------------------------------------------------------------
# 9. 응답 본문 마스킹 회귀
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issue_token_response_body_not_logged_at_all_on_401() -> None:
    """401 응답 본문 자체가 로그에 들어가지 않음 — 마스킹 의존 없이 fail-closed.

    Kiwoom 토큰은 plain alphanumeric (eyJ prefix 없음, hex 아님) 이라 JWT/HEX 패턴
    매칭으로 마스킹 안 됨. _KIWOOM_SECRET_PATTERN 도 prefix 없이 평문 임베딩 시 미매칭.
    → 본문 자체를 log message 에 넣지 않는 것이 유일한 보장.
    """
    setup_logging(log_level="DEBUG", json_output=True)

    buf = io.StringIO()
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    for h in original_handlers:
        root.removeHandler(h)
    capture_handler = logging.StreamHandler(buf)
    # original_handlers 가 비어있을 가능성 가드 (test_kiwoom_auth_client.py:272 1차 리뷰 fragile)
    if original_handlers:
        capture_handler.setFormatter(original_handlers[0].formatter)
    else:
        capture_handler.setFormatter(logging.Formatter())
    root.addHandler(capture_handler)

    leaky_token = "WQJCwyqInph" + "X" * 140  # Kiwoom 평문 토큰 모양 — prefix 없음, hex 아님
    leaky = {
        "return_msg": f"이전 토큰: {leaky_token}",
        "return_code": 1,
        "token": leaky_token,
    }

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json=leaky)

    try:
        async with KiwoomAuthClient(base_url="https://api.kiwoom.com", transport=_mock_transport(handler)) as client:
            with pytest.raises(KiwoomCredentialRejectedError):
                await client.issue_token(_VALID_CREDS)
    finally:
        root.removeHandler(capture_handler)
        for h in original_handlers:
            root.addHandler(h)

    output = buf.getvalue()
    assert leaky_token not in output, "Kiwoom 평문 토큰이 로그에 노출됨 — 본문은 어떤 경로로도 logger 에 전달 금지"


# -----------------------------------------------------------------------------
# H3 — 429 timing oracle 방어: 재시도 금지
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issue_token_429_does_not_retry() -> None:
    """429 RateLimited 도 재시도 금지 — timing oracle 방어 (적대적 리뷰 H3)."""
    from app.adapter.out.kiwoom._exceptions import KiwoomRateLimitedError

    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(429)

    async with KiwoomAuthClient(
        base_url="https://api.kiwoom.com",
        transport=_mock_transport(handler),
        max_attempts=3,
        retry_min_wait=0.0,
        retry_max_wait=0.0,
    ) as client:
        with pytest.raises(KiwoomRateLimitedError):
            await client.issue_token(_VALID_CREDS)

    assert call_count == 1, "429 는 timing oracle 방어 위해 재시도 금지"


# -----------------------------------------------------------------------------
# M1 — KiwoomBusinessError __str__ 가 attacker-influenced message 미노출
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_business_error_str_excludes_upstream_message() -> None:
    """`str(exc)` 에 Kiwoom return_msg 평문 미포함 — attacker-influenced 차단 (M1)."""
    leaky_msg = "appkey AppKey-LEAKY-12345678 rejected by upstream"

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={**_VALID_TOKEN_BODY, "return_code": 9999, "return_msg": leaky_msg})

    async with KiwoomAuthClient(base_url="https://api.kiwoom.com", transport=_mock_transport(handler)) as client:
        with pytest.raises(KiwoomBusinessError) as exc_info:
            await client.issue_token(_VALID_CREDS)

    err = exc_info.value
    # __str__ / args[0] 에 leaky message 미포함
    assert leaky_msg not in str(err)
    assert "AppKey-LEAKY" not in str(err)
    # message 는 attribute 로만 접근 가능
    assert err.message == leaky_msg


# -----------------------------------------------------------------------------
# M2 — expires_at_kst 잘못된 날짜 → 도메인 예외 매핑
# -----------------------------------------------------------------------------


def test_expires_at_kst_invalid_date_raises_domain_error() -> None:
    """regex 통과 + strptime 실패 (99991399999999) → KiwoomResponseValidationError."""
    resp = TokenIssueResponse(
        expires_dt="99991399999999",  # regex `^\d{14}$` 통과, strptime 실패
        token_type="bearer",
        token="X" * 100,
        return_code=0,
        return_msg="",
    )
    with pytest.raises(KiwoomResponseValidationError):
        resp.expires_at_kst()


# -----------------------------------------------------------------------------
# Pydantic 모델 단위 (TokenIssueResponse)
# -----------------------------------------------------------------------------


def test_token_issue_response_repr_masks_token() -> None:
    resp = TokenIssueResponse(
        expires_dt="20260507083713",
        token_type="bearer",
        token="X" * 100,
        return_code=0,
        return_msg="ok",
    )
    rep = repr(resp)
    assert "X" * 100 not in rep
    assert "<masked>" in rep


def test_token_issue_response_expires_at_kst() -> None:
    resp = TokenIssueResponse(
        expires_dt="20260507083713",
        token_type="bearer",
        token="X" * 100,
        return_code=0,
        return_msg="",
    )
    expires = resp.expires_at_kst()
    assert expires == datetime(2026, 5, 7, 8, 37, 13, tzinfo=KST)


def test_token_issue_response_extra_field_ignored() -> None:
    """키움 응답에 신규 필드 추가 시 호환 — extra='ignore'."""
    resp = TokenIssueResponse.model_validate({**_VALID_TOKEN_BODY, "new_kiwoom_field": "future"})
    assert resp.token == _VALID_TOKEN_BODY["token"]
