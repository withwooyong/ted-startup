"""SectorDailyOhlcvScheduler — sector_daily_sync_daily job (D-1).

chunk = D-1, plan doc § 12 참조.

test_weekly_monthly_ohlcv_scheduler.py (C-3β) 의 yearly job 패턴 1:1 응용.

결정 (plan § 12.2 #7):
- CronTrigger(day_of_week="mon-fri", hour=7, minute=0, timezone=Asia/Seoul)
- job_id = SECTOR_DAILY_SYNC_JOB_ID

검증:
- disabled → no-op
- enabled → is_running=True, job_count=1
- job trigger = CronTrigger day_of_week=mon-fri hour=7 minute=0
- timezone = Asia/Seoul (KST)
- start 멱등
- shutdown 멱등
- alias 미설정 → fail-fast (settings alias)
- fire_sector_daily_sync 콜백 → execute 호출 1회
- fire_sector_daily_sync 예외 swallow (cron 연속성)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from typing import Any

import pytest
from apscheduler.triggers.cron import CronTrigger

from app.adapter.web._deps import IngestSectorDailyBulkUseCaseFactory
from app.application.service.sector_ohlcv_service import (
    IngestSectorDailyBulkUseCase,
    SectorBulkSyncResult,
)
from app.scheduler import (
    SECTOR_DAILY_SYNC_JOB_ID,
    SectorDailyOhlcvScheduler,
)


@asynccontextmanager
async def _dummy(_alias: str) -> AsyncIterator[None]:
    yield None


_dummy_factory: IngestSectorDailyBulkUseCaseFactory = _dummy  # type: ignore[assignment]


# ---------- disabled ----------


def test_sector_daily_disabled_no_op() -> None:
    """enabled=False → start 무시, job 등록 없음."""
    sched = SectorDailyOhlcvScheduler(factory=_dummy_factory, alias="t", enabled=False)
    sched.start()
    assert sched.is_running is False
    assert sched.job_count == 0
    sched.shutdown()


# ---------- enabled — cron 검증 ----------


@pytest.mark.asyncio
async def test_sector_daily_enabled_registers_mon_fri_07_00_kst() -> None:
    """plan § 12.2 #7 — CronTrigger mon-fri KST 07:00."""
    sched = SectorDailyOhlcvScheduler(factory=_dummy_factory, alias="t", enabled=True)
    sched.start()
    try:
        assert sched.is_running is True
        assert sched.job_count == 1

        job = sched.get_job(SECTOR_DAILY_SYNC_JOB_ID)
        assert job is not None
        trigger = job.trigger
        assert isinstance(trigger, CronTrigger)

        fields = {f.name: str(f) for f in trigger.fields}
        assert fields["day_of_week"] == "mon-fri", f"day_of_week 기대 mon-fri, 실제: {fields['day_of_week']}"
        assert fields["hour"] == "7", f"hour 기대 7, 실제: {fields['hour']}"
        assert fields["minute"] == "0", f"minute 기대 0, 실제: {fields['minute']}"
        # misfire_grace_time = 21600s (6h) — Mac 절전 catch-up (ADR § 42.5 옵션 C, plan § 3 #1)
        assert job.misfire_grace_time == 21600  # raw apscheduler Job int (not timedelta — _PhaseEJobView wrap 별도)
    finally:
        sched.shutdown()


@pytest.mark.asyncio
async def test_sector_daily_trigger_timezone_kst() -> None:
    """timezone = Asia/Seoul (KST) 적용 확인."""
    from zoneinfo import ZoneInfo

    sched = SectorDailyOhlcvScheduler(factory=_dummy_factory, alias="t", enabled=True)
    sched.start()
    try:
        job = sched.get_job(SECTOR_DAILY_SYNC_JOB_ID)
        assert job is not None
        trigger = job.trigger
        assert isinstance(trigger, CronTrigger)
        assert trigger.timezone == ZoneInfo("Asia/Seoul")
    finally:
        sched.shutdown()


# ---------- 멱등성 ----------


@pytest.mark.asyncio
async def test_sector_daily_start_idempotent() -> None:
    """start 두 번 호출 — job 중복 등록 없음."""
    sched = SectorDailyOhlcvScheduler(factory=_dummy_factory, alias="t", enabled=True)
    sched.start()
    sched.start()
    try:
        assert sched.job_count == 1
    finally:
        sched.shutdown()


@pytest.mark.asyncio
async def test_sector_daily_shutdown_idempotent() -> None:
    """shutdown 두 번 호출 — 안전."""
    sched = SectorDailyOhlcvScheduler(factory=_dummy_factory, alias="t", enabled=True)
    sched.start()
    sched.shutdown()
    sched.shutdown()
    assert sched.is_running is False


# ---------- fire 콜백 ----------


class _StubBulkUseCase:
    def __init__(self, result: SectorBulkSyncResult, *, raise_exc: Exception | None = None) -> None:
        self._result = result
        self._raise_exc = raise_exc
        self.call_count = 0
        self.last_kwargs: dict[str, Any] = {}

    async def execute(self, **kwargs: Any) -> SectorBulkSyncResult:
        self.call_count += 1
        self.last_kwargs = kwargs
        if self._raise_exc is not None:
            raise self._raise_exc
        return self._result


def _make_factory(uc: _StubBulkUseCase) -> IngestSectorDailyBulkUseCaseFactory:
    @asynccontextmanager
    async def _factory(_alias: str) -> AsyncIterator[IngestSectorDailyBulkUseCase]:
        yield uc  # type: ignore[misc]

    return _factory  # type: ignore[return-value]


def _ok_result(total: int = 5, success: int = 5) -> SectorBulkSyncResult:
    return SectorBulkSyncResult(
        total=total,
        success=success,
        failed=0,
        errors=(),
    )


@pytest.mark.asyncio
async def test_fire_sector_daily_sync_calls_execute() -> None:
    """fire_sector_daily_sync → use_case.execute 1회 호출."""
    from app.batch.sector_daily_ohlcv_job import fire_sector_daily_sync

    uc = _StubBulkUseCase(_ok_result())
    await fire_sector_daily_sync(factory=_make_factory(uc), alias="t")
    assert uc.call_count == 1


@pytest.mark.asyncio
async def test_fire_sector_daily_sync_swallows_exception() -> None:
    """cron 콜백은 모든 예외 swallow — 다음 tick 정상 동작 보장."""
    from app.batch.sector_daily_ohlcv_job import fire_sector_daily_sync

    uc = _StubBulkUseCase(_ok_result(), raise_exc=RuntimeError("boom"))
    # 예외 raise 안 함
    await fire_sector_daily_sync(factory=_make_factory(uc), alias="t")


@pytest.mark.asyncio
async def test_fire_sector_daily_sync_passes_base_date(monkeypatch: pytest.MonkeyPatch) -> None:
    """fire_sector_daily_sync 이 execute(base_date=오늘 또는 직전 영업일) 전달."""
    from app.batch import sector_daily_ohlcv_job

    class _FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return date(2026, 5, 12)  # Tuesday → 영업일

    monkeypatch.setattr(sector_daily_ohlcv_job, "date", _FixedDate)

    uc = _StubBulkUseCase(_ok_result())
    await sector_daily_ohlcv_job.fire_sector_daily_sync(factory=_make_factory(uc), alias="t")

    assert uc.call_count == 1
    # base_date 전달 확인 — execute 에 base_date 키워드가 있어야 함
    assert "base_date" in uc.last_kwargs
