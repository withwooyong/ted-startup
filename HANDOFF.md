# Session Handoff

> Last updated: 2026-05-11 (KST) — daily_flow Stage 0~3 + NUMERIC SQL 측정 완료
> Branch: `master`
> Latest commit: `7c07fb7` — fix(kiwoom): DAILY_MARKET_MAX_PAGES 10 → 40
> 미푸시 commit: 1 건 예정 (본 measurement chunk — 사용자 명시 push 대기)

## Current Status

`scripts/backfill_daily_flow.py` 운영 실측 measurement chunk 완료. **코드 변경 0** — Stage 0~3 + NUMERIC SQL 4 컬럼 + since_date edge cross-check 모든 결과를 results.md / ADR § 27.5 / STATUS.md / CHANGELOG.md 에 채움.

**핵심 결과**:
- ✅ NUMERIC(8,4) 4 컬럼 — **마이그레이션 불필요** (max 16.39 / 100.00 / cap 1% 이내)
- ✅ since_date guard daily_flow 가 OHLCV 보다 정확 (F6 edge case 0)
- 🟡 full 9h 53m 34s — KRX 0 fail / **NXT 166 fail (4.07%, 활성 626 의 26.5%)**
- 🔶 컬럼 동일값 의심 (`credit_rate ≡ credit_balance_rate`, `foreign_rate ≡ foreign_weight`)

## Completed This Session

| # | Task | 핵심 |
|---|------|------|
| 1 | **Stage 0 dry-run** | active 4373 / pages 4 / 추정 2h 25m |
| 2 | **Stage 1 smoke 첫 시도** | ❌ 8 fail (`KiwoomMaxPagesExceededError`) |
| 3 | **MAX_PAGES fix** (`7c07fb7`) | mrkcond:50 `10 → 40` (가설 13배 틀림) |
| 4 | **Stage 1 smoke 재시도** | ✅ 6/2/0 / 25s |
| 5 | **Stage 2 mid (KOSPI 100/3y)** | ✅ 78/21/0 / 13m 8s |
| 6 | **Stage 3 full (active 4078/3y)** | 🟡 3922/616/166 / 9h 53m 34s (NXT 166 fail) |
| 7 | **NUMERIC SQL 4 컬럼** | ✅ max < 100 / gt_100·gt_1000 모두 0 / 마이그레이션 불필요 |
| 8 | **since_date edge cross-check** | ✅ 0 rows (OHLCV F6 보다 정확) |
| 9 | **컬럼 동일값 신규 발견** | 🔶 `credit_rate ≡ credit_balance_rate` / `foreign_rate ≡ foreign_weight` |
| 10 | **doc 통합 갱신** | results.md § 0~14 채움 / ADR § 27 헤더 + § 27.5 표 / STATUS.md 5 § / CHANGELOG prepend / HANDOFF |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | 본 measurement chunk 커밋 | pending | 사용자 명시 commit/push 요청 시 진행 |
| 2 | **NXT 166 종목 max_pages 분석 chunk** | not started | MEDIUM — full 결과 신규 발견. log + cont-yn + next-key 추적 / NXT 응답 패턴 분석 |
| 3 | **컬럼 동일값 검증 chunk** | not started | LOW — `<>` SQL 검증 → 동일 시 Migration DROP (C-2γ 패턴) |
| 4 | scheduler_enabled 운영 cron 활성 + 1주 모니터 | not started | OHLCV/daily_flow 통합 측정 가능 |
| 5 | follow-up F6/F7/F8 + daily_flow 빈 응답 1건 | pending | OHLCV + daily_flow 통합 |
| 6 | refactor R2 (1R Defer 일괄) | pending | 기존 유지 |

## Key Decisions Made

### NUMERIC(8,4) 마이그레이션 불필요 — 확정

4 컬럼 모두 max < 100 / gt_100 0 / gt_1000 0:
- `credit_rate` / `credit_balance_rate`: max **16.39**, p99 6.89
- `foreign_rate` / `foreign_weight`: max **100.00**, p99 52.52

NUMERIC(8,4) cap (±9999.9999) 의 1% 이내. **운영 진입 안전**, ADR § 18.4 상속 항목 (`change_rate` / `foreign_holding_ratio` / `credit_ratio`) 모두 해소.

### since_date guard daily_flow 가 OHLCV 보다 정확

OHLCV F6 (002690/004440 같은 since_date 미만 적재) 가 daily_flow 에서는 **0 rows** — `_page_reached_since_market` 가 page 마지막 row + row 단위 fragment 모두 정확히 break. F6 별도 분석 우선순위 ↓.

### NXT 166 종목 fail = 별도 chunk

KRX 0 fail / NXT only 166 fail 패턴 → **NXT 응답 특성 차이** (cont-yn / page row 수). max_pages=40 단순 상향이 아닌 NXT-only 분석 + 별도 가드 정책 필요. 본 chunk 에서 분석은 시간 부족 — MEDIUM 별도 chunk.

### 컬럼 동일값 의심 = 별도 검증 chunk

min/max/p01/p99/rows 모두 일치 → 단순 `<>` SQL 로 검증 가능. C-2γ 의 D-E 중복 컬럼 DROP 패턴과 동일 절차. LOW 이지만 빠르게 수행 가능.

### 측정 흐름 정착

OHLCV 와 동일 흐름 일관:
1. 가이드 chunk (`7be3185`) → 2. 차단 발견·즉시 fix chunk (`7c07fb7`) → 3. measurement chunk (본)

다음 endpoint (예: ka10094 년봉) 에서도 동일 흐름 적용 가능.

## Known Issues

본 chunk 신규 발견 4건:
- **#15 NXT 166 fail** (MEDIUM) — 별도 분석 chunk
- **#16 컬럼 동일값** (LOW) — `<>` 검증 chunk
- KRX 빈 응답 1 종목 (LOW) — OHLCV F8 통합
- KRX 적재 -156 stocks vs OHLCV (LOW) — #15 와 통합

본 chunk 해소 2건:
- ✅ #7 C-2α 상속 NUMERIC magnitude (해소)
- ✅ #14 DAILY_MARKET_MAX_PAGES=10 부족 (`7c07fb7` 해소)

기존 알려진 항목:
- OHLCV F6/F7/F8 (LOW)
- 일간 cron elapsed 미측정

## Context for Next Session

### 사용자의 원래 의도

"#1 daily_flow 백필 운영 실측" — 본 세션에서 가이드 신규 → 차단 fix → mid → full → NUMERIC SQL 까지 일괄 진행. 사용자 정책 일관 (코드 변경 즉시 fix + 측정 결과 별도 chunk).

### 선택된 접근 + 이유

- **runbook + results doc 신규 작성** (사용자 선택) — OHLCV 패턴 일관 / 향후 재실측 가이드
- **즉시 fix chunk** (사용자 선택) — `MAX_PAGES = 10 → 40`
- **mid foreground** (사용자 선택) — ~13분, Bash run_in_background 알림
- **full 백그라운드 즉시 시작** (사용자 선택) — 9h 53m 진행, 익일 05:39 완료, Bash run_in_background 알림
- **measurement chunk 통합** — Stage 2/3/NUMERIC/cross-check 한 chunk 에 묶음 (OHLCV `12f0daf` 패턴)

### 사용자 제약 / 선호 (반복 등장)

- 한글 커밋 메시지
- 푸시는 명시 요청 시만 (`git push` 와 commit 분리)
- backend_kiwoom CLAUDE.md § 1 — STATUS / HANDOFF / CHANGELOG 동시 갱신
- chunk 분리 패턴: 운영 발견 즉시 fix + 새 발견은 다음 chunk
- 긴 작업 백그라운드 + 진행 상황 가시화

### 다음 세션 진입 시 결정 필요

1. **본 measurement chunk 커밋 여부** — 사용자 승인 대기 (예상 메시지: `docs(kiwoom): daily_flow Stage 0~3 + NUMERIC SQL 측정 완료 — full 9h 53m / NXT 166 fail / 마이그레이션 불필요`)
2. **3 미푸시 commit push 여부** — `7be3185` / `7c07fb7` / `<measurement>`
3. 다음 chunk 1순위 후보:
   - **NXT 166 fail 분석** (MEDIUM) — 가장 시급, 운영 cron 영향 가능
   - **컬럼 동일값 검증** (LOW) — 빠르게 수행 + Migration DROP 가능
   - scheduler_enabled 운영 cron 활성 (HANDOFF Pending)

## Files Modified This Session (measurement chunk)

본 chunk (`<this commit>`):

```
src/backend_kiwoom/docs/operations/backfill-daily-flow-results.md       (수정 — § 0~14 채움)
docs/ADR/ADR-0001-backend-kiwoom-foundation.md                          (수정 — § 27 헤더 + § 27.5 표 + 신규 발견 3건)
src/backend_kiwoom/STATUS.md                                             (수정 — § 0 / § 3 / § 4 #15 #16 신규 / § 5 / § 6)
CHANGELOG.md                                                             (수정 — 1 항목 prepend)
HANDOFF.md                                                               (본 파일)
```

## 본 세션 누적 commits (push 안 함)

```
7be3185 docs(kiwoom): daily_flow 운영 실측 runbook + results doc 신규
7c07fb7 fix(kiwoom): daily_flow smoke 첫 호출 운영 차단 fix — DAILY_MARKET_MAX_PAGES 10 → 40
<measurement> docs(kiwoom): daily_flow Stage 0~3 + NUMERIC SQL 측정 완료 (예정)
```

테스트: 1024 tests 그대로 (코드 변경 0). coverage 95% 유지.
