# phase-g-investor-flow.md — Phase G 투자자별 3종 통합 chunk

> Phase G (투자자별 매매 흐름 3 endpoint) 의 _본 chunk_. ka10058 / ka10059 / ka10131 을 단일 chunk 로 통합 도입.
> 공유 인프라 (Migration 019 + 3 테이블 + `KiwoomStkInfoClient` 확장 + `KiwoomForeignClient` 신규 + 7 enum + `_strip_double_sign_int` 재사용) + 3 endpoint 단건/Bulk UseCase + scheduler 3 cron + 라우터 ~9.
> 메모리 정책 `feedback_plan_doc_per_chunk` 정착 첫 chunk — **본 plan doc 결정 게이트 사용자 확정 후 `/ted-run` skill 명시 호출**.
> reference: `endpoint-23-ka10058.md` (Phase G 통합 패턴 정의) + `endpoint-24-ka10059.md` (wide format 차이) + `endpoint-25-ka10131.md` (연속매매 차이).

---

## 1. 메타

| 항목 | 값 |
|------|-----|
| Chunk ID | Phase G |
| 선행 chunk | Phase F-4 (`4fc78a5` — 5 ranking + Migration 018 + ranking_snapshot + JSONB) |
| 후속 chunk | D-2 ka10080 (마지막 endpoint, 대용량 파티션 결정) → Phase H (통합) |
| 분류 | 도메인 확장 (3 endpoint 동시 — 1 카테고리 추가 + 1 카테고리 신규) |
| 우선순위 | P2 (백테스팅 시그널 핵심 — 외인/기관/개인 매매 흐름 + 연속매매 일수) |
| 출처 | endpoint-23-ka10058.md (reference) + 24/25 (차이점만) |
| 예상 규모 | ~1,300-1,600 production line + ~900-1,100 test line (~2,200-2,700 lines) |
| ted-run 적용 여부 | ✅ (메모리 `feedback_plan_doc_per_chunk` 정착 첫 chunk — F-4 임계 ~2,500줄 패턴 미러) |
| 25 endpoint 진행률 | 80% → **92%** (20 → 23 endpoint) |

> **chunk 분할 주의**: 본 chunk 예상 ~2,500줄 — F-4 와 동일 임계. § 9 ted-run input 직전 사용자 D-1 확정 (통합 vs 3 sub-chunk).

---

## 2. 현황 (Phase G 진입 전 상태)

### 2.1 기존 자산 (재사용)

| 자산 | 위치 | 본 chunk 활용 |
|------|------|--------------|
| `KiwoomClient` (httpx + 토큰 + tenacity + pagination) | `app/adapter/out/kiwoom/_client.py` | `KiwoomStkInfoClient` 메서드 추가 + 신규 `KiwoomForeignClient` 가 wrapping |
| `KiwoomStkInfoClient` (ka10099/100/001/101) | `app/adapter/out/kiwoom/stkinfo.py` | ka10058 + ka10059 메서드 추가 |
| `StockRepository.find_by_codes` | `app/adapter/out/persistence/repositories/stock.py` | stk_cd → stock_id lookup batch (ka10058/131 — ranking 응답 / ka10059 — 단일 종목) |
| `strip_kiwoom_suffix` (`_NX` suffix) | `app/adapter/out/kiwoom/_codes.py` | NXT 코드 → KRX 마스터 lookup |
| **`_strip_double_sign_int`** (Phase C ka10086) | `app/adapter/out/kiwoom/_records.py` | ka10058 / 59 / 131 모두 부호 + 이중 부호 (`--714`) 정규화 — 3 endpoint × 12+ 필드 재사용 |
| `_parse_yyyymmdd` / `_to_int` / `_to_decimal` | `app/adapter/out/kiwoom/stkinfo.py` | 정규화 공통 |
| `SkipReason` StrEnum + `errors_above_threshold: tuple[str, ...]` (F-3 정착) | `app/application/dto/_shared.py` | 3 BulkResult tuple 패턴 + 단건 sentinel catch |
| `_empty_bulk_result` helper (F-3 정착) | service helper | 3 endpoint BulkUseCase 동일 패턴 |
| `RankingExchangeType` enum (F-4) | `_records.py` | 3 endpoint stex_tp 공용 (1/2/3) |
| `SentinelStockCodeError` (F-3) | adapter | 단건 UseCase catch (defense-in-depth) |
| `RankingSnapshotRepository.chunked_upsert` 패턴 (F-4 C-3) | repository | ka10059 BATCH=50 / ka10058·131 ~200 row 충분히 가능 |
| `_invoke_single` helper 패턴 (F-4 G-3) | router | 3 endpoint × (단건 sync + bulk-sync) 분리 |
| `lifespan` factory setter (F-4 C-1) | `app/main.py` | 6 factory setter (3 단건 + 3 Bulk) + 3 scheduler instance |
| Settings env alias + enabled (F-4 C-2) | `config/settings.py` | 6 alias env (`KIWOOM_INVESTOR_*`) |
| APScheduler cron + `misfire_grace_time=21600` (F-4 G-2 통일) | `app/scheduler.py` | 3 ranking 후속 cron 추가 |

### 2.2 endpoint-23~25 reference 요약

endpoint-23 § 11.4 의 3 endpoint 비교 표 재인용 + 본 chunk 핵심 차이:

| 항목 | ka10058 (long ranking) | ka10059 (종목 wide) | ka10131 (연속매매 ranking) |
|------|---|---|---|
| URL | `/api/dostk/stkinfo` | 동일 | **`/api/dostk/frgnistt` (신규 카테고리)** |
| Body 필드 수 | 6 | 5 | 8 |
| Body 핵심 식별자 | `(invsr_tp, trde_tp, mrkt_tp, stex_tp)` | `(stk_cd, dt, amt_qty_tp, trde_tp, unit_tp)` | `(dt period, mrkt_tp, stk_inds_tp, amt_qty_tp, stex_tp)` |
| 응답 list 키 | `invsr_daly_trde_stk` | `stk_invsr_orgn` | `orgn_frgnr_cont_trde_prst` |
| 응답 필드 수 | 11 | **20** (12 투자자 wide) | **19** (기관/외국인/합계 × 5 metrics) |
| 응답 정렬 | netslmt_qty | (단일 row) | rank |
| `primary_metric` | `netslmt_qty` (부호 — trde_tp 의존) | (wide — 단일 메트릭 없음) | `total_cont_days` |
| 영속화 테이블 | `investor_flow_daily` | `stock_investor_breakdown` | `frgn_orgn_consecutive` |
| 호출 단위 | (investor, trade, market) → 종목 list | (1 stock, 1 date) → 1 wide row | (period, market) → 종목 list |
| 호출 수 / 일 (default) | 2 mkt × 3 inv × 2 trde = **12** | active 종목 **~3,000** (1조합) | 2 mkt × 2 amt_qty = **4** |
| 우선순위 | P2 | P2 | P2 |

### 2.3 F-4 정착 패턴 (본 chunk 가 적용)

- **G-1 (즉시 일괄 fix)**: 본 chunk 의 R1 → R2 fix 도 _분리 chunk 미루지 않고 즉시 일괄_
- **G-2 (misfire 21600 통일)**: 신규 3 cron 모두 `misfire_grace_time=21600`
- **G-3 (단건 모드 분리)**: 3 endpoint 각각 `_invoke_single` helper + 라우터 sync (body 1×1 호출) / bulk-sync (전체 매트릭스) 분리
- **C-1 (lifespan factory setter)**: 3 단건 + 3 Bulk = 6 setter + 3 scheduler instance + reset
- **C-2 (Settings env alias + enabled)**: 6 env (`KIWOOM_INVESTOR_DAILY_*` / `KIWOOM_STOCK_INVESTOR_*` / `KIWOOM_FRGN_ORGN_*`) + fail-fast
- **C-3 (chunked_upsert)**: ka10059 의 BATCH_SIZE=50 (3000 호출 / 60분 — au10001 24h 만료 위험과 함께 검토)
- **F-3 (SkipReason / tuple errors_above_threshold / empty helper / 단건 sentinel catch)**: 3 endpoint 모두 적용

---

## 3. 범위 외 (out of scope)

| 항목 | 이유 | 후속 chunk |
|------|------|-----------|
| D-2 ka10080 분봉 (마지막 endpoint) | 대용량 파티션 결정 동반 — 별도 chunk | D-2 |
| Phase H (백테스팅 view + 데이터 품질 + Grafana) | Phase G 완료 후 derived feature — `phase-h-integration.md` 작성됨 | Phase H |
| **inh-1 Bulk 트랜잭션 오염 fix (Phase E 상속)** | _Phase G dry-run 후_ 별도 chunk — D-12 결정 게이트로 본 chunk 내 도입 vs 분리 선택 | inh-1 (별도 chunk) |
| ka10059 의 백필 (3년 / 1년) | 운영 default = forward-only (today only) — 백필 정책 별도 결정 | Phase H |
| ka10131 의 `stk_inds_tp=1` (업종) | D-14 결정 게이트 — 본 chunk skip 권고 (운영 1주 검증 후) | Phase F-5 (선택) |
| wide ↔ long 변환 view (ka10059) | derived feature — Phase H typed view | Phase H |
| ka10058 vs ka10059 vs ka10086 정합성 리포트 | 데이터 품질 chunk — Phase H | Phase H |
| 외인 + 기관 동시 연속매수 시그널 (ka10131 derived) | 시그널 derived feature — Phase H | Phase H |
| `netslmt_qty` 부호 의미 / `flu_rt` 표기 (`+698`=6.98%) / `amt_qty_tp` 반대 의미 / `tot_cont_days` 합산 정합성 — 운영 검증 항목 | 응답 schema 운영 검증 — 코드는 raw 그대로 적재 + master.md § 12 사후 기록 | 운영 1주 후 |

---

## 4. 확정 결정 (작성 시점 미확정 — § 9 ted-run input 직전 사용자 확정 필요)

| # | 결정 항목 | 옵션 | 권고 default |
|---|----------|------|--------------|
| **D-1** | 3 endpoint chunk 분할 vs 통합 | (a) 통합 1 chunk (현 plan) (b) G-1 (인프라 + ka10058) / G-2 (ka10059 wide) / G-3 (ka10131 연속) 3 sub-chunk (c) G-1 (ka10058 + 10131 ranking) / G-2 (ka10059 wide) 2 sub-chunk | **(a)** — F-4 동일 임계 (~2,500줄) 패턴 미러. 3 endpoint 공유 자산 많음 (`_strip_double_sign_int` / SkipReason / Settings env) — 통합 시 중복 작업 회피 |
| **D-2** | Migration 019 한 번에 3 테이블 vs 분리 | (a) 단일 Migration 019 + 3 테이블 (현 plan) (b) 019 (investor_flow_daily) / 020 (stock_investor_breakdown) / 021 (frgn_orgn_consecutive) | **(a)** — 같은 Phase chunk, 트랜잭션 단위 일치. Migration 018 단일 테이블 패턴 일관 |
| **D-3** | ka10058 운영 default `invsr_tp` | (a) 3종 (INDIVIDUAL/FOREIGN/INSTITUTION_TOTAL) — 현 plan (b) 12종 모두 (c) 2종 (FOREIGN/INSTITUTION_TOTAL — 백테 핵심) | **(a)** — endpoint-23 § 6.4 default. 12종 전체는 운영 1주 후 row 수 분포 보고 추가 |
| **D-4** | ka10058 운영 default `trde_tp` | (a) 2종 모두 (NET_BUY + NET_SELL) — 현 plan (b) NET_BUY 만 | **(a)** — 매수/매도 비대칭 시그널 추출 모두 필요 |
| **D-5** | 3 endpoint 운영 default `mrkt_tp` | (a) 2종 (KOSPI 001 + KOSDAQ 101) — 현 plan (b) KOSPI 만 (c) KOSPI+KOSDAQ+코넥스 (지원 시) | **(a)** — ka10058 / ka10131 모두 `001/101` 만 (전체 `000` 불가). ka10059 는 종목 단위라 mrkt_tp 없음 |
| **D-6** | 3 endpoint 운영 default `stex_tp` | (a) 통합 (3) 만 — 현 plan (b) `{1, 2, 3}` 모두 (KRX/NXT/통합) | **(a)** — F-4 D-4 동일. NXT 분리는 운영 1주 검증 후 |
| **D-7** | ka10059 운영 default scope (3000 호출 부담) | (a) **active 종목 전체 ~3,000** (현 plan) (b) 시가총액 상위 N (예: 500) (c) `nxt_enable=true` 만 (d) backfill_priority = 'critical' 만 | **(a)** — endpoint-24 § 6.3 row 수 추정. 단, **D-12 / D-13 의 트랜잭션·토큰 만료 위험과 결합 결정 필요** |
| **D-8** | ka10059 운영 default `(amt_qty_tp, trde_tp, unit_tp)` 조합 | (a) **1조합 (QUANTITY / NET_BUY / THOUSAND_SHARES)** — 현 plan (b) (QUANTITY + AMOUNT) × NET_BUY × THOUSAND_SHARES = 2조합 (c) 12조합 (2 × 3 × 2) 전체 | **(a)** — 3000 종목 × 12조합 = 36,000 호출/일 → 약 36분 (RPS 4) 불가능. 1조합으로 시작 |
| **D-9** | ka10131 운영 default `period_type` | (a) **LATEST 만** — 현 plan (b) LATEST + DAYS_5 (c) LATEST + DAYS_5 + DAYS_20 | **(a)** — endpoint-25 § 11.1. 추가 period 는 운영 1주 검증 후 |
| **D-10** | ka10131 운영 default `amt_qty_tp` | (a) **2종 모두 (AMOUNT 0 + QUANTITY 1)** — 현 plan (b) AMOUNT 만 | **(a)** — endpoint-25 § 11.1 #2. `amt_qty_tp` 의미 ka10059 와 _반대_ (★ 운영 검증 1순위) — 단위 mismatch 위험 명시 |
| **D-11** | 3 cron 발화 시점 | (a) **F-4 chain 직후 20:00/20:30/21:00** (ka10058 → ka10059 → ka10131) — 현 plan (b) 모두 20:00 발화 + asyncio.gather (c) F-4 chain 안에 통합 (19:55 / 20:00 / 20:05 — RPS 4 충돌 위험) | **(a)** — F-4 19:50 (ka10023) 직후 10분 gap. ka10059 의 60분 sync 마지막에 다음 ka10131 cron 발화 timing 검토 |
| **D-12** | inh-1 Bulk 트랜잭션 오염 (Phase E 상속) — 본 chunk vs 별도 chunk | (a) **본 chunk dry-run 후 별도 chunk** — 현 plan (b) 본 chunk 내 SAVEPOINT 도입 (단건당 별도 세션) (c) 본 chunk 내 단건당 별도 세션만 (SAVEPOINT 미도입) | **(a)** — Phase E 부터 inherit. 본 chunk 신규 결함 아님 + ka10059 의 3000 호출 / 60분 sync 의 실제 트랜잭션 오염 발화율 측정 후 정책 결정. _단, ka10059 의 BATCH_SIZE=50 commit 으로 부분 mitigate_ |
| **D-13** | ka10059 의 3000 종목 60분 실행 — au10001 24h 만료 대응 | (a) **기존 토큰 매니저 신뢰** (TokenManager 자동 refresh) — 현 plan (b) 호출 직전 명시 refresh helper 추가 (c) 60분 cron 전 sync refresh job 별도 add_job | **(a)** — F-4 ranking_jobs.py 동일 패턴. 토큰 매니저 24h 만료 자동 처리 검증됨. 단, 운영 1주 모니터 후 명시 refresh 필요시 (b) 도입 |
| **D-14** | ka10131 의 `stk_inds_tp=1` (업종) — 본 chunk 도입 vs skip | (a) **본 chunk skip** (STOCK 만, 현 plan) (b) STOCK + INDUSTRY 도입 — stock_id NULL + stock_code_raw 에 업종코드 보관 | **(a)** — 응답 schema 동일성 _운영 미검증_. INDUSTRY 는 Phase F-5 또는 별도 chunk |
| **D-15** | `amt_qty_tp` 의미 반대 (ka10059 vs ka10131) | (a) **별도 enum 분리** (현 plan — `AmountQuantityType` 1=금액/2=수량 vs `ContinuousAmtQtyType` 0=금액/1=수량) (b) 통일 helper (`map_amt_qty_to_kiwoom(endpoint, value)` 함수) | **(a)** — 키움 API 일관성 깨짐 그대로 노출. enum 분리가 _컴파일 타임 가드_ — 실수 차단 |
| **D-16** | ka10059 의 응답 row `dt` (단일 일자 가정) vs 다중 일자 페이지네이션 | (a) **단일 row 가정** (현 plan — 응답 단일 일자) (b) cont-yn=Y 응답 발생 시 max_pages=5 모두 적재 + `trading_date` 분리 | **(a) + 가드** — 응답 단일 row 기대지만 max_pages=5 페이지네이션 유지 (방어). 운영 모니터로 cont-yn 발화 빈도 측정 |
| **D-17** | ka10058 / ka10131 의 `RankingMarketType` (000/001/101 — F-4) vs `InvestorMarketType` (001/101 만) 분리 | (a) **신규 enum `InvestorMarketType`** 분리 (현 plan) (b) F-4 의 `RankingMarketType` 재사용 + Pydantic validator 로 `000` reject | **(a)** — 의미 분리 (전체 `000` 미지원). enum 분리가 타입 안전 |

> **D-1 ~ D-17 권고 default 가 모두 합의되면** § 5 변경면이 확정.

---

## 5. 변경 면 매핑 (D-1~D-17 권고 default 가정)

### 5.1 Migration (1 신규)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `migrations/versions/019_investor_flow.py` (신규) | `kiwoom.investor_flow_daily` + `kiwoom.stock_investor_breakdown` + `kiwoom.frgn_orgn_consecutive` 3 테이블 + UNIQUE 키 3개 + 8 인덱스 (date+inv / stock_id partial / total_cont_days desc / trading_date / stock_id / investor_breakdown stock+date / frgn_cons date / frgn_cons stock partial) |

### 5.2 ORM Model (3 신규)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/adapter/out/persistence/models/investor_flow_daily.py` (신규) | `InvestorFlowDaily` declarative (ka10058) |
| 2 | `app/adapter/out/persistence/models/stock_investor_breakdown.py` (신규) | `StockInvestorBreakdown` declarative (ka10059 — 12 net 컬럼) |
| 3 | `app/adapter/out/persistence/models/frgn_orgn_consecutive.py` (신규) | `FrgnOrgnConsecutive` declarative (ka10131 — 15 metric 컬럼) |

### 5.3 Repository (3 신규)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/adapter/out/persistence/repositories/investor_flow_daily.py` (신규) | `InvestorFlowDailyRepository.upsert_many` (BATCH=200 chunked) + `get_top_stocks` |
| 2 | `app/adapter/out/persistence/repositories/stock_investor_breakdown.py` (신규) | `StockInvestorBreakdownRepository.upsert_many` (BATCH=200) + `get_range` (단일 종목 기간 조회) |
| 3 | `app/adapter/out/persistence/repositories/frgn_orgn_consecutive.py` (신규) | `FrgnOrgnConsecutiveRepository.upsert_many` (BATCH=200) + `get_top_by_total_days` (시그널 핵심 — total_cont_days desc) |

### 5.4 Adapter (2 갱신 + 1 신규)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/adapter/out/kiwoom/stkinfo.py` (갱신) | `KiwoomStkInfoClient.fetch_investor_daily_trade_stocks` (ka10058) + `KiwoomStkInfoClient.fetch_stock_investor_breakdown` (ka10059) — 2 메서드 추가 (기존 클래스에 합류) |
| 2 | `app/adapter/out/kiwoom/frgnistt.py` (신규) | `KiwoomForeignClient.fetch_continuous` (ka10131) — `/api/dostk/frgnistt` 카테고리 첫 endpoint |
| 3 | `app/adapter/out/kiwoom/_records.py` (갱신) | + 7 enum (`InvestorType` 12 / `InvestorTradeType` 2 / `InvestorMarketType` 2 / `AmountQuantityType` 2 / `StockInvestorTradeType` 3 / `UnitType` 2 / `ContinuousPeriodType` 7 / `ContinuousAmtQtyType` 2 / `StockIndsType` 2) + 3 Row / 3 Response + 3 Normalized dataclass + `_to_decimal_div_100` helper (ka10059 의 `flu_rt = "+698" → 6.98`) |

### 5.5 DTO (1 신규)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/application/dto/investor_flow.py` (신규) | `InvestorIngestOutcome` + `StockInvestorBreakdownOutcome` + `FrgnOrgnConsecutiveOutcome` + 3 BulkResult (`errors_above_threshold: tuple[str, ...]` F-3 패턴) |

### 5.6 Service (1 신규)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/application/service/investor_flow_service.py` (신규) | `IngestInvestorDailyTradeUseCase` / `IngestStockInvestorBreakdownUseCase` / `IngestFrgnOrgnConsecutiveUseCase` (단건 3) + 각 Bulk 3 = 6 UseCase. `_empty_bulk_result` (F-3) + 단건 sentinel catch (F-3 D-7) + `_persist_common` 패턴 (F-4 sonnet H-2 합의) |

### 5.7 Router (1 신규)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/adapter/web/routers/investor_flow.py` (신규) | 3 endpoint × (POST sync 단건 / POST bulk-sync 매트릭스 / GET top) = ~9 라우터. `require_admin_key` 의존성 (POST). `_invoke_single` helper × 3 (F-4 G-3 패턴) |

### 5.8 Batch (1 신규)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/batch/investor_flow_jobs.py` (신규) | 3 cron — `fire_investor_daily_sync` (20:00) / `fire_stock_investor_breakdown_sync` (20:30, 60min grace) / `fire_frgn_orgn_continuous_sync` (21:00). KST mon-fri. `misfire_grace_time=21600` (G-2 통일) |

### 5.9 Scheduler 갱신 (1 갱신)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/scheduler.py` | 3 ranking 후속 cron import + `InvestorFlowScheduler` 또는 기존 scheduler 에 add_job 3건 |

### 5.10 DI 갱신 (1 갱신)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/adapter/web/_deps.py` | + 6 factory (3 단건 + 3 Bulk) — lazy factory `_missing_factory` 패턴 (F-4 H-2) + reset_token_manager + 3 단건 단순 factory (F-4 H-4 단건 모드 분리) |

### 5.11 App entry (1 갱신)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/main.py` | + 6 setter (3 단건 + 3 Bulk) + 3 scheduler instance + 6 reset (lifespan F-4 C-1) + router include |

### 5.12 Settings 갱신 (1 갱신)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/config/settings.py` | + 6 alias env + 6 enabled env (`KIWOOM_INVESTOR_DAILY_ENABLED` / `KIWOOM_STOCK_INVESTOR_ENABLED` / `KIWOOM_FRGN_ORGN_ENABLED`) + fail-fast (F-4 C-2) + `.env.prod` 6 env |

### 5.13 테스트 신규 (~12 파일)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `tests/test_migration_019.py` (신규) | testcontainers PG16 — upgrade head + 3 테이블 + UNIQUE/INDEX 검증 (~10 케이스) |
| 2 | `tests/test_records_investor.py` (신규) | Pydantic Row 3종 — `_strip_double_sign_int` / `_to_decimal_div_100` / NXT `_NX` strip / 부호 (`+/-`) 처리 + 7 enum 검증 (~25 케이스) |
| 3 | `tests/test_stkinfo_investor_client.py` (신규) | ka10058 + ka10059 — 정상 / 페이지네이션 / 빈 응답 / sentinel / business error / `amt_qty_tp` 분기 (~30 케이스) |
| 4 | `tests/test_frgnistt_client.py` (신규) | ka10131 — 정상 / period_type 7종 / `amt_qty_tp` 반대 의미 / `tot_cont_days` 합산 raw 적재 / `netslmt_tp=2` 고정 (~20 케이스) |
| 5 | `tests/test_investor_flow_daily_repository.py` (신규) | upsert INSERT/UPDATE 멱등성 / `(investor, trade, market)` 분리 / lookup miss NULL / `get_top_stocks` 정렬 (~12 케이스) |
| 6 | `tests/test_stock_investor_breakdown_repository.py` (신규) | upsert + 12 net 컬럼 / `(amt_qty, trade, unit, exchange)` 분리 UNIQUE / KRX+NXT 분리 / `get_range` (~10 케이스) |
| 7 | `tests/test_frgn_orgn_consecutive_repository.py` (신규) | upsert + 15 metric 컬럼 / `(period, market, amt_qty, stk_inds, exchange, rank)` 분리 UNIQUE / `get_top_by_total_days` desc + nulls_last (~12 케이스) |
| 8 | `tests/test_investor_flow_dto.py` (신규) | 3 Outcome + 3 BulkResult `errors_above_threshold` tuple 회귀 + `skipped_count` property (~8 케이스) |
| 9 | `tests/test_ingest_investor_daily_use_case.py` (신규) | ka10058 단건 + bulk (12 호출 매트릭스) + 단건 sentinel catch + lookup miss → stock_id=NULL 적재 (~15 케이스) |
| 10 | `tests/test_ingest_stock_investor_breakdown_use_case.py` (신규) | ka10059 단건 + bulk (3000 종목 / BATCH=50) + `flu_rt = "+698" → 6.98` + `_strip_double_sign_int` 12 카테고리 (~12 케이스) |
| 11 | `tests/test_ingest_frgn_orgn_continuous_use_case.py` (신규) | ka10131 단건 + bulk (4 호출) + `period_type=PERIOD` strt/end + `amt_qty_tp` 반대 의미 (~12 케이스) |
| 12 | `tests/test_investor_flow_router.py` (신규) | 9 endpoint — admin key 회귀 + Pydantic validation + `_invoke_single` 단건 모드 (~12 케이스) |
| 13 | `tests/test_investor_flow_jobs.py` (신규) | 3 cron — fire 시 BulkUseCase 호출 / misfire 21600 / errors_above_threshold tuple 알람 / 20:00/20:30/21:00 시간 (~10 케이스) |
| 14 | `tests/integration/test_investor_flow_e2e.py` (신규 — testcontainers PG16) | INSERT 50 row + UPDATE 멱등 / 3 테이블 cross-query / lookup miss NULL / Migration upgrade/downgrade (~10 케이스) |

추정 변경 라인:
- Migration + 3 ORM + 3 Repository = ~450줄
- Adapter (stkinfo 메서드 2 + frgnistt 신규 + _records 갱신) = ~500줄
- DTO + Service (3 단건 + 3 bulk) = ~600줄
- Router + Batch + DI + Settings + main = ~450줄
- 테스트 ~14 파일 = ~900-1,100줄

⇒ 총 ~2,400-2,700줄 (F-4 와 동일 임계 — _D-1 결정 게이트 통합 vs 분할 사용자 확정 필수_)

> _대안 D-1 (b)_ 3 sub-chunk 분할 시:
> - G-1: 인프라 + ka10058 (Migration + 1 테이블 + investor_flow_daily 단건/Bulk) (~1,100줄)
> - G-2: ka10059 wide (1 테이블 + 12 net 컬럼 + 3000 종목 bulk) (~900줄)
> - G-3: ka10131 연속매매 (1 테이블 + KiwoomForeignClient 신규 + 15 metric) (~700줄)

---

## 6. 적대적 self-check (보안 / 동시성 / 데이터 정합)

### 6.1 보안

- 9 라우터 POST 모두 `require_admin_key` 의존성 — admin only ⇒ ✅
- `request_filters` JSONB 보관 — 호출자 인증 정보 미포함 ⇒ ✅ (Phase G 는 JSONB payload 없음 — 3 테이블 모두 typed 컬럼)
- structlog 자동 마스킹 — appkey / secretkey / authorization / token ⇒ ✅
- ka10059 의 stock_code path parameter — `stk_cd` Length=6 가드 + `strip_kiwoom_suffix` ⇒ ✅
- ka10059 의 stock 마스터 의존 — `stock_id NOT NULL FOREIGN KEY` 인지 vs `stock_id BIGINT REFERENCES kiwoom.stock(id) ON DELETE CASCADE` ⇒ NXT 응답 시 stock 마스터 누락 가능성 → CASCADE 아닌 SET NULL (lookup miss 정책 통일)

### 6.2 동시성 / 운영

- 3 cron chain (20:00 / 20:30 / 21:00) — F-4 19:50 (ka10023) 직후 10분 gap. **확인 필요**: ka10059 의 60분 sync 가 21:00 (ka10131) cron 시점 도달 시 충돌 가능 → ka10131 cron 시점을 22:00 으로 옮길지 D-11 결정 시점에 사용자 확인
- 3 BulkUseCase 의 호출 수 — ka10058 12 / ka10059 3000 / ka10131 4. ka10059 가 Phase G 최대 부담 — `asyncio.gather` 아닌 sequential (BATCH=50 commit / RPS 4 / 토큰 만료 위험 → D-13)
- ka10058 / ka10131 의 BulkResult tuple `errors_above_threshold` 임계치 — 운영 1주 모니터 후 도입 (F-4 D-11 패턴 미러)
- ka10059 의 inh-1 트랜잭션 오염 (Phase E 상속) — D-12 결정. _현 plan = 본 chunk dry-run 후 별도 chunk_. 단, BATCH=50 commit 으로 부분 mitigate
- 단건 UseCase sentinel catch (F-3 D-7) — 3 endpoint 모두 동일 패턴
- misfire_grace_time=21600 — G-2 통일

### 6.3 데이터 정합

- 3 테이블 UNIQUE 키 각각 6/6/7 컬럼 — 멱등성 보장
- NXT `_NX` suffix — `stock_code_raw` 보존 + stock_id lookup 은 strip 후
  - ka10131 의 stk_cd Length=6 명시 — `_NX` 미지원 가능성 → 운영 검증 항목
  - ka10059 의 stk_cd Length=20 — `_NX` 지원
- lookup miss → stock_id=NULL (F-4 D-8 패턴 미러)
- ka10058 의 `netslmt_qty` 부호 의미 (trde_tp 따라) — raw 그대로 적재. 정합성은 운영 master.md § 12 기록
- ka10059 의 `flu_rt = "+698" → 6.98` — `_to_decimal_div_100` helper 신규
- ka10059 의 `orgn = 12 sub-카테고리 합` 정합성 — raw 적재 (정합성 check 안 함)
- ka10131 의 `tot_cont_days = orgn + frgnr` 정합성 — raw 적재 (운영 검증)
- ka10131 의 `amt_qty_tp` 의미 _ka10059 와 반대_ (★ 위험 1순위) — enum 분리 (D-15 a)
- 이중 부호 (`--714`) — `_strip_double_sign_int` 재사용 (Phase C ka10086 검증됨)

### 6.4 3 endpoint 통합 1 chunk 의 위험

- chunk 크기 ~2,500줄 — F-4 동일 임계. _ted-run 입력 시점에 사용자 재확인 (D-1)_
- 3 endpoint 의 응답 schema 가 _운영 검증 안 됨_ — Excel 명세와 실제 응답 차이 발생 시 1 chunk 안에서 3번 반복 수정
- 3 endpoint 동시 도입 시 verification 5관문 (ruff/mypy/pytest/cov/smoke) 모두 3배 크기 — sonnet 검토 한도 도달 가능 (`ted-run` step 2a sub-agent 분리 검토)
- ka10059 의 3000 호출 60분 sync — _운영 첫 발화_ 가 본 chunk 의 _신뢰성 1순위 검증_

### 6.5 ka10059 의 3000 종목 60분 sync 위험 (★)

| 위험 | mitigate |
|------|----------|
| au10001 24h 만료 | TokenManager 자동 refresh (D-13 a) — 운영 1주 모니터 |
| inh-1 트랜잭션 오염 (Phase E 상속) | BATCH=50 commit + 단건당 별도 세션 (D-12 b) 또는 SAVEPOINT (D-12 c) |
| RPS 4 + 250ms = 188초 (이론) vs 실측 30~60분 | 30~60분 grace + max_instances=1 (cron 겹침 방지) |
| ka10131 cron (21:00) 와 시간 충돌 | D-11 시점에 ka10131 cron 시점 22:00 으로 이동 검토 |
| stock 마스터 누락 (NXT 신규 종목) | stock_id=NULL + stock_code_raw 보관 + lookup miss 비율 모니터 (F-4 D-8 패턴) |

### 6.6 운영 검증 의존 (DoD § 10.3 검증 후 결정)

- ka10058: `netslmt_qty` 부호 의미 (trde_tp=1 응답 시 양수 절댓값 vs 음수)
- ka10058: 이중 부호 (`--335`) 발생 빈도
- ka10058: `prsm_avg_pric` 산출 방법
- ka10058: 12 invsr_tp 별 응답 row 수 분포 (소형 카테고리 row 적을 가능성)
- ka10059: `flu_rt` "우측 2자리 소수점" 가정 (`+698` = +6.98%)
- ka10059: `orgn = 12 sub-카테고리 합` 정합성 (Excel 예시 1 차이)
- ka10059: `natfor` (내외국인) 의미
- ka10059: `amt_qty_tp=1` (금액) 시 단위 (백만원 vs 원)
- ka10059: 페이지네이션 발생 빈도
- ka10131: `amt_qty_tp` 의미 (0=금액, 1=수량) 확정 — ka10059 와 반대
- ka10131: `tot_cont_netprps_dys = orgn + frgnr` 정합성
- ka10131: `period_type` 별 응답 row 수
- ka10131: 응답 stk_cd `_NX` 보존 여부 (Length=6 명시)
- 3 cron 첫 발화 (5-18 이후 평일 20:00/20:30/21:00)

---

## 7. DoD (Definition of Done)

### 7.1 코드 (~20 파일 — 신규 17 / 갱신 3)

- [ ] Migration 019 — 3 테이블 + UNIQUE/INDEX 8개
- [ ] 3 ORM Model
- [ ] 3 Repository — `upsert_many` + 도메인 조회 메서드
- [ ] `KiwoomStkInfoClient` 갱신 — `fetch_investor_daily_trade_stocks` + `fetch_stock_investor_breakdown`
- [ ] `KiwoomForeignClient` 신규 — `fetch_continuous`
- [ ] `_records.py` 갱신 — 9 enum + 3 Row/Response + 3 Normalized + `_to_decimal_div_100`
- [ ] `investor_flow.py` DTO — 3 Outcome + 3 BulkResult (F-3 tuple)
- [ ] `investor_flow_service.py` — 3 단건 + 3 Bulk UseCase (F-3 helper + 단건 catch)
- [ ] `investor_flow.py` Router — 9 endpoint (3 × 3) + `_invoke_single` helper × 3 (G-3)
- [ ] `investor_flow_jobs.py` — 3 cron (20:00 / 20:30 / 21:00)
- [ ] `scheduler.py` 갱신 — 3 add_job (misfire 21600 G-2)
- [ ] `_deps.py` 갱신 — 6 factory (3 단건 + 3 Bulk) — lazy + reset_token (F-4 H-1/H-2)
- [ ] `main.py` 갱신 — 6 setter + 3 scheduler instance + 6 reset (lifespan F-4 C-1)
- [ ] `settings.py` 갱신 + `.env.prod` 6 alias env + 3 enabled (F-4 C-2)
- [ ] **Migration 운영 적용 dry-run** — kiwoom-db `alembic upgrade head` smoke

### 7.2 테스트

- [ ] Unit ~14 파일 / ~180 케이스 PASS
- [ ] Integration (testcontainers PG16) e2e PASS — 3 테이블 cross-query + Migration upgrade/downgrade
- [ ] coverage ≥ 83% baseline (F-4 = 85.00%, 대량 신규 코드라 dip 가능, 84-85% 목표)
- [ ] ruff clean
- [ ] mypy --strict 신규 ~20 파일 Success (전체 ~120 files)
- [ ] pytest 전체 ~1,580-1,610 케이스 PASS (F-4 1424 + ~160-180)

### 7.3 운영 검증 (5-18 이후 평일)

- [ ] **첫 cron 발화 (20:00 ka10058)** — 응답 row 수 / lookup miss 비율 / `netslmt_qty` 부호 의미 / 이중 부호 빈도
- [ ] **첫 cron 발화 (20:30 ka10059)** — 3000 호출 / 60분 sync 완주 / 토큰 만료 발화 0 / inh-1 트랜잭션 오염 발화 빈도 / `flu_rt = "+698" → 6.98` 정규화 검증 / `orgn` 합산 정합성
- [ ] **첫 cron 발화 (21:00 ka10131)** — `amt_qty_tp` 반대 의미 / `tot_cont_days` 합산 정합성 / `_NX` 미지원 검증 / period_type=LATEST 응답
- [ ] 3 endpoint `errors_above_threshold` 발화 0 (baseline 없음 — 운영 1주 후 임계치)
- [ ] ka10059 의 60분 sync 가 21:00 cron 충돌 없는지 확인 (D-11 시점 ka10131 cron 22:00 이동 여부 결정)

### 7.4 문서

- [ ] CHANGELOG: `feat(kiwoom): Phase G — 투자자별 3 endpoint 통합 (ka10058/10059/10131) + Migration 019 + 3 테이블 + KiwoomForeignClient 신규`
- [ ] ADR § 49 신규 — Phase G 결정 D-1~D-17 + 운영 검증 결과 + inh-1 dry-run 결과
- [ ] STATUS.md § 0 (80% → **92%**) + § 2 카탈로그 3종 완료 + § 5 다음 chunk (D-2 ka10080 → Phase H) + § 6 누적 chunk +1
- [ ] HANDOFF.md rewrite — Phase G 완료 + 운영 검증 follow-up + 다음 chunk = D-2 / Phase H
- [ ] `master.md § 12` 결정 기록 — `netslmt_qty` 부호 / `flu_rt` 표기 / `amt_qty_tp` 반대 의미 / `tot_cont_days` 합산 / `_NX` Length=6 검증

---

## 8. 다음 chunk

| 후보 | 시점 | 비고 |
|------|------|------|
| **D-2 ka10080 분봉 (마지막 endpoint)** | Phase G 완료 직후 | 대용량 파티션 결정 동반 — 25 endpoint 100% 도달 |
| **inh-1 Bulk 트랜잭션 오염 fix (Phase E/G 상속)** | Phase G dry-run 후 (ka10059 60분 sync 실측 후) | SAVEPOINT 또는 단건당 별도 세션 (D-12 결정 반영) |
| **Phase F-5 (선택)** — ka10131 `stk_inds_tp=1` 업종 / 다중 시점 sync / 임계치 도입 | Phase G 운영 1주 후 | D-14 (b) 도입 / D-9 (b) DAYS_5 추가 / lookup miss alert |
| **Phase H — 통합** (백테 view + 데이터 품질 + README/SPEC, _Grafana 제외_) | 25 endpoint 100% 도달 후 | plan doc `phase-h-integration.md` 작성됨 |
| (선택) **Phase H' — Grafana 대시보드** | 사용자 마지막 chunk | view + alert 위에 시각화 |

---

## 9. ted-run 풀 파이프라인 input

```yaml
chunk: Phase G
title: 투자자별 3 endpoint 통합 (ka10058/10059/10131) + Migration 019 + 3 테이블 + KiwoomForeignClient 신규
선행: Phase F-4 (4fc78a5 — 5 ranking + Migration 018 + ranking_snapshot + JSONB)
plan_doc: src/backend_kiwoom/docs/plans/phase-g-investor-flow.md
reference: src/backend_kiwoom/docs/plans/endpoint-23-ka10058.md (통합 패턴) + 24/25 (차이점)

input:
  결정_사용자_확정_17건:
    D-1: 3 endpoint 통합 1 chunk (옵션 A) — chunk 크기 ~2,500줄 임계 검토
    D-2: Migration 019 단일 + 3 테이블
    D-3: ka10058 운영 default invsr_tp = {INDIVIDUAL, FOREIGN, INSTITUTION_TOTAL}
    D-4: ka10058 운영 default trde_tp = {NET_BUY, NET_SELL}
    D-5: 운영 default mrkt_tp = {001, 101}
    D-6: 운영 default stex_tp = 3 (통합)
    D-7: ka10059 운영 default scope = active 종목 ~3,000 (단, D-12/D-13 위험 명시)
    D-8: ka10059 운영 default = 1조합 (QUANTITY / NET_BUY / THOUSAND_SHARES)
    D-9: ka10131 운영 default period_type = LATEST 만
    D-10: ka10131 운영 default amt_qty_tp = 둘 (AMOUNT + QUANTITY)
    D-11: cron 20:00 / 20:30 / 21:00 KST mon-fri (F-4 19:50 + 10분 gap chain)
    D-12: inh-1 Bulk 트랜잭션 오염 — 본 chunk dry-run 후 별도 chunk
    D-13: ka10059 토큰 만료 — 기존 TokenManager 자동 refresh 신뢰
    D-14: ka10131 stk_inds_tp=1 (업종) — 본 chunk skip
    D-15: amt_qty_tp 반대 의미 — 별도 enum 분리
    D-16: ka10059 응답 단일 row 가정 + max_pages=5 가드
    D-17: InvestorMarketType (001/101) 신규 enum 분리 (vs F-4 RankingMarketType 재사용)
  변경면:
    Migration: 019 신규 (3 테이블)
    ORM/Repository: 3 + 3 신규
    Adapter: stkinfo 갱신 (2 메서드) + frgnistt 신규 + _records 갱신 (9 enum + 3 Row/Resp + 3 Normalized + _to_decimal_div_100)
    DTO: investor_flow.py 신규 (3 Outcome + 3 BulkResult tuple)
    Service: investor_flow_service.py 신규 (3 단건 + 3 bulk + F-3 helper + 단건 catch + _persist_common)
    Router: investor_flow.py 신규 (9 endpoint + _invoke_single × 3)
    Batch: investor_flow_jobs.py 신규 (3 cron) + scheduler.py 갱신
    DI: _deps.py 갱신 (6 factory + lazy + reset_token)
    Settings: settings.py 갱신 (6 alias + 3 enabled + fail-fast) + .env.prod 6 env
    App entry: main.py 갱신 (6 setter + 3 scheduler instance + 6 reset)
    Test: ~14 신규

verification:
  - alembic upgrade head smoke (kiwoom-db)
  - ruff clean
  - mypy --strict ~120 files Success
  - pytest 전체 ~1,580-1,610 PASS
  - coverage ≥ 83% (대량 신규라 dip 허용, 84-85% 목표)
  - 3 cron 등록 확인 (`scheduler.print_jobs()`)
  - Integration e2e (testcontainers) PASS
  - Migration 019 upgrade/downgrade 회귀

scope_out:
  - D-2 ka10080 (별도 chunk)
  - inh-1 Bulk 트랜잭션 오염 fix (별도 chunk — D-12 결정)
  - Phase H (통합 view + Grafana)
  - 백필 (운영 검증 후)
  - ka10131 stk_inds_tp=1 (Phase F-5 — D-14)
  - 다중 시점 sync / 임계치 도입 (Phase F-5)

postdeploy:
  - 5-18 이후 평일 20:00 / 20:30 / 21:00 첫 cron 발화 모니터
  - netslmt_qty 부호 의미 / flu_rt 표기 / amt_qty_tp 반대 의미 / tot_cont_days 합산 정합성 / _NX Length=6 검증 → master.md § 12 기록
  - ka10059 의 60분 sync 실측 → inh-1 트랜잭션 오염 발화 빈도 측정 → D-12 별도 chunk 진입
  - lookup miss 비율 1주 측정
  - 12 invsr_tp 별 응답 분포 / 12 net 카테고리 분포 / period_type 분포
```

> **chunk 크기 주의**: 본 chunk ~2,500줄 — F-4 동일 임계 (`feedback_chunk_split_for_pipelines`). ted-run 진입 직전 사용자 재확인. _D-1 (a) 통합_ 유지 vs _(b) 3 sub-chunk 분할_ 재논의.

---

## 10. 위험 / 메모 (운영 결정 사항)

### 10.1 핵심 위험 5건 (운영 1순위)

| # | 항목 | 영향 | 검증 시점 |
|---|------|------|-----------|
| 1 | **ka10059 의 3000 호출 60분 sync** | 토큰 만료 / 트랜잭션 오염 (inh-1) / cron 충돌 | 첫 발화 (5-18 이후 평일 20:30) |
| 2 | **`amt_qty_tp` 의미 반대 (ka10059 vs ka10131)** | 단위 mismatch (백만원 vs 원 vs 천원) — 잘못 사용 시 데이터 오염 | enum 분리 (D-15 a) + master.md § 12 검증 |
| 3 | **`netslmt_qty` 부호 의미 (ka10058)** | trde_tp=2 (순매수) 응답 필드명 "순매도수량" — raw 적재만 + 운영 검증 후 의미 명확화 | 첫 발화 + master.md § 12 |
| 4 | **`flu_rt = "+698" → 6.98` 표기 (ka10059)** | "우측 2자리 소수점" 가정 — 실제 응답 검증 필요 (ka10058 의 `+7.43` 와 표기 다름) | `_to_decimal_div_100` helper 검증 + 첫 발화 |
| 5 | **`_NX` Length=6 미지원 (ka10131)** | 응답 stk_cd Length=6 명시 — NXT 종목 누락 가능 | 첫 발화 (NXT 활성 종목 cross-check) |

### 10.2 알려진 위험 (운영 2순위 — DoD § 7.3 검증)

- 이중 부호 (`--714`): Phase C ka10086 패턴 — `_strip_double_sign_int` 재사용 (가설 B 정착됨)
- ka10058 의 `prsm_avg_pric` 산출 방법 (기간 평균 vs 일별 평균)
- ka10059 의 `orgn = 12 sub-카테고리 합` 정합성 (Excel 예시 60195 vs 합 60194 — 1 차이)
- ka10059 의 `natfor` (내외국인) 의미 모호
- ka10131 의 `tot_cont_days = orgn + frgnr` 정합성 (Excel 예시 2 = 1 + 1)
- ka10131 의 `period_type=PERIOD` (0) 시 strt_dt/end_dt 응답 의미 (연속 일수 산정 시점)
- ka10131 의 `netslmt_tp=2` (순매수) 고정 — 매도 ranking 미지원
- ka10058 / ka10059 / ka10086 정합성: 같은 (종목, 일자) net_individual 비교 → 데이터 품질 리포트 (Phase H)

### 10.3 디스크 사용량 추정

| 테이블 | row/일 | row/년 | 3년 백필 | 예상 디스크 |
|--------|--------|--------|----------|-------------|
| `investor_flow_daily` | 600~2,400 | 150K~600K | 450K~1.8M | ~500MB |
| `stock_investor_breakdown` | 3,000 (1조합) | 756K | 2.27M | ~700MB |
| `frgn_orgn_consecutive` | 200~800 | 50K~200K | 150K~600K | ~200MB |
| **합계** | **3,800~6,200** | **~1M** | **~4.7M** | **~1.4GB** |

→ 파티션 불필요 (5년 시점 분리 검토 — Phase H)

### 10.4 메모리 정책 정착 (본 chunk = 정착 첫 chunk)

- [x] plan doc 신규 작성 (본 문서) — `feedback_plan_doc_per_chunk` 정착
- [ ] § 4 결정 게이트 D-1~D-17 사용자 확정 (AskUserQuestion Recommended 포함 — `feedback_recommendation_over_question` 진화 정책)
- [ ] `/ted-run` skill 명시 호출 — Agent tool ad-hoc spawn 자제 (`feedback_plan_doc_per_chunk`)
- [ ] STATUS + HANDOFF + CHANGELOG + plan doc 동시 commit (메타 4종)

### 10.5 후속 chunk 시점

- **5-17 (월) 19:30 KST F-4 첫 cron 발화 검증** → 본 chunk 진입 전 effect 확인 (운영 결정 § 6.6 F-4 검증 사항 master.md 기록)
- **Phase G 진입 시점** = 사용자 결정 게이트 확정 직후 `/ted-run` 호출
- 본 chunk 완료 후 D-2 ka10080 → 25 endpoint 100% → Phase H 통합

---

_Phase G (투자자별 3종) 의 본 chunk. 3 endpoint × Migration **019** × 3 테이블 × KiwoomStkInfoClient 확장 + KiwoomForeignClient 신규 × 9 라우터 × 3 cron. 25 endpoint 진행률 80% → 92%. F-3 정착 패턴 (SkipReason Enum / tuple errors_above_threshold / empty helper / 단건 catch) + F-4 G-1/G-2/G-3 패턴 (lifespan setter / misfire 21600 / 단건 모드 분리) 위에서 작업. 메모리 정책 `feedback_plan_doc_per_chunk` 정착 첫 chunk — 본 plan doc 결정 게이트 확정 후 **`/ted-run` skill 명시 호출**. **2026-05-16: ted-run 풀 파이프라인 완료 (Step 0~5, ADR § 49). R2 PASS/CONDITIONAL — pytest 1596 PASS / mypy strict 114 / cov 84%.**_

---

## 11. Step 1 (구현) 결과 — 2026-05-16

### 11.1 실제 변경면 (Step 1 opus sub-agent)

| 영역 | 파일 | 라인 | 비고 |
|------|------|------|------|
| Migration | `migrations/versions/019_investor_flow.py` | 243 | 3 테이블 + UNIQUE 3 + INDEX 8 + COMMENT ON + downgrade row count 가드 |
| ORM × 3 | `models/{investor_flow_daily,stock_investor_breakdown,frgn_orgn_consecutive}.py` | 100/102/122 | ka10058 + ka10059 12 net + ka10131 15 metric |
| Repository × 3 | `repositories/{investor_flow_daily,stock_investor_breakdown,frgn_orgn_consecutive}.py` | 151/168/173 | `_chunked_upsert` 200 + 도메인 조회 메서드 |
| Adapter 신규 | `app/adapter/out/kiwoom/frgnistt.py` | 131 | KiwoomForeignClient — `/api/dostk/frgnistt` 첫 endpoint |
| Adapter 갱신 | `_records.py` (+515) / `stkinfo.py` (+167) | +682 | 9 enum + 3 Row/Resp/Normalized + `_to_decimal_div_100` + 2 fetch 메서드 |
| DTO | `app/application/dto/investor_flow.py` | 192 | 3 Outcome + 3 BulkResult (F-3 tuple) |
| Service | `app/application/service/investor_flow_service.py` | 699 | 6 UseCase (3 단건 + 3 Bulk) + F-3 helper + 단건 sentinel catch + `_persist_common` |
| Router | `app/adapter/web/routers/investor_flow.py` | 581 | 9 endpoint + `_invoke_single` × 3 (G-3) |
| Batch | `app/batch/investor_flow_jobs.py` | 167 | 3 cron callback + `MISFIRE_GRACE_SECONDS=21600` |
| DI 갱신 | `app/adapter/web/_deps.py` (+257) | +257 | 6 factory + lazy `_missing_factory` + reset_token |
| Settings 갱신 | `app/config/settings.py` (+44) | +44 | 6 env (3 enabled + 3 alias) |

**소계 (Step 1)**: 22 파일 (신규 16 + 갱신 6) / 약 **+3,900 라인** (production) / pytest 1596 PASS / mypy strict 114 / coverage 85%.

### 11.2 미해결 (Step 1 sub-agent 시인)

- `app/main.py` lifespan 6 factory setter + 3 scheduler instance + 6 reset 미연결
- `app/scheduler.py` 3 Scheduler class (`InvestorDailyScheduler` / `StockInvestorBreakdownScheduler` / `FrgnOrgnContinuousScheduler`) 미정의

→ Step 2 R1 이중 리뷰가 catch → Step 2 fix R1 일괄 처리.

---

## 12. Step 2 R1 이중 리뷰 — 2026-05-16

### 12.1 sonnet python-reviewer R1 (5.8/10, RETRY)

| ID | 위치 | 비고 |
|----|------|------|
| C-1 | `main.py` | 6 factory setter + 3 scheduler instance + 6 reset 모두 누락 → 라우터 503 / cron 미발화 (운영 차단) |
| C-2 | `main.py` | `investor_flow_router` include_router 미연결 → 9 endpoint 404 |
| C-3 | `main.py:alias_checks` | 3 Phase G alias 미연결 → fail-fast 무효 |
| H-1 | `investor_flow_jobs.py:107-115` | `fire_stock_investor_breakdown_sync` 의 `stock_codes=[]` / `stock_id_map={}` 하드코딩 → 운영 0 row 적재 |
| H-2 | `routers/investor_flow.py:358` | ka10059 단건 sync `stock_id=0` 하드코딩 → FK 위반 |
| H-3 | `service.py:11-13` | docstring "SAVEPOINT 사용" 주장 vs 실제 `begin_nested()` 0 — 허위 광고 |
| M-1~M-5 + L-1~L-4 | 다양 | BATCH=50 flush 미구현 / `extra="ignore"` 비일관 / 9 enum 단일 파일 / dead field 등 |

### 12.2 opus 적대적 R1 (4.5/10, 운영 D)

| ID | 위치 | 비고 |
|----|------|------|
| **C-1** | `main.py` lifespan | 6 setter + 3 scheduler 미연결 (sonnet C-1 합의) |
| **C-2** | `scheduler.py` | 3 Scheduler class 자체 미정의 — `_InvestorFlowScheduler` 베이스 누락. add_job 호출 0 |
| **C-3** | `investor_flow_jobs.py:110-112` | ka10059 cron `stock_codes=[]` — 60분 sync 호출 자체 부재 |
| **C-4** | `routers/investor_flow.py:396-397` | ka10059 bulk-sync 라우터 동일 |
| **C-5** | `routers/investor_flow.py:358` | `stock_id=0` 하드코딩 (sonnet H-2) |
| **C-6** | `service.py:11-13` | SAVEPOINT/flush 광고 vs 실제 0 (sonnet H-3) |
| **C-7** | `main.py:alias_checks` | 3 Phase G alias 누락 (sonnet C-3) |
| **C-8** | `investor_flow_jobs.py:59/103/146` | alias `"prod-main"` 하드코딩 — F-4 정착 위배 |
| H-1~H-7 | router / repository / batch | Pydantic v2 syntax / get_range stock_id=ge(1) 강제 / UseCase int 강제 / state.schedulers / `_unwrap_client_rows` 휴리스틱 / 단건 docstring "Bulk 만 권장" / is_trading_day KST timezone |
| M-1~M-6 + L-1~L-3 | 다양 | inherit 검토 |

**적대적 시뮬레이션 8 케이스**:
1. admin_api_key brute-force: PASS (`hmac.compare_digest`)
2. stk_cd path injection: PASS (body parameter, path 아님)
3. JSONB unintended payload: N/A (Phase G typed 컬럼)
4. dt SQL injection: PASS (Pydantic pattern + parameterized query)
5. 60분 sync DoS: **N/A** (C-3/C-4 로 60분 sync 호출 자체 부재 — 역설적 safety)
6. structlog 마스킹: PASS
7. partial index 위반: PASS (`WHERE stock_id IS NOT NULL`)
8. cont-yn 페이지 중복: PASS (`on_conflict_do_update`)

**양쪽 독립 리뷰 동일 결론**: 운영 통합 4축 (lifespan + scheduler + batch payload + router payload) 동시 미완성. F-4 R1 (5.5/D) 유사 패턴.

### 12.3 사용자 결정 게이트 (사전 확정 D-1~D-17)

본 chunk 의 G-1/G-2/G-3 패턴은 F-4 정착 그대로 적용 (즉시 일괄 fix / misfire 21600 통일 / 단건 모드 분리). 별도 결정 게이트 추가 없음.

---

## 13. Step 2 fix R1 결과 — 2026-05-16 (opus sub-agent)

### 13.1 fix 17건 일괄 (사용자 G-1 패턴 미러)

| ID | 변경 위치 | 라인 |
|----|----------|------|
| C-1 lifespan 통합 | `main.py:1050-1234,1245-1250,1409-1432,1473-1475,1486-1488,1503-1508` | +~280 |
| C-2 router include | `main.py:1623` | +~3 |
| C-3 alias_checks | `main.py:282-296` | +~15 |
| C-4 3 Scheduler class | `scheduler.py:1428-1567` (`_InvestorFlowScheduler` 베이스 + 3 subclass) | +~140 |
| C-5 active 종목 빌드 | `investor_flow_jobs.py:97-114,130-148` (`_build_active_stock_targets`) | +~30 |
| C-6 ka10059 router stock_codes | `routers/investor_flow.py:140-156,397-434` (body 옵션) | +~40 |
| C-7 ka10059 단건 lookup | `routers/investor_flow.py:362-380` + `service.py:367` `int \| None` | +~20 |
| C-8 SAVEPOINT/flush docstring 정정 (옵션 A) | `service.py:1-20,56-58,257-260,491-494` (D-12 별도 chunk 명시) | ±~30 |
| C-8b alias settings 읽기 | `investor_flow_jobs.py:75-77,132-134,175-177` | ±~10 |
| H-1 Pydantic v2 syntax | `routers/investor_flow.py:171-172` | ±~3 |
| H-2 get_range_optional_stock | `routers/investor_flow.py:478-503` + `repositories/stock_investor_breakdown.py:168-205` | +~30 |
| H-3 stock_id int\|None | `service.py:367` | +~2 |
| H-4 state.schedulers | C-1 안에 통합 | +~3 |
| H-5 inherit | F-3/F-4 동일 패턴 | — |
| H-6 단건 docstring | `routers/investor_flow.py:362-365` | ±~5 |
| H-7 KST timezone | `investor_flow_jobs.py:54-62` | ±~5 |
| M-1 extra="forbid" | `routers/investor_flow.py:185-186` | ±~2 |
| L-1/L-2 test assertion | `tests/test_investor_flow_jobs.py:158-160,248-253` | ±~10 |

**소계 (Step 2 fix R1)**: 17 fix / 8 파일 +~700 / -~100 = 순증 ~600 라인. 사용자 G-1 패턴 (즉시 일괄 fix).

### 13.2 검증 결과 (Step 2 fix R1 직후)

- pytest: **1596 PASS** / 0 failed (baseline 유지, 회귀 0)
- ruff: All checks passed
- mypy --strict: Success in **114 source files** (Step 1 동일)
- scheduler smoke: 20 schedulers 등록 / 3 Phase G next_run_time **2026-05-18 20:00/20:30/21:00 KST** / misfire=21600s

---

## 14. Step 2 R2 재리뷰 — 2026-05-16

### 14.1 sonnet R2 (9.2/10, PASS)

- R1 17건 fix 정확성: **17/17 YES**
- 신규 결함: **0** (관찰 O-1 결함 미달)
- 정착 패턴 미러: `_InvestorFlowScheduler` vs `_RankingScheduler` 합리적 차이 (Phase G hour 다양성 + snapshot_at 캡처) — PASS
- 합의: **PASS** (Step 3 진입 가능)

### 14.2 opus 적대적 R2 (8.4/10, 운영 B+, CONDITIONAL)

- **운영 등급**: R1 (4.5/D) → **R2 (8.4/B+)** — F-4 (5.5→8.6) 동등 향상
- R1 CRITICAL 8건: 8/8 PASS (실호출 / 시그니처 / fail-fast / 옵션 A 모두 검증 통과)
- 적대적 시뮬레이션 5 케이스: 4 PASS + 1 PARTIAL (lookup miss 단건 endpoint NULL UNIQUE distinct N-1)
- 신규 결함: 3 LOW (N-1/N-2/N-3 — 별도 chunk 후속)
- 합의: **CONDITIONAL** (Step 3 진입 + inh-1 dry-run 별도 chunk 의무)

### 14.3 R2 inherit 5건 (§ 48.8 패턴 미러)

| ID | 항목 | 후속 chunk |
|----|------|-----------|
| **inh-1** | ka10059 Bulk 트랜잭션 오염 (Phase E/F-4 상속, D-12 옵션 A) | **5-18~5-22 dry-run 후 5-25 (월) 별도 chunk** |
| **inh-2** | `errors_above_threshold` D-11 임계치 미도입 | Phase H 통합 chunk |
| **inh-3** | `stock_investor_breakdown` UNIQUE NULL distinct (N-1) | Migration 020 후속 — D-12 통합 가능 |
| **inh-4** | lookup miss 종목 list 운영 모니터 미노출 (N-2) | Phase H 데이터 품질 chunk |
| **inh-5** | `_unwrap_client_rows` 휴리스틱 → Protocol (H-5 본 chunk 신규 아님) | Phase F-5 또는 type-safety chunk |

---

## 15. Step 3 Verification + Step 5 Ship — 2026-05-16 ✅ 완료

Step 4 E2E ⚪ 자동 생략 (UI 변경 0).

### 15.1 Step 3 Verification 5관문 결과

| # | 항목 | 결과 |
|---|------|------|
| 3.1 | 빌드 (Python `py_compile` 등 lint 통합) | ✅ ruff clean |
| 3.2 | 정적 분석 | ✅ ruff All checks passed + mypy --strict **114 source files** Success |
| 3.3 | 테스트 + coverage | ✅ pytest **1596 PASS** / 0 failed (5 warnings) / coverage **84%** (F-4 85% → -1.0%p, 대량 신규 코드 dip 허용) |
| 3.4 | 보안 스캔 | ⚪ 자동 생략 (contract 분류, `--force-3-4` 없음) |
| 3.5 | 런타임 검증 | ✅ scheduler smoke 20 schedulers + 3 Phase G next_run_time 2026-05-18 20:00/20:30/21:00 KST + lifespan import 검증 (운영 환경 `MasterKeyNotConfiguredError` fail-fast 정상) |

### 15.2 Step 5 Ship 결과

- ✅ ADR § 49 신규 (9 sub-§) — D-1~D-17 + R1 CRITICAL 8 + HIGH 7 + R1 fix 17건 + R2 inherit 5건 + 운영 등급 D→B+ + ted-run 메트릭 + 메모리 정책 정착 첫 chunk
- ✅ plan doc § 11~15 누적 갱신 (본 § 15)
- ✅ STATUS.md § 0 / § 1 / § 2 (80% → **92%**) / § 4 / § 5 / § 6 갱신
- ✅ HANDOFF.md rewrite (Phase G 완료 + 5-18 dry-run + 다음 chunk = inh-1 D-12 → D-2 ka10080 → Phase H)
- ✅ CHANGELOG.md prepend (2026-05-16 Phase G)
- ✅ 한글 커밋 — `<this commit>`
- 사용자 push 명시 요청 시 push (글로벌 정책)

### 15.3 운영 발화 시점

- **5-18 (월) 20:00 KST** — Phase G 첫 cron 자연 발화 (ka10058 → 30분 후 ka10059 60분 sync → 21:00 ka10131)
- **5-18~5-22 (5거래일) dry-run** — 운영 검증 핵심 5건:
  1. ka10059 의 3000 호출 / 60분 sync 완주율
  2. inh-1 트랜잭션 오염 발화 빈도 (PG abort 로그)
  3. 토큰 만료 발화율 (D-13)
  4. `netslmt_qty` 부호 의미 / `flu_rt` "+698" → 6.98 / `amt_qty_tp` 반대 의미 / `tot_cont_days` 합산 정합성 / `_NX` Length=6
  5. 12 invsr_tp / 12 net 카테고리 / period_type 분포

### 15.4 다음 chunk

- **inh-1 (D-12) 별도 chunk**: 5-25 (월) — ka10059 dry-run 결과 후 SAVEPOINT (begin_nested) vs 단건당 별도 세션 결정
- **D-2 ka10080 분봉 (마지막 endpoint)**: inh-1 직후 — 대용량 파티션 전략 동반. 25 endpoint 100% 도달
- **Phase H — 통합** (백테 view + 데이터 품질 + README/SPEC, _Grafana 분리_): 25 endpoint 100% 도달 후
- (선택) Phase H' — Grafana 대시보드

---

_Phase G ted-run 풀 파이프라인 완료. 25 endpoint **23/25 (92%)** 도달. 본 chunk = **backend_kiwoom 최대 chunk** (~4,600 production + 4,829 test 라인). 메모리 정책 `feedback_plan_doc_per_chunk` 정착 첫 chunk — plan doc 신규 → ted-run skill 명시 호출 → 메타 4종 동시 commit. **2026-05-16: R2 PASS / CONDITIONAL — 5-18 dry-run 후 inh-1 (D-12) 별도 chunk 진입.**_
