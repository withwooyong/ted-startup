"""KiwoomCredentialRepository 통합 테스트 — testcontainers PG16 + Fernet round-trip.

검증:
- upsert (insert + update by alias)
- find_by_alias (활성/비활성)
- get_decrypted (Fernet 복호화 + KiwoomCredentials 반환)
- get_masked_view (appkey/secretkey 마스킹 — secretkey 는 절대 노출 안 됨)
- delete
- alias UNIQUE 충돌 시 update 동작
- env 별 분리 (prod / mock alias 동시 등록 가능)
- find_active_by_env (배치/스케줄러용)
"""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.repositories.kiwoom_credential import (
    KiwoomCredentialRepository,
)
from app.application.dto.kiwoom_auth import KiwoomCredentials
from app.security.kiwoom_credential_cipher import KiwoomCredentialCipher


def _cipher() -> KiwoomCredentialCipher:
    return KiwoomCredentialCipher(Fernet.generate_key().decode())


@pytest.mark.asyncio
async def test_repo_upsert_then_get_decrypted_roundtrip(session: AsyncSession) -> None:
    cipher = _cipher()
    repo = KiwoomCredentialRepository(session, cipher)

    creds = KiwoomCredentials(
        appkey="REAL-APPKEY-AxserEsdcredca123456",
        secretkey="REAL-SECRETKEY-SEefdcwcforehDre2fdvc-0123",
    )
    await repo.upsert(alias="prod-main", env="prod", credentials=creds)

    got = await repo.get_decrypted(alias="prod-main")
    assert got is not None
    assert got == creds


@pytest.mark.asyncio
async def test_repo_upsert_updates_existing_row(session: AsyncSession) -> None:
    """동일 alias 재 upsert → UPDATE. 같은 cipher 로 새 ciphertext 생성."""
    cipher = _cipher()
    repo = KiwoomCredentialRepository(session, cipher)

    await repo.upsert(
        alias="upsert-alias",
        env="prod",
        credentials=KiwoomCredentials(appkey="OLD-APPKEY-1234567890", secretkey="OLD-SECRETKEY-1234567890"),
    )
    await repo.upsert(
        alias="upsert-alias",
        env="prod",
        credentials=KiwoomCredentials(appkey="NEW-APPKEY-1234567890", secretkey="NEW-SECRETKEY-1234567890"),
    )

    got = await repo.get_decrypted(alias="upsert-alias")
    assert got is not None
    assert got.appkey == "NEW-APPKEY-1234567890"
    assert got.secretkey == "NEW-SECRETKEY-1234567890"


@pytest.mark.asyncio
async def test_repo_find_by_alias_returns_row(session: AsyncSession) -> None:
    cipher = _cipher()
    repo = KiwoomCredentialRepository(session, cipher)

    await repo.upsert(
        alias="find-by-alias-test",
        env="mock",
        credentials=KiwoomCredentials(appkey="x" * 16, secretkey="y" * 16),
    )

    row = await repo.find_by_alias("find-by-alias-test")
    assert row is not None
    assert row.alias == "find-by-alias-test"
    assert row.env == "mock"
    assert row.is_active is True
    assert row.appkey_cipher != b"x" * 16  # 평문 저장 금지
    assert row.secretkey_cipher != b"y" * 16


@pytest.mark.asyncio
async def test_repo_find_by_alias_returns_none_when_missing(session: AsyncSession) -> None:
    repo = KiwoomCredentialRepository(session, _cipher())
    assert await repo.find_by_alias("does-not-exist") is None


@pytest.mark.asyncio
async def test_repo_get_decrypted_returns_none_when_missing(session: AsyncSession) -> None:
    repo = KiwoomCredentialRepository(session, _cipher())
    assert await repo.get_decrypted(alias="does-not-exist") is None


@pytest.mark.asyncio
async def test_repo_masked_view_hides_secretkey(session: AsyncSession) -> None:
    """get_masked_view: appkey 는 tail 4자리만 노출, secretkey 는 전체 마스킹."""
    cipher = _cipher()
    repo = KiwoomCredentialRepository(session, cipher)

    await repo.upsert(
        alias="masked-view-test",
        env="prod",
        credentials=KiwoomCredentials(
            appkey="AxserEsdcredca-FULL-APPKEY-1234",
            secretkey="SEefdcwcforehDre2fdvc-FULL-SECRETKEY",
        ),
    )

    view = await repo.get_masked_view(alias="masked-view-test")
    assert view is not None
    assert view.alias == "masked-view-test"
    assert view.env == "prod"
    # appkey: tail 4 글자만 노출
    assert view.appkey_masked.endswith("1234")
    assert "AxserEsdcredca" not in view.appkey_masked
    # secretkey: 어떤 글자도 노출 안 됨
    assert "SEefdcwcforehDre2fdvc" not in view.secretkey_masked
    assert "FULL-SECRETKEY" not in view.secretkey_masked


@pytest.mark.asyncio
async def test_repo_delete_removes_row(session: AsyncSession) -> None:
    cipher = _cipher()
    repo = KiwoomCredentialRepository(session, cipher)

    await repo.upsert(
        alias="delete-test",
        env="mock",
        credentials=KiwoomCredentials(appkey="a" * 16, secretkey="b" * 16),
    )
    deleted = await repo.delete(alias="delete-test")
    assert deleted is True
    assert await repo.find_by_alias("delete-test") is None


@pytest.mark.asyncio
async def test_repo_delete_returns_false_when_missing(session: AsyncSession) -> None:
    repo = KiwoomCredentialRepository(session, _cipher())
    assert await repo.delete(alias="missing") is False


@pytest.mark.asyncio
async def test_repo_separate_alias_for_prod_and_mock(session: AsyncSession) -> None:
    """alias 가 다르면 같은 env 에 여러 자격증명 등록 가능."""
    cipher = _cipher()
    repo = KiwoomCredentialRepository(session, cipher)

    await repo.upsert(
        alias="prod-main",
        env="prod",
        credentials=KiwoomCredentials(appkey="prod-key" + "0" * 8, secretkey="prod-secret" + "0" * 8),
    )
    await repo.upsert(
        alias="mock-ci",
        env="mock",
        credentials=KiwoomCredentials(appkey="mock-key" + "0" * 8, secretkey="mock-secret" + "0" * 8),
    )

    prod = await repo.find_by_alias("prod-main")
    mock = await repo.find_by_alias("mock-ci")
    assert prod is not None and prod.env == "prod"
    assert mock is not None and mock.env == "mock"
    assert prod.appkey_cipher != mock.appkey_cipher


@pytest.mark.asyncio
async def test_repo_appkey_secretkey_stored_as_ciphertext(session: AsyncSession) -> None:
    """DB 컬럼 BYTEA 가 plaintext 로 저장되지 않음을 직접 확인."""
    cipher = _cipher()
    repo = KiwoomCredentialRepository(session, cipher)

    await repo.upsert(
        alias="cipher-check",
        env="prod",
        credentials=KiwoomCredentials(
            appkey="DETECTABLE-APPKEY-MARKER-12345",
            secretkey="DETECTABLE-SECRETKEY-MARKER-67890",
        ),
    )

    row = await repo.find_by_alias("cipher-check")
    assert row is not None
    assert b"DETECTABLE-APPKEY-MARKER-12345" not in row.appkey_cipher
    assert b"DETECTABLE-SECRETKEY-MARKER-67890" not in row.secretkey_cipher


@pytest.mark.asyncio
async def test_repo_list_active_by_env(session: AsyncSession) -> None:
    """find_active_by_env: 활성 자격증명만 환경별로 필터링."""
    cipher = _cipher()
    repo = KiwoomCredentialRepository(session, cipher)

    await repo.upsert(
        alias="prod-a",
        env="prod",
        credentials=KiwoomCredentials(appkey="a" * 16, secretkey="b" * 16),
    )
    await repo.upsert(
        alias="prod-b",
        env="prod",
        credentials=KiwoomCredentials(appkey="c" * 16, secretkey="d" * 16),
    )
    await repo.upsert(
        alias="mock-x",
        env="mock",
        credentials=KiwoomCredentials(appkey="e" * 16, secretkey="f" * 16),
    )

    prods = await repo.list_active_by_env("prod")
    aliases = {r.alias for r in prods}
    assert "prod-a" in aliases
    assert "prod-b" in aliases
    assert "mock-x" not in aliases


@pytest.mark.asyncio
async def test_repo_deactivate_excludes_from_active_list(session: AsyncSession) -> None:
    """deactivate(alias) → is_active=False, list_active_by_env 결과에서 제외."""
    cipher = _cipher()
    repo = KiwoomCredentialRepository(session, cipher)

    await repo.upsert(
        alias="active-then-inactive",
        env="prod",
        credentials=KiwoomCredentials(appkey="a" * 16, secretkey="b" * 16),
    )

    deactivated = await repo.deactivate(alias="active-then-inactive")
    assert deactivated is True

    actives = await repo.list_active_by_env("prod")
    aliases = {r.alias for r in actives}
    assert "active-then-inactive" not in aliases

    # 비활성 상태에서 row 자체는 보존
    row = await repo.find_by_alias("active-then-inactive")
    assert row is not None
    assert row.is_active is False


@pytest.mark.asyncio
async def test_repo_deactivate_returns_false_when_already_inactive(session: AsyncSession) -> None:
    cipher = _cipher()
    repo = KiwoomCredentialRepository(session, cipher)

    await repo.upsert(
        alias="double-deactivate",
        env="mock",
        credentials=KiwoomCredentials(appkey="a" * 16, secretkey="b" * 16),
    )
    assert await repo.deactivate(alias="double-deactivate") is True
    # 이미 비활성 — False
    assert await repo.deactivate(alias="double-deactivate") is False


@pytest.mark.asyncio
async def test_repo_deactivate_returns_false_when_missing(session: AsyncSession) -> None:
    repo = KiwoomCredentialRepository(session, _cipher())
    assert await repo.deactivate(alias="never-existed") is False


@pytest.mark.asyncio
async def test_repo_upsert_after_deactivate_reactivates(session: AsyncSession) -> None:
    """upsert 가 is_active=True 강제 — deactivate 된 alias 도 다시 활성화."""
    cipher = _cipher()
    repo = KiwoomCredentialRepository(session, cipher)

    await repo.upsert(
        alias="reactivate-flow",
        env="prod",
        credentials=KiwoomCredentials(appkey="a" * 16, secretkey="b" * 16),
    )
    await repo.deactivate(alias="reactivate-flow")

    await repo.upsert(
        alias="reactivate-flow",
        env="prod",
        credentials=KiwoomCredentials(appkey="c" * 16, secretkey="d" * 16),
    )
    row = await repo.find_by_alias("reactivate-flow")
    assert row is not None
    assert row.is_active is True
