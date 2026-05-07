"""IssueKiwoomTokenUseCase + RevokeKiwoomTokenUseCase + TokenManager — application 계층.

설계: endpoint-01-au10001.md § 6.3 / 6.4 + endpoint-02-au10002.md § 6.2 / 6.3. 이중 리뷰 1R 반영.

책임:
- IssueKiwoomTokenUseCase: alias → DB credential 단일 쿼리 → 복호화 → 토큰 발급 → IssuedToken
- RevokeKiwoomTokenUseCase: alias/raw_token → DB credential → 키움 폐기 + 캐시 무효화 (best-effort)
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

폐기 멱등성:
- 401/403 → KiwoomCredentialRejectedError → UseCase 가 RevokeResult(revoked=False, reason='already-expired') 변환
- 캐시 miss → adapter 호출 0 + RevokeResult(revoked=False, reason='cache-miss')
- 5xx/네트워크 → KiwoomUpstreamError 전파 (caller 결정 — graceful shutdown 은 swallow)
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._exceptions import (
    KiwoomBusinessError,
    KiwoomCredentialRejectedError,
    KiwoomError,
    KiwoomUpstreamError,
)
from app.adapter.out.kiwoom.auth import KiwoomAuthClient
from app.adapter.out.persistence.repositories.kiwoom_credential import KiwoomCredentialRepository
from app.application.dto.kiwoom_auth import IssuedToken
from app.config.settings import get_settings
from app.security.kiwoom_credential_cipher import KiwoomCredentialCipher

logger = logging.getLogger(__name__)

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

    # =========================================================================
    # β chunk — peek / invalidate_all / alias_keys
    # =========================================================================

    def peek(self, *, alias: str) -> IssuedToken | None:
        """캐시만 조회. 만료 무관 — 폐기 UseCase 가 사용 (만료된 토큰도 폐기 시도).

        발급 트리거 안 함. lock 도 사용 안 함.
        """
        return self._cache.get(alias)

    def alias_keys(self) -> tuple[str, ...]:
        """현재 캐시된 alias 목록. graceful shutdown 의 polling 진입점.

        반환 시점의 snapshot — 동시에 다른 코루틴이 캐시 갱신 가능하지만
        shutdown hook 사용 가정 (다른 발급은 차단 안 함, best-effort 의미).
        """
        return tuple(self._cache.keys())

    def invalidate_all(self) -> None:
        """모든 alias 캐시 비움. lock entries 보존.

        graceful shutdown — 키움 측 폐기 호출 후 일괄 호출.
        """
        self._cache.clear()


# =============================================================================
# β chunk — RevokeKiwoomTokenUseCase
# =============================================================================


@dataclass(frozen=True, slots=True)
class RevokeResult:
    """폐기 결과 — 키움 측 실제 폐기 여부 + 이유.

    revoked=True: 키움이 200 + return_code=0 응답 (정상 폐기)
    revoked=False + reason='cache-miss': 캐시에 토큰 없음, adapter 호출 0
    revoked=False + reason='already-expired': 401/403 → 멱등 성공 (이미 만료/폐기)
    revoked=True + reason='ok-raw': revoke_by_raw_token 정상
    """

    alias: str
    revoked: bool
    reason: str


class RevokeKiwoomTokenUseCase:
    """캐시 토큰 또는 외부 raw 토큰을 키움에 폐기 + 로컬 캐시 무효화.

    설계 (endpoint-02-au10002.md § 6.2):
    - revoke_by_alias: 캐시에 토큰 있을 때만 키움 호출. 없으면 cache-miss 멱등 응답
    - revoke_by_raw_token: 외부 노출된 토큰을 명시 폐기 (운영 사고 대응)
    - 401/403 → 멱등 성공 (already-expired) 변환. caller 가 5xx 는 별도 처리
    - 캐시 무효화는 키움 응답 무관 — finally 블록에서 보장
    """

    def __init__(
        self,
        *,
        session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
        cipher: KiwoomCredentialCipher,
        auth_client_factory: Callable[[str], KiwoomAuthClient],
        token_manager: TokenManager,
    ) -> None:
        self._session_provider = session_provider
        self._cipher = cipher
        self._auth_client_factory = auth_client_factory
        self._token_manager = token_manager

    async def revoke_by_alias(self, *, alias: str) -> RevokeResult:
        """캐시 hit → 키움 폐기 + 캐시 무효화. 캐시 miss → cache-miss 멱등 응답."""
        cached = self._token_manager.peek(alias=alias)
        if cached is None:
            logger.info("revoke skipped: alias=%s cache-miss", alias)
            return RevokeResult(alias=alias, revoked=False, reason="cache-miss")

        async with self._session_provider() as session:
            cred_repo = KiwoomCredentialRepository(session, self._cipher)
            cred_row = await cred_repo.find_by_alias(alias)
            if cred_row is None:
                raise CredentialNotFoundError(f"alias={alias!r} 미등록")
            creds = cred_repo.decrypt_row(cred_row)
            settings = get_settings()
            base_url = settings.kiwoom_base_url_prod if cred_row.env == "prod" else settings.kiwoom_base_url_mock

        try:
            async with self._auth_client_factory(base_url) as client:
                await client.revoke_token(creds, cached.token)
        except KiwoomCredentialRejectedError:
            # 이미 만료/폐기된 토큰 — 멱등 성공 변환
            logger.info("revoke 401/403 → idempotent: alias=%s", alias)
            self._token_manager.invalidate(alias=alias)
            return RevokeResult(alias=alias, revoked=False, reason="already-expired")
        except (KiwoomUpstreamError, KiwoomBusinessError):
            # 5xx/business — 캐시 무효화 후 caller 에 전파 (caller best-effort 결정)
            self._token_manager.invalidate(alias=alias)
            raise

        # 정상 폐기
        self._token_manager.invalidate(alias=alias)
        return RevokeResult(alias=alias, revoked=True, reason="ok")

    async def revoke_by_raw_token(self, *, alias: str, raw_token: str) -> RevokeResult:
        """캐시 외부 토큰을 명시 폐기 — 운영 사고 대응.

        예: 토큰이 외부 로그에 노출됨 → 운영자가 평문으로 들고 와서 즉시 폐기 요청.

        혀명성 정책 (H-2/M-5 적대적 리뷰):
        - 401/403 → RevokeResult(revoked=False, reason='already-expired-raw') 변환
          (raw_token 이 이미 만료/폐기된 경우 — 운영 사고 대응 시 정상 시나리오)
        - 5xx/business → 캐시 무효화 후 caller 에 전파
        - cache 무효화는 키움 결과 무관 — invalidate 를 method 시작 직후로 이동 (M-1)
        """
        # M-1 적대적 리뷰: 키움 호출 전에 invalidate — decrypt 실패해도 캐시는 비워짐
        self._token_manager.invalidate(alias=alias)

        async with self._session_provider() as session:
            cred_repo = KiwoomCredentialRepository(session, self._cipher)
            cred_row = await cred_repo.find_by_alias(alias)
            if cred_row is None:
                raise CredentialNotFoundError(f"alias={alias!r} 미등록")
            creds = cred_repo.decrypt_row(cred_row)
            settings = get_settings()
            base_url = settings.kiwoom_base_url_prod if cred_row.env == "prod" else settings.kiwoom_base_url_mock

        try:
            async with self._auth_client_factory(base_url) as client:
                await client.revoke_token(creds, raw_token)
        except KiwoomCredentialRejectedError:
            # H-2/M-5: raw_token 이 이미 만료/폐기 — 멱등 성공 변환 (revoke_by_alias 와 동일 정책)
            logger.info("revoke_raw 401/403 → idempotent: alias=%s", alias)
            return RevokeResult(alias=alias, revoked=False, reason="already-expired-raw")

        return RevokeResult(alias=alias, revoked=True, reason="ok-raw")


async def revoke_all_aliases_best_effort(
    *,
    manager: TokenManager,
    revoke_use_case: RevokeKiwoomTokenUseCase,
) -> None:
    """graceful shutdown — 활성 alias 전부 폐기 시도. 한 alias 실패해도 다른 alias 진행.

    설계 (endpoint-02-au10002.md § 7.2):
    - 각 alias 별 polling — 폐기 성공 / 멱등 / 실패 무관하게 다음으로 진행
    - 5xx 또는 KiwoomError 발생 시 경고 로그 + 해당 alias 캐시 무효화 후 계속
    - 종료 직전 invalidate_all — 모든 캐시 비움 보장 (좀비 토큰 시간 최소화)
    """
    for alias in manager.alias_keys():
        try:
            await revoke_use_case.revoke_by_alias(alias=alias)
        except KiwoomError as exc:
            logger.warning(
                "shutdown 폐기 실패 alias=%s exc_type=%s — 키움 TTL 까지 활성",
                alias,
                type(exc).__name__,
            )
        except Exception as exc:  # noqa: BLE001 — graceful shutdown 은 모든 예외 swallow
            logger.warning(
                "shutdown 예기치 않은 오류 alias=%s exc_type=%s",
                alias,
                type(exc).__name__,
                exc_info=False,
            )
    manager.invalidate_all()
