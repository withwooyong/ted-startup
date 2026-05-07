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


# =============================================================================
# au10002 — revoke_token (β chunk)
# =============================================================================


@pytest.mark.asyncio
async def test_revoke_token_returns_response_on_200() -> None:
    """정상 폐기 — 200 + return_code=0."""
    captured_body: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/oauth2/revoke"
        captured_body.update(json.loads(request.content))
        assert request.headers["api-id"] == "au10002"
        assert request.headers["authorization"] == f"Bearer {'X' * 100}"
        return httpx.Response(200, json={"return_code": 0, "return_msg": "정상적으로 처리되었습니다"})

    async with KiwoomAuthClient(base_url="https://api.kiwoom.com", transport=_mock_transport(handler)) as client:
        from app.adapter.out.kiwoom.auth import TokenRevokeResponse

        resp = await client.revoke_token(_VALID_CREDS, "X" * 100)

    assert isinstance(resp, TokenRevokeResponse)
    assert resp.succeeded is True
    # body 에 appkey + secretkey + token 3개 모두 포함 (au10002 § 3.1)
    assert captured_body["appkey"] == _VALID_CREDS.appkey
    assert captured_body["secretkey"] == _VALID_CREDS.secretkey
    assert captured_body["token"] == "X" * 100
    # grant_type 은 없음 (au10001 과의 차이)
    assert "grant_type" not in captured_body


@pytest.mark.asyncio
async def test_revoke_token_401_raises_credential_rejected_without_retry() -> None:
    """이미 만료된 토큰 폐기 — 401, 재시도 0회. UseCase 가 idempotent 변환 책임."""
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(401)

    async with KiwoomAuthClient(base_url="https://api.kiwoom.com", transport=_mock_transport(handler)) as client:
        with pytest.raises(KiwoomCredentialRejectedError):
            await client.revoke_token(_VALID_CREDS, "X" * 100)

    assert call_count == 1, "401 은 재시도 없음"


@pytest.mark.asyncio
async def test_revoke_token_403_raises_credential_rejected_without_retry() -> None:
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(403)

    async with KiwoomAuthClient(base_url="https://api.kiwoom.com", transport=_mock_transport(handler)) as client:
        with pytest.raises(KiwoomCredentialRejectedError):
            await client.revoke_token(_VALID_CREDS, "X" * 100)

    assert call_count == 1, "403 은 재시도 없음"


@pytest.mark.asyncio
async def test_revoke_token_500_does_not_retry() -> None:
    """폐기는 best-effort — 5xx 도 재시도 0회 (계획 §6.1: 재시도 없음 의도)."""
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(500)

    async with KiwoomAuthClient(base_url="https://api.kiwoom.com", transport=_mock_transport(handler)) as client:
        with pytest.raises(KiwoomUpstreamError):
            await client.revoke_token(_VALID_CREDS, "X" * 100)

    assert call_count == 1, "revoke 는 5xx 도 재시도 없음 — caller best-effort 결정"


@pytest.mark.asyncio
async def test_revoke_token_business_error_excludes_message_in_str() -> None:
    """200 + return_code != 0 → KiwoomBusinessError. message attribute only (M1)."""
    leaky_msg = "appkey AppKey-LEAKY rejected"

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"return_code": 5, "return_msg": leaky_msg})

    async with KiwoomAuthClient(base_url="https://api.kiwoom.com", transport=_mock_transport(handler)) as client:
        with pytest.raises(KiwoomBusinessError) as exc_info:
            await client.revoke_token(_VALID_CREDS, "X" * 100)

    err = exc_info.value
    assert err.api_id == "au10002"
    assert err.return_code == 5
    assert err.message == leaky_msg
    assert leaky_msg not in str(err)
    assert "AppKey-LEAKY" not in str(err)


@pytest.mark.asyncio
async def test_revoke_token_response_body_not_logged_at_all_on_401() -> None:
    """401 응답 본문이 어떤 경로로도 로그에 포함 안 됨 — au10002 도 동일 정책."""
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

    leaky_token = "WQJCwyqInph" + "Y" * 140  # Kiwoom 평문 토큰 모양
    leaky = {"return_msg": f"이전 토큰: {leaky_token}", "return_code": 1, "token": leaky_token}

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json=leaky)

    try:
        async with KiwoomAuthClient(base_url="https://api.kiwoom.com", transport=_mock_transport(handler)) as client:
            with pytest.raises(KiwoomCredentialRejectedError):
                await client.revoke_token(_VALID_CREDS, leaky_token)
    finally:
        root.removeHandler(capture_handler)
        for h in original_handlers:
            root.addHandler(h)

    output = buf.getvalue()
    assert leaky_token not in output, "au10002 응답 본문이 로그에 노출됨 — 마스킹 회귀"


@pytest.mark.asyncio
async def test_revoke_token_network_error_raises_upstream() -> None:
    """네트워크 오류 → KiwoomUpstreamError, 재시도 없음 (best-effort)."""
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        raise httpx.ConnectError("connection refused")

    async with KiwoomAuthClient(base_url="https://api.kiwoom.com", transport=_mock_transport(handler)) as client:
        with pytest.raises(KiwoomUpstreamError):
            await client.revoke_token(_VALID_CREDS, "X" * 100)

    assert call_count == 1


def test_token_revoke_request_repr_masks_secrets() -> None:
    """TokenRevokeRequest __repr__ 가 secretkey/token 마스킹."""
    from app.adapter.out.kiwoom.auth import TokenRevokeRequest

    req = TokenRevokeRequest(
        appkey="A" * 32,
        secretkey="REAL-SECRET-VALUE-1234567890",
        token="REAL-TOKEN-VALUE-1234567890",
    )
    rep = repr(req)
    assert "REAL-SECRET-VALUE" not in rep
    assert "REAL-TOKEN-VALUE" not in rep
    assert "<masked>" in rep


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


# =============================================================================
# F1 백포트 — `__context__` leak 차단 회귀 (A3-α C-1 패턴 일관)
# =============================================================================
#
# `from None` 은 `__suppress_context__=True` 만 set, `__context__` 는 currently-raised
# exception 으로 자동 채워져 Sentry/structlog `walk_tb(__context__)` 가 토큰 평문 노출 가능.
# 변수 캡처 + except 밖 raise 패턴으로 PEP 3134 자동 chaining 차단.
# 모든 raise 사이트에서 __context__ 와 __cause__ 둘 다 None 인지 확인.


@pytest.mark.asyncio
async def test_issue_token_network_error_context_is_cleared() -> None:
    """F1: au10001 네트워크 오류 wrap 시 `__context__` 가 None.

    httpx.ConnectError 메시지에 토큰 평문 포함 가능성 — `__context__` leak 시 Sentry
    `walk_tb` 가 노출.
    """

    def handler(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused: TOKEN_LEAK_HINT")

    client = KiwoomAuthClient(
        base_url="https://api.kiwoom.com",
        transport=_mock_transport(handler),
        max_attempts=1,
        retry_min_wait=0.0,
        retry_max_wait=0.0,
    )
    async with client:
        with pytest.raises(KiwoomUpstreamError) as exc_info:
            await client.issue_token(_VALID_CREDS)

    err = exc_info.value
    assert err.__cause__ is None
    assert err.__context__ is None, "au10001 network error __context__ leak — F1 회귀"


@pytest.mark.asyncio
async def test_issue_token_401_context_is_cleared() -> None:
    """F1: au10001 401 raise 시도 `__context__` 정리 (자격증명 거부 — chain 없음 보장)."""

    def handler(_req: httpx.Request) -> httpx.Response:
        # body 에 토큰 평문 흉내 — context 로 leak 안 되어야 함
        return httpx.Response(401, json={"return_msg": "leaked-context-marker"})

    client = KiwoomAuthClient(
        base_url="https://api.kiwoom.com",
        transport=_mock_transport(handler),
        max_attempts=1,
        retry_min_wait=0.0,
        retry_max_wait=0.0,
    )
    async with client:
        with pytest.raises(KiwoomCredentialRejectedError) as exc_info:
            await client.issue_token(_VALID_CREDS)

    err = exc_info.value
    assert err.__cause__ is None
    assert err.__context__ is None


@pytest.mark.asyncio
async def test_issue_token_json_parse_error_context_is_cleared() -> None:
    """F1: au10001 JSON 파싱 실패 시 `__context__` 가 None.

    ValueError 메시지가 본문 일부를 포함할 수 있어 chain leak 시 위험.
    """

    def handler(_req: httpx.Request) -> httpx.Response:
        # 200 + 비-JSON 본문 → resp.json() ValueError
        return httpx.Response(200, content=b"not-json-{TOKEN_LEAK_HINT}")

    client = KiwoomAuthClient(
        base_url="https://api.kiwoom.com",
        transport=_mock_transport(handler),
        max_attempts=1,
        retry_min_wait=0.0,
        retry_max_wait=0.0,
    )
    async with client:
        with pytest.raises(KiwoomUpstreamError) as exc_info:
            await client.issue_token(_VALID_CREDS)

    err = exc_info.value
    assert err.__cause__ is None
    assert err.__context__ is None, "au10001 JSON parse error __context__ leak — F1 회귀"


@pytest.mark.asyncio
async def test_issue_token_pydantic_validation_error_context_is_cleared() -> None:
    """F1: au10001 응답 Pydantic 검증 실패 시 `__context__` 가 None.

    ValidationError.errors() 의 `input` 에 토큰 평문이 보존됨 → chain leak 차단 핵심.
    """

    def handler(_req: httpx.Request) -> httpx.Response:
        # return_code=0 통과 + 필수 필드 누락 → Pydantic 검증 실패
        return httpx.Response(200, json={"return_code": 0, "expires_dt": "INVALID"})

    client = KiwoomAuthClient(
        base_url="https://api.kiwoom.com",
        transport=_mock_transport(handler),
        max_attempts=1,
        retry_min_wait=0.0,
        retry_max_wait=0.0,
    )
    async with client:
        with pytest.raises(KiwoomResponseValidationError) as exc_info:
            await client.issue_token(_VALID_CREDS)

    err = exc_info.value
    assert err.__cause__ is None
    assert err.__context__ is None, "au10001 ValidationError __context__ leak — F1 회귀 핵심"


def test_expires_at_kst_invalid_date_context_is_cleared() -> None:
    """F1: TokenIssueResponse.expires_at_kst() 의 strptime ValueError 매핑 시 `__context__` None.

    `99991399999999` 같은 regex 통과하지만 논리상 잘못된 날짜에 대해 chain 차단.
    """
    # regex `^\d{14}$` 통과 + strptime 실패 케이스
    resp = TokenIssueResponse(
        expires_dt="99991399999999",
        token_type="bearer",
        token="X" * 100,
        return_code=0,
        return_msg="",
    )

    with pytest.raises(KiwoomResponseValidationError) as exc_info:
        resp.expires_at_kst()

    err = exc_info.value
    assert err.__cause__ is None
    assert err.__context__ is None, "expires_at_kst ValueError __context__ leak — F1 회귀"


@pytest.mark.asyncio
async def test_revoke_token_network_error_context_is_cleared() -> None:
    """F1: au10002 네트워크 오류 wrap 시 `__context__` 가 None.

    revoke 는 헤더에 Bearer 토큰 평문 — exc 메시지에 포함될 수 있어 chain 차단 필수.
    """

    def handler(_req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused: BEARER_TOKEN_HINT")

    client = KiwoomAuthClient(
        base_url="https://api.kiwoom.com",
        transport=_mock_transport(handler),
        max_attempts=1,
        retry_min_wait=0.0,
        retry_max_wait=0.0,
    )
    async with client:
        with pytest.raises(KiwoomUpstreamError) as exc_info:
            await client.revoke_token(_VALID_CREDS, "X" * 100)

    err = exc_info.value
    assert err.__cause__ is None
    assert err.__context__ is None, "au10002 network error __context__ leak — F1 회귀"


@pytest.mark.asyncio
async def test_revoke_token_401_context_is_cleared() -> None:
    """F1: au10002 401 raise 시도 `__context__` 정리."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"return_msg": "leaked-context-marker"})

    client = KiwoomAuthClient(
        base_url="https://api.kiwoom.com",
        transport=_mock_transport(handler),
        max_attempts=1,
        retry_min_wait=0.0,
        retry_max_wait=0.0,
    )
    async with client:
        with pytest.raises(KiwoomCredentialRejectedError) as exc_info:
            await client.revoke_token(_VALID_CREDS, "X" * 100)

    err = exc_info.value
    assert err.__cause__ is None
    assert err.__context__ is None


@pytest.mark.asyncio
async def test_revoke_token_json_parse_error_context_is_cleared() -> None:
    """F1: au10002 JSON 파싱 실패 시 `__context__` 가 None."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json-{TOKEN_LEAK_HINT}")

    client = KiwoomAuthClient(
        base_url="https://api.kiwoom.com",
        transport=_mock_transport(handler),
        max_attempts=1,
        retry_min_wait=0.0,
        retry_max_wait=0.0,
    )
    async with client:
        with pytest.raises(KiwoomUpstreamError) as exc_info:
            await client.revoke_token(_VALID_CREDS, "X" * 100)

    err = exc_info.value
    assert err.__cause__ is None
    assert err.__context__ is None, "au10002 JSON parse error __context__ leak — F1 회귀"
