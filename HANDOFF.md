# Session Handoff

> Last updated: 2026-05-10 (KST) — daily_flow smoke 첫 호출 운영 차단 fix (DAILY_MARKET_MAX_PAGES 10 → 40)
> Branch: `master`
> Latest commit: `7be3185` — docs(kiwoom): daily_flow 운영 실측 runbook + results doc 신규
> 미푸시 commit: 1 건 예정 (본 fix chunk — 사용자 명시 push 대기)

## Current Status

`scripts/backfill_daily_flow.py` 운영 실측 진입 → smoke 첫 호출에서 신규 운영 차단 1건 발견 → 즉시 fix → smoke 재시도 PASS. OHLCV `d60a9b3` 와 동일 "운영 발견 즉시 fix + 다음 chunk" 패턴 일관.

**핵심 발견**:
- 가설 (mrkcond.py:50 주석) "1 page ~300 거래일" → 실측 **~22 거래일/page** (13배 틀림)
- next-key 추적: p1 only ~80 거래일 / p2~ ~22 거래일 each
- 1년 백필 = 약 12 page 필요 → `DAILY_MARKET_MAX_PAGES = 10` 부족 → KiwoomMaxPagesExceededError

**fix 패턴 사전 적용 부분 검증**:
- ✅ `--max-stocks` CLI fix — raw 10 → 호환 6 정상
- ✅ ETF/ETN 호환 가드 — 4 종목 skip + sample 로깅
- ⚠ since_date guard — logic 정상이지만 max_pages=10 한계로 도달 전 abort → 본 fix 로 해소

**fix 후 smoke 재시도**: total 6 / failed 0 / 25s ✅

## Completed This Session

| # | Task | 핵심 |
|---|------|------|
| 1 | **dry-run 실행** | active 4373 / pages 4 / 추정 2h 25m |
| 2 | **smoke 첫 시도** | ❌ 8건 KiwoomMaxPagesExceededError → 운영 차단 발견 |
| 3 | **근본 원인 분석** | next-key 추적 — 가설 13배 틀림 검증 |
| 4 | **MAX_PAGES fix** | mrkcond.py:50 `10 → 40` + 주석 갱신 |
| 5 | **검증** | ruff / mypy --strict / 1024 tests / mrkcond 17 cases PASS |
| 6 | **smoke 재시도** | ✅ 6/2/0 / 25s — since_date guard 정상 작동 |
| 7 | **doc 갱신** | results.md § 0/§ 1/§ 2.1/§ 2.2 / ADR § 27.5/§ 27.6 / STATUS.md 5 § / CHANGELOG prepend / HANDOFF |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | 본 fix chunk 커밋 | pending | 사용자 명시 commit/push 요청 시 진행 |
| 2 | **Stage 2 mid (KOSPI 100 / 3년)** | not started | 본 fix 후 자연 흐름. 추정 ~수분 (12 page * 100 stock * 0.25s) |
| 3 | **Stage 3 full (active 4078 / 3년)** | not started | mid PASS 후. 추정 1h~2h 30m (32 page 평균 * 4078 * 0.25s, since_date break 적용 후 OHLCV 패턴으로 50% 빠름 가능) |
| 4 | **NUMERIC SQL 4 컬럼** | not started | full 완료 후. `credit_rate`/`credit_balance_rate`/`foreign_rate`/`foreign_weight` |
| 5 | scheduler_enabled 운영 cron 활성 | not started | HANDOFF Pending — OHLCV/daily_flow 통합 측정 가능 |
| 6 | follow-up F6/F7/F8 + ka10086 첫 page 80 거래일 패턴 | pending | LOW — 키움 서버 측 분기 추후 분석 |

## Key Decisions Made

### 즉시 fix vs 다음 chunk — 즉시 fix 선택

OHLCV 의 since_date guard 누락 (`d60a9b3`) 과 동일 패턴 — 운영 차단 발견 즉시 fix + 결과는 동일 chunk 에 기록. 사용자 메모리 룰 "chunk 분리 패턴: 운영 발견 즉시 fix + 새 발견은 다음 chunk" 일관.

### MAX_PAGES = 40 (vs 50)

3년 백필 = 약 32 page 필요 → 안전 마진 8 (25%). 5년 백필도 가능하려면 50 필요하지만 현 시점 운영 케이스는 3년이 최대 (settings.backfill_max_days=1095). 보수적 변경 원칙 — 필요 시 추후 상향.

### regression test 추가 보류

상수값 변경만으로 1024 기존 tests 모두 PASS. mock 테스트가 page row 수 가설을 검증 못 한다는 한계 (`12f0daf` HANDOFF) 가 본 fix 의 본질 — 단위 테스트로 잡기 어려운 운영 edge case. smoke 재시도 자체가 검증.

### 가설 "1 page ~300 거래일" 의 출처

mrkcond.py:50 의 주석 + 계획서 § 12.7. 실측 ~22 거래일 — 키움 서버가 ka10086 응답을 base_dt 기준 약 1개월 단위로 자르는 것으로 추정 (필드 22 vs ka10081 의 8). 첫 page 만 ~80 거래일 다른 패턴은 follow-up.

## Known Issues

본 chunk 신규 발견 1건 (즉시 해소):
- ✅ `DAILY_MARKET_MAX_PAGES = 10` 부족 → fix `=40`

신규 follow-up 1건:
- 🔶 ka10086 첫 page 만 ~80 거래일, p2~ ~22 거래일 패턴 차이 — 키움 서버 측 분기 추후 분석 (LOW)

기존 알려진 항목 변경 없음:
- OHLCV F6/F7/F8 (LOW)
- 일간 cron elapsed 미측정 (HANDOFF Pending)
- ETF/ETN OHLCV 자체 (옵션 c)

## Context for Next Session

### 사용자의 원래 의도

"#1 daily_flow 백필 운영 실측" — 본 chunk 가 그 진입. smoke 단계에서 운영 차단 1건 발견 + 즉시 fix + 재시도 PASS. 다음 자연 흐름 = Stage 2 mid (KOSPI 100 / 3년).

### 선택된 접근 + 이유

- **즉시 fix chunk** (사용자 선택) — OHLCV `d60a9b3` 패턴 일관. fix code change + smoke retry 결과를 한 commit
- **상수값만 변경** — break logic 자체는 정상 작동 검증 완료
- **regression test 보류** — page row 수 가설은 mock 으로 검증 어려운 운영 edge case

### 사용자 제약 / 선호 (반복 등장)

- 한글 커밋 메시지
- 푸시는 명시 요청 시만 (`git push` 와 commit 분리)
- backend_kiwoom CLAUDE.md § 1 — STATUS / HANDOFF / CHANGELOG 동시 갱신
- chunk 분리 패턴: 운영 발견 즉시 fix + 새 발견은 다음 chunk

### 다음 세션 진입 시 결정 필요

1. **본 fix chunk 커밋 여부** — 사용자 승인 대기 (예상 메시지: `fix(kiwoom): daily_flow smoke 첫 호출 운영 차단 fix — DAILY_MARKET_MAX_PAGES 10 → 40`)
2. 다음 chunk 1순위 후보:
   - **Stage 2 mid** (KOSPI 100 / 3년) — 본 fix 자연 흐름. 추정 ~수분
   - **Stage 3 full** 직행 (active 4078 / 3년) — mid 생략, 1h~2h 30m 백그라운드
   - 별도 chunk 분리 — fix commit 후 본 세션 종료, 다음 세션에서 mid/full

## Files Modified This Session

본 fix chunk (1 commit 예정):

```
src/backend_kiwoom/app/adapter/out/kiwoom/mrkcond.py                        (수정 — line 50: MAX_PAGES 10 → 40 + 주석)
src/backend_kiwoom/docs/operations/backfill-daily-flow-results.md           (수정 — § 0 / § 1 / § 2.1 / § 2.2 채움)
docs/ADR/ADR-0001-backend-kiwoom-foundation.md                              (수정 — § 27 헤더 + § 27.5 측정 결과 표)
src/backend_kiwoom/STATUS.md                                                 (수정 — § 0 / § 3 / § 4 / § 5 / § 6)
CHANGELOG.md                                                                 (수정 — 1 항목 prepend)
HANDOFF.md                                                                   (본 파일)
```

테스트: 1024 tests 그대로 (상수값 변경만). coverage 95% 유지.
