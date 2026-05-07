"""키움 인증 도메인 값 객체.

설계: endpoint-01-au10001.md § 6.2.

- KiwoomCredentials: 평문 자격증명. UseCase 스코프 안에서만 존재.
- IssuedToken: 발급된 토큰 + 만료 시각 (KST 가정).
- MaskedKiwoomCredentialView: 외부 노출용 — secretkey 는 어떤 경로로도 평문 노출 안 됨.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import NoReturn, SupportsIndex
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True, slots=True)
class KiwoomCredentials:
    """평문 자격증명. __repr__ 가 secretkey 마스킹.

    원칙: caller 가 dict() 로 변환해 logger 에 넘기지 않음. dataclass 자체로만 전달.

    직렬화 차단 (ADR-0001 § 3 #2, 적대적 리뷰 CRITICAL-1 반영):
    - `__reduce__`/`__reduce_ex__` raise → pickle.dumps 차단
    - `__getstate__`/`__setstate__` raise → Python 3.10+ slots dataclass 자동 생성 메서드 우회 차단.
      jsonpickle/dill/cloudpickle/Celery 등 외부 라이브러리가 `__getstate__()` 를 직접 호출해도 차단.
    - `__copy__`/`__deepcopy__` 는 허용 (도메인 내부 복제는 정당)
    - dataclasses.asdict 는 호출 가능 — 결과를 logger 로 넘기면 structlog `_scan` 이 secretkey 키를
      [MASKED] 처리. 2층 방어.
    - slots=True 로 vars()/__dict__ 는 자연 차단
    """

    appkey: str
    secretkey: str

    def __repr__(self) -> str:
        tail = self.appkey[-4:] if len(self.appkey) >= 4 else "****"
        return f"KiwoomCredentials(appkey=••••{tail}, secretkey=<masked>)"

    def __reduce__(self) -> NoReturn:
        # __reduce_ex__ 가 항상 먼저 호출 — 도달 불가하지만 명시적 방어 (서브클래스가
        # __reduce_ex__ 를 미정의하는 경우에도 차단).
        raise TypeError(
            "KiwoomCredentials serialization is blocked — "
            "pickle 직렬화는 secretkey 평문 노출 위험."
        )

    def __reduce_ex__(self, protocol: SupportsIndex) -> NoReturn:
        raise TypeError(
            "KiwoomCredentials serialization is blocked — "
            "pickle 직렬화는 secretkey 평문 노출 위험."
        )

    def __getstate__(self) -> NoReturn:
        # Python 3.10+ slots dataclass 자동 생성 차단 — jsonpickle/dill 등 우회 방어.
        raise TypeError(
            "KiwoomCredentials state extraction is blocked — "
            "secretkey 평문 누설 위험 (pickle/jsonpickle/dill 우회 차단)."
        )

    def __setstate__(self, state: object) -> NoReturn:
        raise TypeError(
            "KiwoomCredentials state restoration is blocked — "
            "역직렬화 경로의 객체 재구성 차단."
        )

    def __copy__(self) -> KiwoomCredentials:
        """copy.copy 명시 정의 — `__reduce_ex__` raise 우회. 도메인 내부 복제는 정당."""
        return KiwoomCredentials(appkey=self.appkey, secretkey=self.secretkey)

    def __deepcopy__(self, memo: dict[int, object]) -> KiwoomCredentials:
        """copy.deepcopy 명시 정의 — str 은 immutable. memo 갱신 (deepcopy 표준 컨트랙트)."""
        result = KiwoomCredentials(appkey=self.appkey, secretkey=self.secretkey)
        memo[id(self)] = result
        return result


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
