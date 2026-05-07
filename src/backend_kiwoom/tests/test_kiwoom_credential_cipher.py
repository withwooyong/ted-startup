"""KiwoomCredentialCipher (Fernet) 단위 테스트.

설계: master.md § 6.5 / endpoint-01-au10001.md § 5.

검증:
- encrypt → decrypt round-trip
- key_version 다중 관리 + 회전
- 빈 마스터키 → MasterKeyNotConfiguredError (loud fail)
- 잘못된 형식 마스터키 → MasterKeyNotConfiguredError
- 등록 안 된 key_version → UnknownKeyVersionError
- 키 불일치 / 토큰 손상 → DecryptionFailedError (외부 InvalidToken 누출 금지)
"""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from app.security.kiwoom_credential_cipher import (
    DecryptionFailedError,
    KiwoomCredentialCipher,
    MasterKeyNotConfiguredError,
    UnknownKeyVersionError,
)

# -----------------------------------------------------------------------------
# Round-trip
# -----------------------------------------------------------------------------


def test_cipher_encrypt_decrypt_roundtrip() -> None:
    cipher = KiwoomCredentialCipher(Fernet.generate_key().decode())
    original = "키움-운영-appkey-AxserEsdcredca123456"

    token, version = cipher.encrypt(original)
    assert isinstance(token, bytes)
    assert version == 1
    assert original.encode() not in token

    restored = cipher.decrypt(token, version)
    assert restored == original


def test_cipher_encrypt_produces_different_ciphertext_each_call() -> None:
    """Fernet 은 nonce 사용 — 같은 plaintext 여도 ciphertext 가 매번 다름."""
    cipher = KiwoomCredentialCipher(Fernet.generate_key().decode())
    plaintext = "same-secret"

    token_a, _ = cipher.encrypt(plaintext)
    token_b, _ = cipher.encrypt(plaintext)
    assert token_a != token_b
    assert cipher.decrypt(token_a, 1) == plaintext
    assert cipher.decrypt(token_b, 1) == plaintext


def test_cipher_handles_unicode_plaintext() -> None:
    """한글 / 이모지 / 긴 secretkey 도 round-trip."""
    cipher = KiwoomCredentialCipher(Fernet.generate_key().decode())
    for plain in ["한글-시크릿", "🔐emoji-secret", "x" * 256]:
        token, version = cipher.encrypt(plain)
        assert cipher.decrypt(token, version) == plain


# -----------------------------------------------------------------------------
# Failure modes
# -----------------------------------------------------------------------------


def test_cipher_empty_master_key_raises_not_configured() -> None:
    with pytest.raises(MasterKeyNotConfiguredError, match="env var 주입 필수"):
        KiwoomCredentialCipher("")


def test_cipher_malformed_master_key_raises_not_configured() -> None:
    with pytest.raises(MasterKeyNotConfiguredError, match="형식 오류"):
        KiwoomCredentialCipher("not-a-valid-fernet-key")


def test_cipher_decrypt_with_wrong_key_raises_decryption_failed() -> None:
    """다른 마스터키로 만든 cipher 로 decrypt → InvalidToken 을 DecryptionFailedError 로 감쌈."""
    cipher_a = KiwoomCredentialCipher(Fernet.generate_key().decode())
    cipher_b = KiwoomCredentialCipher(Fernet.generate_key().decode())

    token, version = cipher_a.encrypt("plaintext")
    with pytest.raises(DecryptionFailedError, match="복호화 실패"):
        cipher_b.decrypt(token, version)


def test_cipher_decrypt_failure_message_excludes_plaintext() -> None:
    """예외 메시지에는 key_version 만 포함, 바이트/plaintext 누출 금지."""
    cipher_a = KiwoomCredentialCipher(Fernet.generate_key().decode())
    cipher_b = KiwoomCredentialCipher(Fernet.generate_key().decode())
    token, version = cipher_a.encrypt("super-sensitive-12345")

    with pytest.raises(DecryptionFailedError) as exc_info:
        cipher_b.decrypt(token, version)
    msg = str(exc_info.value)
    assert "super-sensitive-12345" not in msg
    assert token.decode("utf-8", errors="ignore") not in msg


def test_cipher_unknown_key_version_raises() -> None:
    """등록되지 않은 key_version 사용 시 UnknownKeyVersionError."""
    cipher = KiwoomCredentialCipher(Fernet.generate_key().decode(), current_version=1)
    token, _ = cipher.encrypt("x")
    with pytest.raises(UnknownKeyVersionError, match="key_version=2"):
        cipher.decrypt(token, key_version=2)


def test_cipher_unknown_version_message_does_not_leak_cipher() -> None:
    """UnknownKeyVersionError 메시지에 ciphertext 누출 금지."""
    cipher = KiwoomCredentialCipher(Fernet.generate_key().decode())
    token, _ = cipher.encrypt("plaintext")
    with pytest.raises(UnknownKeyVersionError) as exc_info:
        cipher.decrypt(token, key_version=99)
    assert token.decode("utf-8", errors="ignore") not in str(exc_info.value)


def test_cipher_decrypt_corrupted_token_raises_decryption_failed() -> None:
    """토큰 손상 (수정된 ciphertext) → DecryptionFailedError."""
    cipher = KiwoomCredentialCipher(Fernet.generate_key().decode())
    token, version = cipher.encrypt("x")
    corrupted = b"AAAA" + token[4:]
    with pytest.raises(DecryptionFailedError):
        cipher.decrypt(corrupted, version)


# -----------------------------------------------------------------------------
# Properties
# -----------------------------------------------------------------------------


def test_cipher_current_version_property() -> None:
    cipher = KiwoomCredentialCipher(Fernet.generate_key().decode(), current_version=3)
    assert cipher.current_version == 3


def test_cipher_repr_does_not_leak_master_key() -> None:
    """__repr__ 에 마스터키나 Fernet 인스턴스 노출 금지."""
    master = Fernet.generate_key().decode()
    cipher = KiwoomCredentialCipher(master)
    rep = repr(cipher)
    assert master not in rep
    assert "Fernet" not in rep or "object at" in rep
