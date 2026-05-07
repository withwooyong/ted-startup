"""raw_response 저장 직전 토큰 평문 필드 제거 — scrub_token_fields helper 검증.

ADR-0001 § 3 #3: au10001 / au10002 응답이 raw_response.response_payload (JSONB) 에
평문으로 들어가지 않도록 UseCase 직전 단계에서 token/expires_dt 필드를 [SCRUBBED] 로 치환.

원본 dict 는 변경하지 않고 (immutable 의미론) 새 dict 반환 — 호출자가 토큰을 다른 경로로 사용 가능.
"""

from __future__ import annotations

import pytest

from app.security.scrub import scrub_token_fields

# -----------------------------------------------------------------------------
# au10001 (issue token) — token / expires_dt 둘 다 제거
# -----------------------------------------------------------------------------


def test_scrub_au10001_removes_token() -> None:
    payload = {
        "return_code": 0,
        "return_msg": "정상적으로 처리되었습니다",
        "token": "WQJCwyqInphKnR3bSRtB9NE1lvDvBiU1OQHX0nVzPJpd4ABCDE",
        "token_type": "bearer",
        "expires_dt": "20260508090000",
    }
    scrubbed = scrub_token_fields(payload, api_id="au10001")
    assert scrubbed["token"] == "[SCRUBBED]"
    assert scrubbed["expires_dt"] == "[SCRUBBED]"
    assert scrubbed["token_type"] == "bearer"
    assert scrubbed["return_code"] == 0
    assert scrubbed["return_msg"] == "정상적으로 처리되었습니다"


def test_scrub_au10001_does_not_mutate_original() -> None:
    """원본 dict 보존 — caller 가 token 을 다른 경로로 사용 가능."""
    payload = {"token": "REAL-TOKEN-VALUE", "expires_dt": "20260508090000"}
    original_copy = dict(payload)
    _ = scrub_token_fields(payload, api_id="au10001")
    assert payload == original_copy


def test_scrub_au10001_returns_new_dict() -> None:
    payload = {"token": "x", "expires_dt": "y"}
    scrubbed = scrub_token_fields(payload, api_id="au10001")
    assert scrubbed is not payload


def test_scrub_au10001_handles_missing_fields() -> None:
    """token 만 있고 expires_dt 없는 비정상 응답도 안전 처리."""
    payload = {"token": "x", "return_code": 0}
    scrubbed = scrub_token_fields(payload, api_id="au10001")
    assert scrubbed["token"] == "[SCRUBBED]"
    assert "expires_dt" not in scrubbed


# -----------------------------------------------------------------------------
# au10002 (revoke token) — request body 의 token 필드 제거 (응답에는 token 없음)
# -----------------------------------------------------------------------------


def test_scrub_au10002_removes_token_appkey_secretkey() -> None:
    """au10002 (revoke) request body 는 appkey/secretkey/token **모두 평문 포함** —
    적대적 리뷰 (CRITICAL-3) 반영: raw_response.request_payload JSONB 평문 저장 차단."""
    payload = {
        "token": "REAL-TOKEN-TO-REVOKE",
        "appkey": "REAL-APPKEY-VALUE",
        "secretkey": "REAL-SECRET-VALUE",
        "grant_type": "client_credentials",
    }
    scrubbed = scrub_token_fields(payload, api_id="au10002")
    assert scrubbed["token"] == "[SCRUBBED]"
    assert scrubbed["appkey"] == "[SCRUBBED]"
    assert scrubbed["secretkey"] == "[SCRUBBED]"
    assert scrubbed["grant_type"] == "client_credentials"  # 비밀 아님 — 보존


def test_scrub_au10002_response_with_no_token_unchanged() -> None:
    """au10002 정상 응답 — token 키 없으면 그대로 통과 (return_code/return_msg 보존)."""
    payload = {"return_code": 0, "return_msg": "정상적으로 처리되었습니다"}
    scrubbed = scrub_token_fields(payload, api_id="au10002")
    assert scrubbed == payload


# -----------------------------------------------------------------------------
# 다른 api_id (ka10081 등) — 이 helper 의 책임 영역 밖, 그대로 통과
# -----------------------------------------------------------------------------


def test_scrub_non_auth_api_does_not_remove_token_field() -> None:
    """ka10081 (일봉) 같은 비인증 endpoint 는 token 필드 자체가 없음.
    혹시 token 키가 있어도 인증 엔드포인트가 아니면 패스 (다른 의미일 가능성)."""
    payload = {"stock_code": "005930", "token": "non-auth-context"}
    scrubbed = scrub_token_fields(payload, api_id="ka10081")
    assert scrubbed == payload  # 원본 그대로


def test_scrub_unknown_non_auth_api_passes_through() -> None:
    """비인증 api_id (`ka_unknown`) 는 통과 — token scrub 책임 영역 외."""
    payload = {"foo": "bar", "token": "x"}
    scrubbed = scrub_token_fields(payload, api_id="ka_unknown")
    assert scrubbed == payload


def test_scrub_unknown_auth_api_raises() -> None:
    """인증 endpoint(au*) 미등록 시 fail-closed — 적대적 리뷰 HIGH-1 반영.

    caller 의 api_id 오타(`au1001`)나 신규 endpoint 누락 시 silent passthrough 차단.
    """
    with pytest.raises(ValueError, match="unknown.*api_id|미등록"):
        scrub_token_fields({"token": "x"}, api_id="au10003")  # 미등록 인증 endpoint


def test_scrub_api_id_normalized_lowercase() -> None:
    """api_id 케이스/공백 정규화 — `AU10001`/`au10001 ` 등도 동일 처리."""
    payload = {"token": "x", "expires_dt": "y"}
    for api_id in ("AU10001", "au10001 ", "  Au10001"):
        scrubbed = scrub_token_fields(payload, api_id=api_id)
        assert scrubbed["token"] == "[SCRUBBED]"


def test_scrub_response_key_case_insensitive() -> None:
    """응답 키가 `Token`/`TOKEN` 으로 와도 매칭 — 적대적 리뷰 HIGH-2 반영."""
    payload_upper = {"Token": "REAL-TOKEN", "Expires_Dt": "20260508"}
    scrubbed = scrub_token_fields(payload_upper, api_id="au10001")
    assert scrubbed["Token"] == "[SCRUBBED]"
    assert scrubbed["Expires_Dt"] == "[SCRUBBED]"


# -----------------------------------------------------------------------------
# 입력 견고성
# -----------------------------------------------------------------------------


def test_scrub_empty_payload() -> None:
    assert scrub_token_fields({}, api_id="au10001") == {}


def test_scrub_nested_dict_not_recursed() -> None:
    """top-level 만 처리 — token 이 nested 로 오면 그대로. (현실에서 키움 응답은 flat)"""
    payload = {"data": {"token": "nested-token"}, "return_code": 0}
    scrubbed = scrub_token_fields(payload, api_id="au10001")
    # nested 의 token 은 그대로 — top-level token 만 처리 책임
    assert scrubbed["data"] == {"token": "nested-token"}


def test_scrub_rejects_non_dict_payload() -> None:
    with pytest.raises(TypeError, match="dict"):
        scrub_token_fields("not a dict", api_id="au10001")  # type: ignore[arg-type]


def test_scrub_rejects_non_string_api_id() -> None:
    with pytest.raises(TypeError, match="api_id"):
        scrub_token_fields({"token": "x"}, api_id=10001)  # type: ignore[arg-type]


# -----------------------------------------------------------------------------
# 평문이 결과 어디에도 남지 않음
# -----------------------------------------------------------------------------


def test_scrub_au10001_plaintext_not_present_anywhere() -> None:
    plaintext_token = "VeryRealTokenValueThatShouldNeverAppearInLogsOrDB12345"
    plaintext_expires = "20260508090000"
    payload = {
        "token": plaintext_token,
        "expires_dt": plaintext_expires,
        "return_code": 0,
    }
    scrubbed = scrub_token_fields(payload, api_id="au10001")
    serialized = repr(scrubbed)
    assert plaintext_token not in serialized
    assert plaintext_expires not in serialized
