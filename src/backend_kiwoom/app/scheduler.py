"""SectorSyncScheduler — APScheduler AsyncIOScheduler 래퍼.

설계: endpoint-14-ka10101.md § 7.2.

책임:
- AsyncIOScheduler 1개 보유 — 현재 이벤트 루프에 묶임
- `scheduler_enabled=False` 시 start 호출 무시 (운영 실수 방어)
- 일요일 KST 03:00 CronTrigger + max_instances=1 + coalesce=True
- start 멱등성 — 재 호출해도 중복 등록 방지 (`replace_existing=True` 패턴)
- shutdown(wait=True) — 진행 중 job 완료 대기 (graceful)

lifespan 통합 순서 (main.py):
1. startup: scheduler.start (settings.scheduler_enabled 가 True 일 때만 실제 기동)
2. shutdown: scheduler.shutdown(wait=True) → 그 다음 graceful token revoke → engine.dispose

cron 트리거 시점에 KiwoomClient 빌드 + DB 호출이 발생하므로 graceful shutdown 직전에
scheduler 를 먼저 멈춰야 token revoke 와 충돌 없음.
"""

from __future__ import annotations

import logging
from typing import Final
from zoneinfo import ZoneInfo

from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.adapter.web._deps import (
    SyncSectorUseCaseFactory,
    SyncStockFundamentalUseCaseFactory,
    SyncStockMasterUseCaseFactory,
)
from app.batch.sector_sync_job import fire_sector_sync
from app.batch.stock_fundamental_job import fire_stock_fundamental_sync
from app.batch.stock_master_job import fire_stock_master_sync

logger = logging.getLogger(__name__)

KST: Final[ZoneInfo] = ZoneInfo("Asia/Seoul")

SECTOR_SYNC_JOB_ID: Final[str] = "sector_sync_weekly"
"""주간 sector sync job 의 고유 ID — replace_existing 멱등성 키."""

STOCK_MASTER_SYNC_JOB_ID: Final[str] = "stock_master_sync_daily"
"""일간 stock master sync job 의 고유 ID (B-α)."""

STOCK_FUNDAMENTAL_SYNC_JOB_ID: Final[str] = "stock_fundamental_sync_daily"
"""일간 stock fundamental sync job 의 고유 ID (B-γ-2). KST 18:00 mon-fri — ka10099 (17:30) 30분 후."""


class SectorSyncScheduler:
    """주간 sector sync cron job 1개를 관리하는 단순 wrapper.

    Phase A3 의 sector sync 전용 — 단일 job. B-α 에서 stock master 용으로 별도
    `StockMasterScheduler` 클래스가 같은 파일에 추가됨 (동일 패턴, 별도 lifecycle).

    enabled=False 일 때는 AsyncIOScheduler 자체를 만들지만 start 를 호출 안 함 →
    is_running=False, job_count=0.
    """

    def __init__(
        self,
        *,
        factory: SyncSectorUseCaseFactory,
        alias: str,
        enabled: bool,
    ) -> None:
        self._factory = factory
        self._alias = alias
        self._enabled = enabled
        self._scheduler = AsyncIOScheduler(timezone=KST)
        self._started = False

    @property
    def is_running(self) -> bool:
        """scheduler 가 시작됐고 아직 정지 안 됐는지 — 호출자 의도 기반.

        AsyncIOScheduler.shutdown(wait=False) 는 비동기 cleanup 이라 직후
        `self._scheduler.running` 이 잠시 True 로 남을 수 있음. `_started` 플래그를
        진실의 원천으로 사용.
        """
        return self._started and self._scheduler.running

    @property
    def job_count(self) -> int:
        """등록된 job 수 — `enabled=False` 면 0."""
        return len(self._scheduler.get_jobs())

    def get_job(self, job_id: str) -> Job | None:
        return self._scheduler.get_job(job_id)

    def start(self) -> None:
        """scheduler 기동 + sector sync job 등록.

        `enabled=False` 면 no-op. 멱등성 — 두 번째 호출은 무시.
        """
        if not self._enabled:
            logger.info("scheduler disabled — start 무시")
            return
        if self._started:
            logger.debug("scheduler 이미 시작됨 — start 무시")
            return

        self._scheduler.add_job(
            fire_sector_sync,
            trigger=CronTrigger(
                day_of_week="sun",
                hour=3,
                minute=0,
                timezone=KST,
            ),
            id=SECTOR_SYNC_JOB_ID,
            kwargs={
                "factory": self._factory,
                "alias": self._alias,
            },
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        self._scheduler.start()
        self._started = True
        logger.info(
            "scheduler 시작 — job=%s alias=%s cron=일 03:00 KST",
            SECTOR_SYNC_JOB_ID,
            self._alias,
        )

    def shutdown(self, *, wait: bool = True) -> None:
        """scheduler 정지. 미기동 상태에서 호출돼도 안전.

        Parameters:
            wait: True 면 진행 중 job 완료 대기 (graceful). False 면 즉시 정지.
        """
        if not self._scheduler.running:
            self._started = False
            return
        try:
            self._scheduler.shutdown(wait=wait)
        except Exception:  # noqa: BLE001 — shutdown 은 모든 예외 swallow
            logger.exception("scheduler shutdown 예외")
        finally:
            self._started = False


class StockMasterScheduler:
    """일간 stock master sync cron job 1개를 관리하는 단순 wrapper (B-α).

    sector scheduler 와 동일 패턴 — 별도 AsyncIOScheduler 보유 (sector cron 과 독립
    lifecycle). enabled=False 시 start no-op.

    cron: KST mon-fri 17:30 (장 마감 후 신규 상장/상장폐지 반영, §7.2).
    """

    def __init__(
        self,
        *,
        factory: SyncStockMasterUseCaseFactory,
        alias: str,
        enabled: bool,
    ) -> None:
        self._factory = factory
        self._alias = alias
        self._enabled = enabled
        self._scheduler = AsyncIOScheduler(timezone=KST)
        self._started = False

    @property
    def is_running(self) -> bool:
        return self._started and self._scheduler.running

    @property
    def job_count(self) -> int:
        return len(self._scheduler.get_jobs())

    def get_job(self, job_id: str) -> Job | None:
        return self._scheduler.get_job(job_id)

    def start(self) -> None:
        """scheduler 기동 + stock master sync job 등록.

        `enabled=False` 면 no-op. 멱등성 — 두 번째 호출은 무시.
        """
        if not self._enabled:
            logger.info("stock master scheduler disabled — start 무시")
            return
        if self._started:
            logger.debug("stock master scheduler 이미 시작됨 — start 무시")
            return

        self._scheduler.add_job(
            fire_stock_master_sync,
            trigger=CronTrigger(
                day_of_week="mon-fri",
                hour=17,
                minute=30,
                timezone=KST,
            ),
            id=STOCK_MASTER_SYNC_JOB_ID,
            kwargs={
                "factory": self._factory,
                "alias": self._alias,
            },
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        self._scheduler.start()
        self._started = True
        logger.info(
            "stock master scheduler 시작 — job=%s alias=%s cron=mon-fri 17:30 KST",
            STOCK_MASTER_SYNC_JOB_ID,
            self._alias,
        )

    def shutdown(self, *, wait: bool = True) -> None:
        """scheduler 정지. 미기동 상태에서 호출돼도 안전."""
        if not self._scheduler.running:
            self._started = False
            return
        try:
            self._scheduler.shutdown(wait=wait)
        except Exception:  # noqa: BLE001 — shutdown 모든 예외 swallow
            logger.exception("stock master scheduler shutdown 예외")
        finally:
            self._started = False


class StockFundamentalScheduler:
    """일간 stock fundamental sync cron job 1개를 관리하는 단순 wrapper (B-γ-2).

    StockMasterScheduler 와 동일 패턴 — 별도 AsyncIOScheduler. cron: KST mon-fri 18:00
    (ADR § 14.1 결정 — ka10099 stock master cron 17:30 의 30분 후, master 갱신 완료 후
    is_active stock 조회 시점에 마스터 최신화 보장. 작업계획서 § 7.2 의 17:45 와는 별도
    결정).

    enabled=False 시 start no-op.
    """

    def __init__(
        self,
        *,
        factory: SyncStockFundamentalUseCaseFactory,
        alias: str,
        enabled: bool,
    ) -> None:
        self._factory = factory
        self._alias = alias
        self._enabled = enabled
        self._scheduler = AsyncIOScheduler(timezone=KST)
        self._started = False

    @property
    def is_running(self) -> bool:
        return self._started and self._scheduler.running

    @property
    def job_count(self) -> int:
        return len(self._scheduler.get_jobs())

    def get_job(self, job_id: str) -> Job | None:
        return self._scheduler.get_job(job_id)

    def start(self) -> None:
        """scheduler 기동 + stock fundamental sync job 등록.

        `enabled=False` 면 no-op. 멱등성 — 두 번째 호출은 무시.
        """
        if not self._enabled:
            logger.info("stock fundamental scheduler disabled — start 무시")
            return
        if self._started:
            logger.debug("stock fundamental scheduler 이미 시작됨 — start 무시")
            return

        self._scheduler.add_job(
            fire_stock_fundamental_sync,
            trigger=CronTrigger(
                day_of_week="mon-fri",
                hour=18,
                minute=0,
                timezone=KST,
            ),
            id=STOCK_FUNDAMENTAL_SYNC_JOB_ID,
            kwargs={
                "factory": self._factory,
                "alias": self._alias,
            },
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        self._scheduler.start()
        self._started = True
        logger.info(
            "stock fundamental scheduler 시작 — job=%s alias=%s cron=mon-fri 18:00 KST",
            STOCK_FUNDAMENTAL_SYNC_JOB_ID,
            self._alias,
        )

    def shutdown(self, *, wait: bool = True) -> None:
        """scheduler 정지. 미기동 상태에서 호출돼도 안전."""
        if not self._scheduler.running:
            self._started = False
            return
        try:
            self._scheduler.shutdown(wait=wait)
        except Exception:  # noqa: BLE001 — shutdown 모든 예외 swallow
            logger.exception("stock fundamental scheduler shutdown 예외")
        finally:
            self._started = False


__all__ = [
    "KST",
    "SECTOR_SYNC_JOB_ID",
    "STOCK_FUNDAMENTAL_SYNC_JOB_ID",
    "STOCK_MASTER_SYNC_JOB_ID",
    "SectorSyncScheduler",
    "StockFundamentalScheduler",
    "StockMasterScheduler",
]
