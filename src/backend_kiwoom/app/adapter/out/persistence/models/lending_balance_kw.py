"""LendingBalanceKw ORM — ka10068 / ka20068 대차거래 (Phase E).

설계: endpoint-16-ka10068.md § 5.2 + endpoint-17-ka20068.md § 5 + endpoint-15-ka10014.md § 12.

특징 (plan § 12.2):
- #2 단일 테이블 — short_selling_kw 와 함께 Migration 016 에서 동시 생성.
- #3 lending 의 scope 분기 = `partial unique index 2 + CHECK constraint`.
  - `uq_lending_market_date (scope, trading_date)` WHERE `scope='MARKET' AND stock_id IS NULL`
  - `uq_lending_stock_date  (scope, stock_id, trading_date)` WHERE `scope='STOCK' AND stock_id IS NOT NULL`
  - `chk_lending_scope` — (scope=MARKET ∧ stock_id NULL) ∨ (scope=STOCK ∧ stock_id NOT NULL).
- #4 NXT 정책: ka10068 = 미적용 (시장 단위) / ka20068 = KRX only (Length=6 명세).
- scope=MARKET → stock_id NULL / scope=STOCK → stock_id FK NOT NULL (CHECK).

ORM 의 Index() 정의는 SQLAlchemy autogenerate / 테스트의 metadata 매칭용. 실제 DDL 은
`migrations/versions/016_short_lending.py` (Agent Z 담당) 가 `CREATE UNIQUE INDEX ...
WHERE ...` 로 직접 발행.

ka10068 vs ka20068 (plan § 11.3):
- ka10068 = MARKET scope (시장 단위, 단일 호출)
- ka20068 = STOCK scope (종목 단위, active 종목 iterate)
- 같은 테이블 + 같은 응답 필드 → scope 컬럼으로 row 분기.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.adapter.out.persistence.base import Base


class LendingBalanceKw(Base):
    """ka10068 / ka20068 대차거래 추이 — MARKET / STOCK scope 통합 테이블 (Phase E).

    plan § 12.2 #2 (단일 테이블) + #3 (partial unique 2 + CHECK constraint).
    """

    __tablename__ = "lending_balance_kw"
    __table_args__ = (
        # partial unique index — MARKET scope (시장 단위, stock_id NULL)
        Index(
            "uq_lending_market_date",
            "scope",
            "trading_date",
            unique=True,
            postgresql_where=text("scope = 'MARKET' AND stock_id IS NULL"),
        ),
        # partial unique index — STOCK scope (종목 단위, stock_id FK)
        Index(
            "uq_lending_stock_date",
            "scope",
            "stock_id",
            "trading_date",
            unique=True,
            postgresql_where=text("scope = 'STOCK' AND stock_id IS NOT NULL"),
        ),
        # CHECK constraint — scope ↔ stock_id 무결성 (plan § 12.2 #3)
        CheckConstraint(
            "(scope = 'MARKET' AND stock_id IS NULL) OR "
            "(scope = 'STOCK' AND stock_id IS NOT NULL)",
            name="chk_lending_scope",
        ),
        # 보조 인덱스 — date range scan + stock_id lookup
        Index("idx_lending_trading_date", "trading_date"),
        Index(
            "idx_lending_stock",
            "stock_id",
            postgresql_where=text("stock_id IS NOT NULL"),
        ),
        {"schema": "kiwoom"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # scope 분기 — "MARKET" (ka10068) / "STOCK" (ka20068). plan § 12.2 #3.
    scope: Mapped[str] = mapped_column(String(8), nullable=False)

    # MARKET scope 일 때 NULL — CHECK constraint 가 무결성 보장.
    # kiwoom.stock.id 가 BIGSERIAL → BIGINT 일치 (sector_price_daily 패턴 일관).
    stock_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("kiwoom.stock.id", ondelete="CASCADE"),
        nullable=True,
    )
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)

    contracted_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    repaid_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    delta_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    balance_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    balance_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

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


__all__ = ["LendingBalanceKw"]
