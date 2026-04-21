"""UseCase 결과 DTO."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class CollectionResult(_Frozen):
    stocks_upserted: int
    stock_prices_upserted: int
    short_selling_upserted: int
    lending_balance_upserted: int
    elapsed_ms: int


class DetectionResult(_Frozen):
    rapid_decline: int
    trend_reversal: int
    short_squeeze: int
    elapsed_ms: int


class BacktestExecutionResult(_Frozen):
    signals_processed: int
    returns_calculated: int
    result_rows: int
    elapsed_ms: int
