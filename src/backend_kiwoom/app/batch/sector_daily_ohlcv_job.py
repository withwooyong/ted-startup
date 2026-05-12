"""sector_daily OHLCV sync 콜백 — APScheduler 가 트리거 (D-1).

설계: endpoint-13-ka20006.md § 7.2 + § 12.

yearly_ohlcv_job 패턴 1:1 응용 — 단, period 없음 (단일 endpoint).

특징 (plan § 12.2):
- #7 cron = mon-fri KST 07:00 — § 35 NXT 마감 후 새벽 cron 일관
- #4 NXT 미호출 (sector 도메인에 NXT 없음)

H-5 (cron 07:00 KST 06:00 ohlcv_daily + 06:30 daily_flow 와 KRX rate limit 경합) —
기존 KRX rate limit lock (asyncio.Lock) 으로 안전 (50~80 호출 × 0.25s = 13~20초 추정).
"""

from __future__ import annotations

import logging
from datetime import date

from app.adapter.web._deps import IngestSectorDailyBulkUseCaseFactory

logger = logging.getLogger(__name__)


FAILURE_RATIO_ALERT_THRESHOLD: float = 0.10


async def fire_sector_daily_sync(
    *,
    factory: IngestSectorDailyBulkUseCaseFactory,
    alias: str,
) -> None:
    """sector daily OHLCV sync 콜백 — best-effort, 예외 swallow (cron 연속성).

    호출자: SectorDailyOhlcvScheduler 의 등록된 cron job (mon-fri KST 07:00).
    `base_date=date.today()` 명시 전달 (sector 도메인은 today 사용).
    """
    today = date.today()
    logger.info("sector daily sync cron 시작 — alias=%s base_date=%s", alias, today)
    try:
        async with factory(alias) as use_case:
            result = await use_case.execute(base_date=today)
    except Exception:  # noqa: BLE001 — cron 콜백은 모든 예외 swallow
        logger.exception("sector daily sync 콜백 예외 — alias=%s", alias)
        return

    failure_ratio = (result.failed / result.total) if result.total > 0 else 0.0

    if failure_ratio > FAILURE_RATIO_ALERT_THRESHOLD:
        sample = list(result.errors[:10])
        logger.error(
            "sector daily sync 실패율 과다 — total=%d success=%d failed=%d skipped=%d ratio=%.2f sample=%s",
            result.total,
            result.success,
            result.failed,
            result.skipped,
            failure_ratio,
            sample,
        )
    elif result.failed > 0:
        logger.warning(
            "sector daily sync 부분 실패 — total=%d success=%d failed=%d skipped=%d ratio=%.2f",
            result.total,
            result.success,
            result.failed,
            result.skipped,
            failure_ratio,
        )
    else:
        logger.info(
            "sector daily sync 완료 — total=%d success=%d skipped=%d",
            result.total,
            result.success,
            result.skipped,
        )


__all__ = ["FAILURE_RATIO_ALERT_THRESHOLD", "fire_sector_daily_sync"]
