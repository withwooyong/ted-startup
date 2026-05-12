"""시장 대차거래 (ka10068) sync 콜백 — APScheduler 가 트리거 (Phase E).

설계: endpoint-16-ka10068.md § 12 + plan § 12.2 #5.

단일 호출 (시장 단위 — mrkt_tp 분리 없음). active 종목 iterate 없음 — elapsed 짧음.

특징 (plan § 12.2):
- #5 cron = mon-fri KST 07:45 — § 35 NXT 마감 후 새벽 cron 일관
- #4 NXT 분기 자체 없음 (시장 단위)
- #6 cron 윈도 = 1주 (T-7 ~ T)
- #10 partial 임계치 N/A (단일 호출 — error 1건 = ERROR)
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from app.adapter.web._deps import IngestLendingMarketUseCaseFactory

logger = logging.getLogger(__name__)


SYNC_WINDOW_DAYS: int = 7
"""plan § 12.2 #6 — cron sync 윈도 1주."""


async def fire_lending_market_sync(
    *,
    factory: IngestLendingMarketUseCaseFactory,
    alias: str,
) -> None:
    """시장 대차거래 sync 콜백 — best-effort, 예외 swallow (cron 연속성).

    호출자: LendingMarketScheduler 의 등록된 cron job (mon-fri KST 07:45).

    단일 호출이므로 실패율 임계치 없음 — outcome.error 1건이면 ERROR 로그.
    """
    end = date.today()
    start = end - timedelta(days=SYNC_WINDOW_DAYS)
    logger.info(
        "lending market sync cron 시작 — alias=%s window=%s~%s",
        alias,
        start,
        end,
    )
    try:
        async with factory(alias) as use_case:
            outcome = await use_case.execute(start_date=start, end_date=end)
            # session.commit 은 factory 의 context exit 직전에 자동 수행.
    except Exception:  # noqa: BLE001 — cron 콜백은 모든 예외 swallow
        logger.exception("lending market sync 콜백 예외 — alias=%s", alias)
        return

    if outcome.error is not None:
        logger.error(
            "lending market sync 실패 — error=%s fetched=%d upserted=%d",
            outcome.error,
            outcome.fetched,
            outcome.upserted,
        )
    else:
        logger.info(
            "lending market sync 완료 — fetched=%d upserted=%d",
            outcome.fetched,
            outcome.upserted,
        )


__all__ = ["SYNC_WINDOW_DAYS", "fire_lending_market_sync"]
