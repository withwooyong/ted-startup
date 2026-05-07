"""키움 자격증명 대칭 암호화 — Fernet (AES-128-CBC + HMAC-SHA256).

설계: master.md § 6.5 / endpoint-01-au10001.md § 5.

책임:
- plaintext (appkey/secretkey/token) → 암호문 변환 + 역변환
- key_version 다중 저장으로 마스터키 회전 대비 (현재 v1)
- 마스터키 미주입 시 즉시 loud fail (운영 환경 보호)

보안 노트:
- plaintext 는 어떤 경로로도 로그에 쓰지 않음. __repr__ 에 민감값 없음.
- 예외 메시지에도 복호화 대상 바이트/plaintext 미포함.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class KiwoomCredentialCipherError(Exception):
    """키움 자격증명 암호화 계층 최상위 예외."""


class MasterKeyNotConfiguredError(KiwoomCredentialCipherError):
    """`KIWOOM_CREDENTIAL_MASTER_KEY` env 미주입 — 앱 기동 차단."""


class UnknownKeyVersionError(KiwoomCredentialCipherError):
    """DB row 의 key_version 이 cipher 인스턴스에 등록 안 됨.

    마스터키 회전 후 구버전 키를 미보존한 운영상의 안전망.
    """


class DecryptionFailedError(KiwoomCredentialCipherError):
    """Fernet 복호화 실패 — 토큰 손상 / 키 불일치 / 만료.

    외부 InvalidToken 을 그대로 노출하지 않고 감쌈. 메시지에는 key_version 만 포함.
    바이트/plaintext 미포함.
    """


class KiwoomCredentialCipher:
    """Fernet 기반 대칭 암호화 래퍼.

    회전 시 `_fernets[2] = Fernet(new_key)` 처럼 확장해 구·신 버전 공존 허용.
    encrypt 는 항상 `_current_version` 으로 수행.
    """

    def __init__(self, master_key: str, *, current_version: int = 1) -> None:
        if not master_key:
            raise MasterKeyNotConfiguredError(
                "KIWOOM_CREDENTIAL_MASTER_KEY 가 비어있음 — 운영 환경은 env var 주입 필수"
            )
        try:
            fernet = Fernet(master_key.encode())
        except ValueError as exc:
            raise MasterKeyNotConfiguredError(f"KIWOOM_CREDENTIAL_MASTER_KEY 형식 오류: {exc}") from exc
        self._fernets: dict[int, Fernet] = {current_version: fernet}
        self._current_version = current_version

    @property
    def current_version(self) -> int:
        return self._current_version

    def encrypt(self, plain: str) -> tuple[bytes, int]:
        """plaintext → (ciphertext bytes, key_version).

        Fernet 토큰(base64 str) 을 bytes 로 반환 — DB BYTEA 컬럼과 대칭.
        """
        token = self._fernets[self._current_version].encrypt(plain.encode("utf-8"))
        return token, self._current_version

    def decrypt(self, cipher: bytes, key_version: int) -> str:
        fernet = self._fernets.get(key_version)
        if fernet is None:
            raise UnknownKeyVersionError(f"key_version={key_version} 미등록 — 마스터키 회전 상태 확인 필요")
        try:
            return fernet.decrypt(cipher).decode("utf-8")
        except InvalidToken as exc:
            raise DecryptionFailedError(f"Fernet 복호화 실패 (key_version={key_version})") from exc

    def __repr__(self) -> str:
        return f"KiwoomCredentialCipher(current_version={self._current_version}, registered={list(self._fernets)})"
