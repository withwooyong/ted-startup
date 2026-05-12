"""Lending DTO — ka10068 (MARKET) + ka20068 (STOCK) UseCase 입출력 (Phase E).

설계: endpoint-16-ka10068.md § 6.3 + endpoint-17-ka20068.md § 6.3 + endpoint-15-ka10014.md § 12.

타입 분포 (10건):
- Market Input/Outcome — 2
- Stock Input/Outcome/BulkResult + bulk warning/error 메타 — 4 (+ Bulk 내부 컬렉션)

테스트 (`test_lending_service.py`) 의 outcome.upserted / outcome.error / outcome.skipped /
result.total_stocks / fetch_stock_trend.await_count 검증을 위한 시그니처.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True, slots=True)
class IngestLendingMarketInput:
    """ka10068 시장 단위 UseCase 입력 — 단일 호출 (mrkt_tp 분리 없음, plan § 12.2 #4)."""

    start_date: date | None = None
    end_date: date | None = None


@dataclass(frozen=True, slots=True)
class IngestLendingStockInput:
    """ka20068 종목 단위 UseCase 입력 — KRX only (plan § 12.2 #4)."""

    stock_code: str
    start_date: date | None = None
    end_date: date | None = None


@dataclass(frozen=True, slots=True)
class LendingMarketIngestOutcome:
    """ka10068 단일 호출 결과.

    error not None → 비즈니스/네트워크 실패. fetched/upserted=0.
    error None + upserted=0 → 응답 빈 list (정상).
    """

    start_date: date | None = None
    end_date: date | None = None
    fetched: int = 0
    upserted: int = 0
    error: str | None = None


@dataclass(frozen=True, slots=True)
class LendingStockIngestOutcome:
    """ka20068 단일 종목 결과.

    skipped=True (정상 운영):
    - reason="inactive" — stock.is_active=False
    - reason="stock_not_found" — 종목 마스터 미존재 (KRX only 가드)

    error not None → 비즈니스/네트워크 실패.
    """

    stock_code: str
    start_date: date | None = None
    end_date: date | None = None
    fetched: int = 0
    upserted: int = 0
    skipped: bool = False
    reason: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class LendingStockBulkResult:
    """ka20068 bulk 실행 결과 — active 종목 iterate.

    plan § 12.2 #10 — partial 임계치 (5% warning / 15% error) 적용.

    - `outcomes` — 종목별 결과 tuple (mutable list 노출 금지, R1 invariant).
    - `total_fetched / upserted / skipped / failed` — 집계 메트릭.
    - `warnings / errors_above_threshold` — partial 임계치 메시지.
    """

    start_date: date
    end_date: date
    total_stocks: int
    outcomes: tuple[LendingStockIngestOutcome, ...] = field(default_factory=tuple)
    total_fetched: int = 0
    total_upserted: int = 0
    total_skipped: int = 0
    total_failed: int = 0
    warnings: tuple[str, ...] = field(default_factory=tuple)
    errors_above_threshold: tuple[str, ...] = field(default_factory=tuple)


__all__ = [
    "IngestLendingMarketInput",
    "IngestLendingStockInput",
    "LendingMarketIngestOutcome",
    "LendingStockBulkResult",
    "LendingStockIngestOutcome",
]
