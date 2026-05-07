"""FastAPI lifespan graceful shutdown 검증.

설계: endpoint-02-au10002.md § 7.2.

시나리오:
1. shutdown 시 활성 alias 전부 폐기 시도
2. 한 alias 폐기 실패해도 나머지 진행 (best-effort)
3. shutdown 후 invalidate_all — 캐시 비워짐
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom.auth import KiwoomAuthClient
from app.adapter.out.persistence.repositories.kiwoom_credential import KiwoomCredentialRepository
from app.application.dto.kiwoom_auth import KiwoomCredentials
from app.application.service.token_service import (
    RevokeKiwoomTokenUseCase,
    TokenManager,
    revoke_all_aliases_best_effort,
)
from app.security.kiwoom_credential_cipher import KiwoomCredentialCipher

_VALID_TOKEN_BODY = {
    "expires_dt": "20991231235959",
    "token_type": "bearer",
    "token": "X" * 150,
    "return_code": 0,
    "return_msg": "ok",
}


@pytest.fixture
def cipher(master_key: str) -> KiwoomCredentialCipher:
    return KiwoomCredentialCipher(master_key=master_key)


def _session_wrapper(session: AsyncSession) -> Callable[[], AbstractAsyncContextManager[AsyncSession]]:
    @asynccontextmanager
    async def _provider() -> AsyncIterator[AsyncSession]:
        yield session

    return _provider


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


@pytest.mark.asyncio
async def test_revoke_all_aliases_best_effort_revokes_all(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
) -> None:
    """shutdown — 활성 alias 3개 모두 폐기 시도 + 캐시 비워짐."""
    repo = KiwoomCredentialRepository(session, cipher)
    for alias in ("a", "b", "c"):
        await repo.upsert(
            alias=alias,
            env="mock",
            credentials=KiwoomCredentials(appkey="A" * 32, secretkey="S" * 32),
        )

    revoke_call_count = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal revoke_call_count
        if req.url.path == "/oauth2/token":
            return httpx.Response(200, json=_VALID_TOKEN_BODY)
        if req.url.path == "/oauth2/revoke":
            revoke_call_count += 1
            return httpx.Response(200, json={"return_code": 0})
        return httpx.Response(404)

    manager = TokenManager(
        session_provider=_session_wrapper(session),
        cipher=cipher,
        auth_client_factory=_auth_factory(handler),
    )
    await manager.get(alias="a")
    await manager.get(alias="b")
    await manager.get(alias="c")
    assert len(manager.alias_keys()) == 3

    revoke_uc = RevokeKiwoomTokenUseCase(
        session_provider=_session_wrapper(session),
        cipher=cipher,
        auth_client_factory=_auth_factory(handler),
        token_manager=manager,
    )

    await revoke_all_aliases_best_effort(manager=manager, revoke_use_case=revoke_uc)

    assert revoke_call_count == 3, "3 alias 모두 키움 폐기 시도"
    assert manager.alias_keys() == (), "캐시 모두 비워짐"


@pytest.mark.asyncio
async def test_revoke_all_aliases_continues_on_failure(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
) -> None:
    """alias-b 폐기 5xx 실패 → A/C 정상 진행. 캐시 모두 비워짐 (shutdown 보장)."""
    repo = KiwoomCredentialRepository(session, cipher)
    for alias in ("alias-a", "alias-b", "alias-c"):
        await repo.upsert(
            alias=alias,
            env="mock",
            credentials=KiwoomCredentials(appkey="A" * 32, secretkey="S" * 32),
        )

    captured_appkeys: list[str] = []
    revoke_attempts: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/oauth2/token":
            return httpx.Response(200, json=_VALID_TOKEN_BODY)
        if req.url.path == "/oauth2/revoke":
            body = json.loads(req.content)
            captured_appkeys.append(body["appkey"])
            attempt_idx = len(revoke_attempts)
            revoke_attempts.append("call")
            # 두 번째 호출만 5xx
            if attempt_idx == 1:
                return httpx.Response(500)
            return httpx.Response(200, json={"return_code": 0})
        return httpx.Response(404)

    manager = TokenManager(
        session_provider=_session_wrapper(session),
        cipher=cipher,
        auth_client_factory=_auth_factory(handler),
    )
    await manager.get(alias="alias-a")
    await manager.get(alias="alias-b")
    await manager.get(alias="alias-c")

    revoke_uc = RevokeKiwoomTokenUseCase(
        session_provider=_session_wrapper(session),
        cipher=cipher,
        auth_client_factory=_auth_factory(handler),
        token_manager=manager,
    )

    # best-effort — 실패해도 다른 alias 진행
    await revoke_all_aliases_best_effort(manager=manager, revoke_use_case=revoke_uc)

    assert len(revoke_attempts) == 3, "한 alias 실패해도 나머지 모두 시도"
    # 캐시는 alias 별 invalidate 가 일어나므로 — 실패한 alias 도 결국 invalidate_all 로 비워짐
    assert manager.alias_keys() == (), "shutdown 후 캐시 비워짐 보장"


@pytest.mark.asyncio
async def test_revoke_all_aliases_empty_cache_is_noop(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
) -> None:
    """캐시 비어있으면 폐기 시도 0회 — best-effort 함수가 안전하게 종료."""
    revoke_call_count = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal revoke_call_count
        if req.url.path == "/oauth2/revoke":
            revoke_call_count += 1
        return httpx.Response(200, json={"return_code": 0})

    manager = TokenManager(
        session_provider=_session_wrapper(session),
        cipher=cipher,
        auth_client_factory=_auth_factory(handler),
    )
    revoke_uc = RevokeKiwoomTokenUseCase(
        session_provider=_session_wrapper(session),
        cipher=cipher,
        auth_client_factory=_auth_factory(handler),
        token_manager=manager,
    )

    await revoke_all_aliases_best_effort(manager=manager, revoke_use_case=revoke_uc)

    assert revoke_call_count == 0
    assert manager.alias_keys() == ()
