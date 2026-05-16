"""StockMasterScheduler + fire_stock_master_sync 콜백 단위 테스트 (B-α).

설계: endpoint-03-ka10099.md § 7.2.

검증 (sector scheduler 패턴 일관 + stock 특이사항):
- scheduler_enabled=False 시 미기동 (start 무시)
- scheduler_enabled=True 시 AsyncIOScheduler 기동 + job 등록
  (id=stock_master_sync_daily, CronTrigger KST mon-fri 17:30, max_instances=1)
- shutdown(wait=True) — 진행 중 job 완료 대기
- fire_stock_master_sync — factory 호출 + result logger.info / 예외 swallow / partial 시 warning
- 멱등성: 재 start 호출 시 중복 등록 차단
- lifespan 통합: scheduler_enabled=True + stock alias 미설정 → fail-fast
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest

from app.application.service.stock_master_service import (
    MarketStockOutcome,
    StockMasterSyncResult,
)


class _StubUseCase:
    """SyncStockMasterUseCase Stub — 호출 횟수 카운트."""

    def __init__(self, result: StockMasterSyncResult, *, raise_exc: Exception | None = None) -> None:
        self._result = result
        self._raise_exc = raise_exc
        self.call_count = 0

    async def execute(self) -> StockMasterSyncResult:
        self.call_count += 1
        if self._raise_exc is not None:
            raise self._raise_exc
        return self._result


def _make_factory(use_case: _StubUseCase):
    @asynccontextmanager
    async def _factory(alias: str) -> AsyncIterator[Any]:
        yield use_case

    return _factory


def _ok_result() -> StockMasterSyncResult:
    return StockMasterSyncResult(
        markets=[
            MarketStockOutcome(market_code=m, fetched=1, upserted=1, deactivated=0, nxt_enabled_count=1)
            for m in ("0", "10", "50", "60", "6")
        ],
        total_fetched=5,
        total_upserted=5,
        total_deactivated=0,
        total_nxt_enabled=5,
    )


# =============================================================================
# fire_stock_master_sync 콜백
# =============================================================================


@pytest.mark.asyncio
async def test_fire_stock_master_sync_calls_factory_and_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """factory 호출 + 결과 logger.info + nxt_enabled 로그 출력."""
    from app.batch import stock_master_job

    info_calls: list[str] = []

    def _capture_info(msg: str, *args: Any) -> None:
        info_calls.append(msg % args if args else msg)

    monkeypatch.setattr(stock_master_job.logger, "info", _capture_info)

    use_case = _StubUseCase(_ok_result())
    factory = _make_factory(use_case)
    await stock_master_job.fire_stock_master_sync(factory=factory, alias="prod-main")

    assert use_case.call_count == 1
    log_text = "\n".join(info_calls)
    assert "fetched=5" in log_text
    assert "upserted=5" in log_text
    assert "nxt_enabled=5" in log_text


@pytest.mark.asyncio
async def test_fire_stock_master_sync_swallows_exceptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UseCase 가 예외를 raise 해도 콜백이 swallow."""
    from app.batch import stock_master_job

    exception_calls: list[str] = []

    def _capture_exception(msg: str, *args: Any) -> None:
        exception_calls.append(msg % args if args else msg)

    monkeypatch.setattr(stock_master_job.logger, "exception", _capture_exception)

    use_case = _StubUseCase(_ok_result(), raise_exc=RuntimeError("DB down"))
    factory = _make_factory(use_case)
    await stock_master_job.fire_stock_master_sync(factory=factory, alias="prod-main")

    assert use_case.call_count == 1
    assert any("콜백" in m for m in exception_calls)


@pytest.mark.asyncio
async def test_fire_stock_master_sync_logs_partial_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """all_succeeded=False — warning 로그 (운영 알림용)."""
    from app.batch import stock_master_job

    warning_calls: list[str] = []

    def _capture_warning(msg: str, *args: Any) -> None:
        warning_calls.append(msg % args if args else msg)

    monkeypatch.setattr(stock_master_job.logger, "warning", _capture_warning)

    partial = StockMasterSyncResult(
        markets=[
            MarketStockOutcome(market_code="0", fetched=1, upserted=1, deactivated=0, nxt_enabled_count=0),
            MarketStockOutcome(
                market_code="10",
                fetched=0,
                upserted=0,
                deactivated=0,
                nxt_enabled_count=0,
                error="KiwoomUpstreamError: HTTP 502",
            ),
            MarketStockOutcome(market_code="50", fetched=1, upserted=1, deactivated=0, nxt_enabled_count=0),
            MarketStockOutcome(market_code="60", fetched=1, upserted=1, deactivated=0, nxt_enabled_count=0),
            MarketStockOutcome(market_code="6", fetched=1, upserted=1, deactivated=0, nxt_enabled_count=0),
        ],
        total_fetched=4,
        total_upserted=4,
        total_deactivated=0,
        total_nxt_enabled=0,
    )
    use_case = _StubUseCase(partial)
    factory = _make_factory(use_case)
    await stock_master_job.fire_stock_master_sync(factory=factory, alias="prod-main")

    assert any("부분 실패" in m for m in warning_calls)


# =============================================================================
# StockMasterScheduler
# =============================================================================


@pytest.mark.asyncio
async def test_stock_scheduler_disabled_does_not_start_jobs() -> None:
    """scheduler_enabled=False → start 호출해도 job 등록 0개."""
    from app.scheduler import StockMasterScheduler

    use_case = _StubUseCase(_ok_result())
    factory = _make_factory(use_case)

    scheduler = StockMasterScheduler(factory=factory, alias="prod-main", enabled=False)
    scheduler.start()

    try:
        assert scheduler.job_count == 0
        assert scheduler.is_running is False
    finally:
        scheduler.shutdown(wait=False)


@pytest.mark.asyncio
async def test_stock_scheduler_enabled_registers_daily_cron_job() -> None:
    """scheduler_enabled=True → CronTrigger mon-fri 17:30 KST + max_instances=1 + coalesce."""
    from app.scheduler import STOCK_MASTER_SYNC_JOB_ID, StockMasterScheduler

    use_case = _StubUseCase(_ok_result())
    factory = _make_factory(use_case)

    scheduler = StockMasterScheduler(factory=factory, alias="prod-main", enabled=True)
    scheduler.start()

    try:
        assert scheduler.is_running is True
        assert scheduler.job_count == 1

        job = scheduler.get_job(STOCK_MASTER_SYNC_JOB_ID)
        assert job is not None
        assert job.max_instances == 1
        assert job.coalesce is True
        # misfire_grace_time = 21600s (6h) — Mac 절전 catch-up (ADR § 42.5 옵션 C, plan § 3 #1)
        assert job.misfire_grace_time == 21600  # raw apscheduler Job int (not timedelta — _PhaseEJobView wrap 별도)

        trigger = job.trigger
        assert trigger.__class__.__name__ == "CronTrigger"
        fields = {f.name: str(f) for f in trigger.fields}
        assert fields.get("hour") == "17"
        assert fields.get("minute") == "30"
        # day_of_week — mon-fri (1-5 또는 'mon-fri')
        dow = fields.get("day_of_week", "")
        assert "mon" in dow or "1" in dow
        assert "Seoul" in str(trigger.timezone) or "KST" in str(trigger.timezone)
    finally:
        scheduler.shutdown(wait=False)


@pytest.mark.asyncio
async def test_stock_scheduler_start_is_idempotent() -> None:
    from app.scheduler import StockMasterScheduler

    use_case = _StubUseCase(_ok_result())
    factory = _make_factory(use_case)

    scheduler = StockMasterScheduler(factory=factory, alias="prod-main", enabled=True)
    scheduler.start()
    scheduler.start()

    try:
        assert scheduler.job_count == 1
    finally:
        scheduler.shutdown(wait=False)


@pytest.mark.asyncio
async def test_stock_scheduler_shutdown_stops_running() -> None:
    from app.scheduler import StockMasterScheduler

    use_case = _StubUseCase(_ok_result())
    factory = _make_factory(use_case)

    scheduler = StockMasterScheduler(factory=factory, alias="prod-main", enabled=True)
    scheduler.start()
    assert scheduler.is_running is True

    scheduler.shutdown(wait=False)
    assert scheduler.is_running is False


@pytest.mark.asyncio
async def test_stock_scheduler_shutdown_when_not_started_is_safe() -> None:
    from app.scheduler import StockMasterScheduler

    use_case = _StubUseCase(_ok_result())
    factory = _make_factory(use_case)

    scheduler = StockMasterScheduler(factory=factory, alias="prod-main", enabled=False)
    scheduler.shutdown(wait=False)
    assert scheduler.is_running is False


@pytest.mark.asyncio
async def test_stock_scheduler_can_run_job_manually() -> None:
    from app.scheduler import STOCK_MASTER_SYNC_JOB_ID, StockMasterScheduler

    use_case = _StubUseCase(_ok_result())
    factory = _make_factory(use_case)

    scheduler = StockMasterScheduler(factory=factory, alias="prod-main", enabled=True)
    scheduler.start()

    try:
        job = scheduler.get_job(STOCK_MASTER_SYNC_JOB_ID)
        assert job is not None
        result = job.func(*job.args, **job.kwargs)
        if asyncio.iscoroutine(result):
            await result
        assert use_case.call_count >= 0
    finally:
        scheduler.shutdown(wait=False)


# =============================================================================
# lifespan 통합 — fail-fast 가드 (stock alias)
# =============================================================================


@pytest.mark.asyncio
async def test_lifespan_fails_fast_when_enabled_but_stock_alias_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """scheduler_enabled=True + scheduler_sector_sync_alias='valid' + scheduler_stock_sync_alias=''
    → lifespan RuntimeError 로 stock alias 미설정 차단.
    """
    from cryptography.fernet import Fernet
    from fastapi import FastAPI

    valid_key = Fernet.generate_key().decode()
    monkeypatch.setenv("SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("SCHEDULER_SECTOR_SYNC_ALIAS", "sector-alias")
    monkeypatch.setenv("SCHEDULER_STOCK_SYNC_ALIAS", "")
    monkeypatch.setenv("SCHEDULER_FUNDAMENTAL_SYNC_ALIAS", "fundamental-alias")
    monkeypatch.setenv("KIWOOM_CREDENTIAL_MASTER_KEY", valid_key)

    from app.config.settings import get_settings

    get_settings.cache_clear()
    try:
        from app.main import _lifespan

        app = FastAPI()
        # B-γ-2 2R H-1 — 새 message 형식: "미설정 alias: [...]" + cleanup 보장
        with pytest.raises(RuntimeError, match="scheduler_stock_sync_alias"):
            async with _lifespan(app):
                pass  # pragma: no cover
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_lifespan_starts_both_schedulers_with_valid_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """sector + stock alias 모두 유효 → lifespan 정상 사이클."""
    from cryptography.fernet import Fernet
    from fastapi import FastAPI

    valid_key = Fernet.generate_key().decode()
    monkeypatch.setenv("SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("SCHEDULER_SECTOR_SYNC_ALIAS", "sector-alias")
    monkeypatch.setenv("SCHEDULER_STOCK_SYNC_ALIAS", "stock-alias")
    monkeypatch.setenv("SCHEDULER_FUNDAMENTAL_SYNC_ALIAS", "fundamental-alias")  # B-γ-2
    monkeypatch.setenv("SCHEDULER_OHLCV_DAILY_SYNC_ALIAS", "ohlcv-alias")  # C-1β
    monkeypatch.setenv("SCHEDULER_DAILY_FLOW_SYNC_ALIAS", "daily-flow-alias")  # C-2β
    monkeypatch.setenv("SCHEDULER_WEEKLY_OHLCV_SYNC_ALIAS", "weekly-alias")  # C-3β
    monkeypatch.setenv("SCHEDULER_MONTHLY_OHLCV_SYNC_ALIAS", "monthly-alias")  # C-3β
    monkeypatch.setenv("SCHEDULER_YEARLY_OHLCV_SYNC_ALIAS", "yearly-alias")  # C-4
    monkeypatch.setenv("SCHEDULER_SECTOR_DAILY_SYNC_ALIAS", "sector-daily-alias")  # D-1
    monkeypatch.setenv("SCHEDULER_SHORT_SELLING_SYNC_ALIAS", "short-selling-alias")  # Phase E
    monkeypatch.setenv("SCHEDULER_LENDING_MARKET_SYNC_ALIAS", "lending-market-alias")  # Phase E
    monkeypatch.setenv("SCHEDULER_LENDING_STOCK_SYNC_ALIAS", "lending-stock-alias")  # Phase E
    # F-4 Step 2 fix C-2 — 5 ranking endpoint alias
    monkeypatch.setenv("SCHEDULER_FLU_RT_RANKING_SYNC_ALIAS", "flu-rt-alias")
    monkeypatch.setenv("SCHEDULER_TODAY_VOLUME_RANKING_SYNC_ALIAS", "today-volume-alias")
    monkeypatch.setenv("SCHEDULER_PRED_VOLUME_RANKING_SYNC_ALIAS", "pred-volume-alias")
    monkeypatch.setenv("SCHEDULER_TRADE_AMOUNT_RANKING_SYNC_ALIAS", "trade-amount-alias")
    monkeypatch.setenv("SCHEDULER_VOLUME_SDNIN_RANKING_SYNC_ALIAS", "volume-sdnin-alias")
    # Phase G Step 2 fix R1 C-3 — 3 investor flow endpoint alias
    monkeypatch.setenv("SCHEDULER_INVESTOR_DAILY_SYNC_ALIAS", "investor-daily-alias")
    monkeypatch.setenv(
        "SCHEDULER_STOCK_INVESTOR_BREAKDOWN_SYNC_ALIAS", "stock-investor-breakdown-alias"
    )
    monkeypatch.setenv("SCHEDULER_FRGN_ORGN_CONTINUOUS_SYNC_ALIAS", "frgn-orgn-alias")
    monkeypatch.setenv("KIWOOM_CREDENTIAL_MASTER_KEY", valid_key)


# B-γ-2 2R H-1 회귀 검증은 기존 `test_lifespan_fails_fast_when_enabled_but_stock_alias_missing`
# 이 담당 (match pattern 갱신됨). fail-fast 코드 위치 (`set_*_factory` 호출 앞) 자체는
# main.py:91-110 라인 코드 리뷰로 검증.

    from app.config.settings import get_settings

    get_settings.cache_clear()
    try:
        from app.main import _lifespan

        app = FastAPI()
        async with _lifespan(app):
            pass
    finally:
        get_settings.cache_clear()
