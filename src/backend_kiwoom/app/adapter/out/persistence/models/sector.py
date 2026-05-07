"""Sector ORM — ka10101 업종 마스터.

설계: endpoint-14-ka10101.md § 5.2.

`market_code` 는 `Literal["0","1","2","4","7"]` 도메인이지만 ORM 컬럼은 `String(2)` 으로
선언 (Python 측 타입은 `str`). 도메인 검증은 UseCase / Pydantic / DB CHECK constraint
3중 방어로 강제 — ORM 단계에서는 운영 마이그레이션 호환성을 우선.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.adapter.out.persistence.base import Base, TimestampMixin


class Sector(Base, TimestampMixin):
    """ka10101 업종 마스터 — 5 시장 (KOSPI/KOSDAQ/KOSPI200/KOSPI100/KRX100).

    동기화 정책 (디액티베이션 정책 B):
    - 응답에 등장하면 `is_active=TRUE` (upsert 시 강제)
    - 응답에서 빠진 (market_code, sector_code) 는 `is_active=FALSE` UPDATE
    - DELETE 안 함 — FK 참조 안전 + 과거 데이터 보존
    """

    __tablename__ = "sector"
    __table_args__ = (
        UniqueConstraint("market_code", "sector_code", name="uq_sector_market_code"),
        CheckConstraint(
            "market_code IN ('0', '1', '2', '4', '7')",
            name="ck_sector_market_code",
        ),
        {"schema": "kiwoom"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    market_code: Mapped[str] = mapped_column(String(2), nullable=False)
    sector_code: Mapped[str] = mapped_column(String(10), nullable=False)
    sector_name: Mapped[str] = mapped_column(String(100), nullable=False)
    group_no: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
