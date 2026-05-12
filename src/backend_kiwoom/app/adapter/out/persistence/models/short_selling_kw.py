"""ShortSellingKw ORM — ka10014 공매도 추이 (Phase E).

설계: endpoint-15-ka10014.md § 5.2 + § 12.

UNIQUE: (stock_id, trading_date, exchange) — 같은 종목/일자/거래소 1행 (KRX/NXT 분리).
FK: stock_id → kiwoom.stock(id) ON DELETE CASCADE.

13 도메인 컬럼 (close/prev_compare/change_rate/trade_volume + short_volume/cumulative/
weight/amount/avg_price) + 메타 (exchange + 3 타임스탬프).

D-1 sector_price_daily.py 패턴 1:1 응용 (Mapped + mapped_column + server_default=func.now()
+ onupdate=func.now() + UniqueConstraint).

partial index `idx_short_selling_kw_weight_high` (plan § 5.1) — 일별 매매비중 상위 종목
시그널 조회용. NULL 제외 (plan § 12 결정 #10 — partial 임계치 5%/15% 와 별개의 index).
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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.adapter.out.persistence.base import Base


class ShortSellingKw(Base):
    """ka10014 공매도 일별 추이 — KRX/NXT 분리 적재 (Phase E)."""

    __tablename__ = "short_selling_kw"
    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "trading_date",
            "exchange",
            name="uq_short_selling_kw",
        ),
        Index("idx_short_selling_kw_date", "trading_date"),
        Index("idx_short_selling_kw_stock", "stock_id"),
        Index(
            "idx_short_selling_kw_weight_high",
            "trading_date",
            "short_trade_weight",
            postgresql_where=text("short_trade_weight IS NOT NULL"),
        ),
        {"schema": "kiwoom"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("kiwoom.stock.id", ondelete="CASCADE"),
        nullable=False,
    )
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)
    exchange: Mapped[str] = mapped_column(String(3), nullable=False)

    close_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prev_compare_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prev_compare_sign: Mapped[str | None] = mapped_column(CHAR(1), nullable=True)
    change_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    trade_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    short_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cumulative_short_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    short_trade_weight: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    short_trade_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    short_avg_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

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


__all__ = ["ShortSellingKw"]
