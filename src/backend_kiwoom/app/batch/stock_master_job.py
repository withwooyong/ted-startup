"""일간 stock master sync 콜백 — APScheduler 가 트리거.

설계: endpoint-03-ka10099.md § 7.2.

책임 (sector 패턴 일관):
- `SyncStockMasterUseCaseFactory` 호출 → `SyncStockMasterUseCase.execute`
- 결과 logger.info (fetched / upserted / deactivated / nxt_enabled 합계)
- 부분 실패 시 logger.warning (운영 oncall 알람)
- 모든 예외 swallow — 다음 cron tick 정상 동작 보장
- 거래일 판정은 cron 트리거가 mon-fri 만 발화 — 별도 holiday filter 는 Phase B-γ 이후 결정

호출자:
- `StockMasterScheduler` 의 등록된 daily cron job
- 수동 호출도 가능 (운영 dry-run 시 직접 트리거)
"""

from __future__ import annotations

import logging

from app.adapter.web._deps import SyncStockMasterUseCaseFactory

logger = logging.getLogger(__name__)


async def fire_stock_master_sync(
    *,
    factory: SyncStockMasterUseCaseFactory,
    alias: str,
) -> None:
    """일간 stock master sync 콜백 — best-effort, 예외 swallow.

    Parameters:
        factory: lifespan 에서 set 된 SyncStockMasterUseCaseFactory
        alias: 사용할 키움 자격증명 alias (settings.scheduler_stock_sync_alias)
    """
    logger.info("stock master sync cron 시작 — alias=%s", alias)
    try:
        async with factory(alias) as use_case:
            result = await use_case.execute()
    except Exception:  # noqa: BLE001 — cron 콜백은 모든 예외 swallow
        logger.exception("stock master sync 콜백 예외 — alias=%s", alias)
        return

    if result.all_succeeded:
        logger.info(
            "stock master sync 완료 — fetched=%d upserted=%d deactivated=%d nxt_enabled=%d",
            result.total_fetched,
            result.total_upserted,
            result.total_deactivated,
            result.total_nxt_enabled,
        )
    else:
        failed_markets = [m.market_code for m in result.markets if m.error is not None]
        logger.warning(
            "stock master sync 부분 실패 — fetched=%d upserted=%d deactivated=%d nxt_enabled=%d failed_markets=%s",
            result.total_fetched,
            result.total_upserted,
            result.total_deactivated,
            result.total_nxt_enabled,
            failed_markets,
        )


__all__ = ["fire_stock_master_sync"]
