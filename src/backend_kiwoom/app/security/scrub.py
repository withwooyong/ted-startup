"""raw_response 저장 직전 토큰/자격증명 평문 필드 제거 (ADR-0001 § 3 #3).

키움 인증 endpoint (au10001 issue / au10002 revoke) 응답·요청 본문이
`raw_response.response_payload` / `request_payload` (JSONB) 에 평문으로 들어가지 않도록,
UseCase 가 저장 직전에 호출.

원본 dict 는 변경하지 않음 (immutable 의미론) — caller 가 token 을
다른 경로 (TokenManager 캐시) 로 사용 가능. 새 dict 반환.

설계 원칙:
- 책임 영역: 인증 endpoint (au*) 한정. 비인증 (ka*) 은 통과. 인증인데 미등록은 fail-closed (ValueError).
- 화이트리스트: api_id 별 제거 대상 키 명시. 미등록 인증 endpoint 는 raise — silent passthrough 차단.
- key 비교 case-insensitive — 키움 응답 케이스 변경 (`Token`/`TOKEN`) 우회 방어.
- top-level 만 처리. 키움 응답은 flat 구조 — nested token 은 비정상 신호로 그대로 둠.
- "필드 삭제" 가 아니라 "[SCRUBBED]" 치환 — 디버깅 시 "있었음을 확인" 가능.

적대적 리뷰 반영:
- CRITICAL-3: au10002 의 appkey/secretkey 도 평문 → request_payload JSONB 저장 차단
- HIGH-1: api_id 정규화 + 인증 endpoint 미등록 fail-closed
- HIGH-2: key 비교 case-insensitive
"""

from __future__ import annotations

from typing import Any, Final

_SCRUBBED: Final[str] = "[SCRUBBED]"

# api_id → 제거 대상 top-level 키 (lowercase 로 정규화하여 저장)
_TOKEN_FIELDS_BY_API: Final[dict[str, frozenset[str]]] = {
    # au10001: issue token 응답 — token + expires_dt 가 평문
    "au10001": frozenset({"token", "expires_dt"}),
    # au10002: revoke — request body 에 token + appkey + secretkey 모두 평문 포함 (계획서 § 3.1)
    "au10002": frozenset({"token", "appkey", "secretkey"}),
}


def scrub_token_fields(payload: dict[str, Any], *, api_id: str) -> dict[str, Any]:
    """인증 endpoint payload 의 평문 비밀 필드를 [SCRUBBED] 로 치환한 새 dict 반환.

    Args:
        payload: 키움 응답 또는 요청 본문 (JSON 디코딩된 dict).
        api_id: 키움 endpoint 식별자. 대소문자/공백 정규화 후 매칭.

    Returns:
        비밀 필드가 [SCRUBBED] 로 치환된 새 dict. 원본은 변경 안 됨.

    Raises:
        TypeError: payload 가 dict 가 아니거나 api_id 가 str 가 아닐 때.
        ValueError: api_id 가 인증 endpoint (au*) 인데 화이트리스트 미등록일 때 — fail-closed.
    """
    if not isinstance(payload, dict):
        raise TypeError(f"payload 는 dict 여야 함 (got {type(payload).__name__})")
    if not isinstance(api_id, str):
        raise TypeError(f"api_id 는 str 여야 함 (got {type(api_id).__name__})")

    api_id_normalized = api_id.strip().lower()

    # 비인증 endpoint 는 통과 — token 키가 있어도 의미 다를 수 있음 (caller 책임).
    if not api_id_normalized.startswith("au"):
        return dict(payload)

    fields_to_scrub = _TOKEN_FIELDS_BY_API.get(api_id_normalized)
    if fields_to_scrub is None:
        # 인증 endpoint 인데 화이트리스트 미등록 — fail-closed. caller 오타·신규 endpoint 누락 차단.
        raise ValueError(
            f"unknown auth api_id={api_id!r} — _TOKEN_FIELDS_BY_API 에 등록 필요. "
            "신규 인증 endpoint 추가 시 화이트리스트 동기화."
        )

    out: dict[str, Any] = {}
    for key, value in payload.items():
        # case-insensitive 매칭 — `Token`/`TOKEN` 등 응답 케이스 변경 우회 방어.
        if isinstance(key, str) and key.lower() in fields_to_scrub and value is not None:
            out[key] = _SCRUBBED
        else:
            out[key] = value
    return out
