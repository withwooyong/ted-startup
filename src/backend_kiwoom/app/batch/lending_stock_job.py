"""종목 대차거래 (ka20068) sync 콜백 — APScheduler 가 트리거 (Phase E).

설계: endpoint-17-ka20068.md § 12 + plan § 12.2 #5.

short_selling_job 패턴 1:1 응용 — active 종목 bulk sync.

특징 (plan § 12.2):
- #5 cron = mon-fri KST 08:00 — § 35 NXT 마감 후 새벽 cron 일관
- #4 ka20068 = KRX only (Length=6 명세, NXT 시도 운영 검증 후 재검토 — 본 chunk 디폴트 skip)
- #6 cron 윈도 = 1주 (T-7 ~ T), misfire_grace_time = 5400s (90분)
- #10 partial 임계치 = 5% / 15% (warning / error)
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from app.adapter.web._deps import IngestLendingStockBulkUseCaseFactory

logger = logging.getLogger(__name__)


SYNC_WINDOW_DAYS: int = 7
"""plan § 12.2 #6 — cron sync 윈도 1주."""


async def fire_lending_stock_sync(
    *,
    factory: IngestLendingStockBulkUseCaseFactory,
    alias: str,
) -> None:
    """종목 대차거래 sync 콜백 — best-effort, 예외 swallow (cron 연속성).

    호출자: LendingStockScheduler 의 등록된 cron job (mon-fri KST 08:00, misfire 90분).
    """
    end = date.today()
    start = end - timedelta(days=SYNC_WINDOW_DAYS)
    logger.info(
        "lending stock sync cron 시작 — alias=%s window=%s~%s",
        alias,
        start,
        end,
    )
    try:
        async with factory(alias) as use_case:
            result = await use_case.execute(start_date=start, end_date=end)
    except Exception:  # noqa: BLE001 — cron 콜백은 모든 예외 swallow
        logger.exception("lending stock sync 콜백 예외 — alias=%s", alias)
        return

    failure_ratio = (
        (result.total_failed / result.total_stocks) if result.total_stocks > 0 else 0.0
    )

    if result.errors_above_threshold:
        logger.error(
            "lending stock sync 실패율 과다 (15%% 초과) — total_stocks=%d upserted=%d "
            "failed=%d skipped=%d alphanumeric_skipped=%d ratio=%.2f errors=%s",
            result.total_stocks,
            result.total_upserted,
            result.total_failed,
            result.total_skipped,
            result.total_alphanumeric_skipped,
            failure_ratio,
            list(result.errors_above_threshold),
        )
    elif result.warnings:
        logger.warning(
            "lending stock sync 부분 실패 (5%% 초과) — total_stocks=%d upserted=%d "
            "failed=%d skipped=%d alphanumeric_skipped=%d ratio=%.2f warnings=%s",
            result.total_stocks,
            result.total_upserted,
            result.total_failed,
            result.total_skipped,
            result.total_alphanumeric_skipped,
            failure_ratio,
            list(result.warnings),
        )
    else:
        logger.info(
            "lending stock sync 완료 — total_stocks=%d upserted=%d failed=%d skipped=%d alphanumeric_skipped=%d",
            result.total_stocks,
            result.total_upserted,
            result.total_failed,
            result.total_skipped,
            result.total_alphanumeric_skipped,
        )


__all__ = ["SYNC_WINDOW_DAYS", "fire_lending_stock_sync"]
