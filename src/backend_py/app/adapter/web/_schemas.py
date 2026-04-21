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


class LatestSignalsResponse(BaseModel):
    """가장 최근 탐지된 signal_date 기준으로 묶은 응답.

    signal_date 가 None 이면 시그널 테이블이 비어있음.
    대시보드가 "오늘 기준 빈 상태"를 피하려고 사용.
    """
    signal_date: date | None = None
    signals: list[SignalResponse] = Field(default_factory=list)


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
    connection_type: Annotated[
        str, Field(pattern=r"^(manual|kis_rest_mock|kis_rest_real)$")
    ]
    # connection_type 과의 조합 검증은 UseCase 에서 수행. 여기선 enum 범위만 방어.
    environment: Annotated[str, Field(pattern=r"^(mock|real)$")] = "mock"


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


class SyncResponse(BaseModel):
    account_id: int
    connection_type: str
    fetched_count: int
    created_count: int
    updated_count: int
    unchanged_count: int
    stock_created_count: int


class ExcelImportRowError(BaseModel):
    row: int
    reason: str


class ExcelImportResponse(BaseModel):
    account_id: int
    total_rows: int
    imported: int
    skipped_duplicates: int
    stock_created_count: int
    errors: list[ExcelImportRowError] = []


# ---------- Brokerage Credential (P15 / KIS sync PR 4) ----------


# KIS app_key/secret 는 운영상 수십 자. 여백·개행이 포함되면 인증 실패로 이어지므로
# `\S` (공백 불가) + 길이 하한만 강제. 상한은 보수적 128자.
KisAppKey = Annotated[str, Field(min_length=16, max_length=128, pattern=r"^\S+$")]
KisAppSecret = Annotated[str, Field(min_length=16, max_length=256, pattern=r"^\S+$")]
# CANO(8) + '-' + ACNT_PRDT_CD(2) 형식. KIS OpenAPI 표준.
KisAccountNo = Annotated[str, Field(pattern=r"^\d{8}-\d{2}$")]


class BrokerageCredentialRequest(BaseModel):
    """실계정 자격증명 등록/교체 요청. plaintext 는 이 스키마 바깥으로 새지 않도록
    router 에서만 사용, 로그·응답에 재노출 금지."""

    app_key: KisAppKey
    app_secret: KisAppSecret
    account_no: KisAccountNo


class BrokerageCredentialResponse(_Base):
    """마스킹된 자격증명 뷰 — `app_secret` 미포함, `app_key`/`account_no` 는 tail 4자리만 공개."""

    account_id: int
    app_key_masked: str
    account_no_masked: str
    key_version: int
    created_at: datetime
    updated_at: datetime


class AlignedSignalItem(BaseModel):
    signal_date: date
    signal_type: str
    score: int
    grade: str


class AlignedHoldingItem(BaseModel):
    stock_id: int
    stock_code: str
    stock_name: str
    quantity: int
    avg_buy_price: Decimal
    max_score: int
    hit_count: int
    signals: list[AlignedSignalItem]


class SignalAlignmentResponse(BaseModel):
    account_id: int
    since: date
    until: date
    min_score: int
    total_holdings: int
    aligned_holdings: int
    items: list[AlignedHoldingItem]


# ---------- AI Report (P13b) ----------


class ReportSourceItem(BaseModel):
    tier: int
    type: str
    url: str
    label: str
    published_at: str | None = None


class ReportContentPayload(BaseModel):
    summary: str
    strengths: list[str]
    risks: list[str]
    outlook: str
    opinion: str
    disclaimer: str


class AnalysisReportResponse(BaseModel):
    stock_code: str
    report_date: date
    provider: str
    model_id: str
    content: ReportContentPayload
    sources: list[ReportSourceItem]
    cache_hit: bool
    token_in: int | None = None
    token_out: int | None = None
    elapsed_ms: int | None = None
