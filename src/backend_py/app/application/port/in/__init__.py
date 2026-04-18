"""Inbound ports — UseCase 인터페이스."""
from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from app.application.dto.results import (
    BacktestExecutionResult,
    CollectionResult,
    DetectionResult,
)


@runtime_checkable
class CollectMarketDataUseCase(Protocol):
    async def collect_all(self, trading_date: date) -> CollectionResult: ...


@runtime_checkable
class DetectSignalsUseCase(Protocol):
    async def detect_all(self, trading_date: date) -> DetectionResult: ...


@runtime_checkable
class RunBacktestUseCase(Protocol):
    async def execute(self, period_start: date, period_end: date) -> BacktestExecutionResult: ...
