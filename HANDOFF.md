# Session Handoff

> Last updated: 2026-05-09 (KST) — Phase C-3β
> Branch: `master`
> Latest commit (커밋 대기): `feat(kiwoom): Phase C-3β — 주/월봉 OHLCV 자동화`
> 직전 푸시: `8fcabe4` — Phase C-3α 인프라

## Current Status

**Phase C-3β (주/월봉 OHLCV 자동화) 완료** — ka10082 (주봉) + ka10083 (월봉) endpoint 자동화 layer (UseCase + Router 4 path + Scheduler 2 job + lifespan). C-3α 인프라 위에 R1 정착 패턴 5종 전면 적용. ted-run 풀 파이프라인 1회 통과 (CONDITIONAL → PASS), **897 → 939 cases / 97% coverage**. **25 endpoint: 8 → 10 (40%)**.

## Completed This Session (커밋 대기)

| # | Task | 산출물 | Notes |
|---|------|--------|-------|
| 1 | IngestPeriodicOhlcvUseCase | `app/application/service/ohlcv_periodic_service.py` (신규) | period dispatch (WEEKLY/MONTHLY) / YEARLY → NotImplementedError / R1 5종 |
| 2 | Router 4 path 신규 | `app/adapter/web/routers/ohlcv_periodic.py` (신규) | POST sync × 2 + POST refresh × 2 / 공용 핸들러 `_do_sync` `_do_refresh` (period 만 caller 결정) |
| 3 | Scheduler 2 클래스 | `app/scheduler.py` (수정) | WeeklyOhlcvScheduler + MonthlyOhlcvScheduler (cron 금 19:30 / 매월 1일 03:00) |
| 4 | Batch fire 콜백 2 | `app/batch/{weekly,monthly}_ohlcv_job.py` (신규) | 실패율 알람 / 예외 swallow / ohlcv_daily_job 패턴 복제 |
| 5 | DI factory 추가 | `app/adapter/web/_deps.py` (수정) | IngestPeriodicOhlcvUseCaseFactory + get/set/reset |
| 6 | Settings alias 2 추가 | `app/config/settings.py` (수정) | scheduler_weekly_ohlcv_sync_alias + scheduler_monthly_ohlcv_sync_alias |
| 7 | Lifespan 통합 | `app/main.py` (수정) | factory + scheduler 등록 + alias fail-fast + router include + LIFO reset |
| 8 | 4 신규 테스트 + 2 수정 | tests/ (+42 cases) | service 17 / router 10 / scheduler+job 11 / deps 4. test_scheduler / test_stock_master_scheduler 의 lifespan smoke test alias 추가 |
| 9 | 1차 코드 리뷰 (sonnet) | python-reviewer | CONDITIONAL → PASS. HIGH 1 (H-1) + MEDIUM 2 (M-1, M-2) + LOW 2 (L-1, L-3) 즉시 적용 |
| 10 | Verification 5관문 | mypy / ruff / pytest+coverage | 72 files 0 errors / All passed / 939 cases / 97% |
| 11 | ADR-0001 § 24 추가 | `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` | 핵심 결정 7건 + 1R 결과 (5건 적용) + Defer + 다음 chunk |
| 12 | STATUS.md 갱신 | `src/backend_kiwoom/STATUS.md` | Phase C 80→90%, chunk 21 누적, 25 endpoint 8→10 (40%), ka10082/83 완료 이동 |
| 13 | CHANGELOG prepend | `CHANGELOG.md` | C-3β 항목 + H-7 cron 충돌 검증 표 |
| 14 | plan doc 체크박스 | `docs/plans/phase-c-3-weekly-monthly-ohlcv.md` § 7.2 | C-3β 완료 표시 |
| 15 | HANDOFF 갱신 | `HANDOFF.md` | 본 파일 |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | 본 세션 산출물 커밋 + 푸시 | pending | 사용자 승인 후 — 한 commit |
| 2 | **C-backfill** — `scripts/backfill_ohlcv.py` CLI | not started | C-1β/C-2β/C-3β 통합. 운영 미해결 4건 (페이지네이션/3년 시간/NUMERIC magnitude/sync 시간) 일괄 해소 |
| 3 | refactor R2 (1R Defer 일괄 정리) | not started | L-2 / E-1 / E-2 / M-3 (4건) — `_do_sync` NotImplementedError 핸들러 / ka10081 sync KiwoomError 핸들러 / `# type: ignore` → `cast()` / reset_* docstring |
| 4 | KOSCOM 공시 수동 cross-check (1~2건) | pending | 가설 B 최종 확정 |
| 5 | ka10094 (년봉, P2) | pending | C-3 와 동일 패턴 (Migration 1 + UseCase YEARLY 분기 활성화) |
| 6 | 운영 first-call 검증 | 대기 | `dt` 의미 / 응답 list 키 / 일봉 vs 키움 주월봉 cross-check (Phase H) |

## Key Decisions Made (C-3β)

### 핵심 설계 (ADR § 24.2)

- **UseCase 통합** (`IngestPeriodicOhlcvUseCase`) — period 인자 dispatch. ka10081 (Daily) 와 분리 (hot path 차이) but ka10082/83 은 통합 (구조 동일 + period 만 다름)
- **Period dispatch** — `_validate_period` 에서 YEARLY → `NotImplementedError`, DAILY 는 enum 자체에서 차단 (3값). `_ingest_one` 내부에서 period 별 fetch_weekly/fetch_monthly 분기
- **Router 분리** (별도 파일 `routers/ohlcv_periodic.py`) — 4 path + 공용 핸들러 `_do_sync` / `_do_refresh` (period 만 caller 결정). 응답 DTO 동일 (`OhlcvPeriodicSyncResultOut`)
- **Scheduler 2 클래스** — WeeklyOhlcvScheduler / MonthlyOhlcvScheduler. OhlcvDailyScheduler 패턴 ~95% 복제. 각자 독립 lifecycle
- **cron 시간 (H-7)** — weekly = 금 KST 19:30 (daily_flow 19:00 후 30분) / monthly = 매월 1일 KST 03:00. 30분 간격 cron 패턴 일관 (17:30→18:00→18:30→19:00→19:30)
- **DI factory 통합** — weekly/monthly Scheduler 가 같은 IngestPeriodicOhlcvUseCaseFactory 공유 (period 는 fire 콜백에서 결정)
- **R1 정착 패턴 5종 전면 적용** — errors tuple / StockMasterNotFoundError / fetched_at non-Optional (조회 endpoint N/A) / max_length=2 / NXT Exception 격리

### 1차 리뷰 결과 (CONDITIONAL → PASS)

- **HIGH H-1**: `_do_sync` 에 KiwoomError 계열 5 except 블록 추가 — `_do_refresh` 와 대칭. factory 진입 시점 누설 차단
- **MEDIUM M-1**: `_validate_period` 의 dead code (`period.value == "daily"`) 제거 + docstring 갱신
- **MEDIUM M-2**: service docstring "재사용" → "동일 구조 복제 (공통 추출은 refactor chunk)" 명확화
- **LOW L-1**: MonthlyOhlcvScheduler.start() docstring 추가 (대칭성 회복)
- **LOW L-3**: KiwoomBusinessError 로그에 `msg=exc.message` 포함

## Known Issues

### C-3β 후 잔여

- **L-2** (1R defer): `_do_sync` / `_do_refresh` 에 `NotImplementedError → 501` 핸들러 부재 (caller 가 period 고정하므로 실질 위험 없음 — refactor chunk 권고)
- **E-1** (기존 코드 이슈): ka10081 `sync_ohlcv_daily` 도 KiwoomError 핸들러 미등록 — H-1 과 동일 패턴 (별도 refactor chunk)
- **E-2** (기존 코드 이슈): `_deps.py` `reset_*` 함수 docstring "테스트 전용" — lifespan teardown 도 사용. 주석 정정 필요
- **M-3** (1R defer C-3α): `# type: ignore[arg-type]` → `cast()` — 기존 일봉 Repository 패턴 답습 (별도 refactor chunk)
- **운영 검증 미해결**: `dt` 의미 / 응답 list 키 / 일봉 vs 키움 주월봉 cross-check (Phase H) / 페이지네이션 빈도 / 3년 백필 시간 / active 3000 + NXT 1500 sync 실측

## Context for Next Session

### 사용자의 원래 의도 / 목표

backend_kiwoom Phase C 의 OHLCV 패밀리 (일/주/월) 모두 production-ready 도달. ka10082/83 자동화가 직전 chunk (C-3α 인프라) 와 페어. R1 정착 패턴 (errors tuple / StockMasterNotFoundError / NXT Exception 격리 / max_length=2) 신규 도메인에서 동일하게 적용 — 회귀 위험 차단.

### 선택된 접근 + 이유

- **chunk 분할 (α/β)** — C-1α/β / C-2α/β/γ 정착 패턴 일관. α 통과 후 β 의존성 명확. 단일 chunk 1,500줄 부담 회피
- **두 endpoint (ka10082/83) 통합 UseCase** — 구조 100% 동일 + period 만 다름. 분리 시 중복 코드. period dispatch 로 ka10094 추가 시 fetch_yearly + 1 분기만
- **공용 핸들러** (`_do_sync` / `_do_refresh`) — 4 path 가 같은 매핑. 변경 시 한 군데 (DRY). period 만 caller 에서 결정
- **ted-run 풀 파이프라인** — TDD red → 구현 green → 1차 리뷰 → 5관문. CONDITIONAL → 5건 즉시 적용 → PASS. 자동 분류 = 계약 변경
- **Quality-First** — 939 PASS / coverage 97%. R1 invariant 회귀 (errors tuple) 단위 검증 + H-7 cron 충돌 단위 검증 (test_weekly_cron_does_not_collide_with_daily_flow_19_00)

### 사용자 제약 / 선호

- 한글 커밋 메시지 (~/.claude/CLAUDE.md 글로벌 규칙)
- 푸시는 명시적 요청 시만 (커밋과 분리)
- 큰 Phase 는 chunk 분할 후 ted-run 풀 파이프라인
- 진행 상황 가시화 — 체크리스트 + 한 줄 현황
- backend_kiwoom CLAUDE.md — STATUS.md / HANDOFF.md / CHANGELOG.md 3 문서 동시 갱신

### 다음 세션 진입 시 결정 필요

사용자에게 옵션 확인 권장:

1. **C-backfill** (`scripts/backfill_ohlcv.py` CLI, 권고 1순위) — Phase C 의 운영 미해결 4건 (페이지네이션 빈도 / 3년 시간 / NUMERIC magnitude / sync 실측) 일괄 해소. 일/주/월 모두 동일 CLI 로 처리
2. **refactor R2** — 1R Defer 4건 일괄 정리 (L-2 + E-1 + E-2 + M-3). 코드 변경 80~150줄, 회귀 위험 낮음
3. **ka10094 (년봉, P2)** — C-3 패턴 그대로 복제 + UseCase YEARLY 분기 활성화 (현재 NotImplementedError → 정상 분기)
4. **KOSCOM cross-check 수동** — 가설 B 최종 확정 (1~2건)
5. **Phase D 진입** — ka10080 분봉 (대용량 파티션 결정 선행)

## Files Modified This Session (커밋 대기)

```
src/backend_kiwoom/app/application/service/ohlcv_periodic_service.py        (신규)
src/backend_kiwoom/app/adapter/web/routers/ohlcv_periodic.py                (신규)
src/backend_kiwoom/app/batch/weekly_ohlcv_job.py                            (신규)
src/backend_kiwoom/app/batch/monthly_ohlcv_job.py                           (신규)
src/backend_kiwoom/tests/test_ohlcv_periodic_service.py                     (신규, 17 cases)
src/backend_kiwoom/tests/test_ohlcv_router_periodic.py                      (신규, 10 cases)
src/backend_kiwoom/tests/test_weekly_monthly_ohlcv_scheduler.py             (신규, 11 cases)
src/backend_kiwoom/tests/test_ohlcv_periodic_deps.py                        (신규, 4 cases)
src/backend_kiwoom/app/scheduler.py                                         (Weekly + Monthly Scheduler 추가)
src/backend_kiwoom/app/main.py                                              (lifespan factory + scheduler + router + alias fail-fast + LIFO reset)
src/backend_kiwoom/app/adapter/web/_deps.py                                 (IngestPeriodicOhlcvUseCaseFactory + get/set/reset)
src/backend_kiwoom/app/config/settings.py                                   (alias 2 추가)
src/backend_kiwoom/tests/test_scheduler.py                                  (lifespan smoke test alias 추가)
src/backend_kiwoom/tests/test_stock_master_scheduler.py                     (lifespan smoke test alias 추가)
src/backend_kiwoom/STATUS.md                                                (Phase C 80→90%, chunk 21, 25 endpoint 8→10)
src/backend_kiwoom/docs/plans/phase-c-3-weekly-monthly-ohlcv.md             (§ 7.2 체크박스 갱신)
docs/ADR/ADR-0001-backend-kiwoom-foundation.md                              (§ 24 추가)
CHANGELOG.md                                                                (prepend)
HANDOFF.md                                                                  (본 파일)
```

총 19 파일 / 신규 8 + 수정 11 / 추정 +2,200 줄
