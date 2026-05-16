"""InvestorIngestOutcome / StockInvestorBreakdownOutcome / FrgnOrgnConsecutiveOutcome + 3 BulkResult — Phase G.

설계: phase-g-investor-flow.md § 5.5 + endpoint-23~25.

3 Outcome dataclass + 3 BulkResult — F-3 정착 패턴 (lending/short_selling/ranking 1:1):
- ``errors_above_threshold: tuple[str, ...]`` — 빈 tuple = falsy.
- D-11 — 임계치 도입 안 함 (운영 1주 모니터 후).
- ``skipped_count`` property — F-3 D-8 통일.
- ``total_calls`` / ``total_upserted`` / ``total_failed`` — outcomes 기반 자동 계산.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# ===========================================================================
# Outcome dataclasses (단건 호출 결과)
# ===========================================================================


@dataclass(frozen=True, slots=True)
class InvestorIngestOutcome:
    """ka10058 단건 ingest 결과 (1 호출 = (investor_type, trade_type, market_type) 1쌍).

    F-3 D-7 패턴: ``error == SkipReason.SENTINEL_SKIP.value`` 면 sentinel skip.
    """

    fetched_at: datetime
    investor_type: str
    trade_type: str
    market_type: str
    exchange_type: str
    fetched: int = 0
    upserted: int = 0
    error: str | None = None


@dataclass(frozen=True, slots=True)
class StockInvestorBreakdownOutcome:
    """ka10059 단건 ingest 결과 (1 호출 = (stock_code, dt) 1쌍).

    wide format — 단일 row + 12 net 컬럼이지만 outcome 단위는 호출당 1개.
    """

    fetched_at: datetime
    stock_code: str
    trading_date: str
    fetched: int = 0
    upserted: int = 0
    error: str | None = None


@dataclass(frozen=True, slots=True)
class FrgnOrgnConsecutiveOutcome:
    """ka10131 단건 ingest 결과 (1 호출 = (period, market, amt_qty) 1쌍)."""

    fetched_at: datetime
    period_type: str
    market_type: str
    amt_qty_tp: str
    exchange_type: str
    fetched: int = 0
    upserted: int = 0
    error: str | None = None


# ===========================================================================
# BulkResult dataclasses (Bulk 매트릭스 결과)
# ===========================================================================


@dataclass(frozen=True, slots=True)
class InvestorFlowBulkResult:
    """ka10058 Bulk 매트릭스 결과 — 2 mkt × 3 inv × 2 trde = 12 호출.

    F-3 D-3 패턴 — ``errors_above_threshold: tuple[str, ...]``. 빈 tuple = falsy.
    D-11 임계치 미도입 — default 빈 tuple.
    """

    outcomes: tuple[InvestorIngestOutcome, ...] = field(default_factory=tuple)
    errors_above_threshold: tuple[str, ...] = field(default_factory=tuple)
    skipped_outcomes: tuple[InvestorIngestOutcome, ...] = field(default_factory=tuple)
    total_calls: int | None = None
    total_upserted: int | None = None
    total_failed: int | None = None

    def __post_init__(self) -> None:
        if self.total_calls is None:
            object.__setattr__(self, "total_calls", len(self.outcomes))
        if self.total_upserted is None:
            object.__setattr__(
                self,
                "total_upserted",
                sum(o.upserted for o in self.outcomes),
            )
        if self.total_failed is None:
            object.__setattr__(
                self,
                "total_failed",
                sum(1 for o in self.outcomes if o.error is not None),
            )

    @property
    def skipped_count(self) -> int:
        """skip 카운터 표준 인터페이스 (F-3 D-8)."""
        return len(self.skipped_outcomes)


@dataclass(frozen=True, slots=True)
class StockInvestorBreakdownBulkResult:
    """ka10059 Bulk 매트릭스 결과 — 3000 종목 × 1조합 (D-8 default).

    F-3 D-3 패턴 — ``errors_above_threshold: tuple[str, ...]``.
    ``skipped_count`` property — outcomes 중 error 있는 항목 수 (F-3 D-8 통일).
    """

    outcomes: tuple[StockInvestorBreakdownOutcome, ...] = field(default_factory=tuple)
    errors_above_threshold: tuple[str, ...] = field(default_factory=tuple)
    skipped_outcomes: tuple[StockInvestorBreakdownOutcome, ...] = field(default_factory=tuple)
    total_calls: int | None = None
    total_upserted: int | None = None
    total_failed: int | None = None

    def __post_init__(self) -> None:
        if self.total_calls is None:
            object.__setattr__(self, "total_calls", len(self.outcomes))
        if self.total_upserted is None:
            object.__setattr__(
                self,
                "total_upserted",
                sum(o.upserted for o in self.outcomes),
            )
        if self.total_failed is None:
            object.__setattr__(
                self,
                "total_failed",
                sum(1 for o in self.outcomes if o.error is not None),
            )

    @property
    def skipped_count(self) -> int:
        """skip 카운터 — outcomes 중 error 있는 항목 (lookup miss / business error 등).

        ``skipped_outcomes`` 가 명시되면 그 길이를 우선, 아니면 outcomes.error 기반 집계.
        """
        if self.skipped_outcomes:
            return len(self.skipped_outcomes)
        return sum(1 for o in self.outcomes if o.error is not None)


@dataclass(frozen=True, slots=True)
class FrgnOrgnConsecutiveBulkResult:
    """ka10131 Bulk 매트릭스 결과 — 2 mkt × 2 amt_qty = 4 호출 (D-10)."""

    outcomes: tuple[FrgnOrgnConsecutiveOutcome, ...] = field(default_factory=tuple)
    errors_above_threshold: tuple[str, ...] = field(default_factory=tuple)
    skipped_outcomes: tuple[FrgnOrgnConsecutiveOutcome, ...] = field(default_factory=tuple)
    total_calls: int | None = None
    total_upserted: int | None = None
    total_failed: int | None = None

    def __post_init__(self) -> None:
        if self.total_calls is None:
            object.__setattr__(self, "total_calls", len(self.outcomes))
        if self.total_upserted is None:
            object.__setattr__(
                self,
                "total_upserted",
                sum(o.upserted for o in self.outcomes),
            )
        if self.total_failed is None:
            object.__setattr__(
                self,
                "total_failed",
                sum(1 for o in self.outcomes if o.error is not None),
            )

    @property
    def skipped_count(self) -> int:
        """skip 카운터 (F-3 D-8)."""
        return len(self.skipped_outcomes)


__all__ = [
    "FrgnOrgnConsecutiveBulkResult",
    "FrgnOrgnConsecutiveOutcome",
    "InvestorFlowBulkResult",
    "InvestorIngestOutcome",
    "StockInvestorBreakdownBulkResult",
    "StockInvestorBreakdownOutcome",
]
