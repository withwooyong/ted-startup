# Session Handoff

> Last updated: 2026-05-09 (KST) — admin CLI 신규 (register_credential + sync_stock_master)
> Branch: `master`
> Latest commit (커밋 대기): `feat(kiwoom): 자격증명 등록 + 종목 마스터 sync admin CLI 신규`
> 직전 푸시: `243d4c7` — backend_kiwoom 전용 docker-compose + runbook 실 환경 값

## Current Status

**admin CLI 신규** — 운영 실측 진입에 필요한 ka10099 sync 1회 흐름을 단일 명령어로 정리. uvicorn 기동 + curl 의존성 제거. `register_credential.py` (자격증명 upsert) + `sync_stock_master.py` (5 시장 sync) + 11 단위 테스트. ted-run 풀 파이프라인 생략 (admin 도구). **테스트 972 → 983**, **mypy 76 files / 0 errors**.

## Completed This Session (커밋 대기)

| # | Task | 산출물 | Notes |
|---|------|--------|-------|
| 1 | register_credential.py 신규 | `scripts/register_credential.py` (~120줄) | argparse + env (KIWOOM_APPKEY/SECRETKEY/MASTER_KEY) → Cipher → upsert. exit code 0/2/3 |
| 2 | sync_stock_master.py 신규 | `scripts/sync_stock_master.py` (~150줄) | TokenManager + KiwoomClient + KiwoomStkInfoClient + SyncStockMasterUseCase. 5 시장 격리 sync. exit code 0/1/2/3 |
| 3 | 단위 테스트 11 cases | `tests/test_register_credential_cli.py` 7 / `tests/test_sync_stock_master_cli.py` 4 | argparse + env 검증 + format_summary |
| 4 | runbook 갱신 | `docs/operations/backfill-measurement-runbook.md` § 1.4/1.5 | register_credential + sync_stock_master 명령어 + 보안 주의 |
| 5 | STATUS.md / HANDOFF.md / CHANGELOG.md 갱신 | 3 문서 동시 갱신 (backend_kiwoom CLAUDE.md § 1) | chunk 22 → 24, 테스트 972 → 983 |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | 본 세션 산출물 커밋 + 푸시 | pending | 사용자 승인 후 — 한 commit |
| 2 | **운영 실측 측정** (사용자 수동) | not started | 1) `.env.prod` 채움 → 2) register_credential.py → 3) sync_stock_master.py → 4) backfill_ohlcv.py |
| 3 | gap detection 정확도 향상 | pending | resume 의 일자별 missing detection |
| 4 | daily_flow (ka10086) 백필 CLI | not started | OHLCV 와 구조 다름 — `scripts/backfill_daily_flow.py` |
| 5 | refactor R2 (1R Defer 일괄) | not started | L-2 + E-1 + E-2 + M-3 |
| 6 | ka10094 (년봉, P2) | pending | C-3 패턴 + UseCase YEARLY 분기 활성화 |

## Key Decisions Made (admin CLI)

### 진입점 — 라우터 vs 스크립트

- **운영 라우터 사용 안 함** — `POST /api/kiwoom/stocks/sync` 가 이미 있지만 uvicorn 기동 + ADMIN_API_KEY + curl 흐름 = 3 step. 사용자 환경 디버깅 어려움
- **직접 UseCase 호출 스크립트** — `_build_use_case` async context manager (backfill_ohlcv.py 패턴 재사용). 1 step + 진입 단순

### 자격증명 등록 라우터 신설 안 함

- admin 라우터 신설은 보안 분류로 ted-run 풀 파이프라인 (TDD/2a/2b/3-1~5/4) 강제. 본 chunk 범위 외
- 스크립트로 직접 INSERT — Cipher + Repository 재사용 (코드 신규 부분 < 30줄)
- 운영에서 외부 admin 진입 필요 시 향후 별도 chunk 에서 라우터 신설

### mock_env 결정

- `settings.kiwoom_default_env == "mock"` 그대로 (main.py 의 sync_stock factory 와 동일 정책)
- 운영 가정: 프로세스당 단일 env (ADR-0001 운영 정책)

### 테스트 깊이

- argparse + env 검증 + format_summary 만 단위 테스트. DB / 키움 통합은 e2e 별도 (사용자 환경 검증)
- ted-run 풀 파이프라인 생략 — 분류 = refactor·문서 + admin 도구. 단위 11 테스트 + mypy + ruff 만

## Known Issues

- **자격증명 / 마스터키 사용자 환경 의존** — 본 chunk 는 도구만. 실제 등록 + sync 는 사용자 수동
- **운영 라우터 vs 스크립트 중복** — `POST /stocks/sync` 와 `sync_stock_master.py` 가 동일 효과. 단, 진입 시점이 다름 (운영 cron + 외부 호출 vs 사용자 1회 admin)
- **글로벌 메모리 "2026-04 KRX 전면 인증화"** — 키움 OpenAPI 도 영향 가능성. 본 chunk 후 사용자 sync 실행 시 401 / data 0 rows 면 별도 issue chunk

## Context for Next Session

### 사용자의 원래 의도

`.env.prod` + 도커 + runbook 까지 정비된 상태에서 **실제 ka10099 sync 진입** 요청. 본 chunk 가 그 진입 도구. 사용자는 이후 환경변수 export → 2 명령어 실행 → backfill 진입.

### 선택된 접근 + 이유

- **B 옵션** (등록 + sync 두 스크립트 신규 + 단위 테스트, ted-run 안 함) — 사용자 결정
- **운영 라우터 신설 회피** — 보안 분류 풀 파이프라인 부담 회피
- **`backfill_ohlcv.py` 패턴 재사용** — `_build_use_case` 일관 (TokenManager + KiwoomClient + UseCase)

### 사용자 제약 / 선호

- 한글 커밋 메시지
- 푸시 명시적 요청 시만
- admin 도구는 ted-run 안 함 (분류 약함 + 11 단위 테스트로 충분)
- backend_kiwoom CLAUDE.md § 1 — STATUS / HANDOFF / CHANGELOG 동시 갱신

### 다음 세션 진입 시 결정 필요

본 chunk commit + push 후 사용자 측정 진입:

1. `.env.prod` 에 환경변수 채움 (KIWOOM_APPKEY / SECRETKEY / MASTER_KEY)
2. `uv run python scripts/register_credential.py --alias prod --env prod`
3. `uv run python scripts/sync_stock_master.py --alias prod`
4. `uv run python scripts/backfill_ohlcv.py --period daily --years 3 --alias prod` (실측)
5. results.md 채움 → ADR § 26.5 갱신 chunk

## Files Modified This Session (커밋 대기)

```
src/backend_kiwoom/scripts/register_credential.py             (신규, ~120줄)
src/backend_kiwoom/scripts/sync_stock_master.py               (신규, ~150줄)
src/backend_kiwoom/tests/test_register_credential_cli.py      (신규, 7 cases)
src/backend_kiwoom/tests/test_sync_stock_master_cli.py        (신규, 4 cases)
src/backend_kiwoom/docs/operations/backfill-measurement-runbook.md (수정 — § 1.4/1.5)
src/backend_kiwoom/STATUS.md                                  (수정)
CHANGELOG.md                                                  (수정 — prepend)
HANDOFF.md                                                    (본 파일)
```

총 8 파일 / 신규 4 + 수정 4 / +600 줄
