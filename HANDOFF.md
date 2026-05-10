# Session Handoff

> Last updated: 2026-05-10 (KST) — daily_flow (ka10086) 백필 CLI 신규 완료
> Branch: `master`
> Latest commit: `23f601b` — feat(kiwoom): daily_flow (ka10086) 백필 CLI 신규
> 미푸시 commit: 0 건 (사용자 명시 push 완료)

## Current Status

`scripts/backfill_daily_flow.py` 신규 + `IngestDailyFlowUseCase` 확장. **OHLCV 백필 (§ 26) 운영 실측에서 발견된 차단 fix 3건 패턴을 처음부터 사전 적용** — mock 테스트가 못 잡는 운영 edge case 방어.

**핵심 산출**:
- 새 CLI: `scripts/backfill_daily_flow.py` (~480 lines, OHLCV 백필 패턴 1:1 응용 + indc-mode 옵션)
- mrkcond.py since_date — chart.py 패턴 헬퍼 2건 (`_page_reached_since` / `_row_on_or_after`)
- IngestDailyFlowUseCase — `_KA10086_COMPATIBLE_RE` ETF 가드 + only_stock_codes/skip_base_date_validation/since_date 확장
- ADR § 27 신규 + plan doc `phase-c-backfill-daily-flow.md` 신규
- 테스트 +31 (993 → 1024) / coverage 95%

## Completed This Session

| # | Task | 핵심 |
|---|------|------|
| 1 | **plan doc 신규** | `docs/plans/phase-c-backfill-daily-flow.md` — chunk DoD / 영향 범위 / 운영 미해결 4건 (CLAUDE.md § 3 권고) |
| 2 | **TDD red 작성** | mrkcond +2 / daily_flow_service +5 / CLI +24 cases (Step 0) |
| 3 | **mrkcond.py since_date** | `fetch_daily_market(since_date=)` + 헬퍼 2건. chart.py 패턴 1:1 |
| 4 | **IngestDailyFlowUseCase 확장** | ETF 가드 (raw_stocks fullmatch + sample 5 로깅) + execute/refresh_one 신규 파라미터 (모두 디폴트값 — 라우터/cron 호환) |
| 5 | **backfill_daily_flow.py CLI 신규** | argparse / resolve_indc_mode / dry-run (1 page ~300 거래일 추정) / resume (`stock_daily_flow.trading_date` max) / `_build_use_case` 외부 lifespan |
| 6 | **Verification 4 관문** | ruff PASS / mypy --strict PASS / 1024 tests / coverage 95% |
| 7 | **STATUS / CHANGELOG / ADR § 27 / plan doc 동시 갱신** | CLAUDE.md § 1 일관 |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | **daily_flow 백필 운영 실측** (사용자 수동) | not started | smoke → mid → full 3 단계 (OHLCV § 26.5 흐름). § 27.5 채우기 |
| 2 | **scheduler_enabled 운영 cron 활성** | not started | 측정 #4 (일간 cron elapsed) — OHLCV HANDOFF 부터 누적 미수행 |
| 3 | follow-up F6/F7/F8 일괄 분석 | not started | LOW (since_date edge case / turnover_rate 음수 / 빈 응답 1 종목) |
| 4 | ETF/ETN OHLCV 별도 endpoint (옵션 c) | not started | 본 chunk 가드는 skip 만 |
| 5 | refactor R2 (1R Defer 일괄) | pending | 기존 유지 |

## Key Decisions Made

### 운영 차단 fix 3건 사전 패턴 적용

OHLCV 백필 (`d60a9b3`/`76b3a4a`/`c75ede6`) 의 fix 패턴이 daily_flow 에서도 **사전 적용 (운영 실측 진입 전)**:

| # | OHLCV 운영 차단 | daily_flow 사전 적용 |
|---|----------------|--------------------|
| 1 | since_date guard | ✅ mrkcond.py `_page_reached_since` / `_row_on_or_after` |
| 2 | `--max-stocks` CLI bug | ✅ `_list_active_stock_codes` + `effective_stock_codes` 일관 (코드 0 차이) |
| 3 | ETF/ETN 호환 가드 | ✅ `_KA10086_COMPATIBLE_RE` 사전 필터 + sample 5 가시성 로깅 |

**의의**: mock 테스트가 운영 edge case (cont-yn=N 짧은 종료, 빈 next-key, ETF 코드) 를 재현 못 한다는 한계 (`12f0daf` HANDOFF) 를 운영 실측 진입 전 일괄 사전 적용으로 부분 완화. 새 운영 edge case 발견 시 OHLCV 와 동일 chunk 분리 방침 (즉시 fix + 다음 chunk).

### CLI 구조 — period dispatch 부재

OHLCV 백필 (`backfill_ohlcv.py` 637줄) 의 `--period` 분기와 `_RESUME_TABLE_BY_PERIOD` 매핑은 daily_flow 에 불필요 (단일 endpoint ka10086). 따라서:

- `_RESUME_TABLE` 단일 상수 (`kiwoom.stock_daily_flow`)
- `compute_resume_remaining_codes` 시그니처에 period 인자 없음
- CLI 약 480줄로 OHLCV 대비 단순

### `--indc-mode` 노출 결정

`IngestDailyFlowUseCase` 의 `indc_mode` 는 lifespan factory 가 settings 기반 단일 정책 묶음 (계획서 § 6.3). 그러나 백필 CLI 는 디버그 / cross-check 용으로 quantity / amount 를 모두 시도해보고 싶을 수 있어 CLI 옵션으로 노출 (`resolve_indc_mode` 헬퍼 + tests 3 cases).

### 코드 변경 vs 운영 실측 chunk 분리

OHLCV 백필 chunk (`055e81e`) 와 동일 정책 — 본 chunk 는 **CLI 코드 + 패턴 사전 적용 + 단위 테스트** 범위. 운영 실측 (smoke / mid / full) 은 사용자 수동 실행 후 별도 measurement chunk (§ 27.5 채움).

## Known Issues

본 chunk 신규 발견 0건. 기존 알려진 항목:

- **OHLCV F6/F7/F8** (LOW): since_date edge case (002690) / turnover_rate 음수 / 빈 응답 1 종목
- **일간 cron elapsed 미측정** — `scheduler_enabled=true` 활성 후 1주 모니터 필요
- **ETF/ETN OHLCV 자체** — 가드는 skip 만. 옵션 (c) 별도 chunk 필요

## Context for Next Session

### 사용자의 원래 의도

직전 세션 종료 시점 1순위 결정 — **daily_flow 백필 CLI**. HANDOFF Pending #1 → 본 chunk 가 흐름 완주.

### 선택된 접근 + 이유

- **OHLCV 백필 패턴 1:1 응용** — period dispatch 만 제거. 학습 비용 최소화 + 검증된 구조 재사용
- **운영 차단 fix 패턴 사전 적용** — OHLCV 에서 운영 진입 후 발견된 3건을 daily_flow 진입 전 일괄 적용 (mock 한계 부분 완화)
- **단일 chunk** — ~750~1000 LOC 추정 → 실측 ~750 LOC. 1500 LOC 미만으로 chunk 분할 불필요

### 사용자 제약 / 선호 (반복 등장)

- 한글 커밋 메시지
- 푸시는 명시 요청 시만 (`git push` 와 commit 분리)
- backend_kiwoom CLAUDE.md § 1 — STATUS / HANDOFF / CHANGELOG 동시 갱신
- chunk 분리 패턴: 운영 발견 즉시 fix + 새 발견은 다음 chunk

### 다음 세션 진입 시 결정 필요

다음 chunk 1순위 후보 (사용자 선택):

1. **daily_flow 백필 운영 실측** (사용자 수동) — OHLCV § 26.5 와 동일 흐름. smoke / mid / full 3 단계 + ADR § 27.5 채움
2. **scheduler_enabled 운영 cron 활성** + 1주 모니터 (HANDOFF 부터 누적 미수행)
3. follow-up F6/F7/F8 일괄 분석 — LOW
4. ETF/ETN OHLCV 별도 endpoint (옵션 c) — 신규 도메인

## Files Modified This Session

본 chunk 누적 (1 commit 예정):

```
src/backend_kiwoom/app/adapter/out/kiwoom/mrkcond.py                       (수정 — since_date 옵션 + 헬퍼 2)
src/backend_kiwoom/app/application/service/daily_flow_service.py           (수정 — ETF 가드 + only_stock_codes/skip_past_cap/since_date)
src/backend_kiwoom/scripts/backfill_daily_flow.py                          (신규 ~480 lines)
src/backend_kiwoom/tests/test_kiwoom_mrkcond_client.py                     (수정 — +2 since_date cases)
src/backend_kiwoom/tests/test_ingest_daily_flow_service.py                 (수정 — +5 cases / _stub_client since_date kwarg)
src/backend_kiwoom/tests/test_backfill_daily_flow_cli.py                   (신규 ~24 cases)
src/backend_kiwoom/docs/plans/phase-c-backfill-daily-flow.md               (신규 plan doc)
src/backend_kiwoom/STATUS.md                                                (수정)
docs/ADR/ADR-0001-backend-kiwoom-foundation.md                             (수정 — § 27 신규)
CHANGELOG.md                                                                (수정 — 1 항목 prepend)
HANDOFF.md                                                                  (본 파일)
```

테스트: 993 → 1024 (+31). coverage 95% (threshold 80%).
