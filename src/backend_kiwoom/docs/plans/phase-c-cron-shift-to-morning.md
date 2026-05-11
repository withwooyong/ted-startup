# phase-c-cron-shift-to-morning — cron 시간을 NXT 마감 후 새벽으로 이동

## 0. 메타

| 항목 | 값 |
|------|-----|
| 분류 | 운영 안전 fix — scheduler cron 시간 변경 + base_date 결정 로직 명시 |
| 범위 | OhlcvDaily (18:30 → 다음 영업일 06:00) + DailyFlow (19:00 → 06:00) + Weekly (fri 19:30 → sat 06:00). master/fundamental/sector/monthly/yearly 무변 |
| 출처 | 사용자 발견 (2026-05-11) — "20시에 NXT 거래가 종료되는데 그 시간 이후로 연동해야". DB 검증 5-11 NXT 74 rows (정상 630 의 12%) 가 정황 증거 |
| 선행 chunk | `7f6beb5` (영숫자 백필 / Phase C 데이터 측면 종결) |
| 우선순위 | **P0** — scheduler 활성 직전 선행 fix. 본 chunk 머지 전 scheduler 활성하면 NXT 미완성 데이터 누적 |
| 분량 추정 | 코드 4 파일 (scheduler 3 cron + 3 batch_job + helper 신규) + 테스트 갱신/신규 + ADR § 35 + 4 문서 |
| 진행 모드 | plan doc → 사용자 승인 → 코드 변경 + 테스트 → ADR/문서 → 단일 commit |

## 1. 현황 / 동기

### 1.1 NXT 정규 거래시간

- **17:00 ~ 20:00 KST** (정규 야간 시장)
- 마감 후 키움 NXT 종가 정산 batch — 사용자 실측 (5-11 21:00 백필 시 74 rows 만 적재) 로 21:00 도 일부만 정산 완료 정황. 안전 마진 = 다음 영업일 새벽

### 1.2 현재 cron 의 NXT 충돌

| Scheduler | 현 cron (KST) | NXT 거래 시점 (17~20시) 대비 | 결함 |
|-----------|--------------|---------------------------|------|
| OhlcvDaily | **mon-fri 18:30** | 거래 시작 후 1.5h 진행 중 | NXT exchange 호출 시 미완성 OHLCV |
| DailyFlow | **mon-fri 19:00** | 진행 중 2h | 동일 |
| Weekly | **fri 19:30** | 진행 중 2.5h | 동일 |
| StockMaster | mon-fri 17:30 | NXT 시작 30분 후 (lookup endpoint NXT 무관) | ✅ 안전 — 변경 없음 |
| StockFundamental | mon-fri 18:00 | 거래 진행 중 (lookup endpoint NXT 무관) | ✅ 안전 — 변경 없음 |
| Sector | sun 03:00 | 거래 없음 | ✅ 안전 |
| Monthly | 매월 1일 03:00 | 거래 없음 | ✅ 안전 |
| Yearly | 매년 1월 5일 03:00 | 거래 없음 | ✅ 안전 |

### 1.3 정황 증거 (DB 실측, 2026-05-11)

| trading_date | NXT rows | 비고 |
|--------------|----------|------|
| 2026-05-11 (월) | **74** | 백필 21:00 실행 — NXT 정산 일부만 |
| 2026-05-08 (금) | 630 | 정상 |
| 2026-05-07 (목) | 630 | 정상 |
| 2026-04-13 ~ 2026-05-08 | 630 균일 | 정상 |

→ 5-11 만 비정상 (12%). 5-11 백필 시각 (21:00) 이 NXT 마감 직후 1시간 — **키움 NXT EOD 정산 batch 완료 전**. 마진 부족.

### 1.4 base_date default 문제 (코드 변경 면 확장 동기)

`OhlcvDailyUseCase.execute()` default `base_date = date.today()` (line 142). 현재 18:30 cron 시 `today = 화요일`, 화요일 종가 fetch 정상. **06:00 으로 옮기면** 화요일 06:00 → today = 화요일 → 화요일 데이터 fetch 시도 → **장 시작 전이라 빈 응답**.

해결: cron 시점 (다음 영업일 06:00) 의 의도 = "전 영업일 데이터 적재". `fire_*_job` 함수에서 `base_date=previous_kst_business_day(today)` 명시 전달.

## 2. 범위 외 (Out of Scope)

- master/fundamental/sector/monthly/yearly cron 시간 변경 — § 1.2 ✅ 안전 분류
- KRX 정규 종가 시점 (15:30) 또는 시간외 종가 (16:00~18:00 단일가) 분석 — 본 chunk 는 NXT 종료 (20:00) + 정산 마진 결정만
- 한국 공휴일 처리 — cron 자체가 mon-fri 발화. 공휴일 (mon-fri 안의 공휴일) 시 빈 응답 → success 0, UPSERT idempotent → 운영 영향 0. 별도 chunk
- KRX/NXT 분리 cron — UseCase 안에서 두 exchange 직렬 처리. 분리 시 코드 면 추가 — 본 chunk 안 함
- 5-11 NXT 74 rows 의 운영 보완 — 본 chunk 머지와 별개. § 8 사용자 실행 명령
- scheduler_enabled 활성 — 본 chunk 머지 후 별도 chunk (STATUS § 5 #1)
- 5-11 KRX 4373 vs NXT 적재 differential 정상화 — 본 chunk 머지 후 자동 cron 또는 수동 backfill

## 3. 변경 면 매핑

### 3.1 scheduler.py — 3 cron 시간 변경

| Line | Scheduler | Before | After |
|------|-----------|--------|-------|
| 387~391 | OhlcvDailyScheduler | `day_of_week="mon-fri", hour=18, minute=30` | `day_of_week="mon-fri", hour=6, minute=0` |
| 471~475 | DailyFlowScheduler | `day_of_week="mon-fri", hour=19, minute=0` | `day_of_week="mon-fri", hour=6, minute=30` (OHLCV 30분 후 — fundamental→ohlcv→flow 의존성 유지) |
| 554~558 | WeeklyOhlcvScheduler | `day_of_week="fri", hour=19, minute=30` | `day_of_week="sat", hour=7, minute=0` (daily/flow 종료 후) |

> DailyFlow 가 OHLCV 의 30분 후 유지 (ADR § 18 결정 — ohlcv 적재 완료 후 수급 적재 시점에 stock master/OHLCV 모두 최신화). Weekly 는 sat 07:00 으로 1시간 stagger.

scheduler class docstring 갱신 (cron 시간 명시 문구 3 곳).

### 3.2 base_date 명시 전달 — 3 batch_job 파일

| 파일 | Before | After |
|------|--------|-------|
| `app/batch/ohlcv_daily_job.py:fire_ohlcv_daily_sync` | `await use_case.execute()` | `await use_case.execute(base_date=previous_kst_business_day(date.today()))` |
| `app/batch/daily_flow_job.py:fire_daily_flow_sync` | 동일 | 동일 |
| `app/batch/weekly_ohlcv_job.py:fire_weekly_ohlcv_sync` | 동일 | 동일 (Weekly base_date = sat 발화 시 직전 fri) |

### 3.3 helper 신규 — `previous_kst_business_day`

신규 파일 `app/utils/business_day.py` (또는 기존 utils 모듈):

```python
from datetime import date, timedelta

def previous_kst_business_day(today: date) -> date:
    """직전 KST 영업일 (mon-fri) 반환.

    today 의 요일에 따라:
    - Monday → today - 3d (last Friday)
    - Tue~Sat → today - 1d
    - Sunday → today - 2d (last Friday)

    공휴일 (mon-fri 안의 공휴일) 무시 — 키움 API 빈 응답 자연 처리.
    sentinel 빈 row fix (72dbe69) 가 처리.
    """
    weekday = today.weekday()  # Mon=0, Sun=6
    if weekday == 0:  # Monday
        return today - timedelta(days=3)
    if weekday == 6:  # Sunday — 사실상 호출 안 됨 (cron mon-fri/sat)
        return today - timedelta(days=2)
    return today - timedelta(days=1)
```

> **Saturday (Weekly cron) 처리**: weekday=5 → today - 1 = Friday. 정상.

### 3.4 테스트 변경

| 파일 | 변경 |
|------|------|
| 신규 `tests/test_business_day.py` (또는 동등) | `previous_kst_business_day` 의 7요일 경계 단언 7건 (Mon~Sun input → 예상 output) |
| `tests/test_scheduler.py` (또는 동등) | OhlcvDaily/DailyFlow/Weekly 의 cron 시간 단언 갱신 — 6:0 / 6:30 / sat 7:0 |
| `tests/test_ohlcv_daily_job.py` (또는 동등) | `fire_ohlcv_daily_sync` 호출 시 `execute(base_date=...)` 가 mock `previous_kst_business_day` 결과로 전달되는지 단언 |
| `tests/test_daily_flow_job.py` | 동일 |
| `tests/test_weekly_ohlcv_job.py` | 동일 |

예상 신규 cases 8~12 — 1046 → ~1055.

## 4. 적대적 사전 self-check (H-1 ~ H-9)

| # | 위험 | 완화 |
|---|------|------|
| **H-1** | NXT 정산 마진 20:00 → 06:00 (10시간) 가 과도 / 부족 | 사용자 실측 5-11 21:00 = 74 rows 만 적재 (12%). 10시간 마진 = 매우 안전. 부족하면 06:00 → 08:00 추후 조정 |
| **H-2** | `previous_kst_business_day` 가 공휴일 무시 — mon 06:00 cron 시 base_date=fri 이 공휴일이면? | 키움 API 빈 응답 → success 0 / UPSERT idempotent → 운영 영향 0. `72dbe69` sentinel fix 가 처리. 공휴일 추적은 별도 chunk |
| **H-3** | cron 시간 변경으로 daily/flow/weekly 의 의존성 (master→fundamental→ohlcv→flow) 깨짐 | master/fundamental 은 그대로 17:30/18:00 (전일 영업일 시점). daily/flow/weekly 는 다음 영업일 06:00/06:30/07:00 — master/fundamental 의 다음날 새벽에 실행. **의존성: 전일 17:30 master sync → 다음날 06:00 ohlcv** — 다음날 새벽 시점에 master 가 이미 최신 (전일 17:30 갱신) ✅ |
| **H-4** | `base_date=previous_kst_business_day(today)` 가 chart endpoint 가 안 받는 일자? | ka10081 의 `base_dt` 인자 — 6자리 YYYYMMDD. 어제 일자는 정상 수용. CLI backfill `--start-date 2026-05-11` 도 같은 인자 → 5-11 백필 SUCCESS 가 검증 |
| **H-5** | UseCase default `today()` 변경 위험 | **변경 안 함** — UseCase default 그대로. `fire_*_job` 에서만 명시 전달. router manual sync 의 의도 (오늘 데이터 fetch) 와 분리 유지 |
| **H-6** | router manual sync 호출자가 cron 변경 인지 후 base_date 별도 전달 필요? | router 의 `/sync` endpoint 는 사용자 결정 — manual sync 의 default base_date 도 today 그대로. cron 만 yesterday 명시. 분리 의도 명확 |
| **H-7** | weekly sat 07:00 — 토요일 발화 시 sentinel 빈 row 또는 키움 API maintenance 시간 | 키움 API maintenance 는 일요일 새벽 (sun 02:00~05:00 추정). sat 07:00 안전. 단 키움 docs 재확인 권장 (별도 ADR 가능) |
| **H-8** | 5-11 NXT 74 rows 보완 - 본 chunk 머지 전/후 어디 | 본 chunk 와 별개. § 8 명시. 사용자 다음날 (5-12) 새벽 수동 실행 |
| **H-9** | cron 시간 변경 첫 시행일 (다음 영업일) base_date mismatch | 첫 mon 06:00 cron 시 base_date = last Friday (5-15 cron 시 5-12 fri base_date). 단 5-15 시점에 5-12 데이터 이미 적재됨 (cron 자연 또는 백필) → UPSERT idempotent. 단 5-15 cron 이 5-14 thu base_date 가 정확 — 단순 today-1 이 더 정직? **재검토** — § 5.1 |

## 5. base_date helper 재검토 (H-9 의존)

### 5.1 두 가지 해석

| 해석 | base_date 결정 |
|------|---------------|
| **A. previous_kst_business_day** | mon → last fri / tue → mon / wed → tue / thu → wed / fri → thu / sat → fri |
| B. `today - 1d` 단순 | mon → sun (공휴일/주말) / tue → mon / ... / sat → fri |

해석 A 는 mon 06:00 cron 시 base_date=fri (3일 전). 해석 B 는 base_date=sun (거래 없음).

해석 A 가 더 정직 (의도 명확 — 직전 영업일). 해석 B 는 단순하나 mon 06:00 시 빈 응답 → success 0. **권장: A**.

### 5.2 weekday=5 (Saturday) 처리

해석 A 에서 Saturday → 어제 (Friday) — 정상. Weekly cron 이 sat 07:00 발화 시 base_date = friday → 주봉 마지막 일자 fri ✅.

## 6. DoD

### 6.1 코드 (ruff/mypy strict PASS)

- [ ] `app/scheduler.py` — 3 cron 시간 변경 (OhlcvDaily/DailyFlow/Weekly) + class docstring 갱신
- [ ] `app/batch/ohlcv_daily_job.py` — `execute(base_date=previous_kst_business_day(date.today()))`
- [ ] `app/batch/daily_flow_job.py` — 동일
- [ ] `app/batch/weekly_ohlcv_job.py` — 동일
- [ ] `app/utils/business_day.py` (또는 동등) 신규 — `previous_kst_business_day`
- [ ] (선택) `app/batch/__init__.py` 또는 helper export

### 6.2 테스트 (목표: 1046 → ~1055 / coverage 유지 ≥ 90%)

- [ ] `previous_kst_business_day` 7 요일 경계 단언 7건
- [ ] scheduler 3 cron 시간 단언 갱신 (test 가 cron hour/minute 검증한다면)
- [ ] 3 fire_*_job 의 `execute()` 호출 시 base_date 전달 mock 단언
- [ ] 기존 1046 회귀 0 — cron 시간 가정 단언 (있다면) 갱신

### 6.3 Verification

- [ ] mypy --strict 0 errors
- [ ] ruff All passed
- [ ] pytest 전체 PASS / coverage 유지

### 6.4 리뷰

- [ ] 1R 리뷰 — sub-agent 1회 라운드 (NXT 도메인 + base_date 명시 의도 검증)
- [ ] Verification Loop — cron 시간 일관성 + 의존성 (master→fundamental→ohlcv→flow) 정직성

### 6.5 문서

- [ ] ADR § 35 신규 — NXT 거래시간 충돌 + cron shift 결정 + DB 정황 증거 + base_date 의도 명확화
- [ ] STATUS § 4 신규 항목 #21 (cron NXT 충돌) → 해소 표시. § 0 / § 5 #1 (scheduler 활성) 의 선행 fix 명시
- [ ] HANDOFF 전체 갱신
- [ ] CHANGELOG prepend — `fix(kiwoom): cron 시간 NXT 마감 후 새벽으로 이동 (ADR § 35)`

## 7. 5-11 NXT 74 rows 보완 (본 chunk 와 별개)

사용자 수동 실행 — 본 chunk 머지 후 또는 별개 시점:

```bash
cd src/backend_kiwoom
uv run python scripts/backfill_ohlcv.py \
  --period daily \
  --start-date 2026-05-11 \
  --end-date 2026-05-11 \
  --alias prod
```

> `--resume` 미사용 — 영업일 calendar 비교가 KRX 만 본다 (`d43d956` 의 _RESUME_TABLE_BY_PERIOD 매핑). 5-11 KRX 4373 적재 완료라 resume 시 모두 skip 되어 NXT 보완 안 됨. --resume 빼고 전체 4373 종목 호출. KRX 는 UPSERT idempotent / NXT 는 미적재 종목 적재.

실행 시간 추정: 4373 × 2 (KRX+NXT) × 1 page × 0.3s ≈ ~44분. 단일 일자 백필.

## 8. 다음 chunk (본 chunk 종결 후)

1. **5-11 NXT 보완 백필 실행** (사용자 수동, § 7) — 본 chunk 머지 후 또는 별개. 5-11 trading_date NXT 74 → 정상치
2. **scheduler_enabled 활성 + 1주 모니터** (STATUS § 5 #1) — env 변경 + 1주
3. Phase D 진입 — ka10080 분봉 / ka20006 업종일봉

---

_사용자 발견 (2026-05-11). NXT 정규 거래시간 미인지 — Phase C 운영 안전성 결함. scheduler 활성 직전 선행 fix._
