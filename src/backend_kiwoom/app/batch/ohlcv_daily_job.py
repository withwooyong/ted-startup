"""일간 OHLCV sync 콜백 — APScheduler 가 트리거 (C-1β / ADR § 35).

설계: endpoint-06-ka10081.md § 7.2 + ADR § 17 (초기 18:30 cron) + ADR § 35 (cron shift to morning).

책임 (stock_fundamental_job 패턴 일관):
- `IngestDailyOhlcvUseCaseFactory` 호출 → `IngestDailyOhlcvUseCase.execute(base_date=직전 영업일)`
- 결과 logger.info (total / success_krx / success_nxt / failed)
- 실패율 10% 초과 시 logger.error (운영 oncall 알람)
- 모든 예외 swallow — 다음 cron tick 정상 동작 보장
- 거래일 판정은 cron 트리거가 mon-fri 만 발화

호출자:
- `OhlcvDailyScheduler` 의 등록된 daily cron job (KST mon-fri 06:00 — ADR § 35 NXT 마감 후)
- 수동 호출도 가능 (운영 dry-run / 백필 시)

ADR § 35 — cron 06:00 시점에서 `date.today()` 는 그날 (장 시작 전). NXT 정산 완료된 직전
영업일 데이터를 fetch 하려면 `base_date=previous_kst_business_day(today)` 명시 전달.
"""

from __future__ import annotations

import logging
from datetime import date

from app.adapter.web._deps import IngestDailyOhlcvUseCaseFactory
from app.batch.business_day import previous_kst_business_day

logger = logging.getLogger(__name__)


# 운영 1주 모니터 후 조정. vendor 일시 장애 / 자격증명 한도 의심 임계값.
FAILURE_RATIO_ALERT_THRESHOLD: float = 0.10


async def fire_ohlcv_daily_sync(
    *,
    factory: IngestDailyOhlcvUseCaseFactory,
    alias: str,
) -> None:
    """일간 OHLCV sync 콜백 — best-effort, 예외 swallow.

    Parameters:
        factory: lifespan 에서 set 된 IngestDailyOhlcvUseCaseFactory
        alias: 사용할 키움 자격증명 alias (settings.scheduler_ohlcv_daily_sync_alias)

    ADR § 35 — base_date = 직전 KST 영업일. mon 06:00 cron → last fri / tue~fri 06:00 → 전일.
    """
    base_date = previous_kst_business_day(date.today())
    logger.info("ohlcv daily sync cron 시작 — alias=%s base_date=%s", alias, base_date)
    try:
        async with factory(alias) as use_case:
            result = await use_case.execute(base_date=base_date)
    except Exception:  # noqa: BLE001 — cron 콜백은 모든 예외 swallow
        logger.exception("ohlcv daily sync 콜백 예외 — alias=%s", alias)
        return

    failure_ratio = (result.failed / result.total) if result.total > 0 else 0.0

    if failure_ratio > FAILURE_RATIO_ALERT_THRESHOLD:
        sample = [(e.stock_code, e.exchange, e.error_class) for e in result.errors[:10]]
        logger.error(
            "ohlcv daily sync 실패율 과다 — total=%d krx=%d nxt=%d failed=%d ratio=%.2f sample=%s",
            result.total,
            result.success_krx,
            result.success_nxt,
            result.failed,
            failure_ratio,
            sample,
        )
    elif result.failed > 0:
        logger.warning(
            "ohlcv daily sync 부분 실패 — total=%d krx=%d nxt=%d failed=%d ratio=%.2f",
            result.total,
            result.success_krx,
            result.success_nxt,
            result.failed,
            failure_ratio,
        )
    else:
        logger.info(
            "ohlcv daily sync 완료 — total=%d krx=%d nxt=%d",
            result.total,
            result.success_krx,
            result.success_nxt,
        )


__all__ = ["FAILURE_RATIO_ALERT_THRESHOLD", "fire_ohlcv_daily_sync"]
