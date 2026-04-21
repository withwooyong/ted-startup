from __future__ import annotations

from datetime import date as date_t
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.adapter.out.persistence.base import Base


class ShortSelling(Base):
    """일별 공매도 거래 — DB 레벨에서 trading_date 월별 파티션."""

    __tablename__ = "short_selling"
    __table_args__ = (UniqueConstraint("stock_id", "trading_date", name="uq_short_selling_stock_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trading_date: Mapped[date_t] = mapped_column(Date, primary_key=True)
    stock_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    short_volume: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    short_amount: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    short_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
