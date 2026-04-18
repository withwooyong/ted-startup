from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.adapter.out.persistence.base import Base


class NotificationPreference(Base):
    """싱글 로우(id=1). Java 쪽 SINGLETON_ID / DEFAULT_MIN_SCORE 규약을 그대로 유지."""

    __tablename__ = "notification_preference"

    SINGLETON_ID = 1
    DEFAULT_MIN_SCORE = 60
    DEFAULT_SIGNAL_TYPES = ["RAPID_DECLINE", "TREND_REVERSAL", "SHORT_SQUEEZE"]

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    daily_summary_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    urgent_alert_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    batch_failure_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    weekly_report_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    min_score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="60")
    signal_types: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default='["RAPID_DECLINE","TREND_REVERSAL","SHORT_SQUEEZE"]',
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
