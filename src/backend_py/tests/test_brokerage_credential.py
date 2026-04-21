"""KIS 실계정 자격증명 — CredentialCipher 단위 + Repository 통합 테스트.

설계: docs/kis-real-account-sync-plan.md § 3.2 / PR 3.
"""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.external import KisCredentials
from app.adapter.out.persistence.models import BrokerageAccount
from app.adapter.out.persistence.repositories import (
    BrokerageAccountCredentialRepository,
    BrokerageAccountRepository,
)
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
