# Session Handoff

> Last updated: 2026-05-14 (KST) — Phase D scheduler misfire_grace_time 통일 완료 (옵션 C + 보조 E 채택) / 컨테이너 재배포 + 5-15 catch-up 검증은 다음.
> Branch: `master`
> Latest commit: `d36cf51` (scheduler dead 원인 확정)
> 미푸시: 본 Phase D chunk commit 1건 예정

## Current Status

**Phase D — scheduler misfire_grace_time 6h 통일 완료** (ADR § 42.5 옵션 C 채택). 12 cron 모두 wake 후 catch-up 가능. cross-scheduler race 위험은 plan doc 보강 + 운영 모니터.

### Pipeline 진행 현황 (ted-run)

| Step | 상태 | 모델 | 비고 |
|------|------|------|------|
| 0. TDD | ✅ | sonnet | 8 test 파일 단언 추가 / red 9 fail |
| 1. 구현 | ✅ | opus (메인) | scheduler.py 12 클래스 / +52 line |
| 2a. 1차 리뷰 | ✅ PASS | sonnet | MEDIUM 3 (docstring 구값) 즉시 fix |
| 2b. 적대적 리뷰 | ✅ PASS | opus | MEDIUM 2 (cross race + diag 가시성) 처리 |
| 3. Verification | ✅ PASS | sonnet/haiku | ruff clean / mypy 95 files / 1199 tests / cov 86.17% |
| 4. E2E | ⚪ | — | UI 변경 0 |
| 5. Ship | 🔄 | — | ADR § 43 + 메타 3종 + 커밋 + 푸시 |

### 본 chunk 핵심 변경

```python
# app/scheduler.py — 12 클래스 모두
MISFIRE_GRACE_SECONDS: Final[int] = 21600  # 6h
# add_job 에 misfire_grace_time=self.MISFIRE_GRACE_SECONDS kwarg

# app/main.py /admin/scheduler/diag — jobs dump
"misfire_grace_time": j.misfire_grace_time,  # 운영 가시화 (2b M-2)
```

| 클래스 | 변경 |
|--------|------|
| SectorSync / StockMaster / StockFundamental / OhlcvDaily / DailyFlow | 신규 21600 |
| WeeklyOhlcv / MonthlyOhlcv / YearlyOhlcv / SectorDailyOhlcv | 신규 21600 |
| ShortSelling (1800→21600) / LendingMarket (1800→21600) / LendingStock (5400→21600) | 갱신 |

### 이중 리뷰 MEDIUM 처리

- **2a M-1/M-2/M-3** docstring 구값 (scheduler.py L94 / L1122 / test_scheduler_phase_e Scenario 9) → 즉시 갱신
- **2b M-1** cross-scheduler catch-up race — 6h grace 시 5+ cron 동시 catch-up → KiwoomClient 인스턴스 단위 lock 한계 → KRX rate limit 위반 위험. **plan doc § 5 H-6 보강** + 운영 모니터 + 위반 시 별도 chunk
- **2b M-2** `/admin/scheduler/diag` `misfire_grace_time` 미노출 → main.py:902 fix

## Completed This Session

| # | Task | 결과 | Files |
|---|------|------|-------|
| 1 | scheduler dead 분석 (이전 chunk) | Mac 절전 확정 / ADR § 42 | 4 / `d36cf51` |
| 2 | 옵션 C + 보조 E 채택 (사용자 결정) | 노트북 + 학습 우선 | — |
| 3 | plan doc 작성 | `phase-d-scheduler-misfire-grace.md` | 1 신규 |
| 4 | **ted-run 풀 파이프라인** | Step 0~5 / 1R+2R PASS / Verification 5관문 PASS | 10 / `<pending commit>` |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| **1** | **컨테이너 재배포 + 5-15 (목) 06:00 catch-up 검증** | **다음 세션 1순위** | docker compose build + up -d → 12 cron 의 misfire_grace_time=21600 적용 → 5-15 06:00 OhlcvDaily 자연 cron + Mac wake 시각 (오전~정오) 안 catch-up 발화 확인 + base_date previous_business_day (5-14) 정합 |
| **2** | **F chunk — ka10001 NUMERIC overflow + sentinel WARN/skipped 분리** | 별도 ted-run | Mac 결정과 독립 / Migration 신규 |
| **3** | (조건부) cross-scheduler rate limit race 별도 chunk | 운영 위반 시 진입 | 2b 2R M-1. 공유 KiwoomClient singleton 또는 cross-scheduler asyncio.Semaphore |
| **4** | (5-19 이후) § 36.5 1주 모니터 측정 | 본 chunk 효과 확정 후 | 12 scheduler elapsed / catch-up 빈도 / misfire skip 빈도 |
| **5** | Phase F / G / H 신규 endpoint wave | 대기 | 25 endpoint 완료까지 |
| **6** | Phase D-2 ka10080 분봉 (마지막) | 대기 | 대용량 파티션 결정 동반 |
| **7** | secret 회전 / .env.prod 정리 | 전체 개발 완료 후 | — |

## Key Decisions Made (본 chunk)

1. **misfire_grace_time = 21600s (6h) 통일** — 9 신규 + 3 갱신. 노트북 wake 분포 (09~13시) 안 catch-up.
2. **`_PhaseEJobView` wrap 차이 인정** — 3개 Phase E 클래스만 timedelta 반환 / 9 신규는 raw int. 테스트도 클래스별 정합 비교 (int 21600 vs timedelta(21600)).
3. **cross-scheduler race 별도 chunk 이월** — 본 chunk 의 직접 결함 아니지만 grace 도입으로 노출. 운영 모니터로 측정 후 진입.
4. **`/admin/scheduler/diag` misfire 노출 추가** — 운영 가시화 (catch-up 발생 추적 도구).
5. **plan doc § 5 H-6 보강** — 2b 적대적 리뷰 의 cross-scheduler 발견 사실 plan doc 에 반영.

## Known Issues

| # | 항목 | 출처 | 결정 |
|---|------|------|------|
| 13 | 일간 cron 실측 | dry-run § 20.4 → § 36 / § 38 / § 43 | 5-19 이후 측정 |
| 20 | NXT 우선주 sentinel 빈 row 1 | § 32.3 | LOW |
| 22 | `.env.prod` 정리 | § 38.6.2' | 전체 개발 완료 후 |
| 23 | secret 회전 | § 38.8 #6/#7 | 전체 개발 완료 후 |
| **24** | Mac 절전 시 컨테이너 중단 | § 38.8 #1 / § 42 | ✅ **§ 43 옵션 C 채택** — misfire 6h grace + backfill CLI 보조 |
| **29** | ka10001 stock_fundamental 7.2% 실패 | `478efaa` | F chunk |
| **31** | cross-scheduler catch-up race — 5+ cron 동시 발화 KRX rate limit 위험 | 본 chunk 2b 2R M-1 | plan § 5 H-6 보강. 운영 위반 시 별도 chunk |

## Context for Next Session

### 다음 세션 진입 시 즉시 할 일

```bash
cd /Users/heowooyong/cursor/learning/ted-startup/src/backend_kiwoom

# 1) 컨테이너 재배포 (Migration 0)
docker compose build kiwoom-app
docker compose up -d kiwoom-app

# 2) misfire_grace_time 노출 검증 (2b M-2 효과)
docker compose exec -T kiwoom-app python -c "
import os, httpx, json
r = httpx.get('http://localhost:8001/admin/scheduler/diag', headers={'X-API-Key': os.environ['ADMIN_API_KEY']}, timeout=10)
d = r.json()
for s in d.get('schedulers', []):
    for j in s.get('jobs', []):
        print(f\"{j.get('id')}: misfire={j.get('misfire_grace_time')}\")
"
# 기대: 12 cron 모두 misfire=21600

# 3) 5-15 (목) 06:00 OhlcvDaily catch-up 검증 (5-15 정오 이후)
# Mac 잠 자도 OK — wake 시점에 catch-up 발화 확인
docker compose logs kiwoom-app --since 12h 2>&1 | grep -E "ohlcv daily sync|Running job|catch-up|misfire"

# 4) 5-15 DB row count
PGPASSWORD=kiwoom psql -h localhost -p 5433 -U kiwoom -d kiwoom_db -c "
SELECT trading_date, count(*) FROM kiwoom.stock_price_krx WHERE trading_date >= DATE '2026-05-14' GROUP BY trading_date ORDER BY trading_date;
"
```

기대:
- 12 cron 모두 misfire=21600 노출
- Mac 정오 이전 wake 시 5-15 06:00 ohlcv_daily 자연 catch-up 발화
- DB stock_price_krx 5-14 (수) row 적재

### 운영 위험 / 주의

- **5-14 (목) 새벽 cron miss**: 본 chunk 머지 + 재배포 시점이 5-14 일중 → 5-14 06:00/06:30 cron 은 이미 지나서 catch-up 영향 X
- **5-15 (금) 06:00 첫 운영 검증** — 본 chunk 효과 확정 시점. Mac active 또는 정오 이전 wake 권고
- **cross-scheduler race 모니터**: 5-15 발화 후 docker logs 에 429 / alias revoke 발생 확인
- **wake 시 5+ cron 동시 catch-up 시 KRX 부하**: 6h 안에 catch-up 못 한 cron 은 skip → backfill CLI 회복

## Files Modified This Session

### 2 코드
- `src/backend_kiwoom/app/scheduler.py` — 12 클래스 정책 통일 (+52 / -10) + docstring 구값 갱신 2건
- `src/backend_kiwoom/app/main.py` — `/admin/scheduler/diag` misfire 노출 (+2)

### 8 테스트
- 7 신규 test 파일 (각 +2~4 line) — int 21600 단언
- `test_scheduler_phase_e.py` — `_6h` 통일 + docstring 갱신

### 1 plan doc (신규)
- `src/backend_kiwoom/docs/plans/phase-d-scheduler-misfire-grace.md`

### 1 ADR 갱신
- `docs/adr/ADR-0001-backend-kiwoom-foundation.md` § 43 신규 (7 sub-§) + § 42.8 갱신

### 3 메타 갱신
- `src/backend_kiwoom/STATUS.md`
- `HANDOFF.md` (본 파일)
- `CHANGELOG.md` prepend

### Verification

- ruff: clean (unused import 8건 자동 fix)
- mypy --strict: 95 files Success
- pytest: 1199 passed / cov 86.17%
- E2E: ⚪ / 보안 스캔: ⚪

---

_Phase D scheduler misfire chunk 완결. Mac 노트북 + 학습 우선 사용자 환경에 맞춘 6h catch-up 정책. 5-15 (목) 06:00 자연 cron + Mac wake 시 catch-up 검증이 본 chunk 효과 확정 시점._
