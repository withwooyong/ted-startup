# Session Handoff

> Last updated: 2026-05-10 (KST) — 운영 실측 measurement 완료
> Branch: `master`
> Latest commit (커밋 대기): `docs(kiwoom): 운영 실측 measurement 완료 — full 3년 백필 34분 / failed 0 / NUMERIC 안전`
> 직전 푸시: `d60a9b3` — since_date guard fix
> 미푸시 commit: `76b3a4a` (max-stocks fix), `c75ede6` (ETF guard) + 본 chunk

## Current Status

`backfill_ohlcv.py` smoke → mid → full **3 단계 측정 완료**. **full 3년 백필 34분 / 4078 호환 / 0 failed** (KRX 2,732,031 rows + NXT 152,152 rows). NUMERIC(8,4) `turnover_rate` max 3,257.80 (cap 33%) — **마이그레이션 불필요**. ADR § 26.5 + results.md 채움. 본 chunk 는 **코드 0 변경 docs only** — 측정 결과 documentation.

## Completed This Session (커밋 대기)

| # | Task | 산출물 | Notes |
|---|------|--------|-------|
| 1 | **smoke 측정** | KOSPI 10/1y → 6 success_krx / 0 failed / 1s | 3 fix (since_date / max-stocks / ETF guard) 동시 작동 검증 |
| 2 | **mid 측정** | KOSPI 100/3y → 78 success / 0 failed / 44s | dry-run 추정 5분 → 실측 44s (8.5x 빠름) |
| 3 | **full 측정** | active 4078/3y → 4078 success_krx + 626 NXT / 0 failed / **34분** | dry-run 추정 1h 13m → 실측 34m (2.1x 빠름) |
| 4 | NUMERIC SQL 측정 | `turnover_rate` max 3,257.80 / cap 33% | `change_rate` 등은 daily_flow chunk 에서 측정 |
| 5 | ADR § 26.5 채움 | 측정값 4건 + 신규 발견 3건 + follow-up F6 + 적재 통계 | `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` |
| 6 | results.md 채움 | 빈 양식 → 측정값 전 항목 채움 | `src/backend_kiwoom/docs/operations/backfill-measurement-results.md` |
| 7 | STATUS / HANDOFF / CHANGELOG 동시 갱신 | 3 문서 동시 갱신 + 미해결 #4/#5/#6 해소 표시 | backend_kiwoom CLAUDE.md § 1 |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | 본 세션 산출물 커밋 + 푸시 | pending | 사용자 승인 후. 미푸시 commit 누적: 76b3a4a + c75ede6 + 본 chunk |
| 2 | **daily_flow (ka10086) 백필 CLI** | not started | 다음 chunk 1순위. `change_rate` / `foreign_holding_ratio` / `credit_ratio` NUMERIC 측정 |
| 3 | **scheduler_enabled 운영 cron 활성** | pending | 측정 #4 미수행 — 1주 모니터 후 ADR § 26.5 추가 |
| 4 | follow-up F6/F7/F8 | pending | LOW 우선순위 일괄 분석 |

## Key Decisions Made

### 운영 실측 핵심 결과 4건

1. **NUMERIC(8,4) turnover_rate 마이그레이션 불필요** — max 3,257.80 (cap 33%)
2. **NXT 수집 prod 활성** — 626 종목 sync 검증
3. **3년 백필 시간 예산 ~ 34분** — daily_flow 백필도 유사 범위 추정
4. **ETF/ETN 정책 (a) 채택** — UseCase 가드 + 향후 별도 endpoint chunk

### 운영 발견 누적 6건 (이번 측정 chain)

| 순위 | 항목 | 해소 |
|------|------|------|
| #1 | since_date guard 누락 (max_pages 초과) | ✅ `d60a9b3` |
| #2 | `--max-stocks` CLI bug | ✅ `76b3a4a` |
| #3 | ETF/ETN stock_code 호환성 | ✅ `c75ede6` |
| F6 | since_date edge case (2 종목 더 과거) | LOW follow-up |
| F7 | turnover_rate 음수 anomaly | LOW follow-up |
| F8 | 1 종목 빈 응답 | LOW follow-up |

### 코드 0 변경 chunk

본 chunk 는 docs / ADR 갱신만 — 코드 변경 0. 측정 결과를 단일 commit 으로 명시하는 것이 변경 추적 명확성에 유리 (직전 chunk 들과 분리).

## Known Issues

- (해소) since_date / max-stocks / ETF — 3 fix 모두 ✅
- **F6**: since_date guard 가 일부 종목 (002690 동일제강 / 004440 삼일씨엔에스) 에서 break 안 됨. 4078 중 2 종목 = 0.05%. row 수 3,626 / 2,732,031 = 0.13%. 데이터 가치 nuetral~plus
- **F7**: turnover_rate min -57.32 — 회전율 음수는 보통 없음. 수정주가 조정 또는 키움 데이터 표기 anomaly 추정
- **F8**: full backfill 의 1 종목이 빈 응답 (4078 fetch 시도 / DISTINCT stock_id 4077 적재). 신규 상장 직전 / 거래 정지 후보
- **일간 cron elapsed 미측정** — `scheduler_enabled=true` 활성 후 1주 모니터 필요

## Context for Next Session

### 사용자의 원래 의도

`backfill_ohlcv.py` 실측 진입 흐름 (1순위 → 2순위 → smoke → mid → full). 본 chunk 가 마지막 단계 (full + measurement docs). 다음은 daily_flow 또는 운영 cron 활성.

### 선택된 접근 + 이유

- **본 chunk = docs only** — 코드 변경 없는 측정 결과 documentation. 직전 3 chunk (since_date / max-stocks / ETF) 와 분리해 변경 추적 명확
- **measurement 순서 smoke → mid → full** — 안전 단계적 검증. 각 단계 결과로 다음 단계 진입 결정

### 사용자 제약 / 선호

- 한글 커밋 메시지
- 푸시 명시적 요청 시만
- backend_kiwoom CLAUDE.md § 1 — STATUS / HANDOFF / CHANGELOG 동시 갱신
- 운영 검증 chunk 분리 패턴 유지

### 다음 세션 진입 시 결정 필요

본 chunk commit 후 미푸시 누적 (`76b3a4a` + `c75ede6` + 본 chunk) push 결정.

다음 chunk 1순위:
1. **daily_flow (ka10086) 백필 CLI** — `scripts/backfill_daily_flow.py` 신규 + `change_rate` 등 NUMERIC 측정
2. **scheduler_enabled 활성** — 측정 #4 (일간 cron) 보완

## Files Modified This Session (커밋 대기)

```
docs/ADR/ADR-0001-backend-kiwoom-foundation.md                            (수정 — § 26.5 채움)
src/backend_kiwoom/docs/operations/backfill-measurement-results.md       (수정 — 빈 양식 → 측정값 전 항목 채움)
src/backend_kiwoom/STATUS.md                                              (수정)
CHANGELOG.md                                                              (수정 — prepend)
HANDOFF.md                                                                (본 파일)
```

총 5 파일 / 수정 5 / 약 +220 줄
