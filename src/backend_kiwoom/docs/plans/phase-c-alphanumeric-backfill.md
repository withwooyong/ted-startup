# phase-c-alphanumeric-backfill — 영숫자 (우선주/특수) 종목 OHLCV 3 period 백필

## 0. 메타

| 항목 | 값 |
|------|-----|
| 분류 | 운영 백필 chunk — 코드 변경 0 / DB 데이터만 적재 |
| 범위 | chart 가드 완화 (Chunk 2 / ADR § 33) 후 active 영숫자 종목 (영문 포함 6자리, 약 195~295) 의 daily + weekly + monthly OHLCV 3년 백필 |
| 출처 | STATUS § 5 #1 / `phase-c-chart-alphanumeric-guard.md` § 7 #1 / HANDOFF Option A |
| 선행 chunk | Chunk 2 `ef7d598` (STK_CD_CHART_PATTERN 적용) + HANDOFF.md 갱신 `e765a39` 모두 머지 완료 |
| 우선순위 | P1 — Phase C 종결의 마지막 데이터 적재. 본 chunk 후 운영 cron 활성 / Phase D 진입 가능 |
| 분량 추정 | CLI 실행 (코드 0) + 결과 분석 + ADR § 34 + 3 문서 갱신 (STATUS/HANDOFF/CHANGELOG) |
| 진행 모드 | Stage 1 dry-run → 사용자 확인 → Stage 2 실 백필 (3 period 순차) → Stage 3 결과 분석 |
| Push 정책 | 사용자 명시 동의 받음 (백필 전 push). 단, 확인 결과 origin/master 와 HEAD 동일 (`e765a39`) — push 작업 0건 |

## 1. 현황 / 동기

### 1.1 chart 가드 완화 결과 (Chunk 2 / ADR § 33)

| 항목 | Chunk 2 전 | Chunk 2 후 |
|------|-----------|------------|
| chart endpoint 가드 정규식 | `^[0-9]{6}$` (LOOKUP 차용) | `^[0-9A-Z]{6}$` (CHART) |
| 영숫자 종목 OHLCV 호출 | UseCase 가 skip (로그만) | UseCase keep → 호출 진행 |
| 영숫자 종목 DB 적재 | 0 rows | (본 chunk 전까지) 여전히 0 — Chunk 2 머지 후 cron 미실행 |
| 다음 cron 실행 시 | — | 자연 수집 시작 (그러나 3년 백필은 별도 chunk 가 정직) |

### 1.2 Chunk 1 dry-run 검증 (ADR § 32)

영숫자 6 종목 (`005935`, `00088K`, `00104K`, `001045`, `001065`, `001067`) 운영 호출 결과:
- KRX 6/6 SUCCESS (return_code=0, items 600+ rows / ka10081 + 20+ rows / ka10086)
- NXT 6/6 empty (sentinel 빈 row) → NXT 우선주 미지원 확정

본 chunk 의 백필 호출도 KRX only (NXT skip — `nxt_enable=False` 자연 차단 + sentinel empty fix `72dbe69` 보호).

### 1.3 본 chunk 의 가치

운영 cron 자연 수집을 기다리면:
- daily 는 다음 영업일 cron (`base_date=어제`) 에서 어제 1일치만 가져옴 → 3년치 누적까지 750+ 영업일 소요
- weekly cron (금 19:30) / monthly cron (1일 03:00) 도 동일
- 즉, 3년 historical 데이터는 cron 만으로는 절대 채워지지 않음 — backfill CLI 필수

또한 백테스팅/시그널 분석은 historical 3년이 핵심 — 영숫자 종목 데이터 부재 시 우선주 종목군 (삼성전자우/현대차2우B 등) 분석 불가.

## 2. 범위 외 (Out of Scope)

- chart 가드 / lookup 가드 코드 변경 — Chunk 2 (`ef7d598`) 가 이미 마침
- 영숫자 종목 펀더멘털 (ka10001) 백필 — lookup 계열이라 Chunk 2 범위 외, 본 chunk 도 동일하게 lookup 영숫자 거부 정책 유지
- daily_flow (ka10086) 백필 — 본 chunk 의 OHLCV 3 period 와는 별개 (이미 daily_flow 백필은 9h 53m 측정 완료 / 4078 종목). 영숫자 daily_flow 는 cron 자연 수집 또는 별도 chunk
- NXT 영숫자 백필 — NXT 우선주 미지원 (Chunk 1 dry-run 확정)
- yearly OHLCV (ka10094) — KRX only / 매년 1월 5일 cron / 영숫자 영향 미미 (1년 1 row). 별도 chunk 가능하나 가치 낮음 → 본 chunk 범위 외. cron 자연 수집에 위임
- scheduler_enabled 활성 — 본 chunk 완료 후 별도 chunk
- 영숫자 종목 신규 영업일 (오늘/내일) 데이터 — cron 이 자연 처리

## 3. 진행 단계

### 3.1 Stage 1 — dry-run + 영숫자 카운트 확정 ✅

**결과 (2026-05-11)**:

- 영숫자 active = **295 종목** (plan doc 추정 정확)
- market_code 분포: `0` (KOSPI) 249 / `10` (KOSDAQ) 44 / `50` (KONEX) 1 / `6` 1
- 우선주 `^[0-9]{5}K$` suffix = **20** — 나머지 275 는 ETF/ETN/회사채 액티브 (TIGER/KODEX/PLUS/RISE/HK 등). 본 plan § 1 의 "우선주/특수" 추정은 ETF dominant 로 정정 필요
- total active = **4373** (full backfill `12f0daf` 시점 4078 → +295 = 4373. 295 가 영숫자만큼 신규 마스터 적재 — chart 가드 완화 전엔 chart 호출 skip 됐던 종목들)

dry-run 추정 (rate_limit `0.25s/call`, ±50% margin):

| period | 영업일 calendar | 백필 대상 stocks | exchanges | pages/call | total calls | est. time |
|--------|----------------|------------------|-----------|------------|-------------|-----------|
| daily | 727 (적재 완료) | **1108** (영숫자 295 + 비영숫자 gap 813) | 2 | 2 | 4432 | **18m 28s** |
| weekly | ∅ (첫 적재) | **4373** (전체) | 2 | 1 | 8746 | **36m 26s** |
| monthly | ∅ (첫 적재) | **4373** (전체) | 2 | 1 | 8746 | **36m 26s** |
| **합계** | — | — | — | — | **21,924 calls** | **~91m 20s** |

> **사용자 결정 (2026-05-11)**: scope 가 plan doc § 1.3 의 "영숫자 295" 보다 큰 1108/4373/4373 임을 인지한 후 **옵션 A — dry-run 그대로 3 period 진행** 동의. 부수 효과 — daily gap 813 보완 + weekly/monthly 첫 적재 완성 (scheduler 활성 전 historical 완전). 본 chunk 가 Phase C 의 데이터 측면 마지막 chunk 가 됨.

### 3.2 Stage 2 — 실 백필 3 period 순차 (✅ 완료, 2026-05-11)

| Step | 명령 | total | success_krx | success_nxt | failed | elapsed |
|------|------|-------|-------------|-------------|--------|---------|
| 1 | `backfill_ohlcv.py --period daily --years 3 --alias prod --resume` | 1108 | 1108 | 75 | **0** | 5m 48s |
| 2 | `backfill_ohlcv.py --period weekly --years 3 --alias prod --resume` | 4373 | 4373 | 630 | **0** | 20m 55s |
| 3 | `backfill_ohlcv.py --period monthly --years 3 --alias prod --resume` | 4373 | 4373 | 630 | **0** | 20m 50s |
| **합계** | — | — | — | — | **0** | **47m 33s** (추정 91m 의 52%) |

### 3.3 Stage 3 — 검증 + 분석 (✅ 완료, 2026-05-11)

| 검증 | 결과 |
|------|------|
| DB 적재 row 합계 (영숫자) | daily 58,909 / weekly 12,983 / monthly 3,257 = **75,149 rows** |
| distinct alphanumeric stocks loaded | **295 / 295** (100%, 0-row 종목 0건) |
| NUMERIC(8,4) magnitude max | daily 3049.40 / weekly 3341.27 / monthly 3445.97 (cap 9999.9999 < 35%) |
| NUMERIC 음수 (F7 anomaly) | min 0.0000 — 음수 0건 |
| sentinel 0-row 종목 (F8 SPAC 패턴) | 0건 (영숫자 295 모두 적재) |
| since_date edge case (F6 패턴) | 0건 (success_krx = distinct stocks 일치) |

상세 표 / SQL / 정정 사항은 ADR § 34.3 / 34.4 / 34.5 참조.

### 3.3 Stage 2 안전장치

- 백그라운드 실행 + `Monitor` 로 진행 가시화 (`feedback_progress_visibility.md` 메모리)
- 각 period 종료 시 exit code 확인 — `0` (전체 SUCCESS) / `1` (부분 실패 — errors 상위 10 분석) / `2` (인자 오류) / `3` (시스템 오류)
- 부분 실패 시: 다음 period 진행 전 errors 분석 후 사용자 결정
- 3 period 동안 다른 작업 미진입 (DB 부하 / KRX rate limit 영향)

### 3.4 Stage 3 — 결과 분석 + 문서 갱신 + 커밋

| 작업 | 산출물 |
|------|--------|
| 3 period summary 통합 — total/success_krx/success_nxt/failed/elapsed/rows | ADR § 34 |
| DB 적재 검증 — `SELECT count(*) FROM stock_price_krx WHERE stock_id IN (영숫자 stock ids) GROUP BY period` | ADR § 34 / Verification SQL |
| 컬럼 동일값 / NUMERIC overflow / since_date edge case 등 anomaly 확인 | ADR § 34 |
| STATUS § 0 / § 5 #1 → § 6 이동 / § 4 #19 측정값 확정 (영숫자 +10분 → 실측) | STATUS.md |
| HANDOFF 전체 갱신 | HANDOFF.md |
| CHANGELOG prepend | CHANGELOG.md |
| 커밋 (1건 chunk) | git commit |

## 4. 적대적 사전 self-check (H-1 ~ H-8)

| # | 위험 | 완화 |
|---|------|------|
| **H-1** | Chunk 1 dry-run 의 6 종목 외 다른 영숫자 종목이 KiwoomBusinessError 반환 | router 5 path 의 KiwoomError 5종 핸들러 (R2 E-1) + UseCase 의 ErrorEntry 누적 → exit code 1 + errors 상위 10. 사용자 분석 후 follow-up chunk |
| **H-2** | `--resume` gap detection 이 영숫자 종목이 stock 마스터에 없거나 (synced 안됨) 또는 영업일 calendar 0 인 경우 misbehave | Stage 1 dry-run + DB query 로 영숫자 active 카운트 사전 확정. 영업일 calendar = full backfill 34분 (`12f0daf`) 후 4078 종목 × 750 거래일 union 비어있을 가능성 0 |
| **H-3** | 3 period 순차 실행 중 KRX rate limit 누적 — daily 후 weekly 시 throttle | rate_limit `0.25s` 자연 준수 + 각 period 종료 시 graceful close (`_build_use_case` 의 `finally: kiwoom_client.close()`). period 간 5초 sleep 보장 안 함 → 필요 시 명령 사이 명시 sleep |
| **H-4** | 영업일 calendar 가 KRX 영업일 (휴장일 제외) 와 다름 — gap detection false negative | 영업일 calendar = DB 실제 적재 trading_date union → 휴장일 자연 제외. 본 chunk 의 영숫자 종목은 영업일 ∅ → gap = 전체. 영업일 자체가 잘못 정의될 risk 0 |
| **H-5** | NUMERIC(8,4) magnitude overflow (turnover_rate) | full backfill 측정 max 3,257.80 / cap 33% — 영숫자 종목 추가는 동일 magnitude 추정. SQL 후 검증 (Stage 3) |
| **H-6** | `since_date` 인자 누락 → max_pages 초과 (`KiwoomMaxPagesExceededError`) | CLI 가 `start_date` (resolve_date_range) 를 `since_date` 로 UseCase 에 전파 (`d60a9b3` since_date fix). 자동 PASS |
| **H-7** | 신한제11호스팩 (`452980`) 같은 신규 상장 종목이 일부 응답 빈 → success_krx 카운트 mismatch | sentinel 빈 응답 fix (`72dbe69`) 가 mrkcond+chart 4 곳에서 break — UseCase 가 `success_krx` 로 카운트하나 DB rows 0. ADR § 31 패턴 (NO-FIX) 동일 적용 — Stage 3 분석 시 detection |
| **H-8** | period 간 partial failure 누적 — daily 부분 실패면 weekly/monthly 미진행 정책? | 사용자 결정 — daily 실패 종목이 weekly/monthly 에도 동일 실패할 가능성 높음. 본 plan 은 **각 period 독립 진행** (daily 부분 실패해도 weekly/monthly 계속) + Stage 3 통합 분석. 사용자 변경 가능 |

## 5. DoD

### 5.1 Stage 1 (dry-run + 카운트 확정)

- [ ] DB query — 영숫자 active 종목 카운트 + sample 10건 (plan doc § 1.4 갱신)
- [ ] `backfill_ohlcv.py --dry-run` daily / weekly / monthly 각 1회 (estimated 시간 확인)
- [ ] 사용자 OK 후 Stage 2 진입

### 5.2 Stage 2 (실 백필)

- [ ] daily 3년 — exit code 0 또는 명시 분석된 부분 실패
- [ ] weekly 3년 — exit code 0 또는 명시 분석된 부분 실패
- [ ] monthly 3년 — exit code 0 또는 명시 분석된 부분 실패
- [ ] 3 period summary stdout 캡처 (Stage 3 분석 input)

### 5.3 Stage 3 (분석 + 문서 + 커밋)

- [ ] DB 적재 검증 SQL — 영숫자 stock ids × 3 period 별 row 카운트 (예상치 대비)
- [ ] anomaly 분석 — 빈 응답 / NUMERIC overflow / since_date edge / sentinel — Stage 3 SQL 결과로 확정
- [ ] ADR § 34 신규 — 결과 표 + anomaly 분석 + 후속 chunk 영향
- [ ] STATUS.md — § 0 / § 4 #19 / § 5 #1 → § 6 / § 6 chunk 누적 추가
- [ ] HANDOFF.md 전체 갱신
- [ ] CHANGELOG.md prepend — `feat(kiwoom): 영숫자 종목 OHLCV 3 period 백필 (Phase C 종결) — ADR § 34`
- [ ] 커밋 1건 — 본 chunk 의 모든 문서 변경 단일 commit
- [ ] push 여부 사용자 재확인 (~/.claude/CLAUDE.md 정책)

## 6. 다음 chunk (본 chunk 종결 후)

1. **scheduler_enabled 활성 + 1주 모니터** (STATUS § 5 최종) — env 변경 1건. 측정 #13 (일간 cron elapsed) + #19 (영숫자 +10분) 첫 영업일 정량화
2. **Phase D — ka10080 분봉 / ka20006 업종일봉** — 대용량 파티션 결정 선행
3. **Phase E/F/G** — 공매도/대차/순위/투자자별 wave
4. **(선택) ka10001 펀더멘털 영숫자 호출 검증** — Excel R22 ASCII 제약은 lookup endpoint 만. 실제 영숫자로 호출 시 wire 거부 여부 검증 후 별도 분기

---

_옵션 c-A 의 Phase C 종결 chunk. Chunk 1 dry-run (a14bb10) + Chunk 2 가드 완화 (ef7d598) 의 데이터 측면 완성._
