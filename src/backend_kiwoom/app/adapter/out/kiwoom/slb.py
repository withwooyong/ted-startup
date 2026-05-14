"""KiwoomLendingClient — `/api/dostk/slb` 어댑터 (ka10068 + ka20068, Phase E).

설계: endpoint-16-ka10068.md § 6.1 + endpoint-17-ka20068.md § 6.1 + endpoint-15-ka10014.md § 12.

범위:
- ka10068 (대차거래추이 시장 단위) — `fetch_market_trend` / `all_tp="1"` / stk_cd 없음.
- ka20068 (대차거래추이 종목별) — `fetch_stock_trend` / `all_tp="0"` / `stk_cd` 6자리 KRX only.

특징 (plan § 12.2):
- #4 NXT 정책 — ka10068=미적용 (시장 단위, mrkt_tp 없음) / ka20068=KRX only (Length=6 명세).
  ka20068 는 `005930_NX` 같은 NXT suffix 거부 — UseCase 도 NXT 시도 안 함.
- KiwoomBusinessError 매핑 — return_code != 0 → bubble up (UseCase 가 outcome.error 격리).
- KiwoomMaxPagesExceededError — cont-yn=Y 무한 응답 방어 (KiwoomClient.call_paginated).

`KiwoomChartClient.fetch_sector_daily` (D-1) 패턴을 응용 — 사전 검증 (Length=6) + body
구성 + `call_paginated` + Pydantic validate + return_code 검증.
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
    LendingMarketResponse,
    LendingMarketRow,
    LendingStockResponse,
    LendingStockRow,
)
from app.adapter.out.kiwoom.stkinfo import SentinelStockCodeError


class KiwoomLendingClient:
    """`/api/dostk/slb` 어댑터 — ka10068 (시장) + ka20068 (종목) 공유 클래스."""

    PATH = "/api/dostk/slb"
    MARKET_API_ID = "ka10068"
    STOCK_API_ID = "ka20068"
    DEFAULT_MAX_PAGES = 5

    def __init__(self, kiwoom_client: KiwoomClient) -> None:
        self._client = kiwoom_client

    async def fetch_market_trend(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        max_pages: int | None = None,
    ) -> list[LendingMarketRow]:
        """ka10068 시장 전체 대차거래 추이 — 단일 호출 (mrkt_tp 분리 없음).

        Parameters:
            start_date: 시작일자 (YYYYMMDD). None 이면 body 미포함.
            end_date: 종료일자. None 이면 body 미포함.
            max_pages: cont-yn=Y 무한 루프 방어 cap. None 이면 DEFAULT_MAX_PAGES (5).

        Raises:
            KiwoomBusinessError: return_code != 0 (api_id=ka10068).
            KiwoomCredentialRejectedError: 401/403.
            KiwoomRateLimitedError: 429 재시도 후 fail.
            KiwoomUpstreamError: 5xx · 네트워크 · 파싱 실패.
            KiwoomMaxPagesExceededError: max_pages 도달.

        plan § 12.2 #4 — NXT 분기 없음 (시장 단위 단일 응답).
        """
        body: dict[str, Any] = {"all_tp": "1"}
        if start_date is not None:
            body["strt_dt"] = start_date.strftime("%Y%m%d")
        if end_date is not None:
            body["end_dt"] = end_date.strftime("%Y%m%d")

        cap = max_pages if max_pages is not None else self.DEFAULT_MAX_PAGES
        all_rows: list[LendingMarketRow] = []

        async for page in self._client.call_paginated(
            api_id=self.MARKET_API_ID,
            endpoint=self.PATH,
            body=body,
            max_pages=cap,
        ):
            # B-β 1R 2b-H2 패턴 — flag-then-raise-outside-except (__context__ 박힘 차단)
            validation_failed = False
            parsed: LendingMarketResponse | None = None
            try:
                parsed = LendingMarketResponse.model_validate(page.body)
            except ValidationError:
                validation_failed = True

            if validation_failed:
                raise KiwoomResponseValidationError(
                    f"{self.MARKET_API_ID} 응답 검증 실패"
                )
            if parsed is None:  # pragma: no cover — validation_failed 와 mutex
                raise RuntimeError("unreachable: parsed None without validation_failed")

            if parsed.return_code != 0:
                # message 는 attacker-influenced — 비식별 메타만 (B-α/B-β M-2 패턴).
                raise KiwoomBusinessError(
                    api_id=self.MARKET_API_ID,
                    return_code=parsed.return_code,
                    message=parsed.return_msg,
                )

            all_rows.extend(parsed.dbrt_trde_trnsn)

            # 빈 응답 가드 — sentinel 무한 루프 방어 (D-1 fetch_sector_daily 패턴).
            if not parsed.dbrt_trde_trnsn:
                break

        return all_rows

    async def fetch_stock_trend(
        self,
        stock_code: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        max_pages: int | None = None,
    ) -> list[LendingStockRow]:
        """ka20068 종목별 대차거래 추이.

        Parameters:
            stock_code: 6자리 숫자만 허용 (NXT suffix `_NX` 거부 — plan § 12.2 #4).
            start_date / end_date / max_pages — fetch_market_trend 와 동일.

        Raises:
            SentinelStockCodeError: stock_code 가 6자리 숫자 외 (ValueError 상속, 호출 차단).
            (이외 키움 도메인 예외) — fetch_market_trend 동일.

        plan § 12.2 #4 — KRX only. NXT suffix (`005930_NX` 8자리) 도 거부.
        endpoint-17 § 2.2 ★ stk_cd Length=6 명세.
        """
        # 사전 검증 — 6자리 숫자 외 거부 (호출 차단). NXT suffix 등도 차단.
        # Phase F-2: SentinelStockCodeError(ValueError) — service layer 가 별도
        # catch → total_alphanumeric_skipped 분리 (ADR § 44.9).
        if not (len(stock_code) == 6 and stock_code.isdigit()):
            raise SentinelStockCodeError(
                f"stock_code 는 6자리 숫자만 허용 (NXT suffix 미지원) — 입력={stock_code!r}"
            )

        body: dict[str, Any] = {
            "stk_cd": stock_code,
            "all_tp": "0",
        }
        if start_date is not None:
            body["strt_dt"] = start_date.strftime("%Y%m%d")
        if end_date is not None:
            body["end_dt"] = end_date.strftime("%Y%m%d")

        cap = max_pages if max_pages is not None else self.DEFAULT_MAX_PAGES
        all_rows: list[LendingStockRow] = []

        async for page in self._client.call_paginated(
            api_id=self.STOCK_API_ID,
            endpoint=self.PATH,
            body=body,
            max_pages=cap,
        ):
            validation_failed = False
            parsed: LendingStockResponse | None = None
            try:
                parsed = LendingStockResponse.model_validate(page.body)
            except ValidationError:
                validation_failed = True

            if validation_failed:
                raise KiwoomResponseValidationError(
                    f"{self.STOCK_API_ID} 응답 검증 실패"
                )
            if parsed is None:  # pragma: no cover
                raise RuntimeError("unreachable: parsed None without validation_failed")

            if parsed.return_code != 0:
                raise KiwoomBusinessError(
                    api_id=self.STOCK_API_ID,
                    return_code=parsed.return_code,
                    message=parsed.return_msg,
                )

            all_rows.extend(parsed.dbrt_trde_trnsn)

            # 빈 응답 가드 — sentinel 무한 루프 방어.
            if not parsed.dbrt_trde_trnsn:
                break

        return all_rows


__all__ = ["KiwoomLendingClient"]
