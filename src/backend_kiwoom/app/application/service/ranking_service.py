"""IngestRankingUseCase 5종 + Bulk 5종 — Phase F-4 (ka10027/30/31/32/23).

설계: phase-f-4-rankings.md § 5.6 + endpoint-18-ka10027.md § 6.3/6.4.

5 단건 + 5 Bulk UseCase — 5 ranking endpoint 가 같은 client / 같은 repository 공유라
service module 1개로 통합. F-3 정착 패턴 (SkipReason / errors_above_threshold tuple /
_empty_bulk_result / 단건 sentinel catch) 1:1 미러.

D-9 nested payload — ka10030 23 필드 {opmr, af_mkrt, bf_mkrt} 분리.
D-11 — 임계치 도입 안 함 (운영 1주 모니터 후).
D-14 — Bulk 매트릭스 sequential 호출 (asyncio.gather 아님 — RPS 4 충돌 회피).
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._exceptions import KiwoomBusinessError
from app.adapter.out.kiwoom._records import (
    FluRtSortType,
    FluRtUpperRow,
    PredVolumeUpperRow,
    RankingExchangeType,
    RankingMarketType,
    RankingType,
    TodayVolumeSortType,
    TodayVolumeUpperRow,
    TradeAmountUpperRow,
    VolumeSdninRow,
    VolumeSdninSortType,
    VolumeSdninTimeType,
)
from app.adapter.out.kiwoom.rkinfo import KiwoomRkInfoClient
from app.adapter.out.kiwoom.stkinfo import SentinelStockCodeError, strip_kiwoom_suffix
from app.adapter.out.persistence.repositories.ranking_snapshot import (
    RankingSnapshotRepository,
)
from app.adapter.out.persistence.repositories.stock import StockRepository
from app.application.dto._shared import SkipReason
from app.application.dto.ranking import (
    NormalizedRanking,
    RankingBulkResult,
    RankingIngestOutcome,
)

logger = logging.getLogger(__name__)


# Bulk 매트릭스 (D-3/D-5) — 2 market × 2 sort = 4 호출 매트릭스.
_FLU_RT_BULK_MARKETS: tuple[RankingMarketType, ...] = (
    RankingMarketType.KOSPI,
    RankingMarketType.KOSDAQ,
)
_FLU_RT_BULK_SORTS: tuple[FluRtSortType, ...] = (
    FluRtSortType.UP_RATE,
    FluRtSortType.DOWN_RATE,
)

# ka10030/31/32 — 2 market × 1 sort (sort_tp 단일).
_VOLUME_BULK_MARKETS: tuple[RankingMarketType, ...] = (
    RankingMarketType.KOSPI,
    RankingMarketType.KOSDAQ,
)

# ka10023 — 2 market × 2 sort (qty / rate).
_VOLUME_SDNIN_BULK_SORTS: tuple[VolumeSdninSortType, ...] = (
    VolumeSdninSortType.SUDDEN_VOLUME,
    VolumeSdninSortType.SUDDEN_RATE,
)


def _empty_bulk_result(
    *,
    ranking_type: RankingType,
) -> RankingBulkResult:
    """F-3 D-5 — empty raw_rows 시 zero-value RankingBulkResult.

    short_selling._empty_bulk_result 와 패턴 일관 (keyword-only 시그니처).
    """
    return RankingBulkResult(
        ranking_type=ranking_type,
        outcomes=(),
        errors_above_threshold=(),
        skipped_outcomes=(),
    )


def _normalize_rows(
    *,
    ranking_type: RankingType,
    snapshot_at: datetime,
    sort_tp: str,
    market_type: str,
    exchange_type: str,
    raw_rows: list[Any],
    stock_lookup: dict[str, Any],
    used_filters: dict[str, Any],
    primary_metric_fn: Any,
) -> list[NormalizedRanking]:
    """raw_rows → NormalizedRanking list.

    - stock_code_raw = 응답 stk_cd 그대로 (NXT _NX suffix 보존)
    - stock_id = strip 후 stock_lookup 에서 매핑 (miss → None, D-8)
    - primary_metric = primary_metric_fn(row) — endpoint 별 다름
    """
    snapshot_date = snapshot_at.date()
    snapshot_time = snapshot_at.time().replace(microsecond=0)

    normalized: list[NormalizedRanking] = []
    for rank_idx, row in enumerate(raw_rows, start=1):
        stk_cd_raw = row.stk_cd
        base_code = strip_kiwoom_suffix(stk_cd_raw)
        stock = stock_lookup.get(base_code)
        stock_id = stock.id if stock is not None else None

        primary_metric = primary_metric_fn(row)
        payload = row.to_payload()

        normalized.append(
            NormalizedRanking(
                snapshot_date=snapshot_date,
                snapshot_time=snapshot_time,
                ranking_type=ranking_type,
                sort_tp=sort_tp,
                market_type=market_type,
                exchange_type=exchange_type,
                rank=rank_idx,
                stock_id=stock_id,
                stock_code_raw=stk_cd_raw,
                primary_metric=primary_metric,
                payload=payload,
                request_filters=dict(used_filters),
            )
        )
    return normalized


def _flu_rt_primary_metric(row: FluRtUpperRow) -> Decimal | None:
    from app.adapter.out.kiwoom.stkinfo import _to_decimal

    return _to_decimal(row.flu_rt)


def _today_volume_primary_metric(row: TodayVolumeUpperRow) -> Decimal | None:
    from app.adapter.out.kiwoom.stkinfo import _to_decimal

    return _to_decimal(row.trde_qty)


def _pred_volume_primary_metric(row: PredVolumeUpperRow) -> Decimal | None:
    from app.adapter.out.kiwoom.stkinfo import _to_decimal

    return _to_decimal(row.trde_qty)


def _trade_amount_primary_metric(row: TradeAmountUpperRow) -> Decimal | None:
    from app.adapter.out.kiwoom.stkinfo import _to_decimal

    return _to_decimal(row.trde_prica)


def _volume_sdnin_primary_metric_fn(sort_tp: VolumeSdninSortType) -> Any:
    """ka10023 sort_tp 분기 — qty 계열은 sdnin_qty, rate 계열은 sdnin_rt."""
    from app.adapter.out.kiwoom.stkinfo import _to_decimal

    def _fn(row: VolumeSdninRow) -> Decimal | None:
        if sort_tp in (VolumeSdninSortType.SUDDEN_VOLUME, VolumeSdninSortType.DROP_VOLUME):
            return _to_decimal(row.sdnin_qty)
        return _to_decimal(row.sdnin_rt)

    return _fn


# ===========================================================================
# ka10027 (FLU_RT) — 단건 + Bulk
# ===========================================================================


class IngestFluRtUpperUseCase:
    """ka10027 등락률 상위 단건 ingest UseCase (Phase F-4)."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        rkinfo_client: KiwoomRkInfoClient,
    ) -> None:
        self._session = session
        self._client = rkinfo_client

    async def execute(
        self,
        *,
        snapshot_at: datetime,
        market_type: RankingMarketType = RankingMarketType.KOSPI,
        sort_tp: FluRtSortType = FluRtSortType.UP_RATE,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
    ) -> RankingIngestOutcome:
        """1 호출 → outcome (fetched / upserted / error).

        F-3 D-7 defense-in-depth: SentinelStockCodeError catch → error = SkipReason.SENTINEL_SKIP.
        """
        try:
            raw_rows, used_filters = await self._client.fetch_flu_rt_upper(
                market_type=market_type,
                sort_tp=sort_tp,
                exchange_type=exchange_type,
            )
        except SentinelStockCodeError:
            # F-3 D-7 defense-in-depth — 응답 row stk_cd 가 sentinel 인 경우.
            # 본 테스트가 실제로 실행하므로 # pragma: no cover 미부착.
            logger.info("ka10027 sentinel skip (defense-in-depth)")
            return RankingIngestOutcome(
                ranking_type=RankingType.FLU_RT,
                snapshot_at=snapshot_at,
                sort_tp=sort_tp.value,
                market_type=market_type.value,
                exchange_type=exchange_type.value,
                fetched=0,
                upserted=0,
                error=SkipReason.SENTINEL_SKIP.value,
            )
        except KiwoomBusinessError as exc:
            return RankingIngestOutcome(
                ranking_type=RankingType.FLU_RT,
                snapshot_at=snapshot_at,
                sort_tp=sort_tp.value,
                market_type=market_type.value,
                exchange_type=exchange_type.value,
                fetched=0,
                upserted=0,
                error=f"business: {exc.return_code}",
            )

        upserted = await _persist_common(
            session=self._session,
            ranking_type=RankingType.FLU_RT,
            snapshot_at=snapshot_at,
            sort_tp=sort_tp.value,
            market_type=market_type.value,
            exchange_type=exchange_type.value,
            raw_rows=raw_rows,
            used_filters=used_filters,
            primary_metric_fn=_flu_rt_primary_metric,
        )
        return RankingIngestOutcome(
            ranking_type=RankingType.FLU_RT,
            snapshot_at=snapshot_at,
            sort_tp=sort_tp.value,
            market_type=market_type.value,
            exchange_type=exchange_type.value,
            fetched=len(raw_rows),
            upserted=upserted,
        )


class IngestFluRtUpperBulkUseCase:
    """ka10027 등락률 Bulk — 2 market × 2 sort = 4 호출 매트릭스 (D-3/D-5)."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        single_use_case: IngestFluRtUpperUseCase,
    ) -> None:
        self._session = session
        self._single = single_use_case

    async def execute(
        self,
        *,
        snapshot_at: datetime,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
    ) -> RankingBulkResult:
        outcomes: list[RankingIngestOutcome] = []
        for market in _FLU_RT_BULK_MARKETS:
            for sort in _FLU_RT_BULK_SORTS:
                try:
                    outcome = await self._single.execute(
                        snapshot_at=snapshot_at,
                        market_type=market,
                        sort_tp=sort,
                        exchange_type=exchange_type,
                    )
                except Exception as exc:  # noqa: BLE001 — partial-failure 격리
                    outcome = RankingIngestOutcome(
                        ranking_type=RankingType.FLU_RT,
                        snapshot_at=snapshot_at,
                        sort_tp=sort.value,
                        market_type=market.value,
                        exchange_type=exchange_type.value,
                        fetched=0,
                        upserted=0,
                        error=type(exc).__name__,
                    )
                    logger.warning(
                        "ka10027 bulk 호출 실패 market=%s sort=%s: %s",
                        market.value,
                        sort.value,
                        type(exc).__name__,
                    )
                outcomes.append(outcome)

        return RankingBulkResult(
            ranking_type=RankingType.FLU_RT,
            outcomes=tuple(outcomes),
            errors_above_threshold=(),
        )


# ===========================================================================
# ka10030 (TODAY_VOLUME) — 단건 + Bulk
# ===========================================================================


class IngestTodayVolumeUpperUseCase:
    """ka10030 당일 거래량 상위 단건 (D-9 nested payload)."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        rkinfo_client: KiwoomRkInfoClient,
    ) -> None:
        self._session = session
        self._client = rkinfo_client

    async def execute(
        self,
        *,
        snapshot_at: datetime,
        market_type: RankingMarketType = RankingMarketType.KOSPI,
        sort_tp: TodayVolumeSortType = TodayVolumeSortType.TRADE_VOLUME,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
    ) -> RankingIngestOutcome:
        try:
            raw_rows, used_filters = await self._client.fetch_today_volume_upper(
                market_type=market_type,
                sort_tp=sort_tp,
                exchange_type=exchange_type,
            )
        except SentinelStockCodeError:  # pragma: no cover — F-3 D-7
            return RankingIngestOutcome(
                ranking_type=RankingType.TODAY_VOLUME,
                snapshot_at=snapshot_at,
                sort_tp=sort_tp.value,
                market_type=market_type.value,
                exchange_type=exchange_type.value,
                error=SkipReason.SENTINEL_SKIP.value,
            )
        except KiwoomBusinessError as exc:
            return RankingIngestOutcome(
                ranking_type=RankingType.TODAY_VOLUME,
                snapshot_at=snapshot_at,
                sort_tp=sort_tp.value,
                market_type=market_type.value,
                exchange_type=exchange_type.value,
                error=f"business: {exc.return_code}",
            )

        upserted = await _persist_common(
            session=self._session,
            ranking_type=RankingType.TODAY_VOLUME,
            snapshot_at=snapshot_at,
            sort_tp=sort_tp.value,
            market_type=market_type.value,
            exchange_type=exchange_type.value,
            raw_rows=raw_rows,
            used_filters=used_filters,
            primary_metric_fn=_today_volume_primary_metric,
        )
        return RankingIngestOutcome(
            ranking_type=RankingType.TODAY_VOLUME,
            snapshot_at=snapshot_at,
            sort_tp=sort_tp.value,
            market_type=market_type.value,
            exchange_type=exchange_type.value,
            fetched=len(raw_rows),
            upserted=upserted,
        )


class IngestTodayVolumeUpperBulkUseCase:
    """ka10030 Bulk — 2 market × 1 sort."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        single_use_case: IngestTodayVolumeUpperUseCase,
    ) -> None:
        self._session = session
        self._single = single_use_case

    async def execute(
        self,
        *,
        snapshot_at: datetime,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
    ) -> RankingBulkResult:
        outcomes: list[RankingIngestOutcome] = []
        for market in _VOLUME_BULK_MARKETS:
            try:
                outcome = await self._single.execute(
                    snapshot_at=snapshot_at,
                    market_type=market,
                    exchange_type=exchange_type,
                )
            except Exception as exc:  # noqa: BLE001
                outcome = RankingIngestOutcome(
                    ranking_type=RankingType.TODAY_VOLUME,
                    snapshot_at=snapshot_at,
                    sort_tp=TodayVolumeSortType.TRADE_VOLUME.value,
                    market_type=market.value,
                    exchange_type=exchange_type.value,
                    error=type(exc).__name__,
                )
            outcomes.append(outcome)

        return RankingBulkResult(
            ranking_type=RankingType.TODAY_VOLUME,
            outcomes=tuple(outcomes),
            errors_above_threshold=(),
        )


# ===========================================================================
# ka10031 (PRED_VOLUME) — 단건 + Bulk
# ===========================================================================


class IngestPredVolumeUpperUseCase:
    """ka10031 전일 거래량 상위 단건."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        rkinfo_client: KiwoomRkInfoClient,
    ) -> None:
        self._session = session
        self._client = rkinfo_client

    async def execute(
        self,
        *,
        snapshot_at: datetime,
        market_type: RankingMarketType = RankingMarketType.KOSPI,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
    ) -> RankingIngestOutcome:
        try:
            raw_rows, used_filters = await self._client.fetch_pred_volume_upper(
                market_type=market_type,
                exchange_type=exchange_type,
            )
        except SentinelStockCodeError:  # pragma: no cover
            return RankingIngestOutcome(
                ranking_type=RankingType.PRED_VOLUME,
                snapshot_at=snapshot_at,
                sort_tp="0",
                market_type=market_type.value,
                exchange_type=exchange_type.value,
                error=SkipReason.SENTINEL_SKIP.value,
            )
        except KiwoomBusinessError as exc:
            return RankingIngestOutcome(
                ranking_type=RankingType.PRED_VOLUME,
                snapshot_at=snapshot_at,
                sort_tp="0",
                market_type=market_type.value,
                exchange_type=exchange_type.value,
                error=f"business: {exc.return_code}",
            )

        upserted = await _persist_common(
            session=self._session,
            ranking_type=RankingType.PRED_VOLUME,
            snapshot_at=snapshot_at,
            sort_tp="0",
            market_type=market_type.value,
            exchange_type=exchange_type.value,
            raw_rows=raw_rows,
            used_filters=used_filters,
            primary_metric_fn=_pred_volume_primary_metric,
        )
        return RankingIngestOutcome(
            ranking_type=RankingType.PRED_VOLUME,
            snapshot_at=snapshot_at,
            sort_tp="0",
            market_type=market_type.value,
            exchange_type=exchange_type.value,
            fetched=len(raw_rows),
            upserted=upserted,
        )


class IngestPredVolumeUpperBulkUseCase:
    def __init__(
        self,
        *,
        session: AsyncSession,
        single_use_case: IngestPredVolumeUpperUseCase,
    ) -> None:
        self._session = session
        self._single = single_use_case

    async def execute(
        self,
        *,
        snapshot_at: datetime,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
    ) -> RankingBulkResult:
        outcomes: list[RankingIngestOutcome] = []
        for market in _VOLUME_BULK_MARKETS:
            try:
                outcome = await self._single.execute(
                    snapshot_at=snapshot_at,
                    market_type=market,
                    exchange_type=exchange_type,
                )
            except Exception as exc:  # noqa: BLE001
                outcome = RankingIngestOutcome(
                    ranking_type=RankingType.PRED_VOLUME,
                    snapshot_at=snapshot_at,
                    sort_tp="0",
                    market_type=market.value,
                    exchange_type=exchange_type.value,
                    error=type(exc).__name__,
                )
            outcomes.append(outcome)
        return RankingBulkResult(
            ranking_type=RankingType.PRED_VOLUME,
            outcomes=tuple(outcomes),
            errors_above_threshold=(),
        )


# ===========================================================================
# ka10032 (TRDE_PRICA) — 단건 + Bulk
# ===========================================================================


class IngestTradeAmountUpperUseCase:
    """ka10032 거래대금 상위 단건."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        rkinfo_client: KiwoomRkInfoClient,
    ) -> None:
        self._session = session
        self._client = rkinfo_client

    async def execute(
        self,
        *,
        snapshot_at: datetime,
        market_type: RankingMarketType = RankingMarketType.KOSPI,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
    ) -> RankingIngestOutcome:
        try:
            raw_rows, used_filters = await self._client.fetch_trde_prica_upper(
                market_type=market_type,
                exchange_type=exchange_type,
            )
        except SentinelStockCodeError:  # pragma: no cover
            return RankingIngestOutcome(
                ranking_type=RankingType.TRDE_PRICA,
                snapshot_at=snapshot_at,
                sort_tp="0",
                market_type=market_type.value,
                exchange_type=exchange_type.value,
                error=SkipReason.SENTINEL_SKIP.value,
            )
        except KiwoomBusinessError as exc:
            return RankingIngestOutcome(
                ranking_type=RankingType.TRDE_PRICA,
                snapshot_at=snapshot_at,
                sort_tp="0",
                market_type=market_type.value,
                exchange_type=exchange_type.value,
                error=f"business: {exc.return_code}",
            )

        upserted = await _persist_common(
            session=self._session,
            ranking_type=RankingType.TRDE_PRICA,
            snapshot_at=snapshot_at,
            sort_tp="0",
            market_type=market_type.value,
            exchange_type=exchange_type.value,
            raw_rows=raw_rows,
            used_filters=used_filters,
            primary_metric_fn=_trade_amount_primary_metric,
        )
        return RankingIngestOutcome(
            ranking_type=RankingType.TRDE_PRICA,
            snapshot_at=snapshot_at,
            sort_tp="0",
            market_type=market_type.value,
            exchange_type=exchange_type.value,
            fetched=len(raw_rows),
            upserted=upserted,
        )


class IngestTradeAmountUpperBulkUseCase:
    def __init__(
        self,
        *,
        session: AsyncSession,
        single_use_case: IngestTradeAmountUpperUseCase,
    ) -> None:
        self._session = session
        self._single = single_use_case

    async def execute(
        self,
        *,
        snapshot_at: datetime,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
    ) -> RankingBulkResult:
        outcomes: list[RankingIngestOutcome] = []
        for market in _VOLUME_BULK_MARKETS:
            try:
                outcome = await self._single.execute(
                    snapshot_at=snapshot_at,
                    market_type=market,
                    exchange_type=exchange_type,
                )
            except Exception as exc:  # noqa: BLE001
                outcome = RankingIngestOutcome(
                    ranking_type=RankingType.TRDE_PRICA,
                    snapshot_at=snapshot_at,
                    sort_tp="0",
                    market_type=market.value,
                    exchange_type=exchange_type.value,
                    error=type(exc).__name__,
                )
            outcomes.append(outcome)
        return RankingBulkResult(
            ranking_type=RankingType.TRDE_PRICA,
            outcomes=tuple(outcomes),
            errors_above_threshold=(),
        )


# ===========================================================================
# ka10023 (VOLUME_SDNIN) — 단건 + Bulk
# ===========================================================================


class IngestVolumeSdninUseCase:
    """ka10023 거래량 급증 단건 — sort_tp 분기 primary_metric (qty / rate)."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        rkinfo_client: KiwoomRkInfoClient,
    ) -> None:
        self._session = session
        self._client = rkinfo_client

    async def execute(
        self,
        *,
        snapshot_at: datetime,
        market_type: RankingMarketType = RankingMarketType.KOSPI,
        sort_tp: VolumeSdninSortType = VolumeSdninSortType.SUDDEN_VOLUME,
        tm_tp: VolumeSdninTimeType = VolumeSdninTimeType.PREVIOUS_DAY,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
    ) -> RankingIngestOutcome:
        try:
            raw_rows, used_filters = await self._client.fetch_volume_sdnin(
                market_type=market_type,
                sort_tp=sort_tp,
                tm_tp=tm_tp,
                exchange_type=exchange_type,
            )
        except SentinelStockCodeError:  # pragma: no cover
            return RankingIngestOutcome(
                ranking_type=RankingType.VOLUME_SDNIN,
                snapshot_at=snapshot_at,
                sort_tp=sort_tp.value,
                market_type=market_type.value,
                exchange_type=exchange_type.value,
                error=SkipReason.SENTINEL_SKIP.value,
            )
        except KiwoomBusinessError as exc:
            return RankingIngestOutcome(
                ranking_type=RankingType.VOLUME_SDNIN,
                snapshot_at=snapshot_at,
                sort_tp=sort_tp.value,
                market_type=market_type.value,
                exchange_type=exchange_type.value,
                error=f"business: {exc.return_code}",
            )

        upserted = await _persist_common(
            session=self._session,
            ranking_type=RankingType.VOLUME_SDNIN,
            snapshot_at=snapshot_at,
            sort_tp=sort_tp.value,
            market_type=market_type.value,
            exchange_type=exchange_type.value,
            raw_rows=raw_rows,
            used_filters=used_filters,
            primary_metric_fn=_volume_sdnin_primary_metric_fn(sort_tp),
        )
        return RankingIngestOutcome(
            ranking_type=RankingType.VOLUME_SDNIN,
            snapshot_at=snapshot_at,
            sort_tp=sort_tp.value,
            market_type=market_type.value,
            exchange_type=exchange_type.value,
            fetched=len(raw_rows),
            upserted=upserted,
        )


class IngestVolumeSdninBulkUseCase:
    """ka10023 Bulk — 2 market × 2 sort (qty + rate)."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        single_use_case: IngestVolumeSdninUseCase,
    ) -> None:
        self._session = session
        self._single = single_use_case

    async def execute(
        self,
        *,
        snapshot_at: datetime,
        exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
        tm_tp: VolumeSdninTimeType = VolumeSdninTimeType.PREVIOUS_DAY,
    ) -> RankingBulkResult:
        outcomes: list[RankingIngestOutcome] = []
        for market in _VOLUME_BULK_MARKETS:
            for sort in _VOLUME_SDNIN_BULK_SORTS:
                try:
                    outcome = await self._single.execute(
                        snapshot_at=snapshot_at,
                        market_type=market,
                        sort_tp=sort,
                        tm_tp=tm_tp,
                        exchange_type=exchange_type,
                    )
                except Exception as exc:  # noqa: BLE001
                    outcome = RankingIngestOutcome(
                        ranking_type=RankingType.VOLUME_SDNIN,
                        snapshot_at=snapshot_at,
                        sort_tp=sort.value,
                        market_type=market.value,
                        exchange_type=exchange_type.value,
                        error=type(exc).__name__,
                    )
                outcomes.append(outcome)
        return RankingBulkResult(
            ranking_type=RankingType.VOLUME_SDNIN,
            outcomes=tuple(outcomes),
            errors_above_threshold=(),
        )


# ===========================================================================
# 공통 persist helper — 5 endpoint 공용 (module-level)
# ===========================================================================


async def _persist_common(
    *,
    session: AsyncSession,
    ranking_type: RankingType,
    snapshot_at: datetime,
    sort_tp: str,
    market_type: str,
    exchange_type: str,
    raw_rows: list[Any],
    used_filters: dict[str, Any],
    primary_metric_fn: Any,
) -> int:
    """공통 정규화 + upsert — 5 endpoint 단건 UseCase 공용 helper."""
    if not raw_rows:
        return 0

    codes = {strip_kiwoom_suffix(r.stk_cd) for r in raw_rows}
    stock_repo = StockRepository(session)
    stock_lookup = await stock_repo.find_by_codes(codes)

    normalized = _normalize_rows(
        ranking_type=ranking_type,
        snapshot_at=snapshot_at,
        sort_tp=sort_tp,
        market_type=market_type,
        exchange_type=exchange_type,
        raw_rows=raw_rows,
        stock_lookup=stock_lookup,
        used_filters=used_filters,
        primary_metric_fn=primary_metric_fn,
    )
    repo = RankingSnapshotRepository(session)
    return await repo.upsert_many(normalized)


__all__ = [
    "IngestFluRtUpperBulkUseCase",
    "IngestFluRtUpperUseCase",
    "IngestPredVolumeUpperBulkUseCase",
    "IngestPredVolumeUpperUseCase",
    "IngestTodayVolumeUpperBulkUseCase",
    "IngestTodayVolumeUpperUseCase",
    "IngestTradeAmountUpperBulkUseCase",
    "IngestTradeAmountUpperUseCase",
    "IngestVolumeSdninBulkUseCase",
    "IngestVolumeSdninUseCase",
]
