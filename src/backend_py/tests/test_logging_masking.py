"""PR 6 — 민감 데이터 마스킹 processor 단위·통합 테스트.

검증 대상:
1. `_scan` 재귀 치환 — dict/list/str 중첩 구조에서 민감 키 값이 [MASKED] 로.
2. `_scrub_string` 패턴 치환 — JWT / 40+ hex.
3. `mask_sensitive` structlog processor — event_dict 전체 스캔.
4. `setup_logging` 후 stdlib `logging.getLogger(__name__).info(...)` 호출도 마스킹 적용.

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
    """각 테스트 전 로깅 상태 리셋 — `_configured` guard + root 핸들러."""
    reset_logging_for_tests()

# -----------------------------------------------------------------------------
# Unit: _scrub_string
# -----------------------------------------------------------------------------


def test_scrub_string_replaces_jwt_pattern() -> None:
    """JWT 3-segment (`eyJ...header.payload.signature`) → [MASKED_JWT]."""
    jwt_ish = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZWQifQ.abcdefghijklmnop"
    assert _scrub_string(f"token={jwt_ish} end") == "token=[MASKED_JWT] end"


def test_scrub_string_ignores_dotted_identifiers_without_jwt_prefix() -> None:
    """`eyJ` 접두 없는 .연결 식별자는 JWT 패턴 미매칭 — logger 이름·버전·파일 경로 보호."""
    # structlog logger 이름이 JSON 출력 `logger` 필드에 그대로 남아야 함
    assert _scrub_string("app.adapter.out.real_client") == "app.adapter.out.real_client"
    # 세 세그먼트 각 10자+ 인 긴 식별자도 `eyJ` 없으면 통과
    long_ident = "module_name-extended.class_name-extended.method_name-extended"
    assert _scrub_string(long_ident) == long_ident
    # 기존 false positive 시나리오도 통과
    assert _scrub_string("v1.2.3 release") == "v1.2.3 release"


def test_scrub_string_replaces_long_hex() -> None:
    """40자 이상 hex → [MASKED_HEX]. SHA-1 digest (40자) 시작 경계 포함."""
    sha1 = "a" * 40
    sha256 = "b" * 64
    assert _scrub_string(f"hash={sha1}") == "hash=[MASKED_HEX]"
    assert _scrub_string(f"digest={sha256}") == "digest=[MASKED_HEX]"


def test_scrub_string_ignores_short_hex() -> None:
    """stock_code(6자) 같은 짧은 hex 는 불변."""
    assert _scrub_string("stock=005930") == "stock=005930"
    assert _scrub_string("account_no=12345678-01") == "account_no=12345678-01"


def test_scrub_string_preserves_non_sensitive() -> None:
    """한국어·일반 영문 문장은 변경 없이 통과."""
    original = "KIS 토큰 발급 성공 (expires_in=86400s)"
    assert _scrub_string(original) == original


# -----------------------------------------------------------------------------
# Unit: _scan (재귀 dict/list/str 치환)
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("sensitive_key", sorted(SENSITIVE_KEYS))
def test_scan_masks_all_registered_sensitive_keys(sensitive_key: str) -> None:
    """등록된 모든 민감 키에 대해 값이 [MASKED] 로 치환."""
    result = _scan({sensitive_key: "real-secret-0123456789"})
    assert result == {sensitive_key: "[MASKED]"}


@pytest.mark.parametrize(
    "key,plaintext",
    [
        # 프로젝트 고유 복합 필드 — SENSITIVE_KEY_SUFFIXES 가 커버해야 함
        ("openai_api_key", "sk-real-key-123"),
        ("dart_api_key", "dart-real-key"),
        ("kis_app_key_mock", "REAL_APP_KEY_MOCK_123"),
        ("kis_app_secret_mock", "REAL_APP_SECRET_MOCK"),
        ("telegram_bot_token", "bot123:AAAAxxxxxxxxxxxxxxxx"),
        ("krx_pw", "my_password_value"),
        ("admin_api_key", "admin-key-0123"),
        ("STRIPE_CLIENT_SECRET", "sk_live_0123"),  # 대소문자 혼합
    ],
)
def test_scan_masks_compound_keys_via_suffix(key: str, plaintext: str) -> None:
    """complex env 필드명 — suffix 매칭으로 자동 커버. HIGH #3 반영."""
    result = _scan({key: plaintext})
    assert result == {key: "[MASKED]"}
    assert plaintext not in json.dumps(result)


def test_scan_case_insensitive() -> None:
    """대소문자 혼합 키도 매칭."""
    assert _scan({"App_Key": "x"}) == {"App_Key": "[MASKED]"}
    assert _scan({"AUTHORIZATION": "Bearer x"}) == {"AUTHORIZATION": "[MASKED]"}


def test_scan_preserves_neutral_keys() -> None:
    """account_no, stock_code 같은 중립 키는 부분 일치에 걸리지 않음."""
    data = {"account_no": "12345678-01", "stock_code": "005930", "environment": "real"}
    assert _scan(data) == data


def test_scan_recurses_nested_dict() -> None:
    """중첩 dict 내부의 민감 키도 치환."""
    nested = {"outer": {"app_secret": "s", "account_no": "x"}}
    assert _scan(nested) == {"outer": {"app_secret": "[MASKED]", "account_no": "x"}}


def test_scan_recurses_list_of_dicts() -> None:
    """list 안의 dict 도 스캔."""
    data = [{"app_key": "k1"}, {"app_key": "k2"}]
    assert _scan(data) == [{"app_key": "[MASKED]"}, {"app_key": "[MASKED]"}]


def test_scan_scrubs_string_leaves() -> None:
    """dict value 가 JWT 문자열이면 scrub 적용."""
    jwt_ish = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZWQifQ.abcdefghijklmnop"
    data = {"message": f"got {jwt_ish}"}
    assert _scan(data) == {"message": "got [MASKED_JWT]"}


def test_scan_preserves_non_string_primitives() -> None:
    """int/bool/None 은 변경 없이 통과."""
    data = {"count": 7, "ok": True, "missing": None, "price": 72000.5}
    assert _scan(data) == data


def test_scan_none_value_in_sensitive_key_stays_none() -> None:
    """민감 키 값이 None 이면 None 유지 (로그 가독성 — 부재 표시)."""
    assert _scan({"app_key": None}) == {"app_key": None}


# -----------------------------------------------------------------------------
# Unit: mask_sensitive structlog processor
# -----------------------------------------------------------------------------


def test_mask_sensitive_processor_applies_scan() -> None:
    """structlog processor 시그니처 — `(logger, method_name, event_dict)` 를 받아 event_dict 반환."""
    event = {"event": "KIS 호출", "app_key": "real-key", "stock_code": "005930"}
    result = mask_sensitive(None, "info", event)
    assert result == {"event": "KIS 호출", "app_key": "[MASKED]", "stock_code": "005930"}


def test_mask_sensitive_processor_masks_event_field_string() -> None:
    """event 필드의 렌더된 메시지도 scrub — JWT 가 섞여 있으면 치환."""
    jwt_ish = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZWQifQ.abcdefghijklmnop"
    event = {"event": f"토큰 발급: {jwt_ish}"}
    result = mask_sensitive(None, "info", event)
    assert "[MASKED_JWT]" in result["event"]
    assert jwt_ish not in result["event"]


# -----------------------------------------------------------------------------
# Integration: setup_logging() + stdlib logger 호출
# -----------------------------------------------------------------------------


def _capture_stdlib_log(record_call: Callable[[], None]) -> str:
    """setup_logging 후 root 핸들러를 StringIO 로 임시 교체해 출력 캡처."""
    setup_logging(log_level="INFO", json_output=True)
    buf = io.StringIO()
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    # 기존 StreamHandler(stderr) 를 StringIO 버전으로 교체 — formatter 는 유지.
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


def test_stdlib_logger_extra_fields_are_dropped_by_default() -> None:
    """stdlib `logger.info(msg, extra={...})` 의 extra 는 ProcessorFormatter 가
    기본적으로 event_dict 로 옮기지 않는다 — 누락 = 노출 0 으로 오히려 안전.

    구조화된 필드를 로그에 남기려면 structlog 네이티브 `log.info("msg", key=v)` 를
    사용해야 하며, 그 경로는 `test_structlog_native_logger_masks_bound_context` 가 검증.
    """
    output = _capture_stdlib_log(
        lambda: logging.getLogger("app.test").info(
            "KIS call prep",  # 한글 이스케이프 회피 — JSONRenderer 는 기본 ensure_ascii=True
            extra={"app_secret": "super-secret-value"},
        )
    )
    assert "super-secret-value" not in output  # 핵심: plaintext 누출 없음
    data = json.loads(output.strip().splitlines()[0])
    assert data["event"] == "KIS call prep"
    assert "app_secret" not in data  # extra 필드 자체가 drop 됨


def test_stdlib_logger_integration_scrubs_jwt_in_message() -> None:
    """stdlib logger 메시지 내부 JWT 패턴 scrub — rendered 문자열 검사."""
    jwt_ish = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZWQifQ.abcdefghijklmnop"
    output = _capture_stdlib_log(
        lambda: logging.getLogger("app.test").warning(
            "토큰 응답: %s (만료 86400s)", jwt_ish
        )
    )
    assert jwt_ish not in output
    assert "[MASKED_JWT]" in output


def test_structlog_native_logger_masks_bound_context() -> None:
    """structlog 네이티브 `log.bind(app_key=...).info(...)` 도 마스킹."""
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
        log.bind(app_key="bound-key", note="ok").info("call")
    finally:
        root.removeHandler(capture_handler)
        for h in original_handlers:
            root.addHandler(h)

    data = json.loads(buf.getvalue().strip().splitlines()[0])
    assert data["app_key"] == "[MASKED]"
    assert data["note"] == "ok"
    assert data["event"] == "call"


def test_setup_logging_is_idempotent() -> None:
    """두 번째 이후 호출은 no-op — root 핸들러 1개, 외부에서 추가한 핸들러 보존."""
    setup_logging(log_level="INFO", json_output=True)
    assert len(logging.getLogger().handlers) == 1

    # 외부 (예: pytest caplog) 가 나중에 핸들러 추가해도 두 번째 setup_logging 이 제거하지 않음
    foreign_handler = logging.StreamHandler(io.StringIO())
    logging.getLogger().addHandler(foreign_handler)
    setup_logging(log_level="DEBUG", json_output=False)  # 실제로는 no-op
    assert foreign_handler in logging.getLogger().handlers
