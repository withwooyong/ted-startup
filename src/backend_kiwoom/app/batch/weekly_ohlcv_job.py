"""주봉 OHLCV sync 콜백 — APScheduler 가 트리거 (C-3β / ADR § 35).

설계: phase-c-3-weekly-monthly-ohlcv.md § 3.2 + endpoint-07-ka10082.md § 7 + ADR § 35 (cron shift).

책임 (ohlcv_daily_job 패턴 일관):
- IngestPeriodicOhlcvUseCaseFactory 호출 → execute(period=WEEKLY, base_date=직전 영업일)
- 결과 logger.info / 실패율 알람
- 모든 예외 swallow — 다음 cron tick 정상 동작 보장

호출자: WeeklyOhlcvScheduler 의 등록된 cron job (KST sat 07:00 — ADR § 35 NXT 마감 후, daily/flow 종료 후).
"""

from __future__ import annotations

import logging
from datetime import date

from app.adapter.web._deps import IngestPeriodicOhlcvUseCaseFactory
from app.application.constants import Period
from app.batch.business_day import previous_kst_business_day

logger = logging.getLogger(__name__)


# 운영 1주 모니터 후 조정. ohlcv_daily_job 과 동일 임계값.
FAILURE_RATIO_ALERT_THRESHOLD: float = 0.10


async def fire_weekly_ohlcv_sync(
    *,
    factory: IngestPeriodicOhlcvUseCaseFactory,
    alias: str,
) -> None:
    """주봉 OHLCV sync 콜백 — best-effort, 예외 swallow.

    Parameters:
        factory: lifespan 에서 set 된 IngestPeriodicOhlcvUseCaseFactory
        alias: 사용할 키움 자격증명 alias (settings.scheduler_weekly_ohlcv_sync_alias)

    ADR § 35 — base_date = 직전 KST 영업일 (sat 발화 시 직전 fri). 주봉 마지막 거래일 일치.
    """
    base_date = previous_kst_business_day(date.today())
    logger.info("ohlcv weekly sync cron 시작 — alias=%s base_date=%s", alias, base_date)
    try:
        async with factory(alias) as use_case:
            result = await use_case.execute(period=Period.WEEKLY, base_date=base_date)
    except Exception:  # noqa: BLE001 — cron 콜백은 모든 예외 swallow
        logger.exception("ohlcv weekly sync 콜백 예외 — alias=%s", alias)
        return

    failure_ratio = (result.failed / result.total) if result.total > 0 else 0.0

    if failure_ratio > FAILURE_RATIO_ALERT_THRESHOLD:
        sample = [(e.stock_code, e.exchange, e.error_class) for e in result.errors[:10]]
        logger.error(
            "ohlcv weekly sync 실패율 과다 — total=%d krx=%d nxt=%d failed=%d ratio=%.2f sample=%s",
            result.total,
            result.success_krx,
            result.success_nxt,
            result.failed,
            failure_ratio,
            sample,
        )
    elif result.failed > 0:
        logger.warning(
            "ohlcv weekly sync 부분 실패 — total=%d krx=%d nxt=%d failed=%d ratio=%.2f",
            result.total,
            result.success_krx,
            result.success_nxt,
            result.failed,
            failure_ratio,
        )
    else:
        logger.info(
            "ohlcv weekly sync 완료 — total=%d krx=%d nxt=%d",
            result.total,
            result.success_krx,
            result.success_nxt,
        )


__all__ = ["FAILURE_RATIO_ALERT_THRESHOLD", "fire_weekly_ohlcv_sync"]
