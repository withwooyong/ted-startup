# Session Handoff

> Last updated: 2026-05-11 (KST) — NXT 빈 응답 sentinel 무한 루프 fix (mrkcond + chart 4곳)
> Branch: `master`
> Latest commit: `4e75dd3` — docs(kiwoom): daily_flow Stage 0~3 + NUMERIC SQL 측정 완료
> 미푸시 commit: 1 건 예정 (본 fix chunk — 사용자 명시 push 대기)

## Current Status

`4e75dd3` full backfill NXT 166 fail 근본 원인 분석 + 즉시 fix. **키움 서버 무한 루프 버그** 발견 — NXT 출범 (2025-03-04) 이전 base_dt 요청 시 resp-cnt=0 + cont-yn=Y + next-key sentinel 후 page 1 로 되돌아가는 패턴. `_page_reached_since` 가 빈 rows 시 False 반환이라 break 안 됨.

**핵심 발견 (010950 ka10086 3년 reproduce)**:
- p1~p14: 정상 (resp-cnt=20)
- p15: 마지막 row (resp-cnt=10)
- p16: 빈 응답 + sentinel next-key (`...20260511000000-1`)
- p17~: page 1 next-key 로 되돌아가서 무한 반복 → max_pages 도달

**fix**: mrkcond.py + chart.py 4 곳 (daily/weekly/monthly) `if not parsed.<list>: break` 추가. since_date guard 와 별도로 빈 응답 즉시 break. ka10081 도 일관성 + 잠재 위험 방어.

**검증**: 010950 3년 fix 후 13s / 0 fail / 1026 tests PASS.

## Completed This Session

| # | Task | 핵심 |
|---|------|------|
| 1 | **NXT 166 fail log 분석** | failed 종목 sample 10건 모두 NXT only — KRX 0 fail |
| 2 | **010950 단독 1년 reproduce** | ✅ PASS (6s) — 1년 백필은 정상 |
| 3 | **010950 단독 3년 reproduce + DEBUG 추적** | ❌ fail (19s) — next-key 추적으로 sentinel 무한 루프 발견 |
| 4 | **근본 원인 확정** | NXT 출범 이전 base_dt → resp-cnt=0 + cont-yn=Y + page 1 으로 되돌아감 |
| 5 | **fix 코드 (4 곳)** | mrkcond.py `fetch_daily_market` / chart.py `fetch_daily/weekly/monthly` 모두 `if not parsed.<list>: break` |
| 6 | **mock tests (+2)** | mrkcond + chart daily 빈 응답 + cont-yn=Y → break 검증 |
| 7 | **검증** | ruff / mypy / 1026 tests / 010950 3년 reproduce PASS (13s, 0 fail) |
| 8 | **doc 갱신** | ADR § 27.5 해소 표시 + STATUS § 0/3/4 #15 해소/5/6 + CHANGELOG prepend + HANDOFF |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | 본 fix chunk 커밋 | pending | 사용자 명시 commit/push 요청 시 진행 |
| 2 | **failed 166 NXT 종목 resume 재시도** | not started | `--resume` 로 166 NXT 종목 재시도. 추정 ~36분 (166 * 13s) |
| 3 | **컬럼 동일값 검증 chunk** | not started | LOW — `<>` SQL 검증 → 동일 시 Migration DROP (C-2γ 패턴) |
| 4 | scheduler_enabled 운영 cron 활성 + 1주 모니터 | not started | OHLCV/daily_flow 통합 측정 가능 |
| 5 | follow-up F6/F7/F8 + daily_flow 빈 응답 1건 | pending | OHLCV + daily_flow 통합 |
| 6 | refactor R2 (1R Defer 일괄) | pending | 기존 유지 |

## Key Decisions Made

### chart.py 도 동일 fix 적용 (사용자 결정)

사용자 선택 — "mrkcond.py + chart.py 통합 fix (권장)". OHLCV 가 현재 fail 없지만 동일 패턴 잠재 위험 (저거래 종목 / 장기 휴장 / NXT 출범 이전 base_dt). page row 수 ~600 이라 발생 안 했을 뿐, sentinel 패턴은 endpoint 공통.

### since_date guard 와 별도 가드

`_page_reached_since` 의 logic 자체는 정확. 단지 빈 rows 에서 `return False` 라 break 안 됨. since_date guard 를 수정 (`return True` for empty) 하는 대신 별도 `if not parsed.<list>: break` 추가 — since_date=None (운영 cron) 도 동일 보호 적용 가능 + 의도 명확.

### chart.py weekly/monthly test 생략

mock test 2 cases (mrkcond + chart daily 대표) 만 추가. weekly/monthly 는 동일 코드 패턴 / code review 의존. 본 chunk 가 너무 커지지 않게.

### Sentinel 패턴 vs since_date 우선순위

빈 응답 break 가 since_date guard 보다 먼저 — sentinel 패턴은 since_date 와 무관 (NXT 출범 이전 base_dt + since_date 도달 못 함). 따라서 since_date 와 별개로 안전망 작동.

## Known Issues

본 chunk 해소 1건:
- ✅ #15 NXT 166 fail (full 2026-05-11) — sentinel 무한 루프 fix

본 chunk 신규 발견 0건.

기존 알려진 항목:
- OHLCV F6/F7/F8 (LOW)
- 일간 cron elapsed 미측정
- #16 컬럼 동일값 의심 (LOW — `<>` 검증 chunk)
- KRX 빈 응답 1 종목 (LOW)

## Context for Next Session

### 사용자의 원래 의도

"#1 NXT 166 fail 분석" — 본 chunk 가 분석 + 즉시 fix 완료. 다음 자연 흐름 = failed 166 NXT 종목 resume 재시도 → 모두 적재 확인.

### 선택된 접근 + 이유

- **mrkcond + chart 통합 fix** (사용자 선택) — 잠재 위험 방어 + 일관성
- **2 tests 만 추가** — mrkcond + chart daily 대표. weekly/monthly 동일 패턴 code review
- **시나리오 별 break 위치** — since_date guard 이전 (빈 응답이면 since_date 비교 자체 불가)

### 사용자 제약 / 선호 (반복 등장)

- 한글 커밋 메시지
- 푸시는 명시 요청 시만
- backend_kiwoom CLAUDE.md § 1 — STATUS / HANDOFF / CHANGELOG 동시 갱신
- chunk 분리 패턴: 운영 발견 즉시 fix + 새 발견은 다음 chunk

### 다음 세션 진입 시 결정 필요

1. **본 fix chunk 커밋 여부** — 사용자 승인 대기 (예상: `fix(kiwoom): NXT 빈 응답 sentinel 무한 루프 fix — mrkcond + chart 4곳`)
2. **다음 chunk** 1순위:
   - **failed 166 NXT 종목 resume 재시도** (자연 흐름, ~36분)
   - 컬럼 동일값 검증 (LOW)
   - scheduler_enabled 운영 cron 활성

## Files Modified This Session (fix chunk)

본 chunk (`<this commit>`):

```
src/backend_kiwoom/app/adapter/out/kiwoom/mrkcond.py                    (수정 — fetch_daily_market 빈 응답 break)
src/backend_kiwoom/app/adapter/out/kiwoom/chart.py                       (수정 — fetch_daily/weekly/monthly 빈 응답 break)
src/backend_kiwoom/tests/test_kiwoom_mrkcond_client.py                   (수정 — +1 case)
src/backend_kiwoom/tests/test_kiwoom_chart_client.py                     (수정 — +1 case)
docs/ADR/ADR-0001-backend-kiwoom-foundation.md                          (수정 — § 27.5 #15 해소 표시 + 근본 원인 / fix 기록)
src/backend_kiwoom/STATUS.md                                             (수정 — § 0 / § 3 / § 4 #15 해소 / § 5 / § 6)
CHANGELOG.md                                                             (수정 — 1 항목 prepend)
HANDOFF.md                                                               (본 파일)
```

테스트: 1024 → **1026** (+2: mrkcond +1, chart +1). coverage 95% 유지.

## 본 세션 누적 commits

```
7be3185 docs(kiwoom): daily_flow 운영 실측 runbook + results doc 신규  ✅ push
7c07fb7 fix(kiwoom): DAILY_MARKET_MAX_PAGES 10 → 40                   ✅ push
4e75dd3 docs(kiwoom): Stage 0~3 + NUMERIC SQL 측정 완료                 ✅ push
<this>  fix(kiwoom): NXT 빈 응답 sentinel 무한 루프 fix                  (예정)
```
