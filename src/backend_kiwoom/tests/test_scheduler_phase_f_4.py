"""Phase F-4 Scheduler 검증 — 5 ranking cron 등록 (ka10027/30/31/32/23).

설계: phase-f-4-rankings.md § 5.9 + § 5.12 #10 + D-6 / D-14.
     test_scheduler_phase_e.py 패턴 1:1 모방.

결정 (plan § 4 D-6 / D-14):
- D-6: cron 19:30/35/40/45/50 KST mon-fri (5분 chain = sequential)
- D-14: 5 endpoint scheduler chain sequential (asyncio.gather 아님)
- F-4 Step 2 fix G-2: misfire_grace_time=21600s (6h) — 12 scheduler 통일 (ADR § 43)
  이전 1800s (plan § 5.8) 에서 변경.

가정 production 변경: app/scheduler.py 에 5 RankingScheduler 클래스 추가 (Step 1).

각 scheduler:
- FluRtRankingScheduler       → cron 19:30 KST mon-fri
- TodayVolumeRankingScheduler → cron 19:35 KST mon-fri
- PredVolumeRankingScheduler  → cron 19:40 KST mon-fri
- TrdePricaRankingScheduler   → cron 19:45 KST mon-fri
- VolumeSdninRankingScheduler → cron 19:50 KST mon-fri

검증 시나리오 (~7 케이스):
1. 5 scheduler 모두 enabled=True 시 각 job 등록 확인
2. FluRtRankingScheduler — CronTrigger 19:30 KST mon-fri
3. TodayVolumeRankingScheduler — CronTrigger 19:35 KST mon-fri
4. PredVolumeRankingScheduler — CronTrigger 19:40 KST mon-fri
5. TrdePricaRankingScheduler — CronTrigger 19:45 KST mon-fri / VolumeSdninRankingScheduler 19:50
6. misfire_grace_time=21600s (6h) 검증 — ADR § 43 (12 scheduler 통일)
7. enabled=False → job 미등록 (한 scheduler disabled 시 다른 scheduler 독립)

TDD red 의도:
- `from app.scheduler import FluRtRankingScheduler` → ImportError (Step 1 미구현)
- Step 1 구현 후 green 전환.
"""

from __future__ import annotations

import datetime
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


# Phase F-4 scheduler JOB_ID 상수 — 미구현 상태에서 ImportError 발생 예정 (red)
_FLU_RT_RANKING_JOB_ID = "flu_rt_ranking_sync_daily"
_TODAY_VOLUME_RANKING_JOB_ID = "today_volume_ranking_sync_daily"
_PRED_VOLUME_RANKING_JOB_ID = "pred_volume_ranking_sync_daily"
_TRDE_PRICA_RANKING_JOB_ID = "trde_prica_ranking_sync_daily"
_VOLUME_SDNIN_RANKING_JOB_ID = "volume_sdnin_ranking_sync_daily"

# misfire_grace_time — F-4 Step 2 fix G-2: 21600s (6h) 12 scheduler 통일 (ADR § 43)
# 이전 1800s (plan § 5.8) 에서 변경.
_RANKING_MISFIRE_GRACE_SECONDS = 21600  # 6h


# ===========================================================================
# Scenario 1 — 5 scheduler 모두 enabled=True 시 각 job 등록 확인
# ===========================================================================


@pytest.mark.asyncio
async def test_phase_f4_all_five_ranking_schedulers_registered_when_enabled() -> None:
    """enabled=True 시 5 ranking cron scheduler 모두 job 등록 확인.

    plan § 5.9 — 5 add_job 추가 (app/scheduler.py 갱신).
    """
    from app.scheduler import (  # type: ignore[attr-defined]  # red: 미구현
        FLU_RT_RANKING_SYNC_JOB_ID,
        PRED_VOLUME_RANKING_SYNC_JOB_ID,
        TODAY_VOLUME_RANKING_SYNC_JOB_ID,
        TRDE_PRICA_RANKING_SYNC_JOB_ID,
        VOLUME_SDNIN_RANKING_SYNC_JOB_ID,
        FluRtRankingScheduler,
        PredVolumeRankingScheduler,
        TodayVolumeRankingScheduler,
        TrdePricaRankingScheduler,
        VolumeSdninRankingScheduler,
    )

    schedulers = [
        FluRtRankingScheduler(factory=_dummy_ctx, alias="t", enabled=True),  # type: ignore[arg-type]
        TodayVolumeRankingScheduler(factory=_dummy_ctx, alias="t", enabled=True),  # type: ignore[arg-type]
        PredVolumeRankingScheduler(factory=_dummy_ctx, alias="t", enabled=True),  # type: ignore[arg-type]
        TrdePricaRankingScheduler(factory=_dummy_ctx, alias="t", enabled=True),  # type: ignore[arg-type]
        VolumeSdninRankingScheduler(factory=_dummy_ctx, alias="t", enabled=True),  # type: ignore[arg-type]
    ]
    job_ids = [
        FLU_RT_RANKING_SYNC_JOB_ID,
        TODAY_VOLUME_RANKING_SYNC_JOB_ID,
        PRED_VOLUME_RANKING_SYNC_JOB_ID,
        TRDE_PRICA_RANKING_SYNC_JOB_ID,
        VOLUME_SDNIN_RANKING_SYNC_JOB_ID,
    ]

    for sched in schedulers:
        sched.start()
    try:
        for sched, jid in zip(schedulers, job_ids, strict=False):
            assert sched.job_count == 1, f"{type(sched).__name__} job 미등록"
            assert sched.get_job(jid) is not None, f"{jid} 미등록"
    finally:
        for sched in schedulers:
            sched.shutdown()


# ===========================================================================
# Scenario 2~5 — CronTrigger 시간 검증 (19:30/35/40/45/50 KST mon-fri)
# ===========================================================================


@pytest.mark.asyncio
async def test_flu_rt_ranking_cron_trigger_19_30_kst_mon_fri() -> None:
    """FluRtRankingScheduler — CronTrigger mon-fri KST 19:30 (plan D-6)."""
    from app.scheduler import (  # type: ignore[attr-defined]
        FLU_RT_RANKING_SYNC_JOB_ID,
        FluRtRankingScheduler,
    )

    sched = FluRtRankingScheduler(factory=_dummy_ctx, alias="t", enabled=True)  # type: ignore[arg-type]
    sched.start()
    try:
        job = sched.get_job(FLU_RT_RANKING_SYNC_JOB_ID)
        assert job is not None
        trigger = job.trigger
        assert isinstance(trigger, CronTrigger)

        fields = {f.name: str(f) for f in trigger.fields}
        assert fields["day_of_week"] == "mon-fri", f"day_of_week 기대 mon-fri, 실제: {fields['day_of_week']}"
        assert fields["hour"] == "19", f"hour 기대 19, 실제: {fields['hour']}"
        assert fields["minute"] == "30", f"minute 기대 30, 실제: {fields['minute']}"
        assert trigger.timezone == ZoneInfo("Asia/Seoul"), f"timezone 기대 Asia/Seoul, 실제: {trigger.timezone}"
    finally:
        sched.shutdown()


@pytest.mark.asyncio
async def test_today_volume_ranking_cron_trigger_19_35_kst_mon_fri() -> None:
    """TodayVolumeRankingScheduler — CronTrigger mon-fri KST 19:35 (plan D-6)."""
    from app.scheduler import (  # type: ignore[attr-defined]
        TODAY_VOLUME_RANKING_SYNC_JOB_ID,
        TodayVolumeRankingScheduler,
    )

    sched = TodayVolumeRankingScheduler(factory=_dummy_ctx, alias="t", enabled=True)  # type: ignore[arg-type]
    sched.start()
    try:
        job = sched.get_job(TODAY_VOLUME_RANKING_SYNC_JOB_ID)
        assert job is not None
        trigger = job.trigger
        assert isinstance(trigger, CronTrigger)

        fields = {f.name: str(f) for f in trigger.fields}
        assert fields["hour"] == "19", f"hour 기대 19, 실제: {fields['hour']}"
        assert fields["minute"] == "35", f"minute 기대 35, 실제: {fields['minute']}"
        assert trigger.timezone == ZoneInfo("Asia/Seoul")
    finally:
        sched.shutdown()


@pytest.mark.asyncio
async def test_pred_volume_ranking_cron_trigger_19_40_kst_mon_fri() -> None:
    """PredVolumeRankingScheduler — CronTrigger mon-fri KST 19:40 (plan D-6)."""
    from app.scheduler import (  # type: ignore[attr-defined]
        PRED_VOLUME_RANKING_SYNC_JOB_ID,
        PredVolumeRankingScheduler,
    )

    sched = PredVolumeRankingScheduler(factory=_dummy_ctx, alias="t", enabled=True)  # type: ignore[arg-type]
    sched.start()
    try:
        job = sched.get_job(PRED_VOLUME_RANKING_SYNC_JOB_ID)
        assert job is not None
        trigger = job.trigger
        assert isinstance(trigger, CronTrigger)

        fields = {f.name: str(f) for f in trigger.fields}
        assert fields["hour"] == "19", f"hour 기대 19, 실제: {fields['hour']}"
        assert fields["minute"] == "40", f"minute 기대 40, 실제: {fields['minute']}"
        assert trigger.timezone == ZoneInfo("Asia/Seoul")
    finally:
        sched.shutdown()


@pytest.mark.asyncio
async def test_trde_prica_and_volume_sdnin_cron_triggers_19_45_19_50() -> None:
    """TrdePricaRankingScheduler 19:45 / VolumeSdninRankingScheduler 19:50 (plan D-6).

    5분 chain 마지막 2개 — D-14 sequential.
    """
    from app.scheduler import (  # type: ignore[attr-defined]
        TRDE_PRICA_RANKING_SYNC_JOB_ID,
        VOLUME_SDNIN_RANKING_SYNC_JOB_ID,
        TrdePricaRankingScheduler,
        VolumeSdninRankingScheduler,
    )

    trde_sched = TrdePricaRankingScheduler(factory=_dummy_ctx, alias="t", enabled=True)  # type: ignore[arg-type]
    sdnin_sched = VolumeSdninRankingScheduler(factory=_dummy_ctx, alias="t", enabled=True)  # type: ignore[arg-type]

    trde_sched.start()
    sdnin_sched.start()
    try:
        trde_job = trde_sched.get_job(TRDE_PRICA_RANKING_SYNC_JOB_ID)
        sdnin_job = sdnin_sched.get_job(VOLUME_SDNIN_RANKING_SYNC_JOB_ID)

        assert trde_job is not None
        assert sdnin_job is not None

        trde_fields = {f.name: str(f) for f in trde_job.trigger.fields}
        sdnin_fields = {f.name: str(f) for f in sdnin_job.trigger.fields}

        assert trde_fields["hour"] == "19"
        assert trde_fields["minute"] == "45", f"trde_prica minute 기대 45, 실제: {trde_fields['minute']}"
        assert sdnin_fields["hour"] == "19"
        assert sdnin_fields["minute"] == "50", f"volume_sdnin minute 기대 50, 실제: {sdnin_fields['minute']}"
    finally:
        trde_sched.shutdown()
        sdnin_sched.shutdown()


# ===========================================================================
# Scenario 6 — misfire_grace_time=21600s (6h) 검증 (F-4 Step 2 fix G-2 통일)
# ===========================================================================


@pytest.mark.asyncio
async def test_phase_f4_ranking_job_misfire_grace_time_6h() -> None:
    """5 ranking scheduler 모두 misfire_grace_time=21600s (6h).

    F-4 Step 2 fix G-2: 12 scheduler 통일 (ADR § 43 옵션 C — Mac 절전 catch-up).
    이전 1800s (plan § 5.8 명시값) 에서 통일.
    """
    from app.scheduler import (  # type: ignore[attr-defined]
        FLU_RT_RANKING_SYNC_JOB_ID,
        PRED_VOLUME_RANKING_SYNC_JOB_ID,
        TODAY_VOLUME_RANKING_SYNC_JOB_ID,
        TRDE_PRICA_RANKING_SYNC_JOB_ID,
        VOLUME_SDNIN_RANKING_SYNC_JOB_ID,
        FluRtRankingScheduler,
        PredVolumeRankingScheduler,
        TodayVolumeRankingScheduler,
        TrdePricaRankingScheduler,
        VolumeSdninRankingScheduler,
    )

    schedulers_and_ids = [
        (FluRtRankingScheduler(factory=_dummy_ctx, alias="t", enabled=True), FLU_RT_RANKING_SYNC_JOB_ID),  # type: ignore[arg-type]
        (TodayVolumeRankingScheduler(factory=_dummy_ctx, alias="t", enabled=True), TODAY_VOLUME_RANKING_SYNC_JOB_ID),  # type: ignore[arg-type]
        (PredVolumeRankingScheduler(factory=_dummy_ctx, alias="t", enabled=True), PRED_VOLUME_RANKING_SYNC_JOB_ID),  # type: ignore[arg-type]
        (TrdePricaRankingScheduler(factory=_dummy_ctx, alias="t", enabled=True), TRDE_PRICA_RANKING_SYNC_JOB_ID),  # type: ignore[arg-type]
        (VolumeSdninRankingScheduler(factory=_dummy_ctx, alias="t", enabled=True), VOLUME_SDNIN_RANKING_SYNC_JOB_ID),  # type: ignore[arg-type]
    ]

    for sched, _ in schedulers_and_ids:
        sched.start()

    try:
        _6h = datetime.timedelta(seconds=_RANKING_MISFIRE_GRACE_SECONDS)  # 21600s

        for sched, jid in schedulers_and_ids:
            job = sched.get_job(jid)
            assert job is not None, f"{jid} 미등록"
            # APScheduler 3.x 에서 misfire_grace_time 은 timedelta 또는 int(seconds)
            raw = job.misfire_grace_time
            actual_td = raw if isinstance(raw, datetime.timedelta) else datetime.timedelta(seconds=int(raw))
            assert actual_td == _6h, (
                f"{jid} misfire_grace_time 기대 21600s(6h), 실제: {actual_td}"
            )
    finally:
        for sched, _ in schedulers_and_ids:
            sched.shutdown()


# ===========================================================================
# Scenario 7 — enabled=False → 해당 job 미등록 (독립 lifecycle)
# ===========================================================================


@pytest.mark.asyncio
async def test_flu_rt_scheduler_disabled_not_registered_others_unaffected() -> None:
    """FluRtRankingScheduler enabled=False → flu_rt job 미등록.

    나머지 4 scheduler 는 독립 lifecycle — 영향 없음.
    """
    from app.scheduler import (  # type: ignore[attr-defined]
        FLU_RT_RANKING_SYNC_JOB_ID,
        TODAY_VOLUME_RANKING_SYNC_JOB_ID,
        FluRtRankingScheduler,
        TodayVolumeRankingScheduler,
    )

    flu_sched = FluRtRankingScheduler(factory=_dummy_ctx, alias="t", enabled=False)  # type: ignore[arg-type]
    vol_sched = TodayVolumeRankingScheduler(factory=_dummy_ctx, alias="t", enabled=True)  # type: ignore[arg-type]

    flu_sched.start()
    vol_sched.start()
    try:
        # flu_rt disabled → job 없음
        assert flu_sched.is_running is False, "flu_rt scheduler enabled=False 인데 기동됨"
        assert flu_sched.job_count == 0, "flu_rt job enabled=False 인데 등록됨"
        assert flu_sched.get_job(FLU_RT_RANKING_SYNC_JOB_ID) is None

        # today_volume 는 독립 — 영향 없음
        assert vol_sched.job_count == 1, "today_volume job 미등록 (flu_rt disabled 와 무관)"
        assert vol_sched.get_job(TODAY_VOLUME_RANKING_SYNC_JOB_ID) is not None
    finally:
        flu_sched.shutdown()
        vol_sched.shutdown()


__all__: list[Any] = []
