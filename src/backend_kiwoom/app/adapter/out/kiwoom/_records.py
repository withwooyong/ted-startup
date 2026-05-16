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


# =============================================================================
# Phase F-4 — 5 ranking endpoint 통합 (ka10027/30/31/32/23)
# =============================================================================


class RankingType(StrEnum):
    """5 ranking endpoint 통합 식별자 (Phase F-4).

    값은 ``ranking_snapshot.ranking_type`` 컬럼에 그대로 저장 (VARCHAR(16)).
    새 ranking 추가 시 본 enum + UseCase 만 (D-2 단일 테이블 패턴).
    """

    FLU_RT = "FLU_RT"
    """ka10027 — 등락률 상위/하위."""
    TODAY_VOLUME = "TODAY_VOLUME"
    """ka10030 — 당일 거래량 상위 (23 필드 + 장중/장후/장전 분리)."""
    PRED_VOLUME = "PRED_VOLUME"
    """ka10031 — 전일 거래량 상위 (6 필드 단순)."""
    TRDE_PRICA = "TRDE_PRICA"
    """ka10032 — 거래대금 상위."""
    VOLUME_SDNIN = "VOLUME_SDNIN"
    """ka10023 — 거래량 급증 (sdnin_qty / sdnin_rt)."""


class RankingMarketType(StrEnum):
    """Phase F 5 endpoint 공통 mrkt_tp — ka10099/ka10101 과 _다른 의미_ (D-3)."""

    ALL = "000"
    KOSPI = "001"
    KOSDAQ = "101"


class RankingExchangeType(StrEnum):
    """Phase F 5 endpoint 공통 stex_tp (D-4 default UNIFIED=3)."""

    KRX = "1"
    NXT = "2"
    UNIFIED = "3"


class FluRtSortType(StrEnum):
    """ka10027 sort_tp 5종 (D-5 운영 default {UP_RATE, DOWN_RATE})."""

    UP_RATE = "1"
    UP_AMOUNT = "2"
    DOWN_RATE = "3"
    DOWN_AMOUNT = "4"
    UNCHANGED = "5"


class TodayVolumeSortType(StrEnum):
    """ka10030 sort_tp 3종 — 거래량 / 회전율 / 거래대금."""

    TRADE_VOLUME = "1"
    TURNOVER_RATE = "2"
    TRADE_AMOUNT = "3"


class VolumeSdninSortType(StrEnum):
    """ka10023 sort_tp 4종 — 급증량 / 급증률 / 감량 / 감률."""

    SUDDEN_VOLUME = "1"
    SUDDEN_RATE = "2"
    DROP_VOLUME = "3"
    DROP_RATE = "4"


class VolumeSdninTimeType(StrEnum):
    """ka10023 tm_tp — 분 / 전일."""

    MINUTES = "1"
    PREVIOUS_DAY = "2"


def _to_payload_decimal_str(value: str) -> str | None:
    """부호 흡수 + Decimal 정밀도 보존 — JSONB 에 string 으로 저장.

    `+38.04` / `-5.50` / `346.54` 등 부호 + 소수 → string ('38.04').
    빈 string / sentinel ('-' / '+') → None.
    유효하지 않은 입력 → None (caller 가 빈 처리).
    """
    if not value:
        return None
    d = _to_decimal(value)
    if d is None:
        return None
    return str(d)


class FluRtUpperRow(BaseModel):
    """ka10027 응답 row — 12 필드 (B-γ-1 2R A-H1 패턴 max_length 강제).

    부호 흡수 (`+74800` → 74800) + JSONB 안전 payload (`to_payload`).
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    stk_cls: Annotated[str, Field(max_length=32)] = ""
    stk_cd: Annotated[str, Field(max_length=20)] = ""
    stk_nm: Annotated[str, Field(max_length=64)] = ""
    cur_prc: Annotated[str, Field(max_length=32)] = ""
    pred_pre_sig: Annotated[str, Field(max_length=4)] = ""
    pred_pre: Annotated[str, Field(max_length=32)] = ""
    flu_rt: Annotated[str, Field(max_length=32)] = ""
    sel_req: Annotated[str, Field(max_length=32)] = ""
    buy_req: Annotated[str, Field(max_length=32)] = ""
    now_trde_qty: Annotated[str, Field(max_length=32)] = ""
    cntr_str: Annotated[str, Field(max_length=32)] = ""
    cnt: Annotated[str, Field(max_length=32)] = ""

    def to_payload(self) -> dict[str, object | None]:
        """JSONB payload 직렬화 — 부호 흡수 + NUMERIC string 보존."""
        return {
            "stk_cls": self.stk_cls or None,
            "stk_nm": self.stk_nm or None,
            "cur_prc": _to_int(self.cur_prc),
            "pred_pre_sig": self.pred_pre_sig or None,
            "pred_pre": _to_int(self.pred_pre),
            "flu_rt": _to_payload_decimal_str(self.flu_rt),
            "sel_req": _to_int(self.sel_req),
            "buy_req": _to_int(self.buy_req),
            "now_trde_qty": _to_int(self.now_trde_qty),
            "cntr_str": _to_payload_decimal_str(self.cntr_str),
            "cnt": _to_int(self.cnt),
        }


class FluRtUpperResponse(BaseModel):
    """ka10027 응답 wrapper — `pred_pre_flu_rt_upper` list."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    pred_pre_flu_rt_upper: list[FluRtUpperRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: Annotated[str, Field(max_length=200)] = ""


class TodayVolumeUpperRow(BaseModel):
    """ka10030 응답 row — 23 필드 (장중/장후/장전 분리, D-9 nested payload source)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    stk_cd: Annotated[str, Field(max_length=20)] = ""
    stk_nm: Annotated[str, Field(max_length=64)] = ""
    cur_prc: Annotated[str, Field(max_length=32)] = ""
    pred_pre_sig: Annotated[str, Field(max_length=4)] = ""
    pred_pre: Annotated[str, Field(max_length=32)] = ""
    flu_rt: Annotated[str, Field(max_length=32)] = ""
    trde_qty: Annotated[str, Field(max_length=32)] = ""
    pred_rt: Annotated[str, Field(max_length=32)] = ""
    trde_tern_rt: Annotated[str, Field(max_length=32)] = ""
    # 장중 (opmr_*) 4 필드
    opmr_trde_qty: Annotated[str, Field(max_length=32)] = ""
    opmr_pred_rt: Annotated[str, Field(max_length=32)] = ""
    opmr_trde_rt: Annotated[str, Field(max_length=32)] = ""
    opmr_trde_amt: Annotated[str, Field(max_length=32)] = ""
    # 장후 (af_mkrt_*) 4 필드
    af_mkrt_trde_qty: Annotated[str, Field(max_length=32)] = ""
    af_mkrt_pred_rt: Annotated[str, Field(max_length=32)] = ""
    af_mkrt_trde_rt: Annotated[str, Field(max_length=32)] = ""
    af_mkrt_trde_amt: Annotated[str, Field(max_length=32)] = ""
    # 장전 (bf_mkrt_*) 4 필드
    bf_mkrt_trde_qty: Annotated[str, Field(max_length=32)] = ""
    bf_mkrt_pred_rt: Annotated[str, Field(max_length=32)] = ""
    bf_mkrt_trde_rt: Annotated[str, Field(max_length=32)] = ""
    bf_mkrt_trde_amt: Annotated[str, Field(max_length=32)] = ""

    def to_payload(self) -> dict[str, object | None]:
        """D-9 nested payload — 23 필드를 {opmr, af_mkrt, bf_mkrt} 3 그룹 분리.

        derived feature 쿼리 단순화 — `payload->'opmr'->>'trde_qty'`.
        """
        return {
            "stk_nm": self.stk_nm or None,
            "cur_prc": _to_int(self.cur_prc),
            "pred_pre_sig": self.pred_pre_sig or None,
            "pred_pre": _to_int(self.pred_pre),
            "flu_rt": _to_payload_decimal_str(self.flu_rt),
            "trde_qty": _to_int(self.trde_qty),
            "pred_rt": _to_payload_decimal_str(self.pred_rt),
            "trde_tern_rt": _to_payload_decimal_str(self.trde_tern_rt),
            "opmr": {
                "trde_qty": _to_int(self.opmr_trde_qty),
                "pred_rt": _to_payload_decimal_str(self.opmr_pred_rt),
                "trde_rt": _to_payload_decimal_str(self.opmr_trde_rt),
                "trde_amt": _to_int(self.opmr_trde_amt),
            },
            "af_mkrt": {
                "trde_qty": _to_int(self.af_mkrt_trde_qty),
                "pred_rt": _to_payload_decimal_str(self.af_mkrt_pred_rt),
                "trde_rt": _to_payload_decimal_str(self.af_mkrt_trde_rt),
                "trde_amt": _to_int(self.af_mkrt_trde_amt),
            },
            "bf_mkrt": {
                "trde_qty": _to_int(self.bf_mkrt_trde_qty),
                "pred_rt": _to_payload_decimal_str(self.bf_mkrt_pred_rt),
                "trde_rt": _to_payload_decimal_str(self.bf_mkrt_trde_rt),
                "trde_amt": _to_int(self.bf_mkrt_trde_amt),
            },
        }


class TodayVolumeUpperResponse(BaseModel):
    """ka10030 응답 wrapper — `tdy_trde_qty_upper` list."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    tdy_trde_qty_upper: list[TodayVolumeUpperRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: Annotated[str, Field(max_length=200)] = ""


class PredVolumeUpperRow(BaseModel):
    """ka10031 응답 row — 6 필드 단순."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    stk_cd: Annotated[str, Field(max_length=20)] = ""
    stk_nm: Annotated[str, Field(max_length=64)] = ""
    cur_prc: Annotated[str, Field(max_length=32)] = ""
    pred_pre_sig: Annotated[str, Field(max_length=4)] = ""
    pred_pre: Annotated[str, Field(max_length=32)] = ""
    trde_qty: Annotated[str, Field(max_length=32)] = ""

    def to_payload(self) -> dict[str, object | None]:
        return {
            "stk_nm": self.stk_nm or None,
            "cur_prc": _to_int(self.cur_prc),
            "pred_pre_sig": self.pred_pre_sig or None,
            "pred_pre": _to_int(self.pred_pre),
            "trde_qty": _to_int(self.trde_qty),
        }


class PredVolumeUpperResponse(BaseModel):
    """ka10031 응답 wrapper — `pred_trde_qty_upper` list."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    pred_trde_qty_upper: list[PredVolumeUpperRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: Annotated[str, Field(max_length=200)] = ""


class TradeAmountUpperRow(BaseModel):
    """ka10032 응답 row — 거래대금 상위 + now_rank/pred_rank (순위 변동 source)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    stk_cd: Annotated[str, Field(max_length=20)] = ""
    stk_nm: Annotated[str, Field(max_length=64)] = ""
    cur_prc: Annotated[str, Field(max_length=32)] = ""
    pred_pre_sig: Annotated[str, Field(max_length=4)] = ""
    pred_pre: Annotated[str, Field(max_length=32)] = ""
    flu_rt: Annotated[str, Field(max_length=32)] = ""
    now_trde_qty: Annotated[str, Field(max_length=32)] = ""
    trde_prica: Annotated[str, Field(max_length=32)] = ""
    now_rank: Annotated[str, Field(max_length=32)] = ""
    pred_rank: Annotated[str, Field(max_length=32)] = ""

    def to_payload(self) -> dict[str, object | None]:
        return {
            "stk_nm": self.stk_nm or None,
            "cur_prc": _to_int(self.cur_prc),
            "pred_pre_sig": self.pred_pre_sig or None,
            "pred_pre": _to_int(self.pred_pre),
            "flu_rt": _to_payload_decimal_str(self.flu_rt),
            "now_trde_qty": _to_int(self.now_trde_qty),
            "trde_prica": _to_int(self.trde_prica),
            "now_rank": _to_int(self.now_rank),
            "pred_rank": _to_int(self.pred_rank),
        }


class TradeAmountUpperResponse(BaseModel):
    """ka10032 응답 wrapper — `trde_prica_upper` list."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    trde_prica_upper: list[TradeAmountUpperRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: Annotated[str, Field(max_length=200)] = ""


class VolumeSdninRow(BaseModel):
    """ka10023 응답 row — 거래량 급증 (sdnin_qty / sdnin_rt 시그널 source)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    stk_cd: Annotated[str, Field(max_length=20)] = ""
    stk_nm: Annotated[str, Field(max_length=64)] = ""
    cur_prc: Annotated[str, Field(max_length=32)] = ""
    pred_pre_sig: Annotated[str, Field(max_length=4)] = ""
    pred_pre: Annotated[str, Field(max_length=32)] = ""
    flu_rt: Annotated[str, Field(max_length=32)] = ""
    now_trde_qty: Annotated[str, Field(max_length=32)] = ""
    sdnin_qty: Annotated[str, Field(max_length=32)] = ""
    sdnin_rt: Annotated[str, Field(max_length=32)] = ""

    def to_payload(self) -> dict[str, object | None]:
        return {
            "stk_nm": self.stk_nm or None,
            "cur_prc": _to_int(self.cur_prc),
            "pred_pre_sig": self.pred_pre_sig or None,
            "pred_pre": _to_int(self.pred_pre),
            "flu_rt": _to_payload_decimal_str(self.flu_rt),
            "now_trde_qty": _to_int(self.now_trde_qty),
            "sdnin_qty": _to_int(self.sdnin_qty),
            "sdnin_rt": _to_payload_decimal_str(self.sdnin_rt),
        }


class VolumeSdninResponse(BaseModel):
    """ka10023 응답 wrapper — `trde_qty_sdnin` list."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    trde_qty_sdnin: list[VolumeSdninRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: Annotated[str, Field(max_length=200)] = ""


# =============================================================================
# Phase G — 투자자별 매매 흐름 (ka10058 / ka10059 / ka10131)
# =============================================================================
#
# 9 enum + 3 Row / 3 Response + 3 Normalized dataclass + `_to_decimal_div_100` helper.
# 설계: phase-g-investor-flow.md § 5.4 + endpoint-23/24/25.
# 사용자 결정 D-15 (amt_qty_tp 반대 의미) — `AmountQuantityType` (ka10059 1/2) vs
# `ContinuousAmtQtyType` (ka10131 0/1) 별도 enum 분리. enum 분리가 컴파일 타임 가드.


def _to_decimal_div_100(value: str) -> Decimal | None:
    """ka10059 flu_rt "우측 2자리 소수점" 정규화 — ``+698`` → ``Decimal("6.98")``.

    ka10058 의 ``pre_rt = "+7.43"`` 와 다른 표기 — ka10059 응답은 100 곱해서 정수로 옴
    (운영 검증 1순위 — master.md § 12 + 본 helper docstring 기록).

    `_to_decimal` (부호 흡수 + 천단위 콤마 + NaN/Infinity 차단) 후 100 나눔. 빈 입력 /
    sentinel (`-` / `+`) → None. 잘못된 입력 → None (caller 가 NULL 영속화).

    예:
        "+698"   → Decimal("6.98")
        "-580"   → Decimal("-5.80")
        "0"      → Decimal("0")
        ""       → None
        "-"      → None
        "abc"    → None
    """
    d = _to_decimal(value)
    if d is None:
        return None
    return d / Decimal(100)


# ---------- 9 enum ----------


class InvestorType(StrEnum):
    """ka10058 invsr_tp — 12 카테고리 (개인/외국인/기관계 + 9 기관 세부)."""

    INDIVIDUAL = "8000"
    """개인."""
    FOREIGN = "9000"
    """외국인."""
    INSTITUTION_TOTAL = "9999"
    """기관계 (= 금융투자 + 보험 + 투신 + 기타금융 + 은행 + 연기금 + 국가 합산 추정)."""
    FINANCIAL_INV = "1000"
    """금융투자."""
    INSURANCE = "2000"
    """보험."""
    INVESTMENT_TRUST = "3000"
    """투신."""
    PRIVATE_FUND = "3100"
    """사모펀드."""
    BANK = "4000"
    """은행."""
    OTHER_FINANCIAL = "5000"
    """기타금융."""
    PENSION_FUND = "6000"
    """연기금."""
    NATION = "7000"
    """국가."""
    OTHER_CORP = "7100"
    """기타법인."""


class InvestorTradeType(StrEnum):
    """ka10058 trde_tp — 순매도/순매수 2종."""

    NET_SELL = "1"
    NET_BUY = "2"


class InvestorMarketType(StrEnum):
    """ka10058/ka10131 mrkt_tp — D-17 신규 enum (코스피/코스닥 만, 전체 ``000`` 불가)."""

    KOSPI = "001"
    KOSDAQ = "101"


class AmountQuantityType(StrEnum):
    """ka10059 amt_qty_tp — 금액/수량 (★ ka10131 의 amt_qty_tp 와 반대 의미)."""

    AMOUNT = "1"
    QUANTITY = "2"


class StockInvestorTradeType(StrEnum):
    """ka10059 trde_tp — 순매수/매수/매도 3종 (ka10058 의 2종보다 1종 많음)."""

    NET_BUY = "0"
    BUY = "1"
    SELL = "2"


class UnitType(StrEnum):
    """ka10059 unit_tp — 단위 (천주/단주)."""

    THOUSAND_SHARES = "1000"
    SINGLE_SHARE = "1"


class ContinuousPeriodType(StrEnum):
    """ka10131 dt — 연속 윈도 7종.

    PERIOD (0) 일 때만 strt_dt / end_dt 사용. 나머지는 응답 시점 기준 N일.
    """

    LATEST = "1"
    DAYS_3 = "3"
    DAYS_5 = "5"
    DAYS_10 = "10"
    DAYS_20 = "20"
    DAYS_120 = "120"
    PERIOD = "0"


class ContinuousAmtQtyType(StrEnum):
    """ka10131 amt_qty_tp — 금액/수량 (★ ka10059 의 amt_qty_tp 와 _반대_ 의미, D-15).

    ka10059 AmountQuantityType: AMOUNT="1" / QUANTITY="2"
    ka10131 ContinuousAmtQtyType: AMOUNT="0" / QUANTITY="1"  ← 반대!

    enum 분리가 컴파일 타임 가드 — 두 endpoint 간 실수 혼용 차단.
    """

    AMOUNT = "0"
    QUANTITY = "1"


class StockIndsType(StrEnum):
    """ka10131 stk_inds_tp — 종목/업종 (D-14: 본 chunk 는 STOCK 만 운영)."""

    STOCK = "0"
    INDUSTRY = "1"


# ---------- ka10058 InvestorDailyTradeRow / Response / Normalized ----------


class InvestorDailyTradeRow(BaseModel):
    """ka10058 응답 row — 11 필드 (B-γ-1 max_length 강제 패턴)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    stk_cd: Annotated[str, Field(max_length=20)] = ""
    stk_nm: Annotated[str, Field(max_length=100)] = ""
    netslmt_qty: Annotated[str, Field(max_length=32)] = ""
    netslmt_amt: Annotated[str, Field(max_length=32)] = ""
    prsm_avg_pric: Annotated[str, Field(max_length=32)] = ""
    cur_prc: Annotated[str, Field(max_length=32)] = ""
    pre_sig: Annotated[str, Field(max_length=4)] = ""
    pred_pre: Annotated[str, Field(max_length=32)] = ""
    avg_pric_pre: Annotated[str, Field(max_length=32)] = ""
    pre_rt: Annotated[str, Field(max_length=32)] = ""
    dt_trde_qty: Annotated[str, Field(max_length=32)] = ""

    def to_normalized(
        self,
        *,
        stock_id: int | None,
        as_of_date: date,
        investor_type: InvestorType,
        trade_type: InvestorTradeType,
        market_type: InvestorMarketType,
        exchange_type: RankingExchangeType,
        rank: int,
    ) -> NormalizedInvestorDailyTrade:
        """ka10058 row → NormalizedInvestorDailyTrade.

        - 부호 + 이중 부호: ``_strip_double_sign_int`` 재사용 (ka10086 가설 B 정착됨).
        - ``prsm_avg_pric`` 은 양수 추정 평균가 → ``_to_int``.
        - ``pre_rt`` (``+7.43``) → ``_to_decimal`` (ka10059 의 ``+698`` 표기와 다름).
        """
        return NormalizedInvestorDailyTrade(
            as_of_date=as_of_date,
            stock_id=stock_id,
            stock_code_raw=self.stk_cd,
            investor_type=investor_type,
            trade_type=trade_type,
            market_type=market_type,
            exchange_type=exchange_type,
            rank=rank,
            net_volume=_strip_double_sign_int(self.netslmt_qty),
            net_amount=_strip_double_sign_int(self.netslmt_amt),
            estimated_avg_price=_to_int(self.prsm_avg_pric),
            current_price=_strip_double_sign_int(self.cur_prc),
            prev_compare_sign=self.pre_sig or None,
            prev_compare_amount=_strip_double_sign_int(self.pred_pre),
            avg_price_compare=_strip_double_sign_int(self.avg_pric_pre),
            prev_compare_rate=_to_decimal(self.pre_rt),
            period_volume=_to_int(self.dt_trde_qty),
            stock_name=self.stk_nm,
        )


class InvestorDailyTradeResponse(BaseModel):
    """ka10058 응답 wrapper — `invsr_daly_trde_stk` list."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    invsr_daly_trde_stk: list[InvestorDailyTradeRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: Annotated[str, Field(max_length=200)] = ""


@dataclass(frozen=True, slots=True)
class NormalizedInvestorDailyTrade:
    """ka10058 정규화 도메인 — Repository 가 보는 형태."""

    as_of_date: date
    stock_id: int | None
    stock_code_raw: str
    investor_type: InvestorType
    trade_type: InvestorTradeType
    market_type: InvestorMarketType
    exchange_type: RankingExchangeType
    rank: int
    net_volume: int | None
    net_amount: int | None
    estimated_avg_price: int | None
    current_price: int | None
    prev_compare_sign: str | None
    prev_compare_amount: int | None
    avg_price_compare: int | None
    prev_compare_rate: Decimal | None
    period_volume: int | None
    stock_name: str


# ---------- ka10059 StockInvestorBreakdownRow / Response / Normalized ----------


class StockInvestorBreakdownRow(BaseModel):
    """ka10059 응답 row — 20 필드 wide (12 net 카테고리 + OHLCV + 메타)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    dt: Annotated[str, Field(max_length=8)] = ""
    cur_prc: Annotated[str, Field(max_length=32)] = ""
    pre_sig: Annotated[str, Field(max_length=4)] = ""
    pred_pre: Annotated[str, Field(max_length=32)] = ""
    flu_rt: Annotated[str, Field(max_length=32)] = ""
    acc_trde_qty: Annotated[str, Field(max_length=32)] = ""
    acc_trde_prica: Annotated[str, Field(max_length=32)] = ""
    # 12 투자자 카테고리 net (부호 포함)
    ind_invsr: Annotated[str, Field(max_length=32)] = ""
    frgnr_invsr: Annotated[str, Field(max_length=32)] = ""
    orgn: Annotated[str, Field(max_length=32)] = ""
    fnnc_invt: Annotated[str, Field(max_length=32)] = ""
    insrnc: Annotated[str, Field(max_length=32)] = ""
    invtrt: Annotated[str, Field(max_length=32)] = ""
    etc_fnnc: Annotated[str, Field(max_length=32)] = ""
    bank: Annotated[str, Field(max_length=32)] = ""
    penfnd_etc: Annotated[str, Field(max_length=32)] = ""
    samo_fund: Annotated[str, Field(max_length=32)] = ""
    natn: Annotated[str, Field(max_length=32)] = ""
    etc_corp: Annotated[str, Field(max_length=32)] = ""
    natfor: Annotated[str, Field(max_length=32)] = ""

    def to_normalized(
        self,
        *,
        stock_id: int | None,
        amt_qty_tp: AmountQuantityType,
        trade_type: StockInvestorTradeType,
        unit_tp: UnitType,
        exchange_type: RankingExchangeType,
    ) -> NormalizedStockInvestorBreakdown:
        """ka10059 row → NormalizedStockInvestorBreakdown.

        - ``flu_rt`` (``+698``) → ``_to_decimal_div_100`` (6.98). ka10058 ``pre_rt`` 와
          다른 표기 — endpoint-24 § 11.2 운영 검증 1순위.
        - 12 net 카테고리: ``_strip_double_sign_int`` (이중 부호 ``--714`` 가설 B 재사용).
        - ``trading_date`` 빈 입력 → ``date.min`` (Repository skip 안전망).
        """
        return NormalizedStockInvestorBreakdown(
            stock_id=stock_id,
            trading_date=_parse_yyyymmdd(self.dt) or date.min,
            amt_qty_tp=amt_qty_tp,
            trade_type=trade_type,
            unit_tp=unit_tp,
            exchange_type=exchange_type,
            current_price=_strip_double_sign_int(self.cur_prc),
            prev_compare_sign=self.pre_sig or None,
            prev_compare_amount=_strip_double_sign_int(self.pred_pre),
            change_rate=_to_decimal_div_100(self.flu_rt),
            acc_trade_volume=_to_int(self.acc_trde_qty),
            acc_trade_amount=_to_int(self.acc_trde_prica),
            net_individual=_strip_double_sign_int(self.ind_invsr),
            net_foreign=_strip_double_sign_int(self.frgnr_invsr),
            net_institution_total=_strip_double_sign_int(self.orgn),
            net_financial_inv=_strip_double_sign_int(self.fnnc_invt),
            net_insurance=_strip_double_sign_int(self.insrnc),
            net_investment_trust=_strip_double_sign_int(self.invtrt),
            net_other_financial=_strip_double_sign_int(self.etc_fnnc),
            net_bank=_strip_double_sign_int(self.bank),
            net_pension_fund=_strip_double_sign_int(self.penfnd_etc),
            net_private_fund=_strip_double_sign_int(self.samo_fund),
            net_nation=_strip_double_sign_int(self.natn),
            net_other_corp=_strip_double_sign_int(self.etc_corp),
            net_dom_for=_strip_double_sign_int(self.natfor),
        )


class StockInvestorBreakdownResponse(BaseModel):
    """ka10059 응답 wrapper — `stk_invsr_orgn` list."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    stk_invsr_orgn: list[StockInvestorBreakdownRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: Annotated[str, Field(max_length=200)] = ""


@dataclass(frozen=True, slots=True)
class NormalizedStockInvestorBreakdown:
    """ka10059 정규화 도메인 — Repository 가 보는 형태 (Phase G — 12 net 카테고리)."""

    stock_id: int | None
    trading_date: date
    amt_qty_tp: AmountQuantityType
    trade_type: StockInvestorTradeType
    unit_tp: UnitType
    exchange_type: RankingExchangeType
    current_price: int | None
    prev_compare_sign: str | None
    prev_compare_amount: int | None
    change_rate: Decimal | None
    acc_trade_volume: int | None
    acc_trade_amount: int | None
    # 12 투자자 카테고리 net
    net_individual: int | None
    net_foreign: int | None
    net_institution_total: int | None
    net_financial_inv: int | None
    net_insurance: int | None
    net_investment_trust: int | None
    net_other_financial: int | None
    net_bank: int | None
    net_pension_fund: int | None
    net_private_fund: int | None
    net_nation: int | None
    net_other_corp: int | None
    net_dom_for: int | None


# ---------- ka10131 ContinuousFrgnOrgnRow / Response / Normalized ----------


class ContinuousFrgnOrgnRow(BaseModel):
    """ka10131 응답 row — 19 필드 (기관/외국인/합계 × 5 metric + rank + 메타)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    rank: Annotated[str, Field(max_length=8)] = ""
    stk_cd: Annotated[str, Field(max_length=20)] = ""
    stk_nm: Annotated[str, Field(max_length=100)] = ""
    prid_stkpc_flu_rt: Annotated[str, Field(max_length=32)] = ""
    # 기관 5
    orgn_nettrde_amt: Annotated[str, Field(max_length=32)] = ""
    orgn_nettrde_qty: Annotated[str, Field(max_length=32)] = ""
    orgn_cont_netprps_dys: Annotated[str, Field(max_length=32)] = ""
    orgn_cont_netprps_qty: Annotated[str, Field(max_length=32)] = ""
    orgn_cont_netprps_amt: Annotated[str, Field(max_length=32)] = ""
    # 외국인 5
    frgnr_nettrde_qty: Annotated[str, Field(max_length=32)] = ""
    frgnr_nettrde_amt: Annotated[str, Field(max_length=32)] = ""
    frgnr_cont_netprps_dys: Annotated[str, Field(max_length=32)] = ""
    frgnr_cont_netprps_qty: Annotated[str, Field(max_length=32)] = ""
    frgnr_cont_netprps_amt: Annotated[str, Field(max_length=32)] = ""
    # 합계 5
    nettrde_qty: Annotated[str, Field(max_length=32)] = ""
    nettrde_amt: Annotated[str, Field(max_length=32)] = ""
    tot_cont_netprps_dys: Annotated[str, Field(max_length=32)] = ""
    tot_cont_nettrde_qty: Annotated[str, Field(max_length=32)] = ""
    tot_cont_netprps_amt: Annotated[str, Field(max_length=32)] = ""

    def to_normalized(
        self,
        *,
        stock_id: int | None,
        as_of_date: date,
        period_type: ContinuousPeriodType,
        market_type: InvestorMarketType,
        amt_qty_tp: ContinuousAmtQtyType,
        stk_inds_tp: StockIndsType,
        exchange_type: RankingExchangeType,
    ) -> NormalizedFrgnOrgnConsecutive:
        """ka10131 row → NormalizedFrgnOrgnConsecutive.

        - ``rank``: ``_to_int`` (양수 정수). 빈 입력 → 0 (caller 가 skip).
        - ``prid_stkpc_flu_rt`` (``-5.80``) → ``_to_decimal`` (ka10059 ``+698`` 표기와 다름).
        - 15 metric: ``_strip_double_sign_int`` (이중 부호 처리).
        - ``tot_cont_netprps_dys = orgn + frgnr`` 정합성은 raw 적재 (운영 검증).
        """
        return NormalizedFrgnOrgnConsecutive(
            stock_id=stock_id,
            stock_code_raw=self.stk_cd,
            stock_name=self.stk_nm,
            as_of_date=as_of_date,
            period_type=period_type,
            market_type=market_type,
            amt_qty_tp=amt_qty_tp,
            stk_inds_tp=stk_inds_tp,
            exchange_type=exchange_type,
            rank=_to_int(self.rank) or 0,
            period_stock_price_flu_rt=_to_decimal(self.prid_stkpc_flu_rt),
            orgn_net_amount=_strip_double_sign_int(self.orgn_nettrde_amt),
            orgn_net_volume=_strip_double_sign_int(self.orgn_nettrde_qty),
            orgn_cont_days=_strip_double_sign_int(self.orgn_cont_netprps_dys),
            orgn_cont_volume=_strip_double_sign_int(self.orgn_cont_netprps_qty),
            orgn_cont_amount=_strip_double_sign_int(self.orgn_cont_netprps_amt),
            frgnr_net_volume=_strip_double_sign_int(self.frgnr_nettrde_qty),
            frgnr_net_amount=_strip_double_sign_int(self.frgnr_nettrde_amt),
            frgnr_cont_days=_strip_double_sign_int(self.frgnr_cont_netprps_dys),
            frgnr_cont_volume=_strip_double_sign_int(self.frgnr_cont_netprps_qty),
            frgnr_cont_amount=_strip_double_sign_int(self.frgnr_cont_netprps_amt),
            total_net_volume=_strip_double_sign_int(self.nettrde_qty),
            total_net_amount=_strip_double_sign_int(self.nettrde_amt),
            total_cont_days=_strip_double_sign_int(self.tot_cont_netprps_dys),
            total_cont_volume=_strip_double_sign_int(self.tot_cont_nettrde_qty),
            total_cont_amount=_strip_double_sign_int(self.tot_cont_netprps_amt),
        )


class ContinuousFrgnOrgnResponse(BaseModel):
    """ka10131 응답 wrapper — `orgn_frgnr_cont_trde_prst` list."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    orgn_frgnr_cont_trde_prst: list[ContinuousFrgnOrgnRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: Annotated[str, Field(max_length=200)] = ""


@dataclass(frozen=True, slots=True)
class NormalizedFrgnOrgnConsecutive:
    """ka10131 정규화 도메인 — Repository 가 보는 형태 (Phase G — 15 metric)."""

    stock_id: int | None
    stock_code_raw: str
    stock_name: str
    as_of_date: date
    period_type: ContinuousPeriodType
    market_type: InvestorMarketType
    amt_qty_tp: ContinuousAmtQtyType
    stk_inds_tp: StockIndsType
    exchange_type: RankingExchangeType
    rank: int
    period_stock_price_flu_rt: Decimal | None
    # 기관 5
    orgn_net_amount: int | None
    orgn_net_volume: int | None
    orgn_cont_days: int | None
    orgn_cont_volume: int | None
    orgn_cont_amount: int | None
    # 외국인 5
    frgnr_net_volume: int | None
    frgnr_net_amount: int | None
    frgnr_cont_days: int | None
    frgnr_cont_volume: int | None
    frgnr_cont_amount: int | None
    # 합계 5
    total_net_volume: int | None
    total_net_amount: int | None
    total_cont_days: int | None
    total_cont_volume: int | None
    total_cont_amount: int | None


__all__ = [
    # Phase C — ka10086 daily market
    "DailyMarketResponse",
    "DailyMarketRow",
    "NormalizedDailyFlow",
    # Phase F-4 — 5 ranking enums + rows + responses
    "FluRtSortType",
    "FluRtUpperResponse",
    "FluRtUpperRow",
    "PredVolumeUpperResponse",
    "PredVolumeUpperRow",
    "RankingExchangeType",
    "RankingMarketType",
    "RankingType",
    "TodayVolumeSortType",
    "TodayVolumeUpperResponse",
    "TodayVolumeUpperRow",
    "TradeAmountUpperResponse",
    "TradeAmountUpperRow",
    "VolumeSdninResponse",
    "VolumeSdninRow",
    "VolumeSdninSortType",
    "VolumeSdninTimeType",
    # Phase E — short selling + lending
    "LendingMarketResponse",
    "LendingMarketRow",
    "LendingScope",
    "LendingStockResponse",
    "LendingStockRow",
    "NormalizedLendingMarket",
    "NormalizedShortSelling",
    "ShortSellingResponse",
    "ShortSellingRow",
    "ShortSellingTimeType",
    # Phase G — 투자자별 매매 흐름 (ka10058/10059/10131)
    "AmountQuantityType",
    "ContinuousAmtQtyType",
    "ContinuousFrgnOrgnResponse",
    "ContinuousFrgnOrgnRow",
    "ContinuousPeriodType",
    "InvestorDailyTradeResponse",
    "InvestorDailyTradeRow",
    "InvestorMarketType",
    "InvestorTradeType",
    "InvestorType",
    "NormalizedFrgnOrgnConsecutive",
    "NormalizedInvestorDailyTrade",
    "NormalizedStockInvestorBreakdown",
    "StockIndsType",
    "StockInvestorBreakdownResponse",
    "StockInvestorBreakdownRow",
    "StockInvestorTradeType",
    "UnitType",
    "_strip_double_sign_int",
    "_to_decimal_div_100",
]
