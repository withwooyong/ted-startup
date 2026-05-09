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

    길이 invariant (C-2α 2b-M2): stock_price_*/stock_daily_flow 의 exchange 컬럼이
    VARCHAR(4) 로 정의됨. 신규 멤버 추가 시 4자 이내 강제 — module import 시점 fail-fast.
    """

    KRX = "KRX"
    NXT = "NXT"
    SOR = "SOR"


# 2b-M2 — VARCHAR(4) silent truncation 차단. 신규 거래소 추가 시 컬럼 확장 강제.
EXCHANGE_TYPE_MAX_LENGTH: Final[int] = 4
_invalid_exchanges = [e.value for e in ExchangeType if len(e.value) > EXCHANGE_TYPE_MAX_LENGTH]
if _invalid_exchanges:
    raise RuntimeError(
        f"ExchangeType value 가 VARCHAR({EXCHANGE_TYPE_MAX_LENGTH}) 한도 초과: {_invalid_exchanges}. "
        "Migration 005/006/007 의 exchange 컬럼 확장 또는 멤버 단축 필요"
    )


class Period(StrEnum):
    """OHLCV 시계열 분류 — 주봉/월봉/년봉 (C-3α).

    설계: phase-c-3-weekly-monthly-ohlcv.md § H-3.

    DAILY 는 본 enum 외 — IngestDailyOhlcvUseCase 가 별도 처리 (hot path 분리).
    YEARLY 는 enum 노출 (3값 일관) but Migration / Repository 미구현 — caller 에서 검증.
    P2 chunk (ka10094) 진입 시 활성화.

    value 는 소문자 string — 라우터 path / cron job id / DB 메타필드 일관.
    """

    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class DailyMarketDisplayMode(StrEnum):
    """ka10086 `indc_tp` 표시구분 (C-2α).

    설계: endpoint-10-ka10086.md § 2.3.

    indc_tp 의미:
    - "0" QUANTITY: 수량 (주식수). 백테스팅 시그널 디폴트 — 다른 종목 비교 안정적
    - "1" AMOUNT: 백만원 단위

    주의 (Excel R15): `for_netprps` / `orgn_netprps` / `ind_netprps` (외인/기관/개인 순매수)
    는 indc_tp 무시하고 항상 수량으로 응답. 단위 mismatch 운영 검증 후 결정.
    """

    QUANTITY = "0"
    AMOUNT = "1"


__all__ = [
    "EXCHANGE_TYPE_MAX_LENGTH",
    "STOCK_SYNC_DEFAULT_MARKETS",
    "DailyMarketDisplayMode",
    "ExchangeType",
    "Period",
    "StockListMarketType",
]
