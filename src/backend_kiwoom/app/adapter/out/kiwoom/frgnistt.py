"""KiwoomForeignClient — `/api/dostk/frgnistt` 카테고리 어댑터 (Phase G).

설계: phase-g-investor-flow.md § 5.4 + endpoint-25-ka10131.md § 6.1.

신규 카테고리 (Phase G 첫 도입) — `/api/dostk/frgnistt`. 향후 외인/기관 관련 endpoint
추가 가능 (현재 ka10131 만).

책임:
- ``KiwoomClient`` 위임 — 토큰 / 재시도 / rate-limit / cont-yn 페이지네이션.
- ka10131 응답 row 파싱 (Pydantic Row) + business error 매핑.
- 페이지네이션 결과 합치기.
- ``netslmt_tp=2`` 고정 (매수만 — 매도 ranking 미지원, plan § 11.2).
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.adapter.out.kiwoom._client import KiwoomClient
from app.adapter.out.kiwoom._exceptions import (
    KiwoomBusinessError,
    KiwoomResponseValidationError,
)
from app.adapter.out.kiwoom._records import (
    ContinuousAmtQtyType,
    ContinuousFrgnOrgnResponse,
    ContinuousFrgnOrgnRow,
    ContinuousPeriodType,
    InvestorMarketType,
    RankingExchangeType,
    StockIndsType,
)


class KiwoomForeignClient:
    """`/api/dostk/frgnistt` 카테고리 어댑터 — ka10131 만의 첫 endpoint."""

    PATH = "/api/dostk/frgnistt"

    CONTINUOUS_API_ID = "ka10131"

    # 페이지네이션 cap — 응답 row ~50~200 추정, 1~5 페이지 예상.
    DEFAULT_MAX_PAGES = 5

    # netslmt_tp 고정값 (매수만) — 매도 ranking 미지원 (plan § 11.2 알려진 위험).
    NETSLMT_TP_NET_BUY = "2"

    def __init__(self, kiwoom_client: KiwoomClient) -> None:
        self._client = kiwoom_client

    async def fetch_continuous(
        self,
        *,
        dt: ContinuousPeriodType = ContinuousPeriodType.LATEST,
        strt_dt: str = "",
        end_dt: str = "",
        mrkt_tp: InvestorMarketType = InvestorMarketType.KOSPI,
        stk_inds_tp: StockIndsType = StockIndsType.STOCK,
        amt_qty_tp: ContinuousAmtQtyType = ContinuousAmtQtyType.AMOUNT,
        stex_tp: RankingExchangeType = RankingExchangeType.UNIFIED,
        max_pages: int | None = None,
    ) -> tuple[list[ContinuousFrgnOrgnRow], dict[str, Any]]:
        """ka10131 — 기관/외국인 연속매매 ranking.

        ``dt == ContinuousPeriodType.PERIOD`` (0) 일 때만 ``strt_dt`` / ``end_dt`` 사용.
        나머지 dt 값은 응답 시점 기준 N일.

        Args:
            dt: ``ContinuousPeriodType`` (1/3/5/10/20/120/0).
            strt_dt: ``YYYYMMDD`` (dt=PERIOD 일 때만).
            end_dt: ``YYYYMMDD`` (dt=PERIOD 일 때만).
            mrkt_tp: ``InvestorMarketType`` (001=KOSPI / 101=KOSDAQ).
            stk_inds_tp: ``StockIndsType`` (D-14 — 본 chunk STOCK 만).
            amt_qty_tp: ``ContinuousAmtQtyType`` (0=금액 / 1=수량 — ★ ka10059 와 _반대_).
            stex_tp: ``RankingExchangeType``.
            max_pages: 페이지 cap (default DEFAULT_MAX_PAGES=5).

        Returns:
            ``(rows, used_filters)`` — ``ContinuousFrgnOrgnRow`` list + body dict.

        Raises:
            KiwoomBusinessError: 응답 return_code != 0.
            KiwoomResponseValidationError: 응답 row Pydantic 검증 실패.
        """
        body: dict[str, Any] = {
            "dt": dt.value,
            "strt_dt": strt_dt,
            "end_dt": end_dt,
            "mrkt_tp": mrkt_tp.value,
            "netslmt_tp": self.NETSLMT_TP_NET_BUY,
            "stk_inds_tp": stk_inds_tp.value,
            "amt_qty_tp": amt_qty_tp.value,
            "stex_tp": stex_tp.value,
        }

        pages_cap = max_pages if max_pages is not None else self.DEFAULT_MAX_PAGES

        all_rows: list[ContinuousFrgnOrgnRow] = []
        async for page in self._client.call_paginated(
            api_id=self.CONTINUOUS_API_ID,
            endpoint=self.PATH,
            body=body,
            max_pages=pages_cap,
        ):
            validation_failed = False
            parsed: ContinuousFrgnOrgnResponse | None = None
            try:
                parsed = ContinuousFrgnOrgnResponse.model_validate(page.body)
            except ValidationError:
                validation_failed = True

            if validation_failed:
                raise KiwoomResponseValidationError(
                    f"{self.CONTINUOUS_API_ID} 응답 검증 실패"
                )
            if parsed is None:  # pragma: no cover — validation_failed 와 mutex
                raise RuntimeError("unreachable: parsed None without validation_failed")
            if parsed.return_code != 0:
                raise KiwoomBusinessError(
                    api_id=self.CONTINUOUS_API_ID,
                    return_code=parsed.return_code,
                    message=parsed.return_msg,
                )
            all_rows.extend(parsed.orgn_frgnr_cont_trde_prst)

        return all_rows, body


__all__ = ["KiwoomForeignClient"]
