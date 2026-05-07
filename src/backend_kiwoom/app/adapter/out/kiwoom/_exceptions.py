"""키움 어댑터 도메인 예외 (5종 + base).

설계: endpoint-01-au10001.md § 8 / endpoint-02-au10002.md § 8 / master.md § 6.4.

분류 원칙:
- 401/403 → KiwoomCredentialRejectedError (재시도 금지 — timing leak 방지)
- 5xx, 네트워크, JSON 파싱 실패 → KiwoomUpstreamError (tenacity 재시도)
- 200 + return_code != 0 → KiwoomBusinessError (재시도 무의미)
- 429 → KiwoomRateLimitedError (tenacity 재시도 후 최종 fail)
- Pydantic 검증 실패 → KiwoomResponseValidationError

예외 메시지 보안 정책 (적대적 리뷰 반영):
- 응답 본문은 메시지에 포함 금지 — 자격증명 hint / 토큰 누설 방어
- HTTP status code, api_id, return_code 등 비식별 메타만 메시지에 노출
- 예외에 원본 응답 보관 시 caller 가 평문으로 logger 에 노출하지 않도록 caller 책임 강제
"""

from __future__ import annotations


class KiwoomError(Exception):
    """모든 키움 어댑터 예외의 베이스."""


class KiwoomUpstreamError(KiwoomError):
    """5xx · 네트워크 · JSON 파싱 실패 — 재시도 후 최종 fail.

    라우터 매핑: 502 Bad Gateway.
    """


class KiwoomCredentialRejectedError(KiwoomError):
    """401 / 403 — 자격증명 거부.

    재시도 금지: 자격증명 무차별 시도 timing leak 방지.
    라우터 매핑: 400 (au10001) / 200 idempotent (au10002 만료 토큰).
    """


class KiwoomBusinessError(KiwoomError):
    """200 + return_code != 0 — 키움 비즈니스 거부.

    api_id / return_code 는 비식별 메타 — `__str__` 로 노출 안전.
    message 는 attacker-influenced (Kiwoom return_msg) 라 super-message 에서 제외 —
    `str(exc)` / `logger.exception(exc)` 경로의 우발적 평문 누설 방어.
    필요 시 caller 가 명시적으로 `exc.message` 접근.
    """

    def __init__(self, *, api_id: str, return_code: int, message: str) -> None:
        super().__init__(f"{api_id} return_code={return_code}")
        self.api_id = api_id
        self.return_code = return_code
        self.message = message


class KiwoomRateLimitedError(KiwoomError):
    """429 — 키움 RPS 초과.

    tenacity 가 wait_exponential 로 재시도. 최종 fail 시 라우터 매핑: 503.
    """


class KiwoomResponseValidationError(KiwoomError):
    """Pydantic 검증 실패 — 응답 형식 위반 (token 누락, expires_dt 비숫자 등).

    라우터 매핑: 502 Bad Gateway. 메시지에 응답 본문 미포함.
    """
