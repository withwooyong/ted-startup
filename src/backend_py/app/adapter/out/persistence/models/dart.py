"""DART 관련 ORM 모델."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.adapter.out.persistence.base import Base


class DartCorpMapping(Base):
    __tablename__ = "dart_corp_mapping"

    stock_code: Mapped[str] = mapped_column(String(6), primary_key=True)
    corp_code: Mapped[str] = mapped_column(String(8), nullable=False, unique=True)
    corp_name: Mapped[str] = mapped_column(String(100), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
