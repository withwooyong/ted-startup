"""Stock ORM — ka10099 종목 마스터.

설계: endpoint-03-ka10099.md § 5.2.

UNIQUE: stock_code 단일 (sector 의 복합키와 차이) — 한 종목이 여러 시장에 등장해도
ON CONFLICT (stock_code) UPDATE 가 market_code 를 덮어씀 (§11.2 의 알려진 위험).

is_active 디액티베이션 정책: 응답에 등장 → TRUE / 같은 mrkt_tp sync 응답에서 누락 → FALSE.
다른 시장 sync 가 같은 stock_code 의 is_active 에 영향을 미치면 안 됨 — UseCase 가
시장 단위로 isolated 호출.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.adapter.out.persistence.base import Base, TimestampMixin


class Stock(Base, TimestampMixin):
    """ka10099 종목 마스터 — 5 시장 (KOSPI/KOSDAQ/KONEX/ETN/REIT) 디폴트."""

    __tablename__ = "stock"
    __table_args__ = (
        UniqueConstraint("stock_code", name="uq_stock_code"),
        Index("idx_stock_market_code", "market_code"),
        Index(
            "idx_stock_nxt_enable",
            "nxt_enable",
            postgresql_where=text("nxt_enable = true"),
        ),
        Index(
            "idx_stock_active",
            "is_active",
            postgresql_where=text("is_active = true"),
        ),
        Index(
            "idx_stock_up_name",
            "up_name",
            postgresql_where=text("up_name IS NOT NULL"),
        ),
        {"schema": "kiwoom"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(20), nullable=False)
    stock_name: Mapped[str] = mapped_column(String(40), nullable=False)
    list_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    audit_info: Mapped[str | None] = mapped_column(String(40), nullable=True)
    listed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_price: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    state: Mapped[str | None] = mapped_column(String(255), nullable=True)
    market_code: Mapped[str] = mapped_column(String(4), nullable=False)
    market_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    up_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    up_size_name: Mapped[str | None] = mapped_column(String(20), nullable=True)
    company_class_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    order_warning: Mapped[str] = mapped_column(String(1), nullable=False, server_default="0")
    nxt_enable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
