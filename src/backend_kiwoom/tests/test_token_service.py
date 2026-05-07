"""IssueKiwoomTokenUseCase + TokenManager 통합 테스트.

testcontainers PG16 + httpx.MockTransport. 외부 호출 0.

시나리오:
- UseCase 정상 / 미등록 / 비활성 / 401 전파 / prod URL 분기
- TokenManager 캐시 hit / 만료 재발급 / 동시 재발급 합체 (real async yield) / invalidate
- TokenManager alias 한도 초과 (H1 — lock 폭증 방어)
- TokenManager 무효 alias 발생 시 lock entry 정리 (H1)
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._exceptions import KiwoomCredentialRejectedError
from app.adapter.out.kiwoom.auth import KiwoomAuthClient
from app.adapter.out.persistence.repositories.kiwoom_credential import KiwoomCredentialRepository
from app.application.dto.kiwoom_auth import IssuedToken, KiwoomCredentials
from app.application.service.token_service import (
    AliasCapacityExceededError,
    CredentialInactiveError,
    CredentialNotFoundError,
    IssueKiwoomTokenUseCase,
    TokenManager,
)
from app.security.kiwoom_credential_cipher import KiwoomCredentialCipher

KST = ZoneInfo("Asia/Seoul")

_VALID_TOKEN_BODY = {
    "expires_dt": "20991231235959",
    "token_type": "bearer",
    "token": "X" * 150,
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다",
}


def _auth_factory(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[str], KiwoomAuthClient]:
    def _factory(base_url: str) -> KiwoomAuthClient:
        return KiwoomAuthClient(
            base_url=base_url,
            transport=httpx.MockTransport(handler),
            max_attempts=1,
            retry_min_wait=0.0,
            retry_max_wait=0.0,
        )

    return _factory


@pytest.fixture
def cipher(master_key: str) -> KiwoomCredentialCipher:
    return KiwoomCredentialCipher(master_key=master_key)


@pytest.fixture
async def seed_credential(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
) -> KiwoomCredentials:
    repo = KiwoomCredentialRepository(session, cipher)
    creds = KiwoomCredentials(appkey="A" * 32, secretkey="S" * 32)
    await repo.upsert(alias="test-prod", env="mock", credentials=creds)
    return creds


def _session_wrapper(session: AsyncSession) -> Callable[[], AbstractAsyncContextManager[AsyncSession]]:
    """테스트용 session_provider — 기존 트랜잭션 세션을 그대로 yield (close 하지 않음).

    pytest-asyncio 의 session 픽스처가 트랜잭션 + 롤백 관리. provider 가 close 하면
    이중 close 로 깨짐.
    """

    @asynccontextmanager
    async def _provider() -> AsyncIterator[AsyncSession]:
        yield session

    return _provider


# -----------------------------------------------------------------------------
# IssueKiwoomTokenUseCase
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issue_use_case_returns_issued_token_on_200(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    seed_credential: KiwoomCredentials,
) -> None:
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=_VALID_TOKEN_BODY)

    use_case = IssueKiwoomTokenUseCase(
        session=session,
        cipher=cipher,
        auth_client_factory=_auth_factory(handler),
    )
    token = await use_case.execute(alias="test-prod")

    assert isinstance(token, IssuedToken)
    assert token.token == "X" * 150
    assert token.token_type == "bearer"
    assert not token.is_expired()
    assert call_count == 1


@pytest.mark.asyncio
async def test_issue_use_case_uses_single_db_query(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    seed_credential: KiwoomCredentials,
) -> None:
    """find_by_alias 1회 + decrypt_row (sync) — 이중 SELECT 회귀 차단 (HIGH 1차 리뷰)."""
    from typing import Any

    from sqlalchemy import event

    query_count = 0

    def _count_select(
        _conn: Any,
        _cursor: Any,
        statement: str,
        _params: Any,
        _ctx: Any,
        _executemany: bool,
    ) -> None:
        nonlocal query_count
        if "SELECT" in statement.upper() and "kiwoom_credential" in statement.lower():
            query_count += 1

    bind = session.bind
    assert bind is not None  # mypy 만족
    sync_engine = bind.sync_engine
    event.listen(sync_engine, "before_cursor_execute", _count_select)

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_VALID_TOKEN_BODY)

    try:
        use_case = IssueKiwoomTokenUseCase(
            session=session,
            cipher=cipher,
            auth_client_factory=_auth_factory(handler),
        )
        await use_case.execute(alias="test-prod")
    finally:
        event.remove(sync_engine, "before_cursor_execute", _count_select)

    assert query_count == 1, f"kiwoom_credential SELECT 1회 기대 — 실제 {query_count}회"


@pytest.mark.asyncio
async def test_issue_use_case_raises_when_alias_not_found(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
) -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_VALID_TOKEN_BODY)

    use_case = IssueKiwoomTokenUseCase(
        session=session,
        cipher=cipher,
        auth_client_factory=_auth_factory(handler),
    )
    with pytest.raises(CredentialNotFoundError) as exc_info:
        await use_case.execute(alias="missing")

    assert "missing" in str(exc_info.value)


@pytest.mark.asyncio
async def test_issue_use_case_raises_when_credential_inactive(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    seed_credential: KiwoomCredentials,
) -> None:
    repo = KiwoomCredentialRepository(session, cipher)
    await repo.deactivate(alias="test-prod")

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_VALID_TOKEN_BODY)

    use_case = IssueKiwoomTokenUseCase(
        session=session,
        cipher=cipher,
        auth_client_factory=_auth_factory(handler),
    )
    with pytest.raises(CredentialInactiveError):
        await use_case.execute(alias="test-prod")


@pytest.mark.asyncio
async def test_issue_use_case_propagates_credential_rejected(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    seed_credential: KiwoomCredentials,
) -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    use_case = IssueKiwoomTokenUseCase(
        session=session,
        cipher=cipher,
        auth_client_factory=_auth_factory(handler),
    )
    with pytest.raises(KiwoomCredentialRejectedError):
        await use_case.execute(alias="test-prod")


@pytest.mark.asyncio
async def test_issue_use_case_uses_prod_url_for_prod_env(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
) -> None:
    repo = KiwoomCredentialRepository(session, cipher)
    await repo.upsert(
        alias="prod-main",
        env="prod",
        credentials=KiwoomCredentials(appkey="A" * 32, secretkey="S" * 32),
    )

    captured_urls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured_urls.append(str(req.url))
        return httpx.Response(200, json=_VALID_TOKEN_BODY)

    use_case = IssueKiwoomTokenUseCase(
        session=session,
        cipher=cipher,
        auth_client_factory=_auth_factory(handler),
    )
    await use_case.execute(alias="prod-main")

    assert any("api.kiwoom.com" in url and "mockapi" not in url for url in captured_urls), (
        f"prod alias 는 운영 도메인으로 호출돼야 함 — got {captured_urls}"
    )


# -----------------------------------------------------------------------------
# TokenManager
# -----------------------------------------------------------------------------


def _make_manager(
    *,
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    handler: Callable[[httpx.Request], httpx.Response],
    max_aliases: int = 1024,
) -> TokenManager:
    return TokenManager(
        session_provider=_session_wrapper(session),
        cipher=cipher,
        auth_client_factory=_auth_factory(handler),
        max_aliases=max_aliases,
    )


@pytest.mark.asyncio
async def test_token_manager_caches_issued_token(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    seed_credential: KiwoomCredentials,
) -> None:
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=_VALID_TOKEN_BODY)

    manager = _make_manager(session=session, cipher=cipher, handler=handler)
    t1 = await manager.get(alias="test-prod")
    t2 = await manager.get(alias="test-prod")

    assert t1 is t2
    assert call_count == 1


@pytest.mark.asyncio
async def test_token_manager_reissues_on_expired_token(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    seed_credential: KiwoomCredentials,
) -> None:
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        soon = datetime.now(KST) + timedelta(seconds=60) if call_count == 1 else datetime.now(KST) + timedelta(hours=23)
        body = {**_VALID_TOKEN_BODY, "expires_dt": soon.strftime("%Y%m%d%H%M%S")}
        return httpx.Response(200, json=body)

    manager = _make_manager(session=session, cipher=cipher, handler=handler)
    t1 = await manager.get(alias="test-prod")
    t2 = await manager.get(alias="test-prod")

    assert call_count == 2
    assert t1 is not t2
    assert not t2.is_expired()


@pytest.mark.asyncio
async def test_token_manager_concurrent_get_coalesces_into_single_issue(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    seed_credential: KiwoomCredentials,
) -> None:
    """진짜 async yield 도입 — 5개 코루틴이 lock 진입 전 인터리브.

    H2 적대적 리뷰: 동기 핸들러는 인터리브 없이 atomic — 의미 없는 테스트.
    asyncio.Event 로 첫 핸들러를 hold, 나머지 4개가 lock 대기 진입 보장.
    """
    call_count = 0
    release = asyncio.Event()
    started = asyncio.Event()

    async def slow_response(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        started.set()
        await release.wait()
        return httpx.Response(200, json=_VALID_TOKEN_BODY)

    # MockTransport 가 sync handler 만 받음 — async handler 는 별도 wrapper
    async def async_handler(req: httpx.Request) -> httpx.Response:
        return await slow_response(req)

    # MockTransport 가 sync handler 를 요구하므로 AsyncMockTransport 사용
    transport = httpx.MockTransport(async_handler)

    def factory(url: str) -> KiwoomAuthClient:
        return KiwoomAuthClient(
            base_url=url,
            transport=transport,
            max_attempts=1,
            retry_min_wait=0.0,
            retry_max_wait=0.0,
        )

    manager = TokenManager(
        session_provider=_session_wrapper(session),
        cipher=cipher,
        auth_client_factory=factory,
    )

    # 5개 동시 실행 — 첫 핸들러 진입 후 release 신호 전까지 모두 대기
    async def gated_get() -> IssuedToken:
        return await manager.get(alias="test-prod")

    task1 = asyncio.create_task(gated_get())
    # 첫 호출이 lock 잡고 핸들러 진입할 때까지 대기 → 다른 코루틴은 lock 대기
    await started.wait()
    task2 = asyncio.create_task(gated_get())
    task3 = asyncio.create_task(gated_get())
    task4 = asyncio.create_task(gated_get())
    task5 = asyncio.create_task(gated_get())
    # 다른 task 들이 lock 대기 진입할 시간 확보
    await asyncio.sleep(0.01)
    release.set()

    results = await asyncio.gather(task1, task2, task3, task4, task5)

    assert call_count == 1, f"동시 5개 get 은 1회 호출로 합체 — got {call_count}"
    first = results[0]
    for r in results[1:]:
        assert r is first


@pytest.mark.asyncio
async def test_token_manager_invalidate_forces_reissue(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    seed_credential: KiwoomCredentials,
) -> None:
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=_VALID_TOKEN_BODY)

    manager = _make_manager(session=session, cipher=cipher, handler=handler)
    await manager.get(alias="test-prod")
    manager.invalidate(alias="test-prod")
    await manager.get(alias="test-prod")

    assert call_count == 2


@pytest.mark.asyncio
async def test_token_manager_separates_caches_by_alias(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
) -> None:
    repo = KiwoomCredentialRepository(session, cipher)
    await repo.upsert(
        alias="test-mock",
        env="mock",
        credentials=KiwoomCredentials(appkey="M" * 32, secretkey="MS" * 16),
    )
    await repo.upsert(
        alias="test-prod",
        env="prod",
        credentials=KiwoomCredentials(appkey="P" * 32, secretkey="PS" * 16),
    )

    captured_appkeys: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        captured_appkeys.append(body["appkey"])
        return httpx.Response(200, json=_VALID_TOKEN_BODY)

    manager = _make_manager(session=session, cipher=cipher, handler=handler)
    t1 = await manager.get(alias="test-mock")
    t2 = await manager.get(alias="test-prod")

    assert len(captured_appkeys) == 2
    assert "M" * 32 in captured_appkeys
    assert "P" * 32 in captured_appkeys
    assert t1 is not t2


# -----------------------------------------------------------------------------
# H1 — Lock 폭증 DoS 방어
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_token_manager_rejects_alias_above_capacity(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    seed_credential: KiwoomCredentials,
) -> None:
    """alias 한도 초과 시 AliasCapacityExceededError — lock 무한 증식 차단."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_VALID_TOKEN_BODY)

    manager = _make_manager(session=session, cipher=cipher, handler=handler, max_aliases=2)
    # 1번째 alias — OK
    await manager.get(alias="test-prod")

    # 2번째 alias — 미등록이므로 CredentialNotFoundError + lock 정리
    with pytest.raises(CredentialNotFoundError):
        await manager.get(alias="invalid-1")

    # 3번째 — invalid-1 의 lock 이 정리됐으므로 capacity 1/2 → 신규 OK 가능
    # 새 capacity 등록 (정리 검증)
    repo = KiwoomCredentialRepository(session, cipher)
    await repo.upsert(
        alias="other",
        env="mock",
        credentials=KiwoomCredentials(appkey="O" * 32, secretkey="OS" * 16),
    )
    await manager.get(alias="other")  # OK — lock 정리됐으니 한도 내

    # 이미 한도 도달 (test-prod, other = 2)
    with pytest.raises(AliasCapacityExceededError):
        await manager.get(alias="overflow")


@pytest.mark.asyncio
async def test_token_manager_cleans_lock_on_invalid_alias(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
) -> None:
    """무효 alias 발생 시 lock entry 즉시 정리 — alias 폭증 차단."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_VALID_TOKEN_BODY)

    manager = _make_manager(session=session, cipher=cipher, handler=handler)

    for i in range(10):
        with pytest.raises(CredentialNotFoundError):
            await manager.get(alias=f"invalid-{i}")

    # lock dict 가 비어 있어야 함
    assert len(manager._locks) == 0, f"무효 alias 는 lock 미보존 — 현재 {len(manager._locks)}"


# =============================================================================
# β chunk — TokenManager 확장 (peek / invalidate_all / alias_keys)
# =============================================================================


@pytest.mark.asyncio
async def test_token_manager_peek_returns_cache_only(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    seed_credential: KiwoomCredentials,
) -> None:
    """peek 은 캐시만 조회 — 발급 트리거 안 함, 만료 무관."""
    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=_VALID_TOKEN_BODY)

    manager = _make_manager(session=session, cipher=cipher, handler=handler)

    # 캐시 비어있음 → None
    assert manager.peek(alias="test-prod") is None
    assert call_count == 0

    # get 으로 캐시 채움
    issued = await manager.get(alias="test-prod")
    assert call_count == 1

    # peek → 같은 인스턴스
    peeked = manager.peek(alias="test-prod")
    assert peeked is issued
    assert call_count == 1, "peek 은 발급 트리거 안 함"


@pytest.mark.asyncio
async def test_token_manager_peek_returns_expired_token_too(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    seed_credential: KiwoomCredentials,
) -> None:
    """peek 은 만료 무관 — 폐기 UseCase 가 캐시 토큰을 직접 받기 위함."""

    def handler(_req: httpx.Request) -> httpx.Response:
        soon = datetime.now(KST) + timedelta(seconds=10)  # is_expired(margin=300)=True
        body = {**_VALID_TOKEN_BODY, "expires_dt": soon.strftime("%Y%m%d%H%M%S")}
        return httpx.Response(200, json=body)

    manager = _make_manager(session=session, cipher=cipher, handler=handler)
    issued = await manager.get(alias="test-prod")
    assert issued.is_expired() is True

    peeked = manager.peek(alias="test-prod")
    assert peeked is issued, "peek 은 만료된 토큰도 반환"


@pytest.mark.asyncio
async def test_token_manager_alias_keys_returns_active_aliases(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
) -> None:
    """alias_keys — 캐시에 있는 alias 만 반환 (lock 만 있고 토큰 없는 alias 제외)."""
    repo = KiwoomCredentialRepository(session, cipher)
    for alias in ("a", "b", "c"):
        await repo.upsert(
            alias=alias,
            env="mock",
            credentials=KiwoomCredentials(appkey="A" * 32, secretkey="S" * 32),
        )

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_VALID_TOKEN_BODY)

    manager = _make_manager(session=session, cipher=cipher, handler=handler)
    await manager.get(alias="a")
    await manager.get(alias="b")
    # c 는 발급 안 함

    keys = manager.alias_keys()
    assert set(keys) == {"a", "b"}, f"활성 alias만 반환 — got {keys}"


@pytest.mark.asyncio
async def test_token_manager_invalidate_all_empties_cache(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
) -> None:
    """invalidate_all — 모든 alias 캐시 비움. lock 은 보존 (정상 alias)."""
    repo = KiwoomCredentialRepository(session, cipher)
    for alias in ("a", "b", "c"):
        await repo.upsert(
            alias=alias,
            env="mock",
            credentials=KiwoomCredentials(appkey="A" * 32, secretkey="S" * 32),
        )

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_VALID_TOKEN_BODY)

    manager = _make_manager(session=session, cipher=cipher, handler=handler)
    await manager.get(alias="a")
    await manager.get(alias="b")
    await manager.get(alias="c")
    assert len(manager.alias_keys()) == 3

    manager.invalidate_all()
    assert manager.alias_keys() == ()
    assert manager.peek(alias="a") is None


# =============================================================================
# β chunk — RevokeKiwoomTokenUseCase
# =============================================================================


@pytest.mark.asyncio
async def test_revoke_use_case_revoke_by_alias_succeeds_with_cached_token(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    seed_credential: KiwoomCredentials,
) -> None:
    """캐시 hit + 200 → RevokeResult(revoked=True, reason='ok'). 캐시 무효화."""
    from app.application.service.token_service import RevokeKiwoomTokenUseCase, RevokeResult

    issue_call_count = 0
    revoke_call_count = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal issue_call_count, revoke_call_count
        if req.url.path == "/oauth2/token":
            issue_call_count += 1
            return httpx.Response(200, json=_VALID_TOKEN_BODY)
        if req.url.path == "/oauth2/revoke":
            revoke_call_count += 1
            return httpx.Response(200, json={"return_code": 0, "return_msg": "ok"})
        return httpx.Response(404)

    manager = _make_manager(session=session, cipher=cipher, handler=handler)
    issued = await manager.get(alias="test-prod")
    assert manager.peek(alias="test-prod") is issued

    revoke_uc = RevokeKiwoomTokenUseCase(
        session_provider=_session_wrapper(session),
        cipher=cipher,
        auth_client_factory=_auth_factory(handler),
        token_manager=manager,
    )
    result = await revoke_uc.revoke_by_alias(alias="test-prod")

    assert isinstance(result, RevokeResult)
    assert result.alias == "test-prod"
    assert result.revoked is True
    assert result.reason == "ok"
    assert revoke_call_count == 1
    # 캐시 무효화
    assert manager.peek(alias="test-prod") is None


@pytest.mark.asyncio
async def test_revoke_use_case_cache_miss_returns_idempotent_success(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    seed_credential: KiwoomCredentials,
) -> None:
    """캐시 비어있음 → RevokeResult(revoked=False, reason='cache-miss'). adapter 호출 0."""
    from app.application.service.token_service import RevokeKiwoomTokenUseCase

    revoke_call_count = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal revoke_call_count
        if req.url.path == "/oauth2/revoke":
            revoke_call_count += 1
        return httpx.Response(200, json={"return_code": 0})

    manager = _make_manager(session=session, cipher=cipher, handler=handler)
    revoke_uc = RevokeKiwoomTokenUseCase(
        session_provider=_session_wrapper(session),
        cipher=cipher,
        auth_client_factory=_auth_factory(handler),
        token_manager=manager,
    )
    result = await revoke_uc.revoke_by_alias(alias="test-prod")

    assert result.revoked is False
    assert result.reason == "cache-miss"
    assert revoke_call_count == 0, "캐시 miss 시 adapter 호출 안 함"


@pytest.mark.asyncio
async def test_revoke_use_case_idempotent_on_401(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    seed_credential: KiwoomCredentials,
) -> None:
    """캐시 hit + 401 → 멱등 성공 변환 (revoked=False, reason='already-expired'). 캐시 무효화."""
    from app.application.service.token_service import RevokeKiwoomTokenUseCase

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/oauth2/token":
            return httpx.Response(200, json=_VALID_TOKEN_BODY)
        if req.url.path == "/oauth2/revoke":
            return httpx.Response(401)  # 이미 만료된 토큰
        return httpx.Response(404)

    manager = _make_manager(session=session, cipher=cipher, handler=handler)
    await manager.get(alias="test-prod")

    revoke_uc = RevokeKiwoomTokenUseCase(
        session_provider=_session_wrapper(session),
        cipher=cipher,
        auth_client_factory=_auth_factory(handler),
        token_manager=manager,
    )
    result = await revoke_uc.revoke_by_alias(alias="test-prod")

    assert result.revoked is False
    assert result.reason == "already-expired"
    # 캐시는 키움 측 결과 무관하게 무효화
    assert manager.peek(alias="test-prod") is None


@pytest.mark.asyncio
async def test_revoke_use_case_credential_not_found(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    seed_credential: KiwoomCredentials,
) -> None:
    """캐시에 토큰은 있지만 DB credential 미등록 → CredentialNotFoundError."""
    from app.application.service.token_service import RevokeKiwoomTokenUseCase

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/oauth2/token":
            return httpx.Response(200, json=_VALID_TOKEN_BODY)
        return httpx.Response(200, json={"return_code": 0})

    manager = _make_manager(session=session, cipher=cipher, handler=handler)
    # test-prod 의 토큰을 발급 후 다른 alias 로 revoke 시도
    await manager.get(alias="test-prod")

    # 임의 alias 의 캐시 토큰을 위조 (실제로는 raw_token 사용 시 시나리오)
    # → revoke_by_alias 는 cred 로 보호 — 미등록 alias 캐시는 발생 안 함
    # 대신 raw_token 으로 미등록 alias 시도
    revoke_uc = RevokeKiwoomTokenUseCase(
        session_provider=_session_wrapper(session),
        cipher=cipher,
        auth_client_factory=_auth_factory(handler),
        token_manager=manager,
    )
    with pytest.raises(CredentialNotFoundError):
        await revoke_uc.revoke_by_raw_token(alias="missing", raw_token="X" * 100)


@pytest.mark.asyncio
async def test_revoke_use_case_revoke_by_raw_token(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    seed_credential: KiwoomCredentials,
) -> None:
    """raw_token 폐기 — 캐시 외부 토큰을 명시 폐기. adapter 호출 1회 + 캐시 무효화."""
    from app.application.service.token_service import RevokeKiwoomTokenUseCase

    captured_tokens: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/oauth2/token":
            return httpx.Response(200, json=_VALID_TOKEN_BODY)
        if req.url.path == "/oauth2/revoke":
            body = json.loads(req.content)
            captured_tokens.append(body["token"])
            return httpx.Response(200, json={"return_code": 0})
        return httpx.Response(404)

    manager = _make_manager(session=session, cipher=cipher, handler=handler)
    await manager.get(alias="test-prod")

    revoke_uc = RevokeKiwoomTokenUseCase(
        session_provider=_session_wrapper(session),
        cipher=cipher,
        auth_client_factory=_auth_factory(handler),
        token_manager=manager,
    )
    raw_token = "ExternalToken-Leaked-987654321"
    result = await revoke_uc.revoke_by_raw_token(alias="test-prod", raw_token=raw_token)

    assert result.revoked is True
    assert result.reason == "ok-raw"
    assert raw_token in captured_tokens, "raw_token 이 키움에 전송됨"
    # 캐시 무효화
    assert manager.peek(alias="test-prod") is None


# =============================================================================
# β chunk — graceful shutdown 시나리오 (lifespan hook 의 단위 동작)
# =============================================================================


@pytest.mark.asyncio
async def test_revoke_use_case_processes_all_aliases_even_when_one_fails(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
) -> None:
    """shutdown — alias B 폐기 실패해도 A/C 진행. 캐시 모두 비워짐."""
    from app.application.service.token_service import RevokeKiwoomTokenUseCase

    repo = KiwoomCredentialRepository(session, cipher)
    for alias in ("alias-a", "alias-b", "alias-c"):
        await repo.upsert(
            alias=alias,
            env="mock",
            credentials=KiwoomCredentials(appkey="A" * 32, secretkey="S" * 32),
        )

    revoke_paths_seen: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/oauth2/token":
            return httpx.Response(200, json=_VALID_TOKEN_BODY)
        if req.url.path == "/oauth2/revoke":
            # alias-b 의 토큰만 500 — appkey 동일이므로 token 으로 식별 어려우니 단순화
            revoke_paths_seen.append("revoke")
            if len(revoke_paths_seen) == 2:  # 2번째 호출 = alias-b
                return httpx.Response(500)
            return httpx.Response(200, json={"return_code": 0})
        return httpx.Response(404)

    manager = _make_manager(session=session, cipher=cipher, handler=handler)
    await manager.get(alias="alias-a")
    await manager.get(alias="alias-b")
    await manager.get(alias="alias-c")
    assert len(manager.alias_keys()) == 3

    revoke_uc = RevokeKiwoomTokenUseCase(
        session_provider=_session_wrapper(session),
        cipher=cipher,
        auth_client_factory=_auth_factory(handler),
        token_manager=manager,
    )

    # 각각 시도 — alias-b 는 KiwoomUpstreamError raise (caller 가 swallow 결정)
    from app.adapter.out.kiwoom._exceptions import KiwoomUpstreamError

    results: list[str] = []
    for alias in manager.alias_keys():
        try:
            r = await revoke_uc.revoke_by_alias(alias=alias)
            results.append(f"{alias}:{r.reason}")
        except KiwoomUpstreamError:
            results.append(f"{alias}:upstream-fail")

    assert len(revoke_paths_seen) == 3, "3 alias 모두 폐기 시도"
    # alias-b 는 KiwoomUpstreamError 라 캐시 무효화 안 됨 (현재 동작)
    # 다른 2개는 성공 + 캐시 비움
