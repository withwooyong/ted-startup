"""IngestShortSellingUseCase + IngestShortSellingBulkUseCase — ka10014 (Phase E).

설계: endpoint-15-ka10014.md § 6.3~6.4 + § 12.

D-1 sector_ohlcv_service.py 의 session_provider factory 패턴 + C-2β daily_flow_service.py
의 KRX/NXT 분리 적재 패턴 1:1 응용.

특징 (plan § 12):
- 결정 #4 NXT 시도 — `should_call_nxt(stock)` 게이팅 (nxt_enable 체크)
- 결정 #9 NXT 빈 응답 정상 처리 (warning 안 함) — fetch_trend 결과 list=[] 도 정상 적재 (0 row)
- 결정 #10 partial 5%/15% — bulk 가 실패율 측정 + warnings / errors_above_threshold

가드 (UseCase Single):
- stock master 미존재 → skipped + reason="stock_master_missing"
- inactive stock → skipped + reason="inactive"
- env="mock" + NXT → skipped + reason="mock_no_nxt"
- nxt_enable=False + NXT 요청 → skipped + reason="nxt_disabled"
- KiwoomBusinessError → outcome.error 격리 (bulk 가 partial 임계치 계산)

세션 정책 (D-1 IngestSectorDailyUseCase 일관):
- session_provider() 새 세션 발급 — `async with provider() as session, session.begin():`
- per-stock try/except — partial-failure 격리 (bulk)
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import date
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._exceptions import KiwoomBusinessError, KiwoomError
from app.adapter.out.kiwoom._records import ShortSellingTimeType
from app.adapter.out.kiwoom.shsa import KiwoomShortSellingClient
from app.adapter.out.persistence.models.stock import Stock
from app.adapter.out.persistence.repositories.short_selling import (
    ShortSellingKwRepository,
)
from app.application.constants import ExchangeType
from app.application.dto.short_selling import (
    ShortSellingBulkResult,
    ShortSellingIngestOutcome,
)

logger = logging.getLogger(__name__)


SessionProvider = Callable[[], AbstractAsyncContextManager[AsyncSession]]
"""세션 팩토리 — `async with provider() as session:` 패턴 (D-1 일관)."""


# partial 임계치 (plan § 8.1 + § 12.2 결정 #10)
PARTIAL_WARN_THRESHOLD: float = 0.05   # 5% 초과 → warning
PARTIAL_ERROR_THRESHOLD: float = 0.15  # 15% 초과 → errors_above_threshold


class IngestShortSellingUseCase:
    """단일 종목·단일 거래소 공매도 적재 (Phase E, ka10014).

    의존성 주입:
    - `session_provider`: `() -> AsyncContextManager[AsyncSession]`
    - `shsa_client`: `KiwoomShortSellingClient`
    - `env`: "prod" / "mock" — mock + NXT 요청 시 skip (결정 #4 + 모의투자 KRX only)

    입력: stock_code (6자리) + start_date + end_date + exchange + tm_tp.
    """

    def __init__(
        self,
        *,
        session_provider: SessionProvider,
        shsa_client: KiwoomShortSellingClient,
        env: Literal["prod", "mock"] = "prod",
    ) -> None:
        self._session_provider = session_provider
        self._client = shsa_client
        self._env = env

    async def execute(
        self,
        stock_code: str,
        *,
        start_date: date,
        end_date: date,
        tm_tp: ShortSellingTimeType = ShortSellingTimeType.PERIOD,
        exchange: ExchangeType = ExchangeType.KRX,
    ) -> ShortSellingIngestOutcome:
        """단일 종목·거래소 공매도 적재.

        Returns:
            ShortSellingIngestOutcome — upserted >=0 (정상) / skipped+reason / error.
        """
        # 가드 1: mock env + NXT skip (모의투자 KRX only)
        if self._env == "mock" and exchange is ExchangeType.NXT:
            return ShortSellingIngestOutcome(
                stock_code=stock_code,
                exchange=exchange,
                skipped=True,
                reason="mock_no_nxt",
            )

        # 가드 2: stock master 조회
        async with self._session_provider() as session:
            stmt = select(Stock).where(Stock.stock_code == stock_code)
            stock = (await session.execute(stmt)).scalar_one_or_none()

        if stock is None:
            return ShortSellingIngestOutcome(
                stock_code=stock_code,
                exchange=exchange,
                skipped=True,
                reason="stock_master_missing",
            )

        # 가드 3: inactive stock skip
        if not stock.is_active:
            return ShortSellingIngestOutcome(
                stock_code=stock_code,
                exchange=exchange,
                skipped=True,
                reason="inactive",
            )

        # 가드 4: NXT + nxt_enable=False skip
        if exchange is ExchangeType.NXT and not stock.nxt_enable:
            return ShortSellingIngestOutcome(
                stock_code=stock_code,
                exchange=exchange,
                skipped=True,
                reason="nxt_disabled",
            )

        # 키움 호출
        try:
            raw_rows = await self._client.fetch_trend(
                stock_code,
                start_date=start_date,
                end_date=end_date,
                tm_tp=tm_tp,
                exchange=exchange,
            )
        except KiwoomBusinessError as exc:
            # 비식별 메타만 (message echo 차단) — exc.return_code 만 노출
            return ShortSellingIngestOutcome(
                stock_code=stock_code,
                exchange=exchange,
                error=f"business:{exc.return_code}",
            )

        # NXT 빈 응답 → 정상 처리 (warning 안 함, 결정 #9).
        # KRX 빈 응답도 정상 (공매도 없는 종목). 본 분기 자체 없음 — 그냥 upsert.
        normalized = [
            r.to_normalized(stock_id=stock.id, exchange=exchange)
            for r in raw_rows
        ]
        async with self._session_provider() as session, session.begin():
            repo = ShortSellingKwRepository(session)
            upserted = await repo.upsert_many(normalized)

        return ShortSellingIngestOutcome(
            stock_code=stock_code,
            exchange=exchange,
            fetched=len(raw_rows),
            upserted=upserted,
        )


class IngestShortSellingBulkUseCase:
    """active 종목 공매도 일괄 적재 (Phase E, ka10014).

    KRX + NXT 분리 호출 (daily_flow_service.py 패턴 일관):
    - 모든 active 종목 KRX 호출
    - stock.nxt_enable=True 종목만 NXT 호출

    50건마다 commit (BATCH_SIZE) — long-running sync (~30~60분 추정) 의 진행 가시성.

    partial 임계치 (plan § 8.1 + § 12.2 결정 #10):
    - 실패율 > 5% → warnings 누적 + logger.warning
    - 실패율 > 15% → errors_above_threshold=True + logger.error

    NXT 빈 응답은 결정 #9 에 따라 warning 안 함 (실패로 분류하지 않음 — outcome.error
    가 None 이면 정상).
    """

    BATCH_SIZE: int = 50

    def __init__(
        self,
        *,
        session_provider: SessionProvider,
        single_use_case: IngestShortSellingUseCase,
    ) -> None:
        self._session_provider = session_provider
        self._single = single_use_case

    async def execute(
        self,
        *,
        start_date: date,
        end_date: date,
        only_market_codes: Sequence[str] | None = None,
        only_stock_codes: Sequence[str] | None = None,
    ) -> ShortSellingBulkResult:
        """active 종목 전체 sync. KRX + NXT (nxt_enable 게이팅).

        Returns:
            ShortSellingBulkResult — total_stocks + krx/nxt outcomes + warnings.

        per-stock try/except — partial-failure 격리. KiwoomError / 일반 예외 모두 다음
        종목으로 진행.
        """
        # active 종목 조회
        async with self._session_provider() as session:
            stmt = select(Stock).where(Stock.is_active.is_(True))
            if only_market_codes:
                stmt = stmt.where(Stock.market_code.in_(list(only_market_codes)))
            if only_stock_codes:
                stmt = stmt.where(Stock.stock_code.in_(list(only_stock_codes)))
            stmt = stmt.order_by(Stock.market_code, Stock.stock_code)
            stocks = list((await session.execute(stmt)).scalars())

        if not stocks:
            logger.info("ka10014 bulk sync — active 종목 0개")
            return ShortSellingBulkResult(total_stocks=0)

        krx_outcomes: list[ShortSellingIngestOutcome] = []
        nxt_outcomes: list[ShortSellingIngestOutcome] = []

        # BATCH_SIZE 마다 commit yield-point — 실 데이터 적재는 Single UC 가 자체
        # `session.begin()` 컨텍스트로 처리. 본 commit 은 외부 fixture/조회 session
        # 의 트랜잭션 가시성 보장 + 50건 단위 진행률 가시화. 운영 데이터 정합성은
        # Single UC 의 atomicity 가 보장 (이 commit 이 fail 해도 적재 손실 없음).
        commit_session_factory = self._session_provider

        async def _batch_visibility_commit() -> None:
            async with commit_session_factory() as session:
                await session.commit()

        for i, stock in enumerate(stocks, start=1):
            # KRX (모든 active 종목)
            try:
                krx_outcome = await self._single.execute(
                    stock.stock_code,
                    start_date=start_date,
                    end_date=end_date,
                    exchange=ExchangeType.KRX,
                )
                krx_outcomes.append(krx_outcome)
            except KiwoomError as exc:
                err_class = type(exc).__name__
                krx_outcomes.append(
                    ShortSellingIngestOutcome(
                        stock_code=stock.stock_code,
                        exchange=ExchangeType.KRX,
                        error=err_class,
                    )
                )
                logger.warning(
                    "ka10014 KRX bulk 실패 stock_code=%s: %s",
                    stock.stock_code,
                    err_class,
                )
            except Exception as exc:  # noqa: BLE001 — partial-failure 격리
                err_class = type(exc).__name__
                krx_outcomes.append(
                    ShortSellingIngestOutcome(
                        stock_code=stock.stock_code,
                        exchange=ExchangeType.KRX,
                        error=err_class,
                    )
                )
                logger.exception(
                    "ka10014 KRX bulk 예상치 못한 예외 stock_code=%s",
                    stock.stock_code,
                )

            # NXT (nxt_enable=True 만)
            if stock.nxt_enable:
                try:
                    nxt_outcome = await self._single.execute(
                        stock.stock_code,
                        start_date=start_date,
                        end_date=end_date,
                        exchange=ExchangeType.NXT,
                    )
                    nxt_outcomes.append(nxt_outcome)
                except KiwoomError as exc:
                    err_class = type(exc).__name__
                    nxt_outcomes.append(
                        ShortSellingIngestOutcome(
                            stock_code=stock.stock_code,
                            exchange=ExchangeType.NXT,
                            error=err_class,
                        )
                    )
                    logger.warning(
                        "ka10014 NXT bulk 실패 stock_code=%s: %s",
                        stock.stock_code,
                        err_class,
                    )
                except Exception as exc:  # noqa: BLE001
                    err_class = type(exc).__name__
                    nxt_outcomes.append(
                        ShortSellingIngestOutcome(
                            stock_code=stock.stock_code,
                            exchange=ExchangeType.NXT,
                            error=err_class,
                        )
                    )
                    logger.exception(
                        "ka10014 NXT bulk 예상치 못한 예외 stock_code=%s",
                        stock.stock_code,
                    )

            # 50건마다 가시성 commit + 진행률 (Single UC 의 begin/commit 이 진실 source)
            if i % self.BATCH_SIZE == 0:
                await _batch_visibility_commit()
                logger.info("ka10014 bulk progress %d/%d", i, len(stocks))

        # partial 임계치 계산 (결정 #10, 2R-C-2 fix).
        # 분모 = KRX 호출만 (active 종목 전체 = 안정 기준).
        # NXT 빈 응답 (정상, 결정 #9) 이 분모에 들어가면 KRX 실패율을 희석하여
        # silent failure 회피 가능 (200 KRX 중 10 fail = 5% → NXT 200 정상 더하면 2.5%).
        # NXT outcome 의 error 도 KRX 분모에 가산하지 않음 — NXT 만의 실패율은 별도 chunk 측정.
        total_calls = len(krx_outcomes)
        total_failed = sum(1 for o in krx_outcomes if o.error is not None)

        warnings: list[str] = []
        errors_above_threshold = False
        if total_calls > 0:
            ratio = total_failed / total_calls
            # plan § 8.1: <5% 정상 / 5~15% warning / >15% error.
            # 경계 5% 는 warning 포함 (>= 5.0%), 15% 초과만 error.
            # "app" logger 로 직접 호출 — pytest caplog 의 logger="app" 캡처 호환성.
            _app_logger = logging.getLogger("app")
            if ratio > PARTIAL_ERROR_THRESHOLD:
                errors_above_threshold = True
                msg = (
                    f"ka10014 bulk 실패율 {ratio:.2%} > {PARTIAL_ERROR_THRESHOLD:.0%} "
                    f"(failed={total_failed}/{total_calls})"
                )
                warnings.append(msg)
                _app_logger.error(msg)
            elif ratio >= PARTIAL_WARN_THRESHOLD:
                msg = (
                    f"ka10014 bulk 실패율 {ratio:.2%} >= {PARTIAL_WARN_THRESHOLD:.0%} "
                    f"(failed={total_failed}/{total_calls})"
                )
                warnings.append(msg)
                _app_logger.warning(msg)

        return ShortSellingBulkResult(
            total_stocks=len(stocks),
            krx_outcomes=tuple(krx_outcomes),
            nxt_outcomes=tuple(nxt_outcomes),
            warnings=tuple(warnings),
            errors_above_threshold=errors_above_threshold,
        )


__all__ = [
    "IngestShortSellingBulkUseCase",
    "IngestShortSellingUseCase",
    "PARTIAL_ERROR_THRESHOLD",
    "PARTIAL_WARN_THRESHOLD",
    "SessionProvider",
    "ShortSellingBulkResult",
    "ShortSellingIngestOutcome",
]
