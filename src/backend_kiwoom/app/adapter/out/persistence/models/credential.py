"""KiwoomCredential / KiwoomToken — Fernet 암호화 BYTEA 저장.

설계: endpoint-01-au10001.md § 5.1.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.adapter.out.persistence.base import Base, TimestampMixin


class KiwoomCredential(Base, TimestampMixin):
    """키움 자격증명. appkey/secretkey 는 Fernet 암호화 후 BYTEA 저장."""

    __tablename__ = "kiwoom_credential"
    __table_args__ = (
        CheckConstraint("env IN ('prod', 'mock')", name="ck_kiwoom_credential_env"),
        {"schema": "kiwoom"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    alias: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    env: Mapped[str] = mapped_column(String(10), nullable=False)
    appkey_cipher: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    secretkey_cipher: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class KiwoomToken(Base):
    """발급된 접근토큰 캐시 (선택적). 자격증명당 1 row UNIQUE.

    MVP 는 메모리 캐시 우선. DB 캐시 본격 사용은 Phase H 결정 시점.
    """

    __tablename__ = "kiwoom_token"
    __table_args__ = (
        UniqueConstraint("credential_id", name="uq_kiwoom_token_credential_id"),
        {"schema": "kiwoom"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    credential_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("kiwoom.kiwoom_credential.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_cipher: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    token_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="bearer")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
