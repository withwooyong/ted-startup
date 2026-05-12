"""공매도 추이 (ka10014) sync 콜백 — APScheduler 가 트리거 (Phase E).

설계: endpoint-15-ka10014.md § 12 + plan § 12.2 #5.

sector_daily_ohlcv_job 패턴 1:1 응용 — active 종목 bulk sync.

특징 (plan § 12.2):
- #5 cron = mon-fri KST 07:30 — § 35 NXT 마감 후 새벽 cron 일관
- #4 NXT 시도 (nxt_enable 게이팅) — 빈 응답 정상 처리
- #6 cron 윈도 = 1주 (T-7 ~ T)
- #10 partial 임계치 = 5% / 15% (warning / error)

H-3 (cron 07:30 KST 06:00 ohlcv_daily + 06:30 daily_flow + 07:00 sector_daily 와 KRX rate
limit 경합) — 기존 KRX rate limit lock (asyncio.Lock) 으로 직렬화 안전.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from app.adapter.web._deps import IngestShortSellingBulkUseCaseFactory

logger = logging.getLogger(__name__)


SYNC_WINDOW_DAYS: int = 7
"""plan § 12.2 #6 — cron sync 윈도 1주 (T-7 ~ T)."""


async def fire_short_selling_sync(
    *,
    factory: IngestShortSellingBulkUseCaseFactory,
    alias: str,
) -> None:
    """공매도 추이 sync 콜백 — best-effort, 예외 swallow (cron 연속성).

    호출자: ShortSellingScheduler 의 등록된 cron job (mon-fri KST 07:30).
    plan § 12.2 #6 — 1주 윈도 (T-7 ~ T) bulk sync.
    """
    end = date.today()
    start = end - timedelta(days=SYNC_WINDOW_DAYS)
    logger.info(
        "short selling sync cron 시작 — alias=%s window=%s~%s",
        alias,
        start,
        end,
    )
    try:
        async with factory(alias) as use_case:
            result = await use_case.execute(start_date=start, end_date=end)
    except Exception:  # noqa: BLE001 — cron 콜백은 모든 예외 swallow
        logger.exception("short selling sync 콜백 예외 — alias=%s", alias)
        return

    total_outcomes = len(result.krx_outcomes) + len(result.nxt_outcomes)
    failure_ratio = (result.total_failed / total_outcomes) if total_outcomes > 0 else 0.0

    if result.errors_above_threshold:
        logger.error(
            "short selling sync 실패율 과다 (15%% 초과) — total_stocks=%d outcomes=%d upserted=%d failed=%d "
            "ratio=%.2f warnings=%s",
            result.total_stocks,
            total_outcomes,
            result.total_upserted,
            result.total_failed,
            failure_ratio,
            list(result.warnings),
        )
    elif result.warnings:
        logger.warning(
            "short selling sync 부분 실패 (5%% 초과) — total_stocks=%d outcomes=%d upserted=%d failed=%d "
            "ratio=%.2f warnings=%s",
            result.total_stocks,
            total_outcomes,
            result.total_upserted,
            result.total_failed,
            failure_ratio,
            list(result.warnings),
        )
    else:
        logger.info(
            "short selling sync 완료 — total_stocks=%d outcomes=%d upserted=%d failed=%d",
            result.total_stocks,
            total_outcomes,
            result.total_upserted,
            result.total_failed,
        )


__all__ = ["SYNC_WINDOW_DAYS", "fire_short_selling_sync"]
