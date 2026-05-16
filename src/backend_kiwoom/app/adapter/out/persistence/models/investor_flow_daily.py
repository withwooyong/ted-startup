"""InvestorFlowDaily ORM — Phase G ka10058 (투자자별 일별 매매 종목 ranking).

설계: phase-g-investor-flow.md § 5.2 + endpoint-23-ka10058.md § 5.2 + Migration 019.

UNIQUE: (as_of_date, market_type, exchange_type, investor_type, trade_type, rank) — 멱등 키.
FK: stock_id → kiwoom.stock(id) ON DELETE SET NULL — lookup miss row 보존 (D-8/D-17).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.adapter.out.persistence.base import Base


class InvestorFlowDaily(Base):
    """ka10058 투자자별 일별 매매 종목 ranking (Phase G)."""

    __tablename__ = "investor_flow_daily"
    __table_args__ = (
        UniqueConstraint(
            "as_of_date",
            "market_type",
            "exchange_type",
            "investor_type",
            "trade_type",
            "rank",
            name="uq_investor_flow_daily",
        ),
        Index(
            "idx_ifd_date_investor",
            "as_of_date",
            "investor_type",
            "trade_type",
            "market_type",
        ),
        Index(
            "idx_ifd_stock",
            "stock_id",
            postgresql_where=text("stock_id IS NOT NULL"),
        ),
        {"schema": "kiwoom"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    market_type: Mapped[str] = mapped_column(String(3), nullable=False)
    exchange_type: Mapped[str] = mapped_column(String(1), nullable=False)
    investor_type: Mapped[str] = mapped_column(String(4), nullable=False)
    trade_type: Mapped[str] = mapped_column(String(1), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    stock_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("kiwoom.stock.id", ondelete="SET NULL"),
        nullable=True,
    )
    stock_code_raw: Mapped[str] = mapped_column(String(20), nullable=False)
    stock_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    net_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    estimated_avg_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    current_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prev_compare_sign: Mapped[str | None] = mapped_column(String(1), nullable=True)
    prev_compare_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    avg_price_compare: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prev_compare_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    period_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


__all__ = ["InvestorFlowDaily"]
