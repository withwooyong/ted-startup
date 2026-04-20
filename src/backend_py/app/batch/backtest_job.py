"""백테스트 배치 파이프라인.

market_data_job 과 달리 단일 Step(engine.execute) 이므로 세션 1개로 처리.
BacktestEngineService.execute 내부에서 `session.flush()` 로 backtest_result 를 기록하고,
이 래퍼가 `session.commit()` 으로 최종 반영한다.

스케줄러(build_scheduler) 에서 주 1회 cron 으로 호출하며, 수동 one-shot 실행은
`scripts/run_backtest.py` 가 동일 함수를 재사용한다.
"""
from __future__ import annotations

import logging
import time
from datetime import date

from dateutil.relativedelta import relativedelta
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapter.out.persistence.session import get_sessionmaker
from app.application.dto.results import BacktestExecutionResult
from app.application.service import BacktestEngineService

logger = logging.getLogger(__name__)


class BacktestPipelineResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    period_start: date
    period_end: date
    succeeded: bool
    elapsed_ms: int
    error: str | None = None
    execution: BacktestExecutionResult | None = None


async def run_backtest_pipeline(
    *,
    period_end: date | None = None,
    period_years: int = 3,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> BacktestPipelineResult:
    """직전 N년 구간 백테스트를 실행하고 backtest_result 에 append.

    기본 동작:
      - period_end 는 인자로 주어진 값 또는 오늘(호출자 책임)
      - period_start = period_end - relativedelta(years=period_years)
      - BacktestEngineService.execute 위임 → SignalType 별 집계 row 추가
      - 단일 세션·트랜잭션. 예외는 rollback 후 BacktestPipelineResult(error=...) 로 반환.
    """
    end = period_end or date.today()
    start = end - relativedelta(years=period_years)
    factory = session_factory or get_sessionmaker()

    t0 = time.monotonic()
    async with factory() as session:
        try:
            execution = await BacktestEngineService(session).execute(start, end)
            await session.commit()
        except Exception as e:
            await session.rollback()
            elapsed = int((time.monotonic() - t0) * 1000)
            logger.exception("백테스트 파이프라인 실패 %s ~ %s", start, end)
            return BacktestPipelineResult(
                period_start=start, period_end=end, succeeded=False,
                elapsed_ms=elapsed, error=f"{type(e).__name__}: {e}",
            )

    elapsed = int((time.monotonic() - t0) * 1000)
    logger.info(
        "백테스트 파이프라인 완료 %s ~ %s signals=%d returns=%d rows=%d elapsed=%dms",
        start, end,
        execution.signals_processed, execution.returns_calculated, execution.result_rows,
        elapsed,
    )
    return BacktestPipelineResult(
        period_start=start, period_end=end, succeeded=True,
        elapsed_ms=elapsed, execution=execution,
    )


async def fire_backtest_pipeline() -> None:
    """APScheduler 콜백 — 예외가 스케줄러 루프를 죽이지 않게 감싼다."""
    try:
        from app.config.settings import get_settings

        s = get_settings()
        result = await run_backtest_pipeline(period_years=s.backtest_period_years)
        if not result.succeeded:
            logger.error("예약 실행 백테스트 실패: %s", result.error)
    except Exception:
        logger.exception("예약 실행 백테스트 콜백 예외")


__all__: list[str] = [
    "BacktestPipelineResult",
    "run_backtest_pipeline",
    "fire_backtest_pipeline",
]
