"""structlog 기반 구조화 로깅 + 민감 데이터 자동 마스킹 (backend_kiwoom).

backend_py PR 6 패턴 복제. 키움 도메인 키 추가:
- `appkey`, `secretkey`, `kiwoom_credential_master_key`, `token`, `authorization` 등

2층 방어:
1. 키 기반 치환: dict/kwargs 키가 SENSITIVE_KEYS (완전일치) 또는 SUFFIXES (접미일치)
   → 값을 [MASKED] 로 재귀 치환
2. 정규식 scrub: 문자열 이벤트에서 JWT 3-segment + 40자 이상 hex → [MASKED_JWT] / [MASKED_HEX]

stdlib `logging` 통합은 ProcessorFormatter foreign_pre_chain 으로 — 기존
`logging.getLogger(__name__).info(...)` 호출도 자동 마스킹 혜택.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

# 완전 일치 키 — 키움 도메인 + 일반 OAuth/HTTP 식별자
SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        # 키움 자격증명
        "appkey",
        "app_key",
        "secretkey",
        "secret_key",
        "appsecret",
        "app_secret",
        "kiwoom_appkey",
        "kiwoom_secretkey",
        "kiwoom_credential_master_key",
        # OAuth2 / JWT
        "access_token",
        "accesstoken",
        "refresh_token",
        "refreshtoken",
        "id_token",
        "token",
        "client_secret",
        "clientsecret",
        # HTTP 헤더
        "authorization",
        "x-api-key",
        "x_api_key",
        "admin_api_key",
        "admin-api-key",
        "api_key",
        "api-key",
        # 범용
        "password",
        "secret",
    }
)

# 접미 일치 — 신규 env 추가 시 SENSITIVE_KEYS 동기화 불필요
SENSITIVE_KEY_SUFFIXES: tuple[str, ...] = (
    "_api_key",
    "-api-key",
    "_app_key",
    "-app-key",
    "_appkey",
    "_app_secret",
    "-app-secret",
    "_secretkey",
    "_access_token",
    "-access-token",
    "_refresh_token",
    "-refresh-token",
    "_bot_token",
    "-bot-token",
    "_client_secret",
    "-client-secret",
    "_password",
    "_secret",
    "_master_key",
    "-master-key",
    "_credential",
    "_pw",
)


def _is_sensitive_key(key: str) -> bool:
    """완전 일치 + 접미 일치. 대소문자 무시."""
    k = key.lower()
    if k in SENSITIVE_KEYS:
        return True
    return k.endswith(SENSITIVE_KEY_SUFFIXES)


# JWT: `eyJ{header}.{payload}.{signature}` — JOSE 표준 헤더 base64url. eyJ 접두 제약으로
# logger 이름·버전 같은 일반 식별자가 오탐되지 않게 안전판.
_JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
# 40+ hex — SHA-1/SHA-256 digest, 일부 토큰 형식. 6자리 stock_code 는 매칭 안 됨.
_HEX_PATTERN = re.compile(r"\b[0-9a-fA-F]{40,}\b")
# 키움 secretkey/appkey/token prefix-aware 매칭 (ADR-0001 § 3 #1, 적대적 리뷰 Round 2 HIGH-A 반영):
# - 운영 식별자 (trace_id, correlation_id, PascalCase, build_id) 광범위 false positive 차단.
# - prefix 화이트리스트: secretkey/appkey/token/access_token/refresh_token/password 등 명시 prefix 뒤에
#   `=` 또는 `:` 로 구분된 16~1024자 영숫자+base64(`+/`) value 만 매칭.
# - `\b` word boundary + `[:=]\s*` 구분자 강제로 변수 prefix 가 비밀 의도일 때만 마스킹.
# - 1차 방어는 dict 키 매칭 (`SENSITIVE_KEYS`). 본 정규식은 f-string 평문 삽입 보조 안전망.
# - prefix 없는 영숫자 평문 (`bare`) 은 매칭 안 됨 — caller 가 f-string 작성 시 prefix 명시 책임.
_KIWOOM_SECRET_PATTERN = re.compile(
    r"(\b(?:secretkey|secret_key|secret|appkey|app_key|access_token|refresh_token|token|password)"
    r"\s*[:=]\s*)[A-Za-z0-9+/]{16,1024}\b",
    re.IGNORECASE,
)

_MASKED = "[MASKED]"
_MASKED_JWT = "[MASKED_JWT]"
_MASKED_HEX = "[MASKED_HEX]"
_MASKED_SECRET = "[MASKED_SECRET]"  # nosec B105 — 마스킹 라벨, 실제 secret 아님


def _scrub_string(s: str) -> str:
    """문자열 내부의 JWT/hex/키움 secretkey 패턴 치환.

    적용 순서:
    1. JWT (`eyJ` 접두 + 3-segment) — 가장 특수한 형태부터
    2. 40+자 hex — SHA digest 계열
    3. 키움 prefix-aware secret/token (prefix 보존, value 만 [MASKED_SECRET])
    """
    s = _JWT_PATTERN.sub(_MASKED_JWT, s)
    s = _HEX_PATTERN.sub(_MASKED_HEX, s)
    # group 1 = prefix+separator 보존, value 부분만 [MASKED_SECRET] 로 치환
    s = _KIWOOM_SECRET_PATTERN.sub(rf"\g<1>{_MASKED_SECRET}", s)
    return s


def _scan(node: Any) -> Any:
    """재귀 스캔. dict 의 민감 키 값은 [MASKED], 일반 str 은 scrub.

    - dict: 키가 민감하면 값 전체 [MASKED]. 아니면 값을 재귀 처리.
    - list/tuple/set/frozenset: 원소 재귀 처리 (타입 보존).
    - str: JWT/hex 패턴 scrub.
    - 기타 (int/bool/None/bytes/사용자 정의 객체): 변경 없이 통과.
    """
    if isinstance(node, Mapping):
        out: dict[Any, Any] = {}
        for k, v in node.items():
            if isinstance(k, str) and _is_sensitive_key(k):
                out[k] = _MASKED if v is not None else None
            else:
                out[k] = _scan(v)
        return out
    if isinstance(node, list):
        return [_scan(x) for x in node]
    if isinstance(node, tuple):
        return tuple(_scan(x) for x in node)
    if isinstance(node, frozenset):
        return frozenset(_scan(x) for x in node)
    if isinstance(node, set):
        return {_scan(x) for x in node}
    if isinstance(node, str):
        return _scrub_string(node)
    return node


def mask_sensitive(_logger: WrappedLogger, _method_name: str, event_dict: EventDict) -> EventDict:
    """structlog processor — 이벤트 딕트 전체를 재귀 스캔해 민감값 치환.

    chain 내 위치: timestamp/level 추가 뒤, 최종 render 직전에 배치.
    """
    scanned = _scan(event_dict)
    if not isinstance(scanned, dict):  # pragma: no cover
        return event_dict
    return scanned


_configured = False


def setup_logging(*, log_level: str = "INFO", json_output: bool = True) -> None:
    """프로세스 시작 시 1회만 호출. structlog + stdlib logging 단일 파이프라인 통합.

    - `json_output=False` 는 개발 콘솔 (ConsoleRenderer).
    - 재호출은 no-op (`_configured` guard) — pytest caplog 같은 외부 핸들러 보존.
    - 테스트 재설정은 `reset_logging_for_tests()`.
    """
    global _configured
    if _configured:
        return

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        mask_sensitive,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer() if json_output else structlog.dev.ConsoleRenderer(colors=False)
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processor=renderer,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(log_level.upper())
    _configured = True


def reset_logging_for_tests() -> None:
    """테스트 전용 — `_configured` guard 리셋 + root 핸들러 제거.

    운영 코드에서 호출 금지.
    """
    global _configured
    _configured = False
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
