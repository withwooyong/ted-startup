"""structlog 기반 구조화 로깅 + 민감 데이터 자동 마스킹.

PR 6 (KIS sync 시리즈 최종): 실 KIS 외부 호출이 PR 5 에서 열리면서 로그에 토큰/
시크릿이 실수로 흘러갈 위험이 현실화. structlog processor 로 두 층 방어:

1. **키 기반 치환**: dict·kwargs 키가 민감 식별자(`app_key`, `app_secret`,
   `access_token`, `authorization` 등)이면 값을 `[MASKED]` 로 재귀 치환.
2. **정규식 scrub**: 문자열 이벤트·메시지에서 JWT 3-segment + 40자 이상 hex
   패턴을 찾아 치환. 토큰 형태를 사전에 모른 채 로그에 섞여도 잡아냄.

stdlib `logging` 과의 통합은 structlog 의 `ProcessorFormatter` 브릿지로 수행 —
기존 `logging.getLogger(__name__)` 호출도 자동으로 마스킹 혜택을 받는다.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

# 완전 일치 키 — 짧고 명확한 식별자 + 프로젝트 특이 env 필드.
# `account_no` 같은 중립 필드는 오염 안 됨.
SENSITIVE_KEYS: frozenset[str] = frozenset({
    # KIS 자격증명 — 표준
    "app_key", "appkey",
    "app_secret", "appsecret",
    "kis_credential_master_key",
    # KIS mock credentials — 테스트 환경 값도 로그 노출 방지
    "kis_app_key_mock", "kis_app_secret_mock", "kis_account_no_mock",
    # OAuth2 / JWT 일반
    "access_token", "accesstoken",
    "refresh_token", "refreshtoken",
    "id_token",
    "token",
    "client_secret", "clientsecret",
    # HTTP 헤더
    "authorization",
    "x-api-key", "x_api_key",
    "admin_api_key", "admin-api-key",
    "api_key", "api-key",
    # 프로젝트 특이 env 필드 (settings.py 실제 필드명)
    "openai_api_key", "dart_api_key", "telegram_bot_token",
    "krx_id", "krx_pw",
    # 범용
    "password",
    "secret",
})

# 접미 일치 키 — `openai_api_key`, `dart_api_key`, `telegram_bot_token`, `krx_pw`,
# `kis_app_key_mock` 같은 프로젝트 고유 복합 필드 자동 커버. 신규 env 필드 추가 시
# `SENSITIVE_KEYS` 를 수동 동기화할 필요 없음.
SENSITIVE_KEY_SUFFIXES: tuple[str, ...] = (
    "_api_key", "-api-key",
    "_app_key", "-app-key",
    "_app_secret", "-app-secret",
    "_access_token", "-access-token",
    "_refresh_token", "-refresh-token",
    "_bot_token", "-bot-token",
    "_client_secret", "-client-secret",
    "_password",
    "_secret",
    "_master_key", "-master-key",
    "_credential",
    "_pw",  # `krx_pw` 같은 축약 필드
)


def _is_sensitive_key(key: str) -> bool:
    """완전 일치 + 접미 일치 OR 검사. 대소문자 무시."""
    k = key.lower()
    if k in SENSITIVE_KEYS:
        return True
    return k.endswith(SENSITIVE_KEY_SUFFIXES)


# JWT: `eyJ{header}.{payload}.{signature}` — base64url 인코딩 `{"` 으로 시작하는 JOSE
# 표준 헤더. `eyJ` 접두 제약으로 false positive 차단:
#   - Python 식별자(`app.adapter.web.real_client` 같은 structlog logger 이름)가
#     `[MASKED_JWT]` 로 오탐되지 않음
#   - 버전(`v1.2.3`), IP, 파일 경로 등은 애초에 `eyJ` 없음
# KIS·OpenAI·Anthropic 등 주요 OAuth2 공급자가 이 표준을 따른다. opaque token 은
# 키 기반 매칭(`access_token` 등) 으로 커버.
_JWT_PATTERN = re.compile(
    r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
)
# 40자 이상 hex — SHA-1/SHA-256 digest, 일부 토큰 형식. 짧은 stock_code(6자) 는 매칭 안 됨.
# Known trade-off: git commit SHA(40자) / content hash 같은 의도적 식별자도 치환됨.
# KIS 도메인에서 문제 없으며, 운영 디버깅 시 구분 필요해지면 56자 이상(SHA-224+) 상향 고려.
_HEX_PATTERN = re.compile(r"\b[0-9a-fA-F]{40,}\b")

_MASKED = "[MASKED]"
_MASKED_JWT = "[MASKED_JWT]"
_MASKED_HEX = "[MASKED_HEX]"


def _scrub_string(s: str) -> str:
    """문자열 내부의 JWT/hex 패턴 치환. 이미 mask 된 값은 fixed-point 로 불변."""
    s = _JWT_PATTERN.sub(_MASKED_JWT, s)
    s = _HEX_PATTERN.sub(_MASKED_HEX, s)
    return s


def _scan(node: Any) -> Any:
    """재귀 스캔 — dict/list/tuple 의 민감 키 값은 `[MASKED]` 로, 일반 str 은 scrub.

    - dict: 키가 `SENSITIVE_KEYS` 에 포함되면 값 전체를 `[MASKED]`. 아니면 값을 재귀 처리.
    - list/tuple: 원소를 재귀 처리 (타입 보존).
    - str: JWT/hex 패턴 scrub.
    - 기타 (int, bool, None, 바이트, custom object): 변경 없이 통과.
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
    if isinstance(node, str):
        return _scrub_string(node)
    return node


def mask_sensitive(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """structlog processor — 이벤트 딕트 전체를 재귀 스캔해 민감값 치환.

    chain 내 위치: timestamp/level 추가 뒤, 최종 render 직전에 배치해
    structlog 이 추가한 메타데이터도 함께 검증되도록 한다.
    """
    scanned = _scan(event_dict)
    # `_scan` 은 polymorphic(Any) — 최상위 호출 결과는 반드시 dict 여야 한다.
    # assert 대신 방어적 분기: `python -O` 에 영향받지 않고 mypy narrowing 도 지원.
    if not isinstance(scanned, dict):  # pragma: no cover — 도달 불가
        return event_dict
    return scanned


_configured = False


def setup_logging(*, log_level: str = "INFO", json_output: bool = True) -> None:
    """프로세스 시작 시 **1회만** 호출. structlog + stdlib logging 을 단일 파이프라인으로 통합.

    - stdlib `logging.getLogger(__name__).info(...)` 호출이 structlog processor
      chain 을 경유 → `mask_sensitive` 가 rendered message·args 를 모두 마스킹.
    - `json_output=False` 는 개발 콘솔용 (ConsoleRenderer, 색상 포함).
    - **재호출 시 no-op**: 두 번째 이후 호출은 `_configured` guard 로 조기 반환.
      pytest `caplog` 픽스처 같은 외부 핸들러가 나중에 추가돼도 소리 없이 제거되지 않음.
    - 런타임에 log_level 을 바꾸려면 프로세스 재기동 필요 (env var `LOG_LEVEL`).
      테스트에서 설정을 재적용하려면 `reset_logging_for_tests()` 사용.
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
        # 마스킹은 renderer 직전 — structlog 이 추가한 메타데이터까지 포함해 검사.
        mask_sensitive,
    ]

    # structlog 네이티브 logger 용 설정.
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # stdlib logging 브릿지 — `foreign_pre_chain` 으로 `logger.info(...)` 호출도 같은 processor 를 태움.
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processor=renderer,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root = logging.getLogger()
    # 기존 핸들러 제거 후 재설정 — pytest caplog 와 공존하도록 propagate 는 True 유지.
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(log_level.upper())
    _configured = True


def reset_logging_for_tests() -> None:
    """테스트 전용 — `_configured` guard 리셋 + root 핸들러 제거.

    운영 코드에서 호출 금지. pytest 에서 서로 다른 설정으로 `setup_logging` 을
    재적용해야 할 때만 사용. 일반 테스트는 setup_logging 을 한 번만 호출하면 OK.
    """
    global _configured
    _configured = False
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
