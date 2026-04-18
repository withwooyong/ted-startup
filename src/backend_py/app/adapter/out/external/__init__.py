"""외부 연동 어댑터 모음."""
from __future__ import annotations

from app.adapter.out.external._records import (
    LendingBalanceRow,
    ShortSellingRow,
    StockPriceRow,
)
from app.adapter.out.external.krx_client import KrxClient
from app.adapter.out.external.telegram_client import TelegramClient

__all__ = [
    "KrxClient",
    "LendingBalanceRow",
    "ShortSellingRow",
    "StockPriceRow",
    "TelegramClient",
]
