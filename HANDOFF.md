# Session Handoff

> Last updated: 2026-05-10 (KST) — backfill_ohlcv smoke 실 호출 + since_date guard fix
> Branch: `master`
> Latest commit (커밋 대기): `fix(kiwoom): backfill_ohlcv 페이지네이션 종료 조건 신규 + dotenv autoload 보강`
> 직전 푸시: `ba531d9` — CHANGELOG 누락 보정

## Current Status

**backfill_ohlcv.py 첫 실 smoke** 에서 **운영 차단 버그 1건 발견·수정**. `KiwoomChartClient.fetch_daily/weekly/monthly` 가 base_dt 만 받고 종료 범위 없어 종목 상장일까지 무한 페이징 → max_pages 도달로 fail (KOSPI 1980년대 상장 종목 영향). **`since_date` 파라미터 신규** + UseCase + CLI 전파. 동시에 `backfill_ohlcv.py` dotenv autoload 누락 (직전 세션 register/sync 만 적용) 보완. 테스트 988 → 990. 실 호출 KOSPI 1782 success / 8m 55s / max_pages 초과 0건.

## Completed This Session (커밋 대기)

| # | Task | 산출물 | Notes |
|---|------|--------|-------|
| 1 | **since_date guard fix** (운영 차단) | `app/adapter/out/kiwoom/chart.py` (fetch_daily/weekly/monthly + helper 2 static method) | 페이지의 가장 오래된 row date <= since_date 면 다음 page 요청 중단. mock 테스트가 못 잡은 이유: cont-yn=N 으로 짧게 종료하는 fixture 만 사용 |
| 2 | UseCase 시그니처 전파 | `app/application/service/ohlcv_daily_service.py` (execute / _ingest_one), `app/application/service/ohlcv_periodic_service.py` (동일) | 디폴트 None → 운영 cron 호환 (기존 1 page 종료 동작) |
| 3 | CLI 전달 | `scripts/backfill_ohlcv.py` (since_date=start_date) | `--years 3` / `--start-date` 가 실질적 페이지네이션 cap 으로 작동 |
| 4 | dotenv autoload 누락 보완 | `scripts/backfill_ohlcv.py` (register/sync 와 동일 패턴) | 직전 세션 admin 도구 보강에서 backfill 만 누락 |
| 5 | 단위 테스트 +2 cases | `tests/test_kiwoom_chart_client.py` since_date page break / since_date=None 기존 동작 유지 | mock 시그니처에 since_date 인자 추가 (`tests/test_ingest_daily_ohlcv_service.py` _fetch stub 2곳) |
| 6 | CHANGELOG / STATUS / HANDOFF 동시 갱신 | 3 문서 동시 갱신 | backend_kiwoom CLAUDE.md § 1 |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | 본 세션 산출물 커밋 + 푸시 | pending | 사용자 승인 후 — 한 commit 통합 |
| 2 | **CLI bug fix**: `--max-stocks` 무시 | pending | 신규 발견 — effective_stock_codes 가 max_stocks 미반영. 다음 chunk |
| 3 | **ETF/ETN stock_code 호환성**: 251 종목 ValueError | pending | 신규 발견 — `0000D0` 같은 영문 코드. 정책 결정 필요 (skip vs 별도 endpoint) |
| 4 | mid-scale (KOSPI 100 / 3년) → full | not started | --max-stocks fix 후 진입 |
| 5 | ADR § 26.5 채움 | pending | 본 chunk 의 정량화 결과 (1 page / 0.3s/stock) 기록 |

## Key Decisions Made

### 운영 차단 버그 발견·수정 — `since_date` guard

| 항목 | 내용 |
|------|------|
| 발견 시점 | smoke 첫 호출 (`002810` KOSPI 1980년대 상장) — 4분 / 8.8MB DEBUG 로그 |
| 증상 | `next-key` 응답이 `2006/06 → 2004/06 → 2002/01` 과거로 거슬러 → max_pages=10 도달 → `KiwoomMaxPagesExceededError` |
| 원인 | ka10081 응답이 base_dt 부터 종목 상장일까지 무한 페이징. 종료 조건 = (cont-yn=N) 또는 (max_pages 도달) 만 존재 |
| Fix | 페이지의 가장 오래된 row date <= since_date 면 break. since_date=None (디폴트) 면 기존 동작 유지 (운영 cron 1 page 종료 호환) |
| 검증 | KOSPI 2031 종목 / 1782 success / 0 max_pages 초과 / avg 0.3s/stock |

### Mock 테스트의 한계 (직전 세션 패턴 재현)

- 직전 세션: `next-key=""` 빈값 reject (`_client.py`) — mock 응답이 항상 non-empty 사용해서 못 잡음
- 본 세션: `since_date` 종료 조건 누락 — mock 응답이 cont-yn=N 으로 짧게 종료해서 못 잡음
- **공통**: 운영 실측의 가치 입증. 모든 endpoint 가 같은 chart.py 사용 → 백필 cron 도 차단 상태였을 것

### 단일 commit 결정

since_date fix + dotenv autoload + 테스트 + 문서 갱신을 **한 commit 으로 통합** (사용자 결정 1번). 맥락 일관: smoke 진입 → fix → 검증.

### 신규 발견 분리 (다음 chunk)

- `--max-stocks 10` 무시 bug → 다음 chunk
- 251 ETF/ETN ValueError → 다음 chunk + 정책 결정

## Known Issues

- **`--max-stocks` 가 실제 백필에서 무시됨** — `effective_stock_codes` 가 only_stock_codes 만 반영. CLI bug. 다음 chunk
- **ETF/ETN stock_code 호환성** — `kiwoom.stock` 의 모든 active 가 ka10081 호환 가정이 틀림. 영문 포함 코드 (예: `0000D0`) 는 build_stk_cd 의 6자리 ASCII 숫자 검증에서 ValueError. 정책 옵션: (a) ka10081 호출 전 stock_code 가드로 skip / (b) 별도 ETF endpoint / (c) Stock 테이블에 ka10081 호환 플래그 컬럼
- **다른 endpoint 도 동일 since_date 미적용** — ka10081/82/83 만 fix. ka10086 (수급), ka10001 (펀더멘털) 등은 단일 페이지라 영향 없음 (확인 필요)

## Context for Next Session

### 사용자의 원래 의도

backfill_ohlcv.py 실측 진입 (1순위) → smoke → mid → full 단계. 본 chunk 가 smoke 단계에서 발견된 운영 차단 fix.

### 선택된 접근 + 이유

- **since_date 옵션 추가** — caller (CLI) 가 백필 하한일 명시. 운영 cron 기존 동작 (since_date=None) 유지로 회귀 0
- **3 메서드 일괄 적용** — fetch_daily / weekly / monthly 모두 같은 함정. helper 메서드 추출 (`_page_reached_since`, `_row_on_or_after`) 로 중복 차단
- **dotenv autoload 동시 보완** — register/sync 와의 일관성. smoke 진입 차단 (KIWOOM_DATABASE_URL 미로드) 도 같이 해소

### 사용자 제약 / 선호

- 한글 커밋 메시지
- 푸시 명시적 요청 시만
- backend_kiwoom CLAUDE.md § 1 — STATUS / HANDOFF / CHANGELOG 동시 갱신
- 진행 중 발견된 새 운영 이슈는 **다음 chunk 로 분리** (현재 chunk 마무리 우선) — 본 세션 결정

### 다음 세션 진입 시 결정 필요

본 chunk commit 후:

1. **CLI bug fix**: `--max-stocks` 가 effective_stock_codes 에 반영되도록 (1순위 — 빠른 fix)
2. **ETF/ETN 정책 결정** + 적용 (2순위 — 정책 + 코드)
3. **smoke 재시도** — `--max-stocks 10` 정상 작동 검증 → mid (100/3년) → full

## Files Modified This Session (커밋 대기)

```
src/backend_kiwoom/app/adapter/out/kiwoom/chart.py                     (수정 — fetch_daily/weekly/monthly + 2 helper)
src/backend_kiwoom/app/application/service/ohlcv_daily_service.py     (수정 — execute / _ingest_one since_date)
src/backend_kiwoom/app/application/service/ohlcv_periodic_service.py  (수정 — 동일)
src/backend_kiwoom/scripts/backfill_ohlcv.py                          (수정 — dotenv + since_date 전달)
src/backend_kiwoom/tests/test_kiwoom_chart_client.py                   (수정 — +2 since_date cases)
src/backend_kiwoom/tests/test_ingest_daily_ohlcv_service.py            (수정 — _fetch stub 시그니처)
src/backend_kiwoom/STATUS.md                                          (수정)
CHANGELOG.md                                                          (수정 — prepend)
HANDOFF.md                                                            (본 파일)
```

총 9 파일 / 수정 9 / 약 +200 줄
