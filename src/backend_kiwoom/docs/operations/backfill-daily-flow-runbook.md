# 운영 실측 Runbook — daily_flow (ka10086) 3년 백필

> **목적**: `scripts/backfill_daily_flow.py` (C-backfill-daily-flow) 로 운영 미해결 4건을 정량화한다.
> **대상 환경**: 사용자 로컬 (Docker Desktop) — `src/backend_kiwoom/docker-compose.yml` 의 postgres:16-alpine + 운영 키움 자격증명.
> **소요 시간**: dry-run + 단계 1~3 실측 (포함 후처리) — 약 2~4시간 (인터랙티브) / + 3년 백필 1~2시간 (백그라운드, OHLCV 34분 + α 추정).
> **관련 문서**:
> - `scripts/backfill_daily_flow.py` (CLI)
> - `docs/plans/phase-c-backfill-daily-flow.md` (chunk 설계)
> - `docs/operations/backfill-measurement-runbook.md` (OHLCV 실측 — 본 runbook 의 base 패턴)
> - ADR-0001 § 27 (C-backfill-daily-flow 결정) / § 27.5 (실측 결과 자리)

---

## 0. 측정 대상 — 운영 미해결 4건 (ADR § 27.4)

| # | 항목 | 측정 방법 | 결과 자리 |
|---|------|-----------|-----------|
| 1 | **페이지네이션 빈도** — 3년 ka10086 1종목당 페이지 수 | dry-run 추정 vs `--log-level=DEBUG` 실측 (mrkcond.py 의 `cont_yn` count) | results.md § 3 |
| 2 | **3년 백필 elapsed** — KOSPI+KOSDAQ active 4078 (KRX+NXT) | `format_summary` elapsed | results.md § 4 |
| 3 | **NUMERIC(8,4) magnitude 분포** — `credit_rate` / `credit_balance_rate` / `foreign_rate` / `foreign_weight` 의 max/min/percentile | 백필 완료 후 SQL 쿼리 (§ 7 후처리) | results.md § 5 |
| 4 | **active 4078 일간 sync 실측** — daily_flow 운영 cron 의 실시간 (5xx 재시도 + DB upsert 포함) | 단계 4 (옵션) — 백필 완료된 다음 영업일 1년 cap 실 sync 1회 | results.md § 6 |

### 0.1 OHLCV 백필과의 차이 (§ 26 패턴 대비)

- **단일 endpoint** — OHLCV 의 `--period {daily,weekly,monthly}` 분기 없음 (ka10086 하나)
- **`--indc-mode {quantity,amount}`** — daily_flow 표시 단위 옵션. 디폴트 `quantity` (시그널 단위 일관)
- **resume 테이블** — `kiwoom.stock_daily_flow` (KRX/NXT 단일 테이블, exchange 컬럼으로 분리). OHLCV 의 `stock_price_krx` 와 다름
- **NUMERIC 측정 컬럼** — 4개 (`credit_rate` / `credit_balance_rate` / `foreign_rate` / `foreign_weight`). OHLCV 의 `change_rate` / `turnover_rate` 와 별도 도메인
- **운영 차단 fix 3건 사전 적용** — since_date guard / `--max-stocks` 정상 작동 / ETF 호환 가드. OHLCV 운영 진입 후 발견 → daily_flow 코드/테스트 단계에서 사전 적용 (ADR § 27.6)

---

## 1. 사전 조건

### 1.1 DB 컨테이너 기동

```bash
cd src/backend_kiwoom

# kiwoom-db 컨테이너 기동 (postgres:16-alpine, 호스트 5433 매핑)
docker compose up -d kiwoom-db

# healthy 확인
docker compose ps
# kiwoom-db   "docker-entrypoint.s…"   Up 5s (healthy)   0.0.0.0:5433->5432/tcp
```

### 1.2 환경변수 (`.env.prod` 또는 export)

OHLCV runbook § 1.2 와 동일 — `KIWOOM_DATABASE_URL` / `KIWOOM_CREDENTIAL_MASTER_KEY` / `KIWOOM_BASE_URL_PROD` / `KIWOOM_DEFAULT_ENV=prod` / `NXT_COLLECTION_ENABLED=true` / `KIWOOM_MIN_REQUEST_INTERVAL_SECONDS=0.25` 등.

> OHLCV 백필 후 본 daily_flow 백필을 이어서 진행한다면, 동일 `.env.prod` 그대로 사용 가능. 추가 변수 없음.

### 1.3 마이그레이션 적용

```bash
# 마이그레이션 head 확인 (012 까지 적용)
uv run alembic current

# 미적용 시
uv run alembic upgrade head

# stock_daily_flow 테이블 존재 확인
docker compose exec kiwoom-db psql -U kiwoom -d kiwoom_db -c "\d kiwoom.stock_daily_flow" | head -30
```

### 1.4 alias 등록 (OHLCV 백필과 공유 가능)

OHLCV runbook § 1.4 와 동일. 같은 alias (`prod`) 재사용 권장.

```bash
# 등록 확인
docker compose exec kiwoom-db psql -U kiwoom -d kiwoom_db -c \
    "SELECT alias, env, is_active FROM kiwoom.kiwoom_credential WHERE alias='prod';"
```

본 runbook 의 예시는 `--alias prod` 가정.

### 1.5 종목 마스터 sync (선행 필수)

`kiwoom.stock` 이 비어있으면 backfill 대상이 0. OHLCV 백필을 먼저 했다면 이미 sync 됨. 확인만:

```bash
docker compose exec kiwoom-db psql -U kiwoom -d kiwoom_db -c \
    "SELECT COUNT(*) FROM kiwoom.stock WHERE is_active = true;"
# 약 4078 (OHLCV 백필 시점 기준 — 종목 마스터 변동 시 차이 가능)
```

신규 환경이면 `uv run python scripts/sync_stock_master.py --alias prod` 1회 실행 (OHLCV runbook § 1.5).

---

## 2. 단계 0 — Dry-run (자격증명 불필요, DB 만)

```bash
cd src/backend_kiwoom

# 3년 (전체 active, 디폴트 quantity 모드)
uv run python scripts/backfill_daily_flow.py \
    --years 3 --alias prod --dry-run

# 출력 예시
# ===== Dry-run 추정 (lower-bound, ±50% margin) =====
# date range:    2023-05-10 ~ 2026-05-10 (1095 days)
# active stocks: 4078
# NXT collection: enabled
# exchanges/stock: 2
# pages/call:    4 (ka10086 1 page ~300 거래일 추정)
# total calls:   32624
# rate limit:    0.25s/call
# estimated:     2h 15m 56s (실측 ±50% margin)
```

### 2.1 amount 모드 vs quantity 모드 차이

```bash
# amount (백만원 단위)
uv run python scripts/backfill_daily_flow.py \
    --years 3 --alias prod --indc-mode amount --dry-run
```

> 디폴트 `quantity` 권장 (시그널 단위 일관 — ADR § 27.2). `amount` 는 cross-check / 디버그용.

> **추정값 vs 실측 ±50% margin**: 5xx 재시도 + DB upsert (NUMERIC 변환) + 네트워크 RTT 가 lower-bound 보다 길게 만든다.

---

## 3. 단계 1 — Smoke test (10 종목)

자격증명 + 키움 API 연결 검증. 실패 시 다음 단계 진입 금지.

```bash
mkdir -p logs

# KOSPI 상위 10 종목, 1년
uv run python scripts/backfill_daily_flow.py \
    --years 1 --alias prod \
    --only-market-codes 0 --max-stocks 10 \
    --log-level DEBUG \
    2>&1 | tee logs/backfill-daily-flow-smoke-$(date +%Y%m%d-%H%M%S).log
```

**예상 결과**:
- `total: 10 종목 / failed: 0` — 정상
- `failed > 0` — 자격증명 / 토큰 / 네트워크 점검. 단계 2 진입 금지

**관찰 포인트** (#1 페이지네이션 측정):
```bash
# DEBUG 로그에서 cont_yn 카운트 (1년 → 1~2 페이지)
grep -c "next_key=" logs/backfill-daily-flow-smoke-*.log

# ETF/ETN skip sample 5 로그 확인 (사전 적용된 _KA10086_COMPATIBLE_RE 가드 동작 검증)
grep -E "(ETF|ETN|skip).*sample" logs/backfill-daily-flow-smoke-*.log
```

**확인 SQL** (적재 검증):
```bash
docker compose exec kiwoom-db psql -U kiwoom -d kiwoom_db -c "
SELECT exchange, COUNT(*) AS rows, COUNT(DISTINCT stock_id) AS stocks,
       MIN(trading_date) AS oldest, MAX(trading_date) AS newest
FROM kiwoom.stock_daily_flow
GROUP BY exchange ORDER BY 1;
"
```

---

## 4. 단계 2 — Mid-scale (KOSPI 100 종목)

```bash
uv run python scripts/backfill_daily_flow.py \
    --years 3 --alias prod \
    --only-market-codes 0 --max-stocks 100 \
    --log-level INFO \
    2>&1 | tee logs/backfill-daily-flow-mid-$(date +%Y%m%d-%H%M%S).log
```

**측정 항목**:
- elapsed (`format_summary` 출력)
- avg/stock — 단계 3 추정 baseline (4078 종목 × avg/stock = 예상 총 시간)
- failed — 5xx 재시도 비율 추정
- ETF skip count (sample 5 로그)

**중간 점검** (실패 비율 > 5% 면 단계 3 진입 보류):
```bash
grep "failed:" logs/backfill-daily-flow-mid-*.log
```

---

## 5. 단계 3 — Full-scale (active 4078, KRX+NXT)

⚠️ **장시간 (1~2시간 추정)**. OHLCV 의 34분보다 페이지네이션이 추가되어 +α 예상. 백그라운드 실행 + 모니터링.

```bash
# 백그라운드 + nohup (SSH 세션 끊김 대비)
nohup uv run python scripts/backfill_daily_flow.py \
    --years 3 --alias prod \
    --log-level INFO \
    > logs/backfill-daily-flow-full-$(date +%Y%m%d).log 2>&1 &

echo $! > logs/backfill-daily-flow.pid
```

**모니터링** (별도 터미널):
```bash
# 진행률 (10분마다)
watch -n 600 'tail -50 logs/backfill-daily-flow-full-*.log | grep -E "(processed|failed|elapsed)"'

# DB 적재 진척 (분당)
watch -n 60 'docker compose exec kiwoom-db psql -U kiwoom -d kiwoom_db -c \
    "SELECT exchange, COUNT(DISTINCT stock_id) FROM kiwoom.stock_daily_flow GROUP BY exchange;"'

# 프로세스 살아있는지
ps -p $(cat logs/backfill-daily-flow.pid) > /dev/null && echo "alive" || echo "dead"
```

**중단 / 재개**:
```bash
# 중단
kill $(cat logs/backfill-daily-flow.pid)

# 재개 (이미 적재된 종목 skip — max(trading_date) >= end_date)
uv run python scripts/backfill_daily_flow.py \
    --years 3 --alias prod --resume \
    > logs/backfill-daily-flow-resume-$(date +%Y%m%d).log 2>&1
```

> resume 한계 — `max(trading_date) >= end_date` 만 본다. 부분 일자 누락 (gap) 은 detect 못 함. 별도 chunk (refactor R2 의 gap detection).

---

## 6. (생략 — daily_flow 는 단일 endpoint)

> OHLCV runbook § 6 (weekly/monthly) 같은 추가 단계는 daily_flow 에 불필요. ka10086 단일 endpoint.

---

## 7. 후처리 — NUMERIC(8,4) magnitude 분포 측정 (#3)

백필 완료 후 SQL 쿼리로 NUMERIC(8,4) 4 컬럼의 실 분포 측정. ADR § 27.4 의 가설 검증.

```sql
-- credit_rate (신용 비율) — NUMERIC(8,4) = max ±9999.9999, 가정 0~100
SELECT
    COUNT(*) AS rows,
    MIN(credit_rate) AS min_pct,
    MAX(credit_rate) AS max_pct,
    PERCENTILE_CONT(0.01) WITHIN GROUP (ORDER BY credit_rate) AS p01,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY credit_rate) AS p99,
    COUNT(*) FILTER (WHERE ABS(credit_rate) > 100) AS gt_100,
    COUNT(*) FILTER (WHERE ABS(credit_rate) > 1000) AS gt_1000
FROM kiwoom.stock_daily_flow
WHERE credit_rate IS NOT NULL;

-- credit_balance_rate (신용 잔고율) — 동일 가정 0~100
SELECT
    COUNT(*) AS rows,
    MIN(credit_balance_rate),
    MAX(credit_balance_rate),
    PERCENTILE_CONT(0.01) WITHIN GROUP (ORDER BY credit_balance_rate) AS p01,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY credit_balance_rate) AS p99,
    COUNT(*) FILTER (WHERE ABS(credit_balance_rate) > 100) AS gt_100,
    COUNT(*) FILTER (WHERE ABS(credit_balance_rate) > 1000) AS gt_1000
FROM kiwoom.stock_daily_flow
WHERE credit_balance_rate IS NOT NULL;

-- foreign_rate (외인 비율) — NUMERIC(8,4)
SELECT
    COUNT(*) AS rows,
    MIN(foreign_rate),
    MAX(foreign_rate),
    PERCENTILE_CONT(0.01) WITHIN GROUP (ORDER BY foreign_rate) AS p01,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY foreign_rate) AS p99,
    COUNT(*) FILTER (WHERE ABS(foreign_rate) > 100) AS gt_100,
    COUNT(*) FILTER (WHERE ABS(foreign_rate) > 1000) AS gt_1000
FROM kiwoom.stock_daily_flow
WHERE foreign_rate IS NOT NULL;

-- foreign_weight (외인 비중) — NUMERIC(8,4) = 0~100 가정 (지분율)
SELECT
    COUNT(*) AS rows,
    MIN(foreign_weight),
    MAX(foreign_weight),
    PERCENTILE_CONT(0.01) WITHIN GROUP (ORDER BY foreign_weight) AS p01,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY foreign_weight) AS p99,
    COUNT(*) FILTER (WHERE ABS(foreign_weight) > 100) AS gt_100  -- 100 초과 = magnitude overflow 후보
FROM kiwoom.stock_daily_flow
WHERE foreign_weight IS NOT NULL;
```

결과는 `backfill-daily-flow-results.md` § 5 에 기록.

> **마이그레이션 결정 기준** — `gt_100` > 0 이거나 `gt_1000` > 0 이면 NUMERIC(8,4) 한도 (±9999.9999) 의 1~10% 초과 케이스 존재. 운영 진입 전 `NUMERIC(10,4)` 등으로 확장 권장 → 별도 Migration chunk.

### 7.1 추가 — exchange 별 분포 cross-check

```sql
-- KRX vs NXT 각각의 row 수 + max
SELECT
    exchange,
    COUNT(*) AS rows,
    COUNT(DISTINCT stock_id) AS stocks,
    MAX(foreign_weight) AS max_fw,
    MAX(foreign_rate) AS max_fr,
    MAX(credit_rate) AS max_cr
FROM kiwoom.stock_daily_flow
GROUP BY exchange ORDER BY 1;
```

### 7.2 since_date guard edge case (OHLCV F6 follow-up cross-check)

```sql
-- since_date (start_date) 보다 과거 row 가 적재된 종목 — daily_flow 에서도 같은 edge case 발생 여부
WITH backfill_start AS (SELECT '2023-05-10'::date AS d)
SELECT s.stock_code, s.stock_name, MIN(p.trading_date) AS oldest_dt
FROM kiwoom.stock_daily_flow p
JOIN kiwoom.stock s ON p.stock_id = s.id
WHERE p.trading_date < (SELECT d FROM backfill_start)
GROUP BY s.stock_code, s.stock_name
ORDER BY oldest_dt
LIMIT 20;
```

> OHLCV 에서 2 종목 (`002690` / `004440`) 발견 — daily_flow 에서도 일치하는지 cross-check (`_page_reached_since_market` / `_row_on_or_after_market` 로직 OHLCV chart.py 1:1 응용).

---

## 8. 후처리 — 일간 cron 실측 (#4, 옵션)

백필 완료 다음 영업일에 daily_flow 운영 cron (`daily_flow_sync_daily`, KST mon-fri 19:00) 1회 실행 시간 측정.

```bash
# 운영 lifespan 기동 (scheduler_enabled=True). cron trigger 19:00 KST 기다리거나 라우터 수동 호출
curl -X POST -H "X-API-Key: $ADMIN_API_KEY" \
    "https://kiwoom-api.internal/api/kiwoom/daily-flow/sync"

# 결과는 structlog JSON 의 `event=daily_flow_sync_completed` 의 elapsed_seconds 필드
```

> 본 측정은 HANDOFF Pending #2 (scheduler_enabled 운영 cron 활성) 와 결합. daily_flow + OHLCV 동일 elapsed 슬롯에서 측정.

---

## 9. 결과 정리

1. 단계별 log 파일을 `logs/` 에서 분류 — smoke / mid / full / resume
2. `format_summary` 의 elapsed / failed / avg/stock 을 `backfill-daily-flow-results.md` 에 기록
3. NUMERIC 분포 SQL 결과를 같이 기록
4. ADR § 27.5 에 핵심 결정 / 후속 chunk 우선순위 갱신
5. STATUS.md § 4 의 운영 미해결 (#1~#4) 중 정량화된 항목 제거
6. CHANGELOG.md 에 운영 실측 결과 chunk 1 항목 prepend (OHLCV § 26.5 와 동일 패턴)

---

## 10. 트러블슈팅

| 증상 | 원인 후보 | 조치 |
|------|----------|------|
| `KiwoomCredentialNotFoundError: alias='prod'` | DB 의 alias 미등록 | § 1.4 에서 alias 등록 확인 |
| `MasterKeyNotConfiguredError` | `KIWOOM_CREDENTIAL_MASTER_KEY` 빈 값 | export 또는 `.env.prod` 추가 |
| 5xx 재시도 누적 | 키움 서버 일시 장애 | 중단 → § 5 의 `--resume` 로 재개 |
| `failed > 0` 다수 (>5%) | 토큰 만료 / 네트워크 / 종목 마스터 미등록 | DEBUG 로그에서 stock_code 별 error_class 확인 |
| `numeric field overflow` | NUMERIC(8,4) 한도 초과 (#3 가설 적중) | overflow 종목 코드 + 컬럼 캡처 → ADR § 27.5 에 기록, Migration chunk 결정 |
| ETF skip 비율 OHLCV 와 큰 차이 | `_KA10086_COMPATIBLE_RE` regex 차이 또는 stock 마스터 변동 | `STK_CD_LOOKUP_PATTERN` 확인 + sample 5 로그 inspection |
| `since_date` 보다 과거 row 적재 (§ 7.2) | mrkcond `_page_reached_since_market` edge case | OHLCV F6 follow-up 일괄 분석 chunk 로 이월 |
| 페이지 5+ 반복 | ka10086 응답 row 수가 가설 (~300 거래일/page) 보다 적음 | DEBUG 로그 page count 캡처 + ADR § 27.5 #1 에 기록. max_pages 상향 검토 |

---

## 11. 안전 장치

- **운영 시간대 회피**: KRX 거래 시간 (09:00~15:30 KST) 에는 백필 금지 (운영 cron 충돌 + KRX rate limit 경합). 권장 시간대: 16:00~다음날 08:00 KST 또는 주말
- **OHLCV 백필 직렬 실행**: 같은 alias 의 OHLCV 백필이 진행 중이면 daily_flow 백필 충돌 (rate limit 공유). OHLCV 완료 후 daily_flow 시작
- **scheduler_enabled 충돌**: 운영 cron (mon-fri 19:00 daily_flow / 18:30 OHLCV / 금 19:30 weekly) 시간대 회피
- **rollback 전략**: NUMERIC overflow 등 데이터 오염 시 — `kiwoom.stock_daily_flow` 의 본 백필 기간만 DELETE 가능 (운영 1년 cap 영역과 분리)
- **TokenManager 자동 재발급**: 24h 토큰 lifecycle 가 백필 (1~2시간) 안에는 만료 가능성 낮음. OHLCV 와 동일 alias 재사용 시 자동 재발급
- **DB 부하**: 단일 worker × 약 16,000 호출 (KRX 4078 × 2 page + NXT 626 × 2 page) → connection pool (`database_pool_size=5`) 흡수
- **resume 한계**: `max(trading_date) >= end_date` 만 본다. 부분 일자 누락 (gap) 은 detect 못 함 (OHLCV 와 동일 한계)

---

## 12. OHLCV 백필 결과 cross-check (실측 진입 전 sanity check)

OHLCV 백필 (2026-05-10 완료, ADR § 26.5) 결과:
- **34분 / failed 0 / 4078 종목 KRX 4077 적재** (1 종목 빈 응답)
- **NUMERIC turnover_rate**: max 3,257.80 (cap 의 33%) / ABS>1000 = 24 rows (0.0009%) — 마이그레이션 불필요
- **since_date guard edge case**: 2 종목 (`002690` / `004440`) 만 since_date 이전 row 적재

**daily_flow 에서 검증 가능한 가설**:

| OHLCV 결과 | daily_flow 가설 |
|------------|----------------|
| 4078 호환 / 4077 적재 (1 빈 응답) | 동일 종목 비율 — 빈 응답 1 종목 cross-check |
| KRX 34분 + 페이지 1~2 | KRX 약 50~100분 (페이지 평균 2~3) |
| since_date edge 2 종목 | 동일 2 종목 또는 추가 종목 발견 (mrkcond 의 `_page_reached_since_market` 가 chart.py 패턴 1:1 인지) |
| ETF skip — sample 로깅 정상 | 동일 skip 비율 (`_KA10086_COMPATIBLE_RE`) |
