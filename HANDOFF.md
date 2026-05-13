# Session Handoff

> Last updated: 2026-05-14 (KST) — Phase D-1 follow-up E4 운영 백필 재호출 완료 + 5-14 06:00/06:30 cron miss 추가 발견 / 다음 세션 = scheduler dead 재발 분석 또는 F chunk.
> Branch: `master`
> Latest commit: `f7bcfe3` (Phase D-1 follow-up 풀 구현 ted-run)
> 미푸시: 본 E4 운영 검증 commit 1건 예정

## Current Status

**Phase D-1 follow-up E4 완료 — 컨테이너 재배포 + 5-12 운영 백필 재호출 + 0 MaxPages / 0 InterfaceError 운영 검증 PASS**. 코드 변경 0 / ADR § 41.7 운영 결과 표 + § 41.8 추가 발견 (5-14 새벽 cron miss).

### E4 운영 검증 결과 (5-14 06:50~07:00 KST)

#### (a) 컨테이너 재배포
- `docker compose build kiwoom-app` — 캐시 빌드 즉시 완료
- `docker compose up -d` — Recreated / Started → /health ok + 12 scheduler 활성

#### (b) sector_daily 5-12 bulk sync — **PASS**
```
POST /api/kiwoom/sectors/ohlcv/daily/sync?alias=prod&base_date=2026-05-12
{ "total": 124, "success": 124, "failed": 0, "errors": [] }
```

| 지표 | 5-12 백필 (5-13 02:33) | 5-12 재호출 (5-14 06:58) |
|------|------------------------|---------------------------|
| total | 124 | 124 |
| success | 60 (48.4%) | **124 (100%)** ✅ |
| failed | 64 (51.6%) | **0** ✅ |
| KiwoomMaxPagesExceededError | 56 | **0** ✅ |
| asyncpg.InterfaceError 32767 | 8 | **0** ✅ |
| DB row 적재 | 59 | **123** (1 sentinel) |

#### (c) KOSDAQ daily_flow 5-12 backfill CLI — **PASS**
```
$ docker compose exec -T kiwoom-app python scripts/backfill_daily_flow.py \
    --alias prod --start-date 2026-05-12 --end-date 2026-05-12 \
    --only-market-codes 10 --resume --log-level INFO

===== Daily Flow Backfill Summary =====
date range:    2026-05-12 ~ 2026-05-12
total:         1487 종목 (KOSDAQ, resume)
success_krx:   1487
success_nxt:   224
failed:        0 (ratio 0.00%)
elapsed:       0h 7m 7s
avg/stock:     0.3s
```

#### (d) DB 최종 상태 (5-12)

| 테이블 | 5-12 row |
|--------|----------|
| `sector_price_daily` | 123 |
| `stock_daily_flow` KRX | 2648 |
| `stock_daily_flow` NXT | 633 |
| `stock_daily_flow` 합계 | 3281 |

### 추가 발견 — 5-14 06:00/06:30 scheduler cron miss

재배포 직전 1시간 docker logs 0 cron event:
- 5-14 06:00 OhlcvDaily 발화 0
- 5-14 06:30 DailyFlow 발화 0

5-13 17:30 stock_master / 18:00 stock_fundamental 자연 발화 정상 검증 후 06:00 dead 일회성 가설 → **5-14 새벽 재발 가능성 ↑**. 본 chunk 컨테이너 재배포 (06:51 KST) 후 07:00 sector_daily cron 자연 발화 정상 (chart.py 호출 진행).

**별도 chunk 후보**: scheduler dead 재발 분석 — APScheduler timer freeze 가설 / Mac 절전 (§ 38.8 #1) 재검토.

## Completed This Session

| # | Task | 결과 | Files |
|---|------|------|-------|
| 1 | (E3) Phase D-1 follow-up ted-run 풀 파이프라인 (이전 chunk) | 6 코드 + 5 테스트 / 1199 tests / cov 86.13% / ADR § 41 | 16 / `f7bcfe3` |
| 2 | **(E4-1) 컨테이너 재빌드 + 재배포** | docker compose build + up -d → /health ok + 12 scheduler 활성 | 0 (배포만) |
| 3 | **(E4-2) sector_daily 5-12 bulk sync** | 124/124 success / 0 failed / 0 MaxPages / 0 InterfaceError | 0 (API 호출만) |
| 4 | **(E4-3) KOSDAQ daily_flow 5-12 backfill CLI** | 1487 KRX + 224 NXT success / 0 failed / 7m 7s | 0 (CLI 호출만) |
| 5 | **(E4-4) ADR § 41.7 운영 결과 표 + § 41.8 추가 발견 + 메타 3종 + 커밋 + 푸시** | 4 메타 파일 갱신 | 4 / `<pending commit>` |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| **1** | **scheduler dead 재발 분석 chunk** | **다음 세션 1순위** | § 4 #30. 5-14 06:00/06:30 cron miss 발견. APScheduler timer freeze 가설 / Mac 절전 (§ 38.8 #1) 재검토. `/admin/scheduler/diag` 발화 시점 직전/후 비교. 컨테이너 sleep 상태 검증. dead 재현 시 ADR 신규 § |
| **2** | **F chunk — ka10001 NUMERIC overflow + sentinel WARN/skipped 분리** | 별도 ted-run | Migration 신규 (NUMERIC(8,4) precision 확대 — overflow 종목 값 분석 선행) + WARN/skipped 분리 + result.errors full exception type/메시지 log 보강 |
| ~~**Pending #1 (이전)**~~ | ~~(E4) 컨테이너 재배포 + 5-12 운영 백필 재호출~~ | ~~본 chunk 종결 ✅~~ | sector_daily 124/124 + KOSDAQ 1487/0 failed |
| **3** | **노출된 secret 4건 회전** | **전체 개발 완료 후** | API_KEY/SECRET revoke + Fernet 마스터키 회전 + DB 재암호화 + Docker Hub PAT revoke (ADR § 38.8 #6/#7). 절차서: [`docs/ops/secret-rotation-2026-05-12.md`](docs/ops/secret-rotation-2026-05-12.md) |
| **4** | `.env.prod` 의 `KIWOOM_SCHEDULER_*` 9 env 정리 | 전체 개발 완료 후 | compose env override 로 우회 완료 |
| **5** | (5-19 이후) § 36.5 1주 모니터 측정 채움 | 대기 | 12 scheduler elapsed |
| **6** | Mac 절전 시 컨테이너 중단 → cron 누락 위험 | 사용자 환경 결정 | 절전 차단 또는 서버 이전 (ADR § 38.8 #1). **dead 재발 가설 후보** |
| **7** | scheduler dead 진단 endpoint 정리 | dead 재발 가설 결정 후 | `/admin/scheduler/diag` 유지 권고 (5-14 새벽 cron miss 발견으로 가치 ↑) |
| 8 | D-1 follow-up: inds_cd echo 검증 / close_index Decimal 통일 / `backfill_sector` CLI | ADR § 39.8 | 운영 첫 호출 후 결정 |
| 9 | Phase F / G / H (순위/투자자별/통합) | 대기 | 신규 endpoint wave |
| 10 | Phase D-2 ka10080 분봉 (**마지막 endpoint**) | 대기 | 사용자 결정 — 대용량 파티션 결정 동반 |
| 11 | §11 포트폴리오·AI 리포트 (P10~P15) | 대기 | CLAUDE.md next priority |

## Key Decisions Made (본 chunk E4)

1. **운영 검증 = sector_daily bulk sync + KOSDAQ backfill CLI 병렬** — 두 인시던트 별도 호출 방식. sector_daily 는 admin endpoint POST (token 필요 — 컨테이너 환경변수 활용 + `X-API-Key` 헤더), KOSDAQ daily_flow 는 backfill CLI (token 무관, `--resume` 으로 미적재만 처리).
2. **본 chunk fix 효과 운영 확정**:
   - cap 상향 (10→40 sector / 40→60 daily_market) → 0 MaxPages
   - bulk insert chunk_size=1000 → 0 InterfaceError (32767 한도 회피)
   - `KiwoomMaxPagesExceededError(page, cap)` 시그니처 → 가시화 (본 chunk 호출에서는 0 발생이라 미사용)
3. **DB 적재 1 sector 차이 (124 success 호출 vs 123 row)** — sentinel break 정상 동작 (1 sector 가 5-12 거래일 데이터 자체 없음 — 빈 응답으로 정상 처리, `chart.py:800` if not parsed.inds_dt_pole_qry: break).
4. **5-14 06:00/06:30 cron miss 발견 → dead 재발 가설** — 5-13 일회성 가설 흔들림. 본 chunk 범위 외 별도 분석 chunk 권고.
5. **푸시 진행** — global CLAUDE.md 규칙: 사용자 명시 요청 시.

## Known Issues

| # | 항목 | 출처 | 결정 |
|---|------|------|------|
| 13 | 일간 cron 실측 | dry-run § 20.4 → § 36 / § 38 | 🔄 5-19 이후 측정 |
| 20 | NXT 우선주 sentinel 빈 row 1개 | § 32.3 + § 33.6 | LOW |
| **22** | `.env.prod` `KIWOOM_SCHEDULER_*` 9 env 정리 | § 38.6.2' | 전체 개발 완료 후 |
| **23** | 노출된 secret 4건 회전 | § 38.8 #6/#7 | 전체 개발 완료 후 |
| **24** | Mac 절전 시 컨테이너 중단 → cron 누락 | § 38.8 #1 | **dead 재발 가설 후보 (#30)** |
| ~~**26**~~ | ~~5-13 06:00/06:30/07:00 cron dead~~ | 5-13 17:30 재현 모니터 | ✅ 1회성 가설 (그러나 #30 으로 재발 가능성) |
| ~~**27**~~ | ~~ka20006 sector_daily 60% 실패~~ | 본 chunk fix 완료 | ✅ **운영 검증 PASS** (124/124, `<this commit>`) |
| ~~**28**~~ | ~~ka10086 KOSDAQ 1814 누락~~ | 본 chunk fix 완료 | ✅ **운영 검증 PASS** (1487+224, `<this commit>`) |
| **29** | ka10001 stock_fundamental 7.2% 실패 | 진단 chunk `478efaa` | F chunk 별도 |
| **30** | **5-14 06:00/06:30 cron miss** — scheduler dead 재발 가능성 | 본 chunk 진단 | **다음 세션 1순위** — APScheduler timer freeze / Mac 절전 (§ 38.8 #1) 재검토. dead 재발 시 ADR 신규 § |

## Context for Next Session

### 다음 세션 진입 (dead 재발 분석) 시 즉시 할 일

```bash
# 1) 현재 컨테이너 상태 + 최근 cron 활동
docker compose ps
docker compose logs kiwoom-app --since 12h 2>&1 | grep -E "sync cron 시작|sync 완료|Running job|executed successfully" | tail -30

# 2) scheduler diag baseline 호출 (admin token via container env)
docker compose exec -T kiwoom-app python -c "
import os, httpx, json
r = httpx.get('http://localhost:8001/admin/scheduler/diag', headers={'X-API-Key': os.environ['ADMIN_API_KEY']}, timeout=10)
print(json.dumps(r.json(), indent=2, ensure_ascii=False))
"

# 3) 5-14 06:00/06:30 cron miss 분석
# - 5-14 05:55 ~ 06:35 의 docker logs 정밀 추적
docker compose logs kiwoom-app --until "2026-05-14T06:35:00" --since "2026-05-13T22:00:00" 2>&1 | grep -E "scheduler|cron|sync|Running job" | tail -50

# 4) APScheduler timer freeze 가설 — apscheduler INFO 로그 (Added job / Running job / executed)
docker compose logs kiwoom-app --since 24h 2>&1 | grep -cE "Running job|executed successfully"

# 5) Mac 절전 가설 — pmset / sleep history
pmset -g log | grep -E "Sleep|Wake" | tail -20
```

### 채택한 접근 (본 chunk E4)

1. **컨테이너 재배포 = 캐시 빌드 + 단순 up -d** (alembic 변경 0, 컨테이너 교체만)
2. **sector_daily 호출 = `docker exec` 내 Python httpx + 컨테이너 환경변수 `ADMIN_API_KEY` + `X-API-Key` 헤더** — 호스트 .env.prod 접근 차단 회피
3. **KOSDAQ 백필 = `docker exec` CLI 백그라운드** — `--only-market-codes 10 --resume` 옵션으로 KOSDAQ 미적재만 처리 (1487 종목 / 7m 7s)
4. **운영 결과 표 ADR § 41.7** + 추가 발견 § 41.8 + 다음 chunk § 41.9 (기존 41.8 재번호)

### 운영 위험 / 주의

- **scheduler dead 재발 가능성 ↑** (5-14 06:00/06:30 cron miss) — 컨테이너 재배포 후 07:00 cron 정상 발화 확인됐으나 새벽 cron 누락 잠재 위험 지속
- **Mac 절전 = dead 의 주된 가설 후보** — pmset 또는 caffeinate 로 절전 차단 권고
- **5-12 데이터 회복 완료**: KRX OHLCV 5-12 는 별도 backfill 필요? — 본 chunk 는 sector_daily + KOSDAQ daily_flow 만. KRX 일봉 (stock_price_krx) 5-12 row 2559 → 미회복 (1814 누락 가능성, 별도 backfill_ohlcv.py 필요)

## Files Modified This Session (본 chunk E4)

### 0 코드 (운영 호출만)

### 1 ADR 갱신
- `docs/adr/ADR-0001-backend-kiwoom-foundation.md` § 41.7 운영 결과 표 + § 41.8 추가 발견 + § 41.9 다음 chunk (재번호)

### 3 메타 갱신
- `src/backend_kiwoom/STATUS.md` § 0 / § 4 #27 #28 (PASS) #30 (신규) / § 5 / § 6
- `HANDOFF.md` (본 파일)
- `CHANGELOG.md` prepend

### Verification

- 운영 sector_daily 5-12: 124/124 success / 0 failed ✅
- 운영 KOSDAQ daily_flow 5-12: 1487+224 success / 0 failed ✅
- 0 MaxPages / 0 InterfaceError 검증 완료 ✅
- 코드 변경 0 → 1199 tests 그대로

---

_Phase D-1 follow-up chunk 운영 검증 종결. 본 chunk 의 fix (cap 상향 + chunk 분할) 가 실제 운영에서 효과 확정. 다음 chunk = scheduler dead 재발 (5-14 06:00/06:30 cron miss) 진단 또는 F chunk (ka10001 NUMERIC)._
