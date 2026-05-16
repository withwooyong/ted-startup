# backend_kiwoom — 진척 현황 (STATUS)

> **단일 진실 출처** — 전체 작업의 어디까지 왔고 무엇이 남았는지 한 화면에서 파악
> **갱신 규칙**: chunk 완료 시 (커밋 직후) 본 문서 update. HANDOFF.md 와 함께 갱신.
> **연관**: `docs/plans/master.md` (전체 설계) / `docs/plans/endpoint-NN-*.md` (endpoint 별 상세 DoD) / `HANDOFF.md` (직전 세션) / `CHANGELOG.md` (시간순 변경)
> **마지막 갱신**: 2026-05-16 (**Phase G — 투자자별 매매 흐름 3 endpoint 통합 ted-run 풀 파이프라인 완료**. ka10058/10059/10131 + Migration 019 + 3 테이블 (`investor_flow_daily` / `stock_investor_breakdown` / `frgn_orgn_consecutive`) + `KiwoomForeignClient` 신규 (`/api/dostk/frgnistt`) + 9 라우터 + 3 cron (20:00/20:30/21:00 KST). 사용자 D-1~D-17 일괄 확정 (권고 default). R1 sonnet 5.8 RETRY + opus 적대적 4.5 운영 D (CRITICAL 8 + HIGH 7) → fix 17건 (G-1 즉시 일괄 — lifespan + scheduler + batch payload + router payload + alias settings + Pydantic v2 + KST timezone) → R2 sonnet 9.2 PASS + opus 8.4 운영 B+ CONDITIONAL / inherit 5건 (inh-1 ka10059 트랜잭션 오염 5-18 dry-run 후 5-25 별도 chunk / D-11 임계치 / N-1 UNIQUE NULL distinct / N-2 lookup miss 모니터 / H-5 `_unwrap_client_rows`). **1596 tests** (+172 신규) / cov **84%** (-1.0%p, 대량 신규 코드 dip) / mypy strict **114 files** (+11). 25 endpoint **23/25 (92%)** 도달. ADR § 49 신규 (9 sub-§). **메모리 정책 `feedback_plan_doc_per_chunk` 정착 첫 chunk** (plan doc 신규 → ted-run skill 명시 호출 → 메타 4종 동시 commit). `_strip_double_sign_int` (ka10086 Phase C) + `_to_decimal_div_100` 신규 helper + 9 enum (`InvestorType` 12 + `InvestorTradeType` + `InvestorMarketType` + `AmountQuantityType` + `StockInvestorTradeType` + `UnitType` + `ContinuousPeriodType` 7 + `ContinuousAmtQtyType` + `StockIndsType`) + 3 Row + 3 Response + 3 Normalized dataclass + `_invoke_single` × 3 (G-3) + `_InvestorFlowScheduler` 베이스 + 3 subclass (KST 20:00/20:30/21:00 mon-fri / misfire 21600). 본 chunk = **backend_kiwoom 최대 chunk** (~4,600 production + 4,829 test 라인).)

---

## 0. 한눈에 보기

| 항목 | 값 |
|------|-----|
| 진행 Phase | **Phase G 완료** (ka10058/10059/10131 3 endpoint 통합 + Migration 019 + 3 테이블 + `KiwoomForeignClient` 신규 + 9 라우터 + 3 cron) — 25 endpoint **23/25 (92%)** 도달. 잔여 = D-2 ka10080 분봉 (마지막 endpoint, 대용량 파티션) |
| 마지막 완료 chunk | **Phase G — 투자자별 매매 흐름 3 endpoint 통합** (ted-run 풀 파이프라인 / **메모리 정책 `feedback_plan_doc_per_chunk` 정착 첫 chunk** — plan doc 신규 + ted-run skill 명시 호출 + 메타 4종 동시 commit). 사용자 D-1~D-17 권고 default 일괄 확정. R1 sonnet 5.8 RETRY + opus 4.5 D (CRITICAL 8 + HIGH 7) → fix 17건 (lifespan 6 setter + 3 InvestorFlowScheduler 신규 + 3 cron alias 통일 + ka10059 stock_codes 빌드 + 단건 stock_id lookup + Pydantic v2 syntax + KST timezone + SAVEPOINT/flush 광고 정정 D-12 옵션 A) → R2 sonnet 9.2 PASS + opus 8.4 B+ CONDITIONAL / inherit 5건 (inh-1 ka10059 60분 sync 트랜잭션 오염 / D-11 임계치 / N-1 NULL distinct / N-2 lookup miss 모니터 / H-5 휴리스틱). Verification 5관문 PASS (ruff + mypy 114 + pytest 1596 + cov 84% + scheduler smoke). 22 production (신규 16 + 갱신 6) + 14 신규 test = ~4,600/4,829 라인. ADR § 49 신규 (9 sub-§) |
| 다음 chunk | **5-18~5-22 (5거래일) dry-run** (Phase G 첫 cron 자연 발화 — 코드 0) → **inh-1 (D-12) 별도 chunk** (5-25 (월) — ka10059 60분 sync 트랜잭션 오염 SAVEPOINT vs 단건당 별도 세션 결정) → **D-2 ka10080 분봉** (마지막 endpoint — 25 endpoint 100% 도달) → **Phase H — 통합** (`phase-h-integration.md` 작성됨, Grafana 분리) → (선택) **Phase H' Grafana** |
| 25 Endpoint 진행 | **23 / 25 완료 (92%)** — Phase G 에서 +3 (ka10058/10059/10131). 잔여 = D-2 ka10080 + Phase H 통합 = 2건 |
| 누적 chunk | 59+ commits (Phase G 포함) |
| 테스트 | **1596 cases** (+172 신규) / coverage **84%** (-1.0%p, 대량 신규 코드 dip) / ruff PASS / mypy strict **114 files** PASS |
| 운영 검증 | ✅ **20 scheduler 활성** (F-4 17 + Phase G 3). ✅ **5-17 (월) 19:30 F-4 첫 cron 자연 발화 예정**. ✅ **5-18 (월) 20:00 Phase G 첫 cron 자연 발화 예정** (코드 0). **다음**: 5-18~5-22 dry-run + inh-1 트랜잭션 오염 발화 빈도 측정 → 5-25 D-12 chunk 진입 결정 |

---

## 1. Phase 진척

| Phase | 범위 | 상태 | chunk 진행 | 주요 endpoint |
|-------|------|------|------------|---------------|
| **A — 기반 인프라** | Settings/Cipher/structlog/Migration 001/Auth/KiwoomClient/Scheduler | ✅ **완료** | A1 / 보안PR / A2-α/β / A3-α/β/γ + F1 (8) | au10001, au10002, ka10101 |
| **B — 종목 마스터** | stock + nxt_enable / 단건 조회 / 펀더멘털 | ✅ **완료** | B-α / B-β / B-γ-1 / B-γ-2 (4) | ka10099, ka10100, ka10001 |
| **C — OHLCV 백테스팅** | KRX/NXT 일봉 + 일별 수급 + 주/월/년봉 + 백필 + 영숫자 호환성 | ✅ **종결 (데이터 측면 100%)** | C-1α/β / C-2α/β/γ/δ / R1/R2 / C-3α/β / C-backfill / C-4 / chart 영숫자 Chunk 1/2 / 영숫자 백필 (16) | 모두 ✅ / scheduler 활성만 남음 |
| **D — 보강 시계열** | 분봉 / 틱 / 업종 일봉 | 🔄 **진행** | **D-1 풀 구현 ✅** (`a1e20e0` plan doc + `249c277` 구현) / D-2 ka10080 분봉 마지막 / ka10079 (P3) | ka10079, ka10080, **ka20006 ✅ (D-1)** |
| **E — 시그널 보강** | 공매도 / 대차거래 | ✅ **완료** | plan doc § 12 (`ac6a941`) + 풀 구현 `0e767fe` | ka10014 ✅ / ka10068 ✅ / ka20068 ✅ |
| **F — 순위** | 등락률/거래량/거래대금 5종 통합 | ✅ **완료** | F-1/F-2/F-3/**F-4** ✅ (5 endpoint + Migration 018 + JSONB) | ka10027 ✅, ka10030 ✅, ka10031 ✅, ka10032 ✅, ka10023 ✅ |
| **G — 투자자별** | 일별 매매 / 종목별 / 연속매매 | ✅ **완료** | Phase G ✅ (3 endpoint + Migration 019 + KiwoomForeignClient + 9 라우터 + 3 cron) | ka10058 ✅, ka10059 ✅, ka10131 ✅ |
| **H — 통합** | 백테스팅 view, 데이터 품질 리포트, README/SPEC, Grafana | ⏳ 대기 | — | (인프라 only) |

**범례**: ✅ 완료 / 🔄 진행중 / ⏳ 대기 / ❌ 차단

---

## 2. 25 Endpoint 카탈로그 (진척별)

### 2.1 완료 (20 / 25)

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
| **11** | **ka10094** | **주식년봉차트** | **C-4** | Migration 014 + UseCase YEARLY 분기 활성 + Router 2 path + Scheduler 매년 1월 5일 03:00. KRX only (NXT skip) | `b75334c` |
| **12** | **ka20006** | **업종일봉조회** | **D-1** | Migration 015 + ORM + Pydantic 3 + DTO 2 + KiwoomChartClient.fetch_sector_daily + SectorPriceDailyRepository + UseCase Single+Bulk + Router 2 path + Scheduler mon-fri 07:00 KST. centi BIGINT + sector_id FK + NXT skip + 7 필드 응답. 9 scheduler 활성 | `249c277` |
| **13** | **ka10014** | **공매도 추이** | **E** | Migration 016 (`short_selling_kw` 테이블) + ORM + Pydantic 3 + ShortSellingTimeType enum + DTO 3 + KiwoomShortSellingClient.fetch_trend (KRX + NXT 시도) + ShortSellingKwRepository (UNIQUE + partial index `idx_*_weight_high`) + UseCase Single+Bulk (partial 5%/15% 분모=KRX only) + Router 4 path + Scheduler mon-fri 07:30 KST | `0e767fe` |
| **14** | **ka10068** | **시장 대차거래 추이** | **E** | Migration 016 (`lending_balance_kw` 통합, scope=MARKET) + ORM (partial unique 2 + CHECK `chk_lending_scope`) + Pydantic 3 + LendingScope enum + DTO 3 + KiwoomLendingClient.fetch_market_trend + LendingBalanceKwRepository.upsert_market (partial unique 매핑) + UseCase IngestLendingMarketUseCase + Router 2 path + Scheduler mon-fri 07:45 KST | `0e767fe` |
| **15** | **ka20068** | **종목별 대차거래 추이** | **E** | 공통 클래스 / 테이블 재사용 (scope=STOCK) — KiwoomLendingClient.fetch_stock_trend (KRX only Length=6) + LendingBalanceKwRepository.upsert_stock + UseCase IngestLendingStockUseCase + IngestLendingStockBulkUseCase (50건마다 commit) + Router 2 path + Scheduler mon-fri 08:00 KST (90분 grace) | `0e767fe` |
| **16** | **ka10027** | **전일대비 등락률 상위** | **F-4** | Migration 018 + ranking_snapshot 테이블 + RankingType.FLU_RT + KiwoomRkInfoClient.fetch_flu_rt_upper + IngestFluRtUpperUseCase 단건/Bulk + Router POST /sync (단건) + POST /bulk-sync (4 매트릭스) + GET /snapshot + Scheduler 19:30 KST mon-fri | (미커밋, ted-run 풀 파이프라인 본 chunk) |
| **17** | **ka10030** | **당일 거래량 상위** | **F-4** | RankingType.TODAY_VOLUME + 23 필드 nested payload (D-9 opmr/af_mkrt/bf_mkrt) + Scheduler 19:35 KST mon-fri | (미커밋, F-4) |
| **18** | **ka10031** | **전일 거래량 상위** | **F-4** | RankingType.PRED_VOLUME + 6 필드 단순 + Scheduler 19:40 KST mon-fri | (미커밋, F-4) |
| **19** | **ka10032** | **거래대금 상위** | **F-4** | RankingType.TRDE_PRICA + now_rank/pred_rank 직접 응답 + Scheduler 19:45 KST mon-fri | (미커밋, F-4) |
| **20** | **ka10023** | **거래량 급증** | **F-4** | RankingType.VOLUME_SDNIN + sdnin_qty/sdnin_rt sort 분기 + Scheduler 19:50 KST mon-fri | `4fc78a5` |
| **21** | **ka10058** | **투자자별 일별 매매 종목** | **G** | Migration 019 + `investor_flow_daily` 테이블 + `InvestorType` 12 / `InvestorTradeType` / `InvestorMarketType` enum + `KiwoomStkInfoClient.fetch_investor_daily_trade_stocks` + IngestInvestorDailyTradeUseCase 단건/Bulk (12 호출 매트릭스 default 3 inv × 2 mkt × 2 trde) + 3 라우터 (sync/bulk-sync/top) + Scheduler 20:00 KST mon-fri / misfire 21600 | (미커밋, Phase G 본 chunk) |
| **22** | **ka10059** | **종목별 투자자/기관별 (wide)** | **G** | `stock_investor_breakdown` 테이블 (12 net 컬럼) + `AmountQuantityType` / `StockInvestorTradeType` / `UnitType` enum + `_to_decimal_div_100` helper (`+698 → 6.98`) + `KiwoomStkInfoClient.fetch_stock_investor_breakdown` + 3000 종목 / BATCH=50 / 60분 sync + 3 라우터 (sync 단건 lookup / bulk-sync active 종목 / range NULL 조회) + Scheduler 20:30 KST mon-fri | (미커밋, Phase G) |
| **23** | **ka10131** | **기관/외국인 연속매매** | **G** | `frgn_orgn_consecutive` 테이블 (15 metric) + `KiwoomForeignClient` 신규 (`/api/dostk/frgnistt` 첫 endpoint) + `ContinuousPeriodType` 7종 + `ContinuousAmtQtyType` (★ ka10059 와 반대 의미 0=금액/1=수량) + `StockIndsType` (STOCK 만, D-14 INDUSTRY skip) + 3 라우터 (sync / bulk-sync 4 호출 / top by total_cont_days desc) + Scheduler 21:00 KST mon-fri | (미커밋, Phase G) |

### 2.2 진행중 / 다음 (0)

Phase G 3 endpoint → ✅ 완료 (2.1 #21~23). 다음 endpoint = D-2 ka10080 (마지막 endpoint, 대용량 파티션 전략).

### 2.3 대기 (2 / 25)

P2 (2주 내):
| # | API | 명 | Phase |
|---|-----|----|-------|
| 12 | ka10080 | 주식분봉차트 | D (**마지막 endpoint** — 대용량 파티션 전략 동반) |

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
| ~~18~~ | ~~ka10094 (년봉) 미구현~~ | C-3β 가드 | ✅ 해소 (`e8c901d`) — C-4 Migration 014 / 11/25 endpoint / 1035 tests / ADR § 29 |
| ~~8~~ | ~~CLI bug: `--max-stocks` 무시~~ | smoke 2026-05-10 | ✅ 해소 (`76b3a4a`) |
| ~~9~~ | ~~ETF/ETN stock_code 호환성: 251 종목 ValueError~~ | smoke 2026-05-10 | ✅ 해소 (`c75ede6`) — UseCase 가드 (옵션 a) |
| ~~10 (F6)~~ | ~~since_date guard edge case — 2 종목 (002690, 004440)~~ | full 2026-05-10 | ✅ 분석 완료 (ADR § 31) — **NO-FIX** (0.13% / 1980s 상장 종목 / page 단위 break 의 row 잔존 / 데이터 가치 ≥ 비용) |
| ~~11 (F7)~~ | ~~turnover_rate min -57.32 음수 anomaly~~ | full 2026-05-10 | ✅ 분석 완료 (ADR § 31) — **NO-FIX** (키움 raw 보존 정직성 / 0.0009% / 분석 layer 책임) |
| ~~12 (F8)~~ | ~~full backfill 1 종목 빈 응답 (OHLCV 4078 fetch / 4077 적재)~~ | full 2026-05-10 | ✅ 식별 완료 (ADR § 31) — **`452980` 신한제11호스팩** (KOSDAQ SPAC, 2026-05-09 등록) / 신규 상장 직후 / sentinel 가드 정상 / **NO-FIX** |
| ~~daily_flow 빈 응답 1 종목~~ | ~~success_krx 3922 vs DISTINCT KRX 3921~~ | full 2026-05-11 | ✅ 식별 완료 (ADR § 31) — **`452980` 신한제11호스팩** (F8 동일 종목) / **NO-FIX** |
| **13** | 일간 cron 실측 (운영 cron elapsed) | dry-run § 20.4 | 🔄 **활성 완료** (§ 36/§ 38) — 컨테이너 적재 완료. 1주 후 측정 별도 chunk (5-19 이후) |
| ~~21~~ | ~~5-11 NXT 74 rows 보완~~ | ADR § 35.8 | ✅ **해소** (§ 37, `00ac3b0`) — NXT 74 → 628 / 0 failed / 21m 6s / KRX 회귀 0 |
| **22** | `.env.prod` 의 잘못된 `KIWOOM_SCHEDULER_*` 9 env 정리 | ADR § 38.6.2' | 사용자 직접 (compose env override 로 우회 완료) |
| **23** | 노출된 secret 4건 회전 (API_KEY/SECRET/Fernet/Docker PAT) | ADR § 38.8 #6/#7 | 사용자 즉시 — 대화 로그 영구 기록 |
| ~~24~~ | ~~Mac 절전 시 컨테이너 중단 (24/7 cron 누락 위험)~~ | ADR § 38.8 #1 / § 42 / § 43 / § 44 | 🔄 **부분 해소** — § 43 misfire 21600 (sleep/resume catch-up) + § 44 kiwoom-db `restart: unless-stopped` (Docker Desktop graceful stop 후 자동 복구) + 보조 E backfill CLI 회복 검증 완료 (5-13 회복 15,898 row). **5-15 자연 cron 시 진정 효과 검증** |
| ~~31~~ | ~~`backfill_short.py` / `backfill_lending_stock.py` 5% 임계치 vs alphanumeric guard (~7%) 충돌~~ | § 44.9 | ✅ **해소** (Phase F-2, ADR § 46) — A+B 하이브리드 채택. `SentinelStockCodeError` 패턴 shsa/slb adapter + service bulk + CLI + cron 까지 확장. `total_skipped` / `total_alphanumeric_skipped` + `skipped_outcomes` tuple 분리. 9 production + 6 신규 test (31 케이스) / 1267 PASS / cov 86.43%. R2 inherit 7건 (다음 chunk) |
| ~~19~~ | ~~영숫자 295 종목 추가로 cron elapsed +10분 추정~~ | ADR § 33.6 → § 34.6 | ✅ **정정** — 영숫자 백필 실측 1108 종목 5m 48s = 0.31s/stock → **cron 추가 시간 ≈ 295 × 0.3 = ~1.5분** (이전 추정의 15%) |
| **20** | NXT 우선주 sentinel 빈 row 1개 detection | ADR § 32.3 + § 33.6 | LOW — 운영 영향 0 (`nxt_enable=False` 자연 차단), 미래 chunk 검토 |
| ~~26~~ | ~~5-13 06:00/06:30/07:00 cron dead~~ | 5-13 17:30 재현 모니터 | ✅ **자연 재현 반증** (`<this chunk>`) — 17:30 stock_master fetched=4788 정상 발화 + 18:00 stock_fundamental total=4379 정상 발화. 06:00 의 dead 는 컨테이너 재배포 직후 일회성 가설로 정리. `/admin/scheduler/diag` 진단 endpoint 유지 (운영 가치). ADR § 41 신규 § 후보 (별도, 코드 변경 0). |
| ~~27~~ | ~~ka20006 sector_daily 60% 실패~~ | 운영 검증 완료 | ✅ **운영 검증 PASS** (5-14 06:58, `<this chunk>`) — 124/124 success / 0 failed / 0 MaxPages / 0 InterfaceError. 이전 60/124 → 100%. DB 적재 123 (1 sentinel break). |
| ~~28~~ | ~~ka10086 KOSDAQ 1814 누락~~ | 운영 검증 완료 | ✅ **운영 검증 PASS** (5-14 06:53~07:00, `<this chunk>`) — KOSDAQ 1487 KRX + 224 NXT success / 0 failed / 7m 7s. 0 MaxPages. backfill CLI `--only-market-codes 10 --resume`. |
| ~~**30**~~ | ~~5-14 06:00 OhlcvDaily / 06:30 DailyFlow cron miss~~ | 본 chunk 분석 완료 | ✅ **원인 확정** (`<this chunk>` ADR § 42) — Mac 절전 → Docker VM sleep → APScheduler timer 미발화. pmset 5-13 20:01~21:12 반복 Sleep 증거. 해결 옵션 § 42.5 (caffeinate / 서버 이전 / misfire 전체 / launchd / 현재 유지) 사용자 환경 결정 대기 |
| ~~29~~ | ~~**ka10001 stock_fundamental 7.2% 실패** (5-13 18:00 cron)~~ | 5-13 18:00 cron | ✅ **해소** (Phase F-1, ADR § 45) — `trade_compare_rate (8,4)→(12,4)` + `low_250d_pre_rate (8,4)→(10,4)` Migration 017 + `SentinelStockCodeError(ValueError)` 신설 + `FundamentalSyncResult.skipped` 분리. 5-14 18:00 cron 부터 NumericValueOutOfRangeError 11건 → 0건 + failed=실제 실패 (sentinel 제외) 예상 |
| ~~**32**~~ | ~~F-2 R2 inherit 7건~~ | ADR § 46.8 | ✅ **해소** (Phase F-3, ADR § 47) — D-1~D-8 사용자 확정 default 일괄 채택. SkipReason StrEnum 신규 모듈 + errors_above_threshold tuple 통일 + empty helper + 단건 sentinel catch + skipped_count property + backfill label fix. 16 파일 +573/-230 / **1284 tests** / cov **86.56%** |
| ~~**34**~~ | ~~F-3 R2 inherit 5건~~ | ADR § 47.8 | ✅ **해소 (Phase F-4)** — inh-1 router DTO breaking (F-4 ranking router 진입 시 자체 호출자 검증 완료) / inh-2 coverage 설정 (pyproject.toml 명시) / inh-3 SkipReason 위치 통일 / inh-4 lending log / inh-5 ruff auto-fix 기록 |
| **38** | Phase H 결정 게이트 D-1~D-6 (사용자 확정 필수) | `phase-h-integration.md` § 4 | view 전략 (마테/동적/이중) / 알람 채널 (Telegram/log/둘다) / SPEC.md 범위 / quality cron 주기 / retention / backfill view 범위. 25 endpoint 100% 도달 후 ted-run 진입 직전 수집 |
| ~~**39**~~ | ~~F-4 R2 inherit 5건~~ | ADR § 48.4 / § 48.8 | 🔄 일부 진행 — inh-1 Bulk 트랜잭션 오염 Phase G dry-run 으로 진입 (5-25 별도 chunk) / inh-2~inh-5 Phase F-5 또는 별도 분산 |
| **40** | 5-17 (월) 19:30 첫 ranking cron 발화 검증 | Phase F-4 운영 검증 | ka10027 → 5분 chain → 19:50 ka10023. 응답 schema / row 수 / lookup miss 비율 / NXT `_NX` 보존 / 23 필드 nested (D-9) 검증. 운영 결정 항목 § 6.6 |
| **41** | Coverage dip 86.56% → 85.00% → 84% | F-4 + Phase G 누적 | F-4 -1.56%p + Phase G -1.0%p = 누적 -2.56%p. 대량 신규 코드 dip. 운영 1주 후 cron 발화 자연 재평가 |
| **42** | Phase G R2 inherit 5건 | ADR § 49.4 / § 49.8 | **inh-1** ka10059 Bulk 트랜잭션 오염 (Phase E/F-4 상속, **5-18~5-22 dry-run 후 5-25 (월) 별도 chunk**) / **inh-2** `errors_above_threshold` D-11 임계치 (Phase H) / **inh-3** stock_investor_breakdown UNIQUE NULL distinct (Migration 020 후속) / **inh-4** lookup miss 운영 모니터 (Phase H 데이터 품질) / **inh-5** `_unwrap_client_rows` 휴리스틱 (F-3/F-4 동일, type-safety chunk) |
| **43** | 5-18 (월) 20:00 첫 Phase G cron 발화 검증 | Phase G 운영 검증 | 20:00 ka10058 → 30분 후 20:30 ka10059 (3000 종목 60분 sync) → 21:00 ka10131. 운영 검증 5건: ka10059 60분 sync 완주율 / inh-1 PG abort 발화 빈도 / 토큰 만료 (D-13) / `netslmt_qty` 부호 / `flu_rt` "+698"→6.98 / `amt_qty_tp` 반대 의미 / `tot_cont_days` 합산 / `_NX` Length=6 |

---

## 5. 다음 chunk 후보 (우선순위순)

| 순위 | chunk | 근거 | 예상 규모 |
|------|-------|------|-----------|
| **1** | **5-17 (월) 19:30 F-4 자연 cron 검증 + 5-18 (월) 20:00 Phase G 자연 cron 검증** | 본 chunk + Phase F-4 효과 동시 검증. 코드 0 | 운영 / 코드 0 |
| **2** | **inh-1 Bulk 트랜잭션 오염 fix** (Phase E/F-4 상속, **D-12 별도 chunk**) | Phase G dry-run 5-18~5-22 (5거래일) 결과 후 5-25 (월) 진입. ka10059 60분 sync PG abort 발화 빈도 측정 → SAVEPOINT (begin_nested) vs 단건당 별도 세션 결정 | 별도 chunk (Migration 020 + N-1 NULL distinct 통합 가능) |
| **3** | **Phase D-2 ka10080 분봉 (마지막 endpoint)** | 25 endpoint 100% 도달. 사용자 결정 (5-12) — 대용량 파티션 전략 결정 동반 | 신규 도메인 + 파티션 |
| 4 | F-4 / G R2 inherit 분산 | inh-2 errors_above_threshold (Phase H) / inh-3 N-1 (D-12 통합) / inh-4 N-2 (Phase H 품질) / inh-5 `_unwrap_client_rows` (type-safety) | Phase H / type-safety chunk |
| **6** | **Phase H — 통합 (백테 view + 데이터 품질 + README/SPEC)** — _Grafana 제외_ (`phase-h-integration.md` 작성됨 2026-05-15) | 25 endpoint 100% 도달 후 진입 (G + D-2 선행). 마테리얼라이즈드 view 4 + quality SQL + Telegram alert + SPEC.md. 결정 게이트 D-1~D-6 사용자 확정 필수 | ~500-800 prod + ~300-500 test |
| 7 | **Phase H' — Grafana 대시보드** (사용자 마지막 chunk) | Phase H view + alert 위에 시각화 | 별도 chunk |
| 6 | Phase E follow-up — partial 비교 연산자 통일 / `--max-stocks` CLI 적용 / placeholder factory 리팩토링 (§ 40.8) | 1R Defer (MEDIUM/LOW 별도 chunk) | 작음 |
| 6 | D-1 follow-up: inds_cd echo 검증 / close_index Decimal 통일 / backfill_sector CLI | ADR § 39.8 1R MEDIUM/LOW | 운영 첫 호출 후 결정 |
| 7 | KOSCOM cross-check 수동 | 가설 B 최종 확정 | 수동 1~2건 |
| 8 | 영숫자 daily_flow (ka10086) 백필 | OHLCV 와 별개. cron 자연 수집 가능 | 사용자 결정 |
| 9 | (전체 개발 종결 후) secret 회전 | ADR § 38.8 #6/#7 / `docs/ops/secret-rotation-2026-05-12.md` 절차서 | 사용자 직접 (회전 진행) + 검증 SQL |
| ~~※~~ | ~~(실측 결과 의존) NUMERIC 마이그레이션~~ | ✅ 해소 — § 34.5 영숫자 max < 35% cap 확인. 마이그레이션 불필요 | — |

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
- **C-flow-resume-eqcol** — failed 166 NXT 종목 `--only-stock-codes` 명시 resume + 컬럼 동일값 확정. resume: 166/10/0 / 21m 33s. 컬럼 동일값 SQL: 2,879,500 rows 모두 동일 (`credit_diff=0`, `foreign_diff=0`). 최종 DB: KRX 4077 / NXT 626 — OHLCV 일치. 코드 변경 0 `e8c901d`
- **C-도커실환경** — backend_kiwoom 전용 docker-compose + runbook 실 환경 값 채움 (검증 완료) `243d4c7`
- **C-admin-CLI** — register_credential.py + sync_stock_master.py + 11 테스트 (ka10099 진입 도구) `12e09c2`
- **C-env-rename** — DATABASE_URL → KIWOOM_DATABASE_URL (다른 프로젝트 격리, 5 코드 + 3 문서 rename) `e9ab050`
- **C-운영검증-1** — ka10099 첫 실 호출 + 2 차단 버그 fix (next-key 빈값 + upsert_many chunk 분할) + admin 도구 보강 (dotenv autoload + KIWOOM_API_KEY fallback + 마스터키 가이드 신규) `e8c901d`
- **C-4** — ka10094 년봉 OHLCV (Migration 014 / KRX only NXT skip / 응답 7 필드 / 매년 1월 5일 03:00 cron) `b75334c`
- **R2** — 1R Defer 5건 일괄 정리 (L-2 stale docstring 5 / E-1 sync_ohlcv_daily KiwoomError 5종 / M-3 cast 2 Repository / E-2 reset_*_factory 7 docstring / gap detection 2 CLI 일자별 차집합) `d43d956`
- **R2-docs sync** — R2 후 backfill runbook 의 resume 동작 설명 현행화 (3 곳) `d6357da`
- **follow-up 분석** — F6/F7/F8 + daily_flow 빈 응답 1건 통합 분석 (4건 모두 NO-FIX / `452980` 신한제11호스팩 식별) `e8d9d38`
- **chart 영숫자 stk_cd Chunk 1 dry-run** — KRX chart endpoint (ka10081/86) 영숫자 6자리 stk_cd 수용 확정 (rc=0 / 600+20 rows). NXT 우선주 미지원 확정 (sentinel empty). plan doc 신규 + dry-run CLI 신규 + 결과 doc 신규 / ADR § 32 / 코드 0줄 `a14bb10`
- **chart 영숫자 stk_cd Chunk 2 구현** — `STK_CD_CHART_PATTERN = ^[0-9A-Z]{6}$` 신규 + `_validate_stk_cd_for_chart` 함수 + chart 계열 11곳 가드 교체 (build_stk_cd / 5 router 7 path / 3 UseCase). lookup 계열 5곳 무변 (ka10100/ka10001). 6 회귀 테스트 의미 반전 + 신규 5 보호/통과 단언 / 1046 tests / coverage 91% / ADR § 33 `ef7d598`
- **영숫자 OHLCV 3 period 백필** — daily 1108 (영숫자 295 + 비영숫자 gap 813) / weekly 4373 / monthly 4373 (영업일 calendar ∅ 첫 적재) = 0 failure / 47m 33s / 영숫자 75,149 rows 적재 / anomaly 0건 (NUMERIC max < 35% cap, F6/F7/F8 영숫자 영향 0). 운영 cron +N분 추정 정정 (10 → 1.5). 코드 변경 0. plan doc 신규 + ADR § 34 / `7f6beb5`
- **cron NXT 마감 후 새벽 이동** — OhlcvDaily mon-fri 18:30→06:00 / DailyFlow mon-fri 19:00→06:30 / Weekly fri 19:30→sat 07:00. NXT 거래 17:00~20:00 진행 중 cron 결함 fix (사용자 발견 + 5-11 NXT 74 rows 정황). base_date default=`today()` 가 06:00 cron 과 충돌 — `fire_*_job` 에서 `previous_kst_business_day(today)` 명시 전달. `app/batch/business_day.py` helper 신규. 1059 tests / ADR § 35 / `8c14aa3`
- **scheduler_enabled 활성 + 1주 모니터** — .env.prod 9 env 추가 (KIWOOM_SCHEDULER_ENABLED=true + 8 alias=prod). 코드 변경 0. lifespan fail-fast 통과 / 첫 발화 5-13 (수) 06:00 OhlcvDaily. 1주 후 측정 (cron elapsed / NXT 정상 / failed / 알람) 은 별도 chunk (사용자 결정). plan doc + ADR § 36 / `cebd262`
- **5-11 NXT 보완 백필** (§ 35.8 별도 chunk) — `backfill_ohlcv.py --period daily --start-date 2026-05-11 --end-date 2026-05-11` (--resume 미사용). NXT 74 → 628 / KRX 4373 success (DB 4370 = 5-7/8 대비 -2 신규/정지) / 0 failed / 21m 6s / 5003 calls (영숫자 nxt_enable=false 호출 skip). § 35 cron shift 데이터 정합성 확정 + § 36.5.2 1주 모니터 SQL 깨끗 진행 / 코드 변경 0 / 검증 SQL 4건 PASS / ADR § 37 / `00ac3b0`
- **Docker 컨테이너 배포 (kiwoom-app)** — Dockerfile (multi-stage builder+runtime, python:3.12-slim, uv --frozen, non-root uid 1001, tzdata Asia/Seoul, HEALTHCHECK) + scripts/entrypoint.py (alembic upgrade → uvicorn workers=1) + uv.lock 87 packages + docker-compose.yml kiwoom-app service (env_file=../../.env.prod, SCHEDULER_* 8 env override, depends_on=kiwoom-db healthy, restart=unless-stopped) + .dockerignore + README Docker 섹션. **빌드 hang 2건 해결**: credsStore desktop→osxkeychain, syntax directive 제거. **env_prefix 불일치 발견** (.env.prod 의 KIWOOM_SCHEDULER_* 잘못 → compose environment 의 SCHEDULER_* 로 override). 이미지 264MB / 5초 기동 / 8 scheduler 활성 / /health OK / TZ KST / 5-13 06:00 첫 발화 준비. 코드 변경 0 (app/ 무변, scripts/entrypoint.py 신규) / ADR § 38 / `550bee5`
- **secret 회전 절차서 + 회전 시점 결정** (5-12) — `docs/ops/secret-rotation-2026-05-12.md` 신규 230줄 + ADR § 38.8 #6/#7 시점 "전체 개발 완료 후" 로 통일. KIWOOM_APPKEY/SECRETKEY + Fernet 마스터키 + Docker Hub PAT 회전 절차 (4 단계 + 백업 + 롤백 + 완료 체크리스트). 사용자 결정 — `.env.prod` 편집 / DB 재암호화 운영 영향 큼 → 개발 종결 후 일괄. 코드 변경 0 / ADR § 38.8 갱신 / HANDOFF Pending #2 갱신 / `39ca7a3`
- **Phase D-1 ka20006 plan doc § 12** (5-12) — `endpoint-13-ka20006.md` 의 § 12 신규 (Migration 015 + 인프라 + 자동화 통합 chunk). 9 결정 + 13 self-check + DoD. 코드 변경 0 / `a1e20e0`
- **Phase D-1 ka20006 풀 구현** (5-12) — Migration 015 (sector_price_daily, sector_id BIGINT FK, UNIQUE (sector_id, trading_date), centi BIGINT 4 컬럼) + ORM + Pydantic 3 (SectorChartRow 7 필드 / Response / NormalizedSectorDailyOhlcv) + DTO 2 (Input / Outcome / BulkResult with skipped) + KiwoomChartClient.fetch_sector_daily (sentinel break) + SectorPriceDailyRepository (upsert_many) + IngestSectorDailyUseCase Single+Bulk (NXT skip + sector_master_missing + sector_inactive 3 가드) + Router 2 path (admin API key) + Scheduler mon-fri 07:00 KST + Settings alias + main.py lifespan 통합. 1R CONDITIONAL → PASS (CRITICAL 3 main.py 통합 누락 + HIGH 2 sector_id INTEGER→BIGINT/skipped 분리 fix). Verification 5관문 PASS. 컨테이너 재배포 (alembic 014→015 자동 적용 / 9 scheduler 활성 / /health OK). 7 신규 + 5 갱신 코드 + 6 신규 테스트 = **1097 tests / coverage 90%** / ruff PASS / mypy strict PASS / 12/25 endpoint. ADR § 39 / `249c277`
- **Phase E 컨테이너 재배포 + scheduler dead 진단 endpoint** (5-13) — 5-13 06:00/06:30/07:00 KST cron dead 발견 (13시간 idle 후 9 scheduler 의 timer 가 모두 발화 0 → KRX/NXT/sector_daily 5-12 row 0). 코드 정적 분석 + baseline 검증 (별도 python 프로세스 1분 cron 정상 발화) + py-spy attach (메인 thread `do_epoll_wait` idle = alive) 모두 정상 — 9개 race 가설 입증 불가. `/admin/scheduler/diag` endpoint 추가 (`require_admin_key` 가드 / 12 scheduler 의 `_eventloop_id`, `eventloop_is_main`, `timeout.cancelled`, `timeout.delta_seconds`, `next_run_time` 노출) + `_app.state.schedulers` dict lifespan 노출. docker-compose.yml 에 Phase E 3 alias env (`SCHEDULER_SHORT_SELLING_SYNC_ALIAS` / `SCHEDULER_LENDING_MARKET_SYNC_ALIAS` / `SCHEDULER_LENDING_STOCK_SYNC_ALIAS` = `prod`) 추가. 컨테이너 재빌드 + 재배포 → 12 scheduler 활성. baseline diag 결과 = 12개 모두 `main_loop_id=187651270154288` 동일 / `timeout.cancelled=false` / `next_run_time` KST 정확 → 인스턴스 race 가설 반증. 다음 단계 = 5-12 D-1 백필 + 5-13 17:30 stock_master 발화 시 재현 모니터. 2 파일 / `0ec6326`
- **5-13 dead 가설 반증 + 신규 인시던트 진단 + Phase D-1 follow-up plan doc § 13 추가** (5-13) — 17:30 stock_master / 18:00 stock_fundamental **자연 cron 정상 발화** 확인 (각각 fetched=4788/total=4379) → dead 가설 반증, 06:00 일회성 가설 정리. 그러나 진단 중 신규 인시던트 3건 발견: (a) ka20006 sector_daily — `KiwoomMaxPagesExceededError` 56건 + `asyncpg.exceptions._base.InterfaceError: the number of query arguments cannot exceed 32767` 8건 (sector_id 29/57/102/103/105-108) — PostgreSQL wire protocol int16 한도 (b) ka10086 KOSDAQ ~1814 누락 — `DAILY_MARKET_MAX_PAGES=40` 부족 (c) ka10001 stock_fundamental 7.2% 실패 (316/4379) — `asyncpg.exceptions.NumericValueOutOfRangeError: precision 8 scale 4 must < 10^4` 11건 + sentinel 거부 2건. (a)+(b) → **endpoint-13 § 13 Phase D-1 follow-up plan doc** 작성 (cap 상향 + `_chunked_upsert` helper + chunk_size=1000 + `KiwoomMaxPagesExceededError(page, cap)`). (c) → F chunk 별도. endpoint-10 § 14 cross-ref 추가. 2 plan doc 갱신 / 코드 변경 0 / 1186 tests 그대로 / `478efaa`
- **Phase D-1 follow-up 풀 구현** (5-14, ted-run) — `SECTOR_DAILY_MAX_PAGES = 10 → 40` (chart.py) + `DAILY_MARKET_MAX_PAGES = 40 → 60` (mrkcond.py) + `KiwoomMaxPagesExceededError(*, api_id, page, cap)` 시그니처 확장 (`_client.py`, raise site 갱신) + `_chunked_upsert(session, statement_factory, rows, *, chunk_size=1000) -> int` helper 신규 (`_helpers.py`, **2b 2R M-1**: `n_cols × chunk_size > 32767` fail-fast 가드 + **2a 2R M-2**: factory stateless docstring 명시) + `SectorPriceDailyRepository.upsert_many` `_chunked_upsert` 적용 (8 col × 1000 = 8000 args/chunk) + `StockDailyFlowRepository.upsert_many` 동일 패턴 (12 col × 1000 = 12000 args/chunk). 1R 2a (sonnet) PASS + 2a 2R M-1 (chart.py:742 docstring `(10)` → `(40)` 정합) fix. 1R 2b (opus) PASS + 2b 2R M-1 (col 가드) fix. Verification 5관문 PASS (ruff: clean / mypy strict: 95 files Success / pytest: **1199 passed** / coverage **86.13%** / 보안스캔 ⚪ 계약분류 / 런타임 ✅ import collection / E2E ⚪ UI 변경 0). 코드 6 파일 + 테스트 5 (4 갱신 + 1 신규) = +13 cases. Migration 0 / UseCase 변경 0. ADR § 41 신규. `f7bcfe3`
- **Phase D-1 follow-up E4 — 컨테이너 재배포 + 5-12 운영 백필 재호출** (5-14, 06:50~07:00 KST) — `docker compose build kiwoom-app` (캐시 빌드) + `up -d` → /health ok + 12 scheduler 활성 (06:51 KST). (a) **sector_daily 5-12 bulk sync** (06:58) — `POST /api/kiwoom/sectors/ohlcv/daily/sync?alias=prod&base_date=2026-05-12` 응답 `total=124, success=124, failed=0, errors=[]` (이전 60/124). DB sector_price_daily 5-12: 59 → 123 (1 sentinel). (b) **KOSDAQ daily_flow backfill CLI** (06:53~07:00) — `docker compose exec -T kiwoom-app python scripts/backfill_daily_flow.py --alias prod --start-date 2026-05-12 --end-date 2026-05-12 --only-market-codes 10 --resume` 결과 `total=1487 / success_krx=1487 / success_nxt=224 / failed=0 / 7m 7s / avg 0.3s/stock`. 0 MaxPages / 0 InterfaceError 검증. (c) **5-14 06:00/06:30 cron miss 발견** (재배포 직전 1시간) — scheduler dead 재발 가능성 → 다음 chunk. (d) 07:00 sector_daily cron 자연 발화 정상 (chart.py 호출 진행). ADR § 41.7 운영 결과 표 + § 41.8 추가 발견 + § 41.9 다음 chunk 갱신. 코드 변경 0 / `5b16d2e`
- **scheduler dead 원인 확정 분석** (5-14, 07:00~07:30 KST) — § 41.8 발견 (5-14 06:00/06:30 cron miss) 후속 진단. (a) **pmset -g log 결정적 증거** — 5-13 20:01:26 / 20:17:35 / 20:34:28 / 20:39:28 / 20:57:07 / ... 반복 Sleep entering (Battery 모드, Charge 80%, `Sleep Service Back to Sleep` + `Maintenance Sleep`). (b) **현재 pmset 상태** — `sleep prevented by sharingd, caffeinate*3, powerd, JANDI` = 현재만 caffeinate 활성 (5-13 비활성 = 자유 절전). (c) **가설 평가 5종** — Mac 절전 ✅ 확정 / APScheduler race 반증 (5-13 diag baseline 12 main_loop 동일 + 자연 발화 17:30/18:00 정상) / Docker network 반증 / healthcheck restart 반증 (`docker inspect finishedAt=0001-01-01`) / Battery 반증 (Charge 80%). (d) **cron 별 misfire 정책 표** — 07:30/07:45/08:00 만 misfire (30분/30분/90분 grace) / 06:00/06:30/03:00 새벽 cron 위험. (e) **해결 옵션 § 42.5 5개** — A caffeinate 영구 활성 (launchd) / B 별도 Linux 서버 / C APScheduler misfire 전체 적용 / D launchd cron / E 현재 유지. ADR § 42 신규 + § 38.8 #1 갱신 (위험 가설 → 확정 인시던트). 사용자 환경 결정 대기. 코드 변경 0 / `d36cf51`
- **Phase D — scheduler misfire_grace_time 통일** (5-14, ted-run) — § 42.5 옵션 C + 보조 E 채택. 12 스케줄러 `MISFIRE_GRACE_SECONDS: Final[int] = 21600` (6h) 통일. **/admin/scheduler/diag** jobs dump 에 `misfire_grace_time` 노출. ADR § 43 신규. `79d1355`
- **Phase D 운영 검증 + kiwoom-db restart 정책 fix + 5-13 backfill 회복** (5-14) — 12 scheduler 활성 + mg=21600 노출 12/12 + kiwoom-db `restart: unless-stopped` + 5-13 backfill 5 테이블 15,898 row 회복. ADR § 44. `b9d32a6`
- **Phase F-1 — ka10001 NUMERIC overflow + sentinel WARN/skipped 분리** (5-14, ted-run) — § 4 #29 (5-13 18:00 cron 7.2% 실패) + § 44.9 해소. `trade_compare_rate (8,4)→(12,4)` + `low_250d_pre_rate (8,4)→(10,4)` Migration 017 운영 적용. `SentinelStockCodeError(ValueError)` 신설 (stkinfo) + `FundamentalSyncResult.skipped: tuple[...]` 분리. R1+R2 PASS / MEDIUM 3 fix / 1236 PASS / cov 86.19%. ADR § 45. `ced66f3`
- **Phase F-2 — backfill 임계치 / alphanumeric guard 분리** (5-14, ted-run) — § 4 #31 + § 44.9 해소. F-1 sentinel 패턴 1:1 확장 (shsa/slb adapter + service bulk + scheduler cron log + CLI 두 파일). 사용자 4 확정 D-1~D-4 (A+B 하이브리드 / 분리 신규 필드 / 분모 유지 + 메시지 명시 / `filter_alphanumeric` 신규 파라미터). R1 HIGH 2 + MEDIUM 7 모두 fix (Step 2 fix 8건 — H-1 A SQL 복원 / MED-1 F-1 `skipped_outcomes` 패턴 이식 / MED-2 cron 가시성 / 정규식 앵커 / alembic env.py 결정) + R2 양쪽 합의 PASS (inherit 7건 § 46.8). 9 production + 6 신규 + 2 회귀 + 1 infra = 18 파일 +232/-28 production / **1267 PASS** / cov **86.43%** (+0.24%p). ADR § 46 신규 (9 sub-§). `8f6b453`
- **Phase F-3 — R2 inherit 7건 정리** (5-14, ted-run) — § 46.8 7건 전부 해소 + § 47 신규. 사용자 8 확정 D-1~D-8 (권고 default 일괄 채택). `SkipReason` StrEnum 신규 모듈 (`app/application/dto/_shared.py`) + 양쪽 DTO `errors_above_threshold: tuple[str, ...]` 통일 + `_empty_bulk_result` private helper (short + lending, keyword-only) + 단건 UseCase `SentinelStockCodeError` catch (D-7 defense-in-depth, 두 단건 UseCase docstring 명시) + `skipped_count` property 양쪽 (비대칭 흡수 — § 46.9 보존) + `backfill_short.py:189` label `total_skipped:` 일치 + DTO `__all__` SkipReason re-export + dead path `# pragma: no cover` 마커 3 사이트. R1 HIGH 2 + MEDIUM 3 + LOW 2 → fix 6건 (H-1 lending else commit 제거 + M-1 dead path 마커 + M-2 defense docstring + M-3 property docstring + L-1 keyword-only + L-3 F401 해소) → R2 ruff auto-fix 3건 → 양쪽 합의 PASS / inherit 5건 (§ 47.8 — router DTO breaking consumer 식별 / coverage 설정 부재 / SkipReason 위치 / lending progress log / ruff auto-fix 기록). Verification 5관문 PASS (ruff clean + mypy strict **106 files** + **1284 tests** (+17) + cov **86.56%** (+0.13%p) + 런타임 imports OK / E2E ⚪ UI 변경 0). 8 production + 4 갱신 + 3 신규 + 1 회귀 + plan doc 2 신규 = 23 파일 +2199/-205. ADR § 47 신규 (9 sub-§). `43af892`
- **Phase G — 투자자별 매매 흐름 3 endpoint 통합** (5-16, ted-run 풀 파이프라인 / **메모리 정책 `feedback_plan_doc_per_chunk` 정착 첫 chunk** — plan doc 신규 → ted-run skill 명시 호출 → 메타 4종 동시 commit). ka10058/10059/10131 통합 1 chunk. 사용자 D-1~D-17 권고 default 일괄 채택. Migration **019_investor_flow** (3 테이블 통합 + UNIQUE 3 + INDEX 8 partial `WHERE stock_id IS NOT NULL` + downgrade 가드) + 3 ORM (InvestorFlowDaily / StockInvestorBreakdown 12 net / FrgnOrgnConsecutive 15 metric) + 3 Repository (`_chunked_upsert` 200 + 도메인 조회) + KiwoomStkInfoClient 갱신 (`fetch_investor_daily_trade_stocks` ka10058 / `fetch_stock_investor_breakdown` ka10059) + `KiwoomForeignClient` 신규 (`/api/dostk/frgnistt` 첫 endpoint, `fetch_continuous` ka10131) + `_records.py` 갱신 (9 enum: InvestorType 12 / InvestorTradeType / InvestorMarketType / AmountQuantityType / StockInvestorTradeType / UnitType / ContinuousPeriodType 7 / ContinuousAmtQtyType / StockIndsType + 3 Row + 3 Response + 3 Normalized + `_to_decimal_div_100` helper for `flu_rt "+698" → 6.98`) + DTO 3 Outcome + 3 BulkResult (errors_above_threshold tuple F-3) + Service 6 UseCase (3 단건 + 3 Bulk + `_empty_bulk_result` helper + 단건 SentinelStockCodeError catch + `_persist_common` 패턴) + Router 9 endpoint (3 × sync 단건 lookup / bulk-sync active 종목 / GET top·range, `_invoke_single` × 3 G-3) + Batch 3 cron callback (20:00/20:30/21:00 KST mon-fri / `is_trading_day` 가드 KST timezone / `MISFIRE_GRACE_SECONDS=21600`) + Scheduler `_InvestorFlowScheduler` 베이스 + 3 subclass + DI 6 factory (lazy `_missing_factory` + reset_token) + main.py lifespan (6 setter + 3 scheduler instance + 6 reset, 20 state.schedulers) + Settings 6 env (3 enabled + 3 alias + fail-fast) + alias_checks 3 추가. R1 sonnet 5.8 RETRY + opus 적대적 4.5 운영 D (CRITICAL 8 + HIGH 7, 적대적 시뮬레이션 7 PASS + 1 N/A) → fix 17건 (G-1 즉시 일괄 / G-2 misfire 21600 통일 / G-3 단건 모드 분리) → R2 sonnet 9.2 PASS + opus 8.4 운영 B+ CONDITIONAL / inherit 5건 (§ 49.4 / § 49.8 — inh-1 ka10059 트랜잭션 오염 / inh-2 D-11 임계치 / inh-3 N-1 NULL distinct / inh-4 N-2 lookup miss 모니터 / inh-5 `_unwrap_client_rows`). Verification 5관문 PASS (ruff + mypy **114 files** + **1596 tests** (+172) + cov **84%** (-1.0%p, 대량 신규 dip) + scheduler smoke 20 schedulers + 3 Phase G next_run_time 2026-05-18 20:00/20:30/21:00 KST + lifespan import). 22 production (신규 16 + 갱신 6) + 14 신규 test = **~4,600 production + 4,829 test** 라인 = **backend_kiwoom 최대 chunk**. **25 endpoint 80% → 92%** 도달. ADR § 49 신규 (9 sub-§). `e8c901d`
- **Phase F-4 — 5 ranking endpoint 통합** (5-16, Agent tool — 메모리 정책 미정착 시점, 다음 chunk 부터 ted-run skill 명시 호출) — ka10027/30/31/32/23 통합 1 chunk. 사용자 D-1~D-14 일괄 + G-1/G-2/G-3 추가 (본 chunk 일괄 fix / misfire 21600 통일 / 단건 모드 분리). Migration **018_ranking_snapshot** (007 stale 정정) + ORM + Repository (`_chunked_upsert` 적용) + KiwoomRkInfoClient (5 fetch + `_paginated_fetch` 공통) + 7 enum + 5 Row + 5 Response (D-9 nested payload 23 필드) + DTO (`NormalizedRanking` / `RankingBulkResult` `int | None` sentinel) + Service (5 단건 + 5 Bulk / `_persist_common` 통합 / `_empty_bulk_result` helper) + Router (15 endpoint — 5 sync `_invoke_single` 단건 / 5 bulk-sync 매트릭스 / 5 GET snapshot) + Batch (5 cron `fire_*_sync` / `is_trading_day` 가드 / `errors_above_threshold` logger.error) + Scheduler (5 RankingScheduler 19:30/35/40/45/50 KST mon-fri, misfire 21600) + DI (10 factory + lazy `_missing_factory` 통일 + reset_token_manager 추가) + main.py lifespan (10 setter + 5 scheduler 인스턴스 + 17 state.schedulers) + Settings 10 신규 env (5 alias + 5 enabled) + .env.prod 10 env. R1 sonnet 8.0 (HIGH 2 + MED 5 + LOW 5) + opus 적대적 5.5 운영 D (CRITICAL 3 + HIGH 5 + MED 6) → fix 10건 → R2 sonnet 9.2 PASS + opus 8.6 운영 B+ CONDITIONAL / inherit 5건 (§ 48.8 — Phase E 상속 Bulk 트랜잭션 / `.env.example` / pred·trde silent ignore / strip regex / 잔여 MEDIUM 통합). Verification 5관문 PASS (ruff + mypy **103 files** + **1424 tests** (+140) + cov **85.00%** (-1.56%p, 대량 신규 코드) + 런타임 / E2E ⚪). 13 production + 4 신규 test + 11 미커밋 (Step 0a~0e) = +~570/-49 라인. **25 endpoint 60% → 80%** 도달. ADR § 48 신규 (9 sub-§). 메모리 update 2건 (추천 정책 진화 + chunk = plan doc + ted-run 명시 호출). `4fc78a5`

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
