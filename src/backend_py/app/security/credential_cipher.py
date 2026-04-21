"""KIS 실계정 자격증명 대칭 암호화 — Fernet (AES-128-CBC + HMAC-SHA256).

설계: docs/kis-real-account-sync-plan.md § 3.2.

책임:
- plaintext → 암호문 변환(encrypt) + 역변환(decrypt)
- `key_version` 다중 저장으로 마스터키 회전 대비 (현재 v1 만)
- 마스터키 미주입(빈 문자열)이면 생성자에서 즉시 loud fail

보안 노트:
- plaintext 는 어떤 경로로도 로그에 쓰지 않는다. `__repr__` 에 민감값 없음.
- 예외 메시지에도 복호화 대상 바이트/plaintext 를 포함하지 않는다.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class CredentialCipherError(Exception):
    """자격증명 암호화 계층 최상위 예외."""


class MasterKeyNotConfiguredError(CredentialCipherError):
    """운영 환경에서 env var `KIS_CREDENTIAL_MASTER_KEY` 가 비어있을 때 앱 기동 차단."""


class UnknownKeyVersionError(CredentialCipherError):
    """DB 에 저장된 key_version 이 현재 cipher 인스턴스에 등록되지 않았을 때.

    마스터키 회전 후 구버전 키를 아직 삭제 안 한 운영상의 안전망.
    """


class DecryptionFailedError(CredentialCipherError):
    """Fernet 복호화 실패 — 토큰 손상·키 불일치·만료 토큰 등.

    외부 `InvalidToken` 을 그대로 노출하지 않고 감싸 예외 계층을 닫는다. 메시지에는
    key_version 만 포함, 바이트/plaintext 는 포함하지 않는다.
    """


class CredentialCipher:
    """Fernet 기반 대칭 암호화 래퍼.

    현재는 단일 버전(v1)만 관리하지만, 회전 시 `_fernets[2] = Fernet(new_key)` 처럼
    확장해 구·신 버전 공존을 허용한다. `encrypt` 는 항상 `_current_version` 으로 수행.
    """

    def __init__(self, master_key: str, *, current_version: int = 1) -> None:
        if not master_key:
            raise MasterKeyNotConfiguredError("KIS_CREDENTIAL_MASTER_KEY 가 비어있음 — 운영 환경은 env var 주입 필수")
        try:
            fernet = Fernet(master_key.encode())
        except ValueError as exc:
            # Fernet 은 32 바이트 url-safe base64 키를 요구. 형식 불일치 시 명확한 에러.
            raise MasterKeyNotConfiguredError(f"KIS_CREDENTIAL_MASTER_KEY 형식 오류: {exc}") from exc
        self._fernets: dict[int, Fernet] = {current_version: fernet}
        self._current_version = current_version

    @property
    def current_version(self) -> int:
        return self._current_version

    def encrypt(self, plain: str) -> tuple[bytes, int]:
        """plaintext → (ciphertext, key_version).

        ciphertext 는 Fernet 토큰 원본(base64 str) 을 bytes 로 반환 — DB BYTEA 컬럼과 대칭.
        """
        token = self._fernets[self._current_version].encrypt(plain.encode("utf-8"))
        return token, self._current_version

    def decrypt(self, cipher: bytes, key_version: int) -> str:
        """(ciphertext, key_version) → plaintext.

        key_version 이 등록 안 됐으면 `UnknownKeyVersionError`.
        Fernet 토큰 손상·키 불일치·만료 시 `DecryptionFailedError` 로 감싸 외부에
        `InvalidToken` 을 노출하지 않는다 (메시지에도 바이트/plaintext 미포함).
        """
        fernet = self._fernets.get(key_version)
        if fernet is None:
            raise UnknownKeyVersionError(f"key_version={key_version} 미등록 — 마스터키 회전 상태 확인 필요")
        try:
            return fernet.decrypt(cipher).decode("utf-8")
        except InvalidToken as exc:
            raise DecryptionFailedError(f"Fernet 복호화 실패 (key_version={key_version})") from exc
