"""StockPriceWeekly{Krx,Nxt} + StockPriceMonthly{Krx,Nxt} + StockPriceYearly{Krx,Nxt} ORM — ka10082/83/94 (C-3α + C-4).

설계: phase-c-3-weekly-monthly-ohlcv.md § 3.1 + endpoint-07-ka10082.md § 5.2 + endpoint-08-ka10083.md § 5.2 + endpoint-09-ka10094.md § 5.2 / § 12.

ka10081 (일봉) 의 `_DailyOhlcvMixin` 재사용 — 6 테이블 컬럼 구조 100% 동일 (H-2 검증).

period 별 의미는 영속화 테이블 이름으로 식별:
- stock_price_weekly_*: trading_date = 주의 첫 거래일
- stock_price_monthly_*: trading_date = 달의 첫 거래일
- stock_price_yearly_*: trading_date = 해의 첫 거래일 (C-4, ka10094 응답 7 필드만 — prev_compare_*/turnover_rate 는 NULL 영속)
- prev_compare_*: period 별 의미 다름 (일봉=직전 거래일 / 주봉=직전 주 / 월봉=직전 달 / 년봉=N/A — ka10094 응답 미포함)

UNIQUE: (stock_id, trading_date, adjusted) — 6 테이블 동일.
FK: stock_id → kiwoom.stock(id) ON DELETE CASCADE.
"""

from __future__ import annotations

from sqlalchemy import Index, UniqueConstraint

from app.adapter.out.persistence.base import Base
from app.adapter.out.persistence.models.stock_price import _DailyOhlcvMixin


class StockPriceWeeklyKrx(Base, _DailyOhlcvMixin):
    """ka10082 KRX 주봉 OHLCV — 백테스팅 중장기 시그널."""

    __tablename__ = "stock_price_weekly_krx"
    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "trading_date",
            "adjusted",
            name="uq_price_weekly_krx_stock_date",
        ),
        Index("idx_price_weekly_krx_trading_date", "trading_date"),
        Index("idx_price_weekly_krx_stock_id", "stock_id"),
        {"schema": "kiwoom"},
    )


class StockPriceWeeklyNxt(Base, _DailyOhlcvMixin):
    """ka10082 NXT 주봉 OHLCV."""

    __tablename__ = "stock_price_weekly_nxt"
    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "trading_date",
            "adjusted",
            name="uq_price_weekly_nxt_stock_date",
        ),
        Index("idx_price_weekly_nxt_trading_date", "trading_date"),
        Index("idx_price_weekly_nxt_stock_id", "stock_id"),
        {"schema": "kiwoom"},
    )


class StockPriceMonthlyKrx(Base, _DailyOhlcvMixin):
    """ka10083 KRX 월봉 OHLCV — 백테스팅 장기 시그널."""

    __tablename__ = "stock_price_monthly_krx"
    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "trading_date",
            "adjusted",
            name="uq_price_monthly_krx_stock_date",
        ),
        Index("idx_price_monthly_krx_trading_date", "trading_date"),
        Index("idx_price_monthly_krx_stock_id", "stock_id"),
        {"schema": "kiwoom"},
    )


class StockPriceMonthlyNxt(Base, _DailyOhlcvMixin):
    """ka10083 NXT 월봉 OHLCV."""

    __tablename__ = "stock_price_monthly_nxt"
    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "trading_date",
            "adjusted",
            name="uq_price_monthly_nxt_stock_date",
        ),
        Index("idx_price_monthly_nxt_trading_date", "trading_date"),
        Index("idx_price_monthly_nxt_stock_id", "stock_id"),
        {"schema": "kiwoom"},
    )


class StockPriceYearlyKrx(Base, _DailyOhlcvMixin):
    """ka10094 KRX 년봉 OHLCV — 백테스팅 초장기 시그널 (C-4).

    응답 7 필드만 (prev_compare_amount / prev_compare_sign / turnover_rate 는 NULL 영속).
    """

    __tablename__ = "stock_price_yearly_krx"
    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "trading_date",
            "adjusted",
            name="uq_price_yearly_krx_stock_date",
        ),
        Index("idx_price_yearly_krx_trading_date", "trading_date"),
        Index("idx_price_yearly_krx_stock_id", "stock_id"),
        {"schema": "kiwoom"},
    )


class StockPriceYearlyNxt(Base, _DailyOhlcvMixin):
    """ka10094 NXT 년봉 OHLCV — 본 chunk 정책상 호출 안 함 (yearly_nxt_disabled).

    테이블은 일관성을 위해 생성 (plan § 12.2 #2). 향후 NXT skip 해제 chunk 시 활용.
    """

    __tablename__ = "stock_price_yearly_nxt"
    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "trading_date",
            "adjusted",
            name="uq_price_yearly_nxt_stock_date",
        ),
        Index("idx_price_yearly_nxt_trading_date", "trading_date"),
        Index("idx_price_yearly_nxt_stock_id", "stock_id"),
        {"schema": "kiwoom"},
    )
