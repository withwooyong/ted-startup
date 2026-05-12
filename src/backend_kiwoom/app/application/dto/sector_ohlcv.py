"""IngestSectorDailyInput / SectorIngestOutcome / SectorBulkSyncResult DTO (D-1).

설계: endpoint-13-ka20006.md § 6.3~6.4 + § 12.

ka10081/82/83/94 DTO 패턴 응용. 단, sector 도메인은 sector_id (PK) 입력 (plan § 12.2 #9).

특징 (plan § 12.2):
- #4 NXT skip — `SectorIngestOutcome(skipped=True, reason="nxt_sector_not_supported")`
- #5 sector_master_missing — sector_id 조회 결과 None 시 skip outcome
- #9 UseCase 입력 = `IngestSectorDailyInput(sector_id: int, base_date: date)`
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True, slots=True)
class IngestSectorDailyInput:
    """UseCase 입력 DTO (plan § 12.2 #9).

    sector_id (PK) 입력 — sector_code 단독 lookup 불가 (sector.py UNIQUE 가
    (market_code, sector_code) 페어이므로).
    """

    sector_id: int
    base_date: date


@dataclass(frozen=True, slots=True)
class SectorIngestOutcome:
    """단일 sector ingest 결과.

    skipped=True 케이스 (plan § 12.2):
    - #4 NXT 요청 → reason="nxt_sector_not_supported"
    - #5 sector_id 조회 결과 None → reason="sector_master_missing"
    - sector.is_active=False → reason="sector_inactive"

    upserted=N (N>0) 가 정상 성공.
    """

    upserted: int = 0
    skipped: bool = False
    reason: str | None = None
    sector_id: int | None = None
    sector_code: str | None = None


@dataclass(frozen=True, slots=True)
class SectorBulkSyncResult:
    """bulk sync 실행 결과 (plan § 12.2 #4 — active sector 전체 iterate).

    R1 invariant — errors 는 tuple (mutable list 노출 금지).

    1R HIGH #5 fix — skipped 카운터 분리:
    - skipped = 정상 운영 상태 (NXT/sector_inactive/sector_master_missing 등 outcome.skipped=True)
    - failed = 예외/오류 (KiwoomError, 일반 Exception)
    이를 분리하지 않으면 FAILURE_RATIO_ALERT_THRESHOLD 가 sector_inactive 케이스에서
    허위 경보 발생.
    """

    total: int
    success: int
    failed: int
    skipped: int = 0
    errors: tuple[str, ...] = field(default_factory=tuple)


__all__ = [
    "IngestSectorDailyInput",
    "SectorBulkSyncResult",
    "SectorIngestOutcome",
]
