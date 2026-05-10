# Session Handoff

> Last updated: 2026-05-10 (KST) — backfill_ohlcv `--max-stocks` CLI bug fix
> Branch: `master`
> Latest commit (커밋 대기): `fix(kiwoom): backfill_ohlcv --max-stocks 가 실 백필에서 무시되던 CLI bug fix`
> 직전 푸시: `d60a9b3` — since_date guard fix

## Current Status

직전 since_date guard chunk 의 smoke 검증 중 발견된 **`--max-stocks` CLI bug** 즉시 수정. 인자가 dry-run 추정 (`_count_active_stocks`) 만 적용되고 실 백필 호출 시 `effective_stock_codes=None` 으로 치환되어 active 전체 처리되던 bug — `resume` 분기와 동일하게 `_list_active_stock_codes` 호출해 explicit 종목 list 를 UseCase 에 전달. 변수명 `resume_only_codes` → `explicit_stock_codes` (resume / max_stocks 단독 둘 다 의미). 테스트 990 → 991 (+1: `_count` + `_list` 가 동일 max_stocks 적용 검증).

## Completed This Session (커밋 대기)

| # | Task | 산출물 | Notes |
|---|------|--------|-------|
| 1 | **CLI bug fix** | `scripts/backfill_ohlcv.py async_main` — max_stocks 단독 branch 추가, 변수명 rename | resume 분기와 동일한 explicit list 전달. dry-run / resume 모두 회귀 0 |
| 2 | 단위 테스트 +1 case | `tests/test_backfill_ohlcv_cli.py::test_list_active_stock_codes_applies_max_stocks_limit` | testcontainers PG16 통합 — `_count_active_stocks` 와 `_list_active_stock_codes` 가 동일 max_stocks 결과 검증 |
| 3 | CHANGELOG / STATUS / HANDOFF 동시 갱신 | 3 문서 동시 갱신 | backend_kiwoom CLAUDE.md § 1 |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | 본 세션 산출물 커밋 + 푸시 | pending | 사용자 승인 후 |
| 2 | **ETF/ETN stock_code 정책 + 가드** (운영 발견 #9) | pending | 251 종목 ValueError. 옵션 결정 필요 (a/b/c) |
| 3 | smoke 재시도 (`--max-stocks 10` 정상 작동 검증) | pending | ETF/ETN 가드 후 진입 |
| 4 | mid (KOSPI 100/3년) → full (4373/3년) | not started | smoke 통과 후 |
| 5 | NUMERIC SQL 분포 측정 → ADR § 26.5 | pending | full 백필 완료 후 |

## Key Decisions Made

### 변수명 `resume_only_codes` → `explicit_stock_codes`

- 의미: resume / max_stocks 단독 두 분기 모두 채우는 변수. "resume_only" 명명이 max_stocks 분기와 의미 불일치
- 대안 (변수명 유지 + branch 만 추가) 보다 코드 가독성 우선

### 1순위 → 2순위 → smoke → mid → full 흐름 (사용자 합의)

- 본 chunk = 1순위 단독 commit
- 다음 chunk = 2순위 (ETF/ETN 정책) — 사용자 옵션 결정 후 가드 구현

## Known Issues

- **ETF/ETN stock_code 호환성** (운영 미해결 #9) — `kiwoom.stock` 의 모든 active 가 ka10081 호환 가정이 틀림. 영문 포함 코드 (예: `0000D0`) 는 build_stk_cd 의 6자리 ASCII 숫자 검증에서 ValueError. 정책 옵션:
  - (a) ka10081 호출 전 stock_code 가드로 skip — UseCase 단순. 사용자 가시성 (skip 종목 수)
  - (b) Stock 테이블에 ka10081 호환 플래그 (Migration 013) — sync 시점에 결정. ETF/ETN 도메인 분리 명확
  - (c) 별도 ETF endpoint (ka10001 등) — 별도 sync chain. 가장 큰 scope

## Context for Next Session

### 사용자의 원래 의도

`backfill_ohlcv.py` 실측 진입 흐름. since_date fix → max-stocks fix → ETF/ETN 가드 → smoke → mid → full.

### 선택된 접근 + 이유

- **CLI fix 만 단독 chunk** — 1줄 핵심 + 테스트 1. ETF/ETN 정책은 결정 필요해 별도 chunk

### 사용자 제약 / 선호

- 한글 커밋 메시지
- 푸시 명시적 요청 시만
- backend_kiwoom CLAUDE.md § 1 — STATUS / HANDOFF / CHANGELOG 동시 갱신
- 운영 검증 chunk 분리 패턴 유지

### 다음 세션 진입 시 결정 필요

본 chunk commit 후:
1. **ETF/ETN 옵션 결정** (a/b/c) — 사용자 선택
2. 가드 구현 + 테스트
3. smoke 재시도 (`--max-stocks 10 --years 1` — 이번엔 정확히 10 종목)

## Files Modified This Session (커밋 대기)

```
src/backend_kiwoom/scripts/backfill_ohlcv.py        (수정 — max-stocks branch + 변수 rename)
src/backend_kiwoom/tests/test_backfill_ohlcv_cli.py (수정 — +1 case)
src/backend_kiwoom/STATUS.md                        (수정)
CHANGELOG.md                                        (수정 — prepend)
HANDOFF.md                                          (본 파일)
```

총 5 파일 / 수정 5 / 약 +90 줄
