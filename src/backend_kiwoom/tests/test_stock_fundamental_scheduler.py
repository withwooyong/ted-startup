"""StockFundamentalScheduler — KST 평일 18:00 cron (B-γ-2).

설계: endpoint-05-ka10001.md § 7.2 + ADR § 14.1 (cron 18:00 결정).

검증 (StockMasterScheduler 패턴 일관 — async event loop 필수):
- enabled=False → start no-op
- enabled=True → job 1개 등록 (mon-fri 18:00 KST)
- start 멱등성
- shutdown 멱등성
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from apscheduler.triggers.cron import CronTrigger

from app.adapter.web._deps import SyncStockFundamentalUseCaseFactory
from app.scheduler import (
    KST,
    STOCK_FUNDAMENTAL_SYNC_JOB_ID,
    StockFundamentalScheduler,
)


@asynccontextmanager
async def _dummy(_alias: str) -> AsyncIterator[None]:
    yield None


_dummy_factory: SyncStockFundamentalUseCaseFactory = _dummy  # type: ignore[assignment]


@pytest.mark.asyncio
async def test_scheduler_disabled_start_is_noop() -> None:
    sched = StockFundamentalScheduler(factory=_dummy_factory, alias="test", enabled=False)
    sched.start()
    assert sched.is_running is False
    assert sched.job_count == 0


@pytest.mark.asyncio
async def test_scheduler_enabled_registers_one_cron_job() -> None:
    sched = StockFundamentalScheduler(factory=_dummy_factory, alias="prod-main", enabled=True)
    try:
        sched.start()
        assert sched.is_running is True
        assert sched.job_count == 1
        job = sched.get_job(STOCK_FUNDAMENTAL_SYNC_JOB_ID)
        assert job is not None
        assert isinstance(job.trigger, CronTrigger)
        assert job.trigger.timezone == KST
        # misfire_grace_time = 21600s (6h) — Mac 절전 catch-up (ADR § 42.5 옵션 C, plan § 3 #1)
        assert job.misfire_grace_time == 21600  # raw apscheduler Job int (not timedelta — _PhaseEJobView wrap 별도)
    finally:
        sched.shutdown(wait=False)


@pytest.mark.asyncio
async def test_scheduler_start_is_idempotent() -> None:
    sched = StockFundamentalScheduler(factory=_dummy_factory, alias="prod-main", enabled=True)
    try:
        sched.start()
        sched.start()
        assert sched.job_count == 1
    finally:
        sched.shutdown(wait=False)


@pytest.mark.asyncio
async def test_scheduler_shutdown_safe_when_not_started() -> None:
    sched = StockFundamentalScheduler(factory=_dummy_factory, alias="prod-main", enabled=True)
    sched.shutdown(wait=False)
    assert sched.is_running is False


@pytest.mark.asyncio
async def test_scheduler_job_uses_18kst_mon_fri_cron() -> None:
    sched = StockFundamentalScheduler(factory=_dummy_factory, alias="prod-main", enabled=True)
    try:
        sched.start()
        job = sched.get_job(STOCK_FUNDAMENTAL_SYNC_JOB_ID)
        assert job is not None
        # CronTrigger fields — name 별 expressions 검사 (apscheduler 출력 형식 의존 회피)
        fields_by_name = {f.name: f for f in job.trigger.fields}
        assert str(fields_by_name["hour"]) == "18"
        assert str(fields_by_name["minute"]) == "0"
        assert str(fields_by_name["day_of_week"]) == "mon-fri"
    finally:
        sched.shutdown(wait=False)
