"""SyncStockMasterUseCase — 5 시장 종목 마스터 동기화.

설계: endpoint-03-ka10099.md § 6.3.

원자성 / 격리 (sector 패턴 일관):
- 시장 단위 트랜잭션 — `session_provider` 가 시장마다 새 AsyncSession 생성
- 시장 N 호출 실패해도 시장 1~N-1 의 변경 보존 (commit 완료)
- KiwoomError 캐치 + `MarketStockOutcome.error` 기록 + 다음 시장 진행
- ValueError (응답 row 의 listCount/lastPrice 비숫자) → KiwoomResponseValidationError 매핑

mock 환경 안전판 (§4.2):
- `mock_env=True` 면 응답의 `nxtEnable` 무시 + 일률 False — mock 도메인은 NXT 미지원

빈 응답 보호 (§5.3):
- response.items 가 빈 list 면 `deactivate_missing` 호출 SKIP
- 이유: KOSPI 시장이 우연히 빈 응답을 반환하면 모든 KOSPI 종목이 비활성화되는 사고

DEFAULT_MARKETS (§2.3 P0+P1):
- KOSPI(0), KOSDAQ(10), KONEX(50), ETN(60), REIT(6) — 5종.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import asdict, dataclass, replace
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._exceptions import (
    KiwoomError,
    KiwoomResponseValidationError,
)
from app.adapter.out.kiwoom.stkinfo import KiwoomStkInfoClient, NormalizedStock, StockListRow
from app.adapter.out.persistence.repositories.stock import StockRepository
from app.application.constants import (
    STOCK_SYNC_DEFAULT_MARKETS,
    StockListMarketType,
)

logger = logging.getLogger(__name__)


SUPPORTED_STOCK_MARKETS: Final[tuple[StockListMarketType, ...]] = STOCK_SYNC_DEFAULT_MARKETS
"""5 시장 — 0:KOSPI / 10:KOSDAQ / 50:KONEX / 60:ETN / 6:REIT (Phase B P0+P1)."""


@dataclass(frozen=True, slots=True)
class MarketStockOutcome:
    """시장 단위 동기화 결과. 실패 시 `error` 에 도메인 예외 클래스명 + 메시지."""

    market_code: str
    fetched: int
    upserted: int
    deactivated: int
    nxt_enabled_count: int
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


@dataclass(frozen=True, slots=True)
class StockMasterSyncResult:
    """5 시장 전체 동기화 결과 — 부분 실패 허용 (§8.1)."""

    markets: list[MarketStockOutcome]
    total_fetched: int
    total_upserted: int
    total_deactivated: int
    total_nxt_enabled: int

    @property
    def all_succeeded(self) -> bool:
        return all(m.succeeded for m in self.markets)


class SyncStockMasterUseCase:
    """5 시장 종목 마스터를 키움에서 가져와 stock 테이블 동기화.

    의존성 주입:
    - `session_provider`: `() -> AsyncContextManager[AsyncSession]` — 시장마다 새 세션
    - `stkinfo_client`: 공유 KiwoomStkInfoClient (KiwoomClient 위임)
    - `mock_env`: True 면 응답의 nxtEnable 무시 (§4.2)

    한 시장 실패가 다른 시장 적재를 막지 않음 — `KiwoomError` catch + outcome.error 기록.
    """

    def __init__(
        self,
        *,
        session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
        stkinfo_client: KiwoomStkInfoClient,
        mock_env: bool = False,
        markets: Sequence[StockListMarketType] | None = None,
    ) -> None:
        self._session_provider = session_provider
        self._client = stkinfo_client
        self._mock_env = mock_env
        self._markets: tuple[StockListMarketType, ...] = (
            tuple(markets) if markets is not None else SUPPORTED_STOCK_MARKETS
        )

    async def execute(self) -> StockMasterSyncResult:
        """5 시장 순회 + 시장 단위 격리. 결과 dataclass 반환."""
        outcomes: list[MarketStockOutcome] = []

        for mrkt in self._markets:
            outcome = await self._sync_one_market(mrkt)
            outcomes.append(outcome)

        return StockMasterSyncResult(
            markets=outcomes,
            total_fetched=sum(m.fetched for m in outcomes),
            total_upserted=sum(m.upserted for m in outcomes),
            total_deactivated=sum(m.deactivated for m in outcomes),
            total_nxt_enabled=sum(m.nxt_enabled_count for m in outcomes),
        )

    async def _sync_one_market(self, mrkt: StockListMarketType) -> MarketStockOutcome:
        """단일 시장 sync — 자체 트랜잭션. 실패 outcome 으로 격리."""
        # 1. 키움 API 호출 — 트랜잭션 밖 (DB 락 점유 시간 최소화)
        try:
            response = await self._client.fetch_stock_list(mrkt)
        except KiwoomError as exc:
            return _failure_outcome(mrkt.value, fetched=0, exc=exc, log_label="ka10099 fetch")

        raw_rows: list[StockListRow] = response.items
        fetched = len(raw_rows)

        # 2. 정규화 — listCount/lastPrice 비숫자 ValueError 시 KiwoomResponseValidationError 매핑
        try:
            normalized = [r.to_normalized(mrkt.value, mock_env=self._mock_env) for r in raw_rows]
        except ValueError as exc:
            wrapped = KiwoomResponseValidationError(
                f"ka10099 응답 row 정규화 실패 mrkt_tp={mrkt.value} — 비숫자 listCount/lastPrice"
            )
            wrapped.__cause__ = None
            wrapped.__context__ = None
            wrapped.__suppress_context__ = True
            del exc  # 명시적 — exc 변수 누설 차단
            return _failure_outcome(mrkt.value, fetched=fetched, exc=wrapped, log_label="ka10099 정규화")

        # mock 환경 안전판은 to_normalized 단계에서 이미 적용됨 (mock_env=True 시 nxt_enable 강제 False)
        # belt-and-suspenders — 추가 검증 (혹시 False 인 코드 경로가 있을 시)
        if self._mock_env:
            normalized = [replace(n, nxt_enable=False) for n in normalized]

        present_codes = {n.stock_code for n in normalized}
        nxt_enabled_count = sum(1 for n in normalized if n.nxt_enable)
        rows_dict = [_to_row_dict(n) for n in normalized]

        # 3. DB 영속화 — 시장 단위 트랜잭션 (실패 시 그 시장만 rollback)
        try:
            async with self._session_provider() as session, session.begin():
                repo = StockRepository(session)
                upserted = await repo.upsert_many(rows_dict)
                # 빈 응답 보호 — present_codes 가 비어있으면 deactivate skip (§5.3)
                if present_codes:
                    deactivated = await repo.deactivate_missing(mrkt.value, present_codes)
                else:
                    deactivated = 0
        except Exception as exc:  # noqa: BLE001 — DB 예외도 시장 단위 격리
            return _failure_outcome(mrkt.value, fetched=fetched, exc=exc, log_label="stock 적재")

        return MarketStockOutcome(
            market_code=mrkt.value,
            fetched=fetched,
            upserted=upserted,
            deactivated=deactivated,
            nxt_enabled_count=nxt_enabled_count,
        )


def _failure_outcome(
    market_code: str,
    *,
    fetched: int,
    exc: BaseException,
    log_label: str,
) -> MarketStockOutcome:
    """실패 outcome 생성 + warning log.

    1R M-2 — outcome.error 는 클래스명 only (응답 본문 echo 차단). 메시지는 logger
    경로로만 노출 (운영 디버깅). admin 키 노출/공유 시 키움 응답 본문이 외부로
    전달되는 경로 차단.
    """
    err_class = type(exc).__name__
    logger.warning("stock sync %s 실패 mrkt_tp=%s: %s: %s", log_label, market_code, err_class, exc)
    return MarketStockOutcome(
        market_code=market_code,
        fetched=fetched,
        upserted=0,
        deactivated=0,
        nxt_enabled_count=0,
        error=err_class,
    )


def _to_row_dict(n: NormalizedStock) -> dict[str, Any]:
    """NormalizedStock dataclass → upsert 용 dict.

    `requested_market_type` 는 영속화 안 함 — 응답 검증/디버깅용 메타.
    """
    full = asdict(n)
    full.pop("requested_market_type", None)
    return full


__all__ = [
    "MarketStockOutcome",
    "SUPPORTED_STOCK_MARKETS",
    "StockMasterSyncResult",
    "SyncStockMasterUseCase",
]
