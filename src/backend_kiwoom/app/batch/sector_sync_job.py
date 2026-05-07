"""주간 sector sync 콜백 — APScheduler 가 트리거.

설계: endpoint-14-ka10101.md § 7.2.

책임:
- `SyncSectorUseCaseFactory` 호출 → `SyncSectorMasterUseCase.execute`
- 결과 logger.info (fetched / upserted / deactivated 합계)
- 부분 실패 시 logger.warning (운영 oncall 알람)
- 모든 예외 swallow — 다음 cron tick 정상 동작 보장

호출자:
- `SectorSyncScheduler` 의 등록된 weekly cron job
- 수동 호출도 가능 (운영 dry-run 시 직접 트리거)
"""

from __future__ import annotations

import logging

from app.adapter.web._deps import SyncSectorUseCaseFactory

logger = logging.getLogger(__name__)


async def fire_sector_sync(
    *,
    factory: SyncSectorUseCaseFactory,
    alias: str,
) -> None:
    """주간 sector sync 콜백 — best-effort, 예외 swallow.

    APScheduler 가 호출 — 예외가 전파되면 다음 cron 트리거가 영향 받을 수 있어
    모든 예외를 잡고 logger.exception 로 보고만 한다.

    Parameters:
        factory: lifespan 에서 set 된 SyncSectorUseCaseFactory
        alias: 사용할 키움 자격증명 alias (settings.scheduler_sector_sync_alias)
    """
    logger.info("sector sync cron 시작 — alias=%s", alias)
    try:
        async with factory(alias) as use_case:
            result = await use_case.execute()
    except Exception:  # noqa: BLE001 — cron 콜백은 모든 예외 swallow
        logger.exception("sector sync 콜백 예외 — alias=%s", alias)
        return

    if result.all_succeeded:
        logger.info(
            "sector sync 완료 — fetched=%d upserted=%d deactivated=%d",
            result.total_fetched,
            result.total_upserted,
            result.total_deactivated,
        )
    else:
        # 부분 실패 — 운영 알림용 warning
        failed_markets = [m.market_code for m in result.markets if m.error is not None]
        logger.warning(
            "sector sync 부분 실패 — fetched=%d upserted=%d deactivated=%d failed_markets=%s",
            result.total_fetched,
            result.total_upserted,
            result.total_deactivated,
            failed_markets,
        )


__all__ = ["fire_sector_sync"]
