"""RankingSnapshot ORM — Phase F-4 ka10027/30/31/32/23 5 ranking endpoint 통합 스냅샷.

설계: phase-f-4-rankings.md § 5.2 + Migration 018.

UNIQUE: (snapshot_date, snapshot_time, ranking_type, sort_tp, market_type, exchange_type, rank) — 멱등 키.
FK: stock_id → kiwoom.stock(id) ON DELETE SET NULL — lookup miss row 보존 (D-8).

13 도메인 컬럼 + 메타 2 (fetched_at / created_at) = 15 컬럼 (id 포함).

D-9 nested payload — ka10030 23 필드를 {opmr, af_mkrt, bf_mkrt} 3 그룹 분리.
D-12 NUMERIC(20, 4) — endpoint-18 합의 (큰 거래대금 + 작은 등락률 모두 정밀도 보존).
D-13 GIN index payload — ad-hoc 쿼리 가속.

016 short_selling_kw 패턴 1:1 응용 (Mapped + mapped_column + server_default=func.now()).
"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.adapter.out.persistence.base import Base


class RankingSnapshot(Base):
    """ka10027/30/31/32/23 5 ranking endpoint 통합 스냅샷 — JSONB payload + ranking_type 컬럼 (Phase F-4)."""

    __tablename__ = "ranking_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_date",
            "snapshot_time",
            "ranking_type",
            "sort_tp",
            "market_type",
            "exchange_type",
            "rank",
            name="uq_ranking_snapshot",
        ),
        Index(
            "idx_ranking_date_type",
            "snapshot_date",
            "ranking_type",
            "market_type",
            "exchange_type",
        ),
        Index(
            "idx_ranking_stock",
            "stock_id",
            postgresql_where=text("stock_id IS NOT NULL"),
        ),
        Index(
            "idx_ranking_payload_gin",
            "payload",
            postgresql_using="gin",
        ),
        {"schema": "kiwoom"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    snapshot_time: Mapped[time] = mapped_column(Time, nullable=False)
    ranking_type: Mapped[str] = mapped_column(String(16), nullable=False)
    sort_tp: Mapped[str] = mapped_column(String(2), nullable=False)
    market_type: Mapped[str] = mapped_column(String(3), nullable=False)
    exchange_type: Mapped[str] = mapped_column(String(1), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    stock_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("kiwoom.stock.id", ondelete="SET NULL"),
        nullable=True,
    )
    stock_code_raw: Mapped[str] = mapped_column(String(20), nullable=False)

    primary_metric: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)

    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    request_filters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

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


__all__ = ["RankingSnapshot"]
