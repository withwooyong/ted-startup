"""StockFundamental ORM — ka10001 종목 펀더멘털 일별 스냅샷 (B-γ-1).

설계: endpoint-05-ka10001.md § 5.2.

UNIQUE: (stock_id, asof_date, exchange) — 같은 종목/일자/거래소 1행.
FK: stock_id → kiwoom.stock(id) ON DELETE CASCADE.

KRX-only (계획서 § 4.3 (a)) — exchange 디폴트 'KRX'. NXT/SOR 추가는 Phase C 후 결정.
컬럼 NULL 허용 — 외부 벤더 PER/EPS/ROE/PBR/EV 빈값 종목 (§ 11.2).
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

from app.adapter.out.persistence.base import Base, TimestampMixin


class StockFundamental(Base, TimestampMixin):
    """ka10001 종목 펀더멘털 — 일별 스냅샷 (45 필드 + hash + 타임스탬프)."""

    __tablename__ = "stock_fundamental"
    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "asof_date",
            "exchange",
            name="uq_fundamental_stock_date_exchange",
        ),
        Index("idx_fundamental_asof_date", "asof_date"),
        Index("idx_fundamental_stock_id", "stock_id"),
        {"schema": "kiwoom"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("kiwoom.stock.id", ondelete="CASCADE"),
        nullable=False,
    )
    asof_date: Mapped[date] = mapped_column(Date, nullable=False)
    exchange: Mapped[str] = mapped_column(String(4), nullable=False, server_default="KRX")

    # A. 기본 — DB 는 CHAR(2) (Migration 004 SQL 일치, B-γ-1 2R L-2)
    settlement_month: Mapped[str | None] = mapped_column(CHAR(2), nullable=True)

    # B. 자본 / 시총 / 외인
    face_value: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    face_value_unit: Mapped[str | None] = mapped_column(String(10), nullable=True)
    capital_won: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    listed_shares: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    market_cap: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    market_cap_weight: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    foreign_holding_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    replacement_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    credit_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    circulating_shares: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    circulating_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)

    # C. 재무 비율 (외부 벤더)
    per_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    eps_won: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    roe_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    pbr_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    ev_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    bps_won: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    revenue_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    operating_profit: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    net_profit: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # D. 250일 / 연중 통계
    high_250d: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    high_250d_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    high_250d_pre_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    low_250d: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    low_250d_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Phase F-1 (§ 4 결정 #2) — Numeric(8,4) → Numeric(10,4). max 999,999.9999.
    # 5-13 cron 실측 max=5745.71 (57.5%). 테마주 250일 점프 대응 마진.
    low_250d_pre_rate: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    year_high: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    year_low: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # E. 일중 시세 (응답 시점 KST)
    current_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prev_compare_sign: Mapped[str | None] = mapped_column(CHAR(1), nullable=True)
    prev_compare_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    change_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    trade_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Phase F-1 (§ 4 결정 #1) — Numeric(8,4) → Numeric(12,4). max 99,999,999.9999.
    # 5-13 cron 18:00 NumericValueOutOfRangeError 11건 (실측 max=8950, 89.5%).
    trade_compare_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    open_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    high_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    low_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    upper_limit_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    lower_limit_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    base_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    expected_match_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    expected_match_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # 변경 감지 hash — DB 는 CHAR(32) (B-γ-1 2R L-2)
    fundamental_hash: Mapped[str | None] = mapped_column(CHAR(32), nullable=True)

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
