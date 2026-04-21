"""APScheduler 기반 일일 배치 트리거.

스케줄 구성:
  - market_data_pipeline: KST 기본 06:00 월~금 (Java MarketDataScheduler 와 동등)
  - backtest_pipeline: KST 기본 07:00 월 (market_data 배치 1시간 후 주 1회)

파이프라인 본체는 각각 market_data_job / backtest_job 모듈이 전담.
"""

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.batch.backtest_job import fire_backtest_pipeline
from app.batch.market_data_job import run_market_data_pipeline
from app.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")


async def _fire_pipeline() -> None:
    """스케줄러 콜백 — 예외가 스케줄러 루프를 죽이지 않도록 방어.

    trading_date 는 KST 로 명시적으로 계산. 프로세스 TZ 가 UTC 로 떨어져도 하루 밀림 방지.
    """
    try:
        trading_date = datetime.now(KST).date()
        result = await run_market_data_pipeline(trading_date=trading_date)
        if result.skipped:
            return
        if not result.succeeded:
            failing = [s.name for s in result.steps if not s.succeeded]
            logger.error("일일 배치 일부 실패: %s", failing)
    except Exception:
        logger.exception("일일 배치 파이프라인 예외")


def build_scheduler(settings: Settings | None = None) -> AsyncIOScheduler:
    s = settings or get_settings()
    scheduler = AsyncIOScheduler(timezone=KST)
    scheduler.add_job(
        _fire_pipeline,
        CronTrigger(
            day_of_week="mon-fri",
            hour=s.scheduler_hour_kst,
            minute=s.scheduler_minute_kst,
            timezone=KST,
        ),
        id="market_data_pipeline",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    if s.backtest_enabled:
        scheduler.add_job(
            fire_backtest_pipeline,
            CronTrigger(
                day_of_week=s.backtest_cron_day_of_week,
                hour=s.backtest_cron_hour_kst,
                minute=s.backtest_cron_minute_kst,
                timezone=KST,
            ),
            id="backtest_pipeline",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
    return scheduler
