from __future__ import annotations

from datetime import date as date_t
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.adapter.out.persistence.base import Base


class Signal(Base):
    __tablename__ = "signal"
    __table_args__ = (
        UniqueConstraint("stock_id", "signal_date", "signal_type", name="uq_signal_stock_date_type"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stock.id"), nullable=False, index=True)
    signal_date: Mapped[date_t] = mapped_column(Date, nullable=False)
    signal_type: Mapped[str] = mapped_column(String(30), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    grade: Mapped[str] = mapped_column(String(1), nullable=False)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    return_5d: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    return_10d: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    return_20d: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
