# Session Handoff

> Last updated: 2026-05-08 (KST) — **backend_kiwoom A1 ~ A3-γ + F1 + B-α + B-β + B-γ-1 완료 — 누적 11 chunk, 커밋 대기**
> Branch: `master` (uncommitted — Step 5 커밋 진행 예정)
> 이전 마일스톤: `abce7e0` — Phase B-β ka10100 단건 gap-filler / lazy fetch
> 세션 시작점: `5985ad0` — B-β 핸드오프 직후 (이전 세션 마지막)

## Current Status

backend_kiwoom **Phase A 100% + B-α (ka10099 bulk) + B-β (ka10100 단건 gap-filler) + B-γ-1 (ka10001 펀더멘털 인프라) 완료**. 백테스팅 진입점에 펀더멘털 (PER/EPS/ROE/PBR/EV/BPS + 시총/외인/250일통계/일중시세 45 필드) 일별 스냅샷 적재 인프라 구비. 다음은 **Phase B-γ-2 (UseCase + Router + Scheduler)** 또는 **운영 dry-run** 또는 **Phase C 진입** (단, lazy fetch RPS 보호 결정 선행 필수).

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
| B-β ka10100 단건 조회 | `abce7e0` | StockLookupResponse + lookup_stock + upsert_one + LookupStockUseCase (execute + ensure_exists) + GET/POST `/api/kiwoom/stocks/{stock_code}` + lifespan factory + teardown reset + 1R 4HIGH 적용 |
| **B-γ-1 ka10001 펀더멘털 인프라** | **(이번 세션)** | Migration 004 + StockFundamental ORM + StockFundamentalRepository + KiwoomStkInfoClient.fetch_basic_info + StockBasicInfoResponse 45 필드 + NormalizedFundamental + normalize_basic_info + 1R 2 CRITICAL + 4 HIGH + 2R 12 적용 + 회귀 16 |

**누적 결과**: **550 tests passed / coverage 94.28%** / 적대적 이중 리뷰 누적 CRITICAL 6 + HIGH 24 발견 → 전부 적용 → 0건 PASS.

## Completed This Session

### Phase B-γ-1 — ka10001 펀더멘털 인프라 chunk

- 자동 분류: **계약 변경 (contract)** + `--force-2b` 적대적 리뷰 강제
- 1R: CRITICAL 2 + HIGH 4 + MEDIUM 5 + LOW 5 → 2R 12 적용 + 회귀 테스트 16 → 2R PASS
- 1,164줄 작업계획서 → B-γ-1 (인프라) + B-γ-2 (UseCase/Router/Scheduler) chunk 분할 (사용자 승인)
- 결정: KRX-only (계획서 § 4.3 (a)) / cron 18:00 KST (B-γ-2 에서 코드화)

**확장/신규 파일 (코드 5 + 테스트 3)**

- `migrations/versions/004_kiwoom_stock_fundamental.py` (신규) — UNIQUE(stock_id, asof_date, exchange) + FK CASCADE + 2 인덱스
- `app/adapter/out/persistence/models/stock_fundamental.py` (신규) — StockFundamental ORM (45 매핑 + CHAR sync)
- `app/adapter/out/persistence/models/__init__.py` (수정) — StockFundamental export
- `app/adapter/out/persistence/repositories/stock_fundamental.py` (신규) — `upsert_one(row, *, stock_id, expected_stock_code=None)` + `find_latest` + `find_by_stock_and_date` + `compute_fundamental_hash` (B-H2 cross-check, B-H3 명시 update_set 46 항목)
- `app/adapter/out/kiwoom/stkinfo.py` (확장) — `_to_int` BIGINT 가드 + `_to_decimal` is_finite/콤마 + `strip_kiwoom_suffix` + `StockBasicInfoRequest/Response` (max_length 강제) + `NormalizedFundamental` + `normalize_basic_info(exchange="KRX")` + `KiwoomStkInfoClient.fetch_basic_info`

**신규 테스트 3 파일 / 55 cases**
- `tests/test_migration_004.py` (8) — 스키마 / UNIQUE / FK CASCADE / 컬럼 타입
- `tests/test_kiwoom_stkinfo_basic_info.py` (33) — 어댑터 + Pydantic + 정규화 + 2R 회귀 14
- `tests/test_stock_fundamental_repository.py` (14) — Repository + 2R 회귀 3

**문서**
- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 14 (B-γ-1 결정 + 2R 매핑 12 + Defer 5)
- `CHANGELOG.md` prepend (이번 세션 항목)

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | **Phase B-γ-2 (UseCase + Router + Scheduler)** | pending | SyncStockFundamentalUseCase + `POST /api/kiwoom/fundamentals/sync` + `POST /stocks/{code}/fundamental/refresh` + StockFundamentalScheduler (KST 18:00 평일). 진입 전 결정: partial-failure 정책 (C-M3) / stock_id resolution invariant / mismatch alert |
| 2 | 운영 dry-run (DoD §10.3 + ADR §13.4.3 + §14.5) | pending | 키움 자격증명 1쌍으로 α/β/A3/B-α/B-β/B-γ-1 통합 검증 — ka10001 응답 45 필드 + 단위 (mac/cap/listed_shares) 검증 + 외부 벤더 PER/EPS/ROE 빈값 종목 패턴 |
| 3 | **Phase C 진입 전 lazy fetch RPS 보호 결정** (1R 2b-M1 deferred) | pending | OHLCV 적재 시 미지 종목 100건 동시 호출 → ka10100 폭주. (a) KiwoomClient lifespan 싱글톤 / (b) stock_code 단위 in-flight cache / (c) batch 후 fail-closed |
| 4 | Phase C~G | pending | OHLCV 백테스팅 본체 |

## Key Decisions Made (이번 세션)

- **chunk 분할 — B-γ-1 (인프라) + B-γ-2 (UseCase/Router/Scheduler)** — 1,164줄 → 두 chunk. B-α (917) + B-β (673) 분할 패턴 일관 (사용자 승인)
- **KRX-only 결정 (계획서 § 4.3 (a))** — `fetch_basic_info(stock_code: str)` 시그니처에 `exchange` 인자 없음 (Phase C 후 결정). NormalizedFundamental.exchange = "KRX" 디폴트, `normalize_basic_info` kwarg 인자화로 BC 보존 (2R C-M4)
- **18:00 KST cron** — ka10099 stock master 직후. is_active stock 조회 시점에 마스터 최신화 보장 (B-γ-2 코드화)
- **stock_id ↔ stock_code invariant 안전망** (2R B-H2) — `upsert_one(expected_stock_code=...)` cross-check. caller 가 `Stock.find_by_code(strip_kiwoom_suffix(stk_cd))` 결과 사용하지 않으면 ValueError. orphaned/cross-link row 차단
- **명시 update_set 46 항목** (2R B-H3) — Stock repository 패턴 일관. NormalizedFundamental 미래 필드 추가 시 silent contract change 방지
- **vendor 입력 보호 가드** (2R A-C1/A-C2/A-H1/A-H4) — `_to_int` BIGINT 경계, `_to_decimal` `is_finite()`, Pydantic 모든 string 필드 max_length 강제. NaN/Infinity/sNaN/거대 string/거대 정수 모두 None 또는 ValidationError
- **fundamental_hash 산출 정책** — PER/EPS/ROE/PBR/EV/BPS 6 필드 MD5. 일중 시세 변경은 hash 영향 없음 (외부 벤더 갱신만 검출). MD5 는 변경 감지 fingerprint, 보안 무결성 아님

## Known Issues

- **lazy fetch RPS 폭주 (Phase C 진입 전 결정)**: B-β 부터 상속. ADR § 13.4.1 옵션 (a/b/c) 중 결정 필요.
- **vendor non-numeric metric 부재** (2R B-M1 defer): `_to_int`/`_to_decimal` 의 None path 진입 시 silent. 운영팀이 vendor 이상 무알림. Phase F monitoring 시 logger.warning + 히스토그램 추가
- **partial-failure 정책 미정** (2R C-M3 defer): B-γ-2 SyncStockFundamentalUseCase 가 multi-stock loop 에서 한 종목 KiwoomBusinessError → 전체 abort 차단 책임. (a) per-stock try/except 후 success/failed counter 누적 (B-α 패턴) 권장
- **단위 모호** (계획서 § 11.2 / § 11.1 #2): mac/cap/listed_shares 단위 운영 검증 후 컬럼 주석에 명시. DoD § 10.3 운영 dry-run 후 결정
- **`replace(",", "")` 의도** (2R B-M5): 키움 명세 콤마 부재 — 안전망. docstring 보강 시점 미정
- **B-α/B-β 의 알려진 위험 그대로 상속**: 응답 `marketCode` ↔ 요청 `mrkt_tp` 불일치, UNIQUE(stock_code) cross-market overwrite, max_pages=100 cap

## Context for Next Session

### 사용자의 원래 의도 / 목표
backend_kiwoom Phase A 인증·트랜스포트 인프라 검증 후, 백테스팅 본체 진입점인 종목 마스터(B) 단계별 chunk 분할 진행. B-α (bulk) + B-β (gap-filler / lazy fetch) + B-γ-1 (펀더멘털 인프라) 완료. 다음은 B-γ-2 (펀더멘털 UseCase/Router/Scheduler), 운영 dry-run, 또는 Phase C 진입.

### 선택된 접근 + 이유
- **chunk 분할 (메모리 `feedback_chunk_split_for_pipelines.md`)**: B-γ 1,164줄 → B-γ-1 (인프라, ~700줄) + B-γ-2 (UseCase/Router/Scheduler, ~450줄). 작은 chunk 로 안전하게 진행
- **/ted-run Quality-First 풀 파이프라인**: TDD red → 구현 → 이중 리뷰 (force-2b 적대적) → 5관문 → ADR/CHANGELOG/HANDOFF/한글 커밋. 이번 chunk 는 푸시 미실행 (사용자 명시 요청 시만)
- **B-α/B-β 패턴 mechanical 차용**: `KiwoomStkInfoClient` 의 새 메서드 (fetch_basic_info), Repository 신규 (StockFundamentalRepository), Pydantic 모델 신규 (StockBasicInfoResponse 45 필드 + 250hgst alias) — 기본 구조는 패턴 차용, ka10001 특이사항 (45 필드 + 외부 벤더 빈값 정책 + Decimal precision + BIGINT overflow vendor 보호) 만 별도 처리

### 사용자 제약 / 선호
- 한글 커밋 메시지 (~/.claude/CLAUDE.md 글로벌 규칙)
- 푸시는 명시적 요청 시만 (커밋과 분리, 글로벌 CLAUDE.md 규칙)
- 큰 Phase 는 chunk 분할 후 ted-run 풀 파이프라인 (메모리 `feedback_chunk_split_for_pipelines.md`)
- 진행 상황 가시화 — 체크리스트 + 한 줄 현황 (메모리 `feedback_progress_visibility.md`)

### 다음 세션 진입 시 결정 필요
사용자에게 옵션 확인 권장:
1. **Phase B-γ-2 (UseCase + Router + Scheduler)** — Phase B 마무리. 진입 전 partial-failure 정책 (C-M3) / stock_id resolution invariant / mismatch alert 결정
2. **운영 dry-run** — 키움 자격증명 1쌍으로 α/β/A3/B-α/B-β/B-γ-1 통합 검증. ka10001 응답 45 필드 + 단위 검증 + 외부 벤더 빈값 종목 패턴
3. **Phase C 진입 + lazy fetch RPS 보호 결정** (1R 2b-M1 deferred) — OHLCV 백테스팅 본체. 진입 전 RPS 우회 차단 옵션 결정 필수 (ADR § 13.4.1)

## Files Modified This Session

이번 세션 한정 (커밋 대기):
```
docs/ADR/ADR-0001-backend-kiwoom-foundation.md     | § 14 추가
CHANGELOG.md                                        | prepend (B-γ-1 항목)
HANDOFF.md                                          | 전체 갱신
src/backend_kiwoom/migrations/versions/004_kiwoom_stock_fundamental.py  (신규)
src/backend_kiwoom/app/adapter/out/persistence/models/stock_fundamental.py  (신규)
src/backend_kiwoom/app/adapter/out/persistence/models/__init__.py  (수정)
src/backend_kiwoom/app/adapter/out/persistence/repositories/stock_fundamental.py  (신규)
src/backend_kiwoom/app/adapter/out/kiwoom/stkinfo.py  (확장 — ka10001 섹션)
src/backend_kiwoom/tests/test_migration_004.py  (신규, 8 cases)
src/backend_kiwoom/tests/test_kiwoom_stkinfo_basic_info.py  (신규, 33 cases)
src/backend_kiwoom/tests/test_stock_fundamental_repository.py  (신규, 14 cases)
```

11 files (코드 5 + 테스트 3 + 문서 3).
