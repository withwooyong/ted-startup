"""POST /api/kiwoom/auth/tokens — 라우터 + admin guard.

httpx.AsyncClient + ASGITransport 패턴 — pytest-asyncio loop 와 동일 loop 유지로
testcontainers asyncpg 연결 충돌 회피.

시나리오:
1. admin key 헤더 누락 → 401
2. admin key 잘못 → 401
3. ADMIN_API_KEY 미설정 → 401 (fail-closed)
4. 정상 발급 → 200, 응답에 토큰 평문 없음 (tail 일부만), expires_at 분 단위
5. credential 미등록 alias → 404 (alias 평문 detail 미포함)
6. credential 비활성 → 400
7. 401 자격증명 거부 → 400
8. 강제 갱신 — invalidate 후 새 발급 (2회 호출)
9. 응답 본문에 appkey 평문 미노출 (F5 follow-up — router 레벨 누설 회귀 방어)
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom.auth import KiwoomAuthClient
from app.adapter.out.persistence.repositories.kiwoom_credential import KiwoomCredentialRepository
from app.adapter.web._deps import get_token_manager
from app.adapter.web.routers.auth import router as auth_router
from app.application.dto.kiwoom_auth import KiwoomCredentials
from app.application.service.token_service import TokenManager
from app.security.kiwoom_credential_cipher import KiwoomCredentialCipher

KST = ZoneInfo("Asia/Seoul")

_PLAINTEXT_TOKEN = "WQJCwyqInph" + "X" * 140  # 평문 토큰 — 응답에 노출되면 안 됨
_TOKEN_BODY: dict[str, str | int] = {
    "expires_dt": "20991231235959",
    "token_type": "bearer",
    "token": _PLAINTEXT_TOKEN,
    "return_code": 0,
    "return_msg": "ok",
}


@pytest.fixture
def admin_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """monkeypatch — 환경변수 자동 복원 (M3 적대적 리뷰: os.environ race 방어)."""
    key = "test-admin-key-1234"
    monkeypatch.setenv("ADMIN_API_KEY", key)
    from app.config.settings import get_settings

    get_settings.cache_clear()
    yield key
    get_settings.cache_clear()


@pytest.fixture
def cipher(master_key: str) -> KiwoomCredentialCipher:
    return KiwoomCredentialCipher(master_key=master_key)


def _make_app(manager: TokenManager | None) -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)
    app.dependency_overrides[get_token_manager] = lambda: manager
    return app


def _session_wrapper(session: AsyncSession) -> Callable[[], AbstractAsyncContextManager[AsyncSession]]:
    @asynccontextmanager
    async def _provider() -> AsyncIterator[AsyncSession]:
        yield session

    return _provider


def _manager_with_handler(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    handler: Callable[[httpx.Request], httpx.Response],
) -> TokenManager:
    def _auth_factory(base_url: str) -> KiwoomAuthClient:
        return KiwoomAuthClient(
            base_url=base_url,
            transport=httpx.MockTransport(handler),
            max_attempts=1,
            retry_min_wait=0.0,
            retry_max_wait=0.0,
        )

    return TokenManager(
        session_provider=_session_wrapper(session),
        cipher=cipher,
        auth_client_factory=_auth_factory,
    )


def _async_client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


# -----------------------------------------------------------------------------
# admin key 가드
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_tokens_rejects_missing_admin_key(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    admin_key: str,
) -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_TOKEN_BODY)

    app = _make_app(_manager_with_handler(session, cipher, handler))
    async with _async_client(app) as client:
        resp = await client.post("/api/kiwoom/auth/tokens", params={"alias": "test-prod"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_post_tokens_rejects_wrong_admin_key(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    admin_key: str,
) -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_TOKEN_BODY)

    app = _make_app(_manager_with_handler(session, cipher, handler))
    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/auth/tokens",
            params={"alias": "test-prod"},
            headers={"X-API-Key": "wrong"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_post_tokens_rejects_when_admin_key_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADMIN_API_KEY 미설정 시 모든 admin 라우터 fail-closed."""
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    from app.config.settings import get_settings

    get_settings.cache_clear()
    try:
        app = _make_app(None)
        async with _async_client(app) as client:
            resp = await client.post(
                "/api/kiwoom/auth/tokens",
                params={"alias": "test-prod"},
                headers={"X-API-Key": "anything"},
            )
        assert resp.status_code == 401
    finally:
        get_settings.cache_clear()


# -----------------------------------------------------------------------------
# 정상 발급
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_tokens_returns_masked_response(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    admin_key: str,
) -> None:
    repo = KiwoomCredentialRepository(session, cipher)
    await repo.upsert(
        alias="test-prod",
        env="mock",
        credentials=KiwoomCredentials(appkey="A" * 32, secretkey="S" * 32),
    )

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_TOKEN_BODY)

    app = _make_app(_manager_with_handler(session, cipher, handler))
    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/auth/tokens",
            params={"alias": "test-prod"},
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["alias"] == "test-prod"
    assert data["token_type"] == "bearer"
    # 토큰 평문 절대 노출 금지
    assert _PLAINTEXT_TOKEN not in resp.text
    assert "token_masked" in data
    assert _PLAINTEXT_TOKEN[:50] not in data["token_masked"]
    # M5: expires_at 분 단위 절단 — 초/마이크로초 fingerprint 방어
    expires_str = data["expires_at"]
    assert expires_str.endswith(":00") or expires_str.endswith(":00+09:00")


# -----------------------------------------------------------------------------
# 에러 매핑
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_tokens_returns_404_for_missing_alias(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    admin_key: str,
) -> None:
    """404 + detail 에 alias 평문 미포함 (M1 — 라우터 detail 비식별화)."""

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_TOKEN_BODY)

    app = _make_app(_manager_with_handler(session, cipher, handler))
    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/auth/tokens",
            params={"alias": "secret-alias-name-12345"},
            headers={"X-API-Key": admin_key},
        )
    assert resp.status_code == 404
    # alias 평문이 detail 에 노출되면 안 됨 (M1)
    assert "secret-alias-name-12345" not in resp.text


@pytest.mark.asyncio
async def test_post_tokens_returns_400_for_inactive_alias(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    admin_key: str,
) -> None:
    repo = KiwoomCredentialRepository(session, cipher)
    await repo.upsert(
        alias="inactive",
        env="mock",
        credentials=KiwoomCredentials(appkey="A" * 32, secretkey="S" * 32),
    )
    await repo.deactivate(alias="inactive")

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_TOKEN_BODY)

    app = _make_app(_manager_with_handler(session, cipher, handler))
    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/auth/tokens",
            params={"alias": "inactive"},
            headers={"X-API-Key": admin_key},
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_post_tokens_returns_400_when_credential_rejected(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    admin_key: str,
) -> None:
    repo = KiwoomCredentialRepository(session, cipher)
    await repo.upsert(
        alias="bad-creds",
        env="mock",
        credentials=KiwoomCredentials(appkey="A" * 32, secretkey="S" * 32),
    )

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(401)

    app = _make_app(_manager_with_handler(session, cipher, handler))
    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/auth/tokens",
            params={"alias": "bad-creds"},
            headers={"X-API-Key": admin_key},
        )
    assert resp.status_code == 400


# -----------------------------------------------------------------------------
# 강제 갱신
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_tokens_invalidates_cache_each_call(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    admin_key: str,
) -> None:
    """POST 는 매번 invalidate 후 새 발급 — 강제 갱신 의미."""
    repo = KiwoomCredentialRepository(session, cipher)
    await repo.upsert(
        alias="rotate",
        env="mock",
        credentials=KiwoomCredentials(appkey="A" * 32, secretkey="S" * 32),
    )

    call_count = 0

    def handler(_req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        future = datetime.now(KST) + timedelta(hours=24, seconds=call_count)
        return httpx.Response(
            200,
            json={**_TOKEN_BODY, "expires_dt": future.strftime("%Y%m%d%H%M%S")},
        )

    app = _make_app(_manager_with_handler(session, cipher, handler))
    async with _async_client(app) as client:
        r1 = await client.post(
            "/api/kiwoom/auth/tokens",
            params={"alias": "rotate"},
            headers={"X-API-Key": admin_key},
        )
        r2 = await client.post(
            "/api/kiwoom/auth/tokens",
            params={"alias": "rotate"},
            headers={"X-API-Key": admin_key},
        )

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert call_count == 2


# -----------------------------------------------------------------------------
# F5 — Router-level secret leak 회귀 방어 (적대적 리뷰 follow-up)
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_tokens_response_does_not_leak_appkey_or_secretkey(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    admin_key: str,
) -> None:
    """라우터 응답 본문에 appkey / secretkey 평문 절대 노출 금지."""
    leaky_appkey = "AppKey-LEAKY-1234567890ABCDEF"
    leaky_secretkey = "SecretKey-LEAKY-1234567890ABCDEF"
    repo = KiwoomCredentialRepository(session, cipher)
    await repo.upsert(
        alias="leak-test",
        env="mock",
        credentials=KiwoomCredentials(appkey=leaky_appkey, secretkey=leaky_secretkey),
    )

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_TOKEN_BODY)

    app = _make_app(_manager_with_handler(session, cipher, handler))
    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/auth/tokens",
            params={"alias": "leak-test"},
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 200
    assert leaky_appkey not in resp.text, "appkey 평문 응답 노출"
    assert leaky_secretkey not in resp.text, "secretkey 평문 응답 노출"


@pytest.mark.asyncio
async def test_post_tokens_business_error_detail_does_not_leak_message(
    session: AsyncSession,
    cipher: KiwoomCredentialCipher,
    admin_key: str,
) -> None:
    """KiwoomBusinessError detail 에 attacker-influenced return_msg 미포함 (M1)."""
    repo = KiwoomCredentialRepository(session, cipher)
    await repo.upsert(
        alias="biz-err",
        env="mock",
        credentials=KiwoomCredentials(appkey="A" * 32, secretkey="S" * 32),
    )

    leaky_msg = "appkey AppKey-LEAKY-1234567890ABCDEF rejected"

    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={**_TOKEN_BODY, "return_code": 9999, "return_msg": leaky_msg},
        )

    app = _make_app(_manager_with_handler(session, cipher, handler))
    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/auth/tokens",
            params={"alias": "biz-err"},
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 400
    # return_msg 평문 absent — api_id / return_code 만 detail
    assert leaky_msg not in resp.text
    assert "AppKey-LEAKY" not in resp.text
