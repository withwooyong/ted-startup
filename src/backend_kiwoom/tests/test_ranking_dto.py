"""RankingIngestOutcome / RankingBulkResult DTO — Phase F-4.

설계: endpoint-18-ka10027.md § 6.3 + phase-f-4-rankings.md § 5.5.

본 테스트는 import 실패가 red 의도 (Step 0 TDD red):
- `app.application.dto.ranking.{RankingIngestOutcome, RankingBulkResult}` 미존재
→ Step 1 신규 구현 후 green.

검증 (8 시나리오):
- Outcome dataclass(frozen=True, slots=True) 검증
- BulkResult tuple errors_above_threshold (F-3 D-3 패턴 통일)
- BulkResult total_upserted / total_failed / total_calls property
- D-11 임계치 도입 안 함 — errors_above_threshold default 빈 tuple
- F-3 D-7 패턴 — outcome.error = SkipReason.SENTINEL_SKIP.value 호환
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.adapter.out.kiwoom._records import RankingType  # type: ignore[import]
from app.application.dto._shared import SkipReason
from app.application.dto.ranking import (  # type: ignore[import]  # Step 1
    RankingBulkResult,
    RankingIngestOutcome,
)

KST = ZoneInfo("Asia/Seoul")


def _make_outcome(
    *,
    ranking_type: RankingType = RankingType.FLU_RT,
    sort_tp: str = "1",
    market_type: str = "001",
    exchange_type: str = "3",
    upserted: int = 50,
    error: str | None = None,
) -> RankingIngestOutcome:
    return RankingIngestOutcome(
        ranking_type=ranking_type,
        snapshot_at=datetime(2026, 5, 14, 19, 30, 0, tzinfo=KST),
        sort_tp=sort_tp,
        market_type=market_type,
        exchange_type=exchange_type,
        fetched=upserted if error is None else 0,
        upserted=upserted,
        error=error,
    )


# ---------------------------------------------------------------------------
# Outcome
# ---------------------------------------------------------------------------


def test_outcome_is_frozen_dataclass() -> None:
    """RankingIngestOutcome — frozen + slots (변경 차단)."""
    outcome = _make_outcome()
    with pytest.raises(Exception):  # noqa: B017
        outcome.upserted = 100  # type: ignore[misc]


def test_outcome_default_no_error() -> None:
    """기본은 error=None — 정상 호출 outcome."""
    outcome = _make_outcome()
    assert outcome.error is None
    assert outcome.upserted == 50


def test_outcome_sentinel_skip_compatible_with_skip_reason() -> None:
    """F-3 D-7 — outcome.error = SkipReason.SENTINEL_SKIP.value 호환.

    StrEnum 이라 string 비교 OK (`outcome.error == SkipReason.SENTINEL_SKIP`).
    """
    outcome = _make_outcome(upserted=0, error=SkipReason.SENTINEL_SKIP.value)
    assert outcome.error == "sentinel_skip"
    assert outcome.error == SkipReason.SENTINEL_SKIP  # StrEnum 호환


# ---------------------------------------------------------------------------
# BulkResult
# ---------------------------------------------------------------------------


def test_bulk_result_is_frozen_dataclass() -> None:
    """RankingBulkResult — frozen + slots."""
    result = RankingBulkResult(ranking_type=RankingType.FLU_RT)
    with pytest.raises(Exception):  # noqa: B017
        result.outcomes = ()  # type: ignore[misc]


def test_bulk_result_errors_above_threshold_is_tuple_default_empty() -> None:
    """F-3 D-3 패턴 통일 — errors_above_threshold: tuple[str, ...] default 빈 tuple.

    D-11: 임계치 도입 안 함 (운영 1주 모니터 후) — default 빈 tuple.
    빈 tuple → falsy (기존 truthy 체크 호환).
    """
    result = RankingBulkResult(ranking_type=RankingType.FLU_RT)
    assert result.errors_above_threshold == ()
    assert not result.errors_above_threshold  # falsy
    assert isinstance(result.errors_above_threshold, tuple)


def test_bulk_result_aggregate_properties() -> None:
    """total_calls / total_upserted / total_failed property."""
    outcomes = (
        _make_outcome(sort_tp="1", market_type="001", upserted=50),
        _make_outcome(sort_tp="3", market_type="001", upserted=40),
        _make_outcome(sort_tp="1", market_type="101", upserted=30),
        _make_outcome(sort_tp="3", market_type="101", upserted=0, error="business: 1"),
    )
    result = RankingBulkResult(
        ranking_type=RankingType.FLU_RT,
        outcomes=outcomes,
    )

    assert result.total_calls == 4
    assert result.total_upserted == 120  # 50 + 40 + 30 + 0
    assert result.total_failed == 1


def test_bulk_result_outcomes_must_be_tuple() -> None:
    """outcomes: tuple[RankingIngestOutcome, ...] (mutable list 노출 금지, F-3 정착)."""
    outcome = _make_outcome()
    result = RankingBulkResult(
        ranking_type=RankingType.FLU_RT,
        outcomes=(outcome,),
    )
    assert isinstance(result.outcomes, tuple)
    assert len(result.outcomes) == 1


def test_bulk_result_empty_outcomes_zero_aggregates() -> None:
    """빈 outcomes → 모든 집계 0."""
    result = RankingBulkResult(ranking_type=RankingType.FLU_RT)
    assert result.total_calls == 0
    assert result.total_upserted == 0
    assert result.total_failed == 0
