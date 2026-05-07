"""SyncSectorMasterUseCase — 5 시장 업종 마스터 동기화.

설계: endpoint-14-ka10101.md § 6.3.

원자성 / 격리:
- 시장 단위 트랜잭션 — `session_provider` 가 시장마다 새 AsyncSession 생성
- 시장 N 호출 실패해도 시장 1~N-1 의 변경 보존 (commit 완료)
- KiwoomError 캐치 + `MarketSyncOutcome.error` 기록 + 다음 시장 진행

트랜잭션 경계:
- `async with session_provider() as session:` 안에서 `session.begin()` 트랜잭션
- 시장 sync 성공 → commit / 실패 (KiwoomError) → context exit 시 자동 rollback
- DB 예외 (IntegrityError 등) 는 시장 단위 롤백 후 outcome.error 기록

mrkt_tp Literal 안전성:
- `SUPPORTED_MARKETS` 가 `tuple[Literal[...], ...]` 로 선언 — mypy 가 fetch_sectors
  의 `Literal["0","1","2","4","7"]` 시그니처와 정합
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Final, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._exceptions import KiwoomError
from app.adapter.out.kiwoom.stkinfo import KiwoomStkInfoClient
from app.adapter.out.persistence.repositories.sector import SectorRepository

logger = logging.getLogger(__name__)

MarketCode = Literal["0", "1", "2", "4", "7"]

SUPPORTED_MARKETS: Final[tuple[MarketCode, ...]] = ("0", "1", "2", "4", "7")
"""5 시장 — 0:KOSPI / 1:KOSDAQ / 2:KOSPI200 / 4:KOSPI100 / 7:KRX100."""


@dataclass(frozen=True, slots=True)
class MarketSyncOutcome:
    """시장 단위 동기화 결과. 실패 시 `error` 에 도메인 예외 클래스명 + 메시지."""

    market_code: str
    fetched: int
    upserted: int
    deactivated: int
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


@dataclass(frozen=True, slots=True)
class SectorSyncResult:
    """5 시장 전체 동기화 결과 — 부분 실패 허용 (계획서 § 8.1)."""

    markets: list[MarketSyncOutcome]
    total_fetched: int
    total_upserted: int
    total_deactivated: int

    @property
    def all_succeeded(self) -> bool:
        return all(m.succeeded for m in self.markets)


class SyncSectorMasterUseCase:
    """5 시장 업종 마스터를 키움에서 가져와 sector 테이블 동기화.

    의존성 주입:
    - `session_provider`: `() -> AsyncContextManager[AsyncSession]` — 시장마다 새 세션
    - `stkinfo_client`: 공유 KiwoomStkInfoClient (KiwoomClient 위임)

    한 시장 실패가 다른 시장 적재를 막지 않음 — `KiwoomError` catch + outcome.error 기록.
    """

    def __init__(
        self,
        *,
        session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
        stkinfo_client: KiwoomStkInfoClient,
    ) -> None:
        self._session_provider = session_provider
        self._client = stkinfo_client

    async def execute(self) -> SectorSyncResult:
        """5 시장 순회 + 시장 단위 격리. 결과 dataclass 반환."""
        outcomes: list[MarketSyncOutcome] = []

        for mrkt_tp in SUPPORTED_MARKETS:
            outcome = await self._sync_one_market(mrkt_tp)
            outcomes.append(outcome)

        return SectorSyncResult(
            markets=outcomes,
            total_fetched=sum(m.fetched for m in outcomes),
            total_upserted=sum(m.upserted for m in outcomes),
            total_deactivated=sum(m.deactivated for m in outcomes),
        )

    async def _sync_one_market(self, mrkt_tp: MarketCode) -> MarketSyncOutcome:
        """단일 시장 sync — 자체 트랜잭션. 실패 outcome 으로 격리."""
        # 1. 키움 API 호출 — 트랜잭션 밖 (DB 락 점유 시간 최소화)
        try:
            response = await self._client.fetch_sectors(mrkt_tp)
        except KiwoomError as exc:
            err_msg = f"{type(exc).__name__}: {exc}"
            logger.warning("sector sync 실패 mrkt_tp=%s: %s", mrkt_tp, err_msg)
            return MarketSyncOutcome(
                market_code=mrkt_tp,
                fetched=0,
                upserted=0,
                deactivated=0,
                error=err_msg,
            )

        rows = [
            {
                "market_code": mrkt_tp,
                "sector_code": r.code,
                "sector_name": r.name,
                "group_no": r.group or None,
            }
            for r in response.items
        ]
        present_codes = {r.code for r in response.items}
        fetched = len(response.items)

        # 2. DB 영속화 — 시장 단위 트랜잭션 (실패 시 그 시장만 rollback)
        try:
            async with self._session_provider() as session, session.begin():
                repo = SectorRepository(session)
                upserted = await repo.upsert_many(rows)
                deactivated = await repo.deactivate_missing(mrkt_tp, present_codes)
        except Exception as exc:  # noqa: BLE001 — DB 예외도 시장 단위로 격리
            err_msg = f"{type(exc).__name__}: {exc}"
            logger.warning("sector sync DB 실패 mrkt_tp=%s: %s", mrkt_tp, err_msg)
            return MarketSyncOutcome(
                market_code=mrkt_tp,
                fetched=fetched,
                upserted=0,
                deactivated=0,
                error=err_msg,
            )

        return MarketSyncOutcome(
            market_code=mrkt_tp,
            fetched=fetched,
            upserted=upserted,
            deactivated=deactivated,
        )


__all__ = [
    "MarketCode",
    "MarketSyncOutcome",
    "SUPPORTED_MARKETS",
    "SectorSyncResult",
    "SyncSectorMasterUseCase",
]
