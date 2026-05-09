# backend_kiwoom — 진척 현황 (STATUS)

> **단일 진실 출처** — 전체 작업의 어디까지 왔고 무엇이 남았는지 한 화면에서 파악
> **갱신 규칙**: chunk 완료 시 (커밋 직후) 본 문서 update. HANDOFF.md 와 함께 갱신.
> **연관**: `docs/plans/master.md` (전체 설계) / `docs/plans/endpoint-NN-*.md` (endpoint 별 상세 DoD) / `HANDOFF.md` (직전 세션) / `CHANGELOG.md` (시간순 변경)
> **마지막 갱신**: 2026-05-09 (자격증명 등록 + 종목 마스터 sync admin CLI 신규 — ka10099 진입 도구)

---

## 0. 한눈에 보기

| 항목 | 값 |
|------|-----|
| 진행 Phase | **Phase C** (OHLCV + 일별 수급, 자격증명·종목sync admin CLI 추가 — Phase C 95%) |
| 마지막 완료 chunk | **admin CLI** (register_credential.py + sync_stock_master.py — ka10099 1회 sync 진입 도구) |
| 다음 chunk | **운영 실측 측정** (사용자 수동, runbook 따라 register → sync → backfill) **또는** daily_flow 백필 / refactor R2 / ka10094 (P2) |
| 25 Endpoint 진행 | **10 / 25 완료** (40%). P0 5/5 완료. P1 6/8 완료. CLI 도구 3건 (backfill_ohlcv + register_credential + sync_stock_master) |
| 테스트 | **983 cases** (+11: register_credential 7 / sync_stock_master 4) |
| 누적 chunk | 24 commits (Phase A: 8 / Phase B: 4 / Phase C: 11 / R1: 1 / 보안 PR 2) |

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

### 2.1 완료 (10 / 25)

| # | API | 명 | Phase | chunk | 커밋 |
|---|-----|----|-------|-------|------|
| 1 | au10001 | 접근토큰 발급 | A2-α | 1R 이중 리뷰 | `115fcce` |
| 2 | au10002 | 접근토큰 폐기 | A2-β | 1R + lifespan shutdown | `0ea955c` |
| 3 | ka10099 | 종목정보 리스트 | B-α | 1R + StockMasterScheduler | `bf9956a` |
| 4 | ka10100 | 종목정보 조회 | B-β | 1R + gap-filler / lazy fetch | `abce7e0` |
| 5 | ka10001 | 주식기본정보 | B-γ-1/2 | 1R+2R + 자동화 | `a287172` / `56dbad9` |
| 6 | ka10081 | 주식일봉차트 | C-1α/β | 1R+2R / 1R + 자동화 | `a98e37b` / `993874c` |
| 7 | ka10086 | 일별주가 (수급) | C-2α/β/γ | 인프라 + 자동화 + Migration 008 (D-E 중복 DROP) | `cddd268` / `e442416` / (C-2γ) |
| 8 | ka10101 | 업종코드 리스트 | A3-α/β | KiwoomClient 공통 + sector 영속화 | `cce855c` / `6cd4371` |
| **9** | **ka10082** | **주식주봉차트** | **C-3α/β** | 인프라 + 자동화 (UseCase + Router 4 path + Scheduler 금 19:30) | `8fcabe4` / (C-3β) |
| **10** | **ka10083** | **주식월봉차트** | **C-3α/β** | ka10082 와 동일 chunk (Period dispatch) — Scheduler 매월 1일 03:00 | `8fcabe4` / (C-3β) |

### 2.2 진행중 / 다음 (0)

OHLCV 패밀리 (일/주/월) 자동화 + 백필 CLI 모두 완료. Phase C 95% 진행.
다음은 **운영 실측** (사용자 수동) / **daily_flow 백필** / **refactor R2** / **ka10094** (P2).

### 2.3 대기 (17 / 25)

P1 (1주 내):
| # | API | 명 | Phase | 비고 |
|---|-----|----|-------|------|
| 9 | ka10094 | 주식년봉차트 | C-3? | P2 (선택) |
| 14 | ka10101 | (완료, 위 #8) | — | — |
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
| C-운영실측 측정 | 사용자 수동 — runbook 따라 active 3000 KRX+NXT 3년 백필 + NUMERIC 분포 SQL | ⏳ | `backfill-measurement-results.md` 채움 + ADR § 26.5 갱신 |
| C-4 (선택) | ka10094 (년봉) — P2 | ⏳ | `endpoint-09-ka10094.md` |
| C-backfill-flow | `scripts/backfill_daily_flow.py` (ka10086) | ⏳ | OHLCV 와 구조 다름, 별도 chunk |

---

## 4. 알려진 이슈 / 운영 검증 미해결

| # | 항목 | 출처 | 결정 시점 |
|---|------|------|-----------|
| 1 | KOSCOM 공시 cross-check (가설 B 최종 확정) | dry-run § 20.4 | 향후 운영 검증 (수동 1~2건) |
| 2 | `indc_tp=1` (금액 모드) 단위 mismatch 검증 | dry-run § 20.4 | 향후 운영 검증 |
| 3 | ka10081 vs ka10086 OHLCV cross-check | dry-run § 20.4 | Phase H |
| 4 | 페이지네이션 빈도 / 3년 백필 시간 | dry-run § 20.4 | C-backfill chunk |
| 5 | active 3000 + NXT 1500 sync 실측 시간 | dry-run § 20.4 | 운영 1주 모니터 (30~60분 추정) |
| 6 | NUMERIC(8,4) magnitude 분포 | dry-run § 20.4 | C-backfill chunk 후 |
| 7 | C-2α 상속 (NUMERIC magnitude / idx_daily_flow_exchange cardinality) | ADR § 18.4 | C-backfill chunk |

---

## 5. 다음 chunk 후보 (우선순위순)

| 순위 | chunk | 근거 | 예상 규모 |
|------|-------|------|-----------|
| 1 | **운영 실측 측정** (사용자 수동) | runbook 따라 dry-run → smoke 10 → mid 100 → full active 3000 → NUMERIC SQL → results.md 채움 → ADR § 26.5 갱신 | 수동 4~8h + 후처리 1h |
| 2 | daily_flow (ka10086) 백필 CLI | OHLCV 와 구조 다름 — `scripts/backfill_daily_flow.py` 신규 (indc_mode 파라미터 추가) | CLI 1 + tests |
| 3 | refactor R2 (1R Defer 일괄 정리) | L-2 (NotImplementedError 핸들러) / E-1 (ka10081 sync KiwoomError 핸들러) / M-3 (`# type: ignore` → `cast()`) / E-2 (reset_* docstring) / gap detection | refactor 5건 일괄 |
| 4 | ka10094 (년봉, P2) | C-3 와 동일 패턴 (Migration 1 + UseCase YEARLY 분기 활성화 — 현재 NotImplementedError) | Migration 1 + ~200줄 |
| 5 | KOSCOM cross-check 수동 | 가설 B 최종 확정 | 수동 1~2건 |
| 6 | Phase D 진입 — ka10080 분봉 | 대용량 파티션 결정 선행 필요 | 신규 도메인 + 파티션 전략 |
| ※ | (실측 결과 의존) NUMERIC 마이그레이션 | 측정 #3 에서 NUMERIC(8,4) overflow 발견 시 즉시 1순위 상승 | Migration 013 + ALTER COLUMN |

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
- **C-도커실환경** — backend_kiwoom 전용 docker-compose + runbook 실 환경 값 채움 (검증 완료) `243d4c7`
- **C-admin-CLI** — register_credential.py + sync_stock_master.py + 11 테스트 (ka10099 진입 도구) `<this commit>`

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
