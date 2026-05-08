"""일간 stock fundamental sync 콜백 — APScheduler 가 트리거 (B-γ-2).

설계: endpoint-05-ka10001.md § 7.2 + ADR § 14.

책임 (stock_master_job 패턴 일관):
- `SyncStockFundamentalUseCaseFactory` 호출 → `SyncStockFundamentalUseCase.execute`
- 결과 logger.info (total / success / failed)
- 실패율 10% 초과 시 logger.error (운영 oncall 알람, 작업계획서 § 7.2 / § 11.1 #7)
- 모든 예외 swallow — 다음 cron tick 정상 동작 보장
- 거래일 판정은 cron 트리거가 mon-fri 만 발화 — 별도 holiday filter 는 운영 검증 후 결정

호출자:
- `StockFundamentalScheduler` 의 등록된 daily cron job (KST 18:00)
- 수동 호출도 가능 (운영 dry-run / 백필 시)
"""

from __future__ import annotations

import logging

from app.adapter.web._deps import SyncStockFundamentalUseCaseFactory

logger = logging.getLogger(__name__)


# ADR § 14.6 deferred — Phase B 후반 운영 1주 모니터 후 조정 (§ 11.1 #7).
# 현재 디폴트 10% — vendor 일시 장애 / 자격증명 한도 의심 임계값.
FAILURE_RATIO_ALERT_THRESHOLD: float = 0.10


async def fire_stock_fundamental_sync(
    *,
    factory: SyncStockFundamentalUseCaseFactory,
    alias: str,
) -> None:
    """일간 stock fundamental sync 콜백 — best-effort, 예외 swallow.

    Parameters:
        factory: lifespan 에서 set 된 SyncStockFundamentalUseCaseFactory
        alias: 사용할 키움 자격증명 alias (settings.scheduler_fundamental_sync_alias)
    """
    logger.info("stock fundamental sync cron 시작 — alias=%s", alias)
    try:
        async with factory(alias) as use_case:
            result = await use_case.execute()
    except Exception:  # noqa: BLE001 — cron 콜백은 모든 예외 swallow
        logger.exception("stock fundamental sync 콜백 예외 — alias=%s", alias)
        return

    failure_ratio = (result.failed / result.total) if result.total > 0 else 0.0

    if failure_ratio > FAILURE_RATIO_ALERT_THRESHOLD:
        # 실패율 임계 초과 — 자격증명 / RPS / 키움 장애 의심 (작업계획서 § 11.1 #7)
        failed_codes = [e.stock_code for e in result.errors[:10]]
        logger.error(
            "stock fundamental sync 실패율 과다 — total=%d success=%d failed=%d ratio=%.2f sample_failed=%s",
            result.total,
            result.success,
            result.failed,
            failure_ratio,
            failed_codes,
        )
    elif result.failed > 0:
        logger.warning(
            "stock fundamental sync 부분 실패 — total=%d success=%d failed=%d ratio=%.2f",
            result.total,
            result.success,
            result.failed,
            failure_ratio,
        )
    else:
        logger.info(
            "stock fundamental sync 완료 — total=%d success=%d",
            result.total,
            result.success,
        )


__all__ = ["FAILURE_RATIO_ALERT_THRESHOLD", "fire_stock_fundamental_sync"]
