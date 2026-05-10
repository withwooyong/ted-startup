# Session Handoff

> Last updated: 2026-05-11 (KST) — failed 166 NXT resume PASS + 컬럼 동일값 확정
> Branch: `master`
> Latest commit: `72dbe69` — fix(kiwoom): NXT 빈 응답 sentinel 무한 루프 fix
> 미푸시 commit: 1 건 예정 (본 resume + eqcol-verify chunk)

## Current Status

`72dbe69` 후 failed 166 NXT 종목 `--only-stock-codes` 명시 resume + 컬럼 동일값 검증. 모두 PASS. daily_flow 운영 차단/위험 항목 모두 해소.

**핵심 결과**:
- ✅ Resume 166 NXT — 166/10/0 / 21m 33s
- ✅ 최종 DB — KRX 4077 / NXT 626 / 2,879,500 rows (OHLCV 정확히 일치)
- ✅ 컬럼 동일값 확정 — 2.88M rows 100% 동일 (`credit_diff=0`, `foreign_diff=0`)
- ✅ Migration 013 chunk entry point 확보

## Completed This Session

| # | Task | 핵심 |
|---|------|------|
| 1 | **failed 166 stock_code 추출** | full log 의 166 WARNING grep → /tmp/failed_nxt_codes.txt |
| 2 | **`--resume` 잘못된 범위 발견** | end_date=today / max < today → 4372 stocks 진행 → 중지 |
| 3 | **resume `--only-stock-codes` 재시도** | 166 codes CSV 명시. stocks=166 정상 진행 |
| 4 | **resume PASS** | 166/10/0 / 21m 33s — KRX 156 + NXT 활성 10 |
| 5 | **최종 DB 검증** | KRX 4077 / NXT 626 — OHLCV 정확히 일치 |
| 6 | **컬럼 동일값 SQL** | `IS DISTINCT FROM` — 2,879,500 rows 모두 0 diff |
| 7 | **NUMERIC 재측정** | max 16.39 / 100.00 변동 없음 |
| 8 | **doc 갱신** | results.md / ADR § 27.5 / STATUS § 0/3/4/5/6 / CHANGELOG prepend / HANDOFF |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | 본 resume + eqcol-verify chunk 커밋 | pending | 사용자 명시 commit/push 시 진행 |
| 2 | **Migration 013 — `credit_balance_rate` + `foreign_weight` DROP** | not started | C-2γ Migration 008 패턴 응용. ORM + 어댑터 매핑 + 테스트. ~1일 |
| 3 | scheduler_enabled 운영 cron 활성 + 1주 모니터 | not started | OHLCV + daily_flow 통합 측정 |
| 4 | follow-up F6/F7/F8 + daily_flow 빈 응답 1건 | pending | OHLCV + daily_flow 통합 |
| 5 | refactor R2 (1R Defer 일괄) | pending | 기존 유지 |

## Key Decisions Made

### resume 범위 오류 발견 + 즉시 중지

첫 `--resume` 시도 시 `end_date=today` / `max(trading_date) < today` (KRX 마지막 거래일 금요일) → 4372 stocks 모두 진행 (~9h). 의도와 다르므로 즉시 중지 + `--only-stock-codes` 명시 재시도.

### failed 166 stock_code 추출 방법

log 의 `WARNING` 카운트 = 166 정확 (full log 직접 grep). 첫 grep 시 sample 10 만 나온 이유 = tee output 잘림 (실제 log file 에는 166 모두 있음). full log 에서 직접 추출.

### success_nxt=10 / KRX-only 156 분기

첫 full 의 failed=166 은 `(stock × NXT exchange)` 단위 카운트. 166 종목 중 NXT 활성 10 만 NXT 적재. 나머지 156 은 KRX-only (KRX 는 첫 full 에서 이미 적재 성공). 즉 fail 의 의미는 "NXT 시도 실패" — 종목 단위 적재 실패가 아님.

### 컬럼 동일값 검증 시점

resume 완료 후 (2,879,500 rows) 검증 → 첫 measurement (2,785,437 rows) 의 컬럼 동일 패턴이 적재 시점과 무관함을 확인. ka10086 응답 자체의 특성.

### Migration 013 = 다음 chunk 1순위

`credit_balance_rate` ≡ `credit_rate` / `foreign_weight` ≡ `foreign_rate` 모두 100% 동일 → DB 스토리지 절약 + ORM 단순화. C-2γ Migration 008 의 D-E 중복 3 컬럼 DROP 패턴 응용 가능.

## Known Issues

본 chunk 해소 2건:
- ✅ #15 NXT 166 fail (이전 chunk `72dbe69` fix + 본 chunk resume PASS)
- ✅ #16 컬럼 동일값 (본 chunk SQL 검증 — Migration 013 별도 chunk)

본 chunk 신규 발견 0건.

기존 알려진 항목:
- OHLCV F6/F7/F8 (LOW)
- 일간 cron elapsed 미측정
- KRX 빈 응답 1 종목 (LOW)

## Context for Next Session

### 사용자의 원래 의도

"#1 NXT 166 fail 분석" 시작 → 본 chunk 가 그 흐름의 최종 단계 (resume + 검증). daily_flow 운영 실측 전 흐름 완료.

### 선택된 접근 + 이유

- **`--only-stock-codes` 명시** — resume 의 잘못된 범위 회피 (4372 → 166)
- **`--years 3` 유지** — 첫 full 과 동일 범위. since_date guard 작동
- **컬럼 동일값 검증 통합** — resume 결과와 같은 chunk (코드 변경 0 measurement chunk 일관)
- **Migration 013 분리** — ORM + 어댑터 + 테스트 변경 범위 큼

### 사용자 제약 / 선호 (반복 등장)

- 한글 커밋 메시지
- 푸시는 명시 요청 시만
- backend_kiwoom CLAUDE.md § 1 — STATUS / HANDOFF / CHANGELOG 동시 갱신
- chunk 분리 패턴: 운영 발견 즉시 fix + 새 발견은 다음 chunk

### 다음 세션 진입 시 결정 필요

1. **본 resume + eqcol-verify chunk 커밋 + push 여부** — 사용자 승인 대기
2. **다음 chunk** 1순위:
   - **Migration 013 — `credit_balance_rate` + `foreign_weight` DROP** (C-2γ 패턴)
   - scheduler_enabled 운영 cron 활성
   - follow-up F6/F7/F8 통합

## Files Modified This Session

본 chunk (`<this commit>`):

```
src/backend_kiwoom/docs/operations/backfill-daily-flow-results.md       (수정 — § 0 / § 2.4 resume / § 5.6 동일값 확정 / § 9 #1 #2 해소 / § 11 우선순위 / § 14 timeline)
docs/ADR/ADR-0001-backend-kiwoom-foundation.md                          (수정 — § 27 헤더 / § 27.5 #3 컬럼 동일값 확정 / chunk 산출)
src/backend_kiwoom/STATUS.md                                             (수정 — § 0 / § 3 / § 4 #16 해소 / § 5 / § 6)
CHANGELOG.md                                                             (수정 — 1 항목 prepend)
HANDOFF.md                                                               (본 파일)
```

테스트: 1026 그대로 (코드 변경 0).

## 본 세션 누적 commits

```
7be3185 ✅ push  docs(kiwoom): daily_flow 운영 실측 runbook + results doc 신규
7c07fb7 ✅ push  fix(kiwoom): DAILY_MARKET_MAX_PAGES 10 → 40
4e75dd3 ✅ push  docs(kiwoom): Stage 0~3 + NUMERIC SQL 측정 완료
72dbe69 ✅ push  fix(kiwoom): NXT 빈 응답 sentinel 무한 루프 fix
<this>  📝 예정 docs(kiwoom): failed 166 NXT resume PASS + 컬럼 동일값 확정
```
