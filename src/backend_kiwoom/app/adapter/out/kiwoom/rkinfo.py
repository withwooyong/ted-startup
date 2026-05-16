"""KiwoomRkInfoClient — `/api/dostk/rkinfo` 카테고리 어댑터 (Phase F-4).

설계: endpoint-18-ka10027.md § 6.1 + endpoint-19~22 + phase-f-4-rankings.md § 5.4.

5 메서드:
- ka10027 등락률 (fetch_flu_rt_upper)
- ka10030 당일 거래량 (fetch_today_volume_upper)
- ka10031 전일 거래량 (fetch_pred_volume_upper)
- ka10032 거래대금 (fetch_trde_prica_upper)
- ka10023 거래량 급증 (fetch_volume_sdnin)

책임:
- KiwoomClient 위임 — 토큰 / 재시도 / rate-limit / cont-yn 페이지네이션
- ka10027~ka10023 응답 row 파싱 (Pydantic Row) — KiwoomBusinessError 매핑
- 페이지네이션 결과 합치기 + 빈 응답 break
- `used_filters` (body dict) 반환 — caller (Service) 가 request_filters JSONB 저장
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from app.adapter.out.kiwoom._client import KiwoomClient
from app.adapter.out.kiwoom._exceptions import (
    KiwoomBusinessError,
    KiwoomResponseValidationError,
)
from app.adapter.out.kiwoom._records import (
    FluRtSortType,
    FluRtUpperResponse,
    FluRtUpperRow,
    PredVolumeUpperResponse,
    PredVolumeUpperRow,
    RankingExchangeType,
    RankingMarketType,
    TodayVolumeSortType,
    TodayVolumeUpperResponse,
    TodayVolumeUpperRow,
    TradeAmountUpperResponse,
    TradeAmountUpperRow,
    VolumeSdninResponse,
    VolumeSdninRow,
    VolumeSdninSortType,
    VolumeSdninTimeType,
)


class KiwoomRkInfoClient:
    """`/api/dostk/rkinfo` 어댑터 — 5 ranking endpoint (Phase F-4)."""

    PATH = "/api/dostk/rkinfo"

    FLU_RT_API_ID = "ka10027"
    TODAY_VOLUME_API_ID = "ka10030"
    PRED_VOLUME_API_ID = "ka10031"
    TRDE_PRICA_API_ID = "ka10032"
    VOLUME_SDNIN_API_ID = "ka10023"

    # 페이지네이션 cap — 안전 마진 (1 시점 1 호출 = ~150 row 추정, 1 페이지 일반).
    DEFAULT_MAX_PAGES = 5

    def __init__(self, kiwoom_client: KiwoomClient) -> None:
        self._client = kiwoom_client

    # ------------------------------------------------------------------
    # ka10027 — 등락률 상위
    # ------------------------------------------------------------------

    async def fetch_flu_rt_upper(
        self,
        *,
        market_type: RankingMarketType = RankingMarketType.KOSPI,
        sort_tp: FluRtSortType = FluRtSortType.UP_RATE,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
        trde_qty_cnd: str = "0000",
        stk_cnd: str = "0",
        crd_cnd: str = "0",
        updown_incls: str = "1",
        pric_cnd: str = "0",
        trde_prica_cnd: str = "0",
        max_pages: int | None = None,
    ) -> tuple[list[FluRtUpperRow], dict[str, Any]]:
        """ka10027 등락률 상위 호출.

        Returns:
            (rows, used_filters) — 페이지네이션 합산 row list + body dict (재현용).
        """
        body: dict[str, Any] = {
            "mrkt_tp": market_type.value,
            "sort_tp": sort_tp.value,
            "trde_qty_cnd": trde_qty_cnd,
            "stk_cnd": stk_cnd,
            "crd_cnd": crd_cnd,
            "updown_incls": updown_incls,
            "pric_cnd": pric_cnd,
            "trde_prica_cnd": trde_prica_cnd,
            "stex_tp": exchange_type.value,
        }
        rows = await self._paginated_fetch(
            api_id=self.FLU_RT_API_ID,
            body=body,
            response_cls=FluRtUpperResponse,
            list_attr="pred_pre_flu_rt_upper",
            max_pages=max_pages,
        )
        return rows, body

    # ------------------------------------------------------------------
    # ka10030 — 당일 거래량 상위
    # ------------------------------------------------------------------

    async def fetch_today_volume_upper(
        self,
        *,
        market_type: RankingMarketType = RankingMarketType.KOSPI,
        sort_tp: TodayVolumeSortType = TodayVolumeSortType.TRADE_VOLUME,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
        mng_stk_incls: str = "0",
        crd_tp: str = "0",
        trde_qty_tp: str = "0",
        pric_tp: str = "0",
        trde_prica_tp: str = "0",
        mrkt_open_tp: str = "1",
        max_pages: int | None = None,
    ) -> tuple[list[TodayVolumeUpperRow], dict[str, Any]]:
        """ka10030 당일 거래량 상위 호출 (23 필드 + 장중/장후/장전 분리)."""
        body: dict[str, Any] = {
            "mrkt_tp": market_type.value,
            "sort_tp": sort_tp.value,
            "mng_stk_incls": mng_stk_incls,
            "crd_tp": crd_tp,
            "trde_qty_tp": trde_qty_tp,
            "pric_tp": pric_tp,
            "trde_prica_tp": trde_prica_tp,
            "mrkt_open_tp": mrkt_open_tp,
            "stex_tp": exchange_type.value,
        }
        rows = await self._paginated_fetch(
            api_id=self.TODAY_VOLUME_API_ID,
            body=body,
            response_cls=TodayVolumeUpperResponse,
            list_attr="tdy_trde_qty_upper",
            max_pages=max_pages,
        )
        return rows, body

    # ------------------------------------------------------------------
    # ka10031 — 전일 거래량 상위
    # ------------------------------------------------------------------

    async def fetch_pred_volume_upper(
        self,
        *,
        market_type: RankingMarketType = RankingMarketType.KOSPI,
        qry_tp: str = "1",
        rank_strt: str = "0",
        rank_end: str = "0",
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
        max_pages: int | None = None,
    ) -> tuple[list[PredVolumeUpperRow], dict[str, Any]]:
        """ka10031 전일 거래량 상위 호출 (6 필드 단순)."""
        body: dict[str, Any] = {
            "mrkt_tp": market_type.value,
            "qry_tp": qry_tp,
            "rank_strt": rank_strt,
            "rank_end": rank_end,
            "stex_tp": exchange_type.value,
        }
        rows = await self._paginated_fetch(
            api_id=self.PRED_VOLUME_API_ID,
            body=body,
            response_cls=PredVolumeUpperResponse,
            list_attr="pred_trde_qty_upper",
            max_pages=max_pages,
        )
        return rows, body

    # ------------------------------------------------------------------
    # ka10032 — 거래대금 상위
    # ------------------------------------------------------------------

    async def fetch_trde_prica_upper(
        self,
        *,
        market_type: RankingMarketType = RankingMarketType.KOSPI,
        mang_stk_incls: str = "0",
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
        max_pages: int | None = None,
    ) -> tuple[list[TradeAmountUpperRow], dict[str, Any]]:
        """ka10032 거래대금 상위 호출 (now_rank / pred_rank 직접 응답)."""
        body: dict[str, Any] = {
            "mrkt_tp": market_type.value,
            "mang_stk_incls": mang_stk_incls,
            "stex_tp": exchange_type.value,
        }
        rows = await self._paginated_fetch(
            api_id=self.TRDE_PRICA_API_ID,
            body=body,
            response_cls=TradeAmountUpperResponse,
            list_attr="trde_prica_upper",
            max_pages=max_pages,
        )
        return rows, body

    # ------------------------------------------------------------------
    # ka10023 — 거래량 급증
    # ------------------------------------------------------------------

    async def fetch_volume_sdnin(
        self,
        *,
        market_type: RankingMarketType = RankingMarketType.KOSPI,
        sort_tp: VolumeSdninSortType = VolumeSdninSortType.SUDDEN_VOLUME,
        tm_tp: VolumeSdninTimeType = VolumeSdninTimeType.PREVIOUS_DAY,
        trde_qty_tp: str = "5",
        tm: str = "1",
        stk_cnd: str = "0",
        pric_tp: str = "0",
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
        max_pages: int | None = None,
    ) -> tuple[list[VolumeSdninRow], dict[str, Any]]:
        """ka10023 거래량 급증 호출 (sdnin_rt + tm_tp 1/2)."""
        body: dict[str, Any] = {
            "mrkt_tp": market_type.value,
            "sort_tp": sort_tp.value,
            "tm_tp": tm_tp.value,
            "trde_qty_tp": trde_qty_tp,
            "tm": tm,
            "stk_cnd": stk_cnd,
            "pric_tp": pric_tp,
            "stex_tp": exchange_type.value,
        }
        rows = await self._paginated_fetch(
            api_id=self.VOLUME_SDNIN_API_ID,
            body=body,
            response_cls=VolumeSdninResponse,
            list_attr="trde_qty_sdnin",
            max_pages=max_pages,
        )
        return rows, body

    # ------------------------------------------------------------------
    # 내부 — 페이지네이션 + 응답 파싱 공통
    # ------------------------------------------------------------------

    async def _paginated_fetch(
        self,
        *,
        api_id: str,
        body: dict[str, Any],
        response_cls: type[BaseModel],
        list_attr: str,
        max_pages: int | None,
    ) -> list[Any]:
        """공통 paginate — cont-yn=Y 동안 호출 + 빈 응답 break + business error raise."""
        cap = max_pages if max_pages is not None else self.DEFAULT_MAX_PAGES
        all_rows: list[Any] = []

        async for page in self._client.call_paginated(
            api_id=api_id,
            endpoint=self.PATH,
            body=body,
            max_pages=cap,
        ):
            try:
                parsed = response_cls.model_validate(page.body)
            except ValidationError as exc:
                raise KiwoomResponseValidationError(
                    f"{api_id} 응답 검증 실패"
                ) from exc

            # 모든 ranking Response 는 return_code/return_msg 를 가짐 — getattr 로 mypy 호환.
            return_code = getattr(parsed, "return_code", 0)
            return_msg = getattr(parsed, "return_msg", "")
            if return_code != 0:
                # B-α/B-β M-2 — message echo 차단 (attacker-influenced).
                raise KiwoomBusinessError(
                    api_id=api_id,
                    return_code=return_code,
                    message=return_msg,
                )

            page_rows = list(getattr(parsed, list_attr))
            all_rows.extend(page_rows)

            # 빈 응답 → 다음 페이지 안 — cont-yn=Y 무한 루프 방어.
            if not page_rows:
                break

        return all_rows


__all__ = ["KiwoomRkInfoClient"]
