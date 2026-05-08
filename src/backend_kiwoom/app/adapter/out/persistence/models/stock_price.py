"""StockPriceKrx + StockPriceNxt ORM — ka10081 일봉 OHLCV (C-1α).

설계: endpoint-06-ka10081.md § 5.2.

KRX/NXT 두 테이블 같은 컬럼 구조 — Mixin 으로 컬럼 정의 공유.
UNIQUE: (stock_id, trading_date, adjusted) — 같은 종목/일자/수정주가 1행 (KRX/NXT 동일).
FK: stock_id → kiwoom.stock(id) ON DELETE CASCADE.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.adapter.out.persistence.base import Base


class _DailyOhlcvMixin:
    """KRX/NXT 두 테이블 공통 컬럼 정의."""

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("kiwoom.stock.id", ondelete="CASCADE"),
        nullable=False,
    )
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)
    adjusted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    open_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    high_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    low_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    close_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    trade_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    trade_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prev_compare_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prev_compare_sign: Mapped[str | None] = mapped_column(CHAR(1), nullable=True)
    turnover_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class StockPriceKrx(Base, _DailyOhlcvMixin):
    """ka10081 KRX 일봉 OHLCV — 백테스팅 코어."""

    __tablename__ = "stock_price_krx"
    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "trading_date",
            "adjusted",
            name="uq_price_krx_stock_date",
        ),
        Index("idx_price_krx_trading_date", "trading_date"),
        Index("idx_price_krx_stock_id", "stock_id"),
        {"schema": "kiwoom"},
    )


class StockPriceNxt(Base, _DailyOhlcvMixin):
    """ka10081 NXT 일봉 OHLCV — 거래소 분리."""

    __tablename__ = "stock_price_nxt"
    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "trading_date",
            "adjusted",
            name="uq_price_nxt_stock_date",
        ),
        Index("idx_price_nxt_trading_date", "trading_date"),
        Index("idx_price_nxt_stock_id", "stock_id"),
        {"schema": "kiwoom"},
    )
