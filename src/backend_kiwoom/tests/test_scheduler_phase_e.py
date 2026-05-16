"""Phase E Scheduler 검증 — short_selling_sync_daily / lending_market_sync_daily / lending_stock_sync_daily.

chunk = Phase E, plan doc § 12.2 결정 #5 / #8 참조.

test_scheduler_sector_daily.py (D-1) 패턴 1:1 응용.

결정 (plan § 12.2):
- #5 cron 시간 — short_selling 07:30 / lending_market 07:45 / lending_stock 08:00 KST mon-fri
- #8 scheduler_enabled 3 env 신규 + 3 alias env 신규 (§ 36 fail-fast 정책 일관)

검증:
- 3 job 등록 (job id 확인)
- CronTrigger 시간 (각 hour/minute/day_of_week/timezone)
- alias fail-fast — SHORT_SELLING / LENDING_MARKET / LENDING_STOCK 각각
- enabled false — 해당 job 미등록 / 나머지 2 job 등록 여부
- max_instances=1 + coalesce=True + misfire_grace_time (lending_stock 90분, 나머지 30분)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from apscheduler.triggers.cron import CronTrigger

# ---------------------------------------------------------------------------
# Stub factories — 구현 없는 상태에서도 스케줄러 단위 테스트 가능
# ---------------------------------------------------------------------------

_KST = ZoneInfo("Asia/Seoul")


@asynccontextmanager
async def _dummy_ctx(_alias: str) -> AsyncIterator[None]:
    yield None


# Phase E scheduler constants — 미구현 상태에서 ImportError 발생 예정 (red)
_SHORT_SELLING_JOB_ID = "short_selling_sync_daily"
_LENDING_MARKET_JOB_ID = "lending_market_sync_daily"
_LENDING_STOCK_JOB_ID = "lending_stock_sync_daily"


# ---------------------------------------------------------------------------
# Scenario 1 — 3 job 등록 확인
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_phase_e_all_three_jobs_registered_when_enabled() -> None:
    """enabled=True 시 short_selling_sync_daily / lending_market_sync_daily / lending_stock_sync_daily 모두 등록."""
    from app.scheduler import (  # type: ignore[attr-defined]  # red: 미구현
        LENDING_MARKET_SYNC_JOB_ID,
        LENDING_STOCK_SYNC_JOB_ID,
        SHORT_SELLING_SYNC_JOB_ID,
        LendingMarketScheduler,
        LendingStockScheduler,
        ShortSellingScheduler,
    )

    ss_sched = ShortSellingScheduler(
        factory=_dummy_ctx,  # type: ignore[arg-type]
        alias="t",
        enabled=True,
    )
    lm_sched = LendingMarketScheduler(
        factory=_dummy_ctx,  # type: ignore[arg-type]
        alias="t",
        enabled=True,
    )
    ls_sched = LendingStockScheduler(
        factory=_dummy_ctx,  # type: ignore[arg-type]
        alias="t",
        enabled=True,
    )

    ss_sched.start()
    lm_sched.start()
    ls_sched.start()
    try:
        assert ss_sched.job_count == 1, "short_selling job 미등록"
        assert lm_sched.job_count == 1, "lending_market job 미등록"
        assert ls_sched.job_count == 1, "lending_stock job 미등록"

        assert ss_sched.get_job(SHORT_SELLING_SYNC_JOB_ID) is not None
        assert lm_sched.get_job(LENDING_MARKET_SYNC_JOB_ID) is not None
        assert ls_sched.get_job(LENDING_STOCK_SYNC_JOB_ID) is not None
    finally:
        ss_sched.shutdown()
        lm_sched.shutdown()
        ls_sched.shutdown()


# ---------------------------------------------------------------------------
# Scenario 2 — CronTrigger 시간 검증 (short_selling 07:30 / lending_market 07:45 / lending_stock 08:00)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_short_selling_cron_trigger_07_30_kst_mon_fri() -> None:
    """short_selling_sync_daily — CronTrigger mon-fri KST 07:30 (plan § 12.2 #5)."""
    from app.scheduler import (  # type: ignore[attr-defined]
        SHORT_SELLING_SYNC_JOB_ID,
        ShortSellingScheduler,
    )

    sched = ShortSellingScheduler(
        factory=_dummy_ctx,  # type: ignore[arg-type]
        alias="t",
        enabled=True,
    )
    sched.start()
    try:
        job = sched.get_job(SHORT_SELLING_SYNC_JOB_ID)
        assert job is not None
        trigger = job.trigger
        assert isinstance(trigger, CronTrigger)

        fields = {f.name: str(f) for f in trigger.fields}
        assert fields["day_of_week"] == "mon-fri", (
            f"day_of_week 기대 mon-fri, 실제: {fields['day_of_week']}"
        )
        assert fields["hour"] == "7", f"hour 기대 7, 실제: {fields['hour']}"
        assert fields["minute"] == "30", f"minute 기대 30, 실제: {fields['minute']}"
        assert trigger.timezone == ZoneInfo("Asia/Seoul"), (
            f"timezone 기대 Asia/Seoul, 실제: {trigger.timezone}"
        )
    finally:
        sched.shutdown()


@pytest.mark.asyncio
async def test_lending_market_cron_trigger_07_45_kst_mon_fri() -> None:
    """lending_market_sync_daily — CronTrigger mon-fri KST 07:45 (plan § 12.2 #5)."""
    from app.scheduler import (  # type: ignore[attr-defined]
        LENDING_MARKET_SYNC_JOB_ID,
        LendingMarketScheduler,
    )

    sched = LendingMarketScheduler(
        factory=_dummy_ctx,  # type: ignore[arg-type]
        alias="t",
        enabled=True,
    )
    sched.start()
    try:
        job = sched.get_job(LENDING_MARKET_SYNC_JOB_ID)
        assert job is not None
        trigger = job.trigger
        assert isinstance(trigger, CronTrigger)

        fields = {f.name: str(f) for f in trigger.fields}
        assert fields["day_of_week"] == "mon-fri", (
            f"day_of_week 기대 mon-fri, 실제: {fields['day_of_week']}"
        )
        assert fields["hour"] == "7", f"hour 기대 7, 실제: {fields['hour']}"
        assert fields["minute"] == "45", f"minute 기대 45, 실제: {fields['minute']}"
        assert trigger.timezone == ZoneInfo("Asia/Seoul"), (
            f"timezone 기대 Asia/Seoul, 실제: {trigger.timezone}"
        )
    finally:
        sched.shutdown()


@pytest.mark.asyncio
async def test_lending_stock_cron_trigger_08_00_kst_mon_fri() -> None:
    """lending_stock_sync_daily — CronTrigger mon-fri KST 08:00 (plan § 12.2 #5)."""
    from app.scheduler import (  # type: ignore[attr-defined]
        LENDING_STOCK_SYNC_JOB_ID,
        LendingStockScheduler,
    )

    sched = LendingStockScheduler(
        factory=_dummy_ctx,  # type: ignore[arg-type]
        alias="t",
        enabled=True,
    )
    sched.start()
    try:
        job = sched.get_job(LENDING_STOCK_SYNC_JOB_ID)
        assert job is not None
        trigger = job.trigger
        assert isinstance(trigger, CronTrigger)

        fields = {f.name: str(f) for f in trigger.fields}
        assert fields["day_of_week"] == "mon-fri", (
            f"day_of_week 기대 mon-fri, 실제: {fields['day_of_week']}"
        )
        assert fields["hour"] == "8", f"hour 기대 8, 실제: {fields['hour']}"
        assert fields["minute"] == "0", f"minute 기대 0, 실제: {fields['minute']}"
        assert trigger.timezone == ZoneInfo("Asia/Seoul"), (
            f"timezone 기대 Asia/Seoul, 실제: {trigger.timezone}"
        )
    finally:
        sched.shutdown()


# ---------------------------------------------------------------------------
# Scenario 3~5 — alias fail-fast (각 scheduler 별)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_short_selling_alias_missing_fail_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SCHEDULER_SHORT_SELLING_SYNC_ALIAS 미설정 시 lifespan fail-fast (RuntimeError).

    sector_daily 패턴 1:1 — alias='' + enabled=True → lifespan 진입 시 RuntimeError.
    """
    from cryptography.fernet import Fernet
    from fastapi import FastAPI

    valid_key = Fernet.generate_key().decode()
    monkeypatch.setenv("SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("SCHEDULER_SECTOR_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_STOCK_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_FUNDAMENTAL_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_OHLCV_DAILY_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_DAILY_FLOW_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_WEEKLY_OHLCV_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_MONTHLY_OHLCV_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_YEARLY_OHLCV_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_SECTOR_DAILY_SYNC_ALIAS", "ok-alias")
    # Phase E 신규 — short_selling 비워둠
    monkeypatch.setenv("SCHEDULER_SHORT_SELLING_SYNC_ALIAS", "")
    monkeypatch.setenv("SCHEDULER_LENDING_MARKET_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_LENDING_STOCK_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("KIWOOM_CREDENTIAL_MASTER_KEY", valid_key)

    from app.config.settings import get_settings

    get_settings.cache_clear()
    try:
        from app.main import _lifespan  # type: ignore[attr-defined]

        app = FastAPI()
        with pytest.raises(RuntimeError, match="short_selling"):
            async with _lifespan(app):
                pass  # pragma: no cover
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_lending_market_alias_missing_fail_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SCHEDULER_LENDING_MARKET_SYNC_ALIAS 미설정 시 lifespan fail-fast (RuntimeError)."""
    from cryptography.fernet import Fernet
    from fastapi import FastAPI

    valid_key = Fernet.generate_key().decode()
    monkeypatch.setenv("SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("SCHEDULER_SECTOR_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_STOCK_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_FUNDAMENTAL_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_OHLCV_DAILY_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_DAILY_FLOW_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_WEEKLY_OHLCV_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_MONTHLY_OHLCV_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_YEARLY_OHLCV_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_SECTOR_DAILY_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_SHORT_SELLING_SYNC_ALIAS", "ok-alias")
    # Phase E 신규 — lending_market 비워둠
    monkeypatch.setenv("SCHEDULER_LENDING_MARKET_SYNC_ALIAS", "")
    monkeypatch.setenv("SCHEDULER_LENDING_STOCK_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("KIWOOM_CREDENTIAL_MASTER_KEY", valid_key)

    from app.config.settings import get_settings

    get_settings.cache_clear()
    try:
        from app.main import _lifespan  # type: ignore[attr-defined]

        app = FastAPI()
        with pytest.raises(RuntimeError, match="lending_market"):
            async with _lifespan(app):
                pass  # pragma: no cover
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_lending_stock_alias_missing_fail_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SCHEDULER_LENDING_STOCK_SYNC_ALIAS 미설정 시 lifespan fail-fast (RuntimeError)."""
    from cryptography.fernet import Fernet
    from fastapi import FastAPI

    valid_key = Fernet.generate_key().decode()
    monkeypatch.setenv("SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("SCHEDULER_SECTOR_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_STOCK_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_FUNDAMENTAL_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_OHLCV_DAILY_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_DAILY_FLOW_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_WEEKLY_OHLCV_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_MONTHLY_OHLCV_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_YEARLY_OHLCV_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_SECTOR_DAILY_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_SHORT_SELLING_SYNC_ALIAS", "ok-alias")
    monkeypatch.setenv("SCHEDULER_LENDING_MARKET_SYNC_ALIAS", "ok-alias")
    # Phase E 신규 — lending_stock 비워둠
    monkeypatch.setenv("SCHEDULER_LENDING_STOCK_SYNC_ALIAS", "")
    monkeypatch.setenv("KIWOOM_CREDENTIAL_MASTER_KEY", valid_key)

    from app.config.settings import get_settings

    get_settings.cache_clear()
    try:
        from app.main import _lifespan  # type: ignore[attr-defined]

        app = FastAPI()
        with pytest.raises(RuntimeError, match="lending_stock"):
            async with _lifespan(app):
                pass  # pragma: no cover
    finally:
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Scenario 6~8 — enabled=False 시 해당 job 미등록 (나머지 2 job 등록 여부)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_short_selling_disabled_not_registered_others_unaffected() -> None:
    """SCHEDULER_SHORT_SELLING_SYNC_ENABLED=False → short_selling job 미등록.

    나머지 lending_market / lending_stock scheduler 는 독립 lifecycle — 영향 없음.
    """
    from app.scheduler import (  # type: ignore[attr-defined]
        LENDING_MARKET_SYNC_JOB_ID,
        LENDING_STOCK_SYNC_JOB_ID,
        SHORT_SELLING_SYNC_JOB_ID,
        LendingMarketScheduler,
        LendingStockScheduler,
        ShortSellingScheduler,
    )

    ss_sched = ShortSellingScheduler(
        factory=_dummy_ctx,  # type: ignore[arg-type]
        alias="t",
        enabled=False,  # disabled
    )
    lm_sched = LendingMarketScheduler(
        factory=_dummy_ctx,  # type: ignore[arg-type]
        alias="t",
        enabled=True,
    )
    ls_sched = LendingStockScheduler(
        factory=_dummy_ctx,  # type: ignore[arg-type]
        alias="t",
        enabled=True,
    )

    ss_sched.start()
    lm_sched.start()
    ls_sched.start()
    try:
        assert ss_sched.is_running is False, "short_selling scheduler enabled=False 인데 기동됨"
        assert ss_sched.job_count == 0, "short_selling job enabled=False 인데 등록됨"
        assert ss_sched.get_job(SHORT_SELLING_SYNC_JOB_ID) is None

        assert lm_sched.job_count == 1, "lending_market job 미등록 (short_selling disabled 와 무관)"
        assert ls_sched.job_count == 1, "lending_stock job 미등록 (short_selling disabled 와 무관)"
        assert lm_sched.get_job(LENDING_MARKET_SYNC_JOB_ID) is not None
        assert ls_sched.get_job(LENDING_STOCK_SYNC_JOB_ID) is not None
    finally:
        ss_sched.shutdown()
        lm_sched.shutdown()
        ls_sched.shutdown()


@pytest.mark.asyncio
async def test_lending_market_disabled_not_registered_others_unaffected() -> None:
    """SCHEDULER_LENDING_MARKET_SYNC_ENABLED=False → lending_market job 미등록."""
    from app.scheduler import (  # type: ignore[attr-defined]
        LENDING_MARKET_SYNC_JOB_ID,
        LENDING_STOCK_SYNC_JOB_ID,
        SHORT_SELLING_SYNC_JOB_ID,
        LendingMarketScheduler,
        LendingStockScheduler,
        ShortSellingScheduler,
    )

    ss_sched = ShortSellingScheduler(
        factory=_dummy_ctx,  # type: ignore[arg-type]
        alias="t",
        enabled=True,
    )
    lm_sched = LendingMarketScheduler(
        factory=_dummy_ctx,  # type: ignore[arg-type]
        alias="t",
        enabled=False,  # disabled
    )
    ls_sched = LendingStockScheduler(
        factory=_dummy_ctx,  # type: ignore[arg-type]
        alias="t",
        enabled=True,
    )

    ss_sched.start()
    lm_sched.start()
    ls_sched.start()
    try:
        assert lm_sched.is_running is False, "lending_market scheduler enabled=False 인데 기동됨"
        assert lm_sched.job_count == 0, "lending_market job enabled=False 인데 등록됨"
        assert lm_sched.get_job(LENDING_MARKET_SYNC_JOB_ID) is None

        assert ss_sched.job_count == 1, "short_selling job 미등록 (lending_market disabled 와 무관)"
        assert ls_sched.job_count == 1, "lending_stock job 미등록 (lending_market disabled 와 무관)"
        assert ss_sched.get_job(SHORT_SELLING_SYNC_JOB_ID) is not None
        assert ls_sched.get_job(LENDING_STOCK_SYNC_JOB_ID) is not None
    finally:
        ss_sched.shutdown()
        lm_sched.shutdown()
        ls_sched.shutdown()


@pytest.mark.asyncio
async def test_lending_stock_disabled_not_registered_others_unaffected() -> None:
    """SCHEDULER_LENDING_STOCK_SYNC_ENABLED=False → lending_stock job 미등록."""
    from app.scheduler import (  # type: ignore[attr-defined]
        LENDING_MARKET_SYNC_JOB_ID,
        LENDING_STOCK_SYNC_JOB_ID,
        SHORT_SELLING_SYNC_JOB_ID,
        LendingMarketScheduler,
        LendingStockScheduler,
        ShortSellingScheduler,
    )

    ss_sched = ShortSellingScheduler(
        factory=_dummy_ctx,  # type: ignore[arg-type]
        alias="t",
        enabled=True,
    )
    lm_sched = LendingMarketScheduler(
        factory=_dummy_ctx,  # type: ignore[arg-type]
        alias="t",
        enabled=True,
    )
    ls_sched = LendingStockScheduler(
        factory=_dummy_ctx,  # type: ignore[arg-type]
        alias="t",
        enabled=False,  # disabled
    )

    ss_sched.start()
    lm_sched.start()
    ls_sched.start()
    try:
        assert ls_sched.is_running is False, "lending_stock scheduler enabled=False 인데 기동됨"
        assert ls_sched.job_count == 0, "lending_stock job enabled=False 인데 등록됨"
        assert ls_sched.get_job(LENDING_STOCK_SYNC_JOB_ID) is None

        assert ss_sched.job_count == 1, "short_selling job 미등록 (lending_stock disabled 와 무관)"
        assert lm_sched.job_count == 1, "lending_market job 미등록 (lending_stock disabled 와 무관)"
        assert ss_sched.get_job(SHORT_SELLING_SYNC_JOB_ID) is not None
        assert lm_sched.get_job(LENDING_MARKET_SYNC_JOB_ID) is not None
    finally:
        ss_sched.shutdown()
        lm_sched.shutdown()
        ls_sched.shutdown()


# ---------------------------------------------------------------------------
# Scenario 9 — max_instances=1 + coalesce=True + misfire_grace_time
# (lending_stock 90분, 나머지 30분)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_phase_e_job_options_max_instances_coalesce_misfire_grace() -> None:
    """3 job 모두 max_instances=1 + coalesce=True.
    misfire_grace_time: 3 cron 모두 21600s (6h) — ADR § 42.5 옵션 C (Mac 절전 catch-up) 2026-05-14 통일.

    plan § 12.4 H-10 (이전 결정) — lending_stock 은 active 3000 × 2초 = ~100분 추정으로 5400s 권고였으나,
    phase-d-scheduler-misfire-grace § 3 #2 로 21600s 통일 (sleep catch-up 정합 + 일관성 ↑).
    """
    from app.scheduler import (  # type: ignore[attr-defined]
        LENDING_MARKET_SYNC_JOB_ID,
        LENDING_STOCK_SYNC_JOB_ID,
        SHORT_SELLING_SYNC_JOB_ID,
        LendingMarketScheduler,
        LendingStockScheduler,
        ShortSellingScheduler,
    )

    ss_sched = ShortSellingScheduler(
        factory=_dummy_ctx,  # type: ignore[arg-type]
        alias="t",
        enabled=True,
    )
    lm_sched = LendingMarketScheduler(
        factory=_dummy_ctx,  # type: ignore[arg-type]
        alias="t",
        enabled=True,
    )
    ls_sched = LendingStockScheduler(
        factory=_dummy_ctx,  # type: ignore[arg-type]
        alias="t",
        enabled=True,
    )

    ss_sched.start()
    lm_sched.start()
    ls_sched.start()
    try:
        ss_job = ss_sched.get_job(SHORT_SELLING_SYNC_JOB_ID)
        lm_job = lm_sched.get_job(LENDING_MARKET_SYNC_JOB_ID)
        ls_job = ls_sched.get_job(LENDING_STOCK_SYNC_JOB_ID)

        assert ss_job is not None
        assert lm_job is not None
        assert ls_job is not None

        # max_instances=1
        assert ss_job.max_instances == 1, f"short_selling max_instances 기대 1, 실제: {ss_job.max_instances}"
        assert lm_job.max_instances == 1, f"lending_market max_instances 기대 1, 실제: {lm_job.max_instances}"
        assert ls_job.max_instances == 1, f"lending_stock max_instances 기대 1, 실제: {ls_job.max_instances}"

        # coalesce=True
        assert ss_job.coalesce is True, f"short_selling coalesce 기대 True, 실제: {ss_job.coalesce}"
        assert lm_job.coalesce is True, f"lending_market coalesce 기대 True, 실제: {lm_job.coalesce}"
        assert ls_job.coalesce is True, f"lending_stock coalesce 기대 True, 실제: {ls_job.coalesce}"

        # misfire_grace_time = 21600s (6h) — Mac 절전 catch-up (ADR § 42.5 옵션 C, plan § 3 #1)
        # 전체 통일: short_selling / lending_market / lending_stock 모두 6h
        import datetime

        _6h = datetime.timedelta(seconds=21600)

        ss_grace = ss_job.misfire_grace_time
        lm_grace = lm_job.misfire_grace_time
        ls_grace = ls_job.misfire_grace_time

        assert ss_grace == _6h, (
            f"short_selling misfire_grace_time 기대 6h(21600s), 실제: {ss_grace}"
        )
        assert lm_grace == _6h, (
            f"lending_market misfire_grace_time 기대 6h(21600s), 실제: {lm_grace}"
        )
        assert ls_grace == _6h, (
            f"lending_stock misfire_grace_time 기대 6h(21600s), 실제: {ls_grace}"
        )
    finally:
        ss_sched.shutdown()
        lm_sched.shutdown()
        ls_sched.shutdown()


# ---------------------------------------------------------------------------
# 보조 — lifespan 완전 사이클 smoke (Phase E alias 모두 주입)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lifespan_startup_shutdown_with_phase_e_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase E alias 3건 추가 포함 lifespan 사이클 — 예외 없이 완료.

    기존 test_scheduler.py 의 smoke 패턴 + Phase E alias 3건 추가.
    """
    from cryptography.fernet import Fernet
    from fastapi import FastAPI

    valid_key = Fernet.generate_key().decode()
    monkeypatch.setenv("SCHEDULER_ENABLED", "true")
    monkeypatch.setenv("SCHEDULER_SECTOR_SYNC_ALIAS", "smoke")
    monkeypatch.setenv("SCHEDULER_STOCK_SYNC_ALIAS", "smoke")
    monkeypatch.setenv("SCHEDULER_FUNDAMENTAL_SYNC_ALIAS", "smoke")
    monkeypatch.setenv("SCHEDULER_OHLCV_DAILY_SYNC_ALIAS", "smoke")
    monkeypatch.setenv("SCHEDULER_DAILY_FLOW_SYNC_ALIAS", "smoke")
    monkeypatch.setenv("SCHEDULER_WEEKLY_OHLCV_SYNC_ALIAS", "smoke")
    monkeypatch.setenv("SCHEDULER_MONTHLY_OHLCV_SYNC_ALIAS", "smoke")
    monkeypatch.setenv("SCHEDULER_YEARLY_OHLCV_SYNC_ALIAS", "smoke")
    monkeypatch.setenv("SCHEDULER_SECTOR_DAILY_SYNC_ALIAS", "smoke")
    # Phase E 신규 3건
    monkeypatch.setenv("SCHEDULER_SHORT_SELLING_SYNC_ALIAS", "smoke")
    monkeypatch.setenv("SCHEDULER_LENDING_MARKET_SYNC_ALIAS", "smoke")
    monkeypatch.setenv("SCHEDULER_LENDING_STOCK_SYNC_ALIAS", "smoke")
    # Phase F-4 Step 2 fix C-2 — 5 ranking endpoint alias
    monkeypatch.setenv("SCHEDULER_FLU_RT_RANKING_SYNC_ALIAS", "smoke")
    monkeypatch.setenv("SCHEDULER_TODAY_VOLUME_RANKING_SYNC_ALIAS", "smoke")
    monkeypatch.setenv("SCHEDULER_PRED_VOLUME_RANKING_SYNC_ALIAS", "smoke")
    monkeypatch.setenv("SCHEDULER_TRADE_AMOUNT_RANKING_SYNC_ALIAS", "smoke")
    monkeypatch.setenv("SCHEDULER_VOLUME_SDNIN_RANKING_SYNC_ALIAS", "smoke")
    monkeypatch.setenv("KIWOOM_CREDENTIAL_MASTER_KEY", valid_key)

    from app.config.settings import get_settings

    get_settings.cache_clear()
    try:
        from app.main import _lifespan  # type: ignore[attr-defined]

        app = FastAPI()
        async with _lifespan(app):
            pass
    finally:
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# 보조 — disabled=True 전체 lifespan smoke
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lifespan_phase_e_disabled_all_smoke(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """scheduler_enabled=False — Phase E alias 없어도 lifespan 정상 완료."""
    from cryptography.fernet import Fernet
    from fastapi import FastAPI

    valid_key = Fernet.generate_key().decode()
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("SCHEDULER_SECTOR_SYNC_ALIAS", "")
    monkeypatch.setenv("KIWOOM_CREDENTIAL_MASTER_KEY", valid_key)

    from app.config.settings import get_settings

    get_settings.cache_clear()
    try:
        from app.main import _lifespan  # type: ignore[attr-defined]

        app = FastAPI()
        async with _lifespan(app):
            pass
    finally:
        get_settings.cache_clear()


__all__: list[Any] = []
