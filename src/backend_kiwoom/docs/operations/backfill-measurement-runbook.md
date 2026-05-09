# 운영 실측 Runbook — OHLCV 3년 백필

> **목적**: `scripts/backfill_ohlcv.py` (C-backfill) 로 운영 미해결 4건을 정량화한다.
> **대상 환경**: 사용자 로컬 (Docker Desktop) — `src/backend_kiwoom/docker-compose.yml` 의 postgres:16-alpine + 운영 키움 자격증명.
> **소요 시간**: dry-run + 단계 1~3 실측 (포함 후처리) — 약 2~4시간 (인터랙티브) / + 3년 백필 4~8시간 (백그라운드).
> **관련 문서**:
> - `scripts/backfill_ohlcv.py` (CLI)
> - `src/backend_kiwoom/docker-compose.yml` (DB 컨테이너 정의)
> - `src/backend_kiwoom/migrations/versions/001~012_*.py` (스키마 진실 출처 — backend_kiwoom 전용 ERD 다이어그램은 별도 없음. PoC 단계 ERD 는 `pipeline/artifacts/04-db-schema/erd.mermaid` 참고지만 실제 스키마와 다름)
> - ADR-0001 § 25 (C-backfill 설계) / ADR-0001 § 26 (실측 결과 자리) / STATUS.md § 4 (운영 미해결 4건)

---

## 0. 측정 대상 — 운영 미해결 4건

| # | 항목 | 측정 방법 | 출처 (STATUS § 4) |
|---|------|-----------|-------------------|
| 1 | **페이지네이션 빈도** — 3년 daily 1종목당 페이지 수 | dry-run 추정 vs `--log-level=DEBUG` 실측 (chart.py 의 `cont_yn` count) | dry-run § 20.4 |
| 2 | **3년 백필 시간** — KOSPI+KOSDAQ active 3000 (NXT 포함 6000 호출) | 단계 3 elapsed (`time.monotonic`) | dry-run § 20.4 |
| 3 | **NUMERIC(8,4) magnitude 분포** — change_rate, foreign_holding_ratio 의 max/min/percentile | 백필 완료 후 SQL 쿼리 (§ 4 후처리) | dry-run § 20.4 + ADR § 18.4 |
| 4 | **active 3000 + NXT 1500 일간 sync 실측** — daily 운영 cron 의 실시간 (5xx 재시도 + DB upsert 포함) | 단계 4 (옵션) — 백필 완료된 다음 날 1년 cap 실 sync 1회 | dry-run § 20.4 |

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

# 호스트에서 접속 확인 (psql 클라이언트 또는 docker exec)
docker compose exec kiwoom-db psql -U kiwoom -d kiwoom_db -c "SELECT version();"
```

### 1.2 환경변수 (`.env.prod` 또는 export)

| 변수 | 값 | 비고 |
|------|-----|------|
| `DATABASE_URL` | `postgresql+asyncpg://kiwoom:kiwoom@localhost:5433/kiwoom_db` | docker-compose.yml 기준 (호스트 5433 매핑). asyncpg 드라이버 |
| `KIWOOM_CREDENTIAL_MASTER_KEY` | Fernet 32B base64 (예: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) | alias 복호화용 — 운영과 동일 키 필수 |
| `KIWOOM_BASE_URL_PROD` | `https://api.kiwoom.com` | 디폴트값 그대로 (Settings 디폴트 사용) |
| `KIWOOM_DEFAULT_ENV` | `prod` | mock 도메인은 NXT 미지원 — 실측은 prod 필수 |
| `NXT_COLLECTION_ENABLED` | `true` | 6000 호출 시나리오 측정 시 (False 면 KRX 만 3000) |
| `KIWOOM_MIN_REQUEST_INTERVAL_SECONDS` | `0.25` | 디폴트 (5 RPS 안전 마진). 변경 시 #1 추정에 영향 |
| `KIWOOM_CONCURRENT_REQUESTS` | `4` | 디폴트. 백필 단일 worker 라 영향 적음 |
| `BACKFILL_MAX_DAYS` | `1095` | 디폴트 (3년) — Settings.backfill_max_days |

> `.env.prod` 위치: `/Users/heowooyong/cursor/learning/ted-startup/.env.prod` (루트). pydantic-settings 가 cwd 기준으로 로드하므로 backend_kiwoom 에서 실행 시 `cd src/backend_kiwoom; cp ../../.env.prod .env.prod` 또는 symlink 권장. 또는 `export $(cat ../../.env.prod | xargs)` 로 환경변수 export.

### 1.3 마이그레이션 적용

```bash
# 마이그레이션 head 확인 (012 까지 적용)
uv run alembic current

# 미적용 시
uv run alembic upgrade head
# Running upgrade  -> 001_init_kiwoom_schema (+11 more) -> 012_stock_price_monthly_nxt

# active stock 수 확인 (백필 대상 산정 — Phase B 의 ka10099 sync 후 채워짐)
docker compose exec kiwoom-db psql -U kiwoom -d kiwoom_db -c \
    "SELECT market_code, COUNT(*) FROM kiwoom.stock WHERE is_active = true GROUP BY market_code ORDER BY 1;"
```

> 빈 DB 라면 `kiwoom.stock` 행수 0 → backfill 도 0 종목. **Phase B 의 ka10099 (종목 마스터 sync) 가 선행되어야 함**. 운영 환경에서 종목 마스터를 가져오거나, 테스트로 mock 데이터 INSERT.

### 1.4 alias 등록

운영 DB 의 `kiwoom.kiwoom_credential` 테이블에 alias 가 등록되어 있어야 한다 (마스터키로 암호화된 appkey/secret). 등록은 admin 라우터 (`POST /api/kiwoom/admin/credentials`) 또는 직접 INSERT 로 가능 — 자세한 절차는 ADR-0001 § 3 (보안 정책) + Phase A2-α 결정 참고.

```bash
# alias 확인
docker compose exec kiwoom-db psql -U kiwoom -d kiwoom_db -c \
    "SELECT alias, env, is_active, created_at FROM kiwoom.kiwoom_credential ORDER BY created_at DESC;"
```

본 runbook 의 예시는 `--alias prod` 가정.

---

## 2. 단계 0 — Dry-run (자격증명 불필요, DB 만)

dry-run 은 키움 API 를 호출하지 않으므로 **DB 만 연결되면 동작**. 시간 추정 (lower-bound) 검증용.

```bash
cd src/backend_kiwoom

# Daily 3년 (전체 active)
uv run python scripts/backfill_ohlcv.py \
    --period daily --years 3 --alias prod --dry-run

# 출력 예시
# ===== Dry-run 추정 (lower-bound, ±50% margin) =====
# period:        daily
# date range:    2023-05-09 ~ 2026-05-09 (1095 days)
# active stocks: 2987   (← 환경마다 다름)
# NXT collection: enabled
# exchanges/stock: 2
# pages/call:    2
# total calls:   11948
# rate limit:    0.25s/call
# estimated:     0h 49m 47s (실측 ±50% margin)
```

| Period | --years 3 추정 (active 3000) | NXT 포함 시 |
|--------|------------------------------|--------------|
| daily | 약 2시간 (KRX 단독) | 약 4시간 (KRX+NXT) |
| weekly | 약 12분 | 약 25분 |
| monthly | 약 12분 | 약 25분 |

> 실 시간은 5xx 재시도 + DB upsert (NUMERIC 변환) + 네트워크 RTT 로 lower-bound 보다 길어진다. ±50% margin 으로 본다.

---

## 3. 단계 1 — Smoke test (10 종목)

자격증명 + 키움 API 연결 검증. 실패 시 다음 단계 진입 금지.

```bash
# KOSPI 상위 10 종목, daily 1년
uv run python scripts/backfill_ohlcv.py \
    --period daily --years 1 --alias prod \
    --only-market-codes 0 --max-stocks 10 \
    --log-level DEBUG \
    2>&1 | tee logs/backfill-smoke-daily-$(date +%Y%m%d-%H%M%S).log
```

**예상 결과**:
- `total: 10 종목 / failed: 0` — 정상
- `failed > 0` — 자격증명 / 토큰 / 네트워크 점검. 단계 2 진입 금지

**관찰 포인트** (#1 페이지네이션 측정):
```bash
# DEBUG 로그에서 cont_yn 카운트 (1년 → 1~2 페이지)
grep -c "next_key=" logs/backfill-smoke-daily-*.log
```

---

## 4. 단계 2 — Mid-scale (KOSPI 100 종목)

```bash
uv run python scripts/backfill_ohlcv.py \
    --period daily --years 3 --alias prod \
    --only-market-codes 0 --max-stocks 100 \
    --log-level INFO \
    2>&1 | tee logs/backfill-mid-daily-$(date +%Y%m%d-%H%M%S).log
```

**측정 항목**:
- elapsed (`format_summary` 출력)
- avg/stock — 단계 3 추정 baseline
- failed — 5xx 재시도 비율 추정

**중간 점검** (실패 비율 > 5% 면 단계 3 진입 보류):
```bash
grep "failed:" logs/backfill-mid-*.log
```

---

## 5. 단계 3 — Full-scale (active 3000, KRX+NXT)

⚠️ **장시간 (4~8시간)**. 백그라운드 실행 + 모니터링.

```bash
# 백그라운드 + nohup (SSH 세션 끊김 대비)
nohup uv run python scripts/backfill_ohlcv.py \
    --period daily --years 3 --alias prod \
    --log-level INFO \
    > logs/backfill-full-daily-$(date +%Y%m%d).log 2>&1 &

echo $! > logs/backfill.pid
```

**모니터링** (별도 터미널):
```bash
# 진행률 (10분마다)
watch -n 600 'tail -50 logs/backfill-full-daily-*.log | grep -E "(processed|failed|elapsed)"'

# DB 적재 진척 (분당)
watch -n 60 'docker compose exec kiwoom-db psql -U kiwoom -d kiwoom_db -c "SELECT COUNT(DISTINCT stock_id) FROM kiwoom.stock_price_krx;"'

# 프로세스 살아있는지
ps -p $(cat logs/backfill.pid) > /dev/null && echo "alive" || echo "dead"
```

**중단 / 재개** (5xx 누적 또는 운영 사정):
```bash
# 중단
kill $(cat logs/backfill.pid)

# 재개 (이미 적재된 종목 skip)
uv run python scripts/backfill_ohlcv.py \
    --period daily --years 3 --alias prod \
    --resume \
    > logs/backfill-resume-daily-$(date +%Y%m%d).log 2>&1
```

> resume 의 한계 — `max(trading_date) >= end_date` 만 본다. 부분 일자 누락 (gap) 은 detect 못 함. 별도 chunk (refactor R2 의 gap detection).

---

## 6. 단계 3' — weekly / monthly (옵션)

3년 weekly = 156 row, monthly = 36 row. daily 보다 빠름 (페이지 1 / 호출).

```bash
# Weekly
uv run python scripts/backfill_ohlcv.py \
    --period weekly --years 3 --alias prod \
    > logs/backfill-full-weekly-$(date +%Y%m%d).log 2>&1

# Monthly
uv run python scripts/backfill_ohlcv.py \
    --period monthly --years 3 --alias prod \
    > logs/backfill-full-monthly-$(date +%Y%m%d).log 2>&1
```

---

## 7. 후처리 — NUMERIC magnitude 분포 측정 (#3)

백필 완료 후 SQL 쿼리로 NUMERIC(8,4) 컬럼의 실 분포 측정. dry-run § 20.4 + ADR § 18.4 의 가설 검증.

```sql
-- change_rate (stock_price_krx) — NUMERIC(8,4) = max ±9999.9999
SELECT
    COUNT(*) AS rows,
    MIN(change_rate) AS min_pct,
    MAX(change_rate) AS max_pct,
    PERCENTILE_CONT(0.01) WITHIN GROUP (ORDER BY change_rate) AS p01,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY change_rate) AS p99,
    COUNT(*) FILTER (WHERE ABS(change_rate) > 100) AS gt_100pct,
    COUNT(*) FILTER (WHERE ABS(change_rate) > 1000) AS gt_1000pct
FROM kiwoom.stock_price_krx
WHERE change_rate IS NOT NULL;

-- foreign_holding_ratio (stock_daily_flow_krx) — NUMERIC(8,4) = 0~100 가정
SELECT
    COUNT(*) AS rows,
    MIN(foreign_holding_ratio),
    MAX(foreign_holding_ratio),
    COUNT(*) FILTER (WHERE foreign_holding_ratio > 100) AS gt_100  -- magnitude overflow 후보
FROM kiwoom.stock_daily_flow_krx
WHERE foreign_holding_ratio IS NOT NULL;

-- credit_ratio — 동일 방식
SELECT
    COUNT(*) AS rows,
    MIN(credit_ratio),
    MAX(credit_ratio),
    COUNT(*) FILTER (WHERE credit_ratio > 100) AS gt_100
FROM kiwoom.stock_daily_flow_krx
WHERE credit_ratio IS NOT NULL;
```

결과는 `backfill-measurement-results.md` § 4 에 기록.

---

## 8. 후처리 — 일간 cron 실측 (#4, 옵션)

백필 완료 다음 영업일에 운영 cron (`scheduler_ohlcv_daily_sync_alias`) 1회 실행 시간 측정. 백필 완료 → resume 효과로 실 sync 는 1일치만 적재.

```bash
# 운영 lifespan 기동 (scheduler_enabled=True). cron trigger 시간 기다리거나 수동 실행
# 수동 실행: 라우터 호출
curl -X POST -H "X-API-Key: $ADMIN_API_KEY" \
    "https://kiwoom-api.internal/api/kiwoom/ohlcv/daily/sync"

# 결과는 structlog JSON 의 `event=ohlcv_daily_sync_completed` 의 elapsed_seconds 필드
```

운영 cron 의 실 elapsed 가 daily sync 시간 (#4) 의 정답.

---

## 9. 결과 정리

1. 단계별 log 파일을 `logs/` 에서 분류 — smoke / mid / full / resume
2. `format_summary` 의 elapsed / failed / avg/stock 을 `backfill-measurement-results.md` 에 기록
3. NUMERIC 분포 SQL 결과를 같이 기록
4. ADR § 26 에 핵심 결정 / 후속 chunk 우선순위 갱신
5. STATUS.md § 4 의 운영 미해결 4건 중 정량화된 항목 제거

---

## 10. 트러블슈팅

| 증상 | 원인 후보 | 조치 |
|------|----------|------|
| `KiwoomCredentialNotFoundError: alias='prod'` | DB 의 alias 미등록 | § 1.3 에서 alias 등록 확인 |
| `MasterKeyNotConfiguredError` | `KIWOOM_CREDENTIAL_MASTER_KEY` 빈 값 | export 또는 `.env.prod` 추가 |
| 5xx 재시도 누적 | 키움 서버 일시 장애 | 중단 → § 5 의 `--resume` 로 재개 |
| `failed > 0` 다수 (>5%) | 토큰 만료 / 네트워크 / 종목 마스터 미등록 | DEBUG 로그에서 stock_code 별 error_class 확인 |
| `asyncpg.exceptions.UndefinedColumnError` | Migration 008/012 미적용 | `uv run alembic upgrade head` |
| `numeric field overflow` | NUMERIC(8,4) 한도 초과 (#3 가설 적중) | overflow 종목 코드 + 값 캡처 → ADR § 26 에 기록, 마이그레이션 chunk 결정 |

---

## 11. 안전 장치

- **운영 시간대 회피**: KRX 거래 시간 (09:00~15:30 KST) 에는 백필 금지 (운영 cron 충돌 + KRX rate limit 경합)
- **rollback 전략**: 백필 중 NUMERIC overflow 등 데이터 오염 발견 시 — `kiwoom.stock_price_krx` 의 본 백필 기간만 DELETE 가능 (운영 1년 cap 영역과 분리됨)
- **인증 절약**: alias 가 prod 라면 백필 1회로 토큰 lifecycle 1회 발급/폐기. 즉 백필 도중 토큰 만료 가능 (24h) — TokenManager 가 자동 재발급하지만 로그 모니터링 필요
- **DB 부하**: backfill 단일 worker 가 KRX+NXT 6000 호출 → 약 6000 INSERT batch. PG 의 connection pool 이 이를 흡수 (`database_pool_size=5` 디폴트)
