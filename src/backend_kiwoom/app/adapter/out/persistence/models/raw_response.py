"""RawResponse — 키움 응답 원본 JSON 보관 (재처리·디버깅 용).

설계: master.md § 4.1. 90일 retention 권장 (Phase H 에서 정책 확정).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.adapter.out.persistence.base import Base


class RawResponse(Base):
    """키움 endpoint 응답 원본. 재처리·스키마 변화 대응."""

    __tablename__ = "raw_response"
    __table_args__ = ({"schema": "kiwoom"},)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    api_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    http_status: Mapped[int] = mapped_column(Integer, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
