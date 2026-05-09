"""WeeklyOhlcvScheduler + MonthlyOhlcvScheduler + fire callbacks (C-3β).

설계: phase-c-3-weekly-monthly-ohlcv.md § 3.2 + H-7 cron 시간 충돌 검증.

cron 시간 (H-7 결정):
- weekly: 금 KST 19:30 (daily_flow 19:00 후 30분, 30분 간격 일관)
- monthly: 매월 1일 KST 03:00

fire 콜백 (ohlcv_daily_job 패턴 일관):
- 정상 완료 logger.info
- 예외 swallow (cron 연속성)
- 실패율 > 10% logger.error
- 부분 실패 (failed > 0) logger.warning
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from typing import Any

import pytest
from apscheduler.triggers.cron import CronTrigger

from app.adapter.web._deps import IngestPeriodicOhlcvUseCaseFactory
from app.application.constants import Period
from app.application.service.ohlcv_periodic_service import (
    IngestPeriodicOhlcvUseCase,
    OhlcvSyncResult,
)
from app.scheduler import (
    MONTHLY_OHLCV_SYNC_JOB_ID,
    WEEKLY_OHLCV_SYNC_JOB_ID,
    MonthlyOhlcvScheduler,
    WeeklyOhlcvScheduler,
)


@asynccontextmanager
async def _dummy(_alias: str) -> AsyncIterator[None]:
    yield None


_dummy_factory: IngestPeriodicOhlcvUseCaseFactory = _dummy  # type: ignore[assignment]


# ---------- WeeklyOhlcvScheduler ----------


def test_weekly_disabled_no_op() -> None:
    sched = WeeklyOhlcvScheduler(factory=_dummy_factory, alias="t", enabled=False)
    sched.start()
    assert sched.is_running is False
    assert sched.job_count == 0
    sched.shutdown()


@pytest.mark.asyncio
async def test_weekly_enabled_registers_friday_19_30_kst() -> None:
    """H-7 — 금 KST 19:30 (daily_flow 19:00 후 30분)."""
    sched = WeeklyOhlcvScheduler(factory=_dummy_factory, alias="t", enabled=True)
    sched.start()
    try:
        assert sched.is_running is True
        assert sched.job_count == 1
        job = sched.get_job(WEEKLY_OHLCV_SYNC_JOB_ID)
        assert job is not None
        trigger = job.trigger
        assert isinstance(trigger, CronTrigger)
        # cron field 확인 — day_of_week=fri, hour=19, minute=30, timezone=KST
        fields = {f.name: str(f) for f in trigger.fields}
        assert fields["day_of_week"] == "fri"
        assert fields["hour"] == "19"
        assert fields["minute"] == "30"
    finally:
        sched.shutdown()


@pytest.mark.asyncio
async def test_weekly_start_idempotent() -> None:
    sched = WeeklyOhlcvScheduler(factory=_dummy_factory, alias="t", enabled=True)
    sched.start()
    sched.start()  # 멱등
    try:
        assert sched.job_count == 1
    finally:
        sched.shutdown()


@pytest.mark.asyncio
async def test_weekly_shutdown_idempotent() -> None:
    sched = WeeklyOhlcvScheduler(factory=_dummy_factory, alias="t", enabled=True)
    sched.start()
    sched.shutdown()
    sched.shutdown()  # 두 번째 shutdown 안전
    assert sched.is_running is False


# ---------- MonthlyOhlcvScheduler ----------


def test_monthly_disabled_no_op() -> None:
    sched = MonthlyOhlcvScheduler(factory=_dummy_factory, alias="t", enabled=False)
    sched.start()
    assert sched.is_running is False
    assert sched.job_count == 0


@pytest.mark.asyncio
async def test_monthly_enabled_registers_first_day_03_00_kst() -> None:
    """매월 1일 KST 03:00 (다른 cron 없음)."""
    sched = MonthlyOhlcvScheduler(factory=_dummy_factory, alias="t", enabled=True)
    sched.start()
    try:
        assert sched.is_running is True
        assert sched.job_count == 1
        job = sched.get_job(MONTHLY_OHLCV_SYNC_JOB_ID)
        assert job is not None
        trigger = job.trigger
        fields = {f.name: str(f) for f in trigger.fields}
        assert fields["day"] == "1"
        assert fields["hour"] == "3"
        assert fields["minute"] == "0"
    finally:
        sched.shutdown()


# ---------- fire 콜백 ----------


def _ok_result(total: int = 5, success_krx: int = 5, failed: int = 0) -> OhlcvSyncResult:
    return OhlcvSyncResult(
        base_date=date(2025, 9, 8),
        total=total,
        success_krx=success_krx,
        success_nxt=0,
        failed=failed,
        errors=(),
    )


class _StubUseCase:
    def __init__(self, result: OhlcvSyncResult, *, raise_exc: Exception | None = None) -> None:
        self._result = result
        self._raise_exc = raise_exc
        self.call_count = 0
        self.last_period: Period | None = None

    async def execute(self, *, period: Period, **_: Any) -> OhlcvSyncResult:
        self.call_count += 1
        self.last_period = period
        if self._raise_exc is not None:
            raise self._raise_exc
        return self._result


def _make_factory(uc: _StubUseCase) -> IngestPeriodicOhlcvUseCaseFactory:
    @asynccontextmanager
    async def _factory(_alias: str) -> AsyncIterator[IngestPeriodicOhlcvUseCase]:
        yield uc  # type: ignore[misc]

    return _factory  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_fire_weekly_ohlcv_sync_passes_period_weekly() -> None:
    from app.batch.weekly_ohlcv_job import fire_weekly_ohlcv_sync

    uc = _StubUseCase(_ok_result())
    await fire_weekly_ohlcv_sync(factory=_make_factory(uc), alias="t")
    assert uc.call_count == 1
    assert uc.last_period == Period.WEEKLY


@pytest.mark.asyncio
async def test_fire_monthly_ohlcv_sync_passes_period_monthly() -> None:
    from app.batch.monthly_ohlcv_job import fire_monthly_ohlcv_sync

    uc = _StubUseCase(_ok_result())
    await fire_monthly_ohlcv_sync(factory=_make_factory(uc), alias="t")
    assert uc.call_count == 1
    assert uc.last_period == Period.MONTHLY


@pytest.mark.asyncio
async def test_fire_weekly_swallows_exception() -> None:
    """cron 콜백은 모든 예외 swallow — 다음 tick 정상 동작 보장."""
    from app.batch.weekly_ohlcv_job import fire_weekly_ohlcv_sync

    uc = _StubUseCase(_ok_result(), raise_exc=RuntimeError("boom"))
    # 예외 raise 안 함
    await fire_weekly_ohlcv_sync(factory=_make_factory(uc), alias="t")


@pytest.mark.asyncio
async def test_fire_monthly_swallows_exception() -> None:
    from app.batch.monthly_ohlcv_job import fire_monthly_ohlcv_sync

    uc = _StubUseCase(_ok_result(), raise_exc=RuntimeError("boom"))
    await fire_monthly_ohlcv_sync(factory=_make_factory(uc), alias="t")


# ---------- H-7 cron 충돌 검증 ----------


@pytest.mark.asyncio
async def test_weekly_cron_does_not_collide_with_daily_flow_19_00() -> None:
    """H-7 — daily_flow 는 mon-fri 19:00. weekly 는 금 19:30 — 30분 후."""
    sched = WeeklyOhlcvScheduler(factory=_dummy_factory, alias="t", enabled=True)
    sched.start()
    try:
        job = sched.get_job(WEEKLY_OHLCV_SYNC_JOB_ID)
        assert job is not None
        fields = {f.name: str(f) for f in job.trigger.fields}
        # 19:00 이 아니어야 (충돌 차단)
        assert not (fields["hour"] == "19" and fields["minute"] == "0")
    finally:
        sched.shutdown()
