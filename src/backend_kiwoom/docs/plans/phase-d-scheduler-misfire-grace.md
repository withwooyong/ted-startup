# Phase D — scheduler misfire_grace_time 전 cron 적용 (Mac 절전 dead 대응)

## 0. 메타

- **추가일**: 2026-05-14 (KST)
- **분류**: ops fix (운영 정책 변경, 코드 변경 작음)
- **선행 조건**: ADR § 42 (Mac 절전 dead 원인 확정) + § 42.5 옵션 C 채택 (사용자 결정)
- **트리거**: 5-13 06:00 / 5-14 06:00/06:30 새벽 cron miss — Mac 절전 → Docker VM sleep → APScheduler timer 미발화
- **선행 chunk**: `d36cf51` (dead 분석)
- **다음 chunk**: F chunk (ka10001 NUMERIC overflow), Phase F 순위 5종

## 1. 현황 / 동기

### 1.1 현재 misfire 정책 (5-14 시점)

| 스케줄러 | cron | 현재 `misfire_grace_time` |
|----------|------|---------------------------|
| `SectorSyncScheduler` | 일 03:00 KST | 없음 (default 1s) |
| `StockMasterScheduler` | mon-fri 17:30 KST | 없음 |
| `StockFundamentalScheduler` | mon-fri 18:00 KST | 없음 |
| `OhlcvDailyScheduler` | mon-fri 06:00 KST | 없음 — **🔴 5-14 miss** |
| `DailyFlowScheduler` | mon-fri 06:30 KST | 없음 — **🔴 5-14 miss** |
| `WeeklyOhlcvScheduler` | sat 07:00 KST | 없음 |
| `MonthlyOhlcvScheduler` | 매월 1일 03:00 KST | 없음 |
| `YearlyOhlcvScheduler` | 매년 1/5 03:00 KST | 없음 |
| `SectorDailyOhlcvScheduler` | mon-fri 07:00 KST | 없음 |
| `ShortSellingScheduler` | mon-fri 07:30 KST | **1800s (30분)** |
| `LendingMarketScheduler` | mon-fri 07:45 KST | **1800s (30분)** |
| `LendingStockScheduler` | mon-fri 08:00 KST | **5400s (90분)** |

→ 12개 중 9개가 misfire 없음 = sleep 도중 cron 시각 도달 시 skip.

### 1.2 동기

ADR § 42 결정:
- Mac 절전 → Docker VM sleep → APScheduler timer wakeup 미발화 → cron miss
- 사용자 환경 = 노트북 + 학습 우선 → 옵션 C (misfire_grace_time) 채택

본 chunk 의 목표:
1. 9개 신규 적용 + 3개 기존 검토 → 통일된 misfire 정책
2. 노트북 wake (오전~정오) 안에 catch-up 가능하도록 grace 충분히 ↑
3. catch-up 못 잡힌 경우 backfill CLI 수동 회복 (보조 E)

## 2. 범위 외 (Out of Scope)

- 코드 외 인프라 (서버 이전 / caffeinate plist) — ADR § 42.5 옵션 B/A 별도
- APScheduler 의 missed firing 알람 / 모니터링 endpoint — `/admin/scheduler/diag` 기존
- backfill CLI 자체 변경 — 보조 E 는 기존 도구 활용 (변경 0)
- F chunk (ka10001 NUMERIC) — 본 chunk 와 독립

## 3. 결정

| # | 사안 | 결정 | 근거 |
|---|------|------|------|
| 1 | `misfire_grace_time` 값 | **21600s (6h)** 통일 | 노트북 wake 시각 분포 (대부분 09:00~13:00 KST) + cron 가장 빠른 06:00 KST → noon 까지 grace 안에 catch-up |
| 2 | 적용 범위 | **12개 스케줄러 모두** (9 신규 + 3 통일) | 일관성 ↑ / 운영 정책 단순화. 기존 1800s/1800s/5400s 의 별도 의도 (Phase E sector_daily 07:00 직후 wave 보호) 는 21600s 안에 포함됨 |
| 3 | 상수 위치 | 각 스케줄러 클래스의 `MISFIRE_GRACE_SECONDS: Final[int] = 21600` (기존 3개 클래스 패턴 1:1) | 클래스별 독립 — 향후 클래스별 조정 가능 |
| 4 | catch-up 실패 대안 | **backfill CLI 수동 회복** (보조 E, 기존 도구) | 사용자 환경 (노트북 학습 단계) — 매일 정오 이후 wake 시 그날 cron 누락 | backfill_ohlcv / backfill_daily_flow 호출 |
| 5 | 알람 / 알림 | **본 chunk 범위 외** | misfire skip 발생 시 사용자가 발견 → backfill CLI 호출. 자동 알람 (Telegram?) 은 향후 chunk |
| 6 | 테스트 전략 | 각 `test_scheduler_*.py` 에 `misfire_grace_time == 21600` 단위 추가 (12 테스트 +) | 기존 add_job kwarg 검증 패턴 일관 |
| 7 | ADR 갱신 | § 42.5 옵션 C 채택 + § 42.9 결정 기록 + 본 § 추가 | dead 분석 ADR 의 후속 |
| 8 | 운영 검증 | 본 chunk 머지 + 컨테이너 재배포 후 다음 새벽 cron (5-18 월 06:00) 발화 확인 | 컨테이너 재배포 = 단순 up -d (Migration 0) |

## 4. 변경 면 매핑

### 4.1 코드 (1 파일)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/scheduler.py` | 12 스케줄러 클래스의 add_job 에 `misfire_grace_time=self.MISFIRE_GRACE_SECONDS` 추가. 9개 신규 클래스에 `MISFIRE_GRACE_SECONDS: Final[int] = 21600` 상수 추가. 3개 기존 (ShortSelling/LendingMarket/LendingStock) 의 1800/1800/5400 → **21600** 통일 |

추정 변경 라인:
- 9개 신규: 클래스당 1줄 (상수) + 1줄 (kwarg) = 18줄
- 3개 갱신: 클래스당 1줄 (상수 값) = 3줄
- 로그 메시지 갱신 (cron= 표시 + misfire= 부분) — 선택, 12줄

총 ~30~40 줄 변경.

### 4.2 테스트 (12 갱신, 신규 0)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `tests/test_scheduler_sector_sync.py` | `misfire_grace_time == 21600` 단위 |
| 2 | `tests/test_scheduler_stock_master.py` | 동일 |
| 3 | `tests/test_scheduler_stock_fundamental.py` | 동일 |
| 4 | `tests/test_scheduler_ohlcv_daily.py` | 동일 |
| 5 | `tests/test_scheduler_daily_flow.py` | 동일 |
| 6 | `tests/test_scheduler_weekly_ohlcv.py` | 동일 |
| 7 | `tests/test_scheduler_monthly_ohlcv.py` | 동일 |
| 8 | `tests/test_scheduler_yearly_ohlcv.py` | 동일 |
| 9 | `tests/test_scheduler_sector_daily.py` | 동일 |
| 10 | `tests/test_scheduler_short_selling.py` | 1800 → **21600** 갱신 |
| 11 | `tests/test_scheduler_lending_market.py` | 1800 → **21600** 갱신 |
| 12 | `tests/test_scheduler_lending_stock.py` | 5400 → **21600** 갱신 |

추정 변경: 케이스당 1줄 단언 (총 ~12 cases). 기존 add_job kwarg 검증 패턴 재사용.

### 4.3 문서 (4 갱신)

- `docs/adr/ADR-0001-backend-kiwoom-foundation.md` § 42.5 옵션 C 채택 + § 42.9 결정 #C 기록 + 본 chunk § 신규 (예: § 43)
- `STATUS.md` § 0 / § 4 / § 5 / § 6
- `HANDOFF.md`
- `CHANGELOG.md` prepend

## 5. 적대적 사전 self-check

| # | 위험 | 완화 |
|---|------|------|
| H-1 | grace 21600s (6h) 가 너무 길어 stale 데이터 catch-up | 06:00 cron + 21600s grace = noon 까지 catch-up. KRX 시장 시작 09:00 — catch-up 발화가 시장 시작 후라도 데이터는 trading_date previous_business_day 기준 (현재 cron 정책 § 35) — stale 위험 X |
| H-2 | misfire grace 동안 중복 발화 가능성 | `max_instances=1` + `coalesce=True` (기존 모든 add_job) 가 보장 — 중복 실행 차단 + 누적 misfire 1회로 압축 |
| H-3 | grace 안에서 catch-up 발화 후 다음 정시 cron 충돌 | coalesce=True 가 정상 발화. 다음 cron 은 정상 시각 발화 (예: 06:00 catch-up 후 익일 06:00) |
| H-4 | 기존 Phase E 3 cron 의 misfire 의도 (sector_daily 07:00 직후 wave 보호) 가 21600s 통일로 손실 | 21600s = 1800s/5400s 의 포함 집합. wave 보호 그대로 + 더 긴 catch-up 추가. 의도 손실 0 |
| H-5 | 노트북 정오 이후 wake 시 그날 cron skip — 매일 발생 가능 | 사용자 결정 (학습 우선) 으로 수용. backfill CLI 수동 회복 (보조 E). 사용자가 노트북 wake 후 STATUS 확인 + 누락 일자 backfill 호출 |
| H-6 | 21600s grace 안에 wake 시 catch-up 발화 = 외부 KRX rate limit 영향 | **2b 2R M-1 보강 (2026-05-14)**: KRX rate limit 보호는 **`KiwoomClient` 인스턴스 단위** (`Semaphore(4)` + `_interval_lock`). 그러나 12 scheduler 가 각자 독립 `AsyncIOScheduler` + factory 매 호출 새 `KiwoomClient` 빌드 = 인스턴스 분리. 6시간 grace 안에 5+ cron 동시 catch-up 시 cross-scheduler 합산 = 5 × Semaphore(4) = **20 concurrent KRX 호출 가능** → 2초 rate limit 위반 + 429 폭증 + alias revoke 위험. `coalesce=True` 는 **동일 job 안에서만** 합치고 cross-scheduler 미보호. **본 chunk 운영 결과 모니터링 + 위반 발생 시 별도 chunk** (공유 `KiwoomClient` singleton 또는 cross-scheduler `asyncio.Semaphore` 도입). 학습 우선 단계 = 위험 수용 + 모니터 |
| H-7 | 5-18 (월) 새벽 첫 cron 검증 (캐치업 효과) | 5-15~5-17 시장 휴장 (목/금/토/일 = 5-15 목 평일이라 cron 있음, 5-17 토 sat 07:00 weekly). 5-18 (월) 06:00 OhlcvDaily cron 자연 catch-up 검증 |
| H-8 | 컨테이너 재배포 = 새벽 cron 사이에 진행 시 sleep gap | docker compose up -d = Recreated → APScheduler 재시작. cron 시각 재계산. 본 chunk 머지는 일중 시각 (낮) 권고 |
| H-9 | 21600s grace 가 너무 길어 의도된 cron 시각 (06:00) 보다 늦은 발화 = 로그상 혼란 | APScheduler 로그가 `scheduled at 06:00 + actual run X:Y` 명시 — 운영자 분명히 식별. 본 chunk 의 운영 결과에 기록 |
| H-10 | 테스트 + 코드 둘 다 21600 매직 넘버 → 상수 변경 시 양쪽 갱신 부담 | Final[int] 상수 사용 + 테스트는 `Scheduler.MISFIRE_GRACE_SECONDS` 클래스 attribute 비교 — 매직 X. 상수 변경 시 자동 동기 |

## 6. DoD

**코드**:
- [ ] `app/scheduler.py` 9개 스케줄러에 `MISFIRE_GRACE_SECONDS: Final[int] = 21600` 추가
- [ ] 12개 스케줄러 모두 `add_job(..., misfire_grace_time=self.MISFIRE_GRACE_SECONDS, ...)` 적용
- [ ] 3개 기존 (Short/LendingMarket/LendingStock) 의 1800/1800/5400 → 21600 통일

**테스트**:
- [ ] 12 `test_scheduler_*.py` 갱신 — `misfire_grace_time == 21600` 단위 단언
- [ ] `ruff check` + `mypy --strict` PASS
- [ ] 1199 → 1199+ 테스트 100% green / cov ≥80%

**이중 리뷰**:
- [ ] 1R 2a (sonnet) — 일반 품질 PASS
- [ ] 1R 2b (opus) — 적대적 / 보안 — `--force-2b` 강제 (backend_kiwoom 표준)
- [ ] MEDIUM 즉시 fix

**Verification**:
- [ ] 빌드 / ruff / mypy / pytest / 보안 ⚪ (계약 분류) / 런타임 ✅ / E2E ⚪ (UI 변경 0)

**문서**:
- [ ] ADR § 43 (본 chunk) 신규 + § 42.5 옵션 C 채택 + § 42.9 결정 기록
- [ ] STATUS.md / HANDOFF.md / CHANGELOG.md / 본 plan doc 자기 참조

**운영**:
- [ ] 컨테이너 재배포 (`docker compose build` + `up -d`) — Migration 0
- [ ] /health + `/admin/scheduler/diag` 12 scheduler 활성 + misfire 21600 확인
- [ ] 5-18 (월) 06:00 OhlcvDaily 자연 catch-up 검증 (운영 모니터, 별도 시점)

## 7. 다음 chunk

1. **(별도) F chunk** — ka10001 NUMERIC overflow + sentinel WARN/skipped 분리 (Migration 신규)
2. **(별도) Phase F 순위 5종** — ka10027/30/31/32/23
3. **(운영) 5-18 (월) 새벽 cron 검증** — 본 chunk 효과 운영 확정
4. **(향후) caffeinate launchd plist** — A 옵션 추가 채택 시 별도 chunk (lid close 시 sleep 대응)
5. **(향후) Linux 서버 이전** — B 옵션 / 25 endpoint 완료 후 결정

---

_Mac 절전 dead 대응 chunk. 노트북 + 학습 우선 사용자 환경에 맞춘 misfire_grace_time = 21600s (6h) 통일. wake 시각 분포 (09~13시) 안에 catch-up + 못 잡힌 경우 backfill CLI 수동 회복. 코드 변경 작음 (~30-40줄) + 테스트 12 갱신._
