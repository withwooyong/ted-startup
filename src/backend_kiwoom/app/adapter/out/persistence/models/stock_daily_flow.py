"""StockDailyFlow ORM — ka10086 일별 수급 (C-2α + C-2γ).

설계: endpoint-10-ka10086.md § 5.2 + § 12 (C-2γ Migration 008).

UNIQUE: (stock_id, trading_date, exchange) — 같은 종목/일자/거래소 1행 (KRX/NXT 분리).
FK: stock_id → kiwoom.stock(id) ON DELETE CASCADE.

10 도메인 컬럼 (신용 2 + 투자자별 4 + 외인 4) + 메타 (exchange / indc_mode + 3 타임스탬프).
OHLCV 8 필드는 ka10081 stock_price_krx/nxt 가 정답 — 본 ORM 에 미적재.

C-2γ (Migration 008): D-E 중복 3 컬럼 (individual_net_purchase / institutional_net_purchase /
foreign_net_purchase) DROP. dry-run § 20.2 #1 — D 카테고리 (individual_net / institutional_net /
foreign_volume) 와 100% 동일값 확인.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.adapter.out.persistence.base import Base


class StockDailyFlow(Base):
    """ka10086 일별 수급 (신용 + 투자자별 + 외인)."""

    __tablename__ = "stock_daily_flow"
    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "trading_date",
            "exchange",
            name="uq_daily_flow_stock_date_exchange",
        ),
        Index("idx_daily_flow_trading_date", "trading_date"),
        Index("idx_daily_flow_stock_id", "stock_id"),
        Index("idx_daily_flow_exchange", "exchange"),
        {"schema": "kiwoom"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("kiwoom.stock.id", ondelete="CASCADE"),
        nullable=False,
    )
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)
    exchange: Mapped[str] = mapped_column(String(4), nullable=False)
    indc_mode: Mapped[str] = mapped_column(CHAR(1), nullable=False)

    # C. 신용
    credit_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    credit_balance_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

    # D. 투자자별 net (단위 indc_mode 따름)
    individual_net: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    institutional_net: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    foreign_brokerage_net: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    program_net: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # E. 외인 (C-2γ — 순매수 3 컬럼 DROP, D 카테고리와 중복이라 의미 없음)
    foreign_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    foreign_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    foreign_holdings: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    foreign_weight: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

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
