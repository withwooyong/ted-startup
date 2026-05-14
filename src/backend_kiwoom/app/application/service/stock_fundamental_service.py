"""SyncStockFundamentalUseCase — ka10001 일별 펀더멘털 적재 (B-γ-2).

설계: endpoint-05-ka10001.md § 6.3 + ADR § 14.

Partial-failure 정책 (ADR § 14.6 / 2R C-M3 — (a) per-stock skip + counter):
- 한 종목 KiwoomError 발생 → try/except 후 success/failed counter 누적
- 다른 종목으로 진행 (B-α SyncStockMasterUseCase 패턴 일관)
- 결과 dataclass 의 `errors` list 에 클래스명 only (응답 본문 echo 차단, B-α M-2)

ensure_exists 미사용 (ADR § 14.6 결정):
- active stock 만 대상 — `SELECT FROM kiwoom.stock WHERE is_active=TRUE`
- 신규 상장 종목은 다음날 ka10099 sync 에서 자동 등장
- 단순성 + RPS 보존

stock_id resolution invariant (ADR § 14.6):
- caller (본 UseCase) 는 strip_kiwoom_suffix(response.stk_cd) → Stock.find_by_code →
  stock_id → upsert_one(row, stock_id=, expected_stock_code=stock.stock_code) 패턴 강제
- StockFundamentalRepository.upsert_one 의 expected_stock_code cross-check 가 fail-closed

mismatch alert (계획서 § 6.3):
- 응답 stk_nm ≠ Stock.stock_name → logger.warning, 적재는 진행

mock 환경 안전판:
- 본 chunk KRX-only 라 mock_env 는 어댑터 단계에서만 영향 (ka10100 nxtEnable). ka10001
  응답에는 nxtEnable 없으므로 mock_env 무관.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._exceptions import KiwoomError
from app.adapter.out.kiwoom.stkinfo import (
    KiwoomStkInfoClient,
    SentinelStockCodeError,
    normalize_basic_info,
)
from app.adapter.out.persistence.models import Stock, StockFundamental
from app.adapter.out.persistence.repositories.stock_fundamental import (
    StockFundamentalRepository,
)
from app.application.exceptions import StockMasterNotFoundError

logger = logging.getLogger(__name__)


# B-γ-2 2R M-1 — log injection 방어용 control character strip.
# vendor 응답 stk_nm 이 attacker-influenced (newline / ANSI escape / NULL) 일 때 sink
# (Sentry/CloudWatch) 의 line 분리 / 색상 spoof 차단. 차단 charset 확장 후보 (B-γ-2 2R 후속
# LOW): DEL `\x7f`, CSI 8-bit `\x9b`, Unicode line/paragraph sep `  `, RTL/LTR
# override `‮‭` — 다음 chunk 에서 화이트리스트 패턴으로 전환 검토.
_LOG_UNSAFE_CHARS = str.maketrans("", "", "\r\n\t\x00\x1b")


def _safe_for_log(value: str | None, *, max_length: int = 40) -> str:
    """logger 출력 직전 control character strip + 길이 cap.

    응답 본문이 logger 경유 외부 sink 로 흘러갈 때 line/format injection 차단.
    """
    if not value:
        return ""
    return value.translate(_LOG_UNSAFE_CHARS)[:max_length]


@dataclass(frozen=True, slots=True)
class FundamentalSyncOutcome:
    """단일 종목 sync 실패 outcome — 응답 본문 echo 차단을 위해 클래스명만 보존."""

    stock_code: str
    error_class: str


@dataclass(frozen=True, slots=True)
class FundamentalSyncResult:
    """sync 실행 결과 (B-α StockMasterSyncResult 와 다른 단위 — 종목 단위 카운터).

    Phase F-1 (§ 4 결정 #5/#6):
    - ``skipped`` — sentinel 종목코드 (``0000D0`` / ``26490K`` 등) 의도된 skip outcome.
      ``SentinelStockCodeError`` 캐치 시 적재. ``failed`` 미증가 (실제 실패 아님).
    - ``failed`` 의미 = 실제 실패 (HTTP 4xx/5xx, DB 오류, 알 수 없는 예외) — sentinel 제외.
    - ``skipped_count`` 는 ``len(skipped)`` 의 derived property.
    """

    asof_date: date
    total: int
    success: int
    failed: int
    errors: tuple[FundamentalSyncOutcome, ...] = field(default_factory=tuple)
    skipped: tuple[FundamentalSyncOutcome, ...] = field(default_factory=tuple)

    @property
    def skipped_count(self) -> int:
        """sentinel skip 종목 수 — ``len(skipped)`` (운영 알람·임계치용)."""
        return len(self.skipped)


class SyncStockFundamentalUseCase:
    """ka10001 호출 → stock_fundamental 일별 적재.

    의존성 주입:
    - `session_provider`: `() -> AsyncContextManager[AsyncSession]` — 종목마다 새 세션
    - `stkinfo_client`: 공유 KiwoomStkInfoClient

    두 진입점:
    - `execute(*, target_date=None, only_market_codes=None)` — 전체 active stock sync
    - `refresh_one(stock_code)` — 단건 새로고침 (admin /refresh 라우터)
    """

    def __init__(
        self,
        *,
        session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
        stkinfo_client: KiwoomStkInfoClient,
    ) -> None:
        self._session_provider = session_provider
        self._client = stkinfo_client

    async def execute(
        self,
        *,
        target_date: date | None = None,
        only_market_codes: Sequence[str] | None = None,
    ) -> FundamentalSyncResult:
        """active stock 순회 → ka10001 호출 → 펀더멘털 적재.

        Parameters:
            target_date: 영속화 일자. None 이면 KST today (응답에 timestamp 부재, § 11.2).
            only_market_codes: 특정 시장만 sync. None 이면 전체 5 시장.

        Returns:
            FundamentalSyncResult — total/success/failed + errors list (per-stock).

        partial-failure 정책 (ADR § 14.6 (a)):
        - per-stock try/except → 한 종목 실패해도 다음 종목 진행
        - errors[*].error_class 에 KiwoomError 서브클래스명 (응답 본문 echo 차단)
        """
        asof = target_date or date.today()

        # 1. active stock 조회 — 별도 세션으로 (sync 작업의 read 단계)
        async with self._session_provider() as session:
            stmt = select(Stock).where(Stock.is_active.is_(True))
            if only_market_codes:
                stmt = stmt.where(Stock.market_code.in_(only_market_codes))
            stmt = stmt.order_by(Stock.market_code, Stock.stock_code)
            active_stocks = list((await session.execute(stmt)).scalars())

        success = 0
        failed = 0
        errors: list[FundamentalSyncOutcome] = []
        skipped: list[FundamentalSyncOutcome] = []

        # 2. per-stock try/except — partial-failure 격리
        for stock in active_stocks:
            try:
                await self._sync_one_stock(stock, asof_date=asof)
                success += 1
            except SentinelStockCodeError as exc:
                # Phase F-1 (§ 4 결정 #5/#6) — sentinel 의도된 skip → skipped 적재.
                # failed 미증가 (실제 실패 아님 — 운영 알람·임계치 의미 정확화).
                # SentinelStockCodeError 가 ValueError 상속이므로 일반 KiwoomError catch
                # 보다 먼저 분기 (좁은 catch → 넓은 catch 순서).
                skipped.append(
                    FundamentalSyncOutcome(
                        stock_code=stock.stock_code,
                        error_class=type(exc).__name__,
                    )
                )
                logger.info(
                    "ka10001 sentinel skip stock_code=%s mrkt_tp=%s",
                    stock.stock_code,
                    stock.market_code,
                )
            except KiwoomError as exc:
                failed += 1
                err_class = type(exc).__name__
                errors.append(FundamentalSyncOutcome(stock_code=stock.stock_code, error_class=err_class))
                # 응답 본문은 logger 경로로만 노출 (admin 응답 echo 차단, B-α M-2 패턴 일관)
                logger.warning(
                    "ka10001 sync 실패 stock_code=%s mrkt_tp=%s: %s",
                    stock.stock_code,
                    stock.market_code,
                    err_class,
                )
            except Exception as exc:  # noqa: BLE001 — DB 등 비-Kiwoom 예외도 종목 단위 격리
                failed += 1
                err_class = type(exc).__name__
                errors.append(FundamentalSyncOutcome(stock_code=stock.stock_code, error_class=err_class))
                logger.exception(
                    "ka10001 sync 예상치 못한 예외 stock_code=%s",
                    stock.stock_code,
                )

        return FundamentalSyncResult(
            asof_date=asof,
            total=len(active_stocks),
            success=success,
            failed=failed,
            errors=tuple(errors),
            skipped=tuple(skipped),
        )

    async def refresh_one(self, stock_code: str) -> StockFundamental:
        """단건 새로고침 — admin POST /stocks/{code}/fundamental/refresh.

        Stock 마스터에 stock_code 가 active 로 등록돼 있어야 함 (ensure_exists 미사용).
        없으면 StockMasterNotFoundError → 라우터가 404 매핑.

        KiwoomError 서브클래스는 그대로 raise — 라우터가 매핑 (B-β execute 패턴 일관).
        """
        # 1. Stock 마스터 조회 (별도 세션) — ensure_exists 미사용 (ADR § 14.6 결정)
        async with self._session_provider() as session:
            stmt = select(Stock).where(Stock.stock_code == stock_code, Stock.is_active.is_(True))
            stock = (await session.execute(stmt)).scalar_one_or_none()

        if stock is None:
            raise StockMasterNotFoundError(stock_code)

        return await self._sync_one_stock(stock, asof_date=date.today())

    async def _sync_one_stock(self, stock: Stock, *, asof_date: date) -> StockFundamental:
        """한 종목 sync — 키움 호출 + 정규화 + DB upsert.

        Returns:
            StockFundamental — 갱신된 row (caller 가 RETURNING 받음).

        Raises:
            KiwoomError 서브클래스 — caller 가 매핑 책임 (per-stock skip).
            기타 Exception — caller 가 unexpected 로 격리.
        """
        # 1. 키움 API 호출 — 트랜잭션 밖 (DB 락 점유 시간 최소화, B-α/B-β 일관)
        response = await self._client.fetch_basic_info(stock.stock_code)

        # 2. 정규화 — 응답 stk_cd 의 suffix 는 base code 로 strip (방어, ADR § 14.6 invariant)
        normalized = normalize_basic_info(response, asof_date=asof_date)

        # 3. mismatch alert (계획서 § 6.3) — 적재는 진행, 알림만.
        # response.stock_name 은 attacker-influenced (Kiwoom 응답 echo) — log injection
        # 방어 위해 control char strip + 길이 cap (B-γ-2 2R M-1).
        if normalized.stock_name and normalized.stock_name != stock.stock_name:
            logger.warning(
                "stock_name mismatch stock_code=%s master=%s response=%s",
                stock.stock_code,
                _safe_for_log(stock.stock_name),
                _safe_for_log(normalized.stock_name),
            )

        # 4. response stk_cd 의 base code 검증.
        # `normalized.stock_code` 는 normalize_basic_info 가 strip_kiwoom_suffix 적용한
        # 결과 — 직접 사용 (B-γ-2 1R M-1, 중복 strip 제거).
        # 본 mismatch 는 "alert 후 적재" 가 아니라 fail-closed — step5 의 expected_stock_code
        # cross-check 가 ValueError raise → execute 의 except 가 failed counter 누적,
        # refresh_one 은 라우터 404 매핑.
        if normalized.stock_code != stock.stock_code:
            # 운영 가시성 alert — 실제 차단은 step5 의 expected_stock_code cross-check
            logger.warning(
                "ka10001 응답 stk_cd 가 요청과 다름 (fail-closed) requested=%s response_base=%s",
                stock.stock_code,
                _safe_for_log(normalized.stock_code, max_length=20),
            )

        # 5. DB upsert — 단건 트랜잭션 (ADR § 14.6 invariant: expected_stock_code cross-check)
        async with self._session_provider() as session, session.begin():
            repo = StockFundamentalRepository(session)
            return await repo.upsert_one(
                normalized,
                stock_id=stock.id,
                expected_stock_code=stock.stock_code,
            )


__all__ = [
    "FundamentalSyncOutcome",
    "FundamentalSyncResult",
    "SentinelStockCodeError",
    "SyncStockFundamentalUseCase",
]
