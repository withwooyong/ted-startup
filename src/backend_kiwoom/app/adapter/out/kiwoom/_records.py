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


__all__ = [
    "DailyMarketResponse",
    "DailyMarketRow",
    "NormalizedDailyFlow",
    "_strip_double_sign_int",
]
