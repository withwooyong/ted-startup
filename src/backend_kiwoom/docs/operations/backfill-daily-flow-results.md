# 운영 실측 결과 — daily_flow (ka10086) 3년 백필

> **상태**: 🔄 **부분 측정** (Stage 0 dry-run + Stage 1 smoke + MAX_PAGES fix 완료, mid~full 대기)
> **측정자**: Ted (dry-run/smoke: Claude assist)
> **측정일**: 2026-05-10 (Stage 0 dry-run / Stage 1 smoke + MAX_PAGES fix) / mid~full TBD
> **참조**: `backfill-daily-flow-runbook.md` (절차) / `scripts/backfill_daily_flow.py` (CLI)
> **운영 환경**: docker-compose 5433 / 운영 키움 (alias=prod) / NXT_COLLECTION_ENABLED=true

---

## 0. 요약 (TL;DR — 부분 채움)

Stage 0 dry-run + Stage 1 smoke 완료. **smoke 첫 시도에서 신규 운영 차단 1건 발견 → 즉시 fix**:

- **`DAILY_MARKET_MAX_PAGES = 10` 부족** — 가설 "1 page ~300 거래일" 실측 ~22 거래일 (13배 틀림). 1년 백필 = 약 12 page 필요 → max_pages 도달 fail
- **fix**: `MAX_PAGES = 10 → 40` (3년 ≈ 32 page + 안전 마진 8)
- **smoke 재시도 PASS**: total 6 / failed 0 / 25s
- 사전 적용 fix 패턴 검증: ✅ max-stocks / ✅ ETF guard / ⚠ since_date (logic 정상, max_pages 부족으로 도달 전 abort)

mid + full + NUMERIC SQL TBD.

---

## 1. 운영 환경 정보

| 항목 | 값 |
|------|-----|
| 측정 시점 (dry-run) | 2026-05-10 17:43 KST |
| 측정 시점 (full backfill) | TBD |
| KIWOOM_DEFAULT_ENV | prod |
| NXT_COLLECTION_ENABLED | true (dry-run 출력 "NXT collection: enabled") |
| KIWOOM_MIN_REQUEST_INTERVAL_SECONDS | 0.25 (기본) |
| INDC_MODE | quantity (기본) |
| active stock 수 | **4373** (kiwoom.stock.is_active=true / 5 시장 모두 — dry-run 출력) |
| DB 마이그레이션 head | 012_stock_price_monthly_nxt |
| 백필 CLI commit | `23f601b` (since_date + max-stocks + ETF guard 사전 적용) |

---

## 2. 단계별 실측

### 2.1 Stage 0 — Dry-run (2026-05-10 17:43 KST, ✅ 완료)

| --years | active | NXT | exchanges/stock | pages/call | total_calls | rate_limit | estimated |
|---------|--------|-----|-----------------|------------|-------------|------------|-----------|
| 3 | **4373** | enabled | 2 | **4** | **34,984** | 0.25s | **2h 25m 46s** |

**관찰**:
- `pages/call=4` — ka10086 1 page ~300 거래일 가정 (1095 days / 300 = 3.65 → ceil 4)
- `total_calls=34,984` = 4373 × 2 × 4
- `estimated=2h 25m 46s` = 34,984 × 0.25s = 약 8,746s

**OHLCV 대비** (§ 12 cross-check 첫 데이터):
| 항목 | OHLCV daily | daily_flow |
|------|-------------|------------|
| active | 4373 | 4373 (동일) |
| pages/call (dry-run) | 2 | **4** (2x) |
| total_calls (dry-run) | 17,492 | **34,984** (2x) |
| estimated | 1h 12m 53s | **2h 25m 46s** (2x) |
| 실측 | **34분** (2.1x 빠름) | TBD |

> 가설: since_date guard 가 page 1~2 안에서 break → 실측은 dry-run 의 50% 미만 추정. OHLCV 패턴 (2.1x 빠름) 적용 시 daily_flow 실측 약 1h 10m 추정.

> dry-run 추정값 (lower-bound). 실측은 다음 단계 (smoke → mid → full).

---

### 2.2 Stage 1 — Smoke (KOSPI 10 / 1년)

#### 첫 시도 (2026-05-10 18:01 KST) — ❌ **운영 차단 발견**

| 항목 | 값 |
|------|-----|
| 명령어 | `--years 1 --max-stocks 10 --only-market-codes 0 --log-level DEBUG` |
| total | 6 (raw 10 → ETF 4 skip → 호환 6) |
| success_krx / success_nxt / failed | 0 / 0 / **8** (ratio 133%) |
| elapsed | 19s |
| 차단 원인 | **`KiwoomMaxPagesExceededError` 8건 — `DAILY_MARKET_MAX_PAGES = 10` 초과** |

**근본 원인 (next-key 헤더 추적)**:
- p1 next=20260108 → p2 base 2026-01-08 (응답 가장 과거 ≈ 2026-01-09, ~80 거래일/page)
- p2~p7 next-key 진행: 20251208 → 20251110 → 20251013 → 20250908 → 20250810 → 20250713
- p2~ 평균 1 page ≈ **22 거래일** (월 단위)
- 1년 (250 거래일) 도달 = 약 12 page 필요 → max_pages=10 부족
- **계획서 § 12.7 가설 "1 page ~300 거래일" 13배 틀림** (mrkcond.py:50 주석)

**fix 패턴 사전 적용 검증 부분 결과**:
- ✅ `--max-stocks` CLI fix 작동 (raw 10 → 호환 6 정상 — active 전체 호출 안 됨)
- ✅ ETF/ETN 호환 가드 작동 (`_KA10086_COMPATIBLE_RE` skip 4 종목)
- ❌ since_date guard — logic 자체 정상이지만 max_pages=10 한계로 도달 전 abort

#### 즉시 fix (2026-05-10 18:24 KST, `<this commit>`)

```python
# mrkcond.py:50 변경
- DAILY_MARKET_MAX_PAGES = 10  # ~300 거래일 추정 (가설)
+ DAILY_MARKET_MAX_PAGES = 40  # 실측 ~22 거래일/page → 3년 ≈ 32 page (안전 마진 8)
```

#### 재시도 (2026-05-10 18:25 KST) — ✅ **PASS**

| 항목 | 값 |
|------|-----|
| 명령어 | `--years 1 --max-stocks 10 --only-market-codes 0 --log-level INFO` |
| total | **6** (raw 10 → ETF 4 skip → 호환 6) |
| success_krx / success_nxt / failed | **6 / 2 / 0** (ratio 0%) |
| elapsed | **25s** |
| avg/stock | 4.2s |
| pages observed | 1년 백필 시 종목당 ~12 page (KRX) + ~5 page (NXT) |

**관찰**:
- 인증 정상 / DB upsert 성공 / max_pages 초과 0건
- since_date guard 정상 작동 — 12 page 도달 시 break (max_pages=40 한계 못 미침)
- NXT 활성 6 종목 중 2 종목만 적재 (NXT 출범 2025-03-04 이후 종목)

---

### 2.3 Stage 2 — Mid (KOSPI 100 / 3년)

| 항목 | 값 |
|------|-----|
| 명령어 | `--years 3 --max-stocks 100 --only-market-codes 0` |
| total | TBD (raw 100 → ETF skip TBD → 호환 TBD) |
| success_krx / success_nxt / failed | TBD / TBD / TBD |
| elapsed | TBD |
| avg/stock | TBD |
| failure_ratio | TBD |

**dry-run 비교**: 추정 TBD → 실측 TBD → TBD x

---

### 2.4 Stage 3 — Full (active 4078 호환 / 3년)

| 항목 | 값 |
|------|-----|
| 명령어 | `--years 3 --alias prod` |
| total | TBD |
| success_krx / success_nxt / failed | TBD / TBD / TBD |
| elapsed | TBD |
| avg/stock | TBD |
| failure_ratio | TBD |
| resume 사용 여부 | TBD |

**상위 실패 원인 (top 5)**: TBD

**dry-run 비교**: 추정 TBD → 실측 TBD → TBD x

---

### 2.5 indc_mode amount 옵션 검증 (선택)

> `--indc-mode amount` 로 일부 종목 cross-check 수행 시 결과 기록. quantity 와 row 수 / NUMERIC 분포 비교.

| 항목 | quantity | amount |
|------|----------|--------|
| total | TBD | TBD |
| 평균 individual_net | TBD (수량) | TBD (백만원) |
| 평균 foreign_volume | TBD (수량) | TBD (백만원) |

---

## 3. 측정 #1 — 페이지네이션 빈도

**가설** (ADR § 27.4): ka10086 22 필드 → 1 page ~300 거래일 → 3년 (~750 거래일) → 종목당 2~3 페이지.

**실측**:
- 1년 daily (smoke): 종목당 TBD 페이지
- 3년 daily (full): 종목당 TBD 페이지
- 5 페이지 이상 종목: TBD건

**가설 vs 실측**: TBD

**OHLCV 비교**: OHLCV (ka10081) 는 1 page ~600 거래일 → 1~2 페이지. ka10086 는 더 많은 컬럼 (22 vs 8) 으로 page row 수 적어 페이지 더 많음 — 검증 결과 TBD

---

## 4. 측정 #2 — 3년 백필 elapsed (active 4078 호환)

**가설** (dry-run lower-bound):
- KRX+NXT: TBD

**실측**:
| 시나리오 | elapsed | avg/stock | 비고 |
|----------|---------|-----------|------|
| KRX 4078 + NXT TBD | TBD | TBD | failed TBD |

**±50% margin 안인지**: TBD
**margin 안 측 / 밖 측 원인 분석**: TBD

**OHLCV 대비**: OHLCV 34분 (페이지 1~2) → daily_flow TBD분 (페이지 TBD)

---

## 5. 측정 #3 — NUMERIC(8,4) magnitude 분포

**측정 대상** (`stock_daily_flow` 의 NUMERIC(8,4) 4 컬럼):
- `credit_rate` (신용 비율)
- `credit_balance_rate` (신용 잔고율)
- `foreign_rate` (외인 비율)
- `foreign_weight` (외인 비중 — 0~100% 가정)

### 5.1 credit_rate

| 항목 | 값 |
|------|-----|
| rows | TBD |
| min | TBD |
| max | TBD |
| p01 | TBD |
| p99 | TBD |
| count(\|x\| > 100) | TBD |
| count(\|x\| > 1000) | TBD |

### 5.2 credit_balance_rate

| 항목 | 값 |
|------|-----|
| rows | TBD |
| min | TBD |
| max | TBD |
| p01 | TBD |
| p99 | TBD |
| count(\|x\| > 100) | TBD |
| count(\|x\| > 1000) | TBD |

### 5.3 foreign_rate

| 항목 | 값 |
|------|-----|
| rows | TBD |
| min | TBD |
| max | TBD |
| p01 | TBD |
| p99 | TBD |
| count(\|x\| > 100) | TBD |
| count(\|x\| > 1000) | TBD |

### 5.4 foreign_weight

| 항목 | 값 |
|------|-----|
| rows | TBD |
| min | TBD |
| max | TBD |
| p01 | TBD |
| p99 | TBD |
| count(\|x\| > 100) | TBD |

### 5.5 가설 vs 실측

- overflow (> NUMERIC(8,4) ±9999.9999): TBD건
- max 컬럼별 TBD = cap 의 TBD %
- 마이그레이션 결정: TBD (gt_100 > 0 또는 gt_1000 > 0 시 NUMERIC 확장 chunk)

### 5.6 exchange 별 cross-check

| exchange | rows | stocks | max foreign_weight | max foreign_rate | max credit_rate |
|----------|------|--------|--------------------|--------------------|-----------------|
| KRX | TBD | TBD | TBD | TBD | TBD |
| NXT | TBD | TBD | TBD | TBD | TBD |

---

## 6. 측정 #4 — 일간 cron 실측

> 본 chunk 미수행 — `scheduler_enabled=true` 활성화 후 daily_flow 운영 cron (`daily_flow_sync_daily`, KST mon-fri 19:00) 1일치 sync 실 측정 필요. HANDOFF Pending #2 와 결합.

---

## 7. 5xx 재시도 비율 / 네트워크 안정성

| 시간대 | 5xx 카운트 | 재시도 성공 | 영구 실패 |
|--------|-----------|----------|----------|
| TBD | TBD | TBD | TBD |

---

## 8. since_date guard edge case cross-check (OHLCV F6 비교)

OHLCV 백필에서 발견된 edge case — since_date (3년 전) 보다 과거 row 적재 종목 (`002690` / `004440`).

**daily_flow 에서의 결과**:

| stock_code | stock_name | OHLCV 결과 (oldest_dt) | daily_flow 결과 (oldest_dt) |
|------------|-----------|------------------------|------------------------------|
| 002690 | 동일제강 | 2015-09-24 | TBD |
| 004440 | 삼일씨엔에스 | 2016-03-30 | TBD |

**추가 발견 종목**: TBD

**해석**: TBD (mrkcond `_page_reached_since_market` 로직이 chart.py 패턴 1:1 인지 검증)

---

## 9. 새로 발견된 위험 / 후속 chunk 후보

(측정 후 채움 — OHLCV § 8 패턴)

| # | 항목 | 심각도 | 근거 | 후속 chunk |
|---|------|--------|------|-----------|
| 1 | TBD | TBD | TBD | TBD |

---

## 10. 결정 사항

(측정 후 채움)

본 실측 결과로 확정된 결정:

1. NUMERIC(8,4) 컬럼 4 — TBD (마이그레이션 필요/불필요)
2. NXT 수집 prod 활성 검증 — TBD
3. 3년 백필 시간 예산 — TBD분
4. ETF/ETN 정책 (a) (사전 적용 가드) 검증 — TBD

---

## 11. 다음 chunk 우선순위 갱신

(측정 후 채움)

| 순위 | chunk | 변경 사유 |
|------|-------|----------|
| 1 | TBD | TBD |

---

## 12. ADR § 27 승격

본 results.md 의 핵심 발견 → ADR `§ 27.5` 표 갱신 (chunk `<측정 commit>`).

ADR 갱신 항목:
- 27.5 표 4건 모두 측정값 채움
- 27.5 신규 운영 발견 (있으면) 기록
- 27.5 follow-up (since_date edge / 빈 응답 / NUMERIC overflow 등) 기록
- 27.5 KRX/NXT 적재 통계 추가

---

## 13. 운영 차단 fix 패턴 사전 적용 검증 결과 (ADR § 27.6 cross-check)

OHLCV 백필 (`d60a9b3`/`76b3a4a`/`c75ede6`) 에서 발견된 운영 차단 3건이 daily_flow 에서 처음부터 fix 패턴 사전 적용된 효과:

| # | 운영 차단 | OHLCV 발견 단계 | daily_flow 효과 (실측) |
|---|----------|----------------|---------------------|
| 1 | since_date guard 누락 → max_pages 도달 | smoke (1980 상장 종목) | TBD (smoke 단계에서 max_pages 초과 0 기대) |
| 2 | `--max-stocks` CLI bug → active 전체 처리 | smoke | TBD (max-stocks 정상 작동 검증 — total = max_stocks 기대) |
| 3 | ETF/ETN 호환성 → fullmatch 실패 | smoke | TBD (sample 5 로깅 — OHLCV 와 동일 ETF 비율 기대) |

**결론**: TBD (3건 모두 사전 적용 검증 완료 / 부분 / 신규 운영 차단 발견)
