# 운영 실측 결과 — OHLCV 3년 백필

> **상태**: ⏳ **사용자 측정 대기** — 본 문서는 빈 양식. 실측 후 채워서 ADR § 26 으로 승격.
> **측정자**: (이름 / 환경)
> **측정일**: YYYY-MM-DD (KST)
> **참조**: `backfill-measurement-runbook.md` (절차) / `scripts/backfill_ohlcv.py` (CLI)
> **운영 환경 fingerprint**: DB host (마스킹), 키움 alias 명, NXT_COLLECTION_ENABLED 값

---

## 0. 요약 (TL;DR)

> 4건의 운영 미해결 건 중 정량화된 항목 / 새로 발견된 위험 / 다음 chunk 우선순위 — 측정 후 1~2 문장.

- (작성 후)

---

## 1. 운영 환경 정보

| 항목 | 값 |
|------|-----|
| 측정 시점 | YYYY-MM-DD HH:MM KST |
| KIWOOM_DEFAULT_ENV | prod \| mock |
| NXT_COLLECTION_ENABLED | true \| false |
| KIWOOM_MIN_REQUEST_INTERVAL_SECONDS | (기본 0.25) |
| active stock 수 | KOSPI: ___ / KOSDAQ: ___ / KONEX: ___ / 합계 ___ |
| DB 마이그레이션 head | 012_stock_price_monthly_nxt |
| 백필 CLI commit | `055e81e` (또는 본인이 사용한 커밋) |

---

## 2. 단계별 실측

### 2.1 Stage 0 — Dry-run (자격증명 없이)

| Period | --years | active | NXT | total_calls | estimated |
|--------|---------|--------|-----|-------------|-----------|
| daily | 3 | | | | |
| weekly | 3 | | | | |
| monthly | 3 | | | | |

> dry-run 추정값 (lower-bound) 만 채움. 실측은 다음 단계.

---

### 2.2 Stage 1 — Smoke test (10 종목)

| 항목 | 값 |
|------|-----|
| 명령어 | `--period daily --years 1 --max-stocks 10 --only-market-codes 0` |
| total | 10 |
| success_krx / success_nxt / failed | / / |
| elapsed | h m s |
| avg/stock | s |
| pages observed (DEBUG) | (next_key 카운트) |

**관찰**:
- (네트워크 / 인증 이상 유무 / DB upsert 성공 여부)

---

### 2.3 Stage 2 — Mid (KOSPI 100, daily 3년)

| 항목 | 값 |
|------|-----|
| 명령어 | `--period daily --years 3 --max-stocks 100 --only-market-codes 0` |
| total | 100 |
| success_krx / success_nxt / failed | / / |
| elapsed | h m s |
| avg/stock | s |
| failure_ratio | % |

**dry-run 비교**:
- 추정 ___ vs 실측 ___ → 비율 ___ (±50% margin 안인지)

---

### 2.4 Stage 3 — Full (active 3000 KRX+NXT, daily 3년)

| 항목 | 값 |
|------|-----|
| 명령어 | `--period daily --years 3 --alias prod` |
| total | |
| success_krx / success_nxt / failed | / / |
| elapsed | h m s |
| avg/stock | s |
| failure_ratio | % |
| resume 사용 여부 | yes / no |

**상위 실패 원인 (top 5)**:
| stock_code | exchange | error_class | count |
|-----------|----------|-------------|-------|
| | | | |

---

### 2.5 Stage 3' — Weekly / Monthly (옵션)

| Period | total | elapsed | avg/stock | failed |
|--------|-------|---------|-----------|--------|
| weekly | | | | |
| monthly | | | | |

---

## 3. 측정 #1 — 페이지네이션 빈도 (3년 daily)

**가설**: 1 페이지 ~600 거래일 → 3년 (~750 거래일) → 종목당 2 페이지.

**실측**:
| 종목 (sample 5) | next_key 카운트 (DEBUG) | 페이지 수 |
|-----------------|------------------------|-----------|
| 005930 (삼성전자) | | |
| 000660 (SK하이닉스) | | |
| 035420 (NAVER) | | |
| (랜덤 KOSDAQ) | | |
| (랜덤 KONEX) | | |

**평균 페이지/종목**: (실측)
**가설 vs 실측**: 일치 / 다름 → (분석)

---

## 4. 측정 #2 — 3년 백필 elapsed (active 3000)

**가설** (dry-run lower-bound):
- KRX 단독 (NXT off): 약 ___ (estimated)
- KRX+NXT: 약 ___ (estimated)

**실측**:
| 시나리오 | elapsed | avg/stock | 비고 |
|----------|---------|-----------|------|
| KRX 단독 | | | |
| KRX+NXT | | | |

**±50% margin 안인지**: yes / no
**margin 초과 시 원인 분석**:
- (네트워크 RTT / 5xx 재시도 / DB upsert / TokenManager 재발급)

---

## 5. 측정 #3 — NUMERIC(8,4) magnitude 분포

**가설**: change_rate, foreign_holding_ratio, credit_ratio 모두 ±9999.9999 한도 내.

**실측 — change_rate** (`stock_price_krx`):

| 항목 | 값 |
|------|-----|
| rows | |
| min_pct | |
| max_pct | |
| p01 | |
| p99 | |
| count(\|change_rate\| > 100) | |
| count(\|change_rate\| > 1000) | |

**실측 — foreign_holding_ratio** (`stock_daily_flow_krx`):

| 항목 | 값 |
|------|-----|
| rows | |
| min | |
| max | |
| count(> 100) | (overflow 후보) |

**실측 — credit_ratio**:

| 항목 | 값 |
|------|-----|
| rows | |
| min | |
| max | |
| count(> 100) | |

**가설 vs 실측**:
- overflow (> NUMERIC(8,4) 한도) 발생: yes / no
- 발생 시 (stock_code, trading_date, value) 5건 샘플:
  | stock_code | trading_date | column | value |
  |-----------|-------------|--------|-------|
  | | | | |

**대응 결정**:
- (스케일 변경 NUMERIC(10,4) / 음수 캡 / 추가 검증 / 본 chunk 외)

---

## 6. 측정 #4 — active 3000 일간 sync 실측

> 백필 완료 다음 영업일에 운영 cron (`scheduler_ohlcv_daily_sync_alias`) 1회 측정.

| 시나리오 | elapsed | failed | NXT 적재 행 | KRX 적재 행 |
|----------|---------|--------|-----------|-----------|
| 1일치 sync (resume effect) | | | | |
| 7일치 sync (1주 지연 가정) | | | | |

**운영 cron 시간 예산** (06:00 ~ 09:00 KST 거래 전): __ 시간 / 한도 3시간 → 여유 / 부족

---

## 7. 5xx 재시도 비율 / 네트워크 안정성

| 시간대 | 5xx 카운트 | 재시도 성공 | 영구 실패 |
|--------|-----------|----------|----------|
| 평일 09:00~15:30 | (피크) | | |
| 평일 야간 | (안정) | | |
| 주말 | (안정) | | |

---

## 8. 새로 발견된 위험 / 후속 chunk 후보

| # | 항목 | 심각도 | 근거 | 후속 chunk |
|---|------|--------|------|-----------|
| | | HIGH/MEDIUM/LOW | | |

---

## 9. 결정 사항

본 실측 결과로 확정된 결정:

1. (예: NXT 수집 정책 prod 전환 — `NXT_COLLECTION_ENABLED=true`)
2. (예: gap detection 우선순위 상승 / 하강)
3. (예: NUMERIC 컬럼 마이그레이션 필요 여부)

---

## 10. 다음 chunk 우선순위 갱신

| 순위 | chunk | 변경 사유 |
|------|-------|----------|
| 1 | | |
| 2 | | |

---

## 11. ADR § 26 승격

본 문서 채움 완료 후 ADR-0001 § 26 의 빈 표를 본 결과로 채우고, STATUS.md § 4 의 정량화된 항목을 제거. 본 문서는 그대로 유지 (raw 측정 기록).
