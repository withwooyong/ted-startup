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


# ---------- Portfolio (P10) ----------


AliasStr = Annotated[str, Field(min_length=1, max_length=50)]
QuantityPositive = Annotated[int, Field(gt=0)]
PriceNonNegative = Annotated[Decimal, Field(ge=Decimal("0"))]


class AccountCreateRequest(BaseModel):
    account_alias: AliasStr
    broker_code: Annotated[str, Field(pattern=r"^(manual|kis|kiwoom)$")]
    connection_type: Annotated[str, Field(pattern=r"^(manual|kis_rest_mock)$")]
    environment: Annotated[str, Field(pattern=r"^mock$")] = "mock"


class AccountResponse(_Base):
    id: int
    account_alias: str
    broker_code: str
    connection_type: str
    environment: str
    is_active: bool
    created_at: datetime


class TransactionCreateRequest(BaseModel):
    stock_code: Annotated[str, Field(min_length=6, max_length=6)]
    transaction_type: Annotated[str, Field(pattern=r"^(BUY|SELL)$")]
    quantity: QuantityPositive
    price: PriceNonNegative
    executed_at: date
    memo: Annotated[str | None, Field(max_length=1000)] = None


class TransactionResponse(_Base):
    id: int
    account_id: int
    stock_id: int
    transaction_type: str
    quantity: int
    price: Decimal
    executed_at: date
    source: str
    memo: str | None = None
    created_at: datetime


class HoldingResponse(_Base):
    account_id: int
    stock_id: int
    stock_code: str | None = None
    stock_name: str | None = None
    quantity: int
    avg_buy_price: Decimal
    first_bought_at: date
    last_transacted_at: date | None = None


class SnapshotResponse(_Base):
    account_id: int
    snapshot_date: date
    total_value: Decimal
    total_cost: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    holdings_count: int


class PerformanceResponse(BaseModel):
    account_id: int
    start_date: date
    end_date: date
    samples: int
    total_return_pct: Decimal | None = None
    max_drawdown_pct: Decimal | None = None
    sharpe_ratio: Decimal | None = None
    first_value: Decimal | None = None
    last_value: Decimal | None = None
