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
    output = _capture_stdlib_log(
        lambda: logging.getLogger("app.test").warning("토큰 응답: %s (만료 86400s)", jwt_ish)
    )
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
