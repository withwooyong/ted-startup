# Session Handoff

> Last updated: 2026-05-11 (KST) — Phase C-4 (ka10094 년봉) 완료. **Phase C chart 카테고리 종결**.
> Branch: `master`
> Latest commit: 본 chunk (C-4 — ka10094 년봉 / Migration 014 / 11/25 endpoint)
> 미푸시 commit: **2 건** (C-2δ Migration 013 + C-4 ka10094, 사용자 명시 요청 시만 push)

## Current Status

Phase C-4 (ka10094 년봉) 완료. C-3α/β 의 YEARLY NotImplementedError 가드 → 활성화. 응답 7 필드 + NXT skip + 매년 1월 5일 KST 03:00 cron. **Phase C chart 카테고리 (일/주/월/년봉) 종결**. /ted-run 풀 파이프라인 (TDD → 구현 → 1R PASS → Verification Loop → ADR § 29). 1030 → **1035 tests** (+5 from test_migration_014 신규). **11/25 endpoint** 완료. scheduler_enabled 활성은 모든 작업 완료 후로 보류.

## Completed This Session

| # | Task | 결과 | Files |
|---|------|------|-------|
| 1 | /ted-run 풀 파이프라인 — Phase C-2δ Migration 013 (C/E 중복 2 컬럼 DROP) | `8dd5727` / 1030 tests / ADR § 28 | 6 코드 + 4 테스트 + 1 운영 doc + 4 ADR/STATUS/HANDOFF/CHANGELOG |
| 2 | /ted-run 풀 파이프라인 — Phase C-4 ka10094 년봉 (Migration 014 / KRX only NXT skip) | (this commit) / 1035 tests / ADR § 29 / Phase C chart 종결 | 11 코드 + 6 테스트 + plan doc § 12 + 4 ADR/STATUS/HANDOFF/CHANGELOG |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | **refactor R2 (1R Defer 일괄 정리)** | not started | L-2 / E-1 / M-3 / E-2 / gap detection 5건 일괄. LOW / 1일 |
| 2 | follow-up F6/F7/F8 + daily_flow 빈 응답 1건 통합 | pending | LOW / 0.5일 |
| 3 | ETF/ETN OHLCV 별도 endpoint (옵션 c) | pending | 신규 도메인 |
| 4 | Phase D — ka10080 분봉 / ka20006 업종일봉 | 대기 | 대용량 파티션 결정 선행 |
| 5 | Phase E (공매도/대차) / F (순위) / G (투자자별) | 대기 | 신규 endpoint wave |
| **최종** | **scheduler_enabled 일괄 활성 + 1주 모니터** | 사용자 결정 보류 | 모든 작업 완료 후 활성. 측정 #4 일간 cron elapsed / OHLCV + daily_flow + yearly 통합 |

## Key Decisions Made

### Phase C 종결 — chart 카테고리 4 endpoint 완성

| API | 명 | cron | 호출 정책 |
|-----|----|----- |----------|
| ka10081 | 일봉 | 평일 18:30 | KRX + NXT |
| ka10082 | 주봉 | 금 19:30 | KRX + NXT |
| ka10083 | 월봉 | 매월 1일 03:00 | KRX + NXT |
| ka10094 | **년봉 (본 chunk)** | **매년 1월 5일 03:00** | **KRX only (NXT skip)** |
| ka10086 | 일별 수급 | 평일 19:00 | KRX + NXT |

`IngestPeriodicOhlcvUseCase` 가 Period dispatch (WEEKLY/MONTHLY/YEARLY) 완성. period dispatch 패턴으로 향후 endpoint 도입 간소화.

### NXT skip 정책 (yearly_nxt_disabled)

ka10094 년봉은 30년 백필이 의미 있으나 NXT 는 2024-03 시작 (1년 미만) — 응답 패턴 미확정 + 데이터 가치 낮음. UseCase 가드로 NXT 호출 자체 차단. 테이블 (stock_price_yearly_nxt) 은 일관성 유지를 위해 신규 (향후 NXT skip 해제 chunk 시 활용).

### Verification Loop 가 잡은 5건 (Phase C-4)

1. **mypy invariant list** — type union 정정
2. **helper signature 확장** — `Sequence[DailyChartRow | YearlyChartRow]`
3. **C-3α stale 가드 단언 6건** — plan doc § 12.3 누락. testcontainers 자동 발견
4. **테스트 env alias 누락** — SCHEDULER_YEARLY_OHLCV_SYNC_ALIAS
5. **test_migration_013 단언** — 014 head 진입 후 transactional rollback 동작 변경 → downgrade target 미도달 단언으로 정정

### scheduler_enabled 보류 (사용자 결정 2026-05-11)

모든 작업 완료 후 일괄 활성. 본 chunk 까지 YearlyOhlcvScheduler 등록 코드만 추가. 활성 시점에 측정 #4 (일간 cron elapsed) 추가 + 1주 모니터로 ADR § 26.5 + § 28 + § 29 후속 측정 채움.

## Known Issues

본 세션 해소 (2건):
- ✅ #17 Migration 013 미진행 → C-2δ 완료 (`8dd5727`)
- ✅ #18 ka10094 (년봉) 미구현 → C-4 완료 (this commit)

기존 미해결 유지:
- OHLCV F6/F7/F8 (LOW)
- 일간 cron elapsed 미측정 (Pending #6, scheduler_enabled 활성화 시)
- KRX 빈 응답 1 종목 (LOW)
- ka10086 첫 page 만 ~80 거래일, p2~ ~22 거래일 패턴 차이 (LOW, 키움 서버 측 분기)
- KOSCOM cross-check 수동 미완 (가설 B)
- ka10094 운영 first-call 미검증 — `dt` 가 1월 2일인지 / 년봉 high/low 가 월/주/일봉의 max/min 과 일치하는지 (plan § 10.3)

## Context for Next Session

### 사용자의 원래 의도

본 세션 흐름:
1. 사용자 "다음작업 알려줘" → STATUS § 5 1순위 = Migration 013 → 사용자 선택
2. ted-run 풀 파이프라인 Migration 013 종료 (`8dd5727`)
3. 사용자 "scheduler 시간 알려줘" → 7 job cron 표 제시
4. 사용자 "scheduler_enabled 운영 cron 활성은 모든 작업이 완료되면 활성화 하는걸로 하고 다음작업 알려줘"
5. § 5 후보 재정렬 → 1순위 ka10094 (Phase C 종결) 추천 → 사용자 선택
6. ted-run 풀 파이프라인 Phase C-4 종료 (this commit)

### 선택된 접근 + 이유

- **scheduler_enabled 보류 정책 명시** — 사용자 결정 STATUS § 5 최종 위치 + 모든 chunk 결정 doc 에 일관 기록 (ADR § 29 / HANDOFF / CHANGELOG)
- **Phase C 종결 우선 (ka10094)** — C-3α/β 패턴 정착 + NotImplementedError 가드 활성만이라 빠르고 안전 (~1일)
- **ted-run 풀 파이프라인 + plan doc § 12 사전 작성** — Migration 013 흐름 정착. self-check H-1~H-10 명시 후 진입
- **NXT skip 정책 UseCase 가드** — fetch_yearly 자체 호출 차단. 테이블은 일관성 유지
- **응답 7 필드 별도 정의** — DailyChartRow 상속 불가, YearlyChartRow 신규 + to_normalized NULL 영속

### 사용자 제약 / 선호 (반복 등장)

- 한글 커밋 메시지
- 푸시는 명시 요청 시만 (`git push` 와 commit 분리)
- backend_kiwoom CLAUDE.md § 1 — STATUS / HANDOFF / CHANGELOG 동시 갱신
- chunk 분리 패턴: 운영 발견 즉시 fix + 새 발견은 다음 chunk
- 긴 작업 백그라운드 + 진행 상황 가시화
- 큰 Phase 는 chunk 분할 후 ted-run 풀 파이프라인
- **scheduler_enabled 활성은 모든 작업 완료 후** (2026-05-11)

### 다음 세션 진입 시 결정 필요

다음 chunk 1순위 후보:

1. **refactor R2 (1R Defer 일괄 정리)** (LOW / 1일)
   - L-2 (NotImplementedError 핸들러 — C-4 후 일부 잔존 여부?)
   - E-1 (ka10081 sync KiwoomError 핸들러)
   - M-3 / E-2 / gap detection
2. follow-up F6/F7/F8 + daily_flow 빈 응답 1건 (LOW)
3. ETF/ETN OHLCV 별도 endpoint
4. Phase D (분봉 / 업종일봉)
5. Phase E/F/G wave

## Files Modified This Session (C-4)

본 chunk (1 commit, push 보류):

```
backend_kiwoom 코드 (11):
src/backend_kiwoom/migrations/versions/014_stock_price_yearly.py        (신규 ~110 line)
src/backend_kiwoom/app/adapter/out/persistence/models/stock_price_periodic.py  (+2 클래스, header 갱신)
src/backend_kiwoom/app/adapter/out/persistence/models/__init__.py        (+2 export)
src/backend_kiwoom/app/adapter/out/kiwoom/chart.py                       (+YearlyChartRow + Response + fetch_yearly + helper union)
src/backend_kiwoom/app/adapter/out/persistence/repositories/stock_price_periodic.py  (+YEARLY dispatch, PeriodicModel union)
src/backend_kiwoom/app/application/service/ohlcv_periodic_service.py     (+_ingest_one YEARLY 분기 + NXT skip 가드 / _validate_period 정리 / _api_id_for 갱신)
src/backend_kiwoom/app/adapter/web/routers/ohlcv_periodic.py             (+yearly sync/refresh 2 path + _api_id_for 헬퍼)
src/backend_kiwoom/app/batch/yearly_ohlcv_job.py                          (신규 ~70 line)
src/backend_kiwoom/app/scheduler.py                                       (+YearlyOhlcvScheduler 클래스 + JOB_ID)
src/backend_kiwoom/app/config/settings.py                                 (+scheduler_yearly_ohlcv_sync_alias)
src/backend_kiwoom/app/main.py                                            (+lifespan alias fail-fast + YearlyOhlcvScheduler)

backend_kiwoom 테스트 (6):
src/backend_kiwoom/tests/test_migration_014.py                            (신규 5 cases)
src/backend_kiwoom/tests/test_stock_price_periodic_repository.py          (3 stale → YEARLY 활성 검증)
src/backend_kiwoom/tests/test_ohlcv_periodic_service.py                   (2 stale → YEARLY KRX-only + NXT skip 검증)
src/backend_kiwoom/tests/test_skip_base_date_validation.py                (1 stale → YEARLY skip-validation 정상)
src/backend_kiwoom/tests/test_scheduler.py + test_stock_master_scheduler.py  (SCHEDULER_YEARLY_OHLCV_SYNC_ALIAS env)
src/backend_kiwoom/tests/test_migration_013.py                            (downgrade 가드 단언 정정 — transactional rollback 동작)

ADR / STATUS / CHANGELOG / HANDOFF / plan doc:
docs/ADR/ADR-0001-backend-kiwoom-foundation.md                            (§ 29 신규 6 sub-§)
src/backend_kiwoom/docs/plans/endpoint-09-ka10094.md                      (§ 12 신규 7 sub-§)
src/backend_kiwoom/STATUS.md                                               (§ 0 / § 2.1 / § 2.3 / § 3 / § 4 / § 5 / 마지막 갱신)
CHANGELOG.md                                                               (feat entry prepend)
HANDOFF.md                                                                 (본 파일)
```

테스트: 1030 → **1035** (+5: test_migration_014 5 신규 / stale 갱신은 count 동일). coverage 유지.

## 본 세션 누적 commits (push 보류, 2건)

```
8dd5727 ✅ refactor(kiwoom): Phase C-2δ — Migration 013 (C/E 중복 2 컬럼 DROP, 10→8 도메인)
<this>  🆕 feat(kiwoom): Phase C-4 — ka10094 년봉 OHLCV (Migration 014, KRX only NXT skip, 11/25 endpoint)
```
