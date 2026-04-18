"""Repository 계층 — 각 애그리게이트 별 async Repository."""
from __future__ import annotations

from app.adapter.out.persistence.repositories.backtest_result import BacktestResultRepository
from app.adapter.out.persistence.repositories.dart import DartCorpMappingRepository
from app.adapter.out.persistence.repositories.lending_balance import LendingBalanceRepository
from app.adapter.out.persistence.repositories.notification_preference import (
    NotificationPreferenceRepository,
)
from app.adapter.out.persistence.repositories.portfolio import (
    BrokerageAccountRepository,
    PortfolioHoldingRepository,
    PortfolioSnapshotRepository,
    PortfolioTransactionRepository,
)
from app.adapter.out.persistence.repositories.short_selling import ShortSellingRepository
from app.adapter.out.persistence.repositories.signal import SignalRepository
from app.adapter.out.persistence.repositories.stock import StockRepository
from app.adapter.out.persistence.repositories.stock_price import StockPriceRepository

__all__ = [
    "BacktestResultRepository",
    "BrokerageAccountRepository",
    "DartCorpMappingRepository",
    "LendingBalanceRepository",
    "NotificationPreferenceRepository",
    "PortfolioHoldingRepository",
    "PortfolioSnapshotRepository",
    "PortfolioTransactionRepository",
    "ShortSellingRepository",
    "SignalRepository",
    "StockPriceRepository",
    "StockRepository",
]
