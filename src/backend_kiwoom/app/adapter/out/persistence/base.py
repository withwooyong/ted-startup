"""SQLAlchemy 2.0 DeclarativeBase + 공용 컬럼 mixin."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """모든 ORM 모델의 부모. metadata 는 kiwoom 스키마로 모인다 (모델별 schema 옵션)."""


class TimestampMixin:
    """created_at / updated_at TZ-aware. server_default + onupdate."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
