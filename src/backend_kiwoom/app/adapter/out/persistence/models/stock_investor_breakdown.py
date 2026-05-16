"""StockInvestorBreakdown ORM — Phase G ka10059 (종목별 투자자 wide breakdown, 12 net).

설계: phase-g-investor-flow.md § 5.2 + endpoint-24-ka10059.md § 5.2 + Migration 019.

UNIQUE: (stock_id, trading_date, amt_qty_tp, trade_type, unit_tp, exchange_type) — 멱등 키.
FK: stock_id → kiwoom.stock(id) ON DELETE SET NULL — lookup miss row 보존.
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
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.adapter.out.persistence.base import Base


class StockInvestorBreakdown(Base):
    """ka10059 종목별 투자자/기관별 wide breakdown (Phase G — 12 net 카테고리)."""

    __tablename__ = "stock_investor_breakdown"
    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "trading_date",
            "amt_qty_tp",
            "trade_type",
            "unit_tp",
            "exchange_type",
            name="uq_stock_investor_breakdown",
        ),
        Index(
            "idx_sib_stock_date",
            "stock_id",
            "trading_date",
            postgresql_where=text("stock_id IS NOT NULL"),
        ),
        Index("idx_sib_date", "trading_date"),
        {"schema": "kiwoom"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    stock_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("kiwoom.stock.id", ondelete="SET NULL"),
        nullable=True,
    )
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)
    amt_qty_tp: Mapped[str] = mapped_column(String(1), nullable=False)
    trade_type: Mapped[str] = mapped_column(String(1), nullable=False)
    unit_tp: Mapped[str] = mapped_column(String(4), nullable=False)
    exchange_type: Mapped[str] = mapped_column(String(1), nullable=False)

    current_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prev_compare_sign: Mapped[str | None] = mapped_column(String(1), nullable=True)
    prev_compare_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    change_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    acc_trade_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    acc_trade_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # 12 투자자 카테고리 net (부호 포함)
    net_individual: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_foreign: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_institution_total: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_financial_inv: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_insurance: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_investment_trust: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_other_financial: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_bank: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_pension_fund: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_private_fund: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_nation: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_other_corp: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_dom_for: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

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


__all__ = ["StockInvestorBreakdown"]
