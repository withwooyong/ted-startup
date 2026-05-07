"""IssueKiwoomTokenUseCase + TokenManager — au10001 발급 application 계층.

설계: endpoint-01-au10001.md § 6.3 / 6.4. 이중 리뷰 Round 1 반영.

책임:
- IssueKiwoomTokenUseCase: alias → DB credential 단일 쿼리 → 복호화 → 토큰 발급 → IssuedToken
- TokenManager: 프로세스 수명 캐시. alias 별 asyncio.Lock 으로 동시 재발급 합체

동시성:
- alias 별 Lock — 같은 alias 동시 재발급 1회로 합체
- 다른 alias 끼리는 병행 (Lock 분리)
- double-check pattern — 락 대기 중 갱신된 토큰 재사용
- `dict.setdefault` 로 lock 인스턴스 일관성 보장 (Python GIL atomic, H2 적대적 리뷰)

방어 (적대적 리뷰 H1):
- `_max_aliases` 캡 — 무한 lock 폭증 DoS 방어
- 무효 alias (CredentialNotFoundError) 발생 시 lock entry 즉시 정리 — 폭증 차단

세션 라이프사이클 (H4 적대적 리뷰):
- TokenManager 가 `session_provider` 주입 받아 매 발급마다 새 세션 생성 + 종료 보장
- IssueKiwoomTokenUseCase 는 외부에서 주입된 session 사용 (lifecycle 관여 X)

α chunk 범위: get / invalidate. peek / invalidate_all / alias_keys / RevokeKiwoomTokenUseCase 는 β.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom.auth import KiwoomAuthClient
from app.adapter.out.persistence.repositories.kiwoom_credential import KiwoomCredentialRepository
from app.application.dto.kiwoom_auth import IssuedToken
from app.config.settings import get_settings
from app.security.kiwoom_credential_cipher import KiwoomCredentialCipher

DEFAULT_MAX_ALIASES = 1024
"""TokenManager 의 alias 수 한도. 이 이상 신규 alias 거부 — H1 적대적 리뷰 lock 폭증 DoS 방어."""


class CredentialNotFoundError(Exception):
    """alias 미등록 — 라우터 매핑 404."""


class CredentialInactiveError(Exception):
    """is_active=False — 라우터 매핑 400."""


class AliasCapacityExceededError(Exception):
    """TokenManager alias 한도 초과 — 운영 모니터링 알람 + 라우터 매핑 503."""


class IssueKiwoomTokenUseCase:
    """credential alias → 단일 SELECT + 복호화 → au10001 호출 → IssuedToken.

    DB 토큰 캐시 사용 여부와 무관 — 캐시 레이어는 호출자(`TokenManager`) 책임.
    `find_by_alias` 로 fetch 한 row 를 바로 `decrypt_row` 에 넘김 — 이중 쿼리 회피 (HIGH 1차 리뷰).
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        cipher: KiwoomCredentialCipher,
        auth_client_factory: Callable[[str], KiwoomAuthClient],
    ) -> None:
        self._session = session
        self._cipher = cipher
        self._factory = auth_client_factory
        self._cred_repo = KiwoomCredentialRepository(session, cipher)

    async def execute(self, *, alias: str) -> IssuedToken:
        cred_row = await self._cred_repo.find_by_alias(alias)
        if cred_row is None:
            raise CredentialNotFoundError(f"alias={alias!r} 등록되지 않음")
        if not cred_row.is_active:
            raise CredentialInactiveError(f"alias={alias!r} 비활성 상태")

        creds = self._cred_repo.decrypt_row(cred_row)

        settings = get_settings()
        base_url = settings.kiwoom_base_url_prod if cred_row.env == "prod" else settings.kiwoom_base_url_mock
        async with self._factory(base_url) as client:
            resp = await client.issue_token(creds)
        return IssuedToken(
            token=resp.token,
            token_type=resp.token_type,
            expires_at=resp.expires_at_kst(),
        )


class TokenManager:
    """프로세스 수명 토큰 캐시. credential alias 단위 IssuedToken 보관.

    동시성 정책:
    - alias 별 asyncio.Lock — 같은 alias 동시 재발급 1회로 합체
    - 다른 alias 끼리는 병행 (Lock 분리)
    - double-check pattern — 락 대기 중 갱신된 토큰 재사용
    - `dict.setdefault` atomic (CPython GIL) — defaultdict race 회피 (H2)

    DoS 방어:
    - `max_aliases` 캡 — alias 폭증 거부 (H1)
    - 무효 alias 발생 시 lock entry 정리 — 누적 차단

    세션 라이프사이클:
    - `session_provider` 가 매 호출마다 AsyncSession 생성 + 종료 (H4)
    - 주입된 session 으로 UseCase 구성 → execute 종료 후 세션 자동 close
    """

    def __init__(
        self,
        *,
        session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
        cipher: KiwoomCredentialCipher,
        auth_client_factory: Callable[[str], KiwoomAuthClient],
        max_aliases: int = DEFAULT_MAX_ALIASES,
    ) -> None:
        self._session_provider = session_provider
        self._cipher = cipher
        self._auth_client_factory = auth_client_factory
        self._cache: dict[str, IssuedToken] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._max_aliases = max_aliases

    def _lock_for(self, alias: str) -> asyncio.Lock:
        """alias 별 lock 반환. 한도 초과 시 AliasCapacityExceededError.

        `dict.setdefault` 는 CPython GIL 보호 하 atomic — 같은 alias 의 동시 호출도 동일 인스턴스 반환.
        """
        existing = self._locks.get(alias)
        if existing is not None:
            return existing
        if len(self._locks) >= self._max_aliases:
            raise AliasCapacityExceededError(f"TokenManager alias 한도 {self._max_aliases} 초과 — alias 폭증 의심")
        return self._locks.setdefault(alias, asyncio.Lock())

    async def get(self, *, alias: str) -> IssuedToken:
        """alias 의 활성 토큰 반환. 만료 임박/미존재 시 재발급."""
        cached = self._cache.get(alias)
        if cached is not None and not cached.is_expired():
            return cached

        lock = self._lock_for(alias)
        async with lock:
            cached = self._cache.get(alias)
            if cached is not None and not cached.is_expired():
                return cached

            try:
                async with self._session_provider() as session:
                    uc = IssueKiwoomTokenUseCase(
                        session=session,
                        cipher=self._cipher,
                        auth_client_factory=self._auth_client_factory,
                    )
                    new_token = await uc.execute(alias=alias)
            except CredentialNotFoundError:
                # 무효 alias — lock entry 정리 (alias 폭증 차단, H1)
                self._locks.pop(alias, None)
                raise
            self._cache[alias] = new_token
            return new_token

    def invalidate(self, *, alias: str) -> None:
        """캐시 무효화 — 다음 get 시 강제 재발급. lock 은 보존 (정상 alias 라 가정)."""
        self._cache.pop(alias, None)
