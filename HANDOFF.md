# Session Handoff

> Last updated: 2026-05-10 (KST) — daily_flow 운영 실측 가이드 신규 (runbook + results doc, 코드 0 변경)
> Branch: `master`
> Latest commit: `23f601b` — feat(kiwoom): daily_flow (ka10086) 백필 CLI 신규
> 미푸시 commit: 0 건 (본 chunk 미커밋 상태 — 사용자 승인 대기)

## Current Status

`scripts/backfill_daily_flow.py` (ka10086, `23f601b`) 운영 실측을 위한 단계별 절차 + 결과 양식 신규. OHLCV § 26 (`backfill-measurement-runbook.md` / `backfill-measurement-results.md`) 패턴 1:1 복제 + ka10086 차이만 반영. **코드 변경 0**, 다음 단계 = 사용자가 runbook 따라 smoke→mid→full 실측.

**핵심 산출**:
- `backfill-daily-flow-runbook.md` 신규 (12 §, 약 250 lines) — § 1 사전 / § 2 dry-run / § 3 smoke / § 4 mid / § 5 full / § 7 NUMERIC SQL 4 컬럼 / § 8 일간 cron / § 12 OHLCV cross-check
- `backfill-daily-flow-results.md` 신규 (13 §, 약 270 lines) — TBD 자리에 측정값 채움. § 13 운영 차단 fix 패턴 사전 적용 검증
- ADR § 27 헤더 + § 27.5 — doc 참조 + 측정 자리 명시
- STATUS.md § 0 / § 3 / § 5 / § 6 갱신 (CLAUDE.md § 1)
- CHANGELOG.md prepend 1 항목

## Completed This Session

| # | Task | 핵심 |
|---|------|------|
| 1 | **runbook 신규** | OHLCV runbook 패턴 1:1 + ka10086 차이 반영 (단일 endpoint / `--indc-mode` / NUMERIC 4 컬럼 / resume 테이블 / § 12 OHLCV cross-check 신규) |
| 2 | **results doc 신규** | 13 § 양식 — § 5 NUMERIC 4 컬럼 분포 / § 8 since_date edge case (002690/004440 cross-check) / § 13 fix 패턴 사전 적용 검증 |
| 3 | **ADR § 27 헤더 갱신** | runbook + results doc 참조 추가, 상태 라벨 (코드/테스트 + 실측 가이드 완료) |
| 4 | **ADR § 27.5 자리 명시** | results.md 채움 후 핵심 결정 표 옮김 정책 명시 |
| 5 | **STATUS.md 4 섹션 갱신** | § 0 마지막 완료 chunk / § 3 sub-chunk 추가 (C-flow-실측 준비 + C-flow-실측 측정 ⏳) / § 5 다음 chunk 후보 / § 6 완료 목록 |
| 6 | **CHANGELOG.md prepend** | 1 항목 — docs(kiwoom) 운영 실측 가이드 신규 |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | **daily_flow 백필 운영 실측** (사용자 수동) | not started | runbook § 2~5 따라 dry-run → smoke → mid → full. results.md 채움. ADR § 27.5 표 4건 갱신 |
| 2 | **scheduler_enabled 운영 cron 활성** | not started | 측정 #4 (일간 cron elapsed) — OHLCV + daily_flow 동시 측정 가능 |
| 3 | follow-up F6/F7/F8 일괄 분석 | not started | LOW (since_date edge case / turnover_rate 음수 / 빈 응답 1 종목) |
| 4 | ETF/ETN OHLCV 별도 endpoint (옵션 c) | not started | 본 가드는 skip 만 |
| 5 | refactor R2 (1R Defer 일괄) | pending | 기존 유지 |
| 6 | 본 chunk 커밋 | pending | 사용자 승인 대기 (CLAUDE.md 한글 커밋 / push 분리) |

## Key Decisions Made

### OHLCV runbook 1:1 복제 + ka10086 차이만 반영

본 chunk 의 핵심 설계 결정:

- **단일 endpoint** — OHLCV 의 `--period {daily,weekly,monthly}` 분기 없음 → runbook § 6 (weekly/monthly) 생략. 단순화로 가독성 +
- **NUMERIC 측정 4 컬럼** — OHLCV 의 1 컬럼 (`turnover_rate`) 대비 daily_flow 는 4 컬럼 (`credit_rate` / `credit_balance_rate` / `foreign_rate` / `foreign_weight`). § 5 / § 7 의 SQL block 4 개로 확장
- **resume 테이블 차이** — `kiwoom.stock_daily_flow` 단일 테이블 + exchange 컬럼 (KRX/NXT). OHLCV 의 `stock_price_krx` / `stock_price_nxt` 분리와 다름
- **§ 12 OHLCV cross-check 신규** — OHLCV 결과 (34분, max 3,257.80, 2 종목 since_date edge) 와 daily_flow 가설 비교 표. 같은 mrkcond/chart.py 패턴 1:1 응용 검증 자리
- **§ 13 (results.md) fix 패턴 검증** — OHLCV 에서 발견된 3건 (since_date / max-stocks / ETF guard) 이 daily_flow 에서 처음부터 사전 적용된 효과를 smoke 단계에서 검증 자리

### 코드 변경 0 chunk 분리 — OHLCV § 26 패턴 일관

OHLCV 도 "C-운영실측 준비" (코드 0, runbook + results doc 신규) chunk 와 "C-운영실측 measurement" (코드 0, 측정 후 채움) chunk 를 분리. daily_flow 도 동일 패턴 — 본 chunk = 가이드 신규 / 다음 chunk = 사용자 측정.

### CLAUDE.md § 1 동시 갱신 정책 일관

본 chunk 는 doc only 라 단순 typo 가 아니지만 "새로운 결정 / 우선순위 변경" 발생 — STATUS.md § 0 / § 3 / § 5 / § 6 갱신. CLAUDE.md § 3 마지막 권고 (코드 변경 0 인 검증 chunk 도 STATUS § 6 + § 4 갱신 대상) 일관.

## Known Issues

본 chunk 신규 발견 0건. 기존 알려진 항목:

- **OHLCV F6/F7/F8** (LOW): since_date edge case (002690/004440) / turnover_rate 음수 / 빈 응답 1 종목
- **일간 cron elapsed 미측정** — `scheduler_enabled=true` 활성 후 1주 모니터 필요 (HANDOFF Pending #2)
- **daily_flow 백필 운영 실측 자체** — 본 chunk = 가이드만. 측정은 사용자 수동
- **ETF/ETN OHLCV 자체** — 가드는 skip 만. 옵션 (c) 별도 chunk 필요

## Context for Next Session

### 사용자의 원래 의도

직전 세션 (`23f601b`) HANDOFF Pending #1 — **daily_flow 백필 운영 실측**. 본 chunk 가 그 가이드 (runbook + results doc) 정착. 다음 chunk 가 실측 자체.

### 선택된 접근 + 이유

- **신규 runbook + results doc 작성** (사용자 선택) — OHLCV 패턴 일관 / § 27.5 채움 자리 명확 / CLAUDE.md § 3 정책 일관
- **OHLCV runbook 통합 확장 거부** — daily_flow + OHLCV 명령이 섞여 가독성 저하
- **채팅 명령만 안내 거부** — doc 부재 → 향후 재실측 시 가이드 부재 (1회성 비용 ↑)

### 사용자 제약 / 선호 (반복 등장)

- 한글 커밋 메시지
- 푸시는 명시 요청 시만 (`git push` 와 commit 분리)
- backend_kiwoom CLAUDE.md § 1 — STATUS / HANDOFF / CHANGELOG 동시 갱신
- chunk 분리 패턴: 운영 발견 즉시 fix + 새 발견은 다음 chunk
- OHLCV / daily_flow 운영 측정은 chunk 분리 (가이드 chunk + 측정 chunk)

### 다음 세션 진입 시 결정 필요

1. **본 chunk 커밋 여부** — 사용자 승인 대기 (예상 커밋 메시지: `docs(kiwoom): daily_flow 운영 실측 runbook + results doc 신규 — OHLCV § 26 패턴 1:1 + ka10086 차이 반영`)
2. 다음 chunk 1순위 후보:
   - **daily_flow 운영 실측 측정** (사용자 수동) — runbook 따라 진행. 결과를 results.md / ADR § 27.5 채움
   - scheduler_enabled 운영 cron 활성 + 1주 모니터 (HANDOFF Pending #2)
   - follow-up F6/F7/F8 일괄 분석 — LOW
   - ETF/ETN OHLCV 별도 endpoint (옵션 c) — 신규 도메인

## Files Modified This Session

본 chunk 누적 (1 commit 예정):

```
src/backend_kiwoom/docs/operations/backfill-daily-flow-runbook.md       (신규 — 12 §, ~250 lines)
src/backend_kiwoom/docs/operations/backfill-daily-flow-results.md       (신규 — 13 §, ~270 lines)
docs/ADR/ADR-0001-backend-kiwoom-foundation.md                          (수정 — § 27 헤더 + § 27.5 자리 명시)
src/backend_kiwoom/STATUS.md                                             (수정 — § 0 / § 3 / § 5 / § 6 + 마지막 갱신)
CHANGELOG.md                                                             (수정 — 1 항목 prepend)
HANDOFF.md                                                               (본 파일)
```

테스트: 1024 tests 그대로 (코드 변경 0). coverage 95% 유지.
