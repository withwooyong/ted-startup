"""년봉 OHLCV sync 콜백 — APScheduler 가 트리거 (C-4).

설계: endpoint-09-ka10094.md § 7 + § 12.

책임: monthly_ohlcv_job 와 동일 패턴. period=YEARLY 만 다름. KRX 만 호출 (UseCase NXT skip
가드, plan § 12.2 #3 yearly_nxt_disabled).
호출자: YearlyOhlcvScheduler 의 등록된 cron job (매년 1월 5일 KST 03:00).
"""

from __future__ import annotations

import logging

from app.adapter.web._deps import IngestPeriodicOhlcvUseCaseFactory
from app.application.constants import Period

logger = logging.getLogger(__name__)


FAILURE_RATIO_ALERT_THRESHOLD: float = 0.10


async def fire_yearly_ohlcv_sync(
    *,
    factory: IngestPeriodicOhlcvUseCaseFactory,
    alias: str,
) -> None:
    """년봉 OHLCV sync 콜백 — best-effort, 예외 swallow."""
    logger.info("ohlcv yearly sync cron 시작 — alias=%s", alias)
    try:
        async with factory(alias) as use_case:
            result = await use_case.execute(period=Period.YEARLY)
    except Exception:  # noqa: BLE001 — cron 콜백은 모든 예외 swallow
        logger.exception("ohlcv yearly sync 콜백 예외 — alias=%s", alias)
        return

    failure_ratio = (result.failed / result.total) if result.total > 0 else 0.0

    if failure_ratio > FAILURE_RATIO_ALERT_THRESHOLD:
        sample = [(e.stock_code, e.exchange, e.error_class) for e in result.errors[:10]]
        logger.error(
            "ohlcv yearly sync 실패율 과다 — total=%d krx=%d nxt=%d failed=%d ratio=%.2f sample=%s",
            result.total,
            result.success_krx,
            result.success_nxt,
            result.failed,
            failure_ratio,
            sample,
        )
    elif result.failed > 0:
        logger.warning(
            "ohlcv yearly sync 부분 실패 — total=%d krx=%d nxt=%d failed=%d ratio=%.2f",
            result.total,
            result.success_krx,
            result.success_nxt,
            result.failed,
            failure_ratio,
        )
    else:
        logger.info(
            "ohlcv yearly sync 완료 — total=%d krx=%d nxt=%d",
            result.total,
            result.success_krx,
            result.success_nxt,
        )


__all__ = ["FAILURE_RATIO_ALERT_THRESHOLD", "fire_yearly_ohlcv_sync"]
