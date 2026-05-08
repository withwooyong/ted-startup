"""KiwoomStkInfoClient — `/api/dostk/stkinfo` 계열 어댑터.

설계: endpoint-14-ka10101.md § 6.1 + endpoint-03-ka10099.md § 6.1 + endpoint-04-ka10100.md § 6.1.

범위: ka10101 (sector 마스터, A3-α) + ka10099 (stock 마스터, B-α) + ka10100 (stock gap-filler, B-β).
ka10001 등은 Phase B 후속.

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
from typing import Annotated, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.adapter.out.kiwoom._client import KiwoomClient
from app.adapter.out.kiwoom._exceptions import KiwoomResponseValidationError
from app.application.constants import StockListMarketType

VALID_MRKT_TP: Final[tuple[str, ...]] = ("0", "1", "2", "4", "7")
"""ka10101 mrkt_tp 유효값 (master.md § 11.3 - 다른 endpoint 와 의미 다름).

0: 코스피(거래소) / 1: 코스닥 / 2: KOSPI200 / 4: KOSPI100 / 7: KRX100
"""


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
"""ka10100 stk_cd 정규식 — Excel R22 Length=6, ASCII 0-9 only.

`_NX`/`_AL` suffix 거부 + unicode digit 거부 (`\\d` 가 unicode digit 매칭하는 점
방어, 1R 2b L2). 어댑터 검증 / Pydantic Request / 라우터 Path pattern 세 곳이
모두 본 상수 참조 — 단일 source of truth.
"""

_STK_CD_LOOKUP_RE = re.compile(STK_CD_LOOKUP_PATTERN)


def _validate_stk_cd_for_lookup(stk_cd: str) -> None:
    """ka10100 stk_cd 사전 검증 — 6자리 ASCII 숫자만. 호출 자체 차단.

    Excel R22 Length=6 — 다른 차트 endpoint 의 `_NX`/`_AL` suffix(Length=20) 와 다름.
    빈 문자열·공백·영문·unicode digit 모두 거부.
    """
    if not _STK_CD_LOOKUP_RE.fullmatch(stk_cd):
        raise ValueError(f"ka10100 stk_cd 는 6자리 ASCII 숫자만 허용: {stk_cd!r}")


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


class KiwoomStkInfoClient:
    """`/api/dostk/stkinfo` 어댑터. KiwoomClient 위임."""

    API_ID = "ka10101"
    PATH = "/api/dostk/stkinfo"

    # ka10099 전용 메타
    STOCK_LIST_API_ID = "ka10099"
    STOCK_LIST_MAX_PAGES = 100  # KOSPI ~900~1000 / KOSDAQ ~1500~1700 추정 — 페이지네이션 빈도 높음

    # ka10100 전용 메타 (B-β)
    STOCK_LOOKUP_API_ID = "ka10100"

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
