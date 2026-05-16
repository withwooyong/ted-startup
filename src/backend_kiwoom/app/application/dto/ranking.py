"""RankingIngestOutcome / RankingBulkResult / NormalizedRanking DTO — Phase F-4.

설계: endpoint-18-ka10027.md § 6.3 + phase-f-4-rankings.md § 5.5.

D-2 single table + JSONB payload 패턴 — 5 endpoint (ka10027/30/31/32/23) 공유.

Phase F-3 D-3 / D-7 패턴 적용:
- ``errors_above_threshold`` tuple[str, ...] (F-3 통일, lending/short 패턴 일관).
  빈 tuple → falsy (기존 truthy/falsy 의존 코드 호환).
- ``SentinelStockCodeError`` 단건 catch → outcome.error = SkipReason.SENTINEL_SKIP.value
  (defense-in-depth — F-3 D-7).

D-11 — 임계치 도입 안 함 (운영 1주 모니터 후). ``errors_above_threshold`` default 빈 tuple.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.adapter.out.kiwoom._records import RankingType


@dataclass(frozen=True, slots=True)
class NormalizedRanking:
    """ranking_snapshot 1 row 의 정규화 도메인 — Repository 가 보는 형태.

    `stock_id=None` 은 lookup miss (D-8) — `stock_code_raw` 만 보존.
    NXT `_NX` suffix 는 `stock_code_raw` 에 보존, `stock_id` 는 strip 후 매핑 (caller 책임).
    """

    snapshot_date: Any  # datetime.date — Repository 는 datetime.date 로 다룸
    snapshot_time: Any  # datetime.time
    ranking_type: RankingType
    sort_tp: str
    market_type: str
    exchange_type: str
    rank: int
    stock_id: int | None
    stock_code_raw: str
    primary_metric: Decimal | None
    payload: dict[str, Any]
    request_filters: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RankingIngestOutcome:
    """단건 ranking ingest 결과 (1 호출 = 1 (mrkt_tp, sort_tp) 쌍).

    F-3 D-7 패턴:
    - ``error == SkipReason.SENTINEL_SKIP.value`` 면 sentinel skip (alphanumeric stk_cd 등).
    - ``error`` 가 None 이면 정상.
    - StrEnum 이라 string 비교 OK (`outcome.error == SkipReason.SENTINEL_SKIP`).
    """

    ranking_type: RankingType
    snapshot_at: datetime
    sort_tp: str
    market_type: str
    exchange_type: str
    fetched: int = 0
    upserted: int = 0
    error: str | None = None


@dataclass(frozen=True, slots=True)
class RankingBulkResult:
    """5 ranking endpoint Bulk UseCase 결과 — 2 market × 2 sort = 4 호출 매트릭스 등.

    Phase F-3 D-3 패턴 (lending/short 통일):
    - ``errors_above_threshold: tuple[str, ...]`` — 빈 tuple = falsy.
    - D-11: 임계치 도입 안 함 — default 빈 tuple (운영 1주 모니터 후 도입 검토).

    ``total_calls`` / ``total_upserted`` / ``total_failed`` 는 dataclass field 로 제공
    (router test 가 직접 전달 가능). 미명시 시 ``outcomes`` 기반으로 자동 계산.
    """

    ranking_type: RankingType
    outcomes: tuple[RankingIngestOutcome, ...] = field(default_factory=tuple)
    errors_above_threshold: tuple[str, ...] = field(default_factory=tuple)
    # F-3 패턴 — skipped_outcomes 도 보존 (short / lending 일관)
    skipped_outcomes: tuple[RankingIngestOutcome, ...] = field(default_factory=tuple)
    # Aggregates — None 이면 outcomes 기반 자동 계산 (post_init).
    # F-4 Step 2 fix H-5: sentinel ``-1`` → ``None`` (type 안전성 + caller 명시성).
    total_calls: int | None = None
    total_upserted: int | None = None
    total_failed: int | None = None

    def __post_init__(self) -> None:
        # frozen dataclass — object.__setattr__ 우회로 None → 계산값.
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
        """skip 카운터 표준 인터페이스 (F-3 D-8 통일)."""
        return len(self.skipped_outcomes)


__all__ = [
    "NormalizedRanking",
    "RankingBulkResult",
    "RankingIngestOutcome",
]
