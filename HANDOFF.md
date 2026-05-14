# Session Handoff

> Last updated: 2026-05-14 (KST) — Phase D 운영 검증 + kiwoom-db restart 정책 fix + 5-13 backfill 회복 / 다음 1순위 = 5-15(금) 06:00 자연 cron 검증
> Branch: `master`
> Latest commit: `<pending>` (본 turn ops fix + 메타 4종)
> 미푸시: 본 turn commit 1건 예정

## Current Status

§ 43 Phase D misfire chunk 머지 후 **운영 검증 turn** — 컨테이너 재배포 + Docker 정리 + 5-15 catch-up 검증 진입 → 인시던트 발견 → 3 트랙 (A backfill + B 체크리스트 + C 원인 분석) 병렬 완료. ADR § 44 신규.

### 본 turn 핵심 변경 (config 1줄 + ADR § 44 + 메타 3종)

```yaml
# src/backend_kiwoom/docker-compose.yml — kiwoom-db.healthcheck 다음 1줄
    restart: unless-stopped
```

라이브 동시 적용: `docker update --restart unless-stopped kiwoom-db` (재생성 X, backfill 보존).

| 항목 | 결과 |
|------|------|
| 컨테이너 재배포 | ✅ 신규 이미지 (`79d1355` Phase D 적용) — kiwoom-app healthy 09:51 KST |
| **misfire=21600 노출** | ✅ 12/12 cron 모두 `/admin/scheduler/diag` 에 정상 노출 |
| Docker 정리 | 이미지 26→9 (1.3GB) + 빌드 캐시 15.6→1.1GB (**14.5GB**) / **총 15.8GB 회수** |
| **catch-up 발화 검증** | ❌ 신규 컨테이너 09:51 시작 + 06:00 cron grace 6h 안인데도 발화 0건 → **scheduler restart 시나리오 한계 발견** (MemoryJobStore 신규 → 과거 missed cron 휘발). § 43 효과는 sleep/resume 자연 사이클 한정 |
| **운영 인시던트 발견** | 5-14 07:21 KST kiwoom-db ExitCode 0 정상 종료 + 자동 복구 ❌ + kiwoom-app restart loop. Root cause = `docker-compose.yml` 의 kiwoom-db `restart:` 누락 (디폴트 `no`) |
| **C fix 적용** | `restart: unless-stopped` 1줄 추가 + 라이브 update — RestartPolicy 검증 = `unless-stopped` (kiwoom-db + kiwoom-app 둘 다) |
| **A 5-13 backfill 회복** | 5 테이블 / **15,898 row** / KRX ~18,500 호출 / 4xx-5xx 0건 |
| B 5-15 검증 체크리스트 | 5 항목 명령 정리 |

### 5-13 backfill 회복 상세

| 단계 | 테이블 | 적재 | 비고 |
|------|--------|------|------|
| 1/5 ohlcv_daily | stock_price_krx | **4,375** row | exit 0 |
| 2/5 daily_flow | stock_daily_flow | **5,008** row | exit 0 |
| 3/5 short | short_selling_kw | **2,441** row | fail 307 (alphanumeric K/L guard) / **exit 1** → set -e 차단 |
| 4/5 lending_market | lending_balance_kw (scope=MARKET) | 1 row | exit 0 (체인 재실행 시) |
| 5/5 lending_stock | lending_balance_kw (scope=STOCK) | **4,072** row | fail 303 (alphanumeric K/L guard) / exit 1 / 1019.9s |

**신규 알려진 이슈** (STATUS § 4 #31): `backfill_short.py` / `backfill_lending_stock.py` 5% 임계치 vs alphanumeric guard (~7%) 충돌 → 실제 적재 실패 = 0인데 exit 1 → set -e 시 체인 단절. F chunk 정리 대상.

## Completed This Session (Turn)

| # | Task | 결과 | Files |
|---|------|------|-------|
| 1 | 컨테이너 재배포 (commit `79d1355` 적용) | kiwoom-app healthy + 12/12 mg=21600 | (build only) |
| 2 | Docker 이미지/캐시 정리 | 15.8GB 회수 | (cleanup only) |
| 3 | **A** 5-13 backfill (5 CLI 직렬) | 5 테이블 15,898 row 적재 | (운영 데이터 only) |
| 4 | **C** kiwoom-db restart 정책 fix | docker-compose.yml + 라이브 update | 1 config |
| 5 | **B** 5-15 검증 체크리스트 | 5 항목 명령 + 판정 매트릭스 | (대화 정리) |
| 6 | ADR § 44 + STATUS / HANDOFF / CHANGELOG 갱신 | 본 메타 4종 | 4 |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| **1** | **5-15 (금) 06:00 자연 cron 검증** | **다음 세션 1순위** | 체크리스트 5종 (ohlcv 자연 발화 / DB 5-14 / 컨테이너 uptime+Restarts / misfire / pmset sleep). § 43 + § 44 효과 진정 검증 시점. base_date previous_business_day = 5-14 (목 영업일) 정합 |
| **2** | **F chunk** — ka10001 NUMERIC overflow + sentinel WARN/skipped 분리 + **backfill 임계치/alphanumeric 분리** | 별도 ted-run | 본 turn 추가 (§ 44.9 / STATUS § 4 #31) |
| **3** | (조건부) cross-scheduler rate limit race 별도 chunk | 운영 위반 시 진입 | § 43.7 변동 없음 |
| **4** | (5-19 이후) § 36.5 1주 모니터 측정 | § 43 효과 정량화 | 12 scheduler elapsed / catch-up 빈도 / misfire skip 빈도 |
| **5** | Phase F / G / H 신규 endpoint wave | 대기 | 25 endpoint 60% (15/25) |
| **6** | Phase D-2 ka10080 분봉 (마지막) | 대기 | 대용량 파티션 결정 동반 |
| **7** | secret 회전 / .env.prod 정리 | 전체 개발 완료 후 | — |

## Key Decisions Made (본 turn)

1. **kiwoom-db `restart: unless-stopped`** — docker-compose.yml + 라이브 update 동시 적용. `kiwoom-app` 과 비대칭 해소
2. **catch-up 시나리오 한계 인정** — § 43 효과는 sleep/resume 자연 사이클 한정 / scheduler restart 시나리오에는 무효 → backfill CLI 회복 (보조 E) 정당성 강화
3. **5-13 backfill = 보조 E 정책 첫 발동 + 성공** — 5 테이블 15,898 row / 알려진 alphanumeric guard 만 fail
4. **backfill 임계치/alphanumeric 분리 = F chunk 합류** — 본 turn 발견 / 실제 적재 실패 = 0 / 체인 단절 회피

## Known Issues

| # | 항목 | 출처 | 결정 |
|---|------|------|------|
| 13 | 일간 cron 실측 | dry-run § 20.4 → § 36 / § 38 / § 43 | 5-19 이후 측정 |
| 20 | NXT 우선주 sentinel 빈 row 1 | § 32.3 | LOW |
| 22 | `.env.prod` 정리 | § 38.6.2' | 전체 개발 완료 후 |
| 23 | secret 회전 | § 38.8 #6/#7 | 전체 개발 완료 후 |
| ~~24~~ | ~~Mac 절전 시 컨테이너 중단~~ | § 38.8 #1 / § 42 / § 43 / § 44 | 🔄 **부분 해소** — § 43 misfire + § 44 kiwoom-db restart + backfill CLI 회복 검증 완료. **5-15 자연 cron 진정 검증** |
| **29** | ka10001 stock_fundamental 7.2% 실패 | `478efaa` | F chunk |
| 30 | 본 chunk 2b 2R M-1 cross-scheduler catch-up race | § 43 plan doc § 5 H-6 | 운영 위반 시 별도 chunk |
| **31** | **backfill 임계치 5% vs alphanumeric guard 7% 충돌** | 본 turn § 44.9 | **F chunk 합류** — failed vs alphanumeric_skipped 분리 |

## Context for Next Session

### 다음 세션 진입 시 즉시 할 일 — 5-15 (금) 자연 cron 검증

```bash
cd /Users/heowooyong/cursor/learning/ted-startup/src/backend_kiwoom

# 1) 06:00 ohlcv 자연 cron 발화 로그 (catch-up 포함)
docker compose logs kiwoom-app --since 12h 2>&1 | \
  grep -iE "ohlcv daily|daily flow|sector daily|short selling|lending|Run time of job|catch-up|misfire"

# 2) DB 5-14 (목 영업일) 적재 검증
PGPASSWORD=kiwoom psql -h localhost -p 5433 -U kiwoom -d kiwoom_db -c "
SELECT 'stock_price_krx' AS tbl, count(*) AS rows FROM kiwoom.stock_price_krx WHERE trading_date = DATE '2026-05-14'
UNION ALL SELECT 'stock_daily_flow', count(*) FROM kiwoom.stock_daily_flow WHERE trading_date = DATE '2026-05-14'
UNION ALL SELECT 'sector_price_daily', count(*) FROM kiwoom.sector_price_daily WHERE trading_date = DATE '2026-05-14'
UNION ALL SELECT 'short_selling_kw', count(*) FROM kiwoom.short_selling_kw WHERE trading_date = DATE '2026-05-14'
UNION ALL SELECT 'lending_balance_kw', count(*) FROM kiwoom.lending_balance_kw WHERE trading_date = DATE '2026-05-14'
ORDER BY tbl;"

# 3) 컨테이너 uptime + restart 정책 효과
docker compose ps --format 'table {{.Service}}\t{{.Status}}'
docker inspect kiwoom-db --format 'Started: {{.State.StartedAt}} | Restarts: {{.RestartCount}} | Policy: {{.HostConfig.RestartPolicy.Name}}'

# 4) misfire 재확인 (12/12 mg=21600)
docker compose exec -T kiwoom-app python -c "
import os, httpx
r = httpx.get('http://localhost:8001/admin/scheduler/diag', headers={'X-API-Key': os.environ['ADMIN_API_KEY']}, timeout=10)
for s in r.json()['schedulers']:
    for j in s['jobs']:
        print(f\"{s['name']:24s} mg={j.get('misfire_grace_time')}\")"

# 5) Mac sleep/wake 이력
pmset -g log | grep -v Assertion | grep -E "^2026-05-1[45]" | grep -iE "Sleep|Wake|smc.sysState"
```

### 판정 매트릭스

| 시나리오 | 결과 |
|---|---|
| 5-15 06:00 Mac active → 자연 cron 정상 발화 + 즉시 적재 | 본 chunk 효과 부분 검증 (misfire grace 미사용) |
| 5-15 06:00 Mac sleep → wake 시점 catch-up 발화 (6h 안) + 적재 | **§ 43 효과 완전 검증** ✅ |
| 5-15 06:00 Mac sleep → 정오 이후 wake (6h 초과) → skip | misfire grace 한계 → backfill CLI 회복 |
| kiwoom-db 재시작 흔적 있음 + 자동 복구됨 | **§ 44 fix 효과 검증** ✅ |

### 운영 위험 / 주의

- **5-15 (금) 06:00 첫 진정 검증 시점** — § 43 + § 44 효과 동시 확인
- **cross-scheduler race 모니터**: 5-15 발화 후 docker logs 에 429 / alias revoke 발생 확인
- **5+ cron 동시 catch-up 시 KRX 부하**: 6h 안에 catch-up 못 한 cron 은 skip → backfill CLI 회복

## Files Modified This Session (Turn)

### 1 config
- `src/backend_kiwoom/docker-compose.yml` — `kiwoom-db.healthcheck` 다음 1줄 `restart: unless-stopped` 추가

### 1 ADR 갱신
- `docs/adr/ADR-0001-backend-kiwoom-foundation.md` § 44 신규 (10 sub-§)

### 3 메타 갱신
- `src/backend_kiwoom/STATUS.md` (§ 0 / § 4 / § 5)
- `HANDOFF.md` (본 파일 — rewrite)
- `CHANGELOG.md` prepend

### 코드 변경 0 / Migration 0 / 테스트 변경 0

### 운영 검증 결과 (DB 5-13)

```
           tbl           | rows
-------------------------+------
 lending_balance_kw      | 4073
 sector_price_daily      |  123
 short_selling_kw        | 2441
 stock_daily_flow        | 5008
 stock_price_krx (ohlcv) | 4375
```

총 5-13 적재 = **15,898 row**.

---

_본 turn = 운영 인시던트 후속 (config 1줄 + 라이브 update + backfill 회복 + 메타). § 43 효과 진정 검증 = 5-15 06:00 자연 cron 발화 + Mac wake catch-up 사이클._
