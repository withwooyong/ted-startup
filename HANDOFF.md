# Session Handoff

> Last updated: 2026-05-08 (KST) — **backend_kiwoom A1 ~ A3-γ + F1 + B-α 완료 — 누적 9 PR**
> Branch: `master` (working tree clean — 모든 커밋 + 푸시 완료)
> Latest commit: `bf9956a` — feat(kiwoom): Phase B-α — ka10099 종목 마스터 + StockMasterScheduler (이중 리뷰 1R, 443 tests / 93.38%)
> 이전 마일스톤: `52c807b` — feat(kiwoom) Phase A3-γ APScheduler weekly cron + lifespan 통합
> 세션 시작점: `52c807b` — A3-γ 직후 (이전 세션 마지막)

## Current Status

backend_kiwoom **Phase A 인증·트랜스포트·sector 100% + Phase B-α (ka10099 종목 마스터) 완료**. 백테스팅 진입점 인프라가 갖춰졌으며, 다음은 **운영 dry-run** (DoD §10.3) 또는 **Phase B-β (ka10100)**.

| 단계 | 커밋 | 범위 |
|------|------|------|
| A1 기반 인프라 | `12f46aa` | Settings + Fernet Cipher + structlog 마스킹 + Migration 001 + KiwoomCredentialRepository |
| 보안 사전 PR | `265b720` | ADR-0001 § 3 #1·#2·#3 적용 (정규식 보강 + 직렬화 차단 + scrub helper) |
| A2-α 토큰 발급 | `115fcce` | KiwoomAuthClient.issue_token + IssueUseCase + TokenManager + POST /tokens (admin) + FastAPI 진입점 |
| A2-β 토큰 폐기 + lifespan | `0ea955c` | KiwoomAuthClient.revoke_token + RevokeUseCase + TokenManager 확장 + DELETE/revoke-raw + lifespan graceful shutdown + RequestValidationError 핸들러 |
| A3-α 공통 트랜스포트 + ka10101 | `cce855c` | KiwoomClient (모든 후속 endpoint 의 기반) + KiwoomStkInfoClient.fetch_sectors |
| F1 auth `__context__` 백포트 | `035a68e` | 9개 raise site 변수 캡처 + 회귀 테스트 8 |
| A3-β sector 도메인 영속화 | `6cd4371` | Migration 002 + Sector ORM/Repository + SyncSectorMasterUseCase + GET/POST 라우터 + F3 통합 |
| A3-γ APScheduler weekly cron | `52c807b` | SectorSyncScheduler (일 03:00 KST) + lifespan 통합 (fail-fast + shutdown 순서) |
| **B-α ka10099 종목 마스터** | **`bf9956a`** (이번 세션) | StockListMarketType StrEnum 16종 + KiwoomStkInfoClient.fetch_stock_list + Stock ORM/Repository + SyncStockMasterUseCase + GET/POST `/api/kiwoom/stocks` + StockMasterScheduler (KST mon-fri 17:30) + Migration 003 + sector M-2 백포트 |

**누적 결과**: **443 tests passed / coverage 93.38%** / 적대적 이중 리뷰 누적 CRITICAL 4 + HIGH 16 발견 → 전부 적용 → 0건 PASS.

## Completed This Session

### Phase B-α — ka10099 종목 마스터 + StockMasterScheduler (`bf9956a`)

- 자동 분류: **계약 변경 (contract)** + `--force-2b` 적대적 리뷰 강제
- 1R: HIGH 2 + MEDIUM 5 + LOW 5 → 전부 적용 후 2R PASS

**신규 파일 (7 코드 + 7 테스트 + 1 마이그레이션)**
- `app/application/constants.py` — `StockListMarketType` StrEnum 16종 + `STOCK_SYNC_DEFAULT_MARKETS` (5종)
- `app/adapter/out/persistence/models/stock.py` — Stock ORM (UNIQUE stock_code 단일키)
- `app/adapter/out/persistence/repositories/stock.py` — list_by_filters / list_nxt_enabled / find_by_code / upsert_many / deactivate_missing
- `app/application/service/stock_master_service.py` — SyncStockMasterUseCase (5 시장 격리 + 빈 응답 보호 + mock_env 안전판)
- `app/adapter/web/routers/stocks.py` — GET `/stocks` + GET `/stocks/nxt-eligible` + POST `/stocks/sync?alias=` (admin)
- `app/batch/stock_master_job.py` — fire_stock_master_sync 콜백
- `migrations/versions/003_kiwoom_stock.py` — kiwoom.stock 테이블 + 4 인덱스
- `tests/test_kiwoom_stkinfo_stock_list.py` (36), `test_stock_repository.py` (17), `test_stock_master_service.py` (14), `test_stock_router.py` (12), `test_stock_router_integration.py` (1), `test_migration_003.py` (7), `test_stock_master_scheduler.py` (11)

**확장 파일**
- `app/adapter/out/kiwoom/stkinfo.py` — fetch_stock_list + StockListRow + NormalizedStock + StockListResponse + StockListRequest + _parse_yyyymmdd + _parse_zero_padded_int
- `app/adapter/web/_deps.py` — SyncStockMasterUseCaseFactory 싱글톤
- `app/config/settings.py` — scheduler_stock_sync_alias (fail-fast 가드 추가)
- `app/main.py` — lifespan stock factory + StockMasterScheduler 통합 (graceful shutdown: stock → sector → revoke → dispose)
- `app/scheduler.py` — StockMasterScheduler (KST mon-fri 17:30, sector scheduler 와 lifecycle 분리)
- `app/application/service/sector_service.py` — outcome.error 클래스명 only 백포트 (1R M-2)
- `tests/test_scheduler.py` — stock alias env 추가 (회귀 fix)

**문서**
- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 12 (10 결정 + dry-run 항목)
- `docs/research/kiwoom-rest-feasibility.md` § 10.5 진행 상태 표 + § 10.6 다음 작업 갱신
- `CHANGELOG.md` prepend (이번 세션 항목)

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | 운영 dry-run (DoD §10.3) | pending | 키움 자격증명 1쌍으로 α/β/A3/B-α 전체 검증 — 응답 marketCode 분포·NXT 비율·페이지네이션 마진 |
| 2 | Phase B-β (ka10100 종목 정보 리스트) | pending | gap-filler 단건 보강 — NormalizedStock 변환 로직 공유 (917 → 673 줄 계획서) |
| 3 | Phase B-γ (ka10001 주식 기본 정보) | pending | 펀더멘털 보강 (1,164 줄 계획서) — Phase B 마무리 |
| 4 | Phase C~G | pending | OHLCV 백테스팅 본체 + 시그널 보강 + 순위 + 투자자별 (Phase B 완료 후) |

## Key Decisions Made (이번 세션)

- **StockListMarketType StrEnum 16종**: ka10101 의 `0/1/2/4/7` 와 mrkt_tp 의미 완전히 다름 (master.md § 12). Literal 16 case 길어서 StrEnum 채택. 디폴트 sync 5종 (KOSPI 0 / KOSDAQ 10 / KONEX 50 / ETN 60 / REIT 6).
- **`UNIQUE(stock_code)` 단일키** (sector 의 복합키와 차이): 한 종목이 여러 시장에 등장하면 ON CONFLICT UPDATE — 운영 dry-run 후 정책 재검토 (§11.1 #2).
- **`to_normalized.market_code = requested_market_code`** (1R H1): 응답 marketCode 영속화 안 함 → cross-market zombie row 방지 + sector 패턴 일관 + deactivate_missing 격리 보장. 응답 marketCode 분포는 운영 dry-run 시 별도 logger 로 추적.
- **mock_env 가 lifespan 1회 결정** (1R H-1): 프로세스당 단일 env 운영 가정. 향후 멀티 env 동시 운영 시 alias 단위 결정으로 변경 필요. ADR 주석 명시.
- **state VARCHAR(255)** (sector 의 100보다 길게, 1R M-1): 키움 다중값 (`"증거금20%|담보대출|..."`) 안전 마진. 길이 초과로 인한 시장 전체 적재 실패 방지.
- **outcome.error 클래스명 only** (1R M-2, sector + stock 둘 다): 응답 본문 echo 차단 (admin 노출 시 키움 본문 누설 방어). 메시지는 logger 경로로만.
- **빈 응답 deactivate skip** (§5.3): KOSPI 빈 응답으로 모든 KOSPI 종목 비활성화 사고 방지.
- **StockMasterScheduler 별도 클래스** (sector scheduler 와 lifecycle 분리): KST mon-fri 17:30 (장 마감 후) — sector 의 일 03:00 와 다른 cron. 같은 패턴, 별도 AsyncIOScheduler.

## Known Issues

- **응답 `marketCode` ↔ 요청 `mrkt_tp` 불일치 가능성** (§11.2): Excel 샘플에서 mrkt_tp="0" 요청에 marketCode="10" 응답 — 현재 H1 fix 로 응답 marketCode 영속화 안 하므로 운영 영향 없음. 단 운영 dry-run 시 분포 확인 필요 (logger 추가 검토).
- **UNIQUE(stock_code) cross-market overwrite** (§11.1 #2): 한 종목이 여러 시장에 등장하면 두 번째 sync 가 market_code 덮어씀. 운영 dry-run 후 별도 row 분리 정책 재검토.
- **max_pages=100 cap의 페이지 사이즈 의존**: KOSPI ~900~1000 / KOSDAQ ~1500~1700 추정. 키움이 페이지 사이즈 축소하면 cap 부족 가능. F3 hint Retry-After 헤더로 모니터링.
- **mock_env 멀티 env 시나리오**: 한 프로세스가 mock + prod alias 혼용 시 mock_env 가 lifespan 1회 결정으로 부정확. 현재는 운영 가정으로 차단, 향후 alias 단위 env 결정 필요.

## Context for Next Session

### 사용자의 원래 의도 / 목표
backend_kiwoom Phase A 의 인증·트랜스포트 인프라를 검증한 뒤, 백테스팅 본체 진입점인 종목 마스터(Phase B)를 단계별로 chunk 분할하여 진행. 이번 세션에서 B-α (ka10099 종목 마스터) 완료. 다음은 운영 dry-run 또는 B-β/γ 진입.

### 선택된 접근 + 이유
- **chunk 분할**: 작업계획서 1,500줄 초과 시 chunk 분할 합의 (메모리 `feedback_chunk_split_for_pipelines.md`). Phase B 2,754줄을 endpoint 별 3-chunk (B-α/β/γ) 로 분할.
- **sector 패턴 mechanical 차용**: ka10101 (sector) 와 ka10099 (stock) 이 같은 KiwoomStkInfoClient 어댑터를 공유, sector 의 Repository/UseCase/Factory/Scheduler/main lifespan 패턴을 그대로 복제하면서 stock 특이사항 (zero-padded 정규화, nxt_enable, 14필드 응답, mock 안전판) 만 반영.
- **/ted-run Quality-First 풀 파이프라인**: 비용 무관, 정확성 우선. Step 0 TDD → Step 1 구현 → Step 2 이중 리뷰 (계약 변경 분류이지만 admin/cron 영향으로 `--force-2b` 강제) → Step 3 Verification (lint/type/test/coverage) → Step 5 ADR + 커밋.
- **TDD red 단계 단축**: sector 패턴 mechanical 복제이므로 stub 단계와 implementation 단계 합침. 테스트 작성 후 green 확인으로 의도 명시화 + 회귀 방어.

### 사용자 제약 / 선호
- 한글 커밋 메시지 (~/.claude/CLAUDE.md 글로벌 규칙)
- 푸시는 명시적 요청 시만 (커밋과 분리, 글로벌 CLAUDE.md 규칙)
- 큰 Phase 는 chunk 분할 후 ted-run 풀 파이프라인 (메모리 `feedback_chunk_split_for_pipelines.md`)
- 진행 상황 가시화 — 체크리스트 + 한 줄 현황 (메모리 `feedback_progress_visibility.md`)

### 다음 세션 진입 시 결정 필요
사용자에게 옵션 확인 권장:
1. **운영 dry-run 먼저** — 키움 자격증명 1쌍으로 α/β/A3/B-α 통합 검증. 응답 marketCode 분포·NXT 비율·페이지네이션 마진 확인. 사용자가 KIWOOM_PROD_APPKEY/SECRETKEY 보유 여부 + 운영 환경 가용성 확인 필요.
2. **Phase B-β (ka10100) 직진** — gap-filler 단건 보강 어댑터. 계획서 673줄 (B-α 의 917줄보다 작음). NormalizedStock 변환 로직 재사용. /ted-run 풀 파이프라인.
3. **Phase B-α 후속 follow-up** (선택사항) — 응답 marketCode 분포 logger 추가, alias 별 mock_env 결정 (TokenManager 자격증명 row env 노출 패턴 검토).

## Files Modified This Session

이번 세션 한정 (커밋 `bf9956a` 기준):
```
docs/ADR/ADR-0001-backend-kiwoom-foundation.md     | § 12 추가
docs/research/kiwoom-rest-feasibility.md           | § 10.5 / 10.6 갱신
src/backend_kiwoom/app/adapter/out/kiwoom/stkinfo.py
src/backend_kiwoom/app/adapter/out/persistence/models/__init__.py
src/backend_kiwoom/app/adapter/out/persistence/models/stock.py        (신규)
src/backend_kiwoom/app/adapter/out/persistence/repositories/stock.py  (신규)
src/backend_kiwoom/app/adapter/web/_deps.py
src/backend_kiwoom/app/adapter/web/routers/stocks.py                  (신규)
src/backend_kiwoom/app/application/constants.py                       (신규)
src/backend_kiwoom/app/application/service/sector_service.py          (M-2 백포트)
src/backend_kiwoom/app/application/service/stock_master_service.py    (신규)
src/backend_kiwoom/app/batch/stock_master_job.py                      (신규)
src/backend_kiwoom/app/config/settings.py
src/backend_kiwoom/app/main.py
src/backend_kiwoom/app/scheduler.py                                   (StockMasterScheduler 추가)
src/backend_kiwoom/migrations/versions/003_kiwoom_stock.py            (신규)
src/backend_kiwoom/tests/test_kiwoom_stkinfo_stock_list.py            (신규, 36 tests)
src/backend_kiwoom/tests/test_migration_003.py                        (신규, 7 tests)
src/backend_kiwoom/tests/test_scheduler.py                            (stock alias env 추가)
src/backend_kiwoom/tests/test_stock_master_scheduler.py               (신규, 11 tests)
src/backend_kiwoom/tests/test_stock_master_service.py                 (신규, 14 tests)
src/backend_kiwoom/tests/test_stock_repository.py                     (신규, 17 tests)
src/backend_kiwoom/tests/test_stock_router.py                         (신규, 12 tests)
src/backend_kiwoom/tests/test_stock_router_integration.py             (신규, 1 test)
```

24 files changed, ~3,100 insertions.
