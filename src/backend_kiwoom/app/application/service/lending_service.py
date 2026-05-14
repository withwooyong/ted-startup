"""IngestLendingMarketUseCase + IngestLendingStockUseCase + IngestLendingStockBulkUseCase.

설계: endpoint-16-ka10068.md § 6.3 + endpoint-17-ka20068.md § 6.3 + endpoint-15-ka10014.md § 12.

3 UseCase:
- `IngestLendingMarketUseCase` — ka10068 시장 단위 단일 호출 (plan § 12.2 #4 NXT 미적용).
- `IngestLendingStockUseCase` — ka20068 종목 단위 단건 (plan § 12.2 #4 KRX only, Length=6).
- `IngestLendingStockBulkUseCase` — active 종목 iterate (plan § 12.2 #10 partial 5%/15%).

테스트 호환 시그니처:
- `IngestLendingMarketUseCase(session=session, slb_client=client)` — session 직접 주입.
- `IngestLendingStockUseCase(session=session, slb_client=client)` — stock 조회는 session 사용.
- `IngestLendingStockBulkUseCase(session=session, single_use_case=single_uc)`.
- 모든 UseCase 가 caller (라우터/배치 job) 에게 session.commit 위임.

NXT 정책 (plan § 12.2 #4):
- ka10068 — 시장 단위, NXT 분기 자체 없음.
- ka20068 — KRX only. fetch_stock_trend 가 Length=6 강제 → NXT suffix 거부.
  UseCase 도 NXT 호출 시도 안 함 (KRX 한 번만).

partial 임계치 (plan § 12.2 #10):
- lending_market = N/A (단일 호출이라 partial 개념 없음).
- lending_stock = 5% warning / 15% error_above_threshold.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from datetime import date
from typing import Final, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._exceptions import KiwoomBusinessError, KiwoomError
from app.adapter.out.kiwoom._records import LendingScope
from app.adapter.out.kiwoom.slb import KiwoomLendingClient
from app.adapter.out.kiwoom.stkinfo import SentinelStockCodeError
from app.adapter.out.persistence.models import Stock
from app.adapter.out.persistence.repositories.lending_balance import (
    LendingBalanceKwRepository,
)
from app.application.dto.lending import (
    IngestLendingStockInput,
    LendingMarketIngestOutcome,
    LendingStockBulkResult,
    LendingStockIngestOutcome,
)

# Phase F-2: alphanumeric pre-filter 정규식.
# Step 2 2a H-1: 앵커 (`^...$`) 명시 — `fullmatch` 와 함께 사용해도 의도 명확화 (부분
# 매치 회피). short_selling_service.py 와 패턴 일관.
_NUMERIC_STOCK_CODE_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9]{6}$")

logger = logging.getLogger(__name__)


# plan § 12.2 #10 — lending_stock partial 임계치 (5% warning / 15% error)
LENDING_STOCK_WARNING_THRESHOLD: float = 0.05
LENDING_STOCK_ERROR_THRESHOLD: float = 0.15


class IngestLendingMarketUseCase:
    """ka10068 시장 단위 대차 적재 — 단일 호출 (plan § 12.2 #4 NXT 미적용).

    의존성:
    - `session`: AsyncSession (caller 가 lifecycle 관리 + commit).
    - `slb_client`: KiwoomLendingClient.

    error 발생 시 outcome.error 에 격리 — raise 안 함.
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        slb_client: KiwoomLendingClient,
    ) -> None:
        self._session = session
        self._client = slb_client
        self._repo = LendingBalanceKwRepository(session)

    async def execute(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> LendingMarketIngestOutcome:
        """ka10068 호출 → scope=MARKET 적재.

        - KiwoomBusinessError → outcome.error 격리, upserted=0 (테스트 4 기대).
        - 응답 list=[] → upserted=0 (정상, 테스트 3 기대).
        - 성공 → outcome.upserted = repo 영향 row 수.
        """
        try:
            raw_rows = await self._client.fetch_market_trend(
                start_date=start_date, end_date=end_date,
            )
        except KiwoomBusinessError as exc:
            return LendingMarketIngestOutcome(
                start_date=start_date,
                end_date=end_date,
                fetched=0,
                upserted=0,
                error=f"business: return_code={exc.return_code}",
            )

        # LendingMarketRow.to_normalized(*, scope=) — plan § 3.3 endpoint-16.
        # scope=MARKET 고정 시 NormalizedLendingMarket.stock_id=None (CHECK constraint).
        normalized = [r.to_normalized(scope=LendingScope.MARKET) for r in raw_rows]
        upserted = await self._repo.upsert_market(normalized)

        return LendingMarketIngestOutcome(
            start_date=start_date,
            end_date=end_date,
            fetched=len(raw_rows),
            upserted=upserted,
        )


class IngestLendingStockUseCase:
    """ka20068 종목 단위 대차 적재 — KRX only (plan § 12.2 #4, Length=6 명세).

    의존성:
    - `session`: AsyncSession.
    - `slb_client`: KiwoomLendingClient.

    플로우:
    1. stock_code → kiwoom.stock 조회. 미존재 시 skipped=True (reason="stock_not_found").
    2. is_active=False → skipped=True (reason="inactive"). fetch_stock_trend 호출 안 함.
    3. nxt_enable=True 여도 NXT 시도 안 함 (KRX 한 번만, plan § 12.2 #4).
    4. KiwoomBusinessError → outcome.error 격리.
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        slb_client: KiwoomLendingClient,
        env: Literal["prod", "mock"] = "prod",
    ) -> None:
        self._session = session
        self._client = slb_client
        self._repo = LendingBalanceKwRepository(session)
        self._env = env

    async def execute(
        self,
        stock_code: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> LendingStockIngestOutcome:
        """단일 종목 ka20068 호출 + scope=STOCK 적재.

        Args:
            stock_code: 6자리 숫자 (NXT suffix 미지원).
            start_date / end_date: 옵션.

        Returns:
            LendingStockIngestOutcome — skipped/error/upserted.
        """
        # 1. stock 조회 (KRX only — nxt_enable 무관)
        stmt = select(Stock).where(Stock.stock_code == stock_code)
        stock = (await self._session.execute(stmt)).scalar_one_or_none()

        if stock is None:
            logger.info("ka20068 stock_not_found skip — stock_code=%s", stock_code)
            return LendingStockIngestOutcome(
                stock_code=stock_code,
                skipped=True,
                reason="stock_not_found",
            )

        if not stock.is_active:
            logger.info(
                "ka20068 inactive skip — stock_code=%s", stock_code
            )
            return LendingStockIngestOutcome(
                stock_code=stock_code,
                skipped=True,
                reason="inactive",
            )

        # 2. ka20068 호출 (KRX only — NXT 시도 안 함, plan § 12.2 #4)
        try:
            raw_rows = await self._client.fetch_stock_trend(
                stock_code,
                start_date=start_date,
                end_date=end_date,
            )
        except KiwoomBusinessError as exc:
            return LendingStockIngestOutcome(
                stock_code=stock_code,
                start_date=start_date,
                end_date=end_date,
                fetched=0,
                upserted=0,
                error=f"business: return_code={exc.return_code}",
            )

        # LendingStockRow.to_normalized(*, stock_id=) — plan § 3.3 endpoint-17.
        # scope=STOCK 고정 + FK stock_id (CHECK constraint 보장).
        normalized = [r.to_normalized(stock_id=stock.id) for r in raw_rows]
        upserted = await self._repo.upsert_stock(normalized)

        return LendingStockIngestOutcome(
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            fetched=len(raw_rows),
            upserted=upserted,
        )


class IngestLendingStockBulkUseCase:
    """ka20068 active 종목 일괄 적재.

    의존성:
    - `session`: AsyncSession (Stock 조회용).
    - `single_use_case`: IngestLendingStockUseCase (per-stock 실행).

    플로우:
    1. active stock 조회 (옵션: market_code / stock_code 필터).
    2. per-stock try/except — partial-failure 격리.
    3. plan § 12.2 #10 — 5% / 15% partial 임계치 (warning / error_above_threshold).

    BATCH_SIZE=50 마다 `session.commit()` 호출 (2R-C-3 fix) — 100분 long-running 중
    프로세스 kill / SIGTERM / OOM 시 all-or-nothing rollback 으로 백필 손실 방지.
    PostgreSQL idle-in-transaction 도 50건 단위로 해소되어 vacuum 차단 회피.
    """

    BATCH_SIZE: int = 50

    def __init__(
        self,
        *,
        session: AsyncSession,
        single_use_case: IngestLendingStockUseCase,
    ) -> None:
        self._session = session
        self._single = single_use_case

    async def execute(
        self,
        *,
        start_date: date,
        end_date: date,
        only_market_codes: Sequence[str] | None = None,
        only_stock_codes: Sequence[str] | None = None,
        filter_alphanumeric: bool = False,
    ) -> LendingStockBulkResult:
        """active 종목 sync.

        Args:
            filter_alphanumeric: Phase F-2 결정 #7 — True 시 ^[0-9]{6}$ 미일치 종목
                (alphanumeric / NXT suffix 등) 호출 자체 skip → total_alphanumeric_skipped
                증가. 기본값 False — 기존 caller (scheduler 등) 영향 없음.

        Returns:
            LendingStockBulkResult — per-stock outcomes + 집계 + partial 임계치 메시지 +
            total_alphanumeric_skipped (Phase F-2: pre-filter + sentinel catch 합산).
        """
        # 1. stock 조회 — Phase F-2 H-1 A (Step 2 2a/2b 리뷰): SQL 단 is_active 필터 복원.
        # short_selling_service.py 와 패턴 일관 (분모 의미 통일). 이전(Step 1) 에서 inactive
        # 종목까지 bulk loop 에 보내려 SQL 필터 제거했으나, 분모 (`total_stocks`) 가
        # inactive 까지 포함되어 `failure_ratio` 분모 정의가 모호해졌음 — SQL 필터 회복으로
        # active 분모 통일. inactive 종목의 outcome.skipped=True 분기는 단건 호출
        # (lending_router /sync 또는 single UC) 경로에서만 발생 (bulk 는 이미 active-only).
        stmt = select(Stock).where(Stock.is_active.is_(True))
        if only_market_codes:
            stmt = stmt.where(Stock.market_code.in_(only_market_codes))
        if only_stock_codes:
            stmt = stmt.where(Stock.stock_code.in_(only_stock_codes))
        stmt = stmt.order_by(Stock.market_code, Stock.stock_code)
        stocks = list((await self._session.execute(stmt)).scalars())

        # Phase F-2 결정 #7: alphanumeric pre-filter.
        # filter_alphanumeric=True 면 ^[0-9]{6}$ 미일치 종목을 호출 시점 이전에 제거.
        pre_filter_skipped: int = 0
        # Phase F-2 Step 2 MED-1: F-1 `FundamentalSyncResult.skipped` 패턴 미러.
        # 종목별 명세 보존 — KOSCOM cross-check 시 사유 식별 (`error` 컬럼 사용).
        alphanumeric_skipped_outcomes_list: list[LendingStockIngestOutcome] = []
        if filter_alphanumeric:
            kept: list[Stock] = []
            for s in stocks:
                if _NUMERIC_STOCK_CODE_RE.fullmatch(s.stock_code):
                    kept.append(s)
                else:
                    pre_filter_skipped += 1
                    alphanumeric_skipped_outcomes_list.append(
                        LendingStockIngestOutcome(
                            stock_code=s.stock_code,
                            error="alphanumeric_pre_filter",
                        )
                    )
            stocks = kept

        if not stocks:
            logger.info(
                "ka20068 bulk sync — active stock 0개 (only_market_codes=%s only_stock_codes=%s)",
                only_market_codes,
                only_stock_codes,
            )
            return LendingStockBulkResult(
                start_date=start_date,
                end_date=end_date,
                total_stocks=pre_filter_skipped,
                outcomes=(),
                total_alphanumeric_skipped=pre_filter_skipped,
                alphanumeric_skipped_outcomes=tuple(alphanumeric_skipped_outcomes_list),
            )

        outcomes: list[LendingStockIngestOutcome] = []
        total_fetched = 0
        total_upserted = 0
        total_skipped = 0
        total_failed = 0
        sentinel_skipped: int = 0

        for i, stock in enumerate(stocks, start=1):
            try:
                outcome = await self._single.execute(
                    stock.stock_code,
                    start_date=start_date,
                    end_date=end_date,
                )
            except SentinelStockCodeError:
                # Phase F-2 결정 #3 — sentinel skip 은 실패가 아님 (total_alphanumeric_skipped 분리).
                # KiwoomError / Exception 보다 먼저 catch (ValueError 상속이라
                # broader Exception 에 잡히지 않도록 분기 위치 우선).
                # Step 2 MED-1: 종목 명세 보존 (F-1 패턴) — outcomes 에는 미적재 (실제 호출만)
                # 하되, alphanumeric_skipped_outcomes 에는 사유와 함께 적재.
                sentinel_skipped += 1
                alphanumeric_skipped_outcomes_list.append(
                    LendingStockIngestOutcome(
                        stock_code=stock.stock_code,
                        error="sentinel_skip",
                    )
                )
                logger.info(
                    "ka20068 bulk sentinel skip stock_code=%s",
                    stock.stock_code,
                )
                # outcome 자체는 추가하지 않음 — outcomes 는 실제 호출 결과만 누적.
                # batch 진행률 로그 위해 i 그대로 사용.
                continue
            except KiwoomError as exc:
                err_class = type(exc).__name__
                logger.warning(
                    "ka20068 bulk per-stock 실패 stock_code=%s: %s",
                    stock.stock_code,
                    err_class,
                )
                outcome = LendingStockIngestOutcome(
                    stock_code=stock.stock_code,
                    error=err_class,
                )
                total_failed += 1
            except Exception as exc:  # noqa: BLE001 — per-stock 격리
                err_class = type(exc).__name__
                logger.exception(
                    "ka20068 bulk per-stock 예상치 못한 예외 stock_code=%s",
                    stock.stock_code,
                )
                outcome = LendingStockIngestOutcome(
                    stock_code=stock.stock_code,
                    error=err_class,
                )
                total_failed += 1
            else:
                if outcome.error is not None:
                    total_failed += 1
                elif outcome.skipped:
                    total_skipped += 1
                else:
                    total_fetched += outcome.fetched
                    total_upserted += outcome.upserted

            outcomes.append(outcome)

            # BATCH_SIZE 마다 commit + 진행률 (2R-C-3 fix — long-running 중간 손실 방지)
            if i % self.BATCH_SIZE == 0:
                await self._session.commit()
                logger.info(
                    "ka20068 bulk progress %d/%d (fetched=%d upserted=%d skipped=%d failed=%d)",
                    i,
                    len(stocks),
                    total_fetched,
                    total_upserted,
                    total_skipped,
                    total_failed,
                )

        # 마지막 batch 미완 row 도 commit
        await self._session.commit()

        # Phase F-2 결정 #4 — pre-filter + bulk loop sentinel catch 합산.
        total_alphanumeric_skipped = pre_filter_skipped + sentinel_skipped

        # plan § 12.2 #10 — partial 임계치 (5% warning / 15% error).
        # Phase F-2 결정 #6: 분모 = total_stocks (sentinel 제외). 메시지에
        # (alphanumeric_skipped=N) 명시 — false positive 회복 가시성.
        warnings, errors_above_threshold = self._evaluate_partial_thresholds(
            total_stocks=len(stocks) + pre_filter_skipped,
            total_failed=total_failed,
            total_alphanumeric_skipped=total_alphanumeric_skipped,
        )

        return LendingStockBulkResult(
            start_date=start_date,
            end_date=end_date,
            total_stocks=len(stocks) + pre_filter_skipped,
            outcomes=tuple(outcomes),
            total_fetched=total_fetched,
            total_upserted=total_upserted,
            total_skipped=total_skipped,
            total_failed=total_failed,
            warnings=warnings,
            errors_above_threshold=errors_above_threshold,
            total_alphanumeric_skipped=total_alphanumeric_skipped,
            alphanumeric_skipped_outcomes=tuple(alphanumeric_skipped_outcomes_list),
        )

    @staticmethod
    def _evaluate_partial_thresholds(
        *,
        total_stocks: int,
        total_failed: int,
        total_alphanumeric_skipped: int = 0,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """plan § 12.2 #10 — lending_stock 5% / 15% 임계치 평가.

        Phase F-2 결정 #6: 분모 = total_stocks (sentinel 제외 안 함). 메시지에
        (alphanumeric_skipped=N) 추가 — false positive 회복 가시성.
        """
        if total_stocks == 0:
            return ((), ())
        failure_ratio = total_failed / total_stocks
        warnings: list[str] = []
        errors: list[str] = []
        skip_suffix = f" (alphanumeric_skipped={total_alphanumeric_skipped})"
        if failure_ratio >= LENDING_STOCK_ERROR_THRESHOLD:
            errors.append(
                f"failure_ratio={failure_ratio:.2%} >= "
                f"{LENDING_STOCK_ERROR_THRESHOLD:.0%} (failed={total_failed}/{total_stocks})"
                f"{skip_suffix}"
            )
        elif failure_ratio >= LENDING_STOCK_WARNING_THRESHOLD:
            warnings.append(
                f"failure_ratio={failure_ratio:.2%} >= "
                f"{LENDING_STOCK_WARNING_THRESHOLD:.0%} (failed={total_failed}/{total_stocks})"
                f"{skip_suffix}"
            )
        return (tuple(warnings), tuple(errors))


__all__ = [
    "LENDING_STOCK_ERROR_THRESHOLD",
    "LENDING_STOCK_WARNING_THRESHOLD",
    "IngestLendingMarketUseCase",
    "IngestLendingStockBulkUseCase",
    "IngestLendingStockUseCase",
    "IngestLendingStockInput",
]
