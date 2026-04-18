"""SQLAlchemy ORM 모델 모음.

주의: `Base.metadata`에 모든 모델을 등록하려면 이 패키지가 임포트돼야 한다.
Alembic env.py 및 테스트 conftest가 이 모듈을 임포트해서 메타데이터를 확보한다.
"""
from __future__ import annotations

from app.adapter.out.persistence.models.analysis_report import AnalysisReport
from app.adapter.out.persistence.models.backtest_result import BacktestResult
from app.adapter.out.persistence.models.dart import DartCorpMapping
from app.adapter.out.persistence.models.enums import (
    BatchJobStatus,
    MarketType,
    SignalGrade,
    SignalType,
)
from app.adapter.out.persistence.models.lending_balance import LendingBalance
from app.adapter.out.persistence.models.notification_preference import NotificationPreference
from app.adapter.out.persistence.models.portfolio import (
    BrokerageAccount,
    PortfolioHolding,
    PortfolioSnapshot,
    PortfolioTransaction,
)
from app.adapter.out.persistence.models.short_selling import ShortSelling
from app.adapter.out.persistence.models.signal import Signal
from app.adapter.out.persistence.models.stock import Stock
from app.adapter.out.persistence.models.stock_price import StockPrice

__all__ = [
    "AnalysisReport",
    "BacktestResult",
    "BatchJobStatus",
    "BrokerageAccount",
    "DartCorpMapping",
    "LendingBalance",
    "MarketType",
    "NotificationPreference",
    "PortfolioHolding",
    "PortfolioSnapshot",
    "PortfolioTransaction",
    "ShortSelling",
    "Signal",
    "SignalGrade",
    "SignalType",
    "Stock",
    "StockPrice",
]
