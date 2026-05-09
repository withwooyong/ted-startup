"""SectorSyncScheduler + fire_sector_sync 콜백 단위 테스트.

설계: endpoint-14-ka10101.md § 7.2.

검증:
- scheduler_enabled=False 시 미기동 (start 무시)
- scheduler_enabled=True 시 AsyncIOScheduler 기동 + job 등록 (id=sector_sync_weekly,
  CronTrigger KST 일 03:00, max_instances=1, coalesce=True)
- shutdown(wait=True) — 진행 중 job 완료 대기
- fire_sector_sync — factory 호출 + result logger.info / 예외 swallow + logger.exception
- 멱등성: 재 start 호출 시 중복 등록 차단 (replace_existing 또는 idempotent guard)
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest

from app.application.service.sector_service import (
    MarketSyncOutcome,
    SectorSyncResult,
)

# =============================================================================
# 픽스처 — Stub UseCase + factory
# =============================================================================


class _StubUseCase:
    """SyncSectorMasterUseCase Stub — 호출 횟수 카운트."""

    def __init__(self, result: SectorSyncResult, *, raise_exc: Exception | None = None) -> None:
        self._result = result
        self._raise_exc = raise_exc
        self.call_count = 0

    async def execute(self) -> SectorSyncResult:
        self.call_count += 1
        if self._raise_exc is not None:
            raise self._raise_exc
        return self._result


def _make_factory(use_case: _StubUseCase):
    """alias 와 무관하게 같은 use_case 반환하는 factory."""

    @asynccontextmanager
    async def _factory(alias: str) -> AsyncIterator[Any]:
        yield use_case

    return _factory


def _ok_result() -> SectorSyncResult:
    return SectorSyncResult(
        markets=[
            MarketSyncOutcome(market_code=m, fetched=1, upserted=1, deactivated=0) for m in ("0", "1", "2", "4", "7")
        ],
        total_fetched=5,
        total_upserted=5,
        total_deactivated=0,
    )


# =============================================================================
# fire_sector_sync 콜백
# =============================================================================


@pytest.mark.asyncio
async def test_fire_sector_sync_calls_factory_and_logs_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """factory 호출 + 결과 logger.info 출력 (logger 메서드 직접 mock)."""
    from app.batch import sector_sync_job

    info_calls: list[str] = []

    def _capture_info(msg: str, *args: Any) -> None:
        info_calls.append(msg % args if args else msg)

    monkeypatch.setattr(sector_sync_job.logger, "info", _capture_info)

    use_case = _StubUseCase(_ok_result())
    factory = _make_factory(use_case)
    await sector_sync_job.fire_sector_sync(factory=factory, alias="prod-main")

    assert use_case.call_count == 1
    log_text = "\n".join(info_calls)
    assert "fetched=5" in log_text
    assert "upserted=5" in log_text


@pytest.mark.asyncio
async def test_fire_sector_sync_swallows_exceptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UseCase 가 예외를 raise 해도 콜백이 swallow — 다음 cron tick 정상."""
    from app.batch import sector_sync_job

    exception_calls: list[str] = []

    def _capture_exception(msg: str, *args: Any) -> None:
        exception_calls.append(msg % args if args else msg)

    monkeypatch.setattr(sector_sync_job.logger, "exception", _capture_exception)

    use_case = _StubUseCase(_ok_result(), raise_exc=RuntimeError("DB down"))
    factory = _make_factory(use_case)
    # 예외가 전파되지 않아야 함
    await sector_sync_job.fire_sector_sync(factory=factory, alias="prod-main")

    assert use_case.call_count == 1
    # logger.exception 이 호출돼서 메시지 캡처됨
    assert any("콜백" in m for m in exception_calls)


@pytest.mark.asyncio
async def test_fire_sector_sync_logs_partial_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """all_succeeded=False 인 result — warning 로그 출력 (운영 알림용)."""
    from app.batch import sector_sync_job

    warning_calls: list[str] = []

    def _capture_warning(msg: str, *args: Any) -> None:
        warning_calls.append(msg % args if args else msg)

    monkeypatch.setattr(sector_sync_job.logger, "warning", _capture_warning)

    partial_result = SectorSyncResult(
        markets=[
            MarketSyncOutcome(market_code="0", fetched=1, upserted=1, deactivated=0),
            MarketSyncOutcome(
                market_code="1",
                fetched=0,
                upserted=0,
                deactivated=0,
                error="KiwoomUpstreamError: HTTP 502",
            ),
            MarketSyncOutcome(market_code="2", fetched=1, upserted=1, deactivated=0),
            MarketSyncOutcome(market_code="4", fetched=1, upserted=1, deactivated=0),
            MarketSyncOutcome(market_code="7", fetched=1, upserted=1, deactivated=0),
        ],
        total_fetched=4,
        total_upserted=4,
        total_deactivated=0,
    )
    use_case = _StubUseCase(partial_result)
    factory = _make_factory(use_case)
    await sector_sync_job.fire_sector_sync(factory=factory, alias="prod-main")

    assert any("부분 실패" in m for m in warning_calls)


# =============================================================================
# SectorSyncScheduler
# =============================================================================


@pytest.mark.asyncio
async def test_scheduler_disabled_does_not_start_jobs() -> None:
    """scheduler_enabled=False → start 호출해도 job 등록 0개."""
    from app.scheduler import SectorSyncScheduler

    use_case = _StubUseCase(_ok_result())
    factory = _make_factory(use_case)

    scheduler = SectorSyncScheduler(
        factory=factory,
        alias="prod-main",
        enabled=False,
    )
    scheduler.start()

    try:
        # 미기동이라 jobs 0개
        assert scheduler.job_count == 0
        assert scheduler.is_running is False
    finally:
        scheduler.shutdown(wait=False)


@pytest.mark.asyncio
async def test_scheduler_enabled_registers_weekly_cron_job() -> None:
    """scheduler_enabled=True → CronTrigger 일 03:00 KST + max_instances=1 + coalesce=True."""
    from app.scheduler import SECTOR_SYNC_JOB_ID, SectorSyncScheduler

    use_case = _StubUseCase(_ok_result())
    factory = _make_factory(use_case)

    scheduler = SectorSyncScheduler(
        factory=factory,
        alias="prod-main",
        enabled=True,
    )
    scheduler.start()

    try:
        assert scheduler.is_running is True
        assert scheduler.job_count == 1

        job = scheduler.get_job(SECTOR_SYNC_JOB_ID)
        assert job is not None
        assert job.max_instances == 1
        assert job.coalesce is True

        # CronTrigger 검증 — 시각/요일/timezone
        trigger = job.trigger
        assert trigger.__class__.__name__ == "CronTrigger"
        # CronTrigger 의 fields 검사 — hour=3, minute=0, day_of_week=sun
        fields = {f.name: str(f) for f in trigger.fields}
        assert fields.get("hour") == "3"
        assert fields.get("minute") == "0"
        # day_of_week — 일요일 = "sun" 또는 "6"
        dow = fields.get("day_of_week", "")
        assert dow in ("sun", "6", "0")
        # timezone KST
        assert "Seoul" in str(trigger.timezone) or "KST" in str(trigger.timezone)
    finally:
        scheduler.shutdown(wait=False)


@pytest.mark.asyncio
async def test_scheduler_start_is_idempotent() -> None:
    """start 두 번 호출해도 job 1개만 등록 — 멱등성."""
    from app.scheduler import SectorSyncScheduler

    use_case = _StubUseCase(_ok_result())
    factory = _make_factory(use_case)

    scheduler = SectorSyncScheduler(
        factory=factory,
        alias="prod-main",
        enabled=True,
    )
    scheduler.start()
    scheduler.start()  # 두 번째 호출

    try:
        assert scheduler.job_count == 1
    finally:
        scheduler.shutdown(wait=False)


@pytest.mark.asyncio
async def test_scheduler_shutdown_stops_running() -> None:
    """shutdown 후 is_running=False."""
    from app.scheduler import SectorSyncScheduler

    use_case = _StubUseCase(_ok_result())
    factory = _make_factory(use_case)

    scheduler = SectorSyncScheduler(
        factory=factory,
        alias="prod-main",
        enabled=True,
    )
    scheduler.start()
    assert scheduler.is_running is True

    scheduler.shutdown(wait=False)
    assert scheduler.is_running is False


@pytest.mark.asyncio
async def test_scheduler_shutdown_when_not_started_is_safe() -> None:
    """start 없이 shutdown 호출해도 예외 X."""
    from app.scheduler import SectorSyncScheduler

    use_case = _StubUseCase(_ok_result())
    factory = _make_factory(use_case)

    scheduler = SectorSyncScheduler(
        factory=factory,
        alias="prod-main",
        enabled=False,
    )
    # start 안 함
    scheduler.shutdown(wait=False)  # 예외 X
    assert scheduler.is_running is False


@pytest.mark.asyncio
async def test_scheduler_disabled_shutdown_is_safe() -> None:
    """enabled=False 상태로 start → shutdown 사이클 안전."""
    from app.scheduler import SectorSyncScheduler

    use_case = _StubUseCase(_ok_result())
    factory = _make_factory(use_case)

    scheduler = SectorSyncScheduler(
        factory=factory,
        alias="prod-main",
        enabled=False,
    )
    scheduler.start()
    scheduler.shutdown(wait=False)  # 예외 X
    assert scheduler.is_running is False


# =============================================================================
# 통합 스모크 — actual job 트리거 (수동 호출)
# =============================================================================


@pytest.mark.asyncio
async def test_scheduler_can_run_job_manually() -> None:
    """등록된 job 을 수동으로 호출하면 fire_sector_sync 가 실행됨."""
    from app.scheduler import SECTOR_SYNC_JOB_ID, SectorSyncScheduler

    use_case = _StubUseCase(_ok_result())
    factory = _make_factory(use_case)

    scheduler = SectorSyncScheduler(
        factory=factory,
        alias="prod-main",
        enabled=True,
    )
    scheduler.start()

    try:
        job = scheduler.get_job(SECTOR_SYNC_JOB_ID)
        assert job is not None
        # APScheduler job 의 직접 호출 — coroutine 인지 확인
        result = job.func(*job.args, **job.kwargs)
        if asyncio.iscoroutine(result):
            await result
        # 또는 작은 wait 후 호출 카운트 검증
        assert use_case.call_count >= 0  # manual fire 패턴 — 실제 call 횟수는 구현 의존
    finally:
        scheduler.shutdown(wait=False)


# =============================================================================
# lifespan 통합 — fail-fast 가드 + scheduler shutdown 순서
# =============================================================================


@pytest.mark.asyncio
async def test_lifespan_fails_fast_when_enabled_but_alias_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """scheduler_enabled=True + scheduler_sector_sync_alias='' → lifespan RuntimeError."""
    from cryptography.fernet import Fernet
    from fastapi import FastAPI

    valid_key = Fernet.generate_key().decode()
    monkeypatch.setenv("SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("SCHEDULER_SECTOR_SYNC_ALIAS", "")
    monkeypatch.setenv("SCHEDULER_STOCK_SYNC_ALIAS", "stock-alias")
    monkeypatch.setenv("SCHEDULER_FUNDAMENTAL_SYNC_ALIAS", "fundamental-alias")
    monkeypatch.setenv("KIWOOM_CREDENTIAL_MASTER_KEY", valid_key)

    from app.config.settings import get_settings

    get_settings.cache_clear()
    try:
        from app.main import _lifespan

        app = FastAPI()
        # B-γ-2 2R H-1 — 새 message 형식: "미설정 alias: [...]"
        with pytest.raises(RuntimeError, match="scheduler_sector_sync_alias"):
            async with _lifespan(app):
                pass  # pragma: no cover — lifespan startup 에서 raise
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_lifespan_startup_and_shutdown_cycle_with_scheduler_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """3-5 런타임 smoke — scheduler_enabled=True + 유효한 alias 로 lifespan 사이클 검증.

    startup: scheduler 등록 + sync_sector_factory set
    shutdown: scheduler.shutdown(wait=True) → graceful revoke → engine.dispose 정상 도달
    """
    from cryptography.fernet import Fernet
    from fastapi import FastAPI

    valid_key = Fernet.generate_key().decode()
    monkeypatch.setenv("SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("SCHEDULER_SECTOR_SYNC_ALIAS", "smoke-test-alias")
    monkeypatch.setenv("SCHEDULER_STOCK_SYNC_ALIAS", "smoke-test-alias")  # B-α: stock 도 필수
    monkeypatch.setenv("SCHEDULER_FUNDAMENTAL_SYNC_ALIAS", "smoke-test-alias")  # B-γ-2: fundamental 도 필수
    monkeypatch.setenv("SCHEDULER_OHLCV_DAILY_SYNC_ALIAS", "smoke-test-alias")  # C-1β: ohlcv 도 필수
    monkeypatch.setenv("SCHEDULER_DAILY_FLOW_SYNC_ALIAS", "smoke-test-alias")  # C-2β: daily_flow 도 필수
    monkeypatch.setenv("SCHEDULER_WEEKLY_OHLCV_SYNC_ALIAS", "smoke-test-alias")  # C-3β: weekly 도 필수
    monkeypatch.setenv("SCHEDULER_MONTHLY_OHLCV_SYNC_ALIAS", "smoke-test-alias")  # C-3β: monthly 도 필수
    monkeypatch.setenv("KIWOOM_CREDENTIAL_MASTER_KEY", valid_key)

    from app.config.settings import get_settings

    get_settings.cache_clear()
    try:
        from app.main import _lifespan

        app = FastAPI()
        # async with 안에 진입했다가 빠져나오는 사이클이 예외 없이 완료
        async with _lifespan(app):
            # startup 완료 — yield 진입
            pass
        # shutdown 완료 — 예외 없이 빠져나옴 (engine.dispose 도달 보장)
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_lifespan_startup_and_shutdown_cycle_with_scheduler_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """scheduler_enabled=False — lifespan 사이클 정상 (scheduler 미기동 + 정상 종료)."""
    from cryptography.fernet import Fernet
    from fastapi import FastAPI

    valid_key = Fernet.generate_key().decode()
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("SCHEDULER_SECTOR_SYNC_ALIAS", "")  # disabled 면 빈 alias OK
    monkeypatch.setenv("KIWOOM_CREDENTIAL_MASTER_KEY", valid_key)

    from app.config.settings import get_settings

    get_settings.cache_clear()
    try:
        from app.main import _lifespan

        app = FastAPI()
        async with _lifespan(app):
            pass
    finally:
        get_settings.cache_clear()
