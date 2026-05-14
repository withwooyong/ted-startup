"""IngestShortSellingInput / ShortSellingIngestOutcome / ShortSellingBulkResult DTO (Phase E, ka10014).

설계: endpoint-15-ka10014.md § 6.3~6.4 + § 12.

D-1 sector_ohlcv.py DTO 패턴 1:1 응용. 단, 본 endpoint 는 stock_code 입력 (sector PK 와 차이).

특징 (plan § 12.2):
- 결정 #9 NXT 빈 응답 정상 처리 (warning 안 함) — outcome 에서 upserted=0 으로만 표현
- 결정 #10 partial 임계치 5%/15% — bulk result 의 `warnings` / `errors_above_threshold`
- KRX + NXT 분리 outcomes — daily_flow_service.py 의 KRX/NXT 분리 패턴 일관

Phase F-3 D-3 / D-8:
- `errors_above_threshold` bool → tuple[str, ...] 로 변경 (lending 패턴 통일).
  빈 tuple → falsy (기존 truthy/falsy 의존 코드 호환).
- `skipped_count` @property 추가 — 외부 코드 `result.skipped_count` 접근 호환.
- `SkipReason` enum 도입 — `app.application.dto._shared.SkipReason` 참조.
  매직 스트링 ("alphanumeric_pre_filter" / "sentinel_skip") 그대로 유지.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.application.constants import ExchangeType
from app.application.dto._shared import SkipReason


@dataclass(frozen=True, slots=True)
class IngestShortSellingInput:
    """UseCase 입력 DTO (plan § 6.3).

    stock_code (6자리) + start_date + end_date + exchange + tm_tp.
    """

    stock_code: str
    start_date: date
    end_date: date
    exchange: ExchangeType = ExchangeType.KRX


@dataclass(frozen=True, slots=True)
class ShortSellingIngestOutcome:
    """단일 종목·거래소 공매도 적재 결과.

    skipped=True 케이스 (plan § 6.3):
    - inactive stock → reason="inactive"
    - mock env + NXT → reason="mock_no_nxt"
    - stock.nxt_enable=False + NXT 요청 → reason="nxt_disabled"
    - stock master 미존재 → reason="stock_master_missing"

    upserted=N (N>=0) 이 정상 응답 (N=0 은 빈 응답 — NXT 공매도 미지원 가능, 결정 #9).
    error 가 set 되면 비즈니스/네트워크 실패 (bulk 가 partial 임계치 계산에 사용).
    """

    stock_code: str
    exchange: ExchangeType
    upserted: int = 0
    fetched: int = 0
    skipped: bool = False
    reason: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ShortSellingBulkResult:
    """bulk sync 실행 결과 (plan § 6.4 + § 12.2 결정 #10 + Phase F-2 결정 #4).

    KRX + NXT 분리 outcomes (daily_flow_service.py 의 KRX/NXT 패턴 일관).

    partial 임계치 (결정 #10):
    - 실패율 5% 초과 → warnings 에 메시지 누적 (운영 알람 경고)
    - 실패율 15% 초과 → errors_above_threshold 에 메시지 누적 (운영 알람 에러)

    Phase F-2 추가 (결정 #4):
    - `total_skipped`: SentinelStockCodeError (alphanumeric 종목) skip 카운터 (합산).
      실제 실패 (`total_failed`) 와 의미 분리 — 임계치 false positive 회복.
      pre-filter (filter_alphanumeric=True) + bulk loop 의 sentinel catch 합산.
    - `skipped_outcomes`: F-1 `FundamentalSyncResult.skipped` 패턴 1:1 미러.
      종목별 명세 보존 (stock_code + error reason) — KOSCOM cross-check 시 사유 식별.
      `error` 값은 `SkipReason.ALPHANUMERIC_PRE_FILTER` 또는 `SkipReason.SENTINEL_SKIP`
      (StrEnum 이라 string 값 그대로 비교 호환).
      `len(skipped_outcomes) == total_skipped` invariant.

    Phase F-3 D-3:
    - `errors_above_threshold`: bool → tuple[str, ...]. 빈 tuple = falsy (기존 truthy
      체크 호환). lending 의 동명 필드와 타입 통일.

    R1 invariant — warnings / errors_above_threshold 모두 tuple (mutable list 노출 금지).
    """

    total_stocks: int
    krx_outcomes: tuple[ShortSellingIngestOutcome, ...] = field(default_factory=tuple)
    nxt_outcomes: tuple[ShortSellingIngestOutcome, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    errors_above_threshold: tuple[str, ...] = field(default_factory=tuple)
    total_skipped: int = 0
    skipped_outcomes: tuple[ShortSellingIngestOutcome, ...] = field(default_factory=tuple)

    @property
    def total_upserted(self) -> int:
        krx = sum(o.upserted for o in self.krx_outcomes)
        nxt = sum(o.upserted for o in self.nxt_outcomes)
        return krx + nxt

    @property
    def total_failed(self) -> int:
        krx = sum(1 for o in self.krx_outcomes if o.error is not None)
        nxt = sum(1 for o in self.nxt_outcomes if o.error is not None)
        return krx + nxt

    @property
    def skipped_count(self) -> int:
        """skip 카운터 표준 인터페이스 (Phase F-3 D-8).

        Short / Lending 의 원 필드명 비대칭 (ADR § 46.9 의도된 보존):
        - ShortSellingBulkResult: `total_skipped` (alphanumeric + sentinel 합산)
        - LendingStockBulkResult: `total_alphanumeric_skipped` (의미 동일, 분리 필드)

        `skipped_count` 가 표준 — caller 는 두 DTO 를 동일 인터페이스로 처리 가능.
        원 필드 (`total_skipped` / `total_alphanumeric_skipped`) 는 historical alias —
        미래 통일 rename 후속 chunk 후보 (ADR § 46.9 보존 결정 변경 시).
        """
        return self.total_skipped


__all__ = [
    "IngestShortSellingInput",
    "ShortSellingBulkResult",
    "ShortSellingIngestOutcome",
    "SkipReason",
]
