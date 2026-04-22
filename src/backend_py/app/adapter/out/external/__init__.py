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
    KisClient,
    KisNotConfiguredError,
)
from app.adapter.out.external.krx_client import KrxClient
from app.adapter.out.external.telegram_client import TelegramClient

# KIS DTO 와 port 예외는 application layer 에 정의 — Hexagonal DIP.
# 여기서는 외부 공용 `app.adapter.out.external` 네임스페이스에서도 여전히
# 접근 가능하도록 re-export (배선·테스트·기존 호출부 편의).
from app.application.dto.kis import (
    KisCredentials,
    KisEnvironment,
    KisHoldingRow,
)
from app.application.port.out.kis_port import (
    KisCredentialRejectedError,
    KisHoldingsFetcher,
    KisRealFetcherFactory,
    KisUpstreamError,
)

__all__ = [
    "DartClient",
    "DartClientError",
    "DartCompanyInfo",
    "DartDisclosure",
    "DartFinancialRow",
    "DartFinancialStatement",
    "DartNotConfiguredError",
    "DartUpstreamError",
    "KisClient",
    "KisCredentialRejectedError",
    "KisCredentials",
    "KisEnvironment",
    "KisHoldingRow",
    "KisHoldingsFetcher",
    "KisNotConfiguredError",
    "KisRealFetcherFactory",
    "KisUpstreamError",
    "KrxClient",
    "LendingBalanceRow",
    "ShortSellingRow",
    "StockPriceRow",
    "TelegramClient",
]
