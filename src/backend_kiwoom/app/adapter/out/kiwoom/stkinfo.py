"""KiwoomStkInfoClient — `/api/dostk/stkinfo` 계열 어댑터.

설계: endpoint-14-ka10101.md § 6.1 + endpoint-03-ka10099.md § 6.1 + endpoint-04-ka10100.md § 6.1
+ endpoint-05-ka10001.md § 6.1.

범위: ka10101 (sector 마스터, A3-α) + ka10099 (stock 마스터, B-α) + ka10100 (stock gap-filler, B-β)
+ ka10001 (종목 기본 정보 / 펀더멘털, B-γ-1 KRX-only).

책임:
- KiwoomClient(공통 트랜스포트) 위임 — 토큰 / 재시도 / rate-limit / 페이지네이션
- mrkt_tp 사전 검증 — 잘못된 값은 호출 자체 차단 (ka10101: 5종 / ka10099: 16종)
- 응답 row 파싱 (Pydantic) → KiwoomResponseValidationError 매핑
- 페이지네이션 결과 합치기
- ka10099 응답 row 정규화 — zero-padded 문자열 → BIGINT/DATE/BOOL

camelCase 키 유지 (키움 응답 그대로) — 영속화 단계에서 snake_case 매핑.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.adapter.out.kiwoom._client import KiwoomClient
from app.adapter.out.kiwoom._exceptions import KiwoomResponseValidationError
from app.application.constants import ExchangeType, StockListMarketType

VALID_MRKT_TP: Final[tuple[str, ...]] = ("0", "1", "2", "4", "7")
"""ka10101 mrkt_tp 유효값 (master.md § 11.3 - 다른 endpoint 와 의미 다름).

0: 코스피(거래소) / 1: 코스닥 / 2: KOSPI200 / 4: KOSPI100 / 7: KRX100
"""

__all__ = [
    "KiwoomStkInfoClient",
    "NormalizedFundamental",
    "NormalizedStock",
    "SectorListRequest",
    "SectorListResponse",
    "SectorRow",
    "SentinelStockCodeError",
    "StockBasicInfoRequest",
    "StockBasicInfoResponse",
    "StockListRequest",
    "StockListResponse",
    "StockLookupRequest",
    "StockLookupResponse",
    "STK_CD_CHART_PATTERN",
    "STK_CD_LOOKUP_PATTERN",
]


class SectorListRequest(BaseModel):
    """ka10101 요청 본문."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mrkt_tp: Literal["0", "1", "2", "4", "7"]


class SectorRow(BaseModel):
    """업종 row — camelCase 유지 (키움 응답 그대로)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    marketCode: str  # 요청한 mrkt_tp 에코  # noqa: N815 — 키움 응답 키 그대로
    code: Annotated[str, Field(min_length=1, max_length=10)]
    name: Annotated[str, Field(min_length=1, max_length=100)]
    group: str = ""


class SectorListResponse(BaseModel):
    """ka10101 응답 본문.

    `list` 필드명이 builtin `list` 를 가리므로 attribute 는 `items` 로 노출,
    JSON 키는 alias 로 `list` 유지 (`populate_by_name=True` 로 양방향 허용).
    """

    model_config = ConfigDict(frozen=True, extra="ignore", populate_by_name=True)

    items: list[SectorRow] = Field(default_factory=list, alias="list")
    return_code: int = 0
    return_msg: str = ""


# =============================================================================
# ka10099 — 종목정보 리스트 (Phase B-α)
# =============================================================================


class StockListRequest(BaseModel):
    """ka10099 요청 본문 — 1R L1 sector 패턴 일관 (wire 직전 Pydantic 검증).

    `mrkt_tp` 는 StockListMarketType StrEnum value (16종 중 1).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    mrkt_tp: str


VALID_STOCK_MRKT_TP: Final[frozenset[str]] = frozenset(
    {
        "0",
        "10",
        "30",
        "50",
        "60",
        "70",
        "80",
        "90",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
    }
)
"""ka10099 mrkt_tp 16종 — endpoint-03-ka10099.md § 2.3.

ka10101 (`0/1/2/4/7`) 와 의미 다름. master.md § 12 결정 기록.
"""


def _parse_yyyymmdd(value: str) -> date | None:
    """YYYYMMDD 8자리 → date | None. 형식 위반 시 None — listed_date NULL 허용 (§3.4)."""
    if not value or len(value) != 8:
        return None
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return None


def _parse_zero_padded_int(value: str) -> int | None:
    """zero-padded 문자열 → int | None.

    예: "0000000123759593" → 123759593 / "" → None / "00000000" → 0.
    비숫자 (예: "abc") 는 ValueError 전파 — caller 가 KiwoomResponseValidationError 매핑.
    """
    if not value:
        return None
    return int(value)


class StockListRow(BaseModel):
    """ka10099 응답 row — camelCase 유지 (키움 응답 그대로).

    `extra="ignore"` — 키움이 신규 필드 추가해도 어댑터 안 깨짐.
    14개 정의된 필드 외 모두 무시.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    code: Annotated[str, Field(min_length=1, max_length=20)]
    name: Annotated[str, Field(min_length=1, max_length=40)]
    listCount: str = ""  # noqa: N815 — 키움 응답 키 그대로
    auditInfo: str = ""  # noqa: N815
    regDay: str = ""  # noqa: N815
    lastPrice: str = ""  # noqa: N815
    state: str = ""
    marketCode: str = ""  # noqa: N815
    marketName: str = ""  # noqa: N815
    upName: str = ""  # noqa: N815
    upSizeName: str = ""  # noqa: N815
    companyClassName: str = ""  # noqa: N815
    orderWarning: Annotated[str, Field(max_length=1)] = "0"  # noqa: N815
    nxtEnable: Annotated[str, Field(max_length=2)] = ""  # noqa: N815

    def to_normalized(self, requested_market_code: str, *, mock_env: bool = False) -> NormalizedStock:
        """zero-padded 문자열 → BIGINT/DATE/BOOL 정규화.

        market_code 정책 (1R 1차 리뷰 H1 — cross-market zombie row 방지):
        - **항상 `requested_market_code` 우선** (sector 패턴 일관, deactivate_missing 격리 보장)
        - 응답 `marketCode` 가 요청과 다른 경우 (§11.2 Excel 샘플 의심) NormalizedStock
          의 `requested_market_type` 와 `market_code` 가 같은 값으로 저장되며, 응답
          `marketCode` 는 영속화하지 않음 (DB 무결성 우선)
        - 운영 dry-run 시 응답 `marketCode` 분포는 logger.warning 으로 추적 (§11.2)

        Parameters:
            requested_market_code: 호출 시 mrkt_tp 값 — 영속 저장의 권위 있는 source.
            mock_env: True 면 응답의 `nxtEnable` 무시하고 일률 False (§4.2).

        Raises:
            ValueError: listCount/lastPrice 가 비숫자 (caller 가 검증 예외로 매핑).
        """
        nxt_enable = False if mock_env else (self.nxtEnable.upper() == "Y")
        return NormalizedStock(
            stock_code=self.code,
            stock_name=self.name,
            list_count=_parse_zero_padded_int(self.listCount),
            audit_info=self.auditInfo or None,
            listed_date=_parse_yyyymmdd(self.regDay),
            last_price=_parse_zero_padded_int(self.lastPrice),
            state=self.state or None,
            market_code=requested_market_code,  # 1R H1 — 응답 marketCode 무시 (sector 패턴 일관)
            market_name=self.marketName or None,
            up_name=self.upName or None,
            up_size_name=self.upSizeName or None,
            company_class_name=self.companyClassName or None,
            order_warning=self.orderWarning or "0",
            nxt_enable=nxt_enable,
            requested_market_type=requested_market_code,
        )


class StockListResponse(BaseModel):
    """ka10099 응답 — `list` 필드를 `items` attribute 로 노출 (sector 패턴 일관)."""

    model_config = ConfigDict(frozen=True, extra="ignore", populate_by_name=True)

    items: list[StockListRow] = Field(default_factory=list, alias="list")
    return_code: int = 0
    return_msg: str = ""


# =============================================================================
# ka10100 — 종목정보 조회 (단건, Phase B-β)
# =============================================================================


STK_CD_LOOKUP_PATTERN: Final[str] = r"^[0-9]{6}$"
"""ka10100/ka10001 lookup stk_cd 정규식 — Excel R22 Length=6, ASCII 0-9 only.

`_NX`/`_AL` suffix 거부 + unicode digit 거부 (`\\d` 가 unicode digit 매칭하는 점
방어, 1R 2b L2). lookup 계열 어댑터 검증 / Pydantic Request / 라우터 Path pattern
세 곳이 모두 본 상수 참조.

chart 계열 (ka10081/82/83/94 + ka10086) 은 `STK_CD_CHART_PATTERN` (영숫자) 사용 —
Chunk 1 dry-run (ADR § 32) 에서 키움 chart endpoint 가 우선주 영숫자 stk_cd 수용
확정 후 분리.
"""

STK_CD_CHART_PATTERN: Final[str] = r"^[0-9A-Z]{6}$"
"""chart 계열 (ka10081/82/83/94 + ka10086) stk_cd 정규식 — 영숫자 대문자 6자리.

LOOKUP 패턴과의 차이: 우선주 (`*K` suffix, 예 `03473K` SK우) / 특수 종목 호환. Excel
docs 는 lookup R22 ASCII 만 명시하나 운영 dry-run (ADR § 32) 에서 chart endpoint
6 호출 모두 SUCCESS — wire-level 수용 확정.

lowercase 거부 유지 (정규식 `A-Z` 만) — 키움 응답 / 마스터 데이터 모두 uppercase 만
관찰. lowercase 입력은 mock/test 사고 또는 공격 패턴으로 간주.
"""

_STK_CD_LOOKUP_RE = re.compile(STK_CD_LOOKUP_PATTERN)
_STK_CD_CHART_RE = re.compile(STK_CD_CHART_PATTERN)


class SentinelStockCodeError(ValueError):
    """sentinel 종목코드 거부 — 운영 의도된 skip (Phase F-1).

    설계: phase-f-1-ka10001-numeric-sentinel.md § 4 결정 #4.

    감지 대상 sentinel 패턴 (§ 2.3):
    - NXT 우선주 sentinel: ``0000D0`` / ``0000H0`` / ``0000J0`` / ``0000Y0`` / ``0000Z0``
      (4자리 0 + 1문자 + 1자리 0)
    - KRX 우선주 / ETN K/L suffix: ``26490K`` / ``28513K`` / ``0070X0`` 등

    상속:
    - ``ValueError`` 상속 — 기존 ``except ValueError:`` caller 호환 유지.
    - service layer 는 본 예외를 별도 catch → ``result.skipped`` 적재 (failed 분리).
    """


def _validate_stk_cd_for_lookup(stk_cd: str) -> None:
    """ka10100/ka10001 stk_cd 사전 검증 — 6자리 ASCII 숫자만. 호출 자체 차단.

    Excel R22 Length=6 — 다른 차트 endpoint 의 `_NX`/`_AL` suffix(Length=20) 와 다름.
    빈 문자열·공백·영문·unicode digit 모두 거부.

    예외 메시지의 입력값은 50자 cap (B-γ-1 2R A-L1) — 거대 입력 / 제어문자 박힌 입력이
    log line 폭주 / RTL override 등 공격 시 message 자체를 dos 수단으로 쓰는 것 차단.

    Phase F-1: ``SentinelStockCodeError(ValueError)`` raise — ValueError 상속이라
    기존 ``except ValueError:`` 호환. service layer 는 별도 catch → ``result.skipped``.
    """
    if not _STK_CD_LOOKUP_RE.fullmatch(stk_cd):
        raise SentinelStockCodeError(f"stk_cd 는 6자리 ASCII 숫자만 허용: {stk_cd[:50]!r}")


def _validate_stk_cd_for_chart(stk_cd: str) -> None:
    """ka10081/82/83/94/ka10086 stk_cd 사전 검증 — 6자리 영숫자 대문자. 호출 자체 차단.

    LOOKUP 보다 관대 — 우선주 (`*K` suffix) / 특수 종목 호환. ADR § 32 dry-run 에서
    영숫자 stk_cd 수용 확정 후 분리. base code 만 (`_NX`/`_AL` suffix 거부) — caller 가
    이미 strip 후 호출. lowercase/특수문자/unicode 모두 거부.

    예외 메시지 50자 cap 정책은 LOOKUP 과 동일.
    """
    if not _STK_CD_CHART_RE.fullmatch(stk_cd):
        raise ValueError(f"stk_cd 는 6자리 영숫자 대문자만 허용: {stk_cd[:50]!r}")


class StockLookupResponse(BaseModel):
    """ka10100 응답 — flat object (ka10099 row + return_code/msg).

    ka10099 의 `StockListRow` 와 14 필드 동일하나 본 모델은 단건 응답을 root 에서
    파싱해야 하므로 별도 정의 (`return_code`/`return_msg` 동행, alias 없음).
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    code: Annotated[str, Field(min_length=1, max_length=20)]
    name: Annotated[str, Field(min_length=1, max_length=40)]
    listCount: str = ""  # noqa: N815 — 키움 응답 키 그대로
    auditInfo: str = ""  # noqa: N815
    regDay: str = ""  # noqa: N815
    lastPrice: str = ""  # noqa: N815
    state: str = ""
    marketCode: str = ""  # noqa: N815
    marketName: str = ""  # noqa: N815
    upName: str = ""  # noqa: N815
    upSizeName: str = ""  # noqa: N815
    companyClassName: str = ""  # noqa: N815
    orderWarning: Annotated[str, Field(max_length=1)] = "0"  # noqa: N815
    nxtEnable: Annotated[str, Field(max_length=2)] = ""  # noqa: N815
    return_code: int = 0
    return_msg: str = ""

    def to_normalized(self, *, mock_env: bool = False) -> NormalizedStock:
        """단건 응답 → NormalizedStock.

        ka10099 의 `to_normalized` 와 차이:
        - `requested_market_code` 인자 없음 — ka10100 은 stk_cd 만으로 호출하므로 응답
          marketCode 가 권위 있는 source. `requested_market_type` 도 응답값으로 채움.
        - 그 외 zero-padded · regDay · nxt_enable 변환은 동일 로직 (`_parse_zero_padded_int`,
          `_parse_yyyymmdd` 공유).

        Parameters:
            mock_env: True 면 응답 `nxtEnable` 무시 + 강제 False (mock 도메인 NXT 미지원).

        Raises:
            ValueError: listCount/lastPrice 가 비숫자 (caller 가 검증 예외로 매핑).
        """
        nxt_enable = False if mock_env else (self.nxtEnable.upper() == "Y")
        return NormalizedStock(
            stock_code=self.code,
            stock_name=self.name,
            list_count=_parse_zero_padded_int(self.listCount),
            audit_info=self.auditInfo or None,
            listed_date=_parse_yyyymmdd(self.regDay),
            last_price=_parse_zero_padded_int(self.lastPrice),
            state=self.state or None,
            market_code=self.marketCode,
            market_name=self.marketName or None,
            up_name=self.upName or None,
            up_size_name=self.upSizeName or None,
            company_class_name=self.companyClassName or None,
            order_warning=self.orderWarning or "0",
            nxt_enable=nxt_enable,
            requested_market_type=self.marketCode,
        )


class StockLookupRequest(BaseModel):
    """ka10100 요청 본문 — sector/ka10099 패턴 일관 (wire 직전 Pydantic 검증).

    pattern 은 `STK_CD_LOOKUP_PATTERN` 단일 source 참조 — 어댑터 validator / 라우터 Path
    pattern 과 sync (1R 2a H2 — 정규식 중복 단일화).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    stk_cd: Annotated[
        str,
        Field(min_length=6, max_length=6, pattern=STK_CD_LOOKUP_PATTERN),
    ]


@dataclass(frozen=True, slots=True)
class NormalizedStock:
    """정규화된 stock 도메인 — Repository 가 보는 형태.

    `requested_market_type` 는 호출 시 mrkt_tp 값. 응답 `marketCode` 와 다를 수 있음
    (§11.2 — Excel 샘플 mrkt_tp="0" 요청에 marketCode="10" 응답). market_code 는
    응답 값 우선, 응답 없으면 요청값 fallback.
    """

    stock_code: str
    stock_name: str
    list_count: int | None
    audit_info: str | None
    listed_date: date | None
    last_price: int | None
    state: str | None
    market_code: str
    market_name: str | None
    up_name: str | None
    up_size_name: str | None
    company_class_name: str | None
    order_warning: str
    nxt_enable: bool
    requested_market_type: str


# =============================================================================
# ka10001 — 주식 기본 정보 (펀더멘털 + 일중 시세 + 250일 통계, Phase B-γ-1)
# =============================================================================
#
# KRX-only 결정 (계획서 § 4.3 권장 (a)) — `_NX`/`_AL` suffix 미지원. NXT/SOR 추가는
# Phase C 후 결정. stk_cd 6자리 ASCII 검증은 ka10100 의 `_validate_stk_cd_for_lookup`
# 재사용.
#
# 응답 45 필드 → 5 카테고리:
# - A. 기본 (3): stk_cd, stk_nm, setl_mm
# - B. 자본/시총/외인 (11): fav, cap, flo_stk, mac, mac_wght, for_exh_rt, repl_pric,
#                            crd_rt, dstr_stk, dstr_rt, fav_unit
# - C. 재무 비율 (9): per, eps, roe, pbr, ev, bps, sale_amt, bus_pro, cup_nga
# - D. 250일/연중 통계 (8): 250hgst/lwst (alias), oyr_hgst/lwst
# - E. 일중 시세 (14): cur_prc, pre_sig, pred_pre, flu_rt, trde_qty, trde_pre,
#                      open/high/low/upl/lst/base_pric, exp_cntr_pric/qty


_BIGINT_MIN: Final[int] = -(2**63)
_BIGINT_MAX: Final[int] = 2**63 - 1


def _to_int(value: str) -> int | None:
    """zero-padded · 부호 포함 string → int | None.

    BIGINT 경계 가드 (B-γ-1 2R A-C1) — Python int 임의정밀 → PG BIGINT 한계
    `[-2^63, 2^63-1]` 초과 시 None 반환. 키움 응답이 단위 변경 / 외부 벤더 오염으로
    거대 숫자 보내도 트랜잭션 abort 차단.

    예:
        "+181400" → 181400 (양수 부호 흡수)
        "-91200"  → -91200 (음수 부호 보존)
        "00136000" → 136000 (zero-padded 흡수)
        ""        → None
        "-"       → None
        "+"       → None
        "abc"     → None (raise 안 함 — caller 가 검증 별도)
        "9" * 30  → None (BIGINT overflow)

    raise 안 함 — 외부 벤더 빈/잘못 응답은 NULL 영속화 정책 (§ 11.2).
    """
    if not value:
        return None
    stripped = value.strip().replace(",", "")
    if stripped in ("-", "+"):
        return None
    try:
        n = int(stripped)
    except ValueError:
        return None
    if not (_BIGINT_MIN <= n <= _BIGINT_MAX):
        return None
    return n


def _to_decimal(value: str) -> Decimal | None:
    """zero-padded · 부호 포함 string → Decimal | None.

    is_finite 가드 (B-γ-1 2R A-C2 / A-H4) — `Decimal("NaN")`/`Decimal("Infinity")`/
    `Decimal("sNaN")` 은 InvalidOperation 발생 안 함 (정상 생성). 그러나 PG NUMERIC
    에 NaN 박히면 다운스트림 백테스팅 산술 폭발 + signaling NaN 은 hash 산출 시
    raise. `is_finite()` 로 finite 값만 통과시킴.

    `_to_int` 와의 비대칭 해소 (M-2): 천단위 콤마 처리도 동일하게 적용.

    예:
        "+0.0800"   → Decimal("+0.0800")
        "-25.5000"  → Decimal("-25.5000")
        "1,234.56"  → Decimal("1234.56")
        ""          → None
        "-"         → None
        "abc"       → None
        "NaN"       → None (vendor 오염 차단)
        "Infinity"  → None
        "sNaN"      → None
    """
    if not value:
        return None
    stripped = value.strip().replace(",", "")
    if stripped in ("-", "+"):
        return None
    try:
        d = Decimal(stripped)
    except (InvalidOperation, ValueError):
        return None
    if not d.is_finite():
        return None
    return d


def strip_kiwoom_suffix(stk_cd: str) -> str:
    """`'005930_NX' → '005930'`, `'005930_AL' → '005930'`, `'005930' → '005930'`.

    응답 `stk_cd` 가 요청 그대로 메아리쳐서 suffix 가 박혀 올 수 있음 (§ 11.2).
    영속화 시 base code (6자리) 로 정규화 — Stock 마스터 FK lookup 일관.
    """
    if not stk_cd:
        return stk_cd
    return stk_cd.split("_", maxsplit=1)[0]


def build_stk_cd(stock_code: str, exchange: ExchangeType) -> str:
    """`(stock_code, exchange) → 키움 호출용 stk_cd` (Phase C 첫 도입).

    설계: endpoint-06-ka10081.md § 2.4. ka10081 / ka10082 / ka10083 / ka10094 +
    ka10086 chart 계열 endpoint 가 본 헬퍼로 stk_cd suffix 합성.

    KRX:  '005930' → '005930'  /  '03473K' → '03473K'
    NXT:  '005930' → '005930_NX'  /  '03473K' → '03473K_NX'
    SOR:  '005930' → '005930_AL'  /  '03473K' → '03473K_AL'

    pre-validation: stock_code 6자리 영숫자 대문자 (`STK_CD_CHART_PATTERN`). LOOKUP
    (`^[0-9]{6}$`) 보다 관대 — 우선주 (`*K` suffix) / 특수 종목 호환 (ADR § 32 chunk 2).
    `_NX`/`_AL` suffix 가 박힌 입력은 거부 — caller 가 이미 base code 로 strip 후 호출.

    Raises:
        ValueError: stock_code 가 6자리 영숫자 대문자 외 또는 미지원 ExchangeType.
    """
    _validate_stk_cd_for_chart(stock_code)
    if exchange is ExchangeType.KRX:
        return stock_code
    if exchange is ExchangeType.NXT:
        return f"{stock_code}_NX"
    if exchange is ExchangeType.SOR:
        return f"{stock_code}_AL"
    raise ValueError(f"unknown exchange: {exchange!r}")


class StockBasicInfoRequest(BaseModel):
    """ka10001 요청 본문 — sector/ka10099/ka10100 패턴 일관 (wire 직전 Pydantic 검증).

    KRX-only — `_NX`/`_AL` suffix 미지원. `STK_CD_LOOKUP_PATTERN` (`^[0-9]{6}$`)
    재사용 — ka10100 과 같은 6자리 ASCII 단일 source.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    stk_cd: Annotated[
        str,
        Field(min_length=6, max_length=6, pattern=STK_CD_LOOKUP_PATTERN),
    ]


class StockBasicInfoResponse(BaseModel):
    """ka10001 응답 — flat object (45 필드 + return_code/msg).

    `populate_by_name=True` 로 비-식별자 키 (`250hgst` 등) 를 alias 로 매핑.
    `extra="ignore"` — 키움이 신규 필드 추가해도 어댑터 안 깨짐.

    필드 빈값 정책: 모든 string 필드 디폴트 "" — 외부 벤더 미공급 (PER/EPS/ROE 등)
    종목도 응답 파싱 가능. 정규화 시 None 으로 변환.
    """

    model_config = ConfigDict(frozen=True, extra="ignore", populate_by_name=True)

    # B-γ-1 2R A-H1 — 모든 string 필드에 max_length 강제 (Pydantic → DB CHAR/VARCHAR sync).
    # vendor 가 거대 string 보내도 DataError 트랜잭션 abort + 메모리 RSS 폭증 차단.
    # 길이 위반 → ValidationError → flag-then-raise-outside-except 가
    # KiwoomResponseValidationError 로 매핑.

    # A. 기본
    stk_cd: Annotated[str, Field(min_length=1, max_length=20)]
    stk_nm: Annotated[str, Field(max_length=40)] = ""
    setl_mm: Annotated[str, Field(max_length=2)] = ""

    # B. 자본 / 시총 / 외인 — 모두 정규화 거치므로 32자 cap (BIGINT 19자 + 부호/콤마 여유)
    fav: Annotated[str, Field(max_length=32)] = ""
    fav_unit: Annotated[str, Field(max_length=10)] = ""
    cap: Annotated[str, Field(max_length=32)] = ""
    flo_stk: Annotated[str, Field(max_length=32)] = ""
    mac: Annotated[str, Field(max_length=32)] = ""
    mac_wght: Annotated[str, Field(max_length=32)] = ""
    for_exh_rt: Annotated[str, Field(max_length=32)] = ""
    repl_pric: Annotated[str, Field(max_length=32)] = ""
    crd_rt: Annotated[str, Field(max_length=32)] = ""
    dstr_stk: Annotated[str, Field(max_length=32)] = ""
    dstr_rt: Annotated[str, Field(max_length=32)] = ""

    # C. 재무 비율 (외부 벤더 — 빈값 가능)
    per: Annotated[str, Field(max_length=32)] = ""
    eps: Annotated[str, Field(max_length=32)] = ""
    roe: Annotated[str, Field(max_length=32)] = ""
    pbr: Annotated[str, Field(max_length=32)] = ""
    ev: Annotated[str, Field(max_length=32)] = ""
    bps: Annotated[str, Field(max_length=32)] = ""
    sale_amt: Annotated[str, Field(max_length=32)] = ""
    bus_pro: Annotated[str, Field(max_length=32)] = ""
    cup_nga: Annotated[str, Field(max_length=32)] = ""

    # D. 250일 / 연중 통계 — Pydantic 식별자 첫 글자 숫자 불가 → alias
    high_250d: Annotated[str, Field(default="", alias="250hgst", max_length=32)]
    high_250d_date: Annotated[str, Field(default="", alias="250hgst_pric_dt", max_length=8)]
    high_250d_pre_rate: Annotated[str, Field(default="", alias="250hgst_pric_pre_rt", max_length=32)]
    low_250d: Annotated[str, Field(default="", alias="250lwst", max_length=32)]
    low_250d_date: Annotated[str, Field(default="", alias="250lwst_pric_dt", max_length=8)]
    low_250d_pre_rate: Annotated[str, Field(default="", alias="250lwst_pric_pre_rt", max_length=32)]
    oyr_hgst: Annotated[str, Field(max_length=32)] = ""
    oyr_lwst: Annotated[str, Field(max_length=32)] = ""

    # E. 일중 시세
    cur_prc: Annotated[str, Field(max_length=32)] = ""
    pre_sig: Annotated[str, Field(max_length=1)] = ""
    pred_pre: Annotated[str, Field(max_length=32)] = ""
    flu_rt: Annotated[str, Field(max_length=32)] = ""
    trde_qty: Annotated[str, Field(max_length=32)] = ""
    trde_pre: Annotated[str, Field(max_length=32)] = ""
    open_pric: Annotated[str, Field(max_length=32)] = ""
    high_pric: Annotated[str, Field(max_length=32)] = ""
    low_pric: Annotated[str, Field(max_length=32)] = ""
    upl_pric: Annotated[str, Field(max_length=32)] = ""
    lst_pric: Annotated[str, Field(max_length=32)] = ""
    base_pric: Annotated[str, Field(max_length=32)] = ""
    exp_cntr_pric: Annotated[str, Field(max_length=32)] = ""
    exp_cntr_qty: Annotated[str, Field(max_length=32)] = ""

    # 처리 결과
    return_code: int = 0
    return_msg: Annotated[str, Field(max_length=200)] = ""


@dataclass(frozen=True, slots=True)
class NormalizedFundamental:
    """ka10001 정규화 도메인 — Repository 가 보는 형태.

    KRX-only (§ 4.3) — `exchange="KRX"` 고정. NXT/SOR 추가 시 enum 도입 (Phase C 후).
    `asof_date` 는 응답 시점 KST 오늘 — 응답 본문에 timestamp 부재 (§ 11.2).
    PER/EPS/ROE/PBR/EV/BPS 는 외부 벤더 미공급 종목에서 None 가능.
    """

    stock_code: str            # base code (suffix 제거)
    exchange: str              # 'KRX' 고정 (B-γ-1 KRX-only)
    asof_date: date            # 응답 시점 KST 오늘
    stock_name: str
    settlement_month: str | None

    # B. 자본 / 시총 / 외인
    face_value: int | None
    face_value_unit: str | None
    capital_won: int | None
    listed_shares: int | None
    market_cap: int | None
    market_cap_weight: Decimal | None
    foreign_holding_rate: Decimal | None
    replacement_price: int | None
    credit_rate: Decimal | None
    circulating_shares: int | None
    circulating_rate: Decimal | None

    # C. 재무 비율
    per_ratio: Decimal | None
    eps_won: int | None
    roe_pct: Decimal | None
    pbr_ratio: Decimal | None
    ev_ratio: Decimal | None
    bps_won: int | None
    revenue_amount: int | None
    operating_profit: int | None
    net_profit: int | None

    # D. 250일 / 연중 통계
    high_250d: int | None
    high_250d_date: date | None
    high_250d_pre_rate: Decimal | None
    low_250d: int | None
    low_250d_date: date | None
    low_250d_pre_rate: Decimal | None
    year_high: int | None
    year_low: int | None

    # E. 일중 시세
    current_price: int | None
    prev_compare_sign: str | None
    prev_compare_amount: int | None
    change_rate: Decimal | None
    trade_volume: int | None
    trade_compare_rate: Decimal | None
    open_price: int | None
    high_price: int | None
    low_price: int | None
    upper_limit_price: int | None
    lower_limit_price: int | None
    base_price: int | None
    expected_match_price: int | None
    expected_match_volume: int | None


def normalize_basic_info(
    response: StockBasicInfoResponse,
    *,
    asof_date: date,
    exchange: str = "KRX",
) -> NormalizedFundamental:
    """ka10001 응답 → NormalizedFundamental.

    KRX-only (§ 4.3) — `exchange="KRX"` 디폴트. Phase C 에서 NXT/SOR 추가 시 caller
    에 명시 (BC 보존, B-γ-1 2R C-M4). NormalizedFundamental.exchange 는 caller 가 명시한
    값 그대로 영속화 (Repository upsert_one 의 ON CONFLICT 키 일치).

    응답 stk_cd 의 suffix 는 strip — 응답이 `005930_NX` 로 메아리치는 경우 방어
    (§ 11.2). caller 의 stock_id resolution 은 base code 로 한다 (ADR § 14 invariant).
    """
    base_code = strip_kiwoom_suffix(response.stk_cd)

    return NormalizedFundamental(
        stock_code=base_code,
        exchange=exchange,
        asof_date=asof_date,
        stock_name=response.stk_nm,
        settlement_month=response.setl_mm or None,

        # B
        face_value=_to_int(response.fav),
        face_value_unit=response.fav_unit or None,
        capital_won=_to_int(response.cap),
        listed_shares=_to_int(response.flo_stk),
        market_cap=_to_int(response.mac),
        market_cap_weight=_to_decimal(response.mac_wght),
        foreign_holding_rate=_to_decimal(response.for_exh_rt),
        replacement_price=_to_int(response.repl_pric),
        credit_rate=_to_decimal(response.crd_rt),
        circulating_shares=_to_int(response.dstr_stk),
        circulating_rate=_to_decimal(response.dstr_rt),

        # C
        per_ratio=_to_decimal(response.per),
        eps_won=_to_int(response.eps),
        roe_pct=_to_decimal(response.roe),
        pbr_ratio=_to_decimal(response.pbr),
        ev_ratio=_to_decimal(response.ev),
        bps_won=_to_int(response.bps),
        revenue_amount=_to_int(response.sale_amt),
        operating_profit=_to_int(response.bus_pro),
        net_profit=_to_int(response.cup_nga),

        # D
        high_250d=_to_int(response.high_250d),
        high_250d_date=_parse_yyyymmdd(response.high_250d_date),
        high_250d_pre_rate=_to_decimal(response.high_250d_pre_rate),
        low_250d=_to_int(response.low_250d),
        low_250d_date=_parse_yyyymmdd(response.low_250d_date),
        low_250d_pre_rate=_to_decimal(response.low_250d_pre_rate),
        year_high=_to_int(response.oyr_hgst),
        year_low=_to_int(response.oyr_lwst),

        # E
        current_price=_to_int(response.cur_prc),
        prev_compare_sign=response.pre_sig or None,
        prev_compare_amount=_to_int(response.pred_pre),
        change_rate=_to_decimal(response.flu_rt),
        trade_volume=_to_int(response.trde_qty),
        trade_compare_rate=_to_decimal(response.trde_pre),
        open_price=_to_int(response.open_pric),
        high_price=_to_int(response.high_pric),
        low_price=_to_int(response.low_pric),
        upper_limit_price=_to_int(response.upl_pric),
        lower_limit_price=_to_int(response.lst_pric),
        base_price=_to_int(response.base_pric),
        expected_match_price=_to_int(response.exp_cntr_pric),
        expected_match_volume=_to_int(response.exp_cntr_qty),
    )


class KiwoomStkInfoClient:
    """`/api/dostk/stkinfo` 어댑터. KiwoomClient 위임."""

    API_ID = "ka10101"
    PATH = "/api/dostk/stkinfo"

    # ka10099 전용 메타
    STOCK_LIST_API_ID = "ka10099"
    STOCK_LIST_MAX_PAGES = 100  # KOSPI ~900~1000 / KOSDAQ ~1500~1700 추정 — 페이지네이션 빈도 높음

    # ka10100 전용 메타 (B-β)
    STOCK_LOOKUP_API_ID = "ka10100"

    # ka10001 전용 메타 (B-γ-1)
    STOCK_BASIC_INFO_API_ID = "ka10001"

    def __init__(self, kiwoom_client: KiwoomClient) -> None:
        self._client = kiwoom_client

    async def fetch_sectors(self, mrkt_tp: Literal["0", "1", "2", "4", "7"]) -> SectorListResponse:
        """단일 시장의 업종 리스트 조회 — 페이지네이션 자동 합쳐짐.

        시그니처 타입을 Literal 로 강제 — mypy strict 가 caller (라우터) 까지 검증 (M2 적대적 리뷰).
        런타임 가드도 belt-and-suspenders 로 유지.

        Raises:
            ValueError: mrkt_tp 가 유효값 외 (typing.Literal 우회 시 안전망).
            KiwoomCredentialRejectedError: 401/403.
            KiwoomBusinessError: 응답 return_code != 0.
            KiwoomUpstreamError: 5xx · 네트워크 · 파싱 실패.
            KiwoomResponseValidationError: 응답 row Pydantic 검증 실패.
            KiwoomMaxPagesExceededError: max_pages=20 도달.
        """
        # Literal 시그니처가 정적 보호 — 런타임 가드는 동적 caller (예: dict.get) 안전망
        if mrkt_tp not in VALID_MRKT_TP:
            raise ValueError(f"mrkt_tp 유효값 외: {mrkt_tp!r} (허용: {VALID_MRKT_TP})")

        # SectorListRequest 사용 — wire 직전 Pydantic 검증 (1차 리뷰 MEDIUM)
        request_body = SectorListRequest(mrkt_tp=mrkt_tp).model_dump()

        all_rows: list[SectorRow] = []
        return_code = 0
        return_msg = ""

        async for page in self._client.call_paginated(
            api_id=self.API_ID,
            endpoint=self.PATH,
            body=request_body,
            max_pages=20,
        ):
            # 변수 캡처 후 except 밖 raise — `__context__` 차단 (C-1 적대적 리뷰 패턴 일관)
            validation_failed = False
            parsed: SectorListResponse | None = None
            try:
                parsed = SectorListResponse.model_validate(page.body)
            except ValidationError:
                validation_failed = True

            if validation_failed:
                # except 밖 raise — Pydantic ValidationError 가 cause/context 에 박히지 않음
                raise KiwoomResponseValidationError(f"{self.API_ID} 응답 검증 실패")
            if parsed is None:  # pragma: no cover — validation_failed 와 mutex
                raise RuntimeError("unreachable: parsed None without validation_failed")
            all_rows.extend(parsed.items)
            return_code = parsed.return_code
            return_msg = parsed.return_msg

        return SectorListResponse(
            items=all_rows,
            return_code=return_code,
            return_msg=return_msg,
        )

    async def fetch_stock_list(self, mrkt_tp: StockListMarketType) -> StockListResponse:
        """ka10099 — 단일 시장의 종목 list. 페이지네이션 자동 합쳐짐.

        시그니처 타입을 StockListMarketType StrEnum 으로 강제 — mypy strict 가 caller
        까지 검증. 런타임 가드도 belt-and-suspenders 로 유지 (Literal 우회 안전망).

        Raises:
            ValueError: mrkt_tp 가 16종 외 (StrEnum 우회 시 안전망).
            KiwoomCredentialRejectedError: 401/403.
            KiwoomBusinessError: 응답 return_code != 0.
            KiwoomUpstreamError: 5xx · 네트워크 · 파싱 실패.
            KiwoomResponseValidationError: 응답 row Pydantic 검증 실패.
            KiwoomMaxPagesExceededError: max_pages=100 도달.
        """
        # StrEnum 시그니처가 정적 보호 — 런타임 가드는 동적 caller (예: dict.get) 안전망
        mrkt_value = mrkt_tp.value if isinstance(mrkt_tp, StockListMarketType) else str(mrkt_tp)
        if mrkt_value not in VALID_STOCK_MRKT_TP:
            raise ValueError(f"ka10099 mrkt_tp 유효값 외: {mrkt_value!r} (16종)")

        # 1R L1 — wire 직전 Pydantic 검증 (sector 패턴 일관)
        request_body: dict[str, Any] = StockListRequest(mrkt_tp=mrkt_value).model_dump()

        all_rows: list[StockListRow] = []
        return_code = 0
        return_msg = ""

        async for page in self._client.call_paginated(
            api_id=self.STOCK_LIST_API_ID,
            endpoint=self.PATH,
            body=request_body,
            max_pages=self.STOCK_LIST_MAX_PAGES,
        ):
            # sector 패턴 일관 — 변수 캡처 후 except 밖 raise (`__context__` 차단)
            validation_failed = False
            parsed: StockListResponse | None = None
            try:
                parsed = StockListResponse.model_validate(page.body)
            except ValidationError:
                validation_failed = True

            if validation_failed:
                raise KiwoomResponseValidationError(f"{self.STOCK_LIST_API_ID} 응답 검증 실패")
            if parsed is None:  # pragma: no cover — validation_failed 와 mutex
                raise RuntimeError("unreachable: parsed None without validation_failed")
            all_rows.extend(parsed.items)
            return_code = parsed.return_code
            return_msg = parsed.return_msg

        return StockListResponse(
            items=all_rows,
            return_code=return_code,
            return_msg=return_msg,
        )

    async def lookup_stock(self, stk_cd: str) -> StockLookupResponse:
        """ka10100 — 단건 종목 조회. ka10099 의 gap-filler.

        스코프:
        - 신규 상장 즉시 보강 (ka10099 일 1회 cron 사이의 gap)
        - 다른 endpoint 응답에 등장한 미지 종목 lazy fetch (ensure_exists 진입점)
        - 운영 디버깅 / 단건 정확도 검증

        Pre-validation:
        - stk_cd 6자리 숫자 강제 — `_NX`/`_AL` suffix 거부 (Excel R22 Length=6).
          호출 자체 차단 — 키움 응답을 받기 전에 ValueError.

        트랜스포트 정책:
        - `KiwoomClient.call` 이 return_code != 0 → KiwoomBusinessError 자동 raise
        - 401/403/429/5xx/네트워크 도메인 매핑도 트랜스포트 책임
        - 본 메서드는 stk_cd 검증 + Pydantic 응답 파싱만 책임

        Raises:
            ValueError: stk_cd 가 6자리 숫자 외.
            KiwoomCredentialRejectedError: 401/403.
            KiwoomBusinessError: 응답 return_code != 0 (존재하지 않는 종목 등).
            KiwoomRateLimitedError: 429 (재시도 후 최종 실패).
            KiwoomUpstreamError: 5xx · 네트워크 · 파싱 실패.
            KiwoomResponseValidationError: 응답 Pydantic 검증 실패.
        """
        _validate_stk_cd_for_lookup(stk_cd)

        # 1R L1 sector/ka10099 패턴 일관 — wire 직전 Pydantic 검증
        request_body: dict[str, Any] = StockLookupRequest(stk_cd=stk_cd).model_dump()

        result = await self._client.call(
            api_id=self.STOCK_LOOKUP_API_ID,
            endpoint=self.PATH,
            body=request_body,
        )

        # sector/ka10099 패턴 일관 — 변수 캡처 후 except 밖 raise (`__context__` 차단)
        validation_failed = False
        parsed: StockLookupResponse | None = None
        try:
            parsed = StockLookupResponse.model_validate(result.body)
        except ValidationError:
            validation_failed = True

        if validation_failed:
            raise KiwoomResponseValidationError(f"{self.STOCK_LOOKUP_API_ID} 응답 검증 실패")
        if parsed is None:  # pragma: no cover — validation_failed 와 mutex
            raise RuntimeError("unreachable: parsed None without validation_failed")
        return parsed

    async def fetch_basic_info(self, stock_code: str) -> StockBasicInfoResponse:
        """ka10001 — 단건 종목 기본 정보 (펀더멘털 + 일중 시세 + 250일 통계).

        Phase B-γ-1 KRX-only 결정 (계획서 § 4.3 권장 (a)):
        - `_NX`/`_AL` suffix 미지원 — 6자리 ASCII 숫자만 (`STK_CD_LOOKUP_PATTERN`).
        - NXT 시세 분리 호출은 Phase C 의 ka10086 에 위임.
        - NXT/SOR 추가는 Phase C 후 결정 — 그때 시그니처에 `exchange` 인자 추가.

        Pre-validation:
        - stk_cd 6자리 숫자 강제 — ka10100 의 `_validate_stk_cd_for_lookup` 재사용.
          호출 자체 차단 (키움 응답 받기 전 ValueError).

        트랜스포트 정책 (ka10100 패턴 일관):
        - `KiwoomClient.call` 이 return_code != 0 → KiwoomBusinessError 자동 raise.
        - 401/403/429/5xx/네트워크 도메인 매핑도 트랜스포트 책임.
        - 본 메서드는 stk_cd 검증 + Pydantic 응답 파싱만 책임.

        Raises:
            ValueError: stk_cd 가 6자리 숫자 외.
            KiwoomCredentialRejectedError: 401/403.
            KiwoomBusinessError: 응답 return_code != 0 (존재하지 않는 종목 등).
            KiwoomRateLimitedError: 429 (재시도 후 최종 실패).
            KiwoomUpstreamError: 5xx · 네트워크 · 파싱 실패.
            KiwoomResponseValidationError: 응답 Pydantic 검증 실패.
        """
        _validate_stk_cd_for_lookup(stock_code)

        # 1R L1 sector/ka10099/ka10100 패턴 일관 — wire 직전 Pydantic 검증
        request_body: dict[str, Any] = StockBasicInfoRequest(stk_cd=stock_code).model_dump()

        result = await self._client.call(
            api_id=self.STOCK_BASIC_INFO_API_ID,
            endpoint=self.PATH,
            body=request_body,
        )

        # flag-then-raise-outside-except (B-β 1R 2b-H2 패턴 일관) — Pydantic
        # ValidationError 가 KiwoomResponseValidationError 의 __context__/__cause__
        # 에 박히지 않도록 except 밖에서 raise.
        validation_failed = False
        parsed: StockBasicInfoResponse | None = None
        try:
            parsed = StockBasicInfoResponse.model_validate(result.body)
        except ValidationError:
            validation_failed = True

        if validation_failed:
            raise KiwoomResponseValidationError(f"{self.STOCK_BASIC_INFO_API_ID} 응답 검증 실패")
        if parsed is None:  # pragma: no cover — validation_failed 와 mutex
            raise RuntimeError("unreachable: parsed None without validation_failed")
        return parsed
