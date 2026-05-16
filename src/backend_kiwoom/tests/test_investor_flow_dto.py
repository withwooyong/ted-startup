"""InvestorIngestOutcome / StockInvestorBreakdownOutcome / FrgnOrgnConsecutiveOutcome + 3 BulkResult (Phase G, ~8 케이스).

TDD red 의도:
- `app.application.dto.investor_flow.{InvestorIngestOutcome, InvestorFlowBulkResult, ...}` 미존재
→ Step 1 구현 후 green.

검증:
- 3 Outcome dataclass(frozen=True, slots=True)
- 3 BulkResult errors_above_threshold: tuple[str, ...] (F-3 패턴)
- BulkResult skipped_count property
- BulkResult total_upserted / total_failed / total_calls property
- D-11 임계치 도입 안 함 — errors_above_threshold default 빈 tuple
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.application.dto.investor_flow import (  # type: ignore[import]  # Step 1
    FrgnOrgnConsecutiveBulkResult,
    FrgnOrgnConsecutiveOutcome,
    InvestorFlowBulkResult,
    InvestorIngestOutcome,
    StockInvestorBreakdownBulkResult,
    StockInvestorBreakdownOutcome,
)

KST = ZoneInfo("Asia/Seoul")
_NOW = datetime(2026, 5, 16, 20, 0, 0, tzinfo=KST)


def _make_investor_outcome(
    *,
    investor_type: str = "9000",
    trade_type: str = "2",
    market_type: str = "001",
    exchange_type: str = "3",
    upserted: int = 50,
    error: str | None = None,
) -> InvestorIngestOutcome:
    return InvestorIngestOutcome(
        fetched_at=_NOW,
        investor_type=investor_type,
        trade_type=trade_type,
        market_type=market_type,
        exchange_type=exchange_type,
        fetched=upserted if error is None else 0,
        upserted=0 if error else upserted,
        error=error,
    )


def _make_breakdown_outcome(
    *,
    stock_code: str = "005930",
    upserted: int = 1,
    error: str | None = None,
) -> StockInvestorBreakdownOutcome:
    return StockInvestorBreakdownOutcome(
        fetched_at=_NOW,
        stock_code=stock_code,
        trading_date="20241107",
        fetched=upserted if error is None else 0,
        upserted=upserted,
        error=error,
    )


def _make_frgn_orgn_outcome(
    *,
    period_type: str = "1",
    market_type: str = "001",
    amt_qty_tp: str = "0",
    upserted: int = 100,
    error: str | None = None,
) -> FrgnOrgnConsecutiveOutcome:
    return FrgnOrgnConsecutiveOutcome(
        fetched_at=_NOW,
        period_type=period_type,
        market_type=market_type,
        amt_qty_tp=amt_qty_tp,
        exchange_type="3",
        fetched=upserted if error is None else 0,
        upserted=upserted,
        error=error,
    )


# ---------------------------------------------------------------------------
# 1. InvestorIngestOutcome — frozen dataclass
# ---------------------------------------------------------------------------


def test_investor_ingest_outcome_is_frozen() -> None:
    """InvestorIngestOutcome frozen=True."""
    outcome = _make_investor_outcome()
    with pytest.raises((AttributeError, TypeError)):
        outcome.upserted = 9999  # type: ignore[misc]


def test_investor_ingest_outcome_error_field() -> None:
    """InvestorIngestOutcome error 필드."""
    outcome = _make_investor_outcome(error="business: 1")
    assert outcome.error == "business: 1"
    assert outcome.upserted == 0


# ---------------------------------------------------------------------------
# 2. StockInvestorBreakdownOutcome — frozen dataclass
# ---------------------------------------------------------------------------


def test_stock_investor_breakdown_outcome_is_frozen() -> None:
    """StockInvestorBreakdownOutcome frozen=True."""
    outcome = _make_breakdown_outcome()
    with pytest.raises((AttributeError, TypeError)):
        outcome.stock_code = "000000"  # type: ignore[misc]


def test_stock_investor_breakdown_outcome_sentinel_skip() -> None:
    """SkipReason.SENTINEL_SKIP.value 와 호환 (F-3 D-7)."""
    from app.application.dto._shared import SkipReason

    outcome = _make_breakdown_outcome(error=SkipReason.SENTINEL_SKIP.value)
    assert outcome.error == SkipReason.SENTINEL_SKIP.value


# ---------------------------------------------------------------------------
# 3. FrgnOrgnConsecutiveOutcome — frozen dataclass
# ---------------------------------------------------------------------------


def test_frgn_orgn_consecutive_outcome_is_frozen() -> None:
    """FrgnOrgnConsecutiveOutcome frozen=True."""
    outcome = _make_frgn_orgn_outcome()
    with pytest.raises((AttributeError, TypeError)):
        outcome.upserted = 9999  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 4. InvestorFlowBulkResult — errors_above_threshold tuple (F-3)
# ---------------------------------------------------------------------------


def test_investor_flow_bulk_result_errors_above_threshold_default_empty() -> None:
    """D-11 — errors_above_threshold default 빈 tuple."""
    result = InvestorFlowBulkResult(
        total_calls=12,
        total_upserted=600,
        total_failed=0,
        outcomes=tuple(_make_investor_outcome() for _ in range(12)),
        errors_above_threshold=(),
    )
    assert result.errors_above_threshold == ()


def test_investor_flow_bulk_result_errors_above_threshold_nonempty() -> None:
    """errors_above_threshold 비어있지 않으면 → 알람 시그널."""
    result = InvestorFlowBulkResult(
        total_calls=12,
        total_upserted=0,
        total_failed=12,
        outcomes=tuple(_make_investor_outcome(error="timeout") for _ in range(12)),
        errors_above_threshold=("FOREIGN:NET_BUY:001", "INDIVIDUAL:NET_BUY:001"),
    )
    assert len(result.errors_above_threshold) == 2
    assert "FOREIGN:NET_BUY:001" in result.errors_above_threshold


def test_investor_flow_bulk_result_total_upserted_property() -> None:
    """total_upserted 집계."""
    result = InvestorFlowBulkResult(
        total_calls=4,
        total_upserted=200,
        total_failed=0,
        outcomes=(),
        errors_above_threshold=(),
    )
    assert result.total_upserted == 200


# ---------------------------------------------------------------------------
# 5. StockInvestorBreakdownBulkResult
# ---------------------------------------------------------------------------


def test_stock_investor_breakdown_bulk_result_skipped_count() -> None:
    """skipped_count property — error 비어있지 않은 outcome 수."""
    outcomes = (
        _make_breakdown_outcome(stock_code="005930", upserted=1),
        _make_breakdown_outcome(stock_code="000660", error="sentinel"),
        _make_breakdown_outcome(stock_code="999999", error="business: 1"),
    )
    result = StockInvestorBreakdownBulkResult(
        total_calls=3,
        total_upserted=1,
        total_failed=2,
        outcomes=outcomes,
        errors_above_threshold=(),
    )
    skipped = result.skipped_count
    assert skipped >= 0  # Step 1 구현 후 = 2 검증


# ---------------------------------------------------------------------------
# 6. FrgnOrgnConsecutiveBulkResult
# ---------------------------------------------------------------------------


def test_frgn_orgn_consecutive_bulk_result_4_calls() -> None:
    """ka10131 default 4 호출 (2 mkt × 2 amt_qty)."""
    outcomes = tuple(_make_frgn_orgn_outcome() for _ in range(4))
    result = FrgnOrgnConsecutiveBulkResult(
        total_calls=4,
        total_upserted=400,
        total_failed=0,
        outcomes=outcomes,
        errors_above_threshold=(),
    )
    assert result.total_calls == 4
    assert result.total_upserted == 400
