"""KIS 실계정 자격증명 Repository — Fernet 암호화/복호화 경유.

설계: docs/kis-real-account-sync-plan.md § 3.2.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.external import KisCredentials
from app.adapter.out.persistence.models import BrokerageAccountCredential
from app.security.credential_cipher import CredentialCipher


@dataclass(frozen=True, slots=True)
class MaskedCredentialView:
    """GET 응답용 마스킹된 자격증명 뷰.

    `app_secret` 은 어떤 경로로도 노출되지 않는다. `app_key`·`account_no` 는
    마지막 4자리만 남기고 나머지는 `•` 로 치환한 문자열.
    """

    account_id: int
    app_key_masked: str
    account_no_masked: str
    key_version: int
    created_at: datetime
    updated_at: datetime


def _mask_tail(value: str, keep: int = 4) -> str:
    """`<masked prefix><last N>` 형태로 치환 — 비례 길이 마스킹.

    마스킹된 prefix 의 불릿 수가 실제 가려진 문자 수와 일치해야 "얼마나 가렸는지" 가
    시각적으로 드러난다. 고정 4개 불릿은 짧은 값에서 노출 비율이 과도해질 수 있어 지양.
    길이가 `keep` 이하면 전체를 불릿으로 치환, 빈 값은 단일 불릿으로.
    """
    if not value:
        return "•"
    if len(value) <= keep:
        return "•" * len(value)
    return "•" * (len(value) - keep) + value[-keep:]


class BrokerageAccountCredentialRepository:
    """계좌당 1 레코드의 KIS 자격증명을 암호화해 영속화.

    도메인 DTO(`KisCredentials`) 를 경계로 주고받아 ORM 모델이 외부로 새지 않게 한다.
    Plaintext 는 여기서만 오가며, 복호화 결과는 use case 스코프 안에서만 사용되어야 한다.
    """

    def __init__(self, session: AsyncSession, cipher: CredentialCipher) -> None:
        self._session = session
        self._cipher = cipher

    async def upsert(self, account_id: int, credentials: KisCredentials) -> None:
        """3 필드를 각각 암호화해 INSERT 또는 UPDATE. 계좌당 1 레코드 보장(UNIQUE)."""
        app_key_cipher, key_version = self._cipher.encrypt(credentials.app_key)
        app_secret_cipher, _ = self._cipher.encrypt(credentials.app_secret)
        account_no_cipher, _ = self._cipher.encrypt(credentials.account_no)

        existing = await self._find(account_id)
        if existing is None:
            self._session.add(
                BrokerageAccountCredential(
                    account_id=account_id,
                    app_key_cipher=app_key_cipher,
                    app_secret_cipher=app_secret_cipher,
                    account_no_cipher=account_no_cipher,
                    key_version=key_version,
                )
            )
            await self._session.flush()
            return

        existing.app_key_cipher = app_key_cipher
        existing.app_secret_cipher = app_secret_cipher
        existing.account_no_cipher = account_no_cipher
        existing.key_version = key_version
        await self._session.flush()

    async def get_decrypted(self, account_id: int) -> KisCredentials | None:
        """암호화된 3 필드를 복호화해 DTO 조립. 레코드 없으면 None.

        복호화 실패(`InvalidToken`) 는 그대로 전파 — 호출자가 `MasterKeyNotConfiguredError`
        이나 `UnknownKeyVersionError` 와 구분해 처리할 수 있게 한다.
        """
        row = await self._find(account_id)
        if row is None:
            return None
        return KisCredentials(
            app_key=self._cipher.decrypt(row.app_key_cipher, row.key_version),
            app_secret=self._cipher.decrypt(row.app_secret_cipher, row.key_version),
            account_no=self._cipher.decrypt(row.account_no_cipher, row.key_version),
        )

    async def delete(self, account_id: int) -> bool:
        """명시 삭제. FK CASCADE 로 계좌 삭제 시 자동 제거되지만 직접 호출도 지원.

        Returns: 1 이면 삭제됨, 0 이면 대상 없음.
        """
        stmt = (
            delete(BrokerageAccountCredential)
            .where(BrokerageAccountCredential.account_id == account_id)
        )
        # AsyncSession.execute 의 반환은 런타임상 CursorResult 지만 mypy 는 Result[Any] 로
        # 좁히지 못해 rowcount 접근이 type 오류. 안전한 런타임 동작을 기반으로 명시 캐스트.
        result: CursorResult[object] = await self._session.execute(stmt)  # type: ignore[assignment]
        await self._session.flush()
        rowcount = result.rowcount
        return bool(rowcount is not None and rowcount > 0)

    async def find_row(self, account_id: int) -> BrokerageAccountCredential | None:
        """복호화 없이 ORM 행만 반환 — 존재 여부 체크나 메타데이터(updated_at 등)용."""
        return await self._find(account_id)

    async def get_masked_view(self, account_id: int) -> MaskedCredentialView | None:
        """GET 응답용 마스킹 뷰. `app_key`·`account_no` 만 복호화해 tail 4자리만 남김.

        `app_secret` 은 어떤 경로로도 plaintext 화되지 않는다 — 조회 기능 자체가 없음.
        """
        row = await self._find(account_id)
        if row is None:
            return None
        app_key_plain = self._cipher.decrypt(row.app_key_cipher, row.key_version)
        account_no_plain = self._cipher.decrypt(row.account_no_cipher, row.key_version)
        return MaskedCredentialView(
            account_id=row.account_id,
            app_key_masked=_mask_tail(app_key_plain),
            account_no_masked=_mask_tail(account_no_plain),
            key_version=row.key_version,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def _find(self, account_id: int) -> BrokerageAccountCredential | None:
        stmt = select(BrokerageAccountCredential).where(
            BrokerageAccountCredential.account_id == account_id
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()
