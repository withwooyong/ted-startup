"""SectorPriceDaily ORM — ka20006 업종 일봉 OHLCV (D-1).

설계: endpoint-13-ka20006.md § 5.2 + § 12.

특징 (plan § 12.2):
- #2 sector_id FK = `INTEGER REFERENCES kiwoom.sector(id)` — sector_code 단독 unique 불가
  (sector.py L31 `uq_sector_market_code (market_code, sector_code)` 페어 UNIQUE).
  UseCase 입력은 sector_id (PK).
- #3 100배 값 저장 = 4 centi BIGINT (open/high/low/close_index_centi).
  read property `.close_index = close_index_centi / 100` (float 반환) — 운영 분석 시
  사용자 친화 표시. 정수 산술이 빠르고 정확.
- #6 응답 7 필드만 (cur_prc / trde_qty / dt / open_pric / high_pric / low_pric / trde_prica).
  `pred_pre / pred_pre_sig / trde_tern_rt` 없음 → 본 모델에도 없음.

UNIQUE: (sector_id, trading_date) — 같은 업종/일자 1행 (KRX only — 거래소 분리 없음).
FK: sector_id → kiwoom.sector(id) ON DELETE CASCADE.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.adapter.out.persistence.base import Base


class SectorPriceDaily(Base):
    """ka20006 업종 일봉 OHLCV — KRX only.

    100배 값 저장 정책 (plan § 12.2 #3): 응답값 (예: "252127") 을 그대로 BIGINT 저장.
    실제 KOSPI 종가 (예: 2521.27) 가 필요한 caller 는 read property `.close_index` 사용
    (또는 / 100 직접 계산).
    """

    __tablename__ = "sector_price_daily"
    __table_args__ = (
        UniqueConstraint(
            "sector_id",
            "trading_date",
            name="uq_sector_price_daily",
        ),
        Index("idx_sector_price_daily_trading_date", "trading_date"),
        Index("idx_sector_price_daily_sector_id", "sector_id"),
        {"schema": "kiwoom"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # 1R HIGH #4: kiwoom.sector.id 가 BIGSERIAL → BIGINT 일치 (autoincrement INTEGER 와 타입 불일치 방어).
    sector_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("kiwoom.sector.id", ondelete="CASCADE"),
        nullable=False,
    )
    trading_date: Mapped[date] = mapped_column(Date, nullable=False)

    open_index_centi: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    high_index_centi: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    low_index_centi: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    close_index_centi: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    trade_volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    trade_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

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

    @property
    def close_index(self) -> float | None:
        """centi BIGINT → float 변환 — 사용자 친화 표시 (plan § 12.2 #3 read helper).

        예: close_index_centi=252127 → close_index=2521.27.
        None 이면 None 반환 (NULL 영속화 대응).
        """
        if self.close_index_centi is None:
            return None
        return self.close_index_centi / 100


__all__ = ["SectorPriceDaily"]
