from __future__ import annotations

from datetime import date as date_t
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Integer, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.adapter.out.persistence.base import Base


class LendingBalance(Base):
    """일별 대차잔고 — DB 레벨에서 trading_date 월별 파티션."""

    __tablename__ = "lending_balance"
    __table_args__ = (UniqueConstraint("stock_id", "trading_date", name="uq_lending_balance_stock_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trading_date: Mapped[date_t] = mapped_column(Date, primary_key=True)
    stock_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    balance_quantity: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    balance_amount: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    change_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    change_quantity: Mapped[int | None] = mapped_column(BigInteger, nullable=True, server_default="0")
    consecutive_decrease_days: Mapped[int | None] = mapped_column(Integer, nullable=True, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
