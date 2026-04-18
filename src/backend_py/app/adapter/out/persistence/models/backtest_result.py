from __future__ import annotations

from datetime import date as date_t
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.adapter.out.persistence.base import Base


class BacktestResult(Base):
    __tablename__ = "backtest_result"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    signal_type: Mapped[str] = mapped_column(String(30), nullable=False)
    period_start: Mapped[date_t] = mapped_column(Date, nullable=False)
    period_end: Mapped[date_t] = mapped_column(Date, nullable=False)
    total_signals: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    hit_count_5d: Mapped[int | None] = mapped_column(Integer, nullable=True, server_default="0")
    hit_rate_5d: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    avg_return_5d: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    hit_count_10d: Mapped[int | None] = mapped_column(Integer, nullable=True, server_default="0")
    hit_rate_10d: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    avg_return_10d: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    hit_count_20d: Mapped[int | None] = mapped_column(Integer, nullable=True, server_default="0")
    hit_rate_20d: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    avg_return_20d: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
