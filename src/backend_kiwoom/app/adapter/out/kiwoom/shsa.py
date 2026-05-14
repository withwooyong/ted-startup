"""KiwoomShortSellingClient — `/api/dostk/shsa` 카테고리 어댑터 (Phase E).

설계: endpoint-15-ka10014.md § 6.1 + § 12.

범위 (Phase E 첫 endpoint): ka10014 (공매도추이요청) — 매도 측 시그널 raw source.
후속 공매도 endpoint 가 들어오면 같은 클래스에 메서드 추가.

책임:
- KiwoomClient 위임 — 토큰 / 재시도 / rate-limit / cont-yn 페이지네이션
- stock_code 6자리 숫자 사전 검증 — `_NX`/`_AL` suffix 입력 거부
- exchange 별 stk_cd suffix 합성 (KRX/NXT — stkinfo.build_stk_cd)
- ka10014 응답 row 파싱 (Pydantic) — KiwoomBusinessError 매핑
- 페이지네이션 결과 합치기

`_records.py` (Agent Z 담당) 에서 `ShortSellingRow` / `ShortSellingResponse` /
`NormalizedShortSelling` / `ShortSellingTimeType` 를 정의. 본 모듈은 import 만.

D-1 chart.py 의 fetch_sector_daily / C-1α fetch_daily 패턴 1:1 응용. 단, ka10014 는
응답 stk_cd 메아리 필드 없음 → cross-stock pollution 검증 skip (응답 root 에 stk_cd 없음).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import ValidationError

from app.adapter.out.kiwoom._client import KiwoomClient
from app.adapter.out.kiwoom._exceptions import (
    KiwoomBusinessError,
    KiwoomResponseValidationError,
)
from app.adapter.out.kiwoom._records import (
    ShortSellingResponse,
    ShortSellingRow,
    ShortSellingTimeType,
)
from app.adapter.out.kiwoom.stkinfo import SentinelStockCodeError, build_stk_cd
from app.application.constants import ExchangeType


class KiwoomShortSellingClient:
    """`/api/dostk/shsa` 어댑터 — ka10014 (공매도추이요청).

    Phase E. 후속 공매도 endpoint (잔고 스냅샷 등) 가 들어오면 같은 클래스에 메서드 추가.
    """

    PATH = "/api/dostk/shsa"
    SHORT_TREND_API_ID = "ka10014"
    # 1주 윈도 = ~5 거래일 < 1 페이지. 백필 (3년) 도 ka10081 와 달리 1 호출당 짧은 윈도라
    # 1 페이지 가정. 안전 마진 5 cap (plan § 6.1).
    SHORT_TREND_MAX_PAGES = 5

    def __init__(self, kiwoom_client: KiwoomClient) -> None:
        self._client = kiwoom_client

    async def fetch_trend(
        self,
        stock_code: str,
        *,
        start_date: date,
        end_date: date,
        tm_tp: ShortSellingTimeType = ShortSellingTimeType.PERIOD,
        exchange: ExchangeType = ExchangeType.KRX,
        max_pages: int | None = None,
    ) -> list[ShortSellingRow]:
        """단일 종목·단일 거래소의 공매도 추이.

        Parameters:
            stock_code: 6자리 ASCII 숫자 base code (`_NX`/`_AL` suffix 거부).
            start_date: 조회 시작일 (포함).
            end_date: 조회 종료일 (포함).
            tm_tp: 시간구분 — PERIOD (default, "1") / START_ONLY ("0"). 의미는 운영 검증
                후 확정 (plan § 11.2 / § 12.2 결정 #4 — 디폴트 PERIOD).
            exchange: KRX (default) / NXT. NXT 공매도 미지원 가능성 → 빈 응답 정상 처리
                (plan § 12.2 결정 #9).
            max_pages: cont-yn=Y 무한 루프 방어 cap. None 이면 SHORT_TREND_MAX_PAGES (5).

        Raises:
            SentinelStockCodeError: stock_code 가 6자리 ASCII 숫자 외 (ValueError 상속).
            KiwoomCredentialRejectedError: 401/403.
            KiwoomBusinessError: 응답 return_code != 0.
            KiwoomRateLimitedError: 429 재시도 후 최종 실패.
            KiwoomUpstreamError: 5xx · 네트워크 · 파싱 실패.
            KiwoomResponseValidationError: Pydantic 검증 실패.
            KiwoomMaxPagesExceededError: max_pages 도달 (plan § 8).
        """
        # 사전 검증 — 6자리 숫자만 허용 (호출 차단). `_NX`/`_AL` suffix 입력 거부.
        # build_stk_cd 가 영숫자 (`A-Z` 포함) 까지 허용하므로 ka10014 는 별도 좁은 검증.
        if not (len(stock_code) == 6 and stock_code.isdigit()):
            # Phase F-2: SentinelStockCodeError(ValueError) 로 변경 — service layer 가
            # 별도 catch 하여 total_skipped 분리 (failed 와 의미 분리, ADR § 44.9).
            # ValueError 상속이라 기존 `except ValueError:` caller 호환 유지.
            raise SentinelStockCodeError(
                f"stock_code 6자리 숫자만 허용 — 입력={stock_code!r}"
            )

        # NXT/SOR suffix 합성 — build_stk_cd 위임 (KRX → "005930" / NXT → "005930_NX").
        stk_cd = build_stk_cd(stock_code, exchange)

        body: dict[str, Any] = {
            "stk_cd": stk_cd,
            "tm_tp": tm_tp.value,
            "strt_dt": start_date.strftime("%Y%m%d"),
            "end_dt": end_date.strftime("%Y%m%d"),
        }

        cap = max_pages if max_pages is not None else self.SHORT_TREND_MAX_PAGES
        all_rows: list[ShortSellingRow] = []

        async for page in self._client.call_paginated(
            api_id=self.SHORT_TREND_API_ID,
            endpoint=self.PATH,
            body=body,
            max_pages=cap,
        ):
            # B-β 1R 2b-H2 패턴 — flag-then-raise-outside-except (__context__ 박힘 차단)
            validation_failed = False
            parsed: ShortSellingResponse | None = None
            try:
                parsed = ShortSellingResponse.model_validate(page.body)
            except ValidationError:
                validation_failed = True

            if validation_failed:
                raise KiwoomResponseValidationError(
                    f"{self.SHORT_TREND_API_ID} 응답 검증 실패"
                )
            if parsed is None:  # pragma: no cover — validation_failed 와 mutex
                raise RuntimeError("unreachable: parsed None without validation_failed")

            if parsed.return_code != 0:
                # message 는 attacker-influenced — 비식별 메타만 (B-α/B-β M-2 패턴).
                raise KiwoomBusinessError(
                    api_id=self.SHORT_TREND_API_ID,
                    return_code=parsed.return_code,
                    message=parsed.return_msg,
                )

            all_rows.extend(parsed.shrts_trnsn)

            # 빈 응답 가드 — chart.py fetch_sector_daily 와 동일 패턴 (C-flow-empty-fix).
            # NXT 공매도 미지원 시 빈 응답 + cont-yn=Y 무한 루프 가능성 방어.
            if not parsed.shrts_trnsn:
                break

        return all_rows


__all__ = [
    "KiwoomShortSellingClient",
    "ShortSellingTimeType",
]
