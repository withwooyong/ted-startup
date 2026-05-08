# Session Handoff

> Last updated: 2026-05-08 (KST) — **backend_kiwoom A1 ~ A3-γ + F1 + B-α + B-β 완료 — 누적 10 PR, 푸시 반영**
> Branch: `master` (working tree clean — 커밋 + 푸시 완료)
> Latest commit: `abce7e0` — feat(kiwoom): Phase B-β — ka10100 단건 조회 (gap-filler / lazy fetch, 498 tests / 93.73%)
> 이전 마일스톤: `bf9956a` — Phase B-α ka10099 종목 마스터 + StockMasterScheduler
> 세션 시작점: `d51cbb2` — B-α 핸드오프 직후 (이전 세션 마지막)

## Current Status

backend_kiwoom **Phase A 100% + B-α (ka10099 bulk) + B-β (ka10100 단건 gap-filler / lazy fetch) 완료**. 백테스팅 진입점 인프라 + Phase C 의 lazy fetch 안전망까지 구비. 다음은 **운영 dry-run** (DoD §10.3 + ADR § 13.4.3) 또는 **Phase B-γ (ka10001 펀더멘털)** 또는 **Phase C 진입** (단, lazy fetch RPS 보호 결정 선행 필수).

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
| **B-β ka10100 단건 조회** | **`abce7e0`** (이번 세션) | StockLookupResponse + lookup_stock + upsert_one + LookupStockUseCase (execute + ensure_exists) + GET/POST `/api/kiwoom/stocks/{stock_code}` + lifespan factory + teardown reset + 1R 4HIGH 적용 |

**누적 결과**: **498 tests passed / coverage 93.73%** / 적대적 이중 리뷰 누적 CRITICAL 4 + HIGH 20 발견 → 전부 적용 → 0건 PASS.

## Completed This Session

### Phase B-β — ka10100 단건 종목 조회 (`abce7e0`)

- 자동 분류: **계약 변경 (contract)** + `--force-2b` 적대적 리뷰 강제
- 1R: HIGH 4 + MEDIUM 9 + LOW 6 → HIGH 4 + MEDIUM 4 적용 후 2R PASS

**확장 파일 (코드 6 + 테스트 5 신규)**

- `app/adapter/out/kiwoom/stkinfo.py` — `STK_CD_LOOKUP_PATTERN` (단일 정규식 source, ASCII only) + `_validate_stk_cd_for_lookup` + `StockLookupResponse` (14 필드 + return_code/msg + `to_normalized()`) + `StockLookupRequest` + `lookup_stock` 메서드 (flag-then-raise-outside-except 패턴)
- `app/adapter/out/persistence/repositories/stock.py` — `upsert_one(row: NormalizedStock) -> Stock` (RETURNING + populate_existing)
- `app/application/service/stock_master_service.py` — `LookupStockUseCase` (execute + ensure_exists, is_active 체크, ValueError → KiwoomResponseValidationError 매핑)
- `app/adapter/web/_deps.py` — `LookupStockUseCaseFactory` set/get/reset
- `app/adapter/web/routers/stocks.py` — `GET /{stock_code}` (DB only, 404 if missing) + `POST /{stock_code}/refresh?alias=` (admin) + KiwoomError 6 매핑
- `app/main.py` — lifespan `_lookup_stock_factory` + finally 에 `reset_*_factory` 3개 호출

**신규 테스트 5 파일 / 55 케이스**
- `tests/test_kiwoom_stkinfo_lookup.py` (17) — 어댑터 단위
- `tests/test_lookup_stock_service.py` (14) — UseCase 통합 + 1R 회귀 4
- `tests/test_stock_lookup_router.py` (18) — 라우터 + 1R 회귀 2
- `tests/test_stock_repository_upsert_one.py` (5)
- `tests/test_lookup_stock_deps.py` (5)

**문서**
- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 13 (7 결정 + 1R 매핑 + Phase C deferred)
- `docs/research/kiwoom-rest-feasibility.md` § 10.5/10.6 갱신 (B-β 진행 상태 + lazy fetch RPS 결정 추가)
- `CHANGELOG.md` prepend (이번 세션 항목 + 커밋 해시)

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | 운영 dry-run (DoD §10.3 + ADR §13.4.3) | pending | 키움 자격증명 1쌍으로 α/β/A3/B-α/B-β 통합 검증 — ka10100 단건 응답 14 필드 + 존재하지 않는 종목 패턴 + ETF/코스닥 차이 + mock 도메인 응답 |
| 2 | Phase B-γ (ka10001 주식 기본 정보) | pending | 펀더멘털 보강 (1,164 줄 계획서) — chunk 분할 검토 필요. Phase B 마무리 |
| 3 | **Phase C 진입 전 lazy fetch RPS 보호 결정** (1R 2b-M1 deferred) | pending | OHLCV 적재 시 미지 종목 100건 동시 호출 → ka10100 폭주. (a) KiwoomClient lifespan 싱글톤 / (b) stock_code 단위 in-flight cache / (c) batch 후 fail-closed |
| 4 | Phase C~G | pending | OHLCV 백테스팅 본체 |

## Key Decisions Made (이번 세션)

- **`ensure_exists` 의 두 진입점 분리** — `execute` (admin POST refresh) 와 `ensure_exists` (internal lazy fetch). HTTP `GET /{stock_code}` 는 DB only — auto_lookup 외부 query 미노출 (alias 모호성 + 운영 수단 부적합).
- **`upsert_one` 가 RETURNING + populate_existing** — caller 가 즉시 갱신된 Stock(.id, .fetched_at) 받도록. session identity map stale 방어 위해 execution_options 명시.
- **단건 `to_normalized()` 시그니처** — `requested_market_code` 인자 없음 (응답 marketCode 가 권위 source). B-α 의 페이지 응답 to_normalized 와 의미 차이 명시.
- **`STK_CD_LOOKUP_PATTERN = r"^[0-9]{6}$"` 단일 source — ASCII only**: 어댑터 validator + Pydantic Request + 라우터 Path 세 곳 동일 상수 참조. unicode digit 차단 (1R 2a-H1 정정).
- **B-α M-2 정책 백포트** (1R 2b-H1): `KiwoomBusinessError.message` admin 응답 echo 차단. detail 에 `return_code` + `error="KiwoomBusinessError"` 만 — 메시지는 logger 만.
- **flag-then-raise-outside-except 패턴** (1R 2b-H2): raw `ValueError` (정규화 실패) → `KiwoomResponseValidationError` 매핑 시 `__context__` 박힘 차단. B-α `fetch_stock_list` 패턴 일관.
- **lifespan teardown factory unset** (1R 2b-M4): close 후 stale factory 노출 차단 — fail-closed 강화.

## Known Issues

- **lazy fetch RPS 폭주 (Phase C 진입 전 결정)**: `ensure_exists` 의 KiwoomClient 가 factory 단위로 새로 생성 → 글로벌 RPS 보호 우회. Phase C OHLCV 적재가 미지 종목 100건 응답 시 ka10100 100회 동시 호출 위험. ADR § 13.4.1 옵션 (a/b/c) 중 결정 필요.
- **`StockListRow` ↔ `StockLookupResponse` 14 필드 중복** (1R 2a-M1 defer): 두 모델이 같은 14 camelCase 필드 보유. mixin 추출 시 Pydantic ConfigDict 병합 위험으로 defer.
- **`asdict` pop 패턴 중복** (1R 2a-M3 defer): `requested_market_type` 영속화 제외 로직이 `_to_row_dict` (B-α) + `upsert_one` (B-β) 두 곳에 중복. 향후 `to_db_dict` 헬퍼 추출.
- **운영 echo 위험 (sink-side)**: `logger.warning` 의 secret_msg 가 Sentry/CloudWatch 외부 sink 로 흘러갈 가능성 — sink-level scrub 정책 ADR 보강 권고.
- **B-α 의 알려진 위험 그대로 상속**: 응답 `marketCode` ↔ 요청 `mrkt_tp` 불일치 가능성, UNIQUE(stock_code) cross-market overwrite, max_pages=100 cap.

## Context for Next Session

### 사용자의 원래 의도 / 목표
backend_kiwoom Phase A 의 인증·트랜스포트 인프라를 검증한 뒤, 백테스팅 본체 진입점인 종목 마스터(Phase B)를 단계별로 chunk 분할하여 진행. B-α (bulk) + B-β (gap-filler / lazy fetch) 완료. 다음은 운영 dry-run, B-γ (펀더멘털), 또는 Phase C 진입.

### 선택된 접근 + 이유
- **chunk 분할 (메모리 `feedback_chunk_split_for_pipelines.md`)**: B-β (673줄) 가 B-α (917줄) 의 gap-filler 라 NormalizedStock/StockRepository/StockOut 재사용. 작은 chunk 로 안전하게 진행.
- **/ted-run Quality-First 풀 파이프라인**: TDD red → 구현 → 이중 리뷰 (force-2b 적대적) → Verification 5관문 → ADR/CHANGELOG/HANDOFF/한글 커밋. 이번 세션은 사용자 명시 요청 후 푸시도 완료.
- **B-α 패턴 mechanical 차용**: `KiwoomStkInfoClient` 의 새 메서드 (lookup_stock), `StockRepository` 의 새 메서드 (upsert_one), 새 UseCase (LookupStockUseCase), 새 factory (LookupStockUseCaseFactory) — 모두 같은 모듈에 추가하면서 단건 endpoint 특이사항 (ASCII pattern, RETURNING populate_existing, ensure_exists is_active, return_msg echo 차단) 만 반영.

### 사용자 제약 / 선호
- 한글 커밋 메시지 (~/.claude/CLAUDE.md 글로벌 규칙)
- 푸시는 명시적 요청 시만 (커밋과 분리, 글로벌 CLAUDE.md 규칙 — 이번 세션은 "푸시하자" 명시 후 실행)
- 큰 Phase 는 chunk 분할 후 ted-run 풀 파이프라인 (메모리 `feedback_chunk_split_for_pipelines.md`)
- 진행 상황 가시화 — 체크리스트 + 한 줄 현황 (메모리 `feedback_progress_visibility.md`)

### 다음 세션 진입 시 결정 필요
사용자에게 옵션 확인 권장:
1. **운영 dry-run** — 키움 자격증명 1쌍으로 α/β/A3/B-α/B-β 통합 검증. ka10100 단건 응답 14 필드 + 존재하지 않는 종목 응답 패턴 + ETF/코스닥 응답 차이 + mock 도메인 응답 패턴.
2. **Phase B-γ (ka10001 주식 기본 정보)** — 펀더멘털 보강 (1,164 줄 계획서, chunk 분할 검토). Phase B 마무리.
3. **Phase C 진입 + lazy fetch RPS 보호 결정** (1R 2b-M1 deferred) — OHLCV 백테스팅 본체. 진입 전 RPS 우회 차단 옵션 결정 필수 (ADR § 13.4.1).

## Files Modified This Session

이번 세션 한정 (커밋 `abce7e0` 기준 + 사후 docs 갱신):
```
docs/ADR/ADR-0001-backend-kiwoom-foundation.md     | § 13 추가
docs/research/kiwoom-rest-feasibility.md           | § 10.5 / 10.6 갱신 (B-β 반영, 사후)
CHANGELOG.md                                        | prepend (사후 커밋 해시 추가)
HANDOFF.md                                          | 전체 갱신
src/backend_kiwoom/app/adapter/out/kiwoom/stkinfo.py
src/backend_kiwoom/app/adapter/out/persistence/repositories/stock.py
src/backend_kiwoom/app/adapter/web/_deps.py
src/backend_kiwoom/app/adapter/web/routers/stocks.py
src/backend_kiwoom/app/application/service/stock_master_service.py
src/backend_kiwoom/app/main.py
src/backend_kiwoom/tests/test_kiwoom_stkinfo_lookup.py        (신규, 17 cases)
src/backend_kiwoom/tests/test_lookup_stock_service.py         (신규, 14 cases)
src/backend_kiwoom/tests/test_stock_lookup_router.py          (신규, 18 cases)
src/backend_kiwoom/tests/test_stock_repository_upsert_one.py  (신규, 5 cases)
src/backend_kiwoom/tests/test_lookup_stock_deps.py            (신규, 5 cases)
```

19 files changed in `abce7e0` (코드 6 확장 + 테스트 5 신규 + 문서 3 갱신 + 기존 테스트 5 ruff format 적용). 사후 핸드오프 갱신 (CHANGELOG 해시 + research doc 현행화 + HANDOFF) 별도 커밋 예정.
