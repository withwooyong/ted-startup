"""FrgnOrgnConsecutive ORM — Phase G ka10131 (기관/외국인 연속매매 ranking, 15 metric).

설계: phase-g-investor-flow.md § 5.2 + endpoint-25-ka10131.md § 5.2 + Migration 019.

UNIQUE: (as_of_date, period_type, market_type, amt_qty_tp, stk_inds_tp, exchange_type, rank) — 멱등 키.
FK: stock_id → kiwoom.stock(id) ON DELETE SET NULL — lookup miss row 보존.

idx_foc_total_cont_days = (as_of_date, total_cont_days DESC NULLS LAST) — 시그널 핵심 (Phase H).
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


class FrgnOrgnConsecutive(Base):
    """ka10131 기관/외국인 연속매매 ranking (Phase G — 15 metric: 기관 5 + 외국인 5 + 합계 5)."""

    __tablename__ = "frgn_orgn_consecutive"
    __table_args__ = (
        UniqueConstraint(
            "as_of_date",
            "period_type",
            "market_type",
            "amt_qty_tp",
            "stk_inds_tp",
            "exchange_type",
            "rank",
            name="uq_frgn_orgn_consecutive",
        ),
        Index(
            "idx_foc_date_market",
            "as_of_date",
            "market_type",
            "period_type",
        ),
        Index(
            "idx_foc_stock",
            "stock_id",
            postgresql_where=text("stock_id IS NOT NULL"),
        ),
        # 시그널 핵심 — total_cont_days DESC NULLS LAST (Phase H derived feature).
        Index(
            "idx_foc_total_cont_days",
            "as_of_date",
            text("total_cont_days DESC NULLS LAST"),
        ),
        {"schema": "kiwoom"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_type: Mapped[str] = mapped_column(String(3), nullable=False)
    market_type: Mapped[str] = mapped_column(String(3), nullable=False)
    amt_qty_tp: Mapped[str] = mapped_column(String(1), nullable=False)
    stk_inds_tp: Mapped[str] = mapped_column(String(1), nullable=False)
    exchange_type: Mapped[str] = mapped_column(String(1), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    stock_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("kiwoom.stock.id", ondelete="SET NULL"),
        nullable=True,
    )
    stock_code_raw: Mapped[str] = mapped_column(String(20), nullable=False)
    stock_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    period_stock_price_flu_rt: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

    # 기관 5 metric
    orgn_net_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    orgn_net_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    orgn_cont_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    orgn_cont_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    orgn_cont_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # 외국인 5 metric
    frgnr_net_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    frgnr_net_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    frgnr_cont_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frgnr_cont_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    frgnr_cont_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # 합계 5 metric (기관 + 외국인)
    total_net_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_net_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_cont_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_cont_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_cont_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

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


__all__ = ["FrgnOrgnConsecutive"]
