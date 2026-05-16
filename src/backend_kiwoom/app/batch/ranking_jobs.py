"""5 ranking endpoint sync 콜백 — APScheduler 가 트리거 (Phase F-4).

설계: phase-f-4-rankings.md § 5.8 + D-6 / D-14.

5 cron 함수 (mon-fri KST 19:30/35/40/45/50 — 5분 chain sequential):
- fire_flu_rt_sync           (ka10027, 19:30)
- fire_today_volume_sync     (ka10030, 19:35)
- fire_pred_volume_sync      (ka10031, 19:40)
- fire_trde_prica_sync       (ka10032, 19:45)
- fire_volume_sdnin_sync     (ka10023, 19:50)

best-effort cron — 모든 예외 swallow (cron 연속성 — short_selling_job 패턴 미러).
is_trading_day 가드 — 휴장일 skip (CronTrigger mon-fri 가 토/일 자동 skip 하지만,
국경일 / 연말 휴장은 별도 캘린더 필요 — 본 helper 가 진실 source).

errors_above_threshold tuple (F-3 D-3 패턴) — 비어있지 않으면 logger.error 알람.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
"""Phase F-4 5 ranking cron 의 snapshot_at timezone — F-4 Step 2 fix sonnet L-3."""


def is_trading_day(today: date | None = None) -> bool:
    """KST 거래일 여부 — 토/일 skip + 국경일 캘린더 확장 포인트.

    현재 구현: 평일이면 True (mon-fri). 국경일 캘린더는 후속 chunk.
    CronTrigger 가 이미 mon-fri 만 발화하지만, defense-in-depth 로 본 가드 추가.

    Phase F-4 cron 시점 (19:30~19:50) 의 ``date.today()`` 는 발화 당일 — 거래 종료 후.
    """
    today = today or date.today()
    return today.weekday() < 5  # 0=Mon ... 4=Fri


async def _fire_ranking_sync(
    *,
    label: str,
    factory: Any,
    alias: str,
) -> None:
    """공통 cron callback — best-effort, 예외 swallow (cron 연속성).

    label: 로깅용 endpoint 이름 (ka10027 / ka10030 / ...).
    """
    if not is_trading_day():
        logger.info("%s cron — 휴장일 skip", label)
        return

    logger.info("%s sync cron 시작 — alias=%s", label, alias)

    # F-4 Step 2 fix sonnet L-3 — Bulk UseCase 는 snapshot_at: datetime keyword-only.
    # 미전달 시 runtime TypeError → cron 콜백 자체가 silent fail. KST `datetime.now()` 명시.
    snapshot_at = datetime.now(tz=KST)

    try:
        async with factory(alias) as use_case:
            result = await use_case.execute(snapshot_at=snapshot_at)
    except Exception:  # noqa: BLE001 — cron 콜백은 모든 예외 swallow
        logger.exception("%s sync 콜백 예외 — alias=%s", label, alias)
        return

    # F-3 D-3 패턴 — errors_above_threshold tuple 비어있지 않으면 logger.error 알람.
    # short_selling_job.py:59 미러.
    if result.errors_above_threshold:
        logger.error(
            "%s sync 임계치 초과 — total_calls=%d upserted=%d failed=%d errors=%s",
            label,
            result.total_calls,
            result.total_upserted,
            result.total_failed,
            list(result.errors_above_threshold),
        )
    else:
        logger.info(
            "%s sync 완료 — total_calls=%d upserted=%d failed=%d",
            label,
            result.total_calls,
            result.total_upserted,
            result.total_failed,
        )


async def fire_flu_rt_sync(*, factory: Any, alias: str) -> None:
    """ka10027 등락률 ranking sync 콜백 (mon-fri KST 19:30)."""
    await _fire_ranking_sync(label="ka10027 flu_rt", factory=factory, alias=alias)


async def fire_today_volume_sync(*, factory: Any, alias: str) -> None:
    """ka10030 당일 거래량 ranking sync 콜백 (mon-fri KST 19:35)."""
    await _fire_ranking_sync(label="ka10030 today_volume", factory=factory, alias=alias)


async def fire_pred_volume_sync(*, factory: Any, alias: str) -> None:
    """ka10031 전일 거래량 ranking sync 콜백 (mon-fri KST 19:40)."""
    await _fire_ranking_sync(label="ka10031 pred_volume", factory=factory, alias=alias)


async def fire_trde_prica_sync(*, factory: Any, alias: str) -> None:
    """ka10032 거래대금 ranking sync 콜백 (mon-fri KST 19:45)."""
    await _fire_ranking_sync(label="ka10032 trde_prica", factory=factory, alias=alias)


async def fire_volume_sdnin_sync(*, factory: Any, alias: str) -> None:
    """ka10023 거래량 급증 ranking sync 콜백 (mon-fri KST 19:50)."""
    await _fire_ranking_sync(label="ka10023 volume_sdnin", factory=factory, alias=alias)


__all__ = [
    "fire_flu_rt_sync",
    "fire_pred_volume_sync",
    "fire_today_volume_sync",
    "fire_trde_prica_sync",
    "fire_volume_sdnin_sync",
    "is_trading_day",
]
