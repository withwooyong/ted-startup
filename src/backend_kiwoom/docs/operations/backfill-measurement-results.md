# 운영 실측 결과 — OHLCV 3년 백필

> **상태**: ✅ **측정 완료** (2026-05-10)
> **측정자**: Ted (로컬 docker-compose)
> **측정일**: 2026-05-10 (KST)
> **참조**: `backfill-measurement-runbook.md` (절차) / `scripts/backfill_ohlcv.py` (CLI)
> **운영 환경**: docker-compose 5433 / 운영 키움 (alias=prod) / NXT_COLLECTION_ENABLED=true

---

## 0. 요약 (TL;DR)

3년 KRX+NXT daily 백필이 **34분** (active 4078 호환 / 0 failed) 으로 dry-run 추정 4시간보다 빠르게 완료. ka10081 NUMERIC(8,4) `turnover_rate` 의 max 3,257.80 (cap 33%) — 마이그레이션 불필요. 운영 차단/사용성 buffers 3건 발견·즉시 fix (`since_date` guard / `--max-stocks` CLI / ETF 호환 가드 = 295 종목 6.7% skip).

---

## 1. 운영 환경 정보

| 항목 | 값 |
|------|-----|
| 측정 시점 | 2026-05-10 13:38 ~ 14:12 KST (full backfill) |
| KIWOOM_DEFAULT_ENV | prod |
| NXT_COLLECTION_ENABLED | true |
| KIWOOM_MIN_REQUEST_INTERVAL_SECONDS | 0.25 (기본) |
| active stock 수 | KOSPI 2031 / KOSDAQ 1823 / KONEX 110 / ETF 25 / ETN 384 = **4373** (호환 4078) |
| DB 마이그레이션 head | 012_stock_price_monthly_nxt |
| 백필 CLI commit | `c75ede6` (since_date + max-stocks + ETF guard 누적) |

---

## 2. 단계별 실측

### 2.1 Stage 0 — Dry-run

| Period | --years | active | NXT | total_calls | estimated |
|--------|---------|--------|-----|-------------|-----------|
| daily | 3 | 4373 | enabled | 17,492 | 1h 12m 53s |

> dry-run 추정값 (lower-bound). 실측은 다음 단계.

---

### 2.2 Stage 1 — Smoke (KOSPI 10 / 1년)

| 항목 | 값 |
|------|-----|
| 명령어 | `--period daily --years 1 --max-stocks 10 --only-market-codes 0` |
| total | **6** (raw 10 → ETF 4 skip → 호환 6) |
| success_krx / success_nxt / failed | 6 / 2 / 0 |
| elapsed | 1s |
| avg/stock | 0.3s |
| pages observed | 1 페이지 (since_date guard 작동) |

**관찰**:
- 인증 정상, DB upsert 성공, max_pages 초과 0건
- ka10081 호환 가드 로깅: `active 10 중 4 종목 skip (ETF/ETN/우선주 추정), sample=['0000D0', '0000H0', '0000J0', '0000Y0']`

---

### 2.3 Stage 2 — Mid (KOSPI 100 / 3년)

| 항목 | 값 |
|------|-----|
| 명령어 | `--period daily --years 3 --max-stocks 100 --only-market-codes 0` |
| total | **78** (raw 100 → ETF 22 skip → 호환 78) |
| success_krx / success_nxt / failed | 78 / 21 / 0 |
| elapsed | 44s |
| avg/stock | 0.6s |
| failure_ratio | 0% |

**dry-run 비교**: 추정 약 5분 → 실측 44s → **8.5x 빠름** (since_date guard 가 page 1~2 안에서 종료, dry-run 의 lower-bound 는 KOSPI 전체 평균이라 KOSPI 100 에 과대추정)

---

### 2.4 Stage 3 — Full (active 4078 호환 / 3년)

| 항목 | 값 |
|------|-----|
| 명령어 | `--period daily --years 3 --alias prod` |
| total | **4078** (active 4373 - ETF 295) |
| success_krx / success_nxt / failed | 4078 / 626 / 0 |
| elapsed | **34분** (33m 59s) |
| avg/stock | 0.5s |
| failure_ratio | **0.00%** |
| resume 사용 여부 | no |

**상위 실패 원인 (top 5)**: **0건 — 실패 없음**

**dry-run 비교**: 추정 1h 13m → 실측 34m → **2.1x 빠름**

---

### 2.5 Stage 3' — Weekly / Monthly

> 본 chunk 미수행. weekly/monthly 백필은 별도 chunk 또는 운영 cron 의 자동 트리거 (금 19:30 / 매월 1일 03:00) 로 적재.

---

## 3. 측정 #1 — 페이지네이션 빈도

**가설**: 1 페이지 ~600 거래일 → 3년 (~750 거래일) → 종목당 2 페이지.

**실측**:
- 1년 daily (smoke): 종목당 **1 페이지** (since_date 가 page 1 안에서 break)
- 3년 daily (full): 종목당 **1~2 페이지** (avg 0.5s/stock)
- 6 페이지 이상 종목: 0 (since_date guard 적용 후 — 적용 전엔 동일제강 같은 1980 상장 종목이 max_pages=10 도달)

**가설 vs 실측**: 1년 가설 부정확 (가설 1 페이지 추정도 가능했음), 3년 가설 일치 (1~2 페이지)

---

## 4. 측정 #2 — 3년 백필 elapsed (active 4078 호환)

**가설** (dry-run lower-bound):
- KRX+NXT: 약 1h 13m (estimated)

**실측**:
| 시나리오 | elapsed | avg/stock | 비고 |
|----------|---------|-----------|------|
| KRX 4078 + NXT 626 | **34분** | 0.5s | failed 0 |

**±50% margin 안인지**: 추정 1h 13m → 실측 34m. dry-run 보다 **빠름** (margin 안). NXT 활성 종목이 626 (15%) 만이라 실 호출 수가 추정 17,492 (전체 NXT 가정) 보다 적음
**margin 안 측 원인 분석**:
- since_date guard 로 page 1~2 종료 (dry-run 은 page 2 가정)
- NXT 비율 15% (dry-run 100% 가정)
- 5xx 재시도 0 (안정적 시간대 — 일요일 비거래일)

---

## 5. 측정 #3 — NUMERIC(8,4) magnitude 분포

**측정 대상 한정**: ka10081 의 NUMERIC(8,4) = `turnover_rate` 1개. `change_rate` / `foreign_holding_ratio` / `credit_ratio` 는 ka10086 (daily_flow) 컬럼 — daily_flow 백필 chunk 에서 측정.

**실측 — turnover_rate** (`stock_price_krx`):

| 항목 | 값 |
|------|-----|
| rows | 2,732,031 |
| min_pct | -57.32 (음수 anomaly — F7 분석 완료 ADR § 31: 키움 raw 보존 NO-FIX) |
| max_pct | **3,257.80** |
| avg_pct | 1.67 |
| p01 | 0.00 |
| p99 | 25.93 |
| count(\|turnover_rate\| > 100) | 2,793 (0.10%) |
| count(\|turnover_rate\| > 1000) | 24 (0.0009%) |

**가설 vs 실측**:
- overflow (> NUMERIC(8,4) ±9999.9999): **0건**
- max 3,257.80 = cap 의 33% — 안전 마진 충분
- 음수 -57.32 anomaly: 키움 데이터 특성 (수정주가 조정 추정). F7 분석 완료 (ADR § 31) — 키움 raw 그대로 보존 (정직성). 분석 시 0/NaN/MAX(0,x) 처리는 분석 layer 책임

**대응 결정**: 마이그레이션 불필요. `change_rate` 등은 daily_flow 측정 후 결정.

---

## 6. 측정 #4 — 일간 cron 실측

> 본 chunk 미수행 — `scheduler_enabled=true` 활성화 후 운영 cron 1일치 sync 실 측정 필요. backfill 적용된 since_date=None 디폴트 동작이 1 페이지 종료 가정 (cron 실측에서 검증).

---

## 7. 5xx 재시도 비율 / 네트워크 안정성

| 시간대 | 5xx 카운트 | 재시도 성공 | 영구 실패 |
|--------|-----------|----------|----------|
| 일요일 13:38~14:12 KST (비거래) | 0 | - | 0 |

> 평일 거래 시간대 (09:00~15:30) 운영 cron 측정은 별도

---

## 8. 새로 발견된 위험 / 후속 chunk 후보

| # | 항목 | 심각도 | 근거 | 후속 chunk |
|---|------|--------|------|-----------|
| 1 | ETF/ETN OHLCV 자체 sync | LOW | 본 chunk 가드는 skip 만. ETF 백테스팅 가치 (옵션 c) | 신규 endpoint chunk |
| ~~2~~ | ~~`since_date` guard edge case (F6)~~ | LOW | ~~4078 중 2 종목 (`002690`, `004440`) / 0.13%~~ | ✅ 분석 완료 (ADR § 31, `e8d9d38`) — **NO-FIX** (1980s 상장 page 단위 break row 잔존 / 데이터 가치 ≥ 비용) |
| ~~3~~ | ~~turnover_rate 음수 anomaly (F7)~~ | LOW | ~~min -57.32 — 회전율 음수~~ | ✅ 분석 완료 (ADR § 31, `e8d9d38`) — **NO-FIX** (키움 raw 보존 정직성 / 0.0009% / 분석 layer 책임) |
| ~~4~~ | ~~1 종목 빈 응답 (4078 fetch / 4077 적재)~~ | LOW | ~~full backfill 결과 1 종목 row 0~~ | ✅ 식별 + 분석 완료 (ADR § 31, `e8d9d38`) — **`452980` 신한제11호스팩** (KOSDAQ SPAC, 2026-05-09 등록, 신규 상장 직후) / sentinel 가드 정상 / **NO-FIX** |
| 5 | 일간 cron 실측 미완 | MEDIUM | 운영 cron 시간 예산 미정 | scheduler_enabled 활성화 chunk |

---

## 9. 결정 사항

본 실측 결과로 확정된 결정:

1. **NUMERIC(8,4) 컬럼 마이그레이션 불필요** — turnover_rate max 3,257.80 (cap 33%)
2. **NXT 수집 prod 활성** — `NXT_COLLECTION_ENABLED=true` 작동 검증 (626 종목 sync)
3. **3년 백필 시간 예산 ~ 34분** — daily_flow 백필도 유사 범위 추정
4. **ETF/ETN 정책 (a) 채택** — UseCase 가드 + 향후 별도 endpoint chunk

---

## 10. 다음 chunk 우선순위 갱신

| 순위 | chunk | 변경 사유 |
|------|-------|----------|
| ~~1~~ | ~~daily_flow (ka10086) 백필 CLI~~ | ✅ 완료 (`23f601b`, `4e75dd3`) — NUMERIC 4 컬럼 마이그레이션 불필요 / KRX 4077 / NXT 626 |
| ~~3~~ | ~~follow-up F6/F7/F8 일괄 분석~~ | ✅ 완료 (`e8d9d38`, ADR § 31) — 4건 NO-FIX / 452980 식별 |
| ~~5~~ | ~~refactor R2 (1R Defer 일괄)~~ | ✅ 완료 (`d43d956`, ADR § 30) — 5건 / 1037 tests / coverage 81.15% |
| ~~6~~ | ~~ka10094 (년봉, P2)~~ | ✅ 완료 (`b75334c`, ADR § 29) — Migration 014 / 11/25 endpoint |
| 1 | ETF/ETN OHLCV 별도 endpoint (옵션 c) | 백테스팅 데이터 가치 확보 |
| 2 | scheduler_enabled 운영 cron 활성 + 1주 모니터 | 측정 #4 (일간 cron elapsed) 미완. **사용자 결정: 모든 작업 완료 후** |

---

## 11. ADR § 26 승격

본 results.md 의 핵심 발견 → ADR `§ 26.5` 표 갱신 완료 (chunk `<this commit>`).

ADR 갱신 항목:
- 26.5 표 4건 모두 측정값 채움
- 26.5 후속 신규 운영 발견 3건 (since_date / max-stocks / ETF guard) 기록
- 26.5 follow-up F6 (since_date edge case) 기록
- 26.5 KRX/NXT 적재 통계 추가
