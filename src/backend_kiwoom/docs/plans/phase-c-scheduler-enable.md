# phase-c-scheduler-enable — APScheduler 본격 활성 + 1주 모니터

## 0. 메타

| 항목 | 값 |
|------|-----|
| 분류 | 운영 활성 — env 변경 9건. 코드 변경 0 (단 .env.prod 는 .gitignore 라 commit 외부) |
| 범위 | `KIWOOM_SCHEDULER_ENABLED=true` + 8 cron alias 모두 `prod` 매핑. lifespan 가드 fail-fast 통과 |
| 출처 | STATUS § 5 #1 / `phase-c-cron-shift-to-morning` § 8 #2 / Phase C 의 마지막 chunk |
| 선행 chunk | `8c14aa3` (cron NXT 안전 + base_date 명시 전달) |
| 우선순위 | **P1** — Phase C 운영 진입의 마지막 마무리 |
| 분량 추정 | .env.prod 9 line + plan doc + ADR § 36 + 3 문서 |
| 진행 모드 | sub-chunk 분리 — (1) 본 chunk: 활성 + 1주 모니터링 가이드 + ADR § 36 (결과 빈칸) / (2) **별도 chunk** (1주 후): § 36 측정 결과 채움 |

## 1. 현황 / 동기

### 1.1 Phase C 전체 완료 상태

- 8 cron scheduler 모두 코드 완성 (§ 17/§ 18/§ 23/§ 29/§ 35)
- cron 시간 NXT 마감 후 안전 (§ 35)
- base_date `previous_kst_business_day(today)` 명시 전달 (§ 35)
- OHLCV (KRX 4078 + NXT 626 + 영숫자 295) historical 3년 적재 완성 (§ 26.5/§ 34)
- daily_flow (KRX 3922 + NXT 626) historical 3년 적재 완성 (§ 27)
- `scheduler_enabled` default False 였음 — **본 chunk 가 활성 첫 시점**

### 1.2 lifespan fail-fast 가드

`app/main.py:126~144` — `scheduler_enabled=True` 일 때 8 alias (sector / stock_master / fundamental / ohlcv_daily / daily_flow / weekly_ohlcv / monthly_ohlcv / yearly_ohlcv) 모두 비어있지 않은지 검증. 한 건이라도 빈 값이면 `RuntimeError` raise → 앱 startup 실패.

본 chunk 의 9 env 추가는 이 가드 통과를 목적으로 함.

### 1.3 DB 등록 alias 현황

```sql
SELECT alias, env FROM kiwoom.kiwoom_credential ORDER BY alias;
```
| alias | env |
|-------|-----|
| prod | prod |

→ 모든 8 cron alias 를 `prod` 로 매핑.

## 2. 범위 외 (Out of Scope)

- **1주 후 측정 결과** — 별도 chunk (사용자 결정 2026-05-12). 본 chunk 는 placeholder 만
- 5-11 NXT 74 rows 보완 — 사용자 수동 (ADR § 35.8)
- KOSCOM cross-check 수동 — 미래 chunk
- 공휴일 calendar 도입 — 별도 chunk 가능
- 알람 임계값 조정 — 1주 모니터 결과에 의존
- Phase D~G 진입 — 본 chunk 후

## 3. 변경 면

### 3.1 .env.prod (commit 외부 — .gitignore)

| Env | Value | 비고 |
|-----|-------|------|
| `KIWOOM_SCHEDULER_ENABLED` | `true` | 마스터 스위치 |
| `KIWOOM_SCHEDULER_SECTOR_SYNC_ALIAS` | `prod` | A3-γ sector cron |
| `KIWOOM_SCHEDULER_STOCK_SYNC_ALIAS` | `prod` | B-α stock master cron |
| `KIWOOM_SCHEDULER_FUNDAMENTAL_SYNC_ALIAS` | `prod` | B-γ-2 fundamental cron |
| `KIWOOM_SCHEDULER_OHLCV_DAILY_SYNC_ALIAS` | `prod` | C-1β ohlcv daily cron |
| `KIWOOM_SCHEDULER_DAILY_FLOW_SYNC_ALIAS` | `prod` | C-2β daily flow cron |
| `KIWOOM_SCHEDULER_WEEKLY_OHLCV_SYNC_ALIAS` | `prod` | C-3β weekly cron |
| `KIWOOM_SCHEDULER_MONTHLY_OHLCV_SYNC_ALIAS` | `prod` | C-3β monthly cron |
| `KIWOOM_SCHEDULER_YEARLY_OHLCV_SYNC_ALIAS` | `prod` | C-4 yearly cron |

### 3.2 plan doc / ADR / STATUS / HANDOFF / CHANGELOG (commit 대상)

- 신규 `src/backend_kiwoom/docs/plans/phase-c-scheduler-enable.md` (본 파일)
- 신규 `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 36
- 갱신 `src/backend_kiwoom/STATUS.md` (§ 0 / § 4 #13 / § 5 / § 6)
- 갱신 `HANDOFF.md` (전체)
- 갱신 `CHANGELOG.md` (prepend)

## 4. 첫 발화 시점 (KST)

본 chunk 머지 + 앱 재시작 후 다음 영업일 기준:

| Scheduler | cron | 첫 발화 (앱 재시작 이후 가장 가까운) |
|-----------|------|--------------------------------------|
| StockMaster | mon-fri 17:30 | 2026-05-12 (오늘 화) 17:30 — 앱 재시작 시점 의존 |
| StockFundamental | mon-fri 18:00 | 동일 18:00 |
| OhlcvDaily | mon-fri 06:00 | 2026-05-13 (수) 06:00 |
| DailyFlow | mon-fri 06:30 | 2026-05-13 (수) 06:30 |
| Weekly | sat 07:00 | 2026-05-16 (토) 07:00 |
| Sector | sun 03:00 | 2026-05-17 (일) 03:00 |
| Monthly | 매월 1일 03:00 | 2026-06-01 (월) 03:00 |
| Yearly | 매년 1월 5일 03:00 | 2027-01-05 (화) 03:00 |

> **앱 재시작 시점이 17:30 / 18:00 이전이면 오늘 발화 — 이후면 내일 17:30 / 18:00**. base_date 는 `previous_kst_business_day(today)` 라 5-12 cron 시 5-11 mon 데이터 fetch.

## 5. 적대적 사전 self-check (H-1 ~ H-6)

| # | 위험 | 완화 |
|---|------|------|
| **H-1** | 첫 발화에서 KiwoomBusinessError 누적 | router/UseCase 의 KiwoomError 5종 핸들러 (§ 22 R1 / § 30 R2 E-1) + sentinel fix (72dbe69). 실패율 > 10% logger.error 알람 |
| **H-2** | NXT 정산 마진 부족 (5-11 NXT 74 rows 같은 anomaly) | cron 06:00/06:30 → NXT 마감 (20:00) + 10시간 마진 → 매우 안전. 1주 후 측정 §36.5 |
| **H-3** | 앱 재시작 직후 master/fundamental 17:30/18:00 발화 시 운영 시점에 일시 부하 | max_instances=1 + coalesce=True (각 scheduler 의 add_job) — 동시 실행 차단 |
| **H-4** | 공휴일 mon-fri 발화 시 빈 응답 누적 | sentinel break (`if not <list>: break`) — UPSERT idempotent. logger.warning 으로 success 0 기록 정상 |
| **H-5** | scheduler 실패 시 cron 다음 tick 도 끊김 | fire_*_job 의 `except Exception` swallow — 다음 tick 정상 보장 |
| **H-6** | env 9건 중 일부 누락 시 lifespan fail-fast → 앱 startup 실패 | 본 plan doc § 3.1 의 9 env 모두 추가 검증. 누락 시 RuntimeError 로 명시 감지 |

## 6. 모니터링 가이드 (1주)

### 6.1 로그 위치

- 콘솔 stdout/stderr — uvicorn / systemd journal
- 각 fire_*_job 의 logger:
  - `app.batch.ohlcv_daily_job` — `"ohlcv daily sync"` 키워드
  - `app.batch.daily_flow_job` — `"daily flow sync"`
  - `app.batch.weekly_ohlcv_job` — `"ohlcv weekly sync"`
  - 동일 패턴 — sector / stock_master / fundamental / monthly / yearly
- logger.info: 정상 완료 (`total=N krx=N nxt=N`)
- logger.warning: failed > 0 + ratio <= 10% (`부분 실패`)
- logger.error: ratio > 10% (`실패율 과다 — sample [...]`)
- logger.exception: cron 콜백 자체 예외 (`콜백 예외`)

### 6.2 핵심 관찰 포인트

| # | 항목 | 기준 |
|---|------|------|
| 1 | 일간 cron elapsed | OHLCV daily ~35분 / DailyFlow ~10시간 추정 (full backfill 9h 53m 기준) |
| 2 | NXT 적재 row 수 (5-13 mon 첫 발화) | 정상 영업일 KRX ~4373 / NXT ~630 |
| 3 | failed 건수 | > 0 시 errors 상위 10 분석 |
| 4 | 알람 (logger.error) 발생 | 매 영업일 0건 기대. 1건이라도 발생 시 즉시 분석 |
| 5 | KRX rate limit (429) 누적 | tenacity 재시도 적정 — 키움 server 5xx 외 client 429 발생 여부 |

### 6.3 1주 후 측정 SQL (§ 36.5 가 채울 placeholder)

```sql
-- 일간 cron 첫 발화 (5-13 mon) 이후 7 영업일 KRX vs NXT 적재 row 분포
SELECT trading_date, exchange, count(*) AS n
FROM (
  SELECT trading_date, 'KRX' AS exchange FROM kiwoom.stock_price_krx
  UNION ALL
  SELECT trading_date, 'NXT' FROM kiwoom.stock_price_nxt
) p
WHERE trading_date >= DATE '2026-05-13'
GROUP BY 1, 2 ORDER BY 1, 2;

-- 운영 cron elapsed 추정 (logger 의 ohlcv daily sync 시작/완료 timestamp pair)
-- 단 elapsed 직접 측정 unavailable → logger.info 시점만 기록. 시간 차 계산은 grep + awk
```

## 7. DoD

### 7.1 본 chunk (활성 + 가이드)

- [ ] `.env.prod` 9 env 추가 — KIWOOM_SCHEDULER_ENABLED + 8 alias=prod
- [ ] plan doc `phase-c-scheduler-enable.md` 신규
- [ ] ADR § 36 신규 (메타 + 환경 + 모니터링 가이드 + 측정 SQL placeholder + 1주 후 별도 chunk 명시)
- [ ] STATUS § 0 / § 4 #13 / § 5 #1 → § 6 / § 6 chunk 누적
- [ ] HANDOFF 전체 갱신
- [ ] CHANGELOG prepend
- [ ] 단일 commit (.env.prod 제외 — .gitignore)
- [ ] 사용자 앱 재시작 안내

### 7.2 1주 후 별도 chunk (사용자 요청 시)

- [ ] § 6.2 5 관찰 포인트 정량화
- [ ] § 6.3 SQL 실행 결과 ADR § 36.5 채움
- [ ] anomaly 분석 (failed / 알람 / NXT 적재 정상)
- [ ] STATUS § 4 #13 해소
- [ ] 다음 chunk = Phase D 진입

## 8. 다음 chunk (본 chunk 종결 후)

1. **(별도 chunk) 1주 후 측정 결과 정리** (2026-05-19 mon 이후)
2. **5-11 NXT 74 rows 보완** — 사용자 수동 (ADR § 35.8)
3. **Phase D 진입** — ka10080 분봉 / ka20006 업종일봉 (대용량 파티션 결정 선행)
4. Phase E/F/G — 공매도/대차/순위/투자자별 wave
5. KOSCOM cross-check 수동

---

_Phase C 의 마지막 chunk — 운영 본격 진입. 1주 후 측정 결과는 별도 chunk._
