"""KIS 실계정 자격증명 — CredentialCipher 단위 + Repository 통합 + HTTP 엔드포인트 테스트.

설계: docs/kis-real-account-sync-plan.md § 3.2 / PR 3 · PR 4.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.external import KisCredentials
from app.adapter.out.persistence.models import BrokerageAccount
from app.adapter.out.persistence.repositories import (
    BrokerageAccountCredentialRepository,
    BrokerageAccountRepository,
)
from app.adapter.web._deps import get_credential_cipher as prod_get_credential_cipher
from app.adapter.web._deps import get_session as prod_get_session
from app.config.settings import get_settings
from app.main import create_app
from app.security.credential_cipher import (
    CredentialCipher,
    DecryptionFailedError,
    MasterKeyNotConfiguredError,
    UnknownKeyVersionError,
)

# -----------------------------------------------------------------------------
# CredentialCipher unit tests (외부 의존성 0)
# -----------------------------------------------------------------------------


def test_cipher_encrypt_decrypt_roundtrip() -> None:
    cipher = CredentialCipher(Fernet.generate_key().decode())
    original = "super-secret-app-key-value"

    token, version = cipher.encrypt(original)
    assert isinstance(token, bytes)
    assert version == 1
    assert original.encode() not in token  # plaintext 가 ciphertext 에 그대로 남지 않음

    restored = cipher.decrypt(token, version)
    assert restored == original


def test_cipher_decrypt_with_wrong_key_raises_decryption_failed() -> None:
    cipher_a = CredentialCipher(Fernet.generate_key().decode())
    cipher_b = CredentialCipher(Fernet.generate_key().decode())

    token, version = cipher_a.encrypt("plaintext")
    # 외부 `InvalidToken` 대신 계층 내 `DecryptionFailedError` 로 감싸져야 함.
    with pytest.raises(DecryptionFailedError, match="복호화 실패"):
        cipher_b.decrypt(token, version)


def test_cipher_empty_master_key_raises_not_configured() -> None:
    with pytest.raises(MasterKeyNotConfiguredError, match="env var 주입 필수"):
        CredentialCipher("")


def test_cipher_malformed_master_key_raises_not_configured() -> None:
    with pytest.raises(MasterKeyNotConfiguredError, match="형식 오류"):
        CredentialCipher("not-a-valid-fernet-key")


def test_cipher_unknown_key_version_raises() -> None:
    cipher = CredentialCipher(Fernet.generate_key().decode(), current_version=1)
    token, _ = cipher.encrypt("x")
    with pytest.raises(UnknownKeyVersionError, match="key_version=2"):
        cipher.decrypt(token, key_version=2)


# -----------------------------------------------------------------------------
# Repository integration tests (testcontainers DB 왕복)
# -----------------------------------------------------------------------------


async def _seed_account(session: AsyncSession, alias: str = "cred-acc") -> BrokerageAccount:
    return await BrokerageAccountRepository(session).add(
        BrokerageAccount(
            account_alias=alias,
            broker_code="kis",
            connection_type="kis_rest_real",
            environment="real",
        )
    )


def _cipher() -> CredentialCipher:
    return CredentialCipher(Fernet.generate_key().decode())


@pytest.mark.asyncio
async def test_repo_upsert_then_get_decrypted_roundtrip(session: AsyncSession) -> None:
    account = await _seed_account(session)
    cipher = _cipher()
    repo = BrokerageAccountCredentialRepository(session, cipher)

    creds = KisCredentials(
        app_key="REAL-APP-KEY-ABCDEFGH",
        app_secret="REAL-APP-SECRET-0123456789",
        account_no="99998888-01",
    )
    await repo.upsert(account.id, creds)

    got = await repo.get_decrypted(account.id)
    assert got is not None
    assert got == creds


@pytest.mark.asyncio
async def test_repo_upsert_updates_existing_row(session: AsyncSession) -> None:
    """동일 account_id 재 upsert → UPDATE. 레코드 수 1건 유지."""
    account = await _seed_account(session, alias="cred-upsert")
    cipher = _cipher()
    repo = BrokerageAccountCredentialRepository(session, cipher)

    await repo.upsert(
        account.id,
        KisCredentials(app_key="OLD", app_secret="OLD-S", account_no="11112222-03"),
    )
    await repo.upsert(
        account.id,
        KisCredentials(app_key="NEW", app_secret="NEW-S", account_no="44445555-06"),
    )

    got = await repo.get_decrypted(account.id)
    assert got is not None
    assert got.app_key == "NEW"
    assert got.account_no == "44445555-06"


@pytest.mark.asyncio
async def test_repo_delete_removes_row(session: AsyncSession) -> None:
    account = await _seed_account(session, alias="cred-del")
    cipher = _cipher()
    repo = BrokerageAccountCredentialRepository(session, cipher)

    await repo.upsert(
        account.id,
        KisCredentials(app_key="K", app_secret="S", account_no="77778888-09"),
    )
    assert await repo.delete(account.id) is True
    assert await repo.get_decrypted(account.id) is None

    # 이미 없는 계좌 삭제 시도 → False
    assert await repo.delete(account.id) is False


@pytest.mark.asyncio
async def test_repo_cascade_delete_with_account(session: AsyncSession) -> None:
    """brokerage_account 삭제 시 credential 이 FK CASCADE 로 자동 제거."""
    account = await _seed_account(session, alias="cred-cascade")
    cipher = _cipher()
    repo = BrokerageAccountCredentialRepository(session, cipher)
    await repo.upsert(
        account.id,
        KisCredentials(app_key="K", app_secret="S", account_no="12345678-01"),
    )

    # 계좌 삭제
    await session.delete(account)
    await session.flush()

    assert await repo.get_decrypted(account.id) is None


@pytest.mark.asyncio
async def test_repo_masked_view_returns_tail4_and_never_secret(
    session: AsyncSession,
) -> None:
    """GET 응답 소스 — `app_key`·`account_no` 는 tail 4자리 마스킹, secret 은 노출 0.

    마스킹 불릿 수 = (len - 4). 고정 4개가 아니라 실제 가려진 문자 수와 일치시켜
    "얼마나 가렸는지" 가 시각적으로 드러나게 한다.
    """
    account = await _seed_account(session, alias="cred-masked")
    cipher = _cipher()
    repo = BrokerageAccountCredentialRepository(session, cipher)
    app_key = "PKABCDEFGHIJKLMNOPQR1234"  # 24자
    account_no = "12345678-01"  # 11자
    await repo.upsert(
        account.id,
        KisCredentials(
            app_key=app_key,
            app_secret="SUPER-SECRET-VALUE",
            account_no=account_no,
        ),
    )
    view = await repo.get_masked_view(account.id)
    assert view is not None
    # 24자 중 tail 4자리 "1234" 를 제외한 20자를 불릿으로 치환
    assert view.app_key_masked == "•" * 20 + "1234"
    assert view.app_key_masked.endswith("1234")
    assert len(view.app_key_masked) == len(app_key)
    # 11자 중 tail 4자리 "8-01" 를 제외한 7자를 불릿으로 치환
    assert view.account_no_masked == "•" * 7 + "8-01"
    assert len(view.account_no_masked) == len(account_no)
    # secret 은 view 의 어떤 필드로도 노출되지 않음
    assert "SUPER-SECRET-VALUE" not in repr(view)


@pytest.mark.asyncio
async def test_repo_masked_view_none_when_absent(session: AsyncSession) -> None:
    account = await _seed_account(session, alias="cred-masked-none")
    cipher = _cipher()
    repo = BrokerageAccountCredentialRepository(session, cipher)
    assert await repo.get_masked_view(account.id) is None


# -----------------------------------------------------------------------------
# HTTP endpoint tests (PR 4 — 실계정 등록 API)
# -----------------------------------------------------------------------------


@pytest_asyncio.fixture
async def credential_app(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[FastAPI]:
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")
    get_settings.cache_clear()
    app = create_app()

    async def _session_override() -> AsyncIterator[AsyncSession]:
        yield session

    # 테스트 중 마스터키는 conftest 가 주입한 더미. cipher 는 고유 인스턴스 주입.
    test_cipher = CredentialCipher(Fernet.generate_key().decode())

    def _cipher_override() -> CredentialCipher:
        return test_cipher

    app.dependency_overrides[prod_get_session] = _session_override
    app.dependency_overrides[prod_get_credential_cipher] = _cipher_override
    try:
        yield app
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


@pytest_asyncio.fixture
async def credential_client(
    credential_app: FastAPI,
) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=credential_app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-API-Key": "test-admin-key"},
    ) as c:
        yield c


async def _seed_real_account(session: AsyncSession, alias: str) -> BrokerageAccount:
    return await BrokerageAccountRepository(session).add(
        BrokerageAccount(
            account_alias=alias,
            broker_code="kis",
            connection_type="kis_rest_real",
            environment="real",
        )
    )


def _sample_body() -> dict[str, str]:
    return {
        "app_key": "PKABCDEFGHIJKLMNOPQR1234",
        "app_secret": "SUPER-SECRET-0123456789",
        "account_no": "12345678-01",
    }


@pytest.mark.asyncio
async def test_credential_endpoints_require_admin_key(credential_app: FastAPI, session: AsyncSession) -> None:
    account = await _seed_real_account(session, alias="cred-auth")
    transport = httpx.ASGITransport(app=credential_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            f"/api/portfolio/accounts/{account.id}/credentials",
            json=_sample_body(),
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_post_credential_returns_masked_201(session: AsyncSession, credential_client: httpx.AsyncClient) -> None:
    account = await _seed_real_account(session, alias="cred-http-post")
    resp = await credential_client.post(
        f"/api/portfolio/accounts/{account.id}/credentials",
        json=_sample_body(),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["account_id"] == account.id
    # app_key "PKABCDEFGHIJKLMNOPQR1234" (24자) → 20 bullets + "1234"
    assert body["app_key_masked"].endswith("1234")
    assert body["app_key_masked"].count("•") == 20
    assert body["account_no_masked"].endswith("8-01")
    assert body["key_version"] == 1
    # 응답에 어떤 형태로도 secret 이 노출되지 않음
    assert "SUPER-SECRET-0123456789" not in resp.text
    assert "app_secret" not in body


@pytest.mark.asyncio
async def test_post_credential_conflict_when_exists(
    session: AsyncSession, credential_client: httpx.AsyncClient
) -> None:
    account = await _seed_real_account(session, alias="cred-http-conflict")
    resp1 = await credential_client.post(
        f"/api/portfolio/accounts/{account.id}/credentials",
        json=_sample_body(),
    )
    assert resp1.status_code == 201
    resp2 = await credential_client.post(
        f"/api/portfolio/accounts/{account.id}/credentials",
        json=_sample_body(),
    )
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_put_credential_replaces_existing(session: AsyncSession, credential_client: httpx.AsyncClient) -> None:
    account = await _seed_real_account(session, alias="cred-http-put")
    await credential_client.post(
        f"/api/portfolio/accounts/{account.id}/credentials",
        json=_sample_body(),
    )
    new_body = {
        "app_key": "REPLACEMENT-KEY-0000000000ABCD",
        "app_secret": "NEW-SECRET-0000000000",
        "account_no": "87654321-99",
    }
    resp = await credential_client.put(f"/api/portfolio/accounts/{account.id}/credentials", json=new_body)
    assert resp.status_code == 200
    body = resp.json()
    assert body["app_key_masked"].endswith("ABCD")
    assert body["account_no_masked"].endswith("1-99")


@pytest.mark.asyncio
async def test_put_credential_404_when_missing(session: AsyncSession, credential_client: httpx.AsyncClient) -> None:
    account = await _seed_real_account(session, alias="cred-http-put-404")
    resp = await credential_client.put(f"/api/portfolio/accounts/{account.id}/credentials", json=_sample_body())
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_credential_returns_masked_and_delete_removes(
    session: AsyncSession, credential_client: httpx.AsyncClient
) -> None:
    account = await _seed_real_account(session, alias="cred-http-get")
    await credential_client.post(
        f"/api/portfolio/accounts/{account.id}/credentials",
        json=_sample_body(),
    )
    get_resp = await credential_client.get(f"/api/portfolio/accounts/{account.id}/credentials")
    assert get_resp.status_code == 200
    assert get_resp.json()["app_key_masked"].endswith("1234")

    del_resp = await credential_client.delete(f"/api/portfolio/accounts/{account.id}/credentials")
    assert del_resp.status_code == 204

    missing_resp = await credential_client.get(f"/api/portfolio/accounts/{account.id}/credentials")
    assert missing_resp.status_code == 404


@pytest.mark.asyncio
async def test_credential_rejects_non_real_connection_type(
    session: AsyncSession, credential_client: httpx.AsyncClient
) -> None:
    """kis_rest_mock 계좌에 credential 등록 시도 → 400 (UnsupportedConnectionError)."""
    mock_account = await BrokerageAccountRepository(session).add(
        BrokerageAccount(
            account_alias="cred-mock-blocked",
            broker_code="kis",
            connection_type="kis_rest_mock",
            environment="mock",
        )
    )
    resp = await credential_client.post(
        f"/api/portfolio/accounts/{mock_account.id}/credentials",
        json=_sample_body(),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_credential_rejects_unknown_account(
    credential_client: httpx.AsyncClient,
) -> None:
    """POST/PUT/GET/DELETE 모든 verb 에서 unknown account_id → 404.

    `_ensure_real_account` 가 네 엔드포인트 공통 전처리로 동작하는지 검증.
    """
    for method, has_body in (
        ("POST", True),
        ("PUT", True),
        ("GET", False),
        ("DELETE", False),
    ):
        resp = await credential_client.request(
            method,
            "/api/portfolio/accounts/999999/credentials",
            json=_sample_body() if has_body else None,
        )
        assert resp.status_code == 404, f"{method} expected 404, got {resp.status_code}"


@pytest.mark.asyncio
async def test_credential_get_surfaces_cipher_failure_as_500(
    session: AsyncSession, credential_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DB 복호화 실패(`DecryptionFailedError`) → 500 으로 변환 + 스택트레이스 미노출.

    시나리오: 등록한 cipher 와 다른 키로 조회 시도 → DB 바이트는 첫 키 전용이라
    `Fernet.decrypt` 가 `InvalidToken` → `DecryptionFailedError` 로 감싸져 전파.
    """
    from app.adapter.web._deps import get_credential_cipher as prod_get_cred

    # 1) 원래 cipher 로 등록
    account = await _seed_real_account(session, alias="cred-cipher-break")
    original_cipher = _cipher()
    await BrokerageAccountCredentialRepository(session, original_cipher).upsert(
        account.id,
        KisCredentials(
            app_key="PKREAL0123456789ABCD",
            app_secret="SECRET-0123456789AB",
            account_no="11112222-03",
        ),
    )
    await session.commit()

    # 2) 조회 시에만 다른 cipher 를 주입 (마스터키 회전 실패 상황 모사)
    broken_cipher = CredentialCipher(Fernet.generate_key().decode())

    def _broken_override() -> CredentialCipher:
        return broken_cipher

    credential_app.dependency_overrides[prod_get_cred] = _broken_override

    transport = httpx.ASGITransport(app=credential_app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-API-Key": "test-admin-key"},
    ) as c:
        resp = await c.get(f"/api/portfolio/accounts/{account.id}/credentials")

    assert resp.status_code == 500
    body = resp.json()
    # 내부 예외 타입·스택트레이스는 응답 본문에 노출되지 않음
    assert "DecryptionFailedError" not in resp.text
    assert "InvalidToken" not in resp.text
    assert "운영" in body.get("detail", "")


@pytest.mark.asyncio
async def test_credential_validates_account_no_format(
    session: AsyncSession, credential_client: httpx.AsyncClient
) -> None:
    """account_no 는 `NNNNNNNN-NN` 형식 필수 — 불일치 시 400.

    프로젝트 전역 예외 핸들러가 `RequestValidationError` 를 400 으로 통일 매핑
    (참조: CLAUDE.md § Scaffolding).
    """
    account = await _seed_real_account(session, alias="cred-invalid-acc-no")
    bad = _sample_body() | {"account_no": "1234"}
    resp = await credential_client.post(f"/api/portfolio/accounts/{account.id}/credentials", json=bad)
    assert resp.status_code == 400
