# Session Handoff

> Last updated: 2026-05-11 (KST, /handoff) — follow-up F6/F7/F8 + daily_flow 빈 응답 통합 분석 완료.
> Branch: `master`
> Latest commit: `<this>` (follow-up 분석 / 4건 모두 NO-FIX / 452980 신한제11호스팩 식별 / ADR § 31 / 코드 0줄)
> 미푸시 commit: **1 건** (`<this>` follow-up 분석. 이전 4 commits 는 이미 push 완료)

## Current Status

STATUS § 4 의 LOW 4건 (F6 / F7 / F8 / daily_flow 빈 응답) 일괄 분석 + 정책 결정. **코드 변경 0줄** — 분석 + 문서 chunk. 4건 모두 **NO-FIX** 결정 (사용자 옵션 A). F8 + daily_flow 빈 응답이 **동일 종목 `452980` 신한제11호스팩** (KOSDAQ SPAC, 2026-05-09 등록, 신규 상장 직후) 으로 확정. sentinel 가드 (`72dbe69`) 정상 동작. ADR § 31 + STATUS § 4 4 항목 ✅ 표시 + § 5 follow-up 항목 제거 (해소) + CHANGELOG / HANDOFF 갱신.

## Completed This Session

| # | Task | 결과 | Files |
|---|------|------|-------|
| 1 | /ted-run 풀 파이프라인 — Phase C-2δ Migration 013 | `8dd5727` / 1030 tests / ADR § 28 | 11 + 4 + 4 |
| 2 | /ted-run 풀 파이프라인 — Phase C-4 ka10094 년봉 | `b75334c` / 1035 tests / ADR § 29 / Phase C chart 종결 | 11 + 6 + 4 + plan |
| 3 | /ted-run 풀 파이프라인 — Phase C-R2 1R Defer 5건 | `d43d956` / 1037 tests / coverage 81.15% / ADR § 30 | 8 + 4 + 4 + plan |
| 4 | docs sync — R2 후 backfill runbook 현행화 | `d6357da` / 3 곳 정정 | 2 docs |
| 5 | follow-up F6/F7/F8 + daily_flow 빈 응답 통합 분석 | (this commit) / 4건 모두 NO-FIX / 452980 식별 / ADR § 31 / 코드 0줄 | 4 docs |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | ETF/ETN OHLCV 별도 endpoint (옵션 c) | pending | 295 종목 / 6.7% |
| 2 | KOSCOM cross-check 수동 | 대기 | 가설 B 최종 확정 |
| 3 | Phase D — ka10080 분봉 / ka20006 업종일봉 | 대기 | 대용량 파티션 결정 선행 |
| 4 | Phase E (공매도/대차) / F (순위) / G (투자자별) | 대기 | 신규 endpoint wave |
| **최종** | **scheduler_enabled 일괄 활성 + 1주 모니터** | 사용자 결정 보류 | 모든 작업 완료 후 활성. 측정 #4 일간 cron elapsed / OHLCV + daily_flow + yearly 통합 |

## Key Decisions Made

### follow-up 4건 통합 분석 결정 (옵션 A, 2026-05-11)

| 항목 | 결정 | 이유 |
|------|------|------|
| **F6 since_date edge** (002690 / 004440 / 0.13%) | **NO-FIX** | 1980s 상장 종목의 page 단위 break 의 row 잔존. 데이터 가치 ≥ row 단위 fragment 제거 비용 (~15줄 + 테스트) |
| **F7 turnover_rate 음수** (-57.32 / 0.0009%) | **NO-FIX (정직성)** | 키움 raw 응답 그대로 보존. `_to_decimal` 음수 가드 추가는 raw 정보 손실. 분석 시 0/NaN/MAX(0,x) 처리는 분석 layer (백테스팅) 책임 |
| **F8 OHLCV 1 종목 row 0** | **NO-FIX (식별 완료)** | DB SELECT — `452980` 신한제11호스팩 (KOSDAQ SPAC, 2026-05-09 등록, **신규 상장 직후**). sentinel 가드 (`72dbe69`) 정상. 키움 빈 응답 → break → row 0 |
| **daily_flow 빈 응답** | **NO-FIX (식별 완료)** | F8 와 **동일 종목 (`452980`)**. results.md 의 "OHLCV F8 일관" 명시와 일치. mrkcond + chart sentinel 가드 양쪽 정상 |

### 식별 SQL (ADR § 31.3)

`SELECT NOT IN (DISTINCT stock_id FROM stock_price_krx)` 형태로 OHLCV / daily_flow 양쪽 모두 동일 종목 `452980` 신한제11호스팩 확정.

### 권고 미래 follow-up

- F6: 1980s 상장 종목 추가 식별 시 row 단위 fragment 제거 chunk
- F7: 분석 layer 에서 0/NaN 처리 정책 명시 (DB 정규화 거부)
- F8 / daily_flow: 다음 cron 실행 후 신한제11호스팩 row 추가 확인 → 다른 신규상장 SPAC 으로 패턴 늘어나면 별도 대응

## Known Issues

본 세션 해소 (4건 follow-up):
- ✅ F6 — NO-FIX (ADR § 31.2)
- ✅ F7 — NO-FIX (ADR § 31.2)
- ✅ F8 — NO-FIX / 452980 신한제11호스팩 식별 (ADR § 31.2 + § 31.3)
- ✅ daily_flow 빈 응답 — NO-FIX / F8 동일 종목 (ADR § 31.2)

기존 미해결 유지:
- 일간 cron elapsed 미측정 (scheduler_enabled 활성화 시)
- ka10086 첫 page 만 ~80 거래일, p2~ ~22 거래일 패턴 차이 (LOW, 키움 서버 측 분기)
- KOSCOM cross-check 수동 미완 (가설 B)
- ka10094 운영 first-call 미검증 — dt 의미 / 년봉 high/low 일치 (plan § 10.3)

## 운영 영향

본 chunk 코드 0줄 — 운영 영향 0. 운영 모니터링 권고:

- **다음 cron (KST mon-fri 18:30 OHLCV / 19:00 daily_flow) 실행 후 `452980` 신한제11호스팩 row 추가 확인** — sentinel 가드 + 키움 응답 정상 흐름 검증
- row 0 종목이 다른 신규상장 SPAC 으로 늘어나면 STATUS § 4 에 추가 (현재는 정상 패턴)

## Context for Next Session

### 사용자의 원래 의도

본 세션 흐름 (4 chunk):
1. 사용자 "다음작업 알려줘" → C-2δ Migration 013 → `8dd5727`
2. 사용자 "scheduler 시간 알려줘" → 7 job cron 표 / 사용자 "scheduler_enabled 활성은 모든 작업 완료 후" + "다음작업"
3. → C-4 ka10094 → `b75334c`
4. 사용자 "다음작업" → refactor R2 → `d43d956`
5. 사용자 "핸드오프/푸시/커밋" → docs sync `d6357da` → 4 commits push
6. 사용자 "다음은 follow-up F6/F7/F8 + daily_flow 빈 응답 통합 분석 진행" → 본 chunk (분석 only)

### 선택된 접근 + 이유

- **옵션 A (NO-FIX)** — F6/F7 은 디자인 trade-off / F8 + daily_flow 는 종목 자체 상태. 코드 변경은 정직성/비용 측면에서 비합리
- **F8 + daily_flow 종목 식별 SQL 실행** — `docker exec kiwoom-db psql` 로 즉시 확인. 1 종목 = 동일 종목 (`452980`) 확정
- **F7 정직성 우선** — 키움 raw 응답 보존. 분석 layer 책임으로 분리
- **F6 운영 재평가** — 1980s 상장 종목 증가 시 row 단위 정밀화 chunk

### 사용자 제약 / 선호 (반복 등장)

- 한글 커밋 메시지
- 푸시는 명시 요청 시만 (`git push` 와 commit 분리)
- backend_kiwoom CLAUDE.md § 1 — STATUS / HANDOFF / CHANGELOG 동시 갱신
- chunk 분리 패턴: 운영 발견 즉시 fix + 새 발견은 다음 chunk
- 긴 작업 백그라운드 + 진행 상황 가시화
- 큰 Phase 는 chunk 분할 후 ted-run 풀 파이프라인 (분석 chunk 는 ted-run 불필요)
- **scheduler_enabled 활성은 모든 작업 완료 후** (2026-05-11)

### 다음 세션 진입 시 결정 필요

다음 chunk 1순위 후보:

1. **ETF/ETN OHLCV 별도 endpoint** (옵션 c, 신규 도메인) — ETF/ETN 295 종목 (6.7%) 도 OHLCV 백테스팅 가치. 본 chunk 가드는 skip 만
2. KOSCOM cross-check 수동 — 가설 B 최종 확정 (1~2건 종목 dry-run cross-check)
3. Phase D — ka10080 분봉 / ka20006 업종일봉 (대용량 파티션 결정 선행)
4. Phase E (공매도/대차) / F (순위) / G (투자자별) — 신규 endpoint wave
5. (최종) scheduler_enabled 일괄 활성 + 1주 모니터 — 사용자 결정 (모든 작업 완료 후)

## Files Modified This Session (follow-up 분석 단독)

본 chunk (분석 only, 1 commit, push 보류):

```
docs/ADR/ADR-0001-backend-kiwoom-foundation.md          (§ 31 신규 6 sub-§)
src/backend_kiwoom/STATUS.md                             (§ 0 / § 4 4 항목 해소 표시 / § 5 follow-up 항목 제거 / § 6)
CHANGELOG.md                                              (follow-up entry prepend)
HANDOFF.md                                                (본 파일 전면 갱신)
```

코드 변경 0줄. 테스트 변화 없음 (1037 유지).

## 본 세션 누적 commits (push: 4 완료 / 1 보류)

```
8dd5727 ✅ refactor(kiwoom): Phase C-2δ — Migration 013 (C/E 중복 2 컬럼 DROP, 10→8 도메인) [pushed]
b75334c ✅ feat(kiwoom): Phase C-4 — ka10094 년봉 OHLCV (Migration 014, KRX only NXT skip) [pushed]
d43d956 ✅ refactor(kiwoom): Phase C-R2 — 1R Defer 5건 일괄 정리 [pushed]
d6357da ✅ docs(kiwoom): R2 후 backfill runbook resume 동작 설명 현행화 [pushed]
<this>  🆕 docs(kiwoom): follow-up F6/F7/F8 + daily_flow 빈 응답 통합 분석 (4건 NO-FIX, ADR § 31)
```
