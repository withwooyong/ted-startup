# Session Handoff

> Last updated: 2026-05-12 (KST, /handoff) — cron 시간 NXT 마감 후 새벽 이동 + base_date 명시 전달.
> Branch: `master`
> Latest commit: `<this commit>` (cron shift / 1059 tests / ADR § 35)
> 미푸시 commit: **2 건** (`7f6beb5` 영숫자 백필 + this commit — 사용자 명시 요청 시 push)

## Current Status

scheduler 활성 직전 P0 fix 완료 — NXT 거래시간 (17:00~20:00) 충돌하던 cron 3건이 NXT 마감 + 정산 마진 후로 이동. base_date default `today()` 의 06:00 cron 충돌도 `fire_*_job` 명시 전달로 해소. 사용자 발견 (5-11) → 같은 세션에서 plan doc → 코드 변경 → 테스트 → ADR § 35.

Phase C 운영 안전성 100% 확보. 다음 chunk = **scheduler_enabled 활성 + 1주 모니터** (Phase C 의 마지막 chunk).

## Completed This Session

| # | Task | 결과 | Files |
|---|------|------|-------|
| 1 | 영숫자 백필 chunk (5-11) | 0 failure / 47m 33s / 75K rows / ADR § 34 | 5 / commit `7f6beb5` |
| 2 | scheduler cron 시간 사용자 확인 | 8 cron 매핑 표 출력 + NXT 거래시간 충돌 발견 | 0 |
| 3 | DB 검증 — 5-11 NXT 74 rows | 4~5월 영업일 모두 630 균일 / 5-11 만 12% (anomaly) | 0 |
| 4 | plan doc — `phase-c-cron-shift-to-morning.md` | 메타/§ 1.1 NXT 거래시간/§ 1.2 cron 매핑/§ 1.3 DB 정황/§ 1.4 base_date 동기/H-1~9/DoD | 1 신규 |
| 5 | 코드 변경 — helper + 3 batch_job + scheduler | base_date 명시 전달 / cron 시간 3 곳 / docstring 갱신 | 5 |
| 6 | 테스트 신규/갱신 | 1046 → 1059 (+13) | 4 |
| 7 | ADR § 35 + STATUS + HANDOFF + CHANGELOG | 4 문서 갱신 + plan doc 1 | 5 |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| **1** | **scheduler_enabled 활성 + 1주 모니터** | **다음 chunk 1순위** | env 변경 1건. cron 06:00/06:30/sat 07:00 첫 발화 검증 + § 34 + § 35 정량화 |
| 2 | 5-11 NXT 74 rows 보완 | 사용자 수동 | `backfill_ohlcv.py --start-date 2026-05-11 --end-date 2026-05-11 --alias prod` (--resume 미사용) |
| 3 | Phase D — ka10080 분봉 / ka20006 업종일봉 | 대기 | 대용량 파티션 결정 선행 |
| 4 | Phase E / F / G | 대기 | 신규 endpoint wave |
| 5 | KOSCOM cross-check 수동 | 대기 | 가설 B 최종 확정 |

## Key Decisions Made

1. **cron 시간 06:00/06:30/sat 07:00 채택** — NXT 마감 (20:00) + 정산 마진 (5-11 NXT 74 rows 검증) → 다음 영업일 새벽이 안전. 22:00 / 자정 옵션 대비 안전 마진 최대
2. **master/fundamental cron 그대로** — lookup endpoint 라 NXT 무관. fundamental 18:00 은 KRX 종가 (15:30) 확정 후 + NXT 거래와 별개
3. **Weekly sat 07:00** — daily/flow 종료 후 1시간 stagger. mon 06:00 옵션 (2.5일 지연) 보다 토요일 새벽 채택
4. **base_date 명시 전달 — UseCase default 유지** — `fire_*_job` 만 `previous_kst_business_day(date.today())` 전달. router manual sync 의도 (오늘 데이터) 와 cron 의도 (어제 데이터) 분리. 5장 변경 (1 helper + 3 batch_job + 3 scheduler docstring)
5. **공휴일 추적 무시** — `previous_kst_business_day` 가 캘린더 외부 의존성 0. mon-fri 안의 공휴일은 키움 API 빈 응답 → success 0 / UPSERT idempotent / sentinel fix `72dbe69` 처리. 별도 chunk 가능
6. **5-11 NXT 보완은 별개 chunk** — 본 chunk 머지와 별개. 사용자 수동 명령 plan doc § 7 / ADR § 35.8 명시
7. **운영 영향 인지** — daily/flow 데이터 가용 시점이 다음 영업일 오전 06:00/06:30 (이전 18:30/19:00 대비 ~12시간 지연). 백테스트/분석 사용자는 다음날 아침 분석. 트레이딩 의사결정 (장중) 은 별도 endpoint (실시간) 필요 — 별개 결정

## Known Issues

| # | 항목 | 출처 | 결정 |
|---|------|------|------|
| **20** | NXT 우선주 sentinel 빈 row 1개 detection | ADR § 32.3 + § 33.6 | LOW — 운영 영향 0 (`nxt_enable=False` 자연 차단) |
| **13** | 일간 cron 실측 (운영 cron elapsed) | dry-run § 20.4 | scheduler 활성화 chunk — cron 06:00/06:30/sat 07:00 첫 발화 측정 |
| **21** | 5-11 NXT 74 rows 보완 | ADR § 35.8 | 사용자 수동 명령 |

## Context for Next Session

### 사용자의 의도

세션 도중 사용자가 "20시에 NXT 거래가 종료되는데 그 시간 이후로 연동해야" 발견. 영숫자 백필 (chunk 7f6beb5) 머지 직후 scheduler 활성으로 진입하기 직전이라 운영 안전성 결함이 매우 timely. 4 분기 옵션 중 추천 A (다음 영업일 새벽 06:00 일괄) 채택.

### 채택한 접근

1. **plan doc 패턴 유지** — `phase-c-chart-alphanumeric-guard` / `phase-c-alphanumeric-backfill` 와 같은 plan doc + 사용자 승인 + 코드 변경 순서
2. **base_date helper 분리** — `app/batch/business_day.py` 신규. UseCase default 변경 X (router 의도 분리)
3. **테스트 신규 + 갱신** — 1046 → 1059 (+13). business_day 단독 단언 10 + 3 scheduler base_date 단언
4. **단일 commit** — 5 코드 (1 helper + 3 batch_job + 1 scheduler) + 4 테스트 + 5 문서

### 사용자 환경 제약

- DB 는 docker-compose `kiwoom-db` (포트 5433). DataGrip 직접 접속 / `docker exec -i kiwoom-db psql` 가능
- 자격증명 `.env.prod` (KIWOOM_API_KEY/KIWOOM_API_SECRET + legacy alias fallback)

### 다음 세션 진입 시점 결정 필요

| 옵션 | 설명 | 비용 |
|------|------|------|
| **A. scheduler_enabled 활성** | env 변경 1건 + 1주 모니터. cron 06:00/06:30/sat 07:00 첫 발화 검증. 측정 #13/§ 34.6/§ 35 정량화 | env + 1주 |
| B. 5-11 NXT 보완 명령 사용자 실행 | `backfill_ohlcv.py --start-date 2026-05-11 ... ` ~44분 | 수동 + 시간 |
| C. Phase D 진입 | ka10080 분봉 / ka20006 업종일봉 | 신규 도메인 + 파티션 |

권장: **A** — scheduler 활성. B 는 cron 첫 발화로 자연 보완 가능 (단 5-12 새벽 cron 이 5-11 base_date 처리할까? 그렇다). C 는 그 다음.

### 운영 위험

- **scheduler 활성 시점 우려**: 첫 영업일 (5-13 화 06:00 가정) cron 발화 — base_date=5-12 mon. 5-12 시점에 5-11 NXT (불완전) 와 별개로 5-12 KRX/NXT 정상 적재. 누적 5-11 NXT 74 rows 는 별도 보완 필요
- **공휴일 첫 발생 시**: `previous_kst_business_day` 가 공휴일을 영업일로 본다 → 빈 응답. sentinel fix 가 처리하나 운영 로그 watch 필요

## Files Modified This Session

### Chunk 1 (`7f6beb5`) — 영숫자 백필 (이미 commit)

5 files (plan doc 신규 + 4 문서 갱신)

### Chunk 2 (`<this commit>`) — cron shift — 13 files

- 신규 (3): `app/batch/business_day.py` / `tests/test_business_day.py` / `src/backend_kiwoom/docs/plans/phase-c-cron-shift-to-morning.md`
- 갱신 코드 (5): `app/scheduler.py` / `app/batch/ohlcv_daily_job.py` / `app/batch/daily_flow_job.py` / `app/batch/weekly_ohlcv_job.py`
- 갱신 테스트 (3): `tests/test_ohlcv_daily_scheduler.py` / `tests/test_daily_flow_scheduler.py` / `tests/test_weekly_monthly_ohlcv_scheduler.py`
- 갱신 문서 (4): `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 35 / `src/backend_kiwoom/STATUS.md` / `HANDOFF.md` / `CHANGELOG.md`

### Verification

- ruff All passed / mypy --strict Success
- pytest **1059 PASS** (+13) / 29.84s

---

_Phase C 운영 안전성 결함 (NXT 거래시간 충돌) 해소. 다음은 scheduler_enabled 활성 — 본 chunk 의 직접 동기._
