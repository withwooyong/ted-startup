"""PR 5 — KIS 실계정 연결 테스트 + 실 sync wire.

- `TestKisConnectionUseCase` (OAuth 토큰만)
- `SyncPortfolioFromKisRealUseCase` 의 REAL 분기 (credential 복호화 → REAL 클라이언트)
- HTTP 엔드포인트 `POST /accounts/{id}/test-connection` + 기존 `/sync` 의 real 경로
- `@pytest.mark.requires_kis_real_account` — 로컬 개발자용 실 KIS smoke (CI skip)

외부 호출은 모두 `httpx.MockTransport` 로 봉쇄. 실 KIS 호출이 나가는 경로는
smoke 테스트에만 존재하며 기본 `pytest` 실행에서 제외된다.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable

import httpx
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.external import (
    KisClient,
    KisClientError,
    KisCredentials,
    KisEnvironment,
)
from app.adapter.out.persistence.models import BrokerageAccount
from app.adapter.out.persistence.repositories import (
    BrokerageAccountCredentialRepository,
    BrokerageAccountRepository,
)
from app.adapter.web._deps import (
    get_credential_cipher as prod_get_credential_cipher,
)
from app.adapter.web._deps import (
    get_kis_real_client_factory as prod_get_real_factory,
)
from app.adapter.web._deps import (
    get_session as prod_get_session,
)
from app.application.service.portfolio_service import (
    CredentialNotFoundError,
    KisRealClientFactory,
    SyncError,
    SyncPortfolioFromKisRealUseCase,
    TestKisConnectionUseCase,
    UnsupportedConnectionError,
)
from app.config.settings import get_settings
from app.main import create_app
from app.security.credential_cipher import CredentialCipher

# -----------------------------------------------------------------------------
# Fixtures & helpers
# -----------------------------------------------------------------------------


def _fresh_cipher() -> CredentialCipher:
    return CredentialCipher(Fernet.generate_key().decode())


def _real_mock_transport(
    *,
    token_status: int = 200,
    balance_rows: list[dict[str, object]] | None = None,
    balance_status: int = 200,
) -> httpx.MockTransport:
    """실 KIS 엔드포인트(openapi:9443) 를 내부 MockTransport 로 대체.

    `token_status=401` 로 토큰 발급 실패를 시뮬레이션해 KisAuthError 경로도 검증.
    """
    rows = balance_rows if balance_rows is not None else []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            if token_status == 200:
                return httpx.Response(
                    200,
                    json={"access_token": "REAL-FAKE-TOKEN", "expires_in": 86400},
                )
            return httpx.Response(
                token_status,
                json={"rt_cd": "1", "msg1": "INVALID_APP_KEY_MOCK"},
            )
        if request.url.path.endswith("/inquire-balance"):
            if balance_status != 200:
                return httpx.Response(balance_status, text="upstream error")
            return httpx.Response(
                200,
                json={"rt_cd": "0", "msg1": "OK", "output1": rows, "output2": []},
            )
        return httpx.Response(404, text=f"unknown path: {request.url.path}")

    return httpx.MockTransport(handler)


def _make_real_factory(transport: httpx.MockTransport) -> KisRealClientFactory:
    """MockTransport 를 주입한 real factory — CI 에서 실 URL 로 나가지 않음."""

    def factory(credentials: KisCredentials) -> KisClient:
        return KisClient(
            environment=KisEnvironment.REAL,
            credentials=credentials,
            transport=transport,
        )

    return factory


async def _seed_real_account_with_credential(
    session: AsyncSession,
    *,
    alias: str,
    cipher: CredentialCipher,
) -> BrokerageAccount:
    account = await BrokerageAccountRepository(session).add(
        BrokerageAccount(
            account_alias=alias,
            broker_code="kis",
            connection_type="kis_rest_real",
            environment="real",
        )
    )
    await BrokerageAccountCredentialRepository(session, cipher).upsert(
        account.id,
        KisCredentials(
            app_key="PKABCDEFGHIJKLMN0123",
            app_secret="SS-ABCDEFGHIJKLMN0123",
            account_no="99998888-01",
        ),
    )
    return account


# -----------------------------------------------------------------------------
# Use case: TestKisConnectionUseCase
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connection_success_returns_ok(session: AsyncSession) -> None:
    cipher = _fresh_cipher()
    account = await _seed_real_account_with_credential(session, alias="conn-ok", cipher=cipher)
    factory = _make_real_factory(_real_mock_transport())
    uc = TestKisConnectionUseCase(session, cipher=cipher, real_client_factory=factory)
    result = await uc.execute(account_id=account.id)
    assert result.ok is True
    assert result.environment == "real"
    assert result.account_id == account.id


@pytest.mark.asyncio
async def test_connection_missing_credential_raises(session: AsyncSession) -> None:
    """계좌는 있으나 credential 미등록 → `CredentialNotFoundError`."""
    cipher = _fresh_cipher()
    account = await BrokerageAccountRepository(session).add(
        BrokerageAccount(
            account_alias="conn-no-cred",
            broker_code="kis",
            connection_type="kis_rest_real",
            environment="real",
        )
    )
    factory = _make_real_factory(_real_mock_transport())
    uc = TestKisConnectionUseCase(session, cipher=cipher, real_client_factory=factory)
    with pytest.raises(CredentialNotFoundError, match="미등록"):
        await uc.execute(account_id=account.id)


@pytest.mark.asyncio
async def test_connection_rejects_non_real_account(session: AsyncSession) -> None:
    """kis_rest_mock 계좌에서 호출 → `UnsupportedConnectionError`."""
    cipher = _fresh_cipher()
    account = await BrokerageAccountRepository(session).add(
        BrokerageAccount(
            account_alias="conn-mock",
            broker_code="kis",
            connection_type="kis_rest_mock",
            environment="mock",
        )
    )
    factory = _make_real_factory(_real_mock_transport())
    uc = TestKisConnectionUseCase(session, cipher=cipher, real_client_factory=factory)
    with pytest.raises(UnsupportedConnectionError):
        await uc.execute(account_id=account.id)


@pytest.mark.asyncio
async def test_connection_token_failure_wrapped_as_sync_error(
    session: AsyncSession,
) -> None:
    """KIS 토큰 발급 실패(401) → `SyncError`. 라우터에서 502 로 변환."""
    cipher = _fresh_cipher()
    account = await _seed_real_account_with_credential(session, alias="conn-token-fail", cipher=cipher)
    factory = _make_real_factory(_real_mock_transport(token_status=401))
    uc = TestKisConnectionUseCase(session, cipher=cipher, real_client_factory=factory)
    with pytest.raises(SyncError, match="KIS 토큰 발급 실패"):
        await uc.execute(account_id=account.id)


# -----------------------------------------------------------------------------
# Use case: SyncPortfolioFromKisRealUseCase
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_real_sync_fetches_balance_and_creates_holdings(
    session: AsyncSession,
) -> None:
    cipher = _fresh_cipher()
    account = await _seed_real_account_with_credential(session, alias="real-sync-ok", cipher=cipher)
    credential_repo = BrokerageAccountCredentialRepository(session, cipher)
    transport = _real_mock_transport(
        balance_rows=[
            {
                "pdno": "005930",
                "prdt_name": "삼성전자",
                "hldg_qty": "7",
                "pchs_avg_pric": "72000",
            }
        ]
    )
    factory = _make_real_factory(transport)

    result = await SyncPortfolioFromKisRealUseCase(
        session,
        credential_repo=credential_repo,
        real_client_factory=factory,
    ).execute(account_id=account.id)

    assert result.connection_type == "kis_rest_real"
    assert result.fetched_count == 1
    assert result.created_count == 1
    assert result.stock_created_count == 1
    assert result.updated_count == 0


@pytest.mark.asyncio
async def test_real_sync_balance_failure_wrapped_as_sync_error(
    session: AsyncSession,
) -> None:
    cipher = _fresh_cipher()
    account = await _seed_real_account_with_credential(session, alias="real-sync-fail", cipher=cipher)
    credential_repo = BrokerageAccountCredentialRepository(session, cipher)
    transport = _real_mock_transport(balance_status=500)
    factory = _make_real_factory(transport)

    with pytest.raises(SyncError, match="실계좌 잔고 조회 실패"):
        await SyncPortfolioFromKisRealUseCase(
            session,
            credential_repo=credential_repo,
            real_client_factory=factory,
        ).execute(account_id=account.id)


# -----------------------------------------------------------------------------
# HTTP endpoint: POST /accounts/{id}/test-connection
# -----------------------------------------------------------------------------


@pytest_asyncio.fixture
async def real_app(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[FastAPI, CredentialCipher, dict[str, httpx.MockTransport]]]:
    """PR 5 전용 FastAPI 인스턴스 — session, cipher, real factory 모두 MockTransport 로 주입."""
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")
    get_settings.cache_clear()
    app = create_app()

    async def _session_override() -> AsyncIterator[AsyncSession]:
        yield session

    test_cipher = _fresh_cipher()
    state: dict[str, httpx.MockTransport] = {"transport": _real_mock_transport()}

    def _cipher_override() -> CredentialCipher:
        return test_cipher

    def _factory_override() -> Callable[[KisCredentials], KisClient]:
        def factory(credentials: KisCredentials) -> KisClient:
            return KisClient(
                environment=KisEnvironment.REAL,
                credentials=credentials,
                transport=state["transport"],
            )

        return factory

    app.dependency_overrides[prod_get_session] = _session_override
    app.dependency_overrides[prod_get_credential_cipher] = _cipher_override
    app.dependency_overrides[prod_get_real_factory] = _factory_override
    try:
        yield app, test_cipher, state
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


@pytest_asyncio.fixture
async def real_client(
    real_app: tuple[FastAPI, CredentialCipher, dict[str, httpx.MockTransport]],
) -> AsyncIterator[tuple[httpx.AsyncClient, CredentialCipher, dict[str, httpx.MockTransport]]]:
    app, cipher, state = real_app
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-API-Key": "test-admin-key"},
    ) as c:
        yield c, cipher, state


@pytest.mark.asyncio
async def test_endpoint_test_connection_success(
    session: AsyncSession,
    real_client: tuple[httpx.AsyncClient, CredentialCipher, dict[str, httpx.MockTransport]],
) -> None:
    client, cipher, _state = real_client
    account = await _seed_real_account_with_credential(session, alias="endpoint-conn-ok", cipher=cipher)
    resp = await client.post(f"/api/portfolio/accounts/{account.id}/test-connection")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"account_id": account.id, "environment": "real", "ok": True}


@pytest.mark.asyncio
async def test_endpoint_test_connection_missing_credential_404(
    session: AsyncSession,
    real_client: tuple[httpx.AsyncClient, CredentialCipher, dict[str, httpx.MockTransport]],
) -> None:
    client, _cipher, _state = real_client
    account = await BrokerageAccountRepository(session).add(
        BrokerageAccount(
            account_alias="endpoint-conn-no-cred",
            broker_code="kis",
            connection_type="kis_rest_real",
            environment="real",
        )
    )
    resp = await client.post(f"/api/portfolio/accounts/{account.id}/test-connection")
    assert resp.status_code == 404
    assert "미등록" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_endpoint_test_connection_token_failure_502(
    session: AsyncSession,
    real_client: tuple[httpx.AsyncClient, CredentialCipher, dict[str, httpx.MockTransport]],
) -> None:
    client, cipher, state = real_client
    account = await _seed_real_account_with_credential(session, alias="endpoint-conn-401", cipher=cipher)
    # 토큰 401 로 교체
    state["transport"] = _real_mock_transport(token_status=401)
    resp = await client.post(f"/api/portfolio/accounts/{account.id}/test-connection")
    assert resp.status_code == 502
    assert "토큰 발급 실패" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_endpoint_test_connection_rejects_mock_account_400(
    session: AsyncSession,
    real_client: tuple[httpx.AsyncClient, CredentialCipher, dict[str, httpx.MockTransport]],
) -> None:
    client, _cipher, _state = real_client
    account = await BrokerageAccountRepository(session).add(
        BrokerageAccount(
            account_alias="endpoint-conn-mock",
            broker_code="kis",
            connection_type="kis_rest_mock",
            environment="mock",
        )
    )
    resp = await client.post(f"/api/portfolio/accounts/{account.id}/test-connection")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_endpoint_sync_real_account_creates_holdings(
    session: AsyncSession,
    real_client: tuple[httpx.AsyncClient, CredentialCipher, dict[str, httpx.MockTransport]],
) -> None:
    """PR 5: `POST /sync` 이 kis_rest_real 계좌에 대해 정상 동작."""
    client, cipher, state = real_client
    account = await _seed_real_account_with_credential(session, alias="endpoint-sync-real", cipher=cipher)
    state["transport"] = _real_mock_transport(
        balance_rows=[
            {
                "pdno": "000660",
                "prdt_name": "SK하이닉스",
                "hldg_qty": "3",
                "pchs_avg_pric": "210000",
            }
        ]
    )
    resp = await client.post(f"/api/portfolio/accounts/{account.id}/sync")
    assert resp.status_code == 200
    body = resp.json()
    assert body["connection_type"] == "kis_rest_real"
    assert body["fetched_count"] == 1
    assert body["created_count"] == 1


@pytest.mark.asyncio
async def test_endpoint_sync_real_account_without_credential_404(
    session: AsyncSession,
    real_client: tuple[httpx.AsyncClient, CredentialCipher, dict[str, httpx.MockTransport]],
) -> None:
    client, _cipher, _state = real_client
    account = await BrokerageAccountRepository(session).add(
        BrokerageAccount(
            account_alias="endpoint-sync-no-cred",
            broker_code="kis",
            connection_type="kis_rest_real",
            environment="real",
        )
    )
    resp = await client.post(f"/api/portfolio/accounts/{account.id}/sync")
    assert resp.status_code == 404
    assert "credential 미등록" in resp.json()["detail"]


# -----------------------------------------------------------------------------
# Smoke test — 로컬 실 KIS 계정 검증 (CI skip)
# -----------------------------------------------------------------------------


@pytest.mark.requires_kis_real_account
@pytest.mark.asyncio
async def test_smoke_real_kis_token_issuance(session: AsyncSession) -> None:
    """실 KIS 엔드포인트로 토큰 발급만 시도. env 로 자격증명 주입.

    로컬 실행 예시:
      KIS_REAL_APP_KEY=... KIS_REAL_APP_SECRET=... KIS_REAL_ACCOUNT_NO=99998888-01 \
      uv run pytest -m requires_kis_real_account -s

    env 가 비어있으면 skip. CI 는 `addopts` 에 `-m "not requires_kis_real_account"`
    가 있어 본 테스트를 자동 제외.
    """
    app_key = os.environ.get("KIS_REAL_APP_KEY", "")
    app_secret = os.environ.get("KIS_REAL_APP_SECRET", "")
    account_no = os.environ.get("KIS_REAL_ACCOUNT_NO", "")
    if not (app_key and app_secret and account_no):
        pytest.skip("KIS_REAL_APP_KEY/SECRET/ACCOUNT env 가 설정되지 않았습니다.")

    credentials = KisCredentials(app_key=app_key, app_secret=app_secret, account_no=account_no)
    async with KisClient(environment=KisEnvironment.REAL, credentials=credentials) as client:
        try:
            await client.test_connection()
        except KisClientError as exc:
            pytest.fail(f"실 KIS 토큰 발급 실패: {exc}")
