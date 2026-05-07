"""키움 인증 도메인 값 객체.

설계: endpoint-01-au10001.md § 6.2.

- KiwoomCredentials: 평문 자격증명. UseCase 스코프 안에서만 존재.
- IssuedToken: 발급된 토큰 + 만료 시각 (KST 가정).
- MaskedKiwoomCredentialView: 외부 노출용 — secretkey 는 어떤 경로로도 평문 노출 안 됨.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True, slots=True)
class KiwoomCredentials:
    """평문 자격증명. __repr__ 가 secretkey 마스킹.

    원칙: caller 가 dict() 로 변환해 logger 에 넘기지 않음. dataclass 자체로만 전달.
    """

    appkey: str
    secretkey: str

    def __repr__(self) -> str:
        tail = self.appkey[-4:] if len(self.appkey) >= 4 else "****"
        return f"KiwoomCredentials(appkey=••••{tail}, secretkey=<masked>)"


@dataclass(frozen=True, slots=True)
class IssuedToken:
    """발급된 키움 접근토큰. expires_at 은 tz-aware datetime 강제.

    tz-naive datetime 이 들어오면 ValueError — 키움 응답 `expires_dt` 가 KST 문자열이라
    파싱 시 tzinfo 미부여 시 만료 판정이 9시간 오차 발생 위험.
    """

    token: str
    token_type: str
    expires_at: datetime

    def __post_init__(self) -> None:
        if self.expires_at.tzinfo is None:
            raise ValueError("IssuedToken.expires_at 은 tz-aware 여야 함 (timezone 미부여 시 만료 판정 오차)")

    def authorization_header(self) -> str:
        return f"{self.token_type.capitalize()} {self.token}"

    def is_expired(self, *, margin_seconds: float = 300.0) -> bool:
        """만료 마진(5분) 이전부터 expired=True. 자동 재발급 마진.

        margin_seconds 는 음수 허용 — 만료 후 일정 시간까지 expired=False 의미.
        """
        tz = self.expires_at.tzinfo
        # __post_init__ 가드로 tz 는 항상 설정됨. mypy 만 만족.
        now = datetime.now(tz if tz is not None else UTC)
        return (self.expires_at - now).total_seconds() < margin_seconds

    def __repr__(self) -> str:
        return f"IssuedToken(token=<masked>, token_type={self.token_type}, expires_at={self.expires_at.isoformat()})"


@dataclass(frozen=True, slots=True)
class MaskedKiwoomCredentialView:
    """외부 응답용 — appkey 는 tail 4자리 노출, secretkey 는 전체 마스킹."""

    alias: str
    env: str
    appkey_masked: str
    secretkey_masked: str
    is_active: bool
    key_version: int


def mask_appkey(value: str, *, keep: int = 4) -> str:
    """appkey 마스킹 — `••••` × (len-keep) + tail keep 자리."""
    if len(value) <= keep:
        return "•" * len(value)
    return "•" * (len(value) - keep) + value[-keep:]


def mask_secretkey(value: str) -> str:
    """secretkey 는 전체 마스킹 — 어떤 글자도 노출 금지. 고정 길이 출력."""
    return "•" * 16
