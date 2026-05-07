"""structlog 기반 민감 데이터 마스킹 — backend_kiwoom 검증.

backend_py PR 6 패턴 복제. 키움 도메인 키(`appkey`, `secretkey`, `kiwoom_credential_master_key`)가
자동 마스킹되는지 + JWT/40+hex 정규식 scrub 동작 확인.

외부 호출 0. structlog·stdlib logging 내부만 사용.
"""

from __future__ import annotations

import io
import json
import logging
from collections.abc import Callable

import pytest
import structlog

from app.observability.logging import (
    SENSITIVE_KEYS,
    _scan,
    _scrub_string,
    mask_sensitive,
    reset_logging_for_tests,
    setup_logging,
)


@pytest.fixture(autouse=True)
def _reset_logging() -> None:
    reset_logging_for_tests()


# -----------------------------------------------------------------------------
# Unit: _scrub_string
# -----------------------------------------------------------------------------


def test_scrub_string_replaces_jwt_pattern() -> None:
    jwt_ish = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZWQifQ.abcdefghijklmnop"
    assert _scrub_string(f"token={jwt_ish} end") == "token=[MASKED_JWT] end"


def test_scrub_string_ignores_dotted_identifiers_without_jwt_prefix() -> None:
    assert _scrub_string("app.adapter.out.kiwoom.auth") == "app.adapter.out.kiwoom.auth"
    assert _scrub_string("v1.2.3 release") == "v1.2.3 release"


def test_scrub_string_replaces_long_hex() -> None:
    assert _scrub_string(f"hash={'a' * 40}") == "hash=[MASKED_HEX]"
    assert _scrub_string(f"digest={'b' * 64}") == "digest=[MASKED_HEX]"


def test_scrub_string_ignores_short_hex() -> None:
    assert _scrub_string("stock=005930") == "stock=005930"
    assert _scrub_string("alias=prod-main") == "alias=prod-main"


# -----------------------------------------------------------------------------
# ADR-0001 § 3 #1 — 키움 secretkey/token 정규식 보강 (prefix-aware)
# 적대적 리뷰 Round 2 (HIGH-A) 반영: 운영 식별자 (trace_id, correlation_id, PascalCase) 보존
# 위해 prefix-aware 매칭으로 좁힘. `secret=/token=/appkey=` 등 명시 prefix 뒤의 value 만 매칭.
# 1차 방어는 dict 키 매칭 (`SENSITIVE_KEYS`). 본 정규식은 f-string 평문 삽입 보조 안전망.
# -----------------------------------------------------------------------------


# ----- prefix-aware 매칭 (secret/token 평문 f-string) -----


def test_scrub_string_masks_secretkey_with_prefix_min_16chars() -> None:
    """`secretkey=Abc...` (16자 value) — prefix-aware 매칭."""
    secret = "Abc123Def456Ghi7"  # 16자
    assert _scrub_string(f"secretkey={secret}") == "secretkey=[MASKED_SECRET]"


def test_scrub_string_masks_token_prefix_150chars() -> None:
    """token=... 150자 운영 토큰 형식."""
    token = "WQJCwyqInph" + "ABCdef0123" * 13 + "X" * 9  # 150자
    out = _scrub_string(f"token={token}")
    assert "[MASKED_SECRET]" in out
    assert token not in out


def test_scrub_string_masks_appkey_prefix_with_colon() -> None:
    """`appkey: value` — `:` 구분도 매칭."""
    secret = "AbCdEfGhIjKlMnOp"  # 16자
    out = _scrub_string(f"appkey: {secret}")
    assert "[MASKED_SECRET]" in out
    assert secret not in out


def test_scrub_string_masks_password_prefix() -> None:
    """일반 password 도 매칭."""
    out = _scrub_string("password=SuperPassword12345")
    assert "[MASKED_SECRET]" in out
    assert "SuperPassword12345" not in out


def test_scrub_string_masks_access_token_prefix() -> None:
    """`access_token=value` 매칭."""
    secret = "AbCdEfGhIjKlMnOp"  # 16자
    out = _scrub_string(f"access_token={secret}")
    assert "[MASKED_SECRET]" in out


def test_scrub_string_masks_base64_padding_in_value() -> None:
    """base64 padding `==` 직전 본체만 매칭 (padding 자체는 비밀 아님)."""
    secret = "AbCdEfGhIjKl+MnOpQr/StUvWxYz1234567890"  # 38자 base64
    out = _scrub_string(f"token={secret}==")
    assert "[MASKED_SECRET]" in out
    assert secret not in out


def test_scrub_string_prefix_match_case_insensitive() -> None:
    """prefix 케이스 변경 (`SecretKey`/`TOKEN`) 도 매칭."""
    out_pascal = _scrub_string("SecretKey=Abc123Def456Ghi7")
    out_upper = _scrub_string("TOKEN=Abc123Def456Ghi7")
    assert "[MASKED_SECRET]" in out_pascal
    assert "[MASKED_SECRET]" in out_upper


# ----- 운영 식별자 보존 (HIGH-A 회귀 방지) -----


def test_scrub_string_preserves_trace_id() -> None:
    """trace_id 32자 hex 는 디버깅에 필수 — prefix 가 secret/token 아니면 통과."""
    s = "trace_id=0123456789abcdef0123456789abcdef"
    assert _scrub_string(s) == s


def test_scrub_string_preserves_correlation_id() -> None:
    """correlation_id 보존."""
    s = "correlation_id=req1234567890abcdef"
    assert _scrub_string(s) == s


def test_scrub_string_preserves_pascal_case_class_name() -> None:
    """PascalCase 클래스명 보존 — 운영 로그·스택트레이스 가독성."""
    assert _scrub_string("class=KiwoomCredentialsRepository") == "class=KiwoomCredentialsRepository"
    assert _scrub_string("ConcreteRepositoryImpl") == "ConcreteRepositoryImpl"


def test_scrub_string_preserves_build_id() -> None:
    """build_id/version_id 보존 — secret/token prefix 아니면 통과."""
    s = "build_id=abc123def4567890"
    assert _scrub_string(s) == s


def test_scrub_string_preserves_user_id() -> None:
    """user_id 같은 식별자 보존."""
    s = "user_id=USER1234567890ABCDEF"
    assert _scrub_string(s) == s


# ----- JWT/HEX 패턴 우선 + 일반 보존 -----


def test_scrub_string_jwt_pattern_takes_precedence() -> None:
    """JWT 형식이면 [MASKED_JWT] 로 우선 처리."""
    jwt_ish = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZWQifQ.abcdefghijklmnopqrstuvwxyz0123456789"
    out = _scrub_string(jwt_ish)
    assert "[MASKED_JWT]" in out


def test_scrub_string_hex_pattern_still_works() -> None:
    """40자 hex digest — `[MASKED_HEX]`."""
    hex_str = "a" * 40
    out = _scrub_string(hex_str)
    assert "[MASKED_HEX]" in out


def test_scrub_string_does_not_mask_iso_timestamp() -> None:
    """ISO 타임스탬프 보존."""
    ts = "2026-05-07T09:00:00+09:00"
    assert _scrub_string(ts) == ts


def test_scrub_string_does_not_mask_long_dotted_path() -> None:
    """dot path 보존."""
    s = "app.adapter.out.kiwoom.persistence.repositories.credential_repository"
    assert _scrub_string(s) == s


def test_scrub_string_does_not_mask_alias() -> None:
    """alias 형식 보존."""
    s = "alias=prod-main-001"
    assert _scrub_string(s) == s


def test_scrub_string_does_not_mask_uuid() -> None:
    """UUID 보존."""
    uuid = "550e8400-e29b-41d4-a716-446655440000"
    assert _scrub_string(uuid) == uuid


def test_scrub_string_does_not_mask_bare_alphanum_without_prefix() -> None:
    """prefix 없는 영숫자 16자 이상은 매칭 안 됨 — secret 인지 알 수 없음.
    1차 방어는 dict 키 매칭. caller 가 f-string 평문 삽입 시 prefix 명시 책임."""
    bare = "Abc123Def456Ghi789"  # 18자, prefix 없음
    assert _scrub_string(bare) == bare


def test_scrub_string_preserves_non_sensitive() -> None:
    original = "키움 토큰 발급 성공 (expires_dt=20251107083713)"
    assert _scrub_string(original) == original


# -----------------------------------------------------------------------------
# Unit: _scan
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("sensitive_key", sorted(SENSITIVE_KEYS))
def test_scan_masks_all_registered_sensitive_keys(sensitive_key: str) -> None:
    result = _scan({sensitive_key: "real-secret-0123456789"})
    assert result == {sensitive_key: "[MASKED]"}


@pytest.mark.parametrize(
    "key,plaintext",
    [
        ("kiwoom_credential_master_key", "ABCDEFGHIJKLMNOPQRSTUVWXYZ123456789012345678="),
        ("appkey", "AxserEsdcredca-prod-key-123"),
        ("secretkey", "SEefdcwcforehDre2fdvc-secret"),
        ("authorization", "Bearer eyJhbGc"),
        ("token", "WQJCwyqInphKnR3bSRtB9NE1lvabc"),
        ("admin_api_key", "admin-key-0123"),
    ],
)
def test_scan_masks_kiwoom_keys(key: str, plaintext: str) -> None:
    result = _scan({key: plaintext})
    assert result == {key: "[MASKED]"}
    assert plaintext not in json.dumps(result)


def test_scan_case_insensitive() -> None:
    assert _scan({"AppKey": "x"}) == {"AppKey": "[MASKED]"}
    assert _scan({"AUTHORIZATION": "Bearer x"}) == {"AUTHORIZATION": "[MASKED]"}


def test_scan_preserves_neutral_keys() -> None:
    """stock_code/alias/api_id 같은 중립 키는 통과."""
    data = {"stock_code": "005930", "alias": "prod-main", "api_id": "ka10081", "env": "prod"}
    assert _scan(data) == data


def test_scan_recurses_nested_dict() -> None:
    nested = {"outer": {"secretkey": "s", "alias": "x"}}
    assert _scan(nested) == {"outer": {"secretkey": "[MASKED]", "alias": "x"}}


def test_scan_recurses_list_of_dicts() -> None:
    data = [{"appkey": "k1"}, {"appkey": "k2"}]
    assert _scan(data) == [{"appkey": "[MASKED]"}, {"appkey": "[MASKED]"}]


def test_scan_recurses_set_with_jwt_string() -> None:
    """set 안의 JWT 문자열도 scrub."""
    jwt_ish = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZWQifQ.abcdefghijklmnop"
    result = _scan({jwt_ish, "neutral-string"})
    assert "[MASKED_JWT]" in result
    assert jwt_ish not in result


def test_scan_recurses_frozenset_with_long_hex() -> None:
    long_hex = "a" * 40
    result = _scan(frozenset([long_hex, "stock=005930"]))
    assert isinstance(result, frozenset)
    assert "[MASKED_HEX]" in result
    assert long_hex not in result


def test_scan_set_returns_set_type() -> None:
    """타입 보존 — set 은 set 으로 반환."""
    result = _scan({"normal-string", "another"})
    assert isinstance(result, set)


def test_scan_scrubs_string_leaves() -> None:
    jwt_ish = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZWQifQ.abcdefghijklmnop"
    data = {"message": f"got {jwt_ish}"}
    assert _scan(data) == {"message": "got [MASKED_JWT]"}


def test_scan_preserves_non_string_primitives() -> None:
    data = {"count": 7, "ok": True, "missing": None, "price": 72000.5}
    assert _scan(data) == data


def test_scan_none_value_in_sensitive_key_stays_none() -> None:
    assert _scan({"appkey": None}) == {"appkey": None}


# -----------------------------------------------------------------------------
# Unit: mask_sensitive processor
# -----------------------------------------------------------------------------


def test_mask_sensitive_processor_applies_scan() -> None:
    event = {"event": "키움 호출", "appkey": "real-key", "stock_code": "005930"}
    result = mask_sensitive(None, "info", event)
    assert result == {"event": "키움 호출", "appkey": "[MASKED]", "stock_code": "005930"}


def test_mask_sensitive_processor_masks_event_field_string() -> None:
    jwt_ish = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZWQifQ.abcdefghijklmnop"
    event = {"event": f"토큰 발급: {jwt_ish}"}
    result = mask_sensitive(None, "info", event)
    assert "[MASKED_JWT]" in result["event"]
    assert jwt_ish not in result["event"]


# -----------------------------------------------------------------------------
# Integration
# -----------------------------------------------------------------------------


def _capture_stdlib_log(record_call: Callable[[], None]) -> str:
    setup_logging(log_level="INFO", json_output=True)
    buf = io.StringIO()
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    for h in original_handlers:
        root.removeHandler(h)
    capture_handler = logging.StreamHandler(buf)
    capture_handler.setFormatter(original_handlers[0].formatter)
    root.addHandler(capture_handler)
    try:
        record_call()
    finally:
        root.removeHandler(capture_handler)
        for h in original_handlers:
            root.addHandler(h)
    return buf.getvalue()


def test_stdlib_logger_extra_fields_dropped_by_default() -> None:
    """stdlib logger.info(msg, extra={...}) 의 extra 는 ProcessorFormatter 가 drop — 노출 0."""
    output = _capture_stdlib_log(
        lambda: logging.getLogger("app.test").info(
            "Kiwoom call prep",
            extra={"secretkey": "super-secret-value"},
        )
    )
    assert "super-secret-value" not in output
    data = json.loads(output.strip().splitlines()[0])
    assert data["event"] == "Kiwoom call prep"
    assert "secretkey" not in data


def test_stdlib_logger_integration_scrubs_jwt_in_message() -> None:
    jwt_ish = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZWQifQ.abcdefghijklmnop"
    output = _capture_stdlib_log(lambda: logging.getLogger("app.test").warning("토큰 응답: %s (만료 86400s)", jwt_ish))
    assert jwt_ish not in output
    assert "[MASKED_JWT]" in output


def test_structlog_native_logger_masks_bound_context() -> None:
    setup_logging(log_level="INFO", json_output=True)
    buf = io.StringIO()
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    for h in original_handlers:
        root.removeHandler(h)
    capture_handler = logging.StreamHandler(buf)
    capture_handler.setFormatter(original_handlers[0].formatter)
    root.addHandler(capture_handler)
    try:
        log = structlog.get_logger("app.test")
        log.bind(appkey="bound-key", note="ok").info("call")
    finally:
        root.removeHandler(capture_handler)
        for h in original_handlers:
            root.addHandler(h)

    data = json.loads(buf.getvalue().strip().splitlines()[0])
    assert data["appkey"] == "[MASKED]"
    assert data["note"] == "ok"
    assert data["event"] == "call"


def test_setup_logging_is_idempotent() -> None:
    setup_logging(log_level="INFO", json_output=True)
    assert len(logging.getLogger().handlers) == 1

    foreign_handler = logging.StreamHandler(io.StringIO())
    logging.getLogger().addHandler(foreign_handler)
    setup_logging(log_level="DEBUG", json_output=False)
    assert foreign_handler in logging.getLogger().handlers


# -----------------------------------------------------------------------------
# au10001 회귀 — 응답 본문 token/expires_dt 마스킹
# -----------------------------------------------------------------------------


def test_au10001_response_token_key_masked_in_dict() -> None:
    """au10001 응답 dict 에 logger 가 노출하면 token 키는 [MASKED]."""
    body = {
        "expires_dt": "20260507083713",
        "token_type": "bearer",
        "token": "WQJCwyqInphKnR3bSRtB9NE1lv",
        "return_code": 0,
        "return_msg": "ok",
    }
    masked = _scan(body)
    assert masked["token"] == "[MASKED]"
    assert "WQJCwyqInphKnR3bSRtB9NE1lv" not in json.dumps(masked)


def test_au10001_response_jwt_in_message_masked_at_logger() -> None:
    """au10001 응답이 잘못 string interpolated 돼 event 에 들어가도 JWT 패턴 자동 마스킹."""
    jwt_ish = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZWQifQ.abcdefghijklmnopqrstuvwxyz"
    output = _capture_stdlib_log(
        lambda: logging.getLogger("app.test").info("au10001 response: token=%s expires=20260507083713", jwt_ish)
    )
    assert jwt_ish not in output
    assert "[MASKED_JWT]" in output


def test_au10001_request_body_appkey_secretkey_masked() -> None:
    """au10001 요청 body 가 dict 로 logger 에 들어가면 appkey/secretkey 키 [MASKED]."""
    request_body = {
        "grant_type": "client_credentials",
        "appkey": "AxserEsdcredca1234567890",
        "secretkey": "SEefdcwcforehDre2fdvc1234567890",
    }
    masked = _scan(request_body)
    assert masked["appkey"] == "[MASKED]"
    assert masked["secretkey"] == "[MASKED]"
    assert masked["grant_type"] == "client_credentials"  # 중립 키 보존
