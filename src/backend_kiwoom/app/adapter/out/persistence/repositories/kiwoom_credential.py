"""KiwoomCredentialRepository — appkey/secretkey Fernet 암호화 CRUD.

설계: endpoint-01-au10001.md § 6.

책임:
- alias 단위 upsert (insert / update on conflict)
- find_by_alias (활성 여부 무관, 비활성 자격증명도 조회 가능)
- get_decrypted (Fernet 복호화 후 KiwoomCredentials 반환)
- get_masked_view (외부 응답용)
- delete (alias)
- list_active_by_env (배치 / 스케줄러)
"""

from __future__ import annotations

from typing import Literal

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.models import KiwoomCredential
from app.adapter.out.persistence.repositories._helpers import rowcount_of
from app.application.dto.kiwoom_auth import (
    KiwoomCredentials,
    MaskedKiwoomCredentialView,
    mask_appkey,
    mask_secretkey,
)
from app.security.kiwoom_credential_cipher import KiwoomCredentialCipher

KiwoomEnv = Literal["prod", "mock"]


class KiwoomCredentialRepository:
    """키움 자격증명 영속 계층.

    cipher 를 생성자 주입 받아 encrypt/decrypt 를 위임 — 마스터키 회전 시점에
    인스턴스만 교체.
    """

    def __init__(self, session: AsyncSession, cipher: KiwoomCredentialCipher) -> None:
        self._session = session
        self._cipher = cipher

    async def upsert(
        self, *, alias: str, env: KiwoomEnv, credentials: KiwoomCredentials
    ) -> KiwoomCredential:
        """alias UNIQUE 기반 upsert. 기존 row 있으면 ciphertext + key_version + is_active 갱신.

        env 는 Literal 로 도메인 계층에서 검증 — DB CheckConstraint 도달 전 차단.
        """
        appkey_cipher, key_version = self._cipher.encrypt(credentials.appkey)
        secretkey_cipher, _ = self._cipher.encrypt(credentials.secretkey)

        stmt = pg_insert(KiwoomCredential).values(
            alias=alias,
            env=env,
            appkey_cipher=appkey_cipher,
            secretkey_cipher=secretkey_cipher,
            key_version=key_version,
            is_active=True,
        )
        # ON CONFLICT 시 updated_at 은 명시적으로 NOW() — excluded.updated_at 은 NULL
        # (INSERT VALUES 절에 미포함된 컬럼은 excluded 에서도 NULL).
        stmt = stmt.on_conflict_do_update(
            index_elements=["alias"],
            set_={
                "env": stmt.excluded.env,
                "appkey_cipher": stmt.excluded.appkey_cipher,
                "secretkey_cipher": stmt.excluded.secretkey_cipher,
                "key_version": stmt.excluded.key_version,
                "is_active": True,
                "updated_at": func.now(),
            },
        )
        await self._session.execute(stmt)
        await self._session.flush()
        row = await self.find_by_alias(alias)
        # 사후조건. python -O 에서 assert 가 무력화되므로 명시 raise.
        if row is None:
            raise RuntimeError(f"upsert post-condition violated: alias={alias!r} not found after flush")
        return row

    async def find_by_alias(self, alias: str) -> KiwoomCredential | None:
        stmt = select(KiwoomCredential).where(KiwoomCredential.alias == alias)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def get_decrypted(self, *, alias: str) -> KiwoomCredentials | None:
        """평문 자격증명 반환. 없으면 None.

        DecryptionFailedError 가 발생하면 그대로 호출자에게 전파 — 마스터키 회전 등
        운영 이슈를 caller 가 인지해야 함.
        """
        row = await self.find_by_alias(alias)
        if row is None:
            return None
        appkey = self._cipher.decrypt(row.appkey_cipher, row.key_version)
        secretkey = self._cipher.decrypt(row.secretkey_cipher, row.key_version)
        return KiwoomCredentials(appkey=appkey, secretkey=secretkey)

    async def get_masked_view(self, *, alias: str) -> MaskedKiwoomCredentialView | None:
        """외부 응답 (admin 라우터) 용. secretkey 는 어떤 경로로도 평문 노출 안 됨."""
        row = await self.find_by_alias(alias)
        if row is None:
            return None
        # appkey 만 tail 4 노출. secretkey 는 평문 자체를 메모리에 올리지 않으려 복호화 안 함.
        appkey_plain = self._cipher.decrypt(row.appkey_cipher, row.key_version)
        return MaskedKiwoomCredentialView(
            alias=row.alias,
            env=row.env,
            appkey_masked=mask_appkey(appkey_plain),
            secretkey_masked=mask_secretkey(""),  # 평문 미접근
            is_active=row.is_active,
            key_version=row.key_version,
        )

    async def delete(self, *, alias: str) -> bool:
        """alias 삭제. 없으면 False."""
        stmt = delete(KiwoomCredential).where(KiwoomCredential.alias == alias)
        result = await self._session.execute(stmt)
        await self._session.flush()
        return rowcount_of(result) > 0

    async def deactivate(self, *, alias: str) -> bool:
        """is_active=False 로 소프트 비활성화. 없으면 False.

        DELETE 와 달리 row 보존 — 추후 재활성화 가능 (upsert 가 is_active=True 강제).
        list_active_by_env() 가 이 행을 결과에서 제외.
        """
        stmt = (
            update(KiwoomCredential)
            .where(KiwoomCredential.alias == alias)
            .where(KiwoomCredential.is_active.is_(True))
            .values(is_active=False, updated_at=func.now())
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return rowcount_of(result) > 0

    async def list_active_by_env(self, env: KiwoomEnv) -> list[KiwoomCredential]:
        """활성 자격증명만 환경별 조회."""
        stmt = (
            select(KiwoomCredential)
            .where(KiwoomCredential.env == env)
            .where(KiwoomCredential.is_active.is_(True))
            .order_by(KiwoomCredential.alias)
        )
        return list((await self._session.execute(stmt)).scalars())
