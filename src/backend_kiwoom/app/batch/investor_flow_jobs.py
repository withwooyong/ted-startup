"""3 Phase G cron 콜백 — ka10058 / ka10059 / ka10131 (mon-fri KST 20:00 / 20:30 / 21:00).

설계: phase-g-investor-flow.md § 5.8 + D-11 (cron 발화 시점).

3 cron 함수:
- ``fire_investor_daily_sync``       (ka10058, KST 20:00)
- ``fire_stock_investor_breakdown_sync`` (ka10059, KST 20:30, 60분 sync 예상)
- ``fire_frgn_orgn_continuous_sync``  (ka10131, KST 21:00)

best-effort cron — 모든 예외 swallow (cron 연속성). ``is_trading_day`` 가드 — 휴장일 skip.
errors_above_threshold tuple (F-3 D-3 패턴) — 비어있지 않으면 ``logger.error`` 알람.

``MISFIRE_GRACE_SECONDS = 21600`` (6h) — G-2 통일 (Mac 절전 catch-up).

cron 시그니처: ``fire_*_sync(*, snapshot_at: datetime)`` — caller (scheduler) 가
``snapshot_at`` 전달. Bulk UseCase 는 factory 통해 lazy 빌드.

Step 2 R1 fix:
- C-5: ``fire_stock_investor_breakdown_sync`` 가 ``active 종목 list + stock_id_map`` 을
  ``StockRepository.list_by_filters(only_active=True)`` 로 빌드 (D-7 a — active 전체).
- C-8b: alias 하드코딩 ``"prod-main"`` 제거 — settings 에서 읽음 (lifespan fail-fast 사전 차단).
- H-7: ``is_trading_day`` KST timezone 적용 — ``datetime.now(KST).date()``.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.adapter.out.persistence.repositories.stock import StockRepository
from app.adapter.out.persistence.session import get_sessionmaker
from app.adapter.web._deps import (
    get_ingest_frgn_orgn_bulk_factory,
    get_ingest_investor_daily_bulk_factory,
    get_ingest_stock_investor_breakdown_bulk_factory,
)
from app.config.settings import get_settings

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
"""Phase G 3 cron callback 의 ``is_trading_day`` 기준 시 (Step 2 R1 H-7)."""

MISFIRE_GRACE_SECONDS = 21600
"""6h grace — G-2 통일 (F-4 ranking_jobs 패턴 미러)."""


def is_trading_day(today: date | None = None) -> bool:
    """KST 거래일 여부 — 토/일 skip (mon-fri).

    Phase G cron 시점 (20:00 ~ 21:00) 의 KST 날짜는 발화 당일 — 거래 종료 후.
    Step 2 R1 H-7 — ``datetime.now(KST).date()`` 로 timezone 명시 (서버 OS 가 UTC 라도
    KST 기준 평일 판단). 국경일 캘린더는 후속 chunk.
    """
    today = today or datetime.now(tz=KST).date()
    return today.weekday() < 5


async def fire_investor_daily_sync(*, snapshot_at: datetime) -> None:
    """ka10058 일별 매매 종목 ranking sync 콜백 (mon-fri KST 20:00).

    best-effort cron — 예외 swallow. errors_above_threshold tuple 비어있지 않으면 logger.error.
    """
    if not is_trading_day():
        logger.info("ka10058 cron — 휴장일 skip")
        return

    today_str = snapshot_at.strftime("%Y%m%d")
    logger.info("ka10058 sync cron 시작 — snapshot_at=%s", snapshot_at.isoformat())

    factory = get_ingest_investor_daily_bulk_factory()
    settings = get_settings()
    alias = settings.scheduler_investor_daily_sync_alias  # 빈 값이면 lifespan fail-fast 가 사전 차단

    try:
        async with factory(alias) as use_case:
            result = await use_case.execute(
                strt_dt=today_str,
                end_dt=today_str,
                fetched_at=snapshot_at,
            )
    except Exception:  # noqa: BLE001 — cron 콜백 예외 swallow
        logger.exception("ka10058 sync 콜백 예외 — alias=%s", alias)
        return

    if result.errors_above_threshold:
        logger.error(
            "ka10058 sync 임계치 초과 — total_calls=%d upserted=%d failed=%d errors=%s",
            result.total_calls,
            result.total_upserted,
            result.total_failed,
            list(result.errors_above_threshold),
        )
    else:
        logger.info(
            "ka10058 sync 완료 — total_calls=%d upserted=%d failed=%d",
            result.total_calls,
            result.total_upserted,
            result.total_failed,
        )


async def _build_active_stock_targets() -> tuple[list[str], dict[str, int]]:
    """ka10059 Bulk 진입점이 사용하는 (stock_codes, stock_id_map) 빌드.

    Step 2 R1 C-5 — D-7 a 결정: ``StockRepository.list_by_filters(only_active=True)`` 의
    전체 종목 (~3,000). ``nxt_enable`` / ``backfill_priority`` 추가 필터링 없음.

    반환:
    - ``stock_codes``: ``list[str]`` (각 active 종목의 ``stock_code``).
    - ``stock_id_map``: ``dict[str, int]`` (``stock_code -> Stock.id``).
    """
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        repo = StockRepository(session)
        stocks = await repo.list_by_filters(only_active=True)
    codes = [s.stock_code for s in stocks]
    id_map = {s.stock_code: s.id for s in stocks}
    return codes, id_map


async def fire_stock_investor_breakdown_sync(*, snapshot_at: datetime) -> None:
    """ka10059 종목별 wide breakdown sync 콜백 (mon-fri KST 20:30, 60분 sync 예상).

    Step 2 R1 C-5: active 종목 전체 (~3,000) 를 cron 진입 시 ``StockRepository`` 로 빌드.
    D-12 inh-1 mitigate 는 별도 chunk — 본 cron 은 빈 list 진입 회귀 없이 정상 적재 보장.
    """
    if not is_trading_day():
        logger.info("ka10059 cron — 휴장일 skip")
        return

    today_str = snapshot_at.strftime("%Y%m%d")
    logger.info("ka10059 sync cron 시작 — snapshot_at=%s", snapshot_at.isoformat())

    factory = get_ingest_stock_investor_breakdown_bulk_factory()
    settings = get_settings()
    alias = settings.scheduler_stock_investor_breakdown_sync_alias

    try:
        # active 종목 list + id_map 사전 빌드 (C-5).
        try:
            stock_codes, stock_id_map = await _build_active_stock_targets()
        except Exception:  # noqa: BLE001 — DB 조회 실패도 cron 연속성
            logger.exception("ka10059 active 종목 조회 실패 — alias=%s", alias)
            return

        if not stock_codes:
            logger.warning("ka10059 active 종목 0건 — sync skip (alias=%s)", alias)
            return

        async with factory(alias) as use_case:
            result = await use_case.execute(
                stock_codes=stock_codes,
                stock_id_map=stock_id_map,
                dt=today_str,
                fetched_at=snapshot_at,
            )
    except Exception:  # noqa: BLE001
        logger.exception("ka10059 sync 콜백 예외 — alias=%s", alias)
        return

    if result.errors_above_threshold:
        logger.error(
            "ka10059 sync 임계치 초과 — total_calls=%d upserted=%d failed=%d errors=%s",
            result.total_calls,
            result.total_upserted,
            result.total_failed,
            list(result.errors_above_threshold),
        )
    else:
        logger.info(
            "ka10059 sync 완료 — total_calls=%d upserted=%d failed=%d",
            result.total_calls,
            result.total_upserted,
            result.total_failed,
        )


async def fire_frgn_orgn_continuous_sync(*, snapshot_at: datetime) -> None:
    """ka10131 기관/외국인 연속매매 ranking sync 콜백 (mon-fri KST 21:00)."""
    if not is_trading_day():
        logger.info("ka10131 cron — 휴장일 skip")
        return

    logger.info("ka10131 sync cron 시작 — snapshot_at=%s", snapshot_at.isoformat())

    factory = get_ingest_frgn_orgn_bulk_factory()
    settings = get_settings()
    alias = settings.scheduler_frgn_orgn_continuous_sync_alias

    try:
        async with factory(alias) as use_case:
            result = await use_case.execute(
                fetched_at=snapshot_at,
                as_of_date=snapshot_at.date(),
            )
    except Exception:  # noqa: BLE001
        logger.exception("ka10131 sync 콜백 예외 — alias=%s", alias)
        return

    if result.errors_above_threshold:
        logger.error(
            "ka10131 sync 임계치 초과 — total_calls=%d upserted=%d failed=%d errors=%s",
            result.total_calls,
            result.total_upserted,
            result.total_failed,
            list(result.errors_above_threshold),
        )
    else:
        logger.info(
            "ka10131 sync 완료 — total_calls=%d upserted=%d failed=%d",
            result.total_calls,
            result.total_upserted,
            result.total_failed,
        )


__all__ = [
    "KST",
    "MISFIRE_GRACE_SECONDS",
    "fire_frgn_orgn_continuous_sync",
    "fire_investor_daily_sync",
    "fire_stock_investor_breakdown_sync",
    "is_trading_day",
]
