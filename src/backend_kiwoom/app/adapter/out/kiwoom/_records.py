"""ka10086 응답 record + 정규화 helpers (C-2α).

설계: endpoint-10-ka10086.md § 3.6 + § 6.1.

- DailyMarketRow: 응답 row Pydantic (22 필드, OHLCV 8 + 신용 2 + 투자자별 4 + 외인 7 + date 1)
- DailyMarketResponse: 페이지 응답 wrapper
- NormalizedDailyFlow: Repository 가 보는 영속화 형태 (OHLCV 8 무시 + 8 도메인 + 메타, C-2γ + C-2δ 후)
- _strip_double_sign_int: Excel R56 의 `--714` 같은 이중 부호 처리 (가설 B)

이 모듈은 `chart.py` (ka10081) / `stkinfo.py` (ka10001/99/100) 와 동급의 record 모듈.
이름이 `_records.py` 인 이유: ka10086 외에도 mrkcond endpoint 가 추가되면 같은 record 공용
시점에 모듈 모음 역할 (계획서 § 11.4 향후 확장).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.adapter.out.kiwoom.stkinfo import (
    _parse_yyyymmdd,
    _to_decimal,
    _to_int,
)
from app.application.constants import DailyMarketDisplayMode, ExchangeType


def _strip_double_sign_int(value: str) -> int | None:
    """Excel R56 의 `--714` 같은 이중 부호 처리 (가설 B 채택).

    Excel 응답 예시에 `ind="--714"`, `for_qty="--266783"` 같은 이중 음수 표기 등장.
    가설 B (사용자 결정): `--714` = `-714` (이중 음수 표시 부호 + 음수 값 의미).
    운영 dry-run 후 raw 응답 측정 + KOSCOM 공시 cross-check 로 가설 확정 예정.

    `_to_int` BIGINT 가드 / 천단위 콤마 / zero-padded / 빈 입력 처리 모두 위임.

    예:
        "+693"     → 693
        "-714"     → -714
        "--714"    → -714 (가설 B)
        "++714"    → 714
        "00136000" → 136000
        "1,234"    → 1234
        ""         → None
        "-"        → None
        "--"       → None
        "abc"      → None
    """
    if not value:
        return None
    stripped = value.strip()
    if stripped in ("-", "+", "--", "++"):
        return None
    # 이중 부호 검출 — `_to_int` 호출 전 prefix 1개만 제거
    if stripped.startswith("--") or stripped.startswith("++"):
        stripped = stripped[1:]
    return _to_int(stripped)


# ---------- Pydantic 응답 ----------


class DailyMarketRow(BaseModel):
    """ka10086 응답 row — 22 필드.

    B-γ-1 2R A-H1 패턴 — 모든 string max_length 강제 (vendor 거대 string DataError 차단).
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    date: Annotated[str, Field(max_length=8)] = ""

    # OHLCV 8 — ka10081 와 중첩, 본 정규화에서 무시 (cross-check only)
    open_pric: Annotated[str, Field(max_length=32)] = ""
    high_pric: Annotated[str, Field(max_length=32)] = ""
    low_pric: Annotated[str, Field(max_length=32)] = ""
    close_pric: Annotated[str, Field(max_length=32)] = ""
    pred_rt: Annotated[str, Field(max_length=32)] = ""
    flu_rt: Annotated[str, Field(max_length=32)] = ""
    trde_qty: Annotated[str, Field(max_length=32)] = ""
    amt_mn: Annotated[str, Field(max_length=32)] = ""

    # 신용 2
    crd_rt: Annotated[str, Field(max_length=32)] = ""
    crd_remn_rt: Annotated[str, Field(max_length=32)] = ""

    # 투자자별 4
    ind: Annotated[str, Field(max_length=32)] = ""
    orgn: Annotated[str, Field(max_length=32)] = ""
    frgn: Annotated[str, Field(max_length=32)] = ""
    prm: Annotated[str, Field(max_length=32)] = ""

    # 외인 7
    for_qty: Annotated[str, Field(max_length=32)] = ""
    for_rt: Annotated[str, Field(max_length=32)] = ""
    for_poss: Annotated[str, Field(max_length=32)] = ""
    for_wght: Annotated[str, Field(max_length=32)] = ""
    for_netprps: Annotated[str, Field(max_length=32)] = ""
    orgn_netprps: Annotated[str, Field(max_length=32)] = ""
    ind_netprps: Annotated[str, Field(max_length=32)] = ""

    def to_normalized(
        self,
        *,
        stock_id: int,
        exchange: ExchangeType,
        indc_mode: DailyMarketDisplayMode,
    ) -> NormalizedDailyFlow:
        """ka10086 row → NormalizedDailyFlow.

        OHLCV 8 무시 (ka10081 정답). 빈 date → date.min (Repository skip 안전망).
        이중 부호 응답은 `_strip_double_sign_int` 가 가설 B 적용 (`--714` → -714).

        C-2γ — `for_netprps` / `orgn_netprps` / `ind_netprps` raw 필드는 D 카테고리
        (`for_qty` / `orgn` / `ind`) 와 100% 동일값 (dry-run § 20.2 #1) 이라 영속화
        하지 않음. raw 필드 자체는 vendor 응답에 존재하므로 DailyMarketRow 에는 유지.

        C-2δ — `crd_remn_rt` ≡ `crd_rt` / `for_wght` ≡ `for_rt` 가 2.88M rows 100% 동일
        (운영 실측 § 5.6) 이라 영속화하지 않음. raw 필드는 DailyMarketRow 에 유지.
        """
        return NormalizedDailyFlow(
            stock_id=stock_id,
            trading_date=_parse_yyyymmdd(self.date) or date.min,
            exchange=exchange,
            indc_mode=indc_mode,
            credit_rate=_to_decimal(self.crd_rt),
            individual_net=_strip_double_sign_int(self.ind),
            institutional_net=_strip_double_sign_int(self.orgn),
            foreign_brokerage_net=_strip_double_sign_int(self.frgn),
            program_net=_strip_double_sign_int(self.prm),
            foreign_volume=_strip_double_sign_int(self.for_qty),
            foreign_rate=_to_decimal(self.for_rt),
            foreign_holdings=_to_int(self.for_poss),
        )


class DailyMarketResponse(BaseModel):
    """ka10086 응답 wrapper — `stk_cd` 메아리 + `daly_stkpc` list."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    stk_cd: Annotated[str, Field(max_length=20)] = ""
    daly_stkpc: list[DailyMarketRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: Annotated[str, Field(max_length=200)] = ""


@dataclass(frozen=True, slots=True)
class NormalizedDailyFlow:
    """ka10086 정규화 도메인 — Repository 가 보는 형태.

    `trading_date == date.min` 은 빈 응답 row 표식 — caller (Repository.upsert_many) 가
    영속화 직전 skip.
    """

    stock_id: int
    trading_date: date
    exchange: ExchangeType
    indc_mode: DailyMarketDisplayMode
    # C. 신용 (C-2δ — credit_balance_rate DROP, credit_rate 와 동일값)
    credit_rate: Decimal | None
    # D. 투자자별 net
    individual_net: int | None
    institutional_net: int | None
    foreign_brokerage_net: int | None
    program_net: int | None
    # E. 외인 (C-2γ — 순매수 3 컬럼 DROP / C-2δ — foreign_weight DROP, foreign_rate 와 동일값)
    foreign_volume: int | None
    foreign_rate: Decimal | None
    foreign_holdings: int | None


# =============================================================================
# Phase E — ka10014 공매도 + ka10068/ka20068 대차거래 (매도 측 시그널 wave)
# =============================================================================


class ShortSellingTimeType(StrEnum):
    """ka10014 `tm_tp` 시간구분 (Phase E).

    설계: endpoint-15-ka10014.md § 11.2.

    - START_ONLY ("0"): 시작일 단독 — 응답이 strt_dt 부근만
    - PERIOD ("1"): 기간 — 응답 기간 보장 (plan § 12.2 H-4 디폴트, endpoint-15 권장)
    """

    START_ONLY = "0"
    PERIOD = "1"


class LendingScope(StrEnum):
    """대차거래 적재 범위 — `lending_balance_kw` 의 row 분기 (Phase E).

    설계: endpoint-16-ka10068.md § 3.3.

    - MARKET (ka10068): 시장 단위 — stock_id NULL
    - STOCK (ka20068): 종목 단위 — stock_id FK
    """

    MARKET = "MARKET"
    STOCK = "STOCK"


# ---------------------------------------------------------------------------
# ka10014 공매도 추이 — ShortSellingRow / Response / NormalizedShortSelling
# ---------------------------------------------------------------------------


class ShortSellingRow(BaseModel):
    """ka10014 응답 row — 11 필드.

    B-γ-1 2R A-H1 패턴 — 모든 string max_length 강제 (vendor 거대 string DataError 차단).
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    dt: Annotated[str, Field(max_length=8)] = ""
    close_pric: Annotated[str, Field(max_length=32)] = ""
    pred_pre_sig: Annotated[str, Field(max_length=4)] = ""
    pred_pre: Annotated[str, Field(max_length=32)] = ""
    flu_rt: Annotated[str, Field(max_length=32)] = ""
    trde_qty: Annotated[str, Field(max_length=32)] = ""
    shrts_qty: Annotated[str, Field(max_length=32)] = ""
    ovr_shrts_qty: Annotated[str, Field(max_length=32)] = ""
    trde_wght: Annotated[str, Field(max_length=32)] = ""
    shrts_trde_prica: Annotated[str, Field(max_length=32)] = ""
    shrts_avg_pric: Annotated[str, Field(max_length=32)] = ""

    def to_normalized(
        self,
        *,
        stock_id: int,
        exchange: ExchangeType,
    ) -> NormalizedShortSelling:
        """ka10014 row → NormalizedShortSelling.

        빈 dt → date.min (Repository skip 안전망). DailyMarketRow.to_normalized 패턴 일관.
        """
        return NormalizedShortSelling(
            stock_id=stock_id,
            trading_date=_parse_yyyymmdd(self.dt) or date.min,
            exchange=exchange,
            close_price=_to_int(self.close_pric),
            prev_compare_amount=_to_int(self.pred_pre),
            prev_compare_sign=self.pred_pre_sig or None,
            change_rate=_to_decimal(self.flu_rt),
            trade_volume=_to_int(self.trde_qty),
            short_volume=_to_int(self.shrts_qty),
            cumulative_short_volume=_to_int(self.ovr_shrts_qty),
            short_trade_weight=_to_decimal(self.trde_wght),
            short_trade_amount=_to_int(self.shrts_trde_prica),
            short_avg_price=_to_int(self.shrts_avg_pric),
        )


class ShortSellingResponse(BaseModel):
    """ka10014 응답 wrapper — `shrts_trnsn` list."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    shrts_trnsn: list[ShortSellingRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: Annotated[str, Field(max_length=200)] = ""


@dataclass(frozen=True, slots=True)
class NormalizedShortSelling:
    """ka10014 정규화 도메인 — Repository 가 보는 형태.

    `trading_date == date.min` 은 빈 응답 row 표식 — caller 가 영속화 직전 skip.
    """

    stock_id: int
    trading_date: date
    exchange: ExchangeType
    close_price: int | None
    prev_compare_amount: int | None
    prev_compare_sign: str | None
    change_rate: Decimal | None
    trade_volume: int | None
    short_volume: int | None
    cumulative_short_volume: int | None
    short_trade_weight: Decimal | None
    short_trade_amount: int | None
    short_avg_price: int | None


# ---------------------------------------------------------------------------
# ka10068 시장 대차 / ka20068 종목 대차 — LendingMarketRow / LendingStockRow / Response 2
# ---------------------------------------------------------------------------


class LendingMarketRow(BaseModel):
    """ka10068 응답 row (시장 단위) — 6 필드.

    plan § 3.1 (endpoint-16) 응답 필드명:
    - dt / dbrt_trde_cntrcnt / dbrt_trde_rpy / dbrt_trde_irds / rmnd / remn_amt
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    dt: Annotated[str, Field(max_length=8)] = ""
    dbrt_trde_cntrcnt: Annotated[str, Field(max_length=32)] = ""
    dbrt_trde_rpy: Annotated[str, Field(max_length=32)] = ""
    dbrt_trde_irds: Annotated[str, Field(max_length=32)] = ""
    rmnd: Annotated[str, Field(max_length=32)] = ""
    remn_amt: Annotated[str, Field(max_length=32)] = ""

    def to_normalized(self, *, scope: LendingScope) -> NormalizedLendingMarket:
        """ka10068 row → NormalizedLendingMarket (scope=MARKET, stock_id=None).

        plan § 3.3 (endpoint-16) 시그니처 1:1. 시장 단위 — stock_id 는 항상 None
        (CHECK constraint 보장).
        빈 dt → date.min (Repository skip 안전망).
        """
        return NormalizedLendingMarket(
            scope=scope,
            stock_id=None,
            trading_date=_parse_yyyymmdd(self.dt) or date.min,
            contracted_volume=_to_int(self.dbrt_trde_cntrcnt),
            repaid_volume=_to_int(self.dbrt_trde_rpy),
            delta_volume=_to_int(self.dbrt_trde_irds),
            balance_volume=_to_int(self.rmnd),
            balance_amount=_to_int(self.remn_amt),
        )


class LendingStockRow(BaseModel):
    """ka20068 응답 row (종목 단위) — schema 는 ka10068 의 LendingMarketRow 와 동일.

    plan § 3.3 (endpoint-17). `to_normalized` 시그니처가 다르므로 (scope vs stock_id)
    별도 클래스로 정의 — 상속 시 시그니처 변경은 LSP 위반.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    dt: Annotated[str, Field(max_length=8)] = ""
    dbrt_trde_cntrcnt: Annotated[str, Field(max_length=32)] = ""
    dbrt_trde_rpy: Annotated[str, Field(max_length=32)] = ""
    dbrt_trde_irds: Annotated[str, Field(max_length=32)] = ""
    rmnd: Annotated[str, Field(max_length=32)] = ""
    remn_amt: Annotated[str, Field(max_length=32)] = ""

    def to_normalized(self, *, stock_id: int) -> NormalizedLendingMarket:
        """ka20068 row → NormalizedLendingMarket (scope=STOCK, stock_id=int).

        plan § 3.3 (endpoint-17) 시그니처 1:1. 종목 단위 — stock_id FK 필수
        (CHECK constraint 보장).
        빈 dt → date.min (Repository skip 안전망).
        """
        return NormalizedLendingMarket(
            scope=LendingScope.STOCK,
            stock_id=stock_id,
            trading_date=_parse_yyyymmdd(self.dt) or date.min,
            contracted_volume=_to_int(self.dbrt_trde_cntrcnt),
            repaid_volume=_to_int(self.dbrt_trde_rpy),
            delta_volume=_to_int(self.dbrt_trde_irds),
            balance_volume=_to_int(self.rmnd),
            balance_amount=_to_int(self.remn_amt),
        )


class LendingMarketResponse(BaseModel):
    """ka10068 응답 wrapper — `dbrt_trde_trnsn` list."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    dbrt_trde_trnsn: list[LendingMarketRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: Annotated[str, Field(max_length=200)] = ""


class LendingStockResponse(BaseModel):
    """ka20068 응답 wrapper — `dbrt_trde_trnsn` list (LendingStockRow)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    dbrt_trde_trnsn: list[LendingStockRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: Annotated[str, Field(max_length=200)] = ""


@dataclass(frozen=True, slots=True)
class NormalizedLendingMarket:
    """ka10068 / ka20068 정규화 도메인 — Repository 가 보는 형태.

    `lending_balance_kw` 테이블 1행에 대응. scope 컬럼으로 MARKET/STOCK 분기.
    `trading_date == date.min` 은 빈 응답 row 표식 — caller 가 영속화 직전 skip.
    """

    scope: LendingScope
    stock_id: int | None
    trading_date: date
    contracted_volume: int | None
    repaid_volume: int | None
    delta_volume: int | None
    balance_volume: int | None
    balance_amount: int | None


__all__ = [
    "DailyMarketResponse",
    "DailyMarketRow",
    "LendingMarketResponse",
    "LendingMarketRow",
    "LendingScope",
    "LendingStockResponse",
    "LendingStockRow",
    "NormalizedDailyFlow",
    "NormalizedLendingMarket",
    "NormalizedShortSelling",
    "ShortSellingResponse",
    "ShortSellingRow",
    "ShortSellingTimeType",
    "_strip_double_sign_int",
]
