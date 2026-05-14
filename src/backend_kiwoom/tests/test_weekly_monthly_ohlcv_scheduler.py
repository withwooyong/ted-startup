"""WeeklyOhlcvScheduler + MonthlyOhlcvScheduler + fire callbacks (C-3β / ADR § 35).

설계: phase-c-3-weekly-monthly-ohlcv.md § 3.2 + H-7 cron 충돌 + ADR § 35 (cron shift).

cron 시간 (ADR § 35 결정 — NXT 마감 후 다음날 새벽):
- weekly: KST sat 07:00 (금 NXT 마감 후 + daily/flow 종료 후 1시간)
- monthly: 매월 1일 KST 03:00 (변경 없음 — 거래 없는 새벽)

fire 콜백 (ohlcv_daily_job 패턴 일관 + ADR § 35 base_date 명시 전달):
- 정상 완료 logger.info
- 예외 swallow (cron 연속성)
- 실패율 > 10% logger.error
- 부분 실패 (failed > 0) logger.warning
- execute() 가 base_date=previous_kst_business_day(today) 로 호출
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
async def test_weekly_enabled_registers_saturday_07_00_kst() -> None:
    """ADR § 35 — sat KST 07:00 (금 NXT 마감 후 + daily/flow 종료 후 1시간 stagger)."""
    sched = WeeklyOhlcvScheduler(factory=_dummy_factory, alias="t", enabled=True)
    sched.start()
    try:
        assert sched.is_running is True
        assert sched.job_count == 1
        job = sched.get_job(WEEKLY_OHLCV_SYNC_JOB_ID)
        assert job is not None
        trigger = job.trigger
        assert isinstance(trigger, CronTrigger)
        # cron field 확인 — day_of_week=sat, hour=7, minute=0, timezone=KST
        fields = {f.name: str(f) for f in trigger.fields}
        assert fields["day_of_week"] == "sat"
        assert fields["hour"] == "7"
        assert fields["minute"] == "0"
        # misfire_grace_time = 21600s (6h) — Mac 절전 catch-up (ADR § 42.5 옵션 C, plan § 3 #1)
        assert job.misfire_grace_time == 21600  # raw apscheduler Job int (not timedelta — _PhaseEJobView wrap 별도)
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
        # misfire_grace_time = 21600s (6h) — Mac 절전 catch-up (ADR § 42.5 옵션 C, plan § 3 #1)
        assert job.misfire_grace_time == 21600  # raw apscheduler Job int (not timedelta — _PhaseEJobView wrap 별도)
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
        self.last_kwargs: dict[str, Any] = {}

    async def execute(self, *, period: Period, **kwargs: Any) -> OhlcvSyncResult:
        self.call_count += 1
        self.last_period = period
        self.last_kwargs = {"period": period, **kwargs}
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
async def test_weekly_cron_does_not_collide_with_daily_flow_06_30() -> None:
    """ADR § 35 — daily_flow 는 mon-fri 06:30. weekly 는 sat 07:00 — day_of_week 분리."""
    sched = WeeklyOhlcvScheduler(factory=_dummy_factory, alias="t", enabled=True)
    sched.start()
    try:
        job = sched.get_job(WEEKLY_OHLCV_SYNC_JOB_ID)
        assert job is not None
        fields = {f.name: str(f) for f in job.trigger.fields}
        # mon-fri 가 아니어야 (요일 분리로 충돌 차단)
        assert "mon" not in fields["day_of_week"]
        assert "fri" not in fields["day_of_week"]
        assert fields["day_of_week"] == "sat"
    finally:
        sched.shutdown()


@pytest.mark.asyncio
async def test_fire_weekly_ohlcv_sync_passes_previous_business_day_as_base_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR § 35 — fire_weekly_*_job 이 execute(base_date=직전 영업일) 명시 전달.

    Sat 발화 시 base_date = Fri (주봉 마지막 거래일 일치).
    """
    from app.batch import weekly_ohlcv_job

    class _FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return date(2026, 5, 16)  # Saturday → prev = Friday 2026-05-15

    monkeypatch.setattr(weekly_ohlcv_job, "date", _FixedDate)

    uc = _StubUseCase(_ok_result())
    await weekly_ohlcv_job.fire_weekly_ohlcv_sync(factory=_make_factory(uc), alias="t")

    assert uc.call_count == 1
    assert uc.last_kwargs.get("base_date") == date(2026, 5, 15)
    assert uc.last_kwargs.get("period") == Period.WEEKLY
