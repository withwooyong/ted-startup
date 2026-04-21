"""시장 데이터 파이프라인 — Java Spring Batch 3 Step 대응.

Step 1 (collect): KrxClient → stock_price/short_selling/lending_balance upsert
Step 2 (detect):  SignalDetectionService 로 당일 시그널 탐지
Step 3 (notify):  NotificationService 로 전송

설계:
- 각 Step 을 독립 세션·트랜잭션으로 감싸 실패 격리
- 한 Step 실패해도 다음 Step 은 시도(alert 우선) — Java 구현은 Spring Batch 가 자동 중단이지만,
  Python 구현은 KRX 수집 실패 시에도 전일 기준 탐지가 가능하도록 유연하게 처리
- 전체 결과는 단일 PipelineResult 로 집계
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapter.out.external import KrxClient, TelegramClient
from app.adapter.out.persistence.models import Signal
from app.adapter.out.persistence.repositories import SignalRepository
from app.adapter.out.persistence.session import get_sessionmaker
from app.application.service import (
    MarketDataCollectionService,
    NotificationService,
    SignalDetectionService,
)
from app.batch.trading_day import is_trading_day

logger = logging.getLogger(__name__)


class StepOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    succeeded: bool
    elapsed_ms: int
    error: str | None = None
    summary: dict[str, int | str] | None = None


class PipelineResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    trading_date: date
    skipped: bool
    skipped_reason: str | None = None
    steps: list[StepOutcome] = []
    total_elapsed_ms: int = 0

    @property
    def succeeded(self) -> bool:
        return not self.skipped and all(s.succeeded for s in self.steps)


async def run_market_data_pipeline(
    trading_date: date,
    *,
    krx_client: KrxClient | None = None,
    telegram_client: TelegramClient | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    force_when_non_trading: bool = False,
) -> PipelineResult:
    """3-Step 파이프라인 실행. 거래일이 아니면 skip(force 플래그로 우회 가능)."""
    if not force_when_non_trading and not is_trading_day(trading_date):
        logger.info("거래일 아님 — 파이프라인 skip: %s (%s)", trading_date, trading_date.strftime("%A"))
        return PipelineResult(
            trading_date=trading_date,
            skipped=True,
            skipped_reason=f"non-trading day ({trading_date.strftime('%A')})",
        )

    krx = krx_client or KrxClient()
    telegram = telegram_client or TelegramClient()
    factory = session_factory or get_sessionmaker()

    pipeline_start = time.monotonic()
    steps: list[StepOutcome] = []

    # Step 1: collect
    async with factory() as session:
        outcome = await _run_step(
            "collect",
            lambda: MarketDataCollectionService(krx, session).collect_all(trading_date),
            session,
            lambda r: {
                "stocks": r.stocks_upserted,
                "prices": r.stock_prices_upserted,
                "short": r.short_selling_upserted,
                "lending": r.lending_balance_upserted,
            },
        )
    steps.append(outcome)

    # Step 2: detect
    async with factory() as session:
        outcome = await _run_step(
            "detect",
            lambda: SignalDetectionService(session).detect_all(trading_date),
            session,
            lambda r: {
                "rapid": r.rapid_decline,
                "trend": r.trend_reversal,
                "squeeze": r.short_squeeze,
            },
        )
    steps.append(outcome)

    # Step 3: notify — detect 성공 시만
    if any(s.name == "detect" and s.succeeded for s in steps):
        async with factory() as session:

            async def _notify() -> int:
                # 같은 세션에서 다시 로드해 Telegram 발송
                signals: list[Signal] = list(await SignalRepository(session).list_between(trading_date, trading_date))
                return await NotificationService(session, telegram).notify_signals(signals)

            outcome = await _run_step(
                "notify",
                _notify,
                session,
                lambda n: {"sent": int(n)},
            )
        steps.append(outcome)
    else:
        steps.append(
            StepOutcome(
                name="notify",
                succeeded=False,
                elapsed_ms=0,
                error="detect step 실패로 notify 생략",
            )
        )

    await telegram.close()

    total = int((time.monotonic() - pipeline_start) * 1000)
    result = PipelineResult(trading_date=trading_date, skipped=False, steps=steps, total_elapsed_ms=total)
    logger.info(
        "파이프라인 종료 date=%s elapsed=%dms 성공=%s",
        trading_date,
        total,
        result.succeeded,
    )
    return result


async def _run_step(
    name: str,
    runner: Callable[[], Awaitable[Any]],
    session: AsyncSession,
    summarize: Callable[[Any], dict[str, Any]],
) -> StepOutcome:
    started = time.monotonic()
    try:
        result = await runner()
        await session.commit()
    except Exception as e:
        await session.rollback()
        elapsed = int((time.monotonic() - started) * 1000)
        logger.error("배치 Step 실패: %s (%s) — %s", name, type(e).__name__, e)
        return StepOutcome(name=name, succeeded=False, elapsed_ms=elapsed, error=f"{type(e).__name__}: {e}")
    elapsed = int((time.monotonic() - started) * 1000)
    summary = summarize(result)
    logger.info("배치 Step 완료: %s elapsed=%dms summary=%s", name, elapsed, summary)
    return StepOutcome(name=name, succeeded=True, elapsed_ms=elapsed, summary=summary)
