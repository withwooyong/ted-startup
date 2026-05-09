"""월봉 OHLCV sync 콜백 — APScheduler 가 트리거 (C-3β).

설계: phase-c-3-weekly-monthly-ohlcv.md § 3.2 + endpoint-08-ka10083.md § 7.

책임: weekly_ohlcv_job 와 동일 패턴. period=MONTHLY 만 다름.
호출자: MonthlyOhlcvScheduler 의 등록된 cron job (매월 1일 KST 03:00).
"""

from __future__ import annotations

import logging

from app.adapter.web._deps import IngestPeriodicOhlcvUseCaseFactory
from app.application.constants import Period

logger = logging.getLogger(__name__)


FAILURE_RATIO_ALERT_THRESHOLD: float = 0.10


async def fire_monthly_ohlcv_sync(
    *,
    factory: IngestPeriodicOhlcvUseCaseFactory,
    alias: str,
) -> None:
    """월봉 OHLCV sync 콜백 — best-effort, 예외 swallow."""
    logger.info("ohlcv monthly sync cron 시작 — alias=%s", alias)
    try:
        async with factory(alias) as use_case:
            result = await use_case.execute(period=Period.MONTHLY)
    except Exception:  # noqa: BLE001 — cron 콜백은 모든 예외 swallow
        logger.exception("ohlcv monthly sync 콜백 예외 — alias=%s", alias)
        return

    failure_ratio = (result.failed / result.total) if result.total > 0 else 0.0

    if failure_ratio > FAILURE_RATIO_ALERT_THRESHOLD:
        sample = [(e.stock_code, e.exchange, e.error_class) for e in result.errors[:10]]
        logger.error(
            "ohlcv monthly sync 실패율 과다 — total=%d krx=%d nxt=%d failed=%d ratio=%.2f sample=%s",
            result.total,
            result.success_krx,
            result.success_nxt,
            result.failed,
            failure_ratio,
            sample,
        )
    elif result.failed > 0:
        logger.warning(
            "ohlcv monthly sync 부분 실패 — total=%d krx=%d nxt=%d failed=%d ratio=%.2f",
            result.total,
            result.success_krx,
            result.success_nxt,
            result.failed,
            failure_ratio,
        )
    else:
        logger.info(
            "ohlcv monthly sync 완료 — total=%d krx=%d nxt=%d",
            result.total,
            result.success_krx,
            result.success_nxt,
        )


__all__ = ["FAILURE_RATIO_ALERT_THRESHOLD", "fire_monthly_ohlcv_sync"]
