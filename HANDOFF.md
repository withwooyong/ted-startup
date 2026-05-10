# Session Handoff

> Last updated: 2026-05-10 (KST) — ka10081/82/83 ETF/ETN 호환 가드 + smoke 통과
> Branch: `master`
> Latest commit (커밋 대기): `feat(kiwoom): ka10081/82/83 호환 stock_code 사전 가드 + smoke 통과 검증`
> 직전 푸시: `d60a9b3` — since_date guard fix

## Current Status

`backfill_ohlcv` smoke 운영 발견 #9 (ETF/ETN/우선주 영문 포함 stock_code) 정책 **(a) UseCase 가드** 채택 (사용자 결정). `IngestDailyOhlcvUseCase` / `IngestPeriodicOhlcvUseCase` 가 active stock 조회 후 `^[0-9]{6}$` 패턴 fullmatch 만 keep, skip 종목 수 + sample logger.info 로 가시성 확보. **smoke 완벽 통과** — 3 fix (since_date / max-stocks / ETF guard) 동시 작동 검증 (KOSPI 10 `--max-stocks` → ETF 4 skip → 호환 6 / 모두 success / 0 failed / 1초). 테스트 991 → 993.

## Completed This Session (커밋 대기)

| # | Task | 산출물 | Notes |
|---|------|--------|-------|
| 1 | **ETF 호환 가드 (daily)** | `app/application/service/ohlcv_daily_service.py` — `_KA10081_COMPATIBLE_RE` (`STK_CD_LOOKUP_PATTERN` 재사용) 사전 필터 + skip 로깅 | 호출 자체 차단 (build_stk_cd ValueError 회피) |
| 2 | **ETF 호환 가드 (periodic)** | `app/application/service/ohlcv_periodic_service.py` — daily 와 동일 (chart.py build_stk_cd 공유) | ka10082/83 도 동일 패턴 |
| 3 | 단위 테스트 +2 cases | `tests/test_ingest_daily_ohlcv_service.py` daily ETF skip / `tests/test_ohlcv_periodic_service.py` weekly ETF skip | ETF (`0000D0`) + 우선주 (`00088K`) 사전 skip 검증 |
| 4 | smoke 통과 검증 | `--period daily --years 1 --only-market-codes 0 --max-stocks 10` | 6/6 success / 4 ETF skip 로깅 / 1초. 3 fix (since_date / max-stocks / ETF guard) 동시 작동 |
| 5 | CHANGELOG / STATUS / HANDOFF 동시 갱신 | 3 문서 동시 갱신 | backend_kiwoom CLAUDE.md § 1 |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | 본 세션 산출물 커밋 + 푸시 | pending | 사용자 승인 후 |
| 2 | **mid (KOSPI 100/3년)** | not started | 다음 단계. 추정 ~30s × 100 = 5분 (페이지 1~2 + NXT) |
| 3 | **full (4078 호환/3년)** | not started | mid 통과 후. 추정 ~30분~1h |
| 4 | NUMERIC SQL 분포 측정 → ADR § 26.5 채움 | pending | full 완료 후 |
| 5 | ETF/ETN OHLCV 별도 endpoint (옵션 c) | pending | 본 chunk 의 가드는 skip 만. ETF 자체 OHLCV 가치 — 별도 chunk |

## Key Decisions Made

### ETF/ETN 정책: 옵션 (a) UseCase 가드 (사용자 결정)

| 옵션 | 채택 여부 | 사유 |
|------|----------|------|
| (a) UseCase 가드 + 가시성 | ✅ **채택** | Migration 0, 즉시 적용, 운영 실측 진입 우선 목표와 일치 |
| (b) Stock 테이블 호환 플래그 | 보류 | 명시적 도메인 모델 가치 vs 즉시 ROI |
| (c) ETF 전용 endpoint | 향후 별도 chunk | ETF 자체 OHLCV 가치 — 신규 도메인 chunk |

### 가드 패턴 — `STK_CD_LOOKUP_PATTERN` 재사용

`stkinfo.py` 의 public constant `STK_CD_LOOKUP_PATTERN` (= `^[0-9]{6}$`) 그대로 import. build_stk_cd 와 100% 동일 정규식 — 동일 출처 보장 (drift 차단).

### smoke 완벽 통과 — 3 fix 누적 검증

```
ka10081 호환 가드 — active 10 중 4 종목 skip (ETF/ETN/우선주 추정),
  sample=['0000D0', '0000H0', '0000J0', '0000Y0']
total: 6 / success_krx: 6 / success_nxt: 2 / failed: 0 / elapsed: 1s
```

직전 3 chunk (since_date / max-stocks / ETF guard) 가 함께 작동. mid → full 진입 준비 완료.

## Known Issues

- (해소) since_date guard, max-stocks fix, ETF stock_code 가드 모두 ✅
- **ETF/ETN OHLCV 자체** — 본 chunk 의 가드는 skip 만. ETF/ETN 도 백테스팅 가치 있어 향후 별도 endpoint chunk 필요 (옵션 c)

## Context for Next Session

### 사용자의 원래 의도

1순위 → 2순위 → smoke 재시도 → mid → full 흐름. 본 chunk 가 2순위 (ETF) + smoke 완료. 다음은 mid (KOSPI 100/3년) → full.

### 선택된 접근 + 이유

- **옵션 (a) UseCase 가드** — Migration 0 + 즉시 적용. ETF OHLCV 는 별도 chunk
- **`STK_CD_LOOKUP_PATTERN` 재사용** — build_stk_cd 와 동일 정규식 single source

### 사용자 제약 / 선호

- 한글 커밋 메시지
- 푸시 명시적 요청 시만
- backend_kiwoom CLAUDE.md § 1 — STATUS / HANDOFF / CHANGELOG 동시 갱신
- 운영 검증 chunk 분리 패턴 유지

### 다음 세션 진입 시 결정 필요

본 chunk commit 후:
1. **mid (KOSPI 100/3년)** 진입 — `--max-stocks 100 --years 3 --only-market-codes 0 --log-level INFO`. 추정 5분
2. mid 통과 시 → full (`--years 3` 전체) 진입. 추정 30분~1h. 백그라운드 실행 고려
3. full 완료 후 NUMERIC SQL 분포 측정 → ADR § 26.5 갱신

## Files Modified This Session (커밋 대기)

```
src/backend_kiwoom/app/application/service/ohlcv_daily_service.py     (수정 — ETF 가드 + import re/STK_CD_LOOKUP_PATTERN)
src/backend_kiwoom/app/application/service/ohlcv_periodic_service.py  (수정 — 동일)
src/backend_kiwoom/tests/test_ingest_daily_ohlcv_service.py            (수정 — +1 case)
src/backend_kiwoom/tests/test_ohlcv_periodic_service.py                (수정 — +1 case)
src/backend_kiwoom/STATUS.md                                          (수정)
CHANGELOG.md                                                          (수정 — prepend)
HANDOFF.md                                                            (본 파일)
```

총 7 파일 / 수정 7 / 약 +130 줄
