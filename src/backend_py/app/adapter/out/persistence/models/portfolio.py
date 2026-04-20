"""P10 포트폴리오 도메인 ORM 모델."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.adapter.out.persistence.base import Base

# ---- Enum-like string constants (DB CHECK 제약과 동기화) ----

VALID_BROKER_CODES = ("manual", "kis", "kiwoom")
VALID_CONNECTION_TYPES = ("manual", "kis_rest_mock")
VALID_ENVIRONMENTS = ("mock", "real")
VALID_TRANSACTION_TYPES = ("BUY", "SELL")
VALID_SOURCES = ("manual", "kis_sync", "excel_import")


class BrokerageAccount(Base):
    __tablename__ = "brokerage_account"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_alias: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    broker_code: Mapped[str] = mapped_column(String(20), nullable=False)
    connection_type: Mapped[str] = mapped_column(String(20), nullable=False)
    environment: Mapped[str] = mapped_column(String(10), nullable=False, server_default="mock")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holding"
    __table_args__ = (
        UniqueConstraint("account_id", "stock_id", name="portfolio_holding_account_id_stock_id_key"),
        CheckConstraint("quantity >= 0", name="portfolio_holding_quantity_check"),
        CheckConstraint("avg_buy_price >= 0", name="portfolio_holding_avg_buy_price_check"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("brokerage_account.id", ondelete="CASCADE"), nullable=False
    )
    stock_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stock.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_buy_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    first_bought_at: Mapped[date] = mapped_column(Date, nullable=False)
    last_transacted_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PortfolioTransaction(Base):
    __tablename__ = "portfolio_transaction"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="portfolio_transaction_quantity_check"),
        CheckConstraint("price >= 0", name="portfolio_transaction_price_check"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("brokerage_account.id", ondelete="CASCADE"), nullable=False
    )
    stock_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("stock.id"), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    executed_at: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "snapshot_date", name="portfolio_snapshot_account_date_key"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("brokerage_account.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, server_default="0")
    holdings_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
