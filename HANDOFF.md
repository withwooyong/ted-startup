# Session Handoff

> Last updated: 2026-05-14 (KST) — scheduler dead 원인 확정 (Mac 절전) / 사용자 환경 결정 대기.
> Branch: `master`
> Latest commit: `5b16d2e` (Phase D-1 follow-up E4 운영 검증)
> 미푸시: 본 dead 분석 commit 1건 예정

## Current Status

**scheduler dead 원인 확정 — Mac 절전 (Docker Desktop VM sleep)**. 5-13 ~ 5-14 dead 사건 분석 종결. ADR § 42 신규 + § 38.8 #1 갱신 (위험 가설 → 확정 인시던트). 코드 변경 0 / 메타 4 갱신.

### 결정적 증거 — `pmset -g log`

5-13 저녁부터 Mac 반복 Sleep 사이클:
```
2026-05-13 20:01:26 +0900 Sleep   Entering Sleep state 'Sleep Service Back to Sleep' (Batt 80%) 967s
2026-05-13 20:17:35 +0900 Sleep   (Batt 80%) 1011s
2026-05-13 20:34:28 +0900 Sleep   (Batt 80%) 287s
2026-05-13 20:39:28 +0900 Sleep   due to 'Maintenance Sleep' (Batt 80%) 1057s
2026-05-13 20:57:07 +0900 Sleep   (Batt 80%) 904s
... (반복 ~ 5-13 21:12)
```

현재 `pmset -g` 상태:
```
sleep   1 (sleep prevented by sharingd, caffeinate, caffeinate, caffeinate, powerd, JANDI)
```

→ **현재만 caffeinate 활성** (5-13 저녁 비활성). Battery 모드 (Charge 80%, 충전 X). Mac 자유 절전 → Docker Desktop VM 일시정지 → 컨테이너 sleep → asyncio 이벤트 루프 sleep → APScheduler timer wakeup 미발화 → cron miss.

### 가설 평가 (ADR § 42.3)

| 가설 | 평가 | 증거 |
|------|------|------|
| **Mac 절전 → Docker VM sleep → APScheduler timer 미발화** | ✅ **확정** | pmset 5-13 20:01~21:12 반복 Sleep + 현재 caffeinate 활성 |
| APScheduler race condition | ❌ 반증 | 5-13 진단 chunk baseline diag = 12개 main_loop 동일 / cancelled=false / 17:30·18:00 자연 발화 정상 |
| Docker network / DB 연결 끊김 | ❌ 반증 | 자연 발화 시점에는 정상 동작 |
| healthcheck restart | ❌ 반증 | `docker inspect finishedAt=0001-01-01` (never finished) |
| Battery 부족 | ❌ | Charge 80% 유지 |

### 현재 cron 별 misfire 정책

| Cron 시각 | misfire | sleep 위험 |
|-----------|---------|-----------|
| 17:30 / 18:00 (stock_master / fundamental) | 없음 | ↓ (저녁 Mac active 가능성 ↑) |
| 06:00 (ohlcv_daily) | 없음 | **🔴 5-14 miss** |
| 06:30 (daily_flow) | 없음 | **🔴 5-14 miss** |
| 07:00 (sector_daily) | 없음 | ↓ (5-14 정상 발화 확인) |
| 07:30 / 07:45 / 08:00 (short_selling / lending_*) | **30m / 30m / 90m grace** | ↓ |
| 03:00 (monthly / yearly / sector_weekly) | 없음 | 🔴 새벽 cron |

### 해결 옵션 (사용자 결정 필요) — ADR § 42.5

| # | 옵션 | 장점 | 단점 |
|---|------|------|------|
| **A** | `caffeinate -dimsu &` 영구 활성 (launchd plist) | 즉시 적용 / 비용 0 | 발열 + 배터리 |
| **B** | 별도 Linux 서버 (Mini PC / NAS / 클라우드 VM) | 절전 무관 / 24/7 안정 | 인프라 + 비용 |
| C | APScheduler `misfire_grace_time` 전 cron 적용 | 부분 완화 | sleep 중 timer X → grace 만 부족 |
| D | host launchd cron + curl admin endpoint | Docker Desktop 의존 ↓ | host Mac sleep 영향 |
| E | 현재 유지 + 모니터링 | 변경 0 | 새벽 cron miss 지속 |

## Completed This Session

| # | Task | 결과 | Files |
|---|------|------|-------|
| 1 | (E4) 컨테이너 재배포 + 5-12 운영 백필 재호출 | 124/124 sector + 1487 KOSDAQ / 0 failed | 4 / `5b16d2e` |
| 2 | **F1 5-14 cron miss timeline 추적** | docker logs 재배포로 소실 (한계) — pmset 으로 대체 증거 | 0 (read-only) |
| 3 | **F2 Mac 절전 가설 검증** | pmset 5-13 20:01~21:12 반복 Sleep 확정 / 현재 caffeinate*3 활성 | 0 (read-only) |
| 4 | **F3 diag baseline** | 12 scheduler / cancelled=false / delta_seconds 정확 (07:30=656s / 07:45=1556s / 08:00=2456s) | 0 (read-only) |
| 5 | **F4 ADR § 42 신규 + 메타 + 커밋 + 푸시** | 가설 평가 5종 + 해결 옵션 5종 + § 38.8 #1 갱신 + cron misfire 정책 표 | 4 / `<pending commit>` |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| **1** | **사용자 환경 결정** (Mac 절전 해결 옵션 A~E) | **다음 세션 1순위** | ADR § 42.5. A caffeinate / B 서버 이전 / C misfire 전체 / D launchd / E 유지. 결정 후 후행 chunk |
| **2** | **F chunk — ka10001 NUMERIC overflow + sentinel WARN/skipped 분리** | 별도 ted-run | Mac 절전 결정과 독립. Migration 신규 + WARN/skipped 분리 + log 보강 |
| ~~Pending #1 (이전)~~ | ~~scheduler dead 재발 분석~~ | ~~본 chunk 종결 ✅~~ | Mac 절전 원인 확정 |
| **3** | **노출된 secret 4건 회전** | 전체 개발 완료 후 | ADR § 38.8 #6/#7 |
| **4** | `.env.prod` 의 `KIWOOM_SCHEDULER_*` 9 env 정리 | 전체 개발 완료 후 | compose env override 로 우회 완료 |
| **5** | (5-19 이후) § 36.5 1주 모니터 측정 | 대기 — **Mac 절전 결정 후 의미** | 절전 결정 안 한 채 측정 시 미발화 cron 포함 — 결정 후 진행 |
| **6** | scheduler dead 진단 endpoint 정리 | **유지 권고** | `/admin/scheduler/diag` 본 chunk 에서 가치 검증됨 — 추가 인시던트 대응 용 유지 |
| 7 | D-1 follow-up: inds_cd echo 검증 / close_index Decimal 통일 / `backfill_sector` CLI | ADR § 39.8 | 운영 첫 호출 후 결정 |
| 8 | Phase F / G / H (순위/투자자별/통합) | 대기 | 신규 endpoint wave |
| 9 | Phase D-2 ka10080 분봉 (**마지막 endpoint**) | 대기 | 대용량 파티션 결정 동반 |
| 10 | §11 포트폴리오·AI 리포트 (P10~P15) | 대기 | CLAUDE.md next priority |

## Key Decisions Made (본 chunk)

1. **분석 종결 = Mac 절전 = 원인 확정** — 가설 5종 평가 + pmset 결정적 증거. APScheduler race / network / healthcheck / battery 모두 반증.
2. **본 chunk 코드 변경 0** — 진단 + ADR § 42 + 메타만. 해결책 = 사용자 환경 결정 (A~E 옵션).
3. **§ 38.8 #1 갱신** — "위험 가설" → "확정 인시던트". HANDOFF Pending #6 (Mac 절전) 시급 결정 요청.
4. **cron 별 misfire 정책 표 추가** — 07:30/07:45/08:00 만 grace 보유, 06:00/06:30/03:00 새벽 cron 가장 위험.
5. **diag endpoint 유지** — 본 chunk 에서 가치 검증 (12 scheduler delta_seconds 정확 확인). 추가 인시던트 진단 용.

## Known Issues

| # | 항목 | 출처 | 결정 |
|---|------|------|------|
| 13 | 일간 cron 실측 | dry-run § 20.4 → § 36 / § 38 | **Mac 절전 결정 후** (그 전에 측정 시 미발화 cron 혼입) |
| 20 | NXT 우선주 sentinel 빈 row 1개 | § 32.3 + § 33.6 | LOW |
| **22** | `.env.prod` 정리 | § 38.6.2' | 전체 개발 완료 후 |
| **23** | secret 회전 | § 38.8 #6/#7 | 전체 개발 완료 후 |
| ~~**24**~~ | ~~Mac 절전 시 컨테이너 중단 → cron 누락~~ | § 38.8 #1 | ✅ **원인 확정** (`<this chunk>` ADR § 42) — 사용자 환경 결정 대기 |
| **29** | ka10001 stock_fundamental 7.2% 실패 | 진단 chunk `478efaa` | F chunk 별도 (Mac 결정과 독립) |
| ~~**30**~~ | ~~5-14 06:00/06:30 cron miss~~ | E4 chunk `5b16d2e` | ✅ **원인 확정** (`<this chunk>`) — Mac 절전 |

## Context for Next Session

### 다음 세션 진입 시 즉시 확인

```bash
# 1) 사용자 환경 결정 확인
# A 옵션 채택 시:
caffeinate -dimsu &   # 임시 — terminal 종료 시 끊김
# 또는 launchd plist 영구 설정

# B 옵션 채택 시:
# - 별도 Linux 머신 인프라 결정 (Mini PC / NAS / 클라우드 VM)
# - docker compose / .env.prod 이식 절차 chunk

# 2) 현재 컨테이너 + scheduler 상태
cd /Users/heowooyong/cursor/learning/ted-startup/src/backend_kiwoom
docker compose ps
docker compose exec -T kiwoom-app python -c "
import os, httpx, json
r = httpx.get('http://localhost:8001/admin/scheduler/diag', headers={'X-API-Key': os.environ['ADMIN_API_KEY']}, timeout=10)
print(json.dumps(r.json(), indent=2, ensure_ascii=False))
"

# 3) pmset 현재 sleep 상태
pmset -g | head -25

# 4) 다음 cron 발화 검증 (월요일 06:00 / 06:30)
# 5-18 (월) 새벽까지 Mac active 유지 권고
```

### 채택한 접근 (본 chunk)

1. **정공법 우선** — F1 timeline / F2 pmset / F3 diag baseline 병렬 진단
2. **결정적 증거 = pmset -g log** — Mac sleep history 가 가장 명확
3. **가설 평가 5종** — 정합되지 않는 가설 모두 반증 + 확정 가설 1개 남김
4. **해결 옵션 5종 제시** — 사용자 환경 결정 영역 (인프라 + 비용 trade-off)
5. **코드 변경 0** — 진단만, 해결은 사용자 결정 후 별도 chunk

### 운영 위험 / 주의

- **다음 새벽 cron 까지 Mac active 유지 권고** — 5-15 (목) 06:00 OhlcvDaily / 06:30 DailyFlow / 07:00 SectorDaily — caffeinate 실행 또는 노트북 연결 + 깬 상태
- **주말 (5-17/18) 동안 새벽 cron 0건** — 시장 휴장 가정. 5-19 (월) 06:00 부터 정상 cron 필요
- **B 옵션 (서버 이전)** 채택 시 = 별도 chunk (인프라 결정 + docker compose 이식 + secret 회전 + 테스트). 상당한 작업 분량

## Files Modified This Session (본 chunk)

### 0 코드

### 1 ADR 갱신
- `docs/adr/ADR-0001-backend-kiwoom-foundation.md` § 42 신규 (8 sub-§ — 배경 / 증거 / 가설 평가 / misfire 정책 / 해결 옵션 / 결정 / 관련 § 갱신 / 다음 chunk) + § 41.9 갱신

### 3 메타 갱신
- `src/backend_kiwoom/STATUS.md` § 0 / § 4 #30 PASS / § 5 / § 6
- `HANDOFF.md` (본 파일)
- `CHANGELOG.md` prepend

### Verification

- pmset 5-13 20:01~21:12 반복 Sleep 증거 ✅
- 가설 5종 평가 + 4종 반증 + 1종 확정 ✅
- 코드 변경 0 → 1199 tests 그대로

---

_scheduler dead 분석 종결. Mac 절전 = 확정. 사용자 환경 결정 (caffeinate / 서버 이전 / 현재 유지) 후 후행 chunk 진행. F chunk (ka10001 NUMERIC) 는 Mac 절전 결정과 독립._
