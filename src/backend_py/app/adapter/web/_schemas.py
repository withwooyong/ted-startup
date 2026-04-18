"""HTTP 요청/응답 Pydantic 스키마.

OpenAPI 문서화와 타입 안정성을 동시에 제공. ORM 모델은 직접 노출하지 않고
이 스키마로 변환해 필드 노출 범위를 제어.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Signals ----------

class SignalResponse(_Base):
    id: int
    stock_id: int
    stock_code: str | None = None
    stock_name: str | None = None
    signal_date: date
    signal_type: str
    score: int
    grade: str
    detail: dict[str, Any] | None = None
    return_5d: Decimal | None = None
    return_10d: Decimal | None = None
    return_20d: Decimal | None = None


class StockSummary(_Base):
    stock_code: str
    stock_name: str
    market_type: str


class StockPricePoint(_Base):
    trading_date: date
    close_price: int
    open_price: int | None = None
    high_price: int | None = None
    low_price: int | None = None
    volume: int
    change_rate: Decimal | None = None


class StockDetailResponse(BaseModel):
    stock: StockSummary
    prices: list[StockPricePoint]
    signals: list[SignalResponse]


# ---------- Backtest ----------

class BacktestResultResponse(_Base):
    id: int
    signal_type: str
    period_start: date
    period_end: date
    total_signals: int
    hit_count_5d: int | None = None
    hit_rate_5d: Decimal | None = None
    avg_return_5d: Decimal | None = None
    hit_count_10d: int | None = None
    hit_rate_10d: Decimal | None = None
    avg_return_10d: Decimal | None = None
    hit_count_20d: int | None = None
    hit_rate_20d: Decimal | None = None
    avg_return_20d: Decimal | None = None
    created_at: datetime


# ---------- Notification Preference ----------

class NotificationPreferenceResponse(_Base):
    id: int
    daily_summary_enabled: bool
    urgent_alert_enabled: bool
    batch_failure_enabled: bool
    weekly_report_enabled: bool
    min_score: int
    signal_types: list[str]
    updated_at: datetime


ScoreInt = Annotated[int, Field(ge=0, le=100)]


class NotificationPreferenceUpdateRequest(BaseModel):
    daily_summary_enabled: bool
    urgent_alert_enabled: bool
    batch_failure_enabled: bool
    weekly_report_enabled: bool
    min_score: ScoreInt
    signal_types: Annotated[list[str], Field(min_length=1, max_length=3)]
