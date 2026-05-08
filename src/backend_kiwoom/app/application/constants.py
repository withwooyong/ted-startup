"""백엔드 키움 도메인 공통 상수 — endpoint 간 공유.

설계: endpoint-03-ka10099.md § 2.3.

`StockListMarketType` (16종 StrEnum) 은 ka10099 의 `mrkt_tp` 값.
ka10101 (sector) 의 mrkt_tp 의미와 다름 — master.md § 12 결정 기록 참조.

Phase B 수집 범위 (P0 + P1) — `STOCK_SYNC_DEFAULT_MARKETS`:
- KOSPI(0), KOSDAQ(10), KONEX(50), ETN(60), REIT(6)
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class StockListMarketType(StrEnum):
    """ka10099 mrkt_tp 16종.

    Excel R22 원문 — 숫자 의미가 endpoint 별로 다름. ka10101 (`0/1/2/4/7`) 와
    혼동 금지. master.md § 12 결정 기록.
    """

    KOSPI = "0"
    KOSDAQ = "10"
    K_OTC = "30"
    KONEX = "50"
    ETN = "60"
    ETN_LOSS_LIMIT = "70"
    GOLD_SPOT = "80"
    ETN_VOLATILITY = "90"
    INFRA_FUND = "2"
    ELW = "3"
    MUTUAL_FUND = "4"
    SUBSCRIPTION_RIGHT = "5"
    REIT = "6"
    SUBSCRIPTION_CERT = "7"
    ETF = "8"
    HIGH_YIELD_FUND = "9"


STOCK_SYNC_DEFAULT_MARKETS: Final[tuple[StockListMarketType, ...]] = (
    StockListMarketType.KOSPI,
    StockListMarketType.KOSDAQ,
    StockListMarketType.KONEX,
    StockListMarketType.ETN,
    StockListMarketType.REIT,
)
"""Phase B 동기화 디폴트 시장 5개 (P0 + P1) — endpoint-03-ka10099.md § 2.3."""


class ExchangeType(StrEnum):
    """거래소 종류 — Phase C 첫 도입 (B-γ-1 ADR § 14.5 deferred 결정).

    ka10081 등 시계열 endpoint 의 stk_cd suffix 결정에 사용:
    - KRX: 005930 (suffix 없음)
    - NXT: 005930_NX
    - SOR: 005930_AL (Smart Order Routing — Phase D 이후 사용)

    Phase C-1α 는 KRX/NXT 만 영속화 (stock_price_krx + stock_price_nxt). SOR 은
    호출 가능하지만 영속화 미지원 — Phase D 시점 결정.
    """

    KRX = "KRX"
    NXT = "NXT"
    SOR = "SOR"


__all__ = [
    "STOCK_SYNC_DEFAULT_MARKETS",
    "ExchangeType",
    "StockListMarketType",
]
