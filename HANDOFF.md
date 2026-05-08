# Session Handoff

> Last updated: 2026-05-08 (KST) — **backend_kiwoom A1 ~ A3-γ + F1 + B-α + B-β + B-γ-1 + B-γ-2 완료 — Phase B 마무리, 누적 12 chunk, 커밋 대기**
> Branch: `master` (uncommitted — Step 5 커밋 진행 예정)
> 이전 마일스톤: `a287172` — Phase B-γ-1 ka10001 펀더멘털 인프라
> 세션 시작점: `a287172` 직후 (이번 세션 B-γ-1 푸시 후)

## Current Status

backend_kiwoom **Phase A 100% + B-α + B-β + B-γ-1 + B-γ-2 완료 — Phase B 100%**. 백테스팅 진입점에 종목 마스터 + 펀더멘털 (PER/EPS/ROE/PBR/EV/BPS + 시총/외인/250일통계/일중시세 45 필드) 일별 적재 + 자동화 (KST 18:00 cron + admin sync/refresh + GET latest) 모두 완료. 다음은 **Phase C (OHLCV 백테스팅 본체)** 또는 **운영 dry-run** (단, lazy fetch RPS 보호 결정 선행 필수).

| 단계 | 커밋 | 범위 |
|------|------|------|
| A1 기반 인프라 | `12f46aa` | Settings + Fernet Cipher + structlog 마스킹 + Migration 001 + KiwoomCredentialRepository |
| 보안 사전 PR | `265b720` | ADR-0001 § 3 #1·#2·#3 적용 |
| A2-α 토큰 발급 | `115fcce` | KiwoomAuthClient.issue_token + IssueUseCase + TokenManager + POST /tokens (admin) |
| A2-β 토큰 폐기 + lifespan | `0ea955c` | revoke_token + RevokeUseCase + lifespan graceful shutdown |
| A3-α 공통 트랜스포트 + ka10101 | `cce855c` | KiwoomClient + KiwoomStkInfoClient.fetch_sectors |
| F1 auth `__context__` 백포트 | `035a68e` | 9개 raise site 변수 캡처 + 회귀 8 |
| A3-β sector 도메인 영속화 | `6cd4371` | Migration 002 + Sector ORM/Repository + SyncSectorMasterUseCase + 라우터 |
| A3-γ APScheduler weekly cron | `52c807b` | SectorSyncScheduler + lifespan 통합 |
| B-α ka10099 종목 마스터 | `bf9956a` | ka10099 어댑터 + Stock ORM/Repository + SyncStockMasterUseCase + 라우터 + StockMasterScheduler + Migration 003 |
| B-β ka10100 단건 조회 | `abce7e0` | StockLookupResponse + lookup_stock + upsert_one + LookupStockUseCase + GET/POST `/api/kiwoom/stocks/{stock_code}` + lifespan factory |
| B-γ-1 ka10001 펀더멘털 인프라 | `a287172` | Migration 004 + StockFundamental ORM + StockFundamentalRepository + KiwoomStkInfoClient.fetch_basic_info + StockBasicInfoResponse 45 필드 |
| **B-γ-2 ka10001 펀더멘털 자동화** | **(이번 세션)** | SyncStockFundamentalUseCase (execute + refresh_one) + 라우터 (sync/refresh/latest) + StockFundamentalScheduler (KST 18:00) + Lifespan factory + 2R H-1 lifespan fail-fast cleanup 우회 차단 + 2R M-1 log injection 방어 |

**누적 결과**: **589 tests passed / coverage 93.24%** / 적대적 이중 리뷰 누적 CRITICAL 6 + HIGH 25 발견 → 전부 적용 → 0건 PASS. **Phase B 마무리**.

## Completed This Session

### Phase B-γ-2 — ka10001 펀더멘털 자동화 (UseCase + Router + Scheduler + Lifespan)

- 자동 분류: **계약 변경 (contract)** + `--force-2b` 적대적 리뷰 강제
- 1R: HIGH 1 + MEDIUM 4 + LOW 3 → 2R 5개 적용 + 회귀 테스트 5 → 2R PASS + ruff 후속 정정
- 사용자 결정: **Partial-failure (a) per-stock skip + counter** / **ensure_exists 미사용**

**확장/신규 파일 (코드 7 + 테스트 4 + 테스트 2 갱신)**

- `app/application/service/stock_fundamental_service.py` (신규) — SyncStockFundamentalUseCase + `_safe_for_log` (2R M-1) + Result/Outcome dataclass
- `app/adapter/web/routers/fundamentals.py` (신규) — POST sync (admin) + POST refresh (admin) + GET latest + 6 KiwoomError 매핑
- `app/batch/stock_fundamental_job.py` (신규) — fire callback + 10% 임계 alert
- `app/scheduler.py` (확장) — StockFundamentalScheduler + STOCK_FUNDAMENTAL_SYNC_JOB_ID 상수
- `app/adapter/web/_deps.py` (확장) — SyncStockFundamentalUseCaseFactory + 3 함수 + reset_token_manager 일괄 unset
- `app/main.py` (확장) — lifespan factory + scheduler + router 등록 + **2R H-1 fail-fast 위치 이동** (set 호출 앞)
- `app/config/settings.py` (확장) — scheduler_fundamental_sync_alias

**신규 테스트 4 파일 / 39 cases**
- `tests/test_stock_fundamental_service.py` (16) — UseCase + per-stock skip + mismatch + 2R 회귀 3
- `tests/test_fundamental_router.py` (14) — _make_app + dependency_overrides 패턴 + KiwoomError 매핑
- `tests/test_stock_fundamental_scheduler.py` (5) — KST 18:00 cron + 멱등성
- `tests/test_stock_fundamental_deps.py` (4) — factory get/set/reset

**기존 테스트 2 갱신**
- `tests/test_scheduler.py` + `tests/test_stock_master_scheduler.py` — SCHEDULER_FUNDAMENTAL_SYNC_ALIAS env + fail-fast pattern 갱신

**문서**
- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 15 (B-γ-2 결정 + 1R/2R 매핑 + Phase B 회고 + Defer 8 + Phase C 진입 결정)
- `CHANGELOG.md` prepend (이번 세션)

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | **Phase C 진입 + lazy fetch RPS 보호 결정** | pending | OHLCV 시계열 + 백테스팅 본체. ADR § 13.4.1 옵션 (a) lifespan 싱글톤 / (b) in-flight cache / (c) batch fail-closed |
| 2 | 운영 dry-run (DoD §10.3 + ADR §13.4.3 + §14.5) | pending | 키움 자격증명으로 α/β/A3/B-α/B-β/B-γ-1/B-γ-2 통합 검증 — ka10001 응답 45 필드 + 외부 벤더 PER/EPS/ROE 빈값 종목 + 부분 실패 임계 |
| 3 | Phase D~G | pending | 시그널 백테스팅 / 결과 / 운영 |

## Key Decisions Made (이번 세션)

- **chunk 분할 — B-γ-2 단일 진행** (~450줄 추정, 실제 더 큰 chunk 였으나 단일 ted-run 완수)
- **Partial-failure 정책 (a) per-stock skip + counter** — multi-stock loop 의 한 종목 실패가 다른 종목 적재를 막지 않음 (B-α SyncStockMasterUseCase 패턴 일관). ADR § 14.6 / 2R C-M3 해소
- **ensure_exists 미사용** — active stock 만 대상. 신규 상장 종목은 다음날 ka10099 sync 에서 자동 등장 (KISS + RPS 보존)
- **cron KST mon-fri 18:00** — ka10099 stock master 17:30 의 30분 후, master 갱신 완료 후 active stock 조회 보장
- **단일 SyncStockFundamentalUseCase + factory 1개** — execute + refresh_one 두 메서드. B-β LookupStockUseCase 의 execute + ensure_exists 분리와 다름 (본 chunk 는 ROI 약함)
- **2R H-1 — lifespan fail-fast cleanup 우회 차단** — alias 미설정 검증을 set_*_factory 호출 **앞으로** 이동. cleanup (reset_*_factory + revoke + engine.dispose) 우회 차단. 새 message: list 형식
- **2R M-1 — `_safe_for_log` log injection 방어** — vendor 응답 stk_nm 의 control char (\\r\\n\\t\\x00\\x1b) strip + 길이 cap. mismatch alert sink (Sentry/CloudWatch) 의 line 분리 / 색상 spoof 차단
- **failure_ratio > 0.10 임계** — fire callback 의 logger.error 알람 트리거 (작업계획서 § 11.1 #7 디폴트, 운영 1주 모니터 후 조정)

## Known Issues

- **Phase C lazy fetch RPS 폭주 결정 미정** (1R 2b-M1 deferred from B-β, ADR § 13.4.1)
- **target_date 무한 허용** (2R M-2 defer) — backfill 시 미래/과거 일자 데이터 오염 위험. 운영 1주 후 lower/upper bound 결정
- **errors list 무제한** (2R M-3 defer) — 3000 종목 모두 실패 시 response/log 폭주. errors[:200] cap + 카운터 패턴 검토
- **GET /latest 익명 공개 정책** (2R M-4 defer) — 펀더멘털 공시 데이터지만 OTC/제재 종목 노출 우려. admin 가드 또는 user OAuth 결정 필요
- **`_safe_for_log` charset 부분 커버** (2R LOW-1) — DEL/CSI 8-bit/RTL/LSEP 미차단. 후속 chunk 화이트리스트 전환 검토
- **vendor non-numeric metric 부재** (B-γ-1 2R B-M1 defer) — `_to_int`/`_to_decimal` None path silent
- **단위 모호** (계획서 § 11.2) — mac/cap/listed_shares 단위 운영 검증 후 컬럼 주석 명시
- **B-α/B-β 알려진 위험 상속** — UNIQUE(stock_code) cross-market overwrite, max_pages=100 cap

## Context for Next Session

### 사용자의 원래 의도 / 목표
backend_kiwoom Phase A 인증·트랜스포트 + Phase B 종목 마스터·펀더멘털 chunk 분할 진행. **Phase B 마무리** — 백테스팅 진입점 모든 데이터 인프라 + 자동화 완료. 다음은 Phase C OHLCV 본체 또는 운영 dry-run.

### 선택된 접근 + 이유
- **chunk 분할 + ted-run 풀 파이프라인**: B-γ 1,164줄 → B-γ-1 인프라 (700줄) + B-γ-2 자동화 (~700줄, 실제 단일 chunk 완수). 메모리 `feedback_chunk_split_for_pipelines.md` 일관
- **B-α/B-β/B-γ-1 패턴 mechanical 차용**: SyncStockMasterUseCase per-market loop → 종목 단위 변형, StockMasterScheduler → StockFundamentalScheduler 동일 패턴, B-α/B-β/B-γ-1 의 모든 보안 가드 (응답 message echo / __context__ / Pydantic max_length / BIGINT/NaN 등) 본 chunk 에 자동 적용
- **2R 적대적 리뷰 (--force-2b)**: 모든 chunk 일관 적용. 본 chunk 는 H-1 (lifespan teardown 우회) + M-1 (log injection) 발견 → 즉시 fix
- **Quality-First** (장애 없이 / 정확한 구조로 / 확장 가능)

### 사용자 제약 / 선호
- 한글 커밋 메시지 (~/.claude/CLAUDE.md 글로벌 규칙)
- 푸시는 명시적 요청 시만 (커밋과 분리, 글로벌 CLAUDE.md 규칙)
- 큰 Phase 는 chunk 분할 후 ted-run 풀 파이프라인 (메모리)
- 진행 상황 가시화 — 체크리스트 + 한 줄 현황

### 다음 세션 진입 시 결정 필요
사용자에게 옵션 확인 권장:
1. **Phase C 진입 + lazy fetch RPS 보호 결정** (1R 2b-M1) — OHLCV 백테스팅 본체. 진입 전 RPS 우회 차단 옵션 결정 필수 (ADR § 13.4.1)
2. **운영 dry-run** — 키움 자격증명으로 α/β/A3/B-α/B-β/B-γ-1/B-γ-2 통합 검증. ka10001 응답 45 필드 + 외부 벤더 PER/EPS/ROE 빈값 종목 + 부분 실패 임계 운영 테스트
3. **Phase B 후속 정리** (운영 검증 / 정책 결정 항목들 반영) — target_date bound, GET /latest 가드, errors cap, charset 화이트리스트 등

## Files Modified This Session

이번 세션 한정 (커밋 대기):
```
docs/ADR/ADR-0001-backend-kiwoom-foundation.md     | § 15 추가
CHANGELOG.md                                        | prepend (B-γ-2)
HANDOFF.md                                          | 전체 갱신
src/backend_kiwoom/app/application/service/stock_fundamental_service.py  (신규)
src/backend_kiwoom/app/adapter/web/routers/fundamentals.py               (신규)
src/backend_kiwoom/app/batch/stock_fundamental_job.py                    (신규)
src/backend_kiwoom/app/scheduler.py                                      (확장 — StockFundamentalScheduler)
src/backend_kiwoom/app/adapter/web/_deps.py                              (확장 — factory)
src/backend_kiwoom/app/main.py                                           (확장 — lifespan + 2R H-1)
src/backend_kiwoom/app/config/settings.py                                (확장)
src/backend_kiwoom/tests/test_stock_fundamental_service.py               (신규, 16 cases)
src/backend_kiwoom/tests/test_fundamental_router.py                      (신규, 14 cases)
src/backend_kiwoom/tests/test_stock_fundamental_scheduler.py             (신규, 5 cases)
src/backend_kiwoom/tests/test_stock_fundamental_deps.py                  (신규, 4 cases)
src/backend_kiwoom/tests/test_scheduler.py                               (수정 — env)
src/backend_kiwoom/tests/test_stock_master_scheduler.py                  (수정 — env + pattern)
```

16 files changed (코드 7 + 테스트 6 + 문서 3).
