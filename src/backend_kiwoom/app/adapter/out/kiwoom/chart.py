"""KiwoomChartClient — `/api/dostk/chart` 계열 어댑터 (Phase C-1α).

설계: endpoint-06-ka10081.md § 6.1.

범위 (C-1α): ka10081 (주식일봉차트) — 백테스팅 코어. 후속 ka10082/83/94 (주봉/월봉/년봉)
는 같은 endpoint path 공유, 본 클래스에 메서드 추가 예정 (Phase C-1β/γ).

책임:
- KiwoomClient 위임 — 토큰 / 재시도 / rate-limit / cont-yn 페이지네이션
- stock_code 6자리 영숫자 대문자 사전 검증 (build_stk_cd / STK_CD_CHART_PATTERN, ADR § 32)
  — `_NX`/`_AL` suffix 입력 거부, 우선주 (`*K`) 등 영숫자 종목 허용
- exchange 별 stk_cd suffix 합성 (KRX/NXT/SOR)
- 응답 row 파싱 (Pydantic) — KiwoomBusinessError / KiwoomResponseValidationError 매핑
- 페이지네이션 결과 합치기

`_to_int` / `_to_decimal` / `_parse_yyyymmdd` 는 `stkinfo.py` 의 helper 재사용 — B-γ-1
2R A-C1/A-C2/A-H4 가드 (BIGINT/NaN/Infinity) 자동 적용.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.adapter.out.kiwoom._client import KiwoomClient
from app.adapter.out.kiwoom._exceptions import (
    KiwoomBusinessError,
    KiwoomResponseValidationError,
)
from app.adapter.out.kiwoom.stkinfo import (
    _parse_yyyymmdd,
    _to_decimal,
    _to_int,
    build_stk_cd,
    strip_kiwoom_suffix,
)
from app.application.constants import ExchangeType


class DailyChartRow(BaseModel):
    """ka10081 응답 row — 키움 응답 그대로 (string + 부호 포함).

    B-γ-1 2R A-H1 패턴 — 모든 string 필드 max_length 강제 (DB 컬럼 sync, vendor 거대
    string DataError 차단).
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    cur_prc: Annotated[str, Field(max_length=32)] = ""
    trde_qty: Annotated[str, Field(max_length=32)] = ""
    trde_prica: Annotated[str, Field(max_length=32)] = ""
    dt: Annotated[str, Field(max_length=8)] = ""
    open_pric: Annotated[str, Field(max_length=32)] = ""
    high_pric: Annotated[str, Field(max_length=32)] = ""
    low_pric: Annotated[str, Field(max_length=32)] = ""
    pred_pre: Annotated[str, Field(max_length=32)] = ""
    pred_pre_sig: Annotated[str, Field(max_length=1)] = ""
    trde_tern_rt: Annotated[str, Field(max_length=32)] = ""

    def to_normalized(
        self,
        *,
        stock_id: int,
        exchange: ExchangeType,
        adjusted: bool,
    ) -> NormalizedDailyOhlcv:
        """ka10081 row → NormalizedDailyOhlcv.

        빈 dt → trading_date=date.min. caller (Repository.upsert_many) 가 skip.
        `_to_int` BIGINT 가드 / `_to_decimal` is_finite 가드 자동 적용 (B-γ-1).
        """
        return NormalizedDailyOhlcv(
            stock_id=stock_id,
            trading_date=_parse_yyyymmdd(self.dt) or date.min,
            exchange=exchange,
            adjusted=adjusted,
            open_price=_to_int(self.open_pric),
            high_price=_to_int(self.high_pric),
            low_price=_to_int(self.low_pric),
            close_price=_to_int(self.cur_prc),
            trade_volume=_to_int(self.trde_qty),
            trade_amount=_to_int(self.trde_prica),
            prev_compare_amount=_to_int(self.pred_pre),
            prev_compare_sign=self.pred_pre_sig or None,
            turnover_rate=_to_decimal(self.trde_tern_rt),
        )


class DailyChartResponse(BaseModel):
    """ka10081 응답 — `stk_cd` 메아리 + `stk_dt_pole_chart_qry` list."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    stk_cd: Annotated[str, Field(max_length=20)] = ""
    stk_dt_pole_chart_qry: list[DailyChartRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: Annotated[str, Field(max_length=200)] = ""


class WeeklyChartRow(DailyChartRow):
    """ka10082 응답 row — DailyChartRow 와 필드 동일 (C-3α).

    설계: endpoint-07-ka10082.md § 3.3.

    `to_normalized` 부모 메서드 그대로 재사용 (NormalizedDailyOhlcv 반환). period 정보는
    Repository 가 분기.

    `dt` 의미: 주의 첫 거래일 (가설 — 운영 first-call 후 확정).
    영속화 시 trading_date = dt 그대로.
    """


class WeeklyChartResponse(BaseModel):
    """ka10082 응답 — `stk_stk_pole_chart_qry` list 키 (ka10081 와 다름)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    stk_cd: Annotated[str, Field(max_length=20)] = ""
    stk_stk_pole_chart_qry: list[WeeklyChartRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: Annotated[str, Field(max_length=200)] = ""


class MonthlyChartRow(DailyChartRow):
    """ka10083 응답 row — DailyChartRow 와 필드 동일 (C-3α).

    설계: endpoint-08-ka10083.md § 3.3.

    `dt` 의미: 달의 첫 거래일 (가설 — 운영 first-call 후 확정).
    """


class MonthlyChartResponse(BaseModel):
    """ka10083 응답 — `stk_mth_pole_chart_qry` list 키."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    stk_cd: Annotated[str, Field(max_length=20)] = ""
    stk_mth_pole_chart_qry: list[MonthlyChartRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: Annotated[str, Field(max_length=200)] = ""


class YearlyChartRow(BaseModel):
    """ka10094 응답 row — 7 필드만 (DailyChartRow 와 다름, C-4).

    설계: endpoint-09-ka10094.md § 3.2.

    DailyChartRow 의 10 필드 중 `pred_pre` / `pred_pre_sig` / `trde_tern_rt` 없음.
    `to_normalized` 에선 prev_compare_amount / prev_compare_sign / turnover_rate = None 으로
    영속화 (NormalizedDailyOhlcv 의 모든 필드 Optional).

    extra="ignore" — vendor 가 운영에서 누락 필드 추가 시 silent 무시 (plan § 12.4 H-3).

    `dt` 의미: 해의 첫 거래일 (가설 — 운영 first-call 후 확정).
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    cur_prc: Annotated[str, Field(max_length=32)] = ""
    trde_qty: Annotated[str, Field(max_length=32)] = ""
    trde_prica: Annotated[str, Field(max_length=32)] = ""
    dt: Annotated[str, Field(max_length=8)] = ""
    open_pric: Annotated[str, Field(max_length=32)] = ""
    high_pric: Annotated[str, Field(max_length=32)] = ""
    low_pric: Annotated[str, Field(max_length=32)] = ""

    def to_normalized(
        self,
        *,
        stock_id: int,
        exchange: ExchangeType,
        adjusted: bool,
    ) -> NormalizedDailyOhlcv:
        """ka10094 row → NormalizedDailyOhlcv.

        7 필드만 → prev_compare_* / turnover_rate = None (NULL 영속).
        빈 dt → trading_date=date.min. caller (Repository.upsert_many) 가 skip.
        """
        return NormalizedDailyOhlcv(
            stock_id=stock_id,
            trading_date=_parse_yyyymmdd(self.dt) or date.min,
            exchange=exchange,
            adjusted=adjusted,
            open_price=_to_int(self.open_pric),
            high_price=_to_int(self.high_pric),
            low_price=_to_int(self.low_pric),
            close_price=_to_int(self.cur_prc),
            trade_volume=_to_int(self.trde_qty),
            trade_amount=_to_int(self.trde_prica),
            prev_compare_amount=None,
            prev_compare_sign=None,
            turnover_rate=None,
        )


class YearlyChartResponse(BaseModel):
    """ka10094 응답 — `stk_yr_pole_chart_qry` list 키."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    stk_cd: Annotated[str, Field(max_length=20)] = ""
    stk_yr_pole_chart_qry: list[YearlyChartRow] = Field(default_factory=list)
    return_code: int = 0
    return_msg: Annotated[str, Field(max_length=200)] = ""


@dataclass(frozen=True, slots=True)
class NormalizedDailyOhlcv:
    """ka10081 정규화 도메인 — Repository 가 보는 형태.

    `trading_date == date.min` 은 빈 응답 row 표식 — caller (Repository.upsert_many) 가
    영속화 직전 skip.
    """

    stock_id: int
    trading_date: date
    exchange: ExchangeType
    adjusted: bool
    open_price: int | None
    high_price: int | None
    low_price: int | None
    close_price: int | None
    trade_volume: int | None
    trade_amount: int | None
    prev_compare_amount: int | None
    prev_compare_sign: str | None
    turnover_rate: Decimal | None


class KiwoomChartClient:
    """`/api/dostk/chart` 어댑터 — ka10081 (일봉) + ka10082 (주봉) + ka10083 (월봉)."""

    PATH = "/api/dostk/chart"
    DAILY_API_ID = "ka10081"
    DAILY_MAX_PAGES = 10  # 키움 일봉 1 페이지 ~600 거래일 추정. 3년 백필 = 2 페이지 + 여유

    # C-3α — 주/월봉 (백필 시 페이지 수 적음. 3년 = 156 주 / 36 월. 1 페이지면 충분 + 여유)
    WEEKLY_API_ID = "ka10082"
    WEEKLY_MAX_PAGES = 3
    MONTHLY_API_ID = "ka10083"
    MONTHLY_MAX_PAGES = 2
    YEARLY_API_ID = "ka10094"
    # 년봉은 30년 백필도 1 페이지 가정 (plan § 11.3 / 12.4 H-7). 안전 마진으로 2 cap.
    YEARLY_MAX_PAGES = 2

    def __init__(self, kiwoom_client: KiwoomClient) -> None:
        self._client = kiwoom_client

    async def fetch_daily(
        self,
        stock_code: str,
        *,
        base_date: date,
        exchange: ExchangeType = ExchangeType.KRX,
        adjusted: bool = True,
        max_pages: int | None = None,
        since_date: date | None = None,
    ) -> list[DailyChartRow]:
        """단일 종목·단일 거래소의 일봉 시계열. cont-yn 자동 페이지네이션.

        Parameters:
            stock_code: 6자리 ASCII 숫자 base code (`_NX`/`_AL` suffix 거부).
            base_date: 기준일자 (이 날짜를 포함한 과거 시계열 응답).
            exchange: KRX (디폴트) / NXT / SOR. build_stk_cd 가 suffix 합성.
            adjusted: True 면 수정주가 (백테스팅 디폴트). False 는 raw 비교 검증용.
            max_pages: cont-yn=Y 무한 루프 방어 cap. None 이면 DAILY_MAX_PAGES.
            since_date: 백필 하한일. 페이지의 가장 오래된 row 가 since_date 보다 과거면
                다음 페이지 요청 중단. 운영 차단 fix — ka10081 은 base_dt 만 받고 종료
                범위가 없어, 오래된 종목 (1980년대 상장) 은 max_pages 도달로 fail. None
                (디폴트) 면 기존 동작 (운영 cron 호환).

        Raises:
            ValueError: stock_code 가 6자리 ASCII 숫자 외 (build_stk_cd 사전 검증).
                SOR 은 호출 가능 — 영속화는 Phase D 결정 (Repository 단계 거부).
            KiwoomCredentialRejectedError: 401/403.
            KiwoomBusinessError: 응답 return_code != 0.
            KiwoomRateLimitedError: 429 재시도 후 최종 실패.
            KiwoomUpstreamError: 5xx · 네트워크 · 파싱 실패.
            KiwoomResponseValidationError: Pydantic 검증 실패 또는 stk_cd 메아리 mismatch
                (C-1α 2R H-1 cross-stock pollution 차단).
            KiwoomMaxPagesExceededError: max_pages 도달.
        """
        # build_stk_cd 가 stock_code 사전 검증 + suffix 합성 (raise 시 호출 차단)
        expected_stk_cd = build_stk_cd(stock_code, exchange)

        body: dict[str, Any] = {
            "stk_cd": expected_stk_cd,
            "base_dt": base_date.strftime("%Y%m%d"),
            "upd_stkpc_tp": "1" if adjusted else "0",
        }

        cap = max_pages if max_pages is not None else self.DAILY_MAX_PAGES
        all_rows: list[DailyChartRow] = []

        async for page in self._client.call_paginated(
            api_id=self.DAILY_API_ID,
            endpoint=self.PATH,
            body=body,
            max_pages=cap,
        ):
            # B-β 1R 2b-H2 패턴 — flag-then-raise-outside-except (__context__ 박힘 차단)
            validation_failed = False
            parsed: DailyChartResponse | None = None
            try:
                parsed = DailyChartResponse.model_validate(page.body)
            except ValidationError:
                validation_failed = True

            if validation_failed:
                raise KiwoomResponseValidationError(f"{self.DAILY_API_ID} 응답 검증 실패")
            if parsed is None:  # pragma: no cover — validation_failed 와 mutex
                raise RuntimeError("unreachable: parsed None without validation_failed")

            # C-1α 2R H-1 — 페이지 응답의 root.stk_cd 메아리 검증 (base code 비교).
            # 키움 백엔드 버그 / proxy 캐시 / MITM 으로 page N 의 stk_cd 가 다른 종목으로 박혀
            # 오면 silent merge → cross-stock pollution.
            #
            # base code 비교 정책 (계획서 § 4.3 — 운영 미검증):
            # - 응답 stk_cd 가 `005930_NX` (suffix 동봉) → base `005930`
            # - 응답 stk_cd 가 `005930` (suffix stripped) → base `005930`
            # - 둘 다 expected base 와 일치하면 통과. base 가 다르면 cross-stock 으로 raise.
            # 빈 string 은 응답 미동봉 (운영 검증 후 strict 전환 검토).
            # 메시지에 attacker-influenced 응답값 echo 금지 — 비식별 메타만.
            if parsed.stk_cd:
                response_base = strip_kiwoom_suffix(parsed.stk_cd)
                expected_base = strip_kiwoom_suffix(expected_stk_cd)
                if response_base != expected_base:
                    raise KiwoomResponseValidationError(
                        f"{self.DAILY_API_ID} 응답 stk_cd 메아리 mismatch (요청 vs 응답)"
                    )

            if parsed.return_code != 0:
                # KiwoomClient.call_paginated 가 보통 return_code 검증을 처리하지만 page 단위
                # 검증 안전망. message 는 attacker-influenced 라 비식별 메타만 (B-α/B-β M-2).
                raise KiwoomBusinessError(
                    api_id=self.DAILY_API_ID,
                    return_code=parsed.return_code,
                    message=parsed.return_msg,
                )

            all_rows.extend(parsed.stk_dt_pole_chart_qry)

            # 빈 응답 가드 — 키움 서버가 NXT 출범 이전 base_dt 등 sentinel 패턴에서
            # resp-cnt=0 + cont-yn=Y 무한 루프 가능 (mrkcond ka10086 010950 reproduce
            # 검증, 2026-05-11). ka10081 page row 수 ~600 이라 현재 fail 없지만 잠재
            # 위험 (저거래 종목 / 장기 휴장) 방어. since_date guard 와 별도.
            if not parsed.stk_dt_pole_chart_qry:
                break

            # since_date guard — 페이지의 가장 오래된 row date 가 since_date 보다 과거면
            # 다음 페이지 요청 stop. ka10081 응답은 신→구 정렬 (next-key 가 점점 과거).
            # 운영 검증: base_dt 만 보내면 종목 상장일까지 무한 페이징 → max_pages 초과 fail.
            if since_date is not None and self._page_reached_since(
                parsed.stk_dt_pole_chart_qry, since_date
            ):
                break

        # since_date 보다 과거인 row 제거 (마지막 페이지 fragment).
        if since_date is not None:
            all_rows = [r for r in all_rows if self._row_on_or_after(r, since_date)]

        return all_rows

    @staticmethod
    def _page_reached_since(rows: Sequence[DailyChartRow | YearlyChartRow], since_date: date) -> bool:
        """페이지의 가장 오래된 row date 가 since_date 보다 과거 (이하) 면 True.

        ka10081/82/83/94 응답은 신→구 정렬 가정 — 마지막 row 가 가장 과거. 빈 dt 는 무시.
        Weekly/MonthlyChartRow 는 DailyChartRow subclass — Sequence (covariant) 로 호환.
        YearlyChartRow 는 별도 정의 (7 필드) — `dt` attribute 동일하므로 union 으로 cover.
        """
        for row in reversed(rows):
            parsed = _parse_yyyymmdd(row.dt)
            if parsed is not None:
                return parsed <= since_date
        return False

    @staticmethod
    def _row_on_or_after(row: DailyChartRow | YearlyChartRow, since_date: date) -> bool:
        """row date >= since_date 면 True. 빈 dt (date.min) 는 keep — Repository 가 skip."""
        parsed = _parse_yyyymmdd(row.dt)
        if parsed is None:
            return True
        return parsed >= since_date

    async def fetch_weekly(
        self,
        stock_code: str,
        *,
        base_date: date,
        exchange: ExchangeType = ExchangeType.KRX,
        adjusted: bool = True,
        max_pages: int | None = None,
        since_date: date | None = None,
    ) -> list[WeeklyChartRow]:
        """ka10082 주봉 OHLCV — fetch_daily 패턴 복제. list 키 + api_id 만 다름.

        Parameters / Raises 는 fetch_daily 와 동일 (api_id="ka10082", list 키
        `stk_stk_pole_chart_qry`). `since_date` 도 fetch_daily 와 동일 의미.

        `dt` 의미는 주의 첫 거래일 (가설 — 운영 first-call 후 확정).
        """
        expected_stk_cd = build_stk_cd(stock_code, exchange)

        body: dict[str, Any] = {
            "stk_cd": expected_stk_cd,
            "base_dt": base_date.strftime("%Y%m%d"),
            "upd_stkpc_tp": "1" if adjusted else "0",
        }

        cap = max_pages if max_pages is not None else self.WEEKLY_MAX_PAGES
        all_rows: list[WeeklyChartRow] = []

        async for page in self._client.call_paginated(
            api_id=self.WEEKLY_API_ID,
            endpoint=self.PATH,
            body=body,
            max_pages=cap,
        ):
            validation_failed = False
            parsed: WeeklyChartResponse | None = None
            try:
                parsed = WeeklyChartResponse.model_validate(page.body)
            except ValidationError:
                validation_failed = True

            if validation_failed:
                raise KiwoomResponseValidationError(f"{self.WEEKLY_API_ID} 응답 검증 실패")
            if parsed is None:  # pragma: no cover — validation_failed 와 mutex
                raise RuntimeError("unreachable: parsed None without validation_failed")

            if parsed.stk_cd:
                response_base = strip_kiwoom_suffix(parsed.stk_cd)
                expected_base = strip_kiwoom_suffix(expected_stk_cd)
                if response_base != expected_base:
                    raise KiwoomResponseValidationError(
                        f"{self.WEEKLY_API_ID} 응답 stk_cd 메아리 mismatch (요청 vs 응답)"
                    )

            if parsed.return_code != 0:
                raise KiwoomBusinessError(
                    api_id=self.WEEKLY_API_ID,
                    return_code=parsed.return_code,
                    message=parsed.return_msg,
                )

            all_rows.extend(parsed.stk_stk_pole_chart_qry)

            # 빈 응답 가드 (fetch_daily 와 동일 — sentinel 무한 루프 방어).
            if not parsed.stk_stk_pole_chart_qry:
                break

            if since_date is not None and self._page_reached_since(
                parsed.stk_stk_pole_chart_qry, since_date
            ):
                break

        if since_date is not None:
            all_rows = [r for r in all_rows if self._row_on_or_after(r, since_date)]

        return all_rows

    async def fetch_monthly(
        self,
        stock_code: str,
        *,
        base_date: date,
        exchange: ExchangeType = ExchangeType.KRX,
        adjusted: bool = True,
        max_pages: int | None = None,
        since_date: date | None = None,
    ) -> list[MonthlyChartRow]:
        """ka10083 월봉 OHLCV — fetch_daily 패턴 복제. list 키 + api_id 만 다름.

        Parameters / Raises 는 fetch_daily 와 동일 (api_id="ka10083", list 키
        `stk_mth_pole_chart_qry`). `since_date` 도 fetch_daily 와 동일 의미.

        `dt` 의미는 달의 첫 거래일 (가설 — 운영 first-call 후 확정).
        """
        expected_stk_cd = build_stk_cd(stock_code, exchange)

        body: dict[str, Any] = {
            "stk_cd": expected_stk_cd,
            "base_dt": base_date.strftime("%Y%m%d"),
            "upd_stkpc_tp": "1" if adjusted else "0",
        }

        cap = max_pages if max_pages is not None else self.MONTHLY_MAX_PAGES
        all_rows: list[MonthlyChartRow] = []

        async for page in self._client.call_paginated(
            api_id=self.MONTHLY_API_ID,
            endpoint=self.PATH,
            body=body,
            max_pages=cap,
        ):
            validation_failed = False
            parsed: MonthlyChartResponse | None = None
            try:
                parsed = MonthlyChartResponse.model_validate(page.body)
            except ValidationError:
                validation_failed = True

            if validation_failed:
                raise KiwoomResponseValidationError(f"{self.MONTHLY_API_ID} 응답 검증 실패")
            if parsed is None:  # pragma: no cover — validation_failed 와 mutex
                raise RuntimeError("unreachable: parsed None without validation_failed")

            if parsed.stk_cd:
                response_base = strip_kiwoom_suffix(parsed.stk_cd)
                expected_base = strip_kiwoom_suffix(expected_stk_cd)
                if response_base != expected_base:
                    raise KiwoomResponseValidationError(
                        f"{self.MONTHLY_API_ID} 응답 stk_cd 메아리 mismatch (요청 vs 응답)"
                    )

            if parsed.return_code != 0:
                raise KiwoomBusinessError(
                    api_id=self.MONTHLY_API_ID,
                    return_code=parsed.return_code,
                    message=parsed.return_msg,
                )

            all_rows.extend(parsed.stk_mth_pole_chart_qry)

            # 빈 응답 가드 (fetch_daily 와 동일 — sentinel 무한 루프 방어).
            if not parsed.stk_mth_pole_chart_qry:
                break

            if since_date is not None and self._page_reached_since(
                parsed.stk_mth_pole_chart_qry, since_date
            ):
                break

        if since_date is not None:
            all_rows = [r for r in all_rows if self._row_on_or_after(r, since_date)]

        return all_rows

    async def fetch_yearly(
        self,
        stock_code: str,
        *,
        base_date: date,
        exchange: ExchangeType = ExchangeType.KRX,
        adjusted: bool = True,
        max_pages: int | None = None,
        since_date: date | None = None,
    ) -> list[YearlyChartRow]:
        """ka10094 년봉 OHLCV — fetch_weekly/monthly 패턴 복제. list 키 + api_id 만 다름.

        Parameters / Raises 는 fetch_weekly 와 동일 (api_id="ka10094", list 키
        `stk_yr_pole_chart_qry`). NXT skip 정책은 UseCase 가드에서 처리 — 본 메서드는
        호출되지 않거나 KRX 만 호출됨.

        `dt` 의미는 해의 첫 거래일 (가설 — 운영 first-call 후 확정).
        응답 7 필드만 (pred_pre/pred_pre_sig/trde_tern_rt 없음) — to_normalized 에서 NULL 영속.
        """
        expected_stk_cd = build_stk_cd(stock_code, exchange)

        body: dict[str, Any] = {
            "stk_cd": expected_stk_cd,
            "base_dt": base_date.strftime("%Y%m%d"),
            "upd_stkpc_tp": "1" if adjusted else "0",
        }

        cap = max_pages if max_pages is not None else self.YEARLY_MAX_PAGES
        all_rows: list[YearlyChartRow] = []

        async for page in self._client.call_paginated(
            api_id=self.YEARLY_API_ID,
            endpoint=self.PATH,
            body=body,
            max_pages=cap,
        ):
            validation_failed = False
            parsed: YearlyChartResponse | None = None
            try:
                parsed = YearlyChartResponse.model_validate(page.body)
            except ValidationError:
                validation_failed = True

            if validation_failed:
                raise KiwoomResponseValidationError(f"{self.YEARLY_API_ID} 응답 검증 실패")
            if parsed is None:  # pragma: no cover — validation_failed 와 mutex
                raise RuntimeError("unreachable: parsed None without validation_failed")

            if parsed.stk_cd:
                response_base = strip_kiwoom_suffix(parsed.stk_cd)
                expected_base = strip_kiwoom_suffix(expected_stk_cd)
                if response_base != expected_base:
                    raise KiwoomResponseValidationError(
                        f"{self.YEARLY_API_ID} 응답 stk_cd 메아리 mismatch (요청 vs 응답)"
                    )

            if parsed.return_code != 0:
                raise KiwoomBusinessError(
                    api_id=self.YEARLY_API_ID,
                    return_code=parsed.return_code,
                    message=parsed.return_msg,
                )

            all_rows.extend(parsed.stk_yr_pole_chart_qry)

            # 빈 응답 가드 (fetch_daily/weekly/monthly 와 동일 — sentinel 무한 루프 방어, C-flow-empty-fix).
            if not parsed.stk_yr_pole_chart_qry:
                break

            if since_date is not None and self._page_reached_since(
                parsed.stk_yr_pole_chart_qry, since_date
            ):
                break

        if since_date is not None:
            all_rows = [r for r in all_rows if self._row_on_or_after(r, since_date)]

        return all_rows


__all__ = [
    "DailyChartResponse",
    "DailyChartRow",
    "KiwoomChartClient",
    "MonthlyChartResponse",
    "MonthlyChartRow",
    "NormalizedDailyOhlcv",
    "WeeklyChartResponse",
    "WeeklyChartRow",
    "YearlyChartResponse",
    "YearlyChartRow",
]
