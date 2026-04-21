"""외부 연동 어댑터 모음."""

from __future__ import annotations

from app.adapter.out.external._records import (
    LendingBalanceRow,
    ShortSellingRow,
    StockPriceRow,
)
from app.adapter.out.external.dart_client import (
    DartClient,
    DartClientError,
    DartCompanyInfo,
    DartDisclosure,
    DartFinancialRow,
    DartFinancialStatement,
    DartNotConfiguredError,
    DartUpstreamError,
)
from app.adapter.out.external.kis_client import (
    KisAuthError,
    KisClient,
    KisClientError,
    KisCredentials,
    KisEnvironment,
    KisHoldingRow,
    KisNotConfiguredError,
)
from app.adapter.out.external.krx_client import KrxClient
from app.adapter.out.external.telegram_client import TelegramClient

__all__ = [
    "DartClient",
    "DartClientError",
    "DartCompanyInfo",
    "DartDisclosure",
    "DartFinancialRow",
    "DartFinancialStatement",
    "DartNotConfiguredError",
    "DartUpstreamError",
    "KisAuthError",
    "KisClient",
    "KisClientError",
    "KisCredentials",
    "KisEnvironment",
    "KisHoldingRow",
    "KisNotConfiguredError",
    "KrxClient",
    "LendingBalanceRow",
    "ShortSellingRow",
    "StockPriceRow",
    "TelegramClient",
]
