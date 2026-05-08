"""DailyFlowScheduler + fire_daily_flow_sync 콜백 (C-2β).

설계: endpoint-10-ka10086.md § 7.2 + ADR § 18.x (cron 19:00 결정 — ohlcv 18:30 의 30분 후).

검증 (OhlcvDailyScheduler 패턴 일관):
- enabled=False → start no-op
- enabled=True → job 1개 등록 (mon-fri 19:00 KST)
- start 멱등성
- shutdown 멱등성
- cron field 검증

fire_daily_flow_sync 콜백 (C-1β 2a-M3 패턴 일관):
- 정상 완료 logger.info
- 예외 swallow (cron 연속성)
- 실패율 > 10% logger.error 알람
- 부분 실패 (failed > 0 + ratio <= 10%) logger.warning
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from typing import Any

import pytest
from apscheduler.triggers.cron import CronTrigger

from app.adapter.web._deps import IngestDailyFlowUseCaseFactory
from app.application.service.daily_flow_service import (
    DailyFlowSyncOutcome,
    DailyFlowSyncResult,
    IngestDailyFlowUseCase,
)
from app.scheduler import (
    DAILY_FLOW_SYNC_JOB_ID,
    KST,
    DailyFlowScheduler,
)


@asynccontextmanager
async def _dummy(_alias: str) -> AsyncIterator[None]:
    yield None


_dummy_factory: IngestDailyFlowUseCaseFactory = _dummy  # type: ignore[assignment]


# =============================================================================
# fire_daily_flow_sync 콜백
# =============================================================================


class _StubUseCase:
    """IngestDailyFlowUseCase stub — execute 호출 카운트 + 결과 / 예외 제어."""

    def __init__(self, result: DailyFlowSyncResult, *, raise_exc: Exception | None = None) -> None:
        self._result = result
        self._raise_exc = raise_exc
        self.call_count = 0

    async def execute(self, **_: Any) -> DailyFlowSyncResult:
        self.call_count += 1
        if self._raise_exc is not None:
            raise self._raise_exc
        return self._result


def _make_factory(uc: _StubUseCase) -> Any:
    @asynccontextmanager
    async def _factory(_alias: str) -> AsyncIterator[IngestDailyFlowUseCase]:
        yield uc  # type: ignore[misc]

    return _factory


def _ok_result(total: int = 5, success_krx: int = 5, failed: int = 0) -> DailyFlowSyncResult:
    return DailyFlowSyncResult(
        base_date=date(2025, 9, 8),
        total=total,
        success_krx=success_krx,
        success_nxt=0,
        failed=failed,
        errors=[],
    )


@pytest.mark.asyncio
async def test_fire_daily_flow_sync_calls_factory_and_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """factory 호출 + 결과 logger.info."""
    from app.batch import daily_flow_job

    info_calls: list[str] = []

    def _capture_info(msg: str, *args: Any) -> None:
        info_calls.append(msg % args if args else msg)

    monkeypatch.setattr(daily_flow_job.logger, "info", _capture_info)

    use_case = _StubUseCase(_ok_result())
    factory = _make_factory(use_case)
    await daily_flow_job.fire_daily_flow_sync(factory=factory, alias="prod-main")

    assert use_case.call_count == 1
    log_text = "\n".join(info_calls)
    assert "total=5" in log_text
    assert "krx=5" in log_text


@pytest.mark.asyncio
async def test_fire_daily_flow_sync_swallows_exceptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UseCase 예외 → 콜백 swallow (cron 다음 tick 정상 동작)."""
    from app.batch import daily_flow_job

    exception_calls: list[str] = []

    def _capture_exception(msg: str, *args: Any) -> None:
        exception_calls.append(msg % args if args else msg)

    monkeypatch.setattr(daily_flow_job.logger, "exception", _capture_exception)

    use_case = _StubUseCase(_ok_result(), raise_exc=RuntimeError("DB down"))
    factory = _make_factory(use_case)
    await daily_flow_job.fire_daily_flow_sync(factory=factory, alias="prod-main")

    assert use_case.call_count == 1
    assert any("콜백" in m for m in exception_calls)


@pytest.mark.asyncio
async def test_fire_daily_flow_sync_logs_high_failure_ratio_as_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """실패율 > 10% → logger.error (oncall 알람)."""
    from app.batch import daily_flow_job

    error_calls: list[str] = []

    def _capture_error(msg: str, *args: Any) -> None:
        error_calls.append(msg % args if args else msg)

    monkeypatch.setattr(daily_flow_job.logger, "error", _capture_error)

    # total=10, failed=5 → ratio 0.5 > 0.10
    high_fail = DailyFlowSyncResult(
        base_date=date(2025, 9, 8),
        total=10,
        success_krx=5,
        success_nxt=0,
        failed=5,
        errors=[
            DailyFlowSyncOutcome(stock_code=f"00000{i}", exchange="KRX", error_class="KiwoomBusinessError")
            for i in range(5)
        ],
    )
    use_case = _StubUseCase(high_fail)
    factory = _make_factory(use_case)
    await daily_flow_job.fire_daily_flow_sync(factory=factory, alias="prod-main")

    assert any("실패율 과다" in m for m in error_calls)


@pytest.mark.asyncio
async def test_fire_daily_flow_sync_logs_low_failure_ratio_as_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """실패율 <= 10% 이지만 failed > 0 → logger.warning."""
    from app.batch import daily_flow_job

    warning_calls: list[str] = []

    def _capture_warning(msg: str, *args: Any) -> None:
        warning_calls.append(msg % args if args else msg)

    monkeypatch.setattr(daily_flow_job.logger, "warning", _capture_warning)

    # total=100, failed=5 → ratio 0.05 <= 0.10
    partial = DailyFlowSyncResult(
        base_date=date(2025, 9, 8),
        total=100,
        success_krx=95,
        success_nxt=0,
        failed=5,
        errors=[
            DailyFlowSyncOutcome(stock_code=f"00000{i}", exchange="KRX", error_class="KiwoomBusinessError")
            for i in range(5)
        ],
    )
    use_case = _StubUseCase(partial)
    factory = _make_factory(use_case)
    await daily_flow_job.fire_daily_flow_sync(factory=factory, alias="prod-main")

    assert any("부분 실패" in m for m in warning_calls)


# =============================================================================
# DailyFlowScheduler — 5 cases
# =============================================================================


@pytest.mark.asyncio
async def test_scheduler_disabled_start_is_noop() -> None:
    sched = DailyFlowScheduler(factory=_dummy_factory, alias="test", enabled=False)
    sched.start()
    assert sched.is_running is False
    assert sched.job_count == 0


@pytest.mark.asyncio
async def test_scheduler_enabled_registers_one_cron_job() -> None:
    sched = DailyFlowScheduler(factory=_dummy_factory, alias="prod-main", enabled=True)
    try:
        sched.start()
        assert sched.is_running is True
        assert sched.job_count == 1
        job = sched.get_job(DAILY_FLOW_SYNC_JOB_ID)
        assert job is not None
        assert isinstance(job.trigger, CronTrigger)
        assert job.trigger.timezone == KST
    finally:
        sched.shutdown(wait=False)


@pytest.mark.asyncio
async def test_scheduler_start_is_idempotent() -> None:
    sched = DailyFlowScheduler(factory=_dummy_factory, alias="prod-main", enabled=True)
    try:
        sched.start()
        sched.start()
        assert sched.job_count == 1
    finally:
        sched.shutdown(wait=False)


@pytest.mark.asyncio
async def test_scheduler_shutdown_safe_when_not_started() -> None:
    sched = DailyFlowScheduler(factory=_dummy_factory, alias="prod-main", enabled=True)
    sched.shutdown(wait=False)
    assert sched.is_running is False


@pytest.mark.asyncio
async def test_scheduler_job_uses_19_00_kst_mon_fri_cron() -> None:
    sched = DailyFlowScheduler(factory=_dummy_factory, alias="prod-main", enabled=True)
    try:
        sched.start()
        job = sched.get_job(DAILY_FLOW_SYNC_JOB_ID)
        assert job is not None
        fields_by_name = {f.name: f for f in job.trigger.fields}
        assert str(fields_by_name["hour"]) == "19"
        assert str(fields_by_name["minute"]) == "0"
        assert str(fields_by_name["day_of_week"]) == "mon-fri"
    finally:
        sched.shutdown(wait=False)
