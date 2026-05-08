# Session Handoff

> Last updated: 2026-05-08 (KST) — **backend_kiwoom A1 ~ A3-γ + F1 + B-α/β + B-γ-1/2 + C-1α/β 완료 — Phase C-1 마무리, 누적 14 chunk, 커밋 대기**
> Branch: `master` (uncommitted — Step 5 커밋 진행 예정)
> 이전 마일스톤: `a98e37b` — Phase C-1α 인프라
> 세션 시작점: `a98e37b` 직후 (이번 세션 C-1β 자동화)

## Current Status

backend_kiwoom **Phase A 100% + Phase B 100% + Phase C-1 100% (α 인프라 + β 자동화)**. 백테스팅 OHLCV 풀 파이프라인 완성 — IngestDailyOhlcvUseCase + 라우터 3종 + OhlcvDailyScheduler + lifespan 통합.

| 단계 | 커밋 | 범위 |
|------|------|------|
| A1~A3-γ + F1 | (생략) | 인증 / 트랜스포트 / 섹터 마스터 |
| B-α | `bf9956a` | ka10099 종목 마스터 + StockMasterScheduler |
| B-β | `abce7e0` | ka10100 단건 gap-filler / lazy fetch |
| B-γ-1 | `a287172` | ka10001 펀더멘털 인프라 |
| B-γ-2 | `56dbad9` | ka10001 펀더멘털 자동화 |
| C-1α | (이번 세션 시작 직전) | ka10081 OHLCV 인프라 |
| **C-1β** | **(이번 세션)** | ka10081 OHLCV 자동화 — UseCase + 라우터 + Scheduler + lifespan |

**누적 결과**: **694 tests passed / coverage 93.08%** / 적대적 이중 리뷰 누적 CRITICAL 6 + HIGH 26 발견 → 전부 적용 → 0건 PASS. **Phase C-1 마무리 (백테스팅 OHLCV 본체 완성)**.

## Completed This Session

### Phase C-1β — ka10081 OHLCV 자동화

- 자동 분류: **계약 변경 (contract)** + `--force-2b` 적대적 리뷰 강제
- 1R: HIGH 0 / MEDIUM 6 (2a 3 + 2b 3) / LOW 6 → 5건 즉시 적용 + 회귀 4 추가 → **2R 진입 없이 PASS**
- 사용자 결정: nxt_collection_enabled 디폴트 OFF / target_date_range = today ± 365 / cron = KST mon-fri 18:30

**신규/수정 파일 (코드 8 + 테스트 5)**

- `app/application/service/ohlcv_daily_service.py` (신규) — `IngestDailyOhlcvUseCase.execute / refresh_one` + per-(stock,exchange) 격리 + KRX/NXT 분리 ingest + `_validate_base_date` (today ± 365) + `_validate_market_codes` (StockListMarketType 화이트리스트)
- `app/adapter/web/routers/ohlcv.py` (신규) — POST sync (admin) / POST refresh (admin) / GET range (DB only). KiwoomError 매핑 + `GET_RANGE_MAX_DAYS=400` cap
- `app/batch/ohlcv_daily_job.py` (신규) — `fire_ohlcv_daily_sync` callback + 실패율 10% 임계 alert
- `app/scheduler.py` (확장) — `OhlcvDailyScheduler` + `OHLCV_DAILY_SYNC_JOB_ID`
- `app/adapter/web/_deps.py` (확장) — `IngestDailyOhlcvUseCaseFactory` + get/set/reset
- `app/adapter/out/persistence/repositories/stock_price.py` (확장) — `find_range(stock_id, *, exchange, start, end)`
- `app/config/settings.py` (수정) — nxt_collection_enabled 디폴트 **False** + `scheduler_ohlcv_daily_sync_alias` 추가
- `app/main.py` (수정) — `_ingest_ohlcv_factory` 등록 + `OhlcvDailyScheduler` 통합 + `ohlcv_router` 포함

**신규 테스트 5 파일 / 55 cases**
- `tests/test_ingest_daily_ohlcv_service.py` (21 — 16 신규 + 5 회귀)
- `tests/test_stock_price_repository_find_range.py` (6)
- `tests/test_ohlcv_router.py` (16 — 15 신규 + 1 회귀)
- `tests/test_ohlcv_daily_scheduler.py` (9 — 5 신규 + 4 콜백 회귀)
- `tests/test_ohlcv_daily_deps.py` (4)

**기존 테스트 회귀 픽스 4 cases**
- test_settings (nxt 디폴트 False 반영)
- test_scheduler / test_stock_master_scheduler — `SCHEDULER_OHLCV_DAILY_SYNC_ALIAS` env 추가

**1R 적대적 이중 리뷰 fix 매핑**
| ID | 발견 | 적용 |
|---|------|------|
| 2a-M1 / 2b-L3 | refresh_one NXT 격리 부재 | KRX raise propagate, NXT try/except → errors 격리 |
| 2a-M2 | refresh_one KRX KiwoomError propagate 테스트 누락 | 신규 테스트 |
| 2a-M3 | fire_ohlcv_daily_sync 콜백 테스트 누락 | 4 cases 추가 |
| 2b-M1 | GET range 무제한 DoS amplification | `GET_RANGE_MAX_DAYS=400` 가드 + 회귀 |
| 2b-M2 | only_market_codes 화이트리스트 부재 | `_validate_market_codes` |
| 2b-M3 | docstring vs 코드 불일치 (`_safe_for_log`) | docstring 정정 |

**문서**
- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 17 (C-1β 결정 + 1R 매핑 + Defer 6 + 다음 chunk)
- `CHANGELOG.md` prepend (이번 세션)

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | **Phase C-2 (ka10086 일별 보강)** | pending | 투자자별 + 외인 + 신용 — 백테스팅 시그널 핵심 (P0). 별도 endpoint path (`/api/dostk/mrkcond`) |
| 2 | 운영 dry-run | pending | 키움 자격증명으로 α/β/A3/B-α/β/γ + C-1α/β 통합 검증 — turnover_rate magnitude 분포, NXT 운영 토글 검증, fail-fast alias 검증 |
| 3 | Phase C-3 (ka10082/83 주봉/월봉, P1) | pending | 같은 chart endpoint, KiwoomChartClient 메서드 추가 |
| 4 | Phase D~G | pending | 시그널 백테스팅 / 결과 / 운영 |

## Key Decisions Made (이번 세션)

- **nxt_collection_enabled 디폴트 OFF** — settings flag, 운영 전환 전 안전판. 이중 게이팅 (`settings AND stock.nxt_enable`) — 실수 활성화 차단
- **target_date_range = today - 365 ~ today** — admin /sync 호출 base_date 1년 cap. 백필 1095일과 분리 (백필은 별도 admin 작업)
- **Cron = KST mon-fri 18:30** — fundamental 18:00 의 30분 후, master(17:30) 까지 직렬화. 시계열 적재 가장 마지막 단계
- **per-(stock, exchange) 격리** — KRX 실패가 NXT 호출 막지 않음, 한 종목 실패가 다른 종목 막지 않음
- **refresh_one KRX raise / NXT 격리** — KRX 실패는 admin 즉시 인지 (4xx/5xx), NXT 실패는 응답 200 + errors[NXT] (KRX 이미 적재됨)
- **only_market_codes 화이트리스트** — StockListMarketType.value cross-check, silent no-op 차단
- **GET range cap = 400일** — DoS amplification 차단. 1년 sync 범위 + 안전 마진
- **GET 라우터 admin guard 미적용** — DB-only 공개, internet-facing 배포 시 Phase D 결정

## Known Issues

- **GET 라우터 익명 공개** (LOW) — Phase D internet-facing 배포 시 admin guard 또는 별도 정책 결정
- **date.today() vs `datetime.now(KST).date()`** (2b-L1) — 컨테이너 TZ=UTC 면 KST 자정~09:00 사이 admin 호출이 어제 날짜로 동작. cron 영향 없음
- **C-1α 상속 알려진 이슈** — NUMERIC(8,4) magnitude 가드 / list 길이 cap / `_MODEL_BY_EXCHANGE` MappingProxyType / chart.py private import / 응답 stk_cd 빈 string strict 전환 — 운영 dry-run 후 결정
- **B-γ-2 알려진 이슈 상속** — target_date 무한 / errors list 무제한 / GET /latest 익명 공개 / `_safe_for_log` charset 부분 커버 / vendor non-numeric metric

## Context for Next Session

### 사용자의 원래 의도 / 목표
backend_kiwoom Phase C-1 (백테스팅 OHLCV 본체) 완성. 다음은 Phase C-2 (ka10086 시그널 핵심) 또는 운영 dry-run.

### 선택된 접근 + 이유
- **chunk 분할 + ted-run 풀 파이프라인**: B-γ-1/2, C-1α/β 패턴 일관. 인프라/자동화 분리로 적대적 리뷰 부담 감소 + 회귀 차단
- **B-α/β/γ 패턴 mechanical 차용**: per-stock try/except + factory 싱글톤 + lifespan reset_*_factory. Scheduler 도 동일 패턴
- **2R 적대적 리뷰 (--force-2b)**: 본 chunk 는 1R PASS — 이전 chunk 학습 효과로 적대적 발견이 5건 모두 MEDIUM (HIGH 0)
- **Quality-First** (장애 없이 / 정확한 구조로 / 확장 가능)

### 사용자 제약 / 선호
- 한글 커밋 메시지 (~/.claude/CLAUDE.md 글로벌 규칙)
- 푸시는 명시적 요청 시만 (커밋과 분리)
- 큰 Phase 는 chunk 분할 후 ted-run 풀 파이프라인 (메모리)
- 진행 상황 가시화 — 체크리스트 + 한 줄 현황

### 다음 세션 진입 시 결정 필요
사용자에게 옵션 확인 권장:
1. **Phase C-2 (ka10086 일별 보강 — 투자자별/외인/신용)** — 백테스팅 시그널 핵심 (P0). 별도 endpoint (`/api/dostk/mrkcond`)
2. **운영 dry-run** — α/β/A3/B-α/β/γ + C-1α/β 통합 검증. turnover_rate magnitude 분포 + NXT 토글 + fail-fast 검증
3. **Phase C-3 (ka10082/83 주봉/월봉, P1)** — 같은 chart endpoint, KiwoomChartClient 메서드 추가

## Files Modified This Session

이번 세션 한정 (커밋 대기):
```
docs/ADR/ADR-0001-backend-kiwoom-foundation.md     | § 17 추가
CHANGELOG.md                                        | prepend (C-1β)
HANDOFF.md                                          | 전체 갱신
src/backend_kiwoom/app/application/service/ohlcv_daily_service.py            (신규)
src/backend_kiwoom/app/adapter/web/routers/ohlcv.py                          (신규)
src/backend_kiwoom/app/batch/ohlcv_daily_job.py                              (신규)
src/backend_kiwoom/app/scheduler.py                                          (확장)
src/backend_kiwoom/app/adapter/web/_deps.py                                  (확장)
src/backend_kiwoom/app/adapter/out/persistence/repositories/stock_price.py   (확장 — find_range)
src/backend_kiwoom/app/config/settings.py                                    (수정)
src/backend_kiwoom/app/main.py                                               (수정)
src/backend_kiwoom/tests/test_ingest_daily_ohlcv_service.py                  (신규, 21 cases)
src/backend_kiwoom/tests/test_stock_price_repository_find_range.py           (신규, 6 cases)
src/backend_kiwoom/tests/test_ohlcv_router.py                                (신규, 16 cases)
src/backend_kiwoom/tests/test_ohlcv_daily_scheduler.py                       (신규, 9 cases)
src/backend_kiwoom/tests/test_ohlcv_daily_deps.py                            (신규, 4 cases)
src/backend_kiwoom/tests/test_settings.py                                    (회귀, nxt 디폴트)
src/backend_kiwoom/tests/test_scheduler.py                                   (회귀, env)
src/backend_kiwoom/tests/test_stock_master_scheduler.py                      (회귀, env)
```

16 files changed (코드 8 + 테스트 5 신규 + 테스트 3 회귀 + 문서 3).
