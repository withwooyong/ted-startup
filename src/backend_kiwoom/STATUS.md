# backend_kiwoom — 진척 현황 (STATUS)

> **단일 진실 출처** — 전체 작업의 어디까지 왔고 무엇이 남았는지 한 화면에서 파악
> **갱신 규칙**: chunk 완료 시 (커밋 직후) 본 문서 update. HANDOFF.md 와 함께 갱신.
> **연관**: `docs/plans/master.md` (전체 설계) / `docs/plans/endpoint-NN-*.md` (endpoint 별 상세 DoD) / `HANDOFF.md` (직전 세션) / `CHANGELOG.md` (시간순 변경)
> **마지막 갱신**: 2026-05-11 (chart 영숫자 stk_cd 가드 완화 — Chunk 1 dry-run 완료 / KRX 6/6 SUCCESS + NXT 6/6 empty / 우선주 dominant / ADR § 32)

---

## 0. 한눈에 보기

| 항목 | 값 |
|------|-----|
| 진행 Phase | **Phase C** (OHLCV + 일별 수급, 자격증명·종목sync admin CLI + since_date guard + daily_flow 백필 CLI — Phase C 97%) |
| 마지막 완료 chunk | **chart 영숫자 stk_cd 가드 완화 — Chunk 1 dry-run** — KRX 6/6 SUCCESS (ka10081 600 row / ka10086 20 row) + NXT 6/6 empty (우선주 미상장) / 우선주 dominant 패턴 (`*K` suffix) / Chunk 2 진행 결정 / ADR § 32 / 코드 0줄 |
| 다음 chunk | **chart 영숫자 가드 완화 Chunk 2** (옵션 c-A, Chunk 1 dry-run 완료 / ADR § 32) → Phase D/E/F/G → **(최종) scheduler_enabled 활성** |
| 25 Endpoint 진행 | **11 / 25 완료** (44%). CLI 도구 4건 |
| 누적 chunk | 39 commits (follow-up 분석 1) |
| 테스트 | **1037 cases** (1035 → +5 E-1 신규 / +6 gap 신규 / -6 should_skip_resume 폐기 / -3 placeholder 통합 / +2 dispatch yearly = net +4 ※ 통계 1035→1037) |
| 운영 검증 | ✅ **full 3년 OHLCV 백필 34분 / 4078 호환 / 0 failed**. daily_flow 백필 ⏳ 사용자 실측 대기 |

---

## 1. Phase 진척

| Phase | 범위 | 상태 | chunk 진행 | 주요 endpoint |
|-------|------|------|------------|---------------|
| **A — 기반 인프라** | Settings/Cipher/structlog/Migration 001/Auth/KiwoomClient/Scheduler | ✅ **완료** | A1 / 보안PR / A2-α/β / A3-α/β/γ + F1 (8) | au10001, au10002, ka10101 |
| **B — 종목 마스터** | stock + nxt_enable / 단건 조회 / 펀더멘털 | ✅ **완료** | B-α / B-β / B-γ-1 / B-γ-2 (4) | ka10099, ka10100, ka10001 |
| **C — OHLCV 백테스팅** | KRX/NXT 일봉 + 일별 수급 + 주/월/년봉 + 백필 | 🔄 **진행중 (95%)** | C-1α/β / C-2α/β/γ / R1 / C-3α/β / C-backfill / C-운영실측 준비 (11) | ka10081 ✅, ka10086 ✅, ka10082 ✅, ka10083 ✅, C-backfill ✅, 운영 실측 준비 ✅ / 측정 ⏳, ka10094 ⏳, daily_flow 백필 ⏳ |
| **D — 보강 시계열** | 분봉 / 틱 / 업종 일봉 | ⏳ 대기 | — | ka10079, ka10080, ka20006 |
| **E — 시그널 보강** | 공매도 / 대차거래 | ⏳ 대기 | — | ka10014, ka10068, ka20068 |
| **F — 순위** | 등락률/거래량/거래대금 5종 통합 | ⏳ 대기 | — | ka10027, ka10030, ka10031, ka10032, ka10023 |
| **G — 투자자별** | 일별 매매 / 종목별 / 연속매매 | ⏳ 대기 | — | ka10058, ka10059, ka10131 |
| **H — 통합** | 백테스팅 view, 데이터 품질 리포트, README/SPEC, Grafana | ⏳ 대기 | — | (인프라 only) |

**범례**: ✅ 완료 / 🔄 진행중 / ⏳ 대기 / ❌ 차단

---

## 2. 25 Endpoint 카탈로그 (진척별)

### 2.1 완료 (11 / 25)

| # | API | 명 | Phase | chunk | 커밋 |
|---|-----|----|-------|-------|------|
| 1 | au10001 | 접근토큰 발급 | A2-α | 1R 이중 리뷰 | `115fcce` |
| 2 | au10002 | 접근토큰 폐기 | A2-β | 1R + lifespan shutdown | `0ea955c` |
| 3 | ka10099 | 종목정보 리스트 | B-α | 1R + StockMasterScheduler | `bf9956a` |
| 4 | ka10100 | 종목정보 조회 | B-β | 1R + gap-filler / lazy fetch | `abce7e0` |
| 5 | ka10001 | 주식기본정보 | B-γ-1/2 | 1R+2R + 자동화 | `a287172` / `56dbad9` |
| 6 | ka10081 | 주식일봉차트 | C-1α/β | 1R+2R / 1R + 자동화 | `a98e37b` / `993874c` |
| 7 | ka10086 | 일별주가 (수급) | C-2α/β/γ/δ | 인프라 + 자동화 + Migration 008/013 (중복 컬럼 DROP) | `cddd268` / `e442416` / (C-2γ) / `8dd5727` |
| 8 | ka10101 | 업종코드 리스트 | A3-α/β | KiwoomClient 공통 + sector 영속화 | `cce855c` / `6cd4371` |
| 9 | ka10082 | 주식주봉차트 | C-3α/β | 인프라 + 자동화 (UseCase + Router 4 path + Scheduler 금 19:30) | `8fcabe4` / (C-3β) |
| 10 | ka10083 | 주식월봉차트 | C-3α/β | ka10082 와 동일 chunk (Period dispatch) — Scheduler 매월 1일 03:00 | `8fcabe4` / (C-3β) |
| **11** | **ka10094** | **주식년봉차트** | **C-4** | Migration 014 + UseCase YEARLY 분기 활성 + Router 2 path + Scheduler 매년 1월 5일 03:00. KRX only (NXT skip) | (this commit) |

### 2.2 진행중 / 다음 (0)

OHLCV 패밀리 (일/주/월) 자동화 + 백필 CLI 모두 완료. Phase C 95% 진행.
다음은 **운영 실측** (사용자 수동) / **daily_flow 백필** / **refactor R2** / **ka10094** (P2).

### 2.3 대기 (14 / 25)

P1 (1주 내):
| # | API | 명 | Phase | 비고 |
|---|-----|----|-------|------|
| 15 | ka10014 | 공매도 추이 | E | shsa endpoint 신규 |
| 16 | ka10068 | 대차거래 추이 | E | slb endpoint 신규 |

P2 (2주 내):
| # | API | 명 | Phase |
|---|-----|----|-------|
| 12 | ka10080 | 주식분봉차트 | D |
| 13 | ka20006 | 업종일봉조회 | D |
| 17 | ka20068 | 대차거래 (종목별) | E |
| 18~22 | ka10027/30/31/32/23 | 순위 5종 | F |
| 23~25 | ka10058/10059/10131 | 투자자별 3종 | G |

P3 (선택):
| # | API | 명 | Phase | 결정 |
|---|-----|----|-------|------|
| 11 | ka10079 | 주식틱차트 | D | 대용량 — 파티션 부담, 우선순위 낮음 |
| 20 | ka10031 | 전일 거래량 상위 | F | F 통합 collector 시 일괄 처리 |

---

## 3. Phase C 세부 진행 (현재)

| Sub-chunk | 범위 | 상태 | 산출물 |
|-----------|------|------|--------|
| C-1α | ka10081 일봉 OHLCV 인프라 (Migration 005/006 + ORM + Repository + Adapter + ExchangeType) | ✅ | `a98e37b` (1R+2R, 639 tests) |
| C-1β | ka10081 OHLCV 자동화 (UseCase + Router + Scheduler + Lifespan) | ✅ | `993874c` (1R, 694 tests) |
| C-2α | ka10086 일별 수급 인프라 (Migration 007 + ORM + Repository + Adapter + helpers) | ✅ | `cddd268` (1R, 760 tests) |
| C-2β | ka10086 일별 수급 자동화 (UseCase + Router + Scheduler + Lifespan) | ✅ | `e442416` (1R, 812 tests) |
| dry-run | 운영 raw 1,200 row 분석 (가설 B / NXT mirror / D-E 중복) | ✅ | `bf7320c` (ADR § 19/20) |
| C-2γ | Migration 008 — D-E 중복 컬럼 3개 DROP (13→10) | ✅ | 1R PASS, 816 tests / 93.11% (ADR § 21) |
| R1 | 3 도메인 일관 개선 (errors→tuple / StockMasterNotFoundError / LOW 3건) | ✅ | 1R PASS, 822 tests / 92.86% (ADR § 22) |
| C-3α | ka10082/83 인프라 — Migration 4 + ORM 4 + Repository + chart.py 확장 + Period enum | ✅ | 1R PASS, 897 tests / 97% (ADR § 23) `8fcabe4` |
| C-3β | ka10082/83 자동화 — IngestPeriodicOhlcvUseCase + Router 4 path + Scheduler 2 job | ✅ | 1R CONDITIONAL → PASS, 939 tests / 97% (ADR § 24) `2d4e2ae` |
| **C-backfill** | OHLCV 통합 백필 CLI — daily/weekly/monthly period dispatch + dry-run + resume | ✅ | 1R CONDITIONAL → PASS, 972 tests / 96% (ADR § 25) `055e81e` |
| **C-운영실측 준비** | runbook + 결과 템플릿 + ADR § 26 (코드 0 변경) | ✅ | 문서 3 신규 + 3 갱신, 972 tests 그대로 (ADR § 26) |
| **C-since_date fix** | smoke 첫 호출에서 발견된 max_pages 초과 운영 차단 fix — fetch_daily/weekly/monthly 에 since_date 옵션. dotenv autoload 누락 보완 | ✅ | 990 tests / KOSPI 1782 success / 8m 55s `d60a9b3` |
| **C-운영실측 측정** | smoke (KOSPI 10/1y) + mid (KOSPI 100/3y) + full (active 4078/3y) 3 단계 + NUMERIC SQL + ADR § 26.5 / results.md 채움 | ✅ | full 34분 / 0 failed / 2.7M KRX rows + 152K NXT rows / turnover_rate max 3257.80 (cap 33%) |
| **C-backfill-flow** | `scripts/backfill_daily_flow.py` (ka10086) — mrkcond since_date / ETF 가드 / `--indc-mode` / OHLCV 운영 차단 fix 3건 사전 적용 | ✅ | 1024 tests / +31 (mrkcond +2 / service +5 / CLI +24) — ADR § 27 / `phase-c-backfill-daily-flow.md` |
| **C-flow-실측 준비** | daily_flow 운영 실측 runbook + results doc 신규 (코드 0 변경) — OHLCV § 26 패턴 1:1 + ka10086 차이 반영 (단일 endpoint / `--indc-mode` / NUMERIC 4 컬럼) | ✅ | runbook 12 § + results 13 § / ADR § 27.5 자리 명시 + § 27 헤더 doc 참조 추가 |
| **C-flow-MAX_PAGES fix** | smoke 첫 호출 운영 차단 — `DAILY_MARKET_MAX_PAGES = 10 → 40` (가설 13배 틀림 / 실측 1 page ~22 거래일). smoke 재시도 PASS (6/2/0/25s) | ✅ | 1024 tests 그대로 — 상수 변경만 / ADR § 27.5 + § 27.6 갱신 |
| **C-flow-실측 측정** | Stage 0~3 + NUMERIC SQL 4 컬럼 + ADR § 27.5 결과 표 채움 | ✅ | full 9h 53m (3922/616/166 / NXT 166 fail) / NUMERIC 마이그레이션 불필요 / since_date edge 0 / 컬럼 동일값 의심 |
| **C-flow-empty-fix** | NXT 빈 응답 sentinel 무한 루프 fix (mrkcond + chart daily/weekly/monthly 4 곳 `if not <list>: break`) | ✅ | 010950 3년 reproduce PASS (13s / 0 fail) / 1026 tests (+2: mrkcond +1, chart +1) `72dbe69` |
| **C-flow-resume-eqcol** | failed 166 NXT resume 재시도 + 컬럼 동일값 검증 (`IS DISTINCT FROM` SQL) | ✅ | resume 166/10/0 / 21m 33s — 최종 DB KRX 4077 + NXT 626 (OHLCV 일치). 컬럼 동일값 확정 (2.88M rows / `credit_diff=0` / `foreign_diff=0`) — Migration 013 chunk 진입 |
| **C-2δ** | Migration 013 — C/E 중복 2 컬럼 DROP (`credit_balance_rate` / `foreign_weight`). 10 → 8 도메인 | ✅ | 1R PASS (M-1/L-1 fix), **1030 tests** (+4) / ADR § 28 / Verification 가 잡은 2건: VARCHAR(32) revision id truncation + test_008 hard-coded 카운트 |
| **C-4** | Migration 014 + ka10094 년봉 인프라 + 자동화. KRX only (NXT skip yearly_nxt_disabled). 응답 7 필드 + 매년 1월 5일 03:00 cron. Phase C chart 카테고리 종결 (10/25 → 11/25) | ✅ | **1035 tests** (+5) / ADR § 29 / Verification 가 잡은 5건: revision id 22 chars 사전 안전 / mypy invariant list / helper signature union / stale C-3α 가드 6건 / env alias 누락 2건 |
| **R2** | 1R Defer 5건 일괄 정리 — L-2 stale docstring 5곳 (C-4 가 YEARLY 활성 → 핸들러 추가 dead branch 라 폐기) / E-1 sync_ohlcv_daily KiwoomError 5종 핸들러 추가 / M-3 `# type: ignore` → `cast()` 2 Repository / E-2 reset_*_factory 7 docstring 정정 / **gap detection** — DB union 영업일 calendar 기반 일자별 차집합 검사 (2 CLI compute_resume_remaining_codes 시그니처 + 로직 변경, should_skip_resume 폐기) | ✅ | **1037 tests** / coverage 81.15% / ADR § 30 / 1R 리뷰 PASS (CRITICAL 0 / HIGH 0 / MEDIUM 3 — M-1/M-2 fix, M-3 정책 동일) / C-4 잔존 stale ruff 4건 함께 fix |

---

## 4. 알려진 이슈 / 운영 검증 미해결

| # | 항목 | 출처 | 결정 시점 |
|---|------|------|-----------|
| 1 | KOSCOM 공시 cross-check (가설 B 최종 확정) | dry-run § 20.4 | 향후 운영 검증 (수동 1~2건) |
| 2 | `indc_tp=1` (금액 모드) 단위 mismatch 검증 | dry-run § 20.4 | 향후 운영 검증 |
| 3 | ka10081 vs ka10086 OHLCV cross-check | dry-run § 20.4 | Phase H |
| ~~4~~ | ~~페이지네이션 빈도~~ | smoke 2026-05-10 | ✅ 정량화: 1년 = 1 page / 3년 = 1~2 page |
| ~~5~~ | ~~active 3000 + NXT 1500 sync 실측 시간~~ | full 2026-05-10 | ✅ **34분** (4078 호환 / NXT 626 / 0 failed) |
| ~~6~~ | ~~NUMERIC(8,4) magnitude 분포 (turnover_rate)~~ | full 2026-05-10 | ✅ max 3,257.80 / cap 33% / 마이그레이션 불필요 |
| ~~7~~ | ~~C-2α 상속 (foreign_holding_ratio / credit_ratio NUMERIC magnitude)~~ | ADR § 18.4 | ✅ 해소 — Stage 3 measurement: 4 컬럼 max < 100 / 마이그레이션 불필요 |
| ~~14~~ | ~~`DAILY_MARKET_MAX_PAGES=10` 부족~~ | smoke 2026-05-10 | ✅ 해소 (`7c07fb7`) — fix `=40` |
| ~~15~~ | ~~NXT 166 종목 max_pages=40 도 부족~~ | full 2026-05-11 | ✅ 해소 (`72dbe69`) — sentinel 무한 루프 mrkcond/chart 4 곳 fix + resume PASS |
| ~~16~~ | ~~컬럼 동일값 의심~~ | NUMERIC SQL 2026-05-11 | ✅ 확정 (`2317528`) — 2,879,500 rows 100% 동일 |
| ~~17~~ | ~~Migration 013 미진행~~ | resume 후 2026-05-11 | ✅ 해소 (`8dd5727`) — Migration 013 C-2δ / 10 → 8 도메인 / 1030 tests / ADR § 28 |
| ~~18~~ | ~~ka10094 (년봉) 미구현~~ | C-3β 가드 | ✅ 해소 (`<this commit>`) — C-4 Migration 014 / 11/25 endpoint / 1035 tests / ADR § 29 |
| ~~8~~ | ~~CLI bug: `--max-stocks` 무시~~ | smoke 2026-05-10 | ✅ 해소 (`76b3a4a`) |
| ~~9~~ | ~~ETF/ETN stock_code 호환성: 251 종목 ValueError~~ | smoke 2026-05-10 | ✅ 해소 (`c75ede6`) — UseCase 가드 (옵션 a) |
| ~~10 (F6)~~ | ~~since_date guard edge case — 2 종목 (002690, 004440)~~ | full 2026-05-10 | ✅ 분석 완료 (ADR § 31) — **NO-FIX** (0.13% / 1980s 상장 종목 / page 단위 break 의 row 잔존 / 데이터 가치 ≥ 비용) |
| ~~11 (F7)~~ | ~~turnover_rate min -57.32 음수 anomaly~~ | full 2026-05-10 | ✅ 분석 완료 (ADR § 31) — **NO-FIX** (키움 raw 보존 정직성 / 0.0009% / 분석 layer 책임) |
| ~~12 (F8)~~ | ~~full backfill 1 종목 빈 응답 (OHLCV 4078 fetch / 4077 적재)~~ | full 2026-05-10 | ✅ 식별 완료 (ADR § 31) — **`452980` 신한제11호스팩** (KOSDAQ SPAC, 2026-05-09 등록) / 신규 상장 직후 / sentinel 가드 정상 / **NO-FIX** |
| ~~daily_flow 빈 응답 1 종목~~ | ~~success_krx 3922 vs DISTINCT KRX 3921~~ | full 2026-05-11 | ✅ 식별 완료 (ADR § 31) — **`452980` 신한제11호스팩** (F8 동일 종목) / **NO-FIX** |
| **13** | 일간 cron 실측 (운영 cron elapsed) | dry-run § 20.4 | scheduler_enabled 활성화 chunk |

---

## 5. 다음 chunk 후보 (우선순위순)

| 순위 | chunk | 근거 | 예상 규모 |
|------|-------|------|-----------|
| **1** | **chart 영숫자 stk_cd 가드 완화 — Chunk 2** (옵션 c-A) | Chunk 1 dry-run (ADR § 32) 에서 KRX chart 가 `^[0-9A-Z]{6}$` 수용 확정. `STK_CD_CHART_PATTERN` 신규 + chart 계열 11곳 가드 교체. NXT 우선주는 기존 `nxt_enable=False` 가 자연 차단 | 코드 5 + 테스트 4 + 문서 4 |
| 2 | KOSCOM cross-check 수동 | 가설 B 최종 확정 | 수동 1~2건 |
| 3 | Phase D 진입 — ka10080 분봉 / ka20006 업종일봉 | 분봉 대용량 파티션 결정 선행 필요 | 신규 도메인 + 파티션 전략 |
| 4 | Phase E / F / G (공매도/대차/순위/투자자별) | 신규 endpoint wave | 각 chunk 별 신규 |
| **최종** | **scheduler_enabled 운영 cron 활성 + 1주 모니터** | **사용자 결정 (2026-05-11): 모든 작업 완료 후 활성**. 측정 #4 (일간 cron elapsed) / OHLCV + daily_flow + 통합 1주 모니터 → ADR § 26.5 + § 28 + § 29 + § 30 후속 측정 | env 변경 + 1주 |
| ※ | (실측 결과 의존) NUMERIC 마이그레이션 | 측정 #3 에서 NUMERIC(8,4) overflow 발견 시 즉시 1순위 상승 | Migration + ALTER COLUMN |

---

## 6. Phase A~B 완료 목록 (참고)

### Phase A (8 chunks)
- A1 — 기반 인프라 (Settings/Cipher/structlog/Migration 001/Repository) `12f46aa`
- A2 사전 보안 PR — ADR § 3 #1·#2·#3 (3R 이중 리뷰) `265b720`
- A2-α — au10001 KiwoomAuthClient 발급 `115fcce`
- A2-β — au10002 폐기 + lifespan graceful shutdown `0ea955c`
- A3-α — KiwoomClient 공통 트랜스포트 + ka10101 어댑터 `cce855c`
- F1 보안 — auth.py `__context__` leak 백포트 `035a68e`
- A3-β — sector 도메인 영속화 + UseCase + 라우터 `6cd4371`
- A3-γ — APScheduler weekly cron + lifespan `52c807b`

### Phase B (4 chunks)
- B-α — ka10099 종목 마스터 + StockMasterScheduler `bf9956a`
- B-β — ka10100 단건 조회 (gap-filler / lazy fetch) `abce7e0`
- B-γ-1 — ka10001 펀더멘털 인프라 (Migration 004) `a287172`
- B-γ-2 — ka10001 펀더멘털 자동화 (Phase B 마무리) `56dbad9`

### Phase C 진행 (8 chunks)
- C-1α — ka10081 일봉 OHLCV 인프라 (Migration 005/006) `a98e37b`
- C-1β — ka10081 OHLCV 자동화 `993874c`
- C-2α — ka10086 일별 수급 인프라 (Migration 007) `cddd268`
- C-2β — ka10086 일별 수급 자동화 `e442416`
- C-2γ — Migration 008 (D-E 중복 컬럼 DROP) `f8cece0`
- R1 — 3 도메인 일관 개선 `c3e0952`
- C-3α — ka10082/83 주/월봉 인프라 (Migration 009-012 + ORM 4 + Repository + chart.py 확장 + Period enum) `8fcabe4`
- C-3β — ka10082/83 주/월봉 자동화 (IngestPeriodicOhlcvUseCase + Router 4 path + Scheduler 금 19:30 / 매월 1일 03:00) `2d4e2ae`
- **C-backfill** — OHLCV 통합 백필 CLI (`scripts/backfill_ohlcv.py` daily/weekly/monthly + dry-run + resume + `_skip_base_date_validation` 옵션) `055e81e`
- **C-운영실측 준비** — runbook + 결과 템플릿 + ADR § 26 (코드 0 변경) `62079f1`
- **C-since_date fix** — backfill_ohlcv smoke 첫 호출 운영 차단 fix (chart.py fetch_daily/weekly/monthly 에 since_date 옵션 + UseCase + CLI 전파 + dotenv autoload 누락 보완) `d60a9b3`
- **C-max-stocks fix** — `--max-stocks` 가 dry-run 만 적용되고 실 백필에서 무시되던 CLI bug fix (변수명 `resume_only_codes` → `explicit_stock_codes` + max_stocks 단독 branch 추가) `76b3a4a`
- **C-ETF guard** — ka10081/82/83 호환 stock_code (`^[0-9]{6}$`) 사전 가드. ETF/ETN/우선주 (영문 포함 코드, 약 6.7%) UseCase 단계 skip + 가시성 로깅. smoke 통과 (3 fix 동시 작동 검증) `c75ede6`
- **C-운영실측 measurement** — smoke + mid + full 3 단계 측정 + NUMERIC SQL + ADR § 26.5 / results.md 채움 (코드 0 변경). 4078 종목 / 34분 / 0 failed `12f0daf`
- **C-backfill-flow** — `scripts/backfill_daily_flow.py` 신규 + mrkcond.py since_date + IngestDailyFlowUseCase ETF 가드 + only_stock_codes/skip_base_date_validation/since_date 확장. 1024 tests / +31 (ADR § 27 + plan doc 신규) `23f601b`
- **C-flow-실측 준비** — daily_flow 운영 실측 runbook + results doc 신규 (`backfill-daily-flow-runbook.md` 12 § + `backfill-daily-flow-results.md` 13 §). OHLCV § 26 패턴 1:1 + ka10086 차이. 코드 0 변경 `7be3185`
- **C-flow-MAX_PAGES fix** — smoke 첫 호출 (`7be3185` 후) `KiwoomMaxPagesExceededError` 8건 → mrkcond.py:50 `DAILY_MARKET_MAX_PAGES = 10 → 40`. smoke 재시도 PASS (6/2/0 / 25s) `7c07fb7`
- **C-flow-measurement** — Stage 0~3 + NUMERIC SQL 측정 완료 (코드 0 변경). full 9h 53m (3922/616/166 — KRX 0 fail / NXT 166 fail) / NUMERIC 4 컬럼 max < 100 (마이그레이션 불필요) / since_date edge 0 (OHLCV F6 보다 정확) / 컬럼 동일값 의심 `4e75dd3`
- **C-flow-empty-fix** — NXT 빈 응답 sentinel 무한 루프 fix (mrkcond + chart 4 곳 `if not <list>: break`). 010950 fix 후 13s 0 fail. 1026 tests `72dbe69`
- **C-flow-resume-eqcol** — failed 166 NXT 종목 `--only-stock-codes` 명시 resume + 컬럼 동일값 확정. resume: 166/10/0 / 21m 33s. 컬럼 동일값 SQL: 2,879,500 rows 모두 동일 (`credit_diff=0`, `foreign_diff=0`). 최종 DB: KRX 4077 / NXT 626 — OHLCV 일치. 코드 변경 0 `<this commit>`
- **C-도커실환경** — backend_kiwoom 전용 docker-compose + runbook 실 환경 값 채움 (검증 완료) `243d4c7`
- **C-admin-CLI** — register_credential.py + sync_stock_master.py + 11 테스트 (ka10099 진입 도구) `12e09c2`
- **C-env-rename** — DATABASE_URL → KIWOOM_DATABASE_URL (다른 프로젝트 격리, 5 코드 + 3 문서 rename) `e9ab050`
- **C-운영검증-1** — ka10099 첫 실 호출 + 2 차단 버그 fix (next-key 빈값 + upsert_many chunk 분할) + admin 도구 보강 (dotenv autoload + KIWOOM_API_KEY fallback + 마스터키 가이드 신규) `<this commit>`
- **C-4** — ka10094 년봉 OHLCV (Migration 014 / KRX only NXT skip / 응답 7 필드 / 매년 1월 5일 03:00 cron) `b75334c`
- **R2** — 1R Defer 5건 일괄 정리 (L-2 stale docstring 5 / E-1 sync_ohlcv_daily KiwoomError 5종 / M-3 cast 2 Repository / E-2 reset_*_factory 7 docstring / gap detection 2 CLI 일자별 차집합) `d43d956`
- **R2-docs sync** — R2 후 backfill runbook 의 resume 동작 설명 현행화 (3 곳) `d6357da`
- **follow-up 분석** — F6/F7/F8 + daily_flow 빈 응답 1건 통합 분석 (4건 모두 NO-FIX / `452980` 신한제11호스팩 식별) `e8d9d38`
- **chart 영숫자 stk_cd Chunk 1 dry-run** — KRX chart endpoint (ka10081/86) 영숫자 6자리 stk_cd 수용 확정 (rc=0 / 600+20 rows). NXT 우선주 미지원 확정 (sentinel empty). plan doc 신규 + dry-run CLI 신규 + 결과 doc 신규 / ADR § 32 / 코드 0줄 `<this commit>`

---

## 7. 갱신 절차 (체크리스트)

매 chunk 커밋 직후:
- [ ] § 0 한눈에 보기 — 마지막 완료 / 다음 chunk / 테스트 수 갱신
- [ ] § 1 Phase 진척 — 해당 Phase chunk 진행 + 상태 갱신
- [ ] § 2 Endpoint 카탈로그 — 완료 endpoint 이동 (대기 → 완료)
- [ ] § 3 (Phase C 진행 중에만) sub-chunk 상태 갱신
- [ ] § 4 알려진 이슈 — 해소된 항목 제거 / 신규 발견 항목 추가
- [ ] § 5 다음 chunk 후보 — 순위 재조정
- [ ] § 6 완료 목록 — 새 chunk 추가
- [ ] 마지막 갱신 날짜 갱신
