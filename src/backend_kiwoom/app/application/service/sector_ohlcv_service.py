"""IngestSectorDailyUseCase + IngestSectorDailyBulkUseCase — ka20006 (D-1).

설계: endpoint-13-ka20006.md § 6.3~6.4 + § 12.

ka10094 IngestPeriodicOhlcvUseCase 의 KRX only 패턴 응용 — 단, period dispatch 없음
(단일 endpoint) + sector_id 입력 (plan § 12.2 #9).

특징 (plan § 12):
- #2 sector_id FK = `INTEGER REFERENCES kiwoom.sector(id)`
- #4 NXT 호출 = skip. `SectorIngestOutcome(skipped=True, reason="nxt_sector_not_supported")`
- #5 sector_master_missing 가드 = `SectorIngestOutcome(skipped=True, reason="sector_master_missing")`
- #9 UseCase 입력 = sector_id (PK) + base_date

H-5 (cron 07:00 KST KRX rate limit 경합) — 기존 KRX rate limit lock (asyncio.Lock) 으로 안전.
H-6 (sector_master_missing 가드) — 본 결정 #5.
H-7 (NXT skip 정책) — sector 도메인에 NXT 없음 → 본 chunk 무관. 가드 코드만 추가.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._exceptions import KiwoomError
from app.adapter.out.kiwoom.chart import KiwoomChartClient, SectorChartRow
from app.adapter.out.persistence.models import Sector
from app.adapter.out.persistence.repositories.sector_price import (
    SectorPriceDailyRepository,
)
from app.application.constants import ExchangeType
from app.application.dto.sector_ohlcv import (
    IngestSectorDailyInput,
    SectorBulkSyncResult,
    SectorIngestOutcome,
)

logger = logging.getLogger(__name__)


SessionProvider = Callable[[], AbstractAsyncContextManager[AsyncSession]]
"""세션 팩토리 — `async with provider() as session:` 패턴."""


class IngestSectorDailyUseCase:
    """ka20006 호출 → kiwoom.sector_price_daily 적재 (단일 sector, D-1).

    의존성 주입:
    - `session_provider`: `() -> AsyncContextManager[AsyncSession]`
    - `chart_client`: `KiwoomChartClient` (`fetch_sector_daily` 사용)

    입력 (plan § 12.2 #9): `sector_id` (PK) + `base_date`. exchange 는 옵션 (디폴트 KRX).
    """

    def __init__(
        self,
        *,
        session_provider: SessionProvider,
        chart_client: KiwoomChartClient,
    ) -> None:
        self._session_provider = session_provider
        self._client = chart_client

    async def execute(
        self,
        *,
        sector_id: int,
        base_date: date,
        exchange: ExchangeType = ExchangeType.KRX,
    ) -> SectorIngestOutcome:
        """단일 sector 적재.

        Parameters:
            sector_id: kiwoom.sector(id) FK.
            base_date: 기준일자.
            exchange: 디폴트 KRX. NXT 면 skip outcome (plan § 12.2 #4).

        Returns:
            SectorIngestOutcome — 성공 시 upserted>0, 실패/skip 시 skipped=True+reason.
        """
        # plan § 12.2 #4 — NXT 가드 (sector 도메인에 NXT 없음 — 가드 코드만)
        if exchange is ExchangeType.NXT:
            logger.info(
                "ka20006 NXT 호출 요청 skip — sector_id=%d (plan § 12.2 #4)",
                sector_id,
            )
            return SectorIngestOutcome(
                sector_id=sector_id,
                skipped=True,
                reason="nxt_sector_not_supported",
            )

        # 1. sector 마스터 조회 (plan § 12.2 #5 — sector_master_missing 가드)
        async with self._session_provider() as session:
            stmt = select(Sector).where(Sector.id == sector_id)
            sector = (await session.execute(stmt)).scalar_one_or_none()

        if sector is None:
            logger.warning(
                "ka20006 sector_master_missing — sector_id=%d (ka10101 sync 선행 필요)",
                sector_id,
            )
            return SectorIngestOutcome(
                sector_id=sector_id,
                skipped=True,
                reason="sector_master_missing",
            )

        if not sector.is_active:
            logger.info(
                "ka20006 sector_inactive skip — sector_id=%d sector_code=%s",
                sector_id,
                sector.sector_code,
            )
            return SectorIngestOutcome(
                sector_id=sector_id,
                sector_code=sector.sector_code,
                skipped=True,
                reason="sector_inactive",
            )

        # 2. 키움 호출
        raw_rows = await self._client.fetch_sector_daily(
            sector.sector_code,
            base_date=base_date,
        )

        # 3. 정규화 + DB upsert — dict / SectorChartRow 양쪽 수용 (테스트 호환).
        # 운영에서는 항상 SectorChartRow 가 반환되지만 mock stub 은 dict 가능.
        normalized = [
            (SectorChartRow.model_validate(r) if isinstance(r, dict) else r).to_normalized(sector_id=sector.id)
            for r in raw_rows
        ]
        async with self._session_provider() as session, session.begin():
            repo = SectorPriceDailyRepository(session)
            upserted = await repo.upsert_many(normalized)

        return SectorIngestOutcome(
            sector_id=sector.id,
            sector_code=sector.sector_code,
            upserted=upserted,
        )


class IngestSectorDailyBulkUseCase:
    """모든 active sector 의 일봉 일괄 적재 (D-1, plan § 12.2 #4 — active 전체 iterate).

    의존성 주입:
    - `session_provider`: `() -> AsyncContextManager[AsyncSession]`
    - `chart_client`: `KiwoomChartClient`

    H-1 (sector 매핑) — `list_all_active` 결과 iterate. 각 sector 의 sector_id 를 단건
    UseCase 에 전달.
    """

    def __init__(
        self,
        *,
        session_provider: SessionProvider,
        chart_client: KiwoomChartClient,
    ) -> None:
        self._session_provider = session_provider
        self._client = chart_client
        self._single = IngestSectorDailyUseCase(
            session_provider=session_provider,
            chart_client=chart_client,
        )

    async def execute(self, *, base_date: date) -> SectorBulkSyncResult:
        """active sector 전체 sync.

        Returns:
            SectorBulkSyncResult — total / success / failed + errors tuple.

        per-sector try/except — partial-failure 격리. KiwoomError / 일반 예외 모두 다음
        sector 로 진행.
        """
        # 1. active sector 조회
        async with self._session_provider() as session:
            stmt = select(Sector).where(Sector.is_active.is_(True)).order_by(Sector.market_code, Sector.sector_code)
            sectors = list((await session.execute(stmt)).scalars())

        if not sectors:
            logger.info("ka20006 bulk sync — active sector 0개 (ka10101 sync 권고)")
            return SectorBulkSyncResult(total=0, success=0, failed=0, skipped=0, errors=())

        # 1R HIGH #5 fix — skipped 와 failed 분리:
        # - skipped: outcome.skipped=True (NXT/sector_inactive/sector_master_missing — 정상 운영)
        # - failed: 실제 예외 (KiwoomError / Exception — 디버깅 필요)
        # FAILURE_RATIO_ALERT_THRESHOLD 가 sector_inactive 케이스에서 허위 경보 내지 않도록.
        success = 0
        failed = 0
        skipped = 0
        errors: list[str] = []

        for sector in sectors:
            try:
                outcome = await self._single.execute(
                    sector_id=sector.id,
                    base_date=base_date,
                )
                if outcome.skipped:
                    skipped += 1
                    # 정보성 로그만 — errors 에는 추가 안 함 (failure 와 분리)
                    logger.info(
                        "ka20006 bulk sync skipped — sector_id=%d sector_code=%s reason=%s",
                        sector.id,
                        sector.sector_code,
                        outcome.reason,
                    )
                elif outcome.upserted > 0:
                    success += 1
                else:
                    success += 1  # 빈 응답도 성공 (운영적 정상)
            except KiwoomError as exc:
                failed += 1
                errors.append(f"sector_id={sector.id} {type(exc).__name__}")
                logger.warning(
                    "ka20006 bulk sync 실패 sector_id=%d sector_code=%s: %s",
                    sector.id,
                    sector.sector_code,
                    type(exc).__name__,
                )
            except Exception as exc:  # noqa: BLE001 — partial-failure 격리
                failed += 1
                errors.append(f"sector_id={sector.id} {type(exc).__name__}")
                logger.exception(
                    "ka20006 bulk sync 예상치 못한 예외 sector_id=%d",
                    sector.id,
                )

        return SectorBulkSyncResult(
            total=len(sectors),
            success=success,
            failed=failed,
            skipped=skipped,
            errors=tuple(errors),
        )


__all__ = [
    "IngestSectorDailyBulkUseCase",
    "IngestSectorDailyInput",
    "IngestSectorDailyUseCase",
    "SectorBulkSyncResult",
    "SectorIngestOutcome",
    "SessionProvider",
]
