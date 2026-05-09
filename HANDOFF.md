# Session Handoff

> Last updated: 2026-05-09 (KST) — Phase C-backfill
> Branch: `master`
> Latest commit (커밋 대기): `feat(kiwoom): Phase C-backfill — OHLCV 통합 백필 CLI`
> 직전 푸시: `2d4e2ae` — Phase C-3β 자동화

## Current Status

**Phase C-backfill (OHLCV 통합 백필 CLI) 완료** — `scripts/backfill_ohlcv.py` 신규. daily/weekly/monthly period dispatch + dry-run + resume + exit code 4 분기. 운영 라우터의 1년 cap 우회를 위해 UseCase 시그니쳐에 `_skip_base_date_validation` 키워드 옵션 추가 (디폴트 False — R1 invariant 유지). 운영 미해결 4건의 정량화 측정 도구. ted-run 풀 파이프라인 1회 통과 (CONDITIONAL → PASS), **939 → 972 cases / 96% coverage**. **Phase C 90% → 95%**.

## Completed This Session (커밋 대기)

| # | Task | 산출물 | Notes |
|---|------|--------|-------|
| 1 | plan doc 신규 | `docs/plans/phase-c-backfill-ohlcv.md` (신규) | 영향 범위 + self-check H-1~H-7 + DoD |
| 2 | UseCase 시그니쳐 확장 | `ohlcv_daily_service.py` / `ohlcv_periodic_service.py` | `_skip_base_date_validation` (default False) + `only_stock_codes` 인자 추가. 운영 라우터 영향 0 (R1 invariant) |
| 3 | CLI 신규 | `scripts/backfill_ohlcv.py` (~480줄) | argparse + period dispatch + dry-run + resume + exit code + try/finally cleanup |
| 4 | resume 헬퍼 | `compute_resume_remaining_codes` (CLI) | KRX 테이블 max(trading_date) per stock → 미적재 종목만 only_stock_codes 로 전달 |
| 5 | 2 신규 테스트 (+33 cases) | `test_backfill_ohlcv_cli.py` 25 / `test_skip_base_date_validation.py` 8 | argparse / period dispatch / dry-run / resume DB 통합 / R1 invariant |
| 6 | 기존 코드 fix (E-3) | `scripts/dry_run_ka10086_capture.py` | Migration 008 (C-2γ) 에서 DROP 된 컬럼 출력 제거. 작은 fix 라 본 chunk 합침 |
| 7 | 1차 코드 리뷰 (sonnet) | python-reviewer | CONDITIONAL → PASS. HIGH 1 (resume dead flag) + MEDIUM 1 (only_stock_codes 미전달) 즉시 적용 |
| 8 | Verification 5관문 | mypy / ruff / pytest+coverage | 74 files 0 errors / All passed / 972 cases / 96% |
| 9 | ADR-0001 § 25 추가 | `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` | 핵심 결정 7건 + 1R 결과 (HIGH/MEDIUM 적용) + 운영 실측 가이드 + Defer + 다음 chunk |
| 10 | STATUS.md 갱신 | `src/backend_kiwoom/STATUS.md` | Phase C 90→95%, chunk 22 누적, C-backfill 완료 |
| 11 | CHANGELOG prepend | `CHANGELOG.md` | C-backfill 항목 |
| 12 | HANDOFF 갱신 | `HANDOFF.md` | 본 파일 |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | 본 세션 산출물 커밋 + 푸시 | pending | 사용자 승인 후 — 한 commit |
| 2 | **운영 실측** (사용자 수동) | not started | 100 종목 → active 3000. 운영 미해결 4건 정량화. 사용자 환경 (실제 키움 자격증명 + 운영 DB) |
| 3 | gap detection 정확도 향상 | pending | resume 의 일자별 missing detection (현재는 max(trading_date) >= end_date 만) |
| 4 | daily_flow (ka10086) 백필 CLI | not started | OHLCV 와 구조 다름 — `scripts/backfill_daily_flow.py` |
| 5 | refactor R2 (1R Defer 일괄) | not started | L-2 + E-1 + E-2 + M-3 — `_do_sync` 류 핸들러 / ka10081 sync KiwoomError / `# type: ignore` → `cast()` / reset_* docstring |
| 6 | ka10094 (년봉, P2) | pending | C-3 패턴 + UseCase YEARLY 분기 활성화 |
| 7 | KOSCOM 공시 수동 cross-check (1~2건) | pending | 가설 B 최종 확정 |

## Key Decisions Made (C-backfill)

### 핵심 설계 (ADR § 25.2)

- **UseCase 재사용 vs 별도 BackfillUseCase** — 재사용 (사용자 결정 옵션 A). period dispatch 는 CLI 레이어에서 (`use_case_class_for_period`)
- **`_skip_base_date_validation` 키워드 옵션** — UseCase 시그니쳐 확장 (디폴트 False — R1 invariant 유지). CLI 만 True. 미래 가드는 `skip_past_cap=True` 일 때도 유지 (오타 방어)
- **`only_stock_codes` UseCase 인자 추가** — `only_market_codes` 와 같은 패턴. CLI 의 `--only-stock-codes` + `--resume` 모두 같은 인자로 위임
- **resume 알고리즘** — stock-level skip (max(trading_date) >= end_date 면 skip). 부분 적재 (gap) detection 은 별도 chunk
- **dry-run 시간 추정** — lower-bound (rate_limit × 호출수, ±50% margin)
- **exit code 4 분기** — 0/1/2/3 (success/partial/args/system)
- **라이프사이클** — `_build_use_case` async context manager + try/finally (KiwoomClient.close + engine.dispose)

### 1차 리뷰 결과 (CONDITIONAL → PASS)

- **HIGH H-1**: `--resume` dead flag → `compute_resume_remaining_codes` 헬퍼 + async_main 통합
- **MEDIUM M-1**: `--only-stock-codes` UseCase 미전달 → 두 UseCase 에 인자 추가 + CLI 의 `effective_stock_codes` 통합 처리
- **LOW L-1, L-2, L-3**: 기록 (별도 fix 불필요)

### 기존 코드 이슈 (E-3) — 본 chunk 에 합침

- `scripts/dry_run_ka10086_capture.py` 의 deprecated 컬럼 출력 (Migration 008 DROP) → 출력 제거. mypy strict 통과

## Known Issues

### C-backfill 후 잔여

- **운영 실측 미수행**: 본 chunk 는 CLI + 단위 테스트만. 실측은 사용자 환경 (실제 키움 자격증명 + 운영 DB) 필요
- **gap detection 미구현**: resume 이 max(trading_date) >= end_date 만 본다 — 일자별 missing 적재 시점 detection 은 별도 chunk
- **daily_flow 백필 미구현**: ka10086 은 OHLCV 와 다른 구조 (indc_mode 등) — 별도 chunk
- **L-2 / E-1 / E-2 / M-3** (1R Defer): refactor R2 chunk

## Context for Next Session

### 사용자의 원래 의도 / 목표

Phase C 의 운영 미해결 4건 (페이지네이션 빈도 / 3년 시간 / NUMERIC magnitude / sync 시간) 정량화 도구 마련. 실제 측정은 사용자 환경에서 수동. 본 chunk 는 그 도구 (CLI) 자체.

### 선택된 접근 + 이유

- **단일 chunk** — CLI 1개 + 테스트 (운영 실측은 별도)
- **UseCase 재사용** (별도 BackfillUseCase 안 만듦) — 80% 코드 중복 방지. period dispatch 는 CLI 가 책임
- **`_skip_base_date_validation` 키워드** — 운영 라우터 시그니쳐 변경 없음 (R1 invariant). CLI 만 사용
- **resume 정식 구현** (1R H-1 fix) — `--resume` flag 가 의도대로 작동. 사용자 기대 대 동작 일치
- **ted-run 풀 파이프라인** — TDD red → 구현 green → 1차 리뷰 → 5관문. CONDITIONAL → 2건 즉시 적용 → PASS
- **자동 분류 = 일반 기능** → 2b 적대적 / 3-4 보안 / 3-5 런타임 / 4 E2E 자동 생략

### 사용자 제약 / 선호

- 한글 커밋 메시지 (~/.claude/CLAUDE.md 글로벌 규칙)
- 푸시는 명시적 요청 시만 (커밋과 분리)
- 큰 Phase 는 chunk 분할 후 ted-run 풀 파이프라인
- 진행 상황 가시화 — 체크리스트 + 한 줄 현황
- backend_kiwoom CLAUDE.md — STATUS.md / HANDOFF.md / CHANGELOG.md 3 문서 동시 갱신

### 다음 세션 진입 시 결정 필요

사용자에게 옵션 확인 권장:

1. **운영 실측** (사용자 수동, 권고 1순위) — CLI 로 100 종목 → active 3000 실측. 운영 미해결 4건 정량화. 결과 정리 (docs/operations/ + ADR § 26)
2. **gap detection** — resume 정확도 향상 (일자별 missing detection)
3. **daily_flow (ka10086) 백필 CLI** — OHLCV 와 구조 다름
4. **refactor R2** — 1R Defer 4건 일괄 정리
5. **ka10094 (년봉, P2)** — UseCase YEARLY 분기 활성화

## Files Modified This Session (커밋 대기)

```
src/backend_kiwoom/scripts/backfill_ohlcv.py                              (신규, ~480줄)
src/backend_kiwoom/tests/test_backfill_ohlcv_cli.py                       (신규, 25 cases)
src/backend_kiwoom/tests/test_skip_base_date_validation.py                (신규, 8 cases)
src/backend_kiwoom/docs/plans/phase-c-backfill-ohlcv.md                   (신규)
src/backend_kiwoom/app/application/service/ohlcv_daily_service.py         (수정 — 키워드 옵션 + only_stock_codes)
src/backend_kiwoom/app/application/service/ohlcv_periodic_service.py      (수정 — 동일 옵션 추가)
src/backend_kiwoom/scripts/dry_run_ka10086_capture.py                     (수정 — E-3 기존 코드 fix)
src/backend_kiwoom/STATUS.md                                              (수정 — Phase C 90→95%, chunk 22)
docs/ADR/ADR-0001-backend-kiwoom-foundation.md                            (수정 — § 25 추가)
CHANGELOG.md                                                              (수정 — prepend)
HANDOFF.md                                                                (본 파일)
```

총 11 파일 / 신규 4 + 수정 7 / 추정 +1,400 줄
