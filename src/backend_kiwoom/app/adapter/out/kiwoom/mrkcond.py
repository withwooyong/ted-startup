"""KiwoomMarketCondClient — `/api/dostk/mrkcond` 계열 어댑터 (Phase C-2α).

설계: endpoint-10-ka10086.md § 6.1.

범위 (C-2α): ka10086 (일별주가요청) — 백테스팅 시그널 보강 (투자자별/외인/신용).
후속 mrkcond endpoint 는 본 클래스에 메서드 추가.

책임:
- KiwoomClient 위임 — 토큰 / 재시도 / rate-limit / cont-yn 페이지네이션
- stock_code 6자리 ASCII 사전 검증 (build_stk_cd) — `_NX`/`_AL` suffix 입력 거부
- exchange 별 stk_cd suffix 합성 (KRX/NXT/SOR)
- Pydantic 검증 + KiwoomBusinessError / KiwoomResponseValidationError 매핑
- C-1α 2R H-1 패턴 차용 — 페이지 응답 stk_cd 메아리 mismatch 차단 (cross-stock pollution)
- 페이지네이션 결과 합치기

`_to_int` / `_to_decimal` / `_parse_yyyymmdd` / `_strip_double_sign_int` 는 도메인 record
모듈 (`_records.py`) 가 책임. 본 어댑터는 transport + Pydantic 만.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

from pydantic import ValidationError

from app.adapter.out.kiwoom._client import KiwoomClient
from app.adapter.out.kiwoom._exceptions import (
    KiwoomBusinessError,
    KiwoomResponseValidationError,
)
from app.adapter.out.kiwoom._records import (
    DailyMarketResponse,
    DailyMarketRow,
)
from app.adapter.out.kiwoom.stkinfo import (
    _parse_yyyymmdd,
    build_stk_cd,
    strip_kiwoom_suffix,
)
from app.application.constants import DailyMarketDisplayMode, ExchangeType


class KiwoomMarketCondClient:
    """`/api/dostk/mrkcond` 어댑터 (C-2α — ka10086 일별 수급)."""

    PATH = "/api/dostk/mrkcond"
    DAILY_MARKET_API_ID = "ka10086"
    DAILY_MARKET_MAX_PAGES = 10  # 22 필드라 페이지 row 수 ka10081 보다 적을 가능성 (~300 거래일 추정)

    def __init__(self, kiwoom_client: KiwoomClient) -> None:
        self._client = kiwoom_client

    async def fetch_daily_market(
        self,
        stock_code: str,
        *,
        query_date: date,
        exchange: ExchangeType = ExchangeType.KRX,
        indc_mode: DailyMarketDisplayMode = DailyMarketDisplayMode.QUANTITY,
        max_pages: int | None = None,
        since_date: date | None = None,
    ) -> list[DailyMarketRow]:
        """단일 종목·단일 거래소의 일별 수급 시계열. cont-yn 자동 페이지네이션.

        Parameters:
            stock_code: 6자리 ASCII 숫자 base code (`_NX`/`_AL` suffix 거부).
            query_date: 조회일자 (이 날짜 이후 시계열 응답 — ka10081 와 같은 의미).
            exchange: KRX (디폴트) / NXT / SOR. build_stk_cd 가 suffix 합성.
            indc_mode: QUANTITY (디폴트, 수량) / AMOUNT (백만원).
            max_pages: cont-yn=Y 무한 루프 방어 cap. None 이면 DAILY_MARKET_MAX_PAGES.
            since_date: 백필 하한일 (CLI backfill 전용). 페이지의 가장 오래된 row date 가
                since_date 보다 과거 (이하) 면 다음 페이지 요청 stop. ka10081 의
                since_date guard 와 동일 의미 — qry_dt 만 받고 종료 범위 없는 endpoint
                특성으로 오래된 종목 백필 시 max_pages 초과 fail 방어. None (디폴트) 이면
                기존 동작 (운영 cron 호환).

        Raises:
            ValueError: stock_code 가 6자리 ASCII 숫자 외 (build_stk_cd 사전 검증).
            KiwoomCredentialRejectedError: 401/403.
            KiwoomBusinessError: 응답 return_code != 0 (message echo 차단).
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
            "qry_dt": query_date.strftime("%Y%m%d"),
            "indc_tp": indc_mode.value,
        }

        cap = max_pages if max_pages is not None else self.DAILY_MARKET_MAX_PAGES
        all_rows: list[DailyMarketRow] = []

        async for page in self._client.call_paginated(
            api_id=self.DAILY_MARKET_API_ID,
            endpoint=self.PATH,
            body=body,
            max_pages=cap,
        ):
            # B-β 1R 2b-H2 패턴 — flag-then-raise-outside-except (__context__ 박힘 차단)
            validation_failed = False
            parsed: DailyMarketResponse | None = None
            try:
                parsed = DailyMarketResponse.model_validate(page.body)
            except ValidationError:
                validation_failed = True

            if validation_failed:
                raise KiwoomResponseValidationError(
                    f"{self.DAILY_MARKET_API_ID} 응답 검증 실패"
                )
            if parsed is None:  # pragma: no cover — validation_failed 와 mutex
                raise RuntimeError("unreachable: parsed None without validation_failed")

            # C-1α 2R H-1 패턴 — 페이지 응답 root.stk_cd 메아리 검증 (base code 비교).
            # 빈 string 은 통과 (계획서 운영 미검증, C-1α 정책 일관). 메시지에
            # attacker-influenced 응답값 echo 금지 — 비식별 메타만.
            if parsed.stk_cd:
                response_base = strip_kiwoom_suffix(parsed.stk_cd)
                expected_base = strip_kiwoom_suffix(expected_stk_cd)
                if response_base != expected_base:
                    raise KiwoomResponseValidationError(
                        f"{self.DAILY_MARKET_API_ID} 응답 stk_cd 메아리 mismatch (요청 vs 응답)"
                    )

            if parsed.return_code != 0:
                # KiwoomClient.call_paginated 가 return_code 검증 우선 처리하지만 page 단위
                # 안전망. message 는 attacker-influenced 라 비식별 메타만 (B-α/B-β M-2).
                raise KiwoomBusinessError(
                    api_id=self.DAILY_MARKET_API_ID,
                    return_code=parsed.return_code,
                    message=parsed.return_msg,
                )

            all_rows.extend(parsed.daly_stkpc)

            # since_date guard — chart.py fetch_daily 와 동일 의미. ka10086 응답은 신→구
            # 정렬 가정 (계획서 § 6.1) — 페이지의 마지막 row 가 가장 과거. 가장 과거 row 의
            # date 가 since_date 보다 과거 (이하) 면 다음 페이지 요청 stop.
            if since_date is not None and self._page_reached_since(
                parsed.daly_stkpc, since_date
            ):
                break

        # since_date 보다 과거인 row 제거 (마지막 페이지 fragment).
        if since_date is not None:
            all_rows = [r for r in all_rows if self._row_on_or_after(r, since_date)]

        return all_rows

    @staticmethod
    def _page_reached_since(rows: Sequence[DailyMarketRow], since_date: date) -> bool:
        """페이지의 가장 오래된 row date 가 since_date 보다 과거 (이하) 면 True.

        ka10086 응답은 신→구 정렬 가정 (계획서 § 6.1) — 마지막 row 가 가장 과거.
        빈 date 는 무시. chart.py 의 _page_reached_since 와 동일 패턴.
        """
        for row in reversed(rows):
            parsed = _parse_yyyymmdd(row.date)
            if parsed is not None:
                return parsed <= since_date
        return False

    @staticmethod
    def _row_on_or_after(row: DailyMarketRow, since_date: date) -> bool:
        """row date >= since_date 면 True. 빈 date 는 keep — Repository 가 skip."""
        parsed = _parse_yyyymmdd(row.date)
        if parsed is None:
            return True
        return parsed >= since_date


__all__ = ["KiwoomMarketCondClient"]
