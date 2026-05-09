# backend_kiwoom — 진척 현황 (STATUS)

> **단일 진실 출처** — 전체 작업의 어디까지 왔고 무엇이 남았는지 한 화면에서 파악
> **갱신 규칙**: chunk 완료 시 (커밋 직후) 본 문서 update. HANDOFF.md 와 함께 갱신.
> **연관**: `docs/plans/master.md` (전체 설계) / `docs/plans/endpoint-NN-*.md` (endpoint 별 상세 DoD) / `HANDOFF.md` (직전 세션) / `CHANGELOG.md` (시간순 변경)
> **마지막 갱신**: 2026-05-09 (Phase C-3α — 주/월봉 OHLCV 인프라 완료)

---

## 0. 한눈에 보기

| 항목 | 값 |
|------|-----|
| 진행 Phase | **Phase C** (OHLCV + 일별 수급, **C-3α 인프라 완료** / C-3β 자동화 다음) |
| 마지막 완료 chunk | **C-3α** (ka10082/83 주/월봉 인프라 — Migration 4 + ORM 4 + Repository + chart.py 확장) |
| 다음 chunk | **C-3β** (자동화 — UseCase + Router 4 path + Scheduler 2 job) |
| 25 Endpoint 진행 | **8 / 25 완료** (32%, ka10082/83 인프라만 — 자동화 후 +2). P0 5/5 완료. P1 4/8 완료 |
| 테스트 | **897 cases / 97% coverage** (+75: chart adapter 23 / Repository 18 / Migration 26 / Period enum 8) |
| 누적 chunk | 20 commits (Phase A: 8 / Phase B: 4 / Phase C: 7 / R1: 1 / 보안 PR 2) |

---

## 1. Phase 진척

| Phase | 범위 | 상태 | chunk 진행 | 주요 endpoint |
|-------|------|------|------------|---------------|
| **A — 기반 인프라** | Settings/Cipher/structlog/Migration 001/Auth/KiwoomClient/Scheduler | ✅ **완료** | A1 / 보안PR / A2-α/β / A3-α/β/γ + F1 (8) | au10001, au10002, ka10101 |
| **B — 종목 마스터** | stock + nxt_enable / 단건 조회 / 펀더멘털 | ✅ **완료** | B-α / B-β / B-γ-1 / B-γ-2 (4) | ka10099, ka10100, ka10001 |
| **C — OHLCV 백테스팅** | KRX/NXT 일봉 + 일별 수급 + 주/월/년봉 + 백필 | 🔄 **진행중 (80%)** | C-1α/β / C-2α/β/γ / R1 / C-3α + dry-run (8) | ka10081 ✅, ka10086 ✅, ka10082/83 인프라 ✅ (자동화 ⏳), ka10094 ⏳ |
| **D — 보강 시계열** | 분봉 / 틱 / 업종 일봉 | ⏳ 대기 | — | ka10079, ka10080, ka20006 |
| **E — 시그널 보강** | 공매도 / 대차거래 | ⏳ 대기 | — | ka10014, ka10068, ka20068 |
| **F — 순위** | 등락률/거래량/거래대금 5종 통합 | ⏳ 대기 | — | ka10027, ka10030, ka10031, ka10032, ka10023 |
| **G — 투자자별** | 일별 매매 / 종목별 / 연속매매 | ⏳ 대기 | — | ka10058, ka10059, ka10131 |
| **H — 통합** | 백테스팅 view, 데이터 품질 리포트, README/SPEC, Grafana | ⏳ 대기 | — | (인프라 only) |

**범례**: ✅ 완료 / 🔄 진행중 / ⏳ 대기 / ❌ 차단

---

## 2. 25 Endpoint 카탈로그 (진척별)

### 2.1 완료 (8 / 25)

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

### 2.2 진행중 / 다음 (2 인프라 완료, 자동화 대기)

**ka10082 / ka10083 — 인프라(C-3α) 완료, 자동화(C-3β) 다음**:
- C-3α (`<commit>`): Migration 009-012 + ORM 4 + Repository + chart.py fetch_weekly/fetch_monthly + Period enum
- C-3β: IngestPeriodicOhlcvUseCase + Router 4 path + Scheduler (금 19:00 / 매월 1일 03:00) — 다음 chunk

### 2.3 대기 (17 / 25)

P1 (1주 내):
| # | API | 명 | Phase | 비고 |
|---|-----|----|-------|------|
| 6 | ka10082 | 주식주봉차트 | C-3 | chart endpoint 재사용 |
| 7 | ka10083 | 주식월봉차트 | C-3 | chart endpoint 재사용 |
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
| **C-3α** | ka10082/83 인프라 — Migration 4 + ORM 4 + Repository + chart.py 확장 + Period enum | ✅ | 1R PASS, 897 tests / 97% (ADR § 23) |
| C-3β | ka10082/83 자동화 — UseCase period dispatch + Router 4 path + Scheduler 2 job | ⏳ | `endpoint-07-ka10082.md` / `endpoint-08-ka10083.md` § 6.3 |
| C-4 (선택) | ka10094 (년봉) — P2 | ⏳ | `endpoint-09-ka10094.md` |
| C-backfill | `scripts/backfill_*.py` CLI + 3년 백필 실측 | ⏳ | C-1β/C-2β/C-3β 공용 chunk |

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
| 1 | **C-3β (ka10082/83 자동화)** | C-3α 인프라 정착 직후 자동화 마무리. UseCase period dispatch + Router 4 path + Scheduler 2 job. R1 패턴 5종 전면 적용 | UseCase 1 + Router 4 path + Scheduler 2 |
| 2 | C-backfill (`scripts/backfill_ohlcv.py` CLI) | C-1β/C-2β/C-3β 통합 마무리 + 운영 실측 (페이지네이션/3년 시간/NUMERIC magnitude) | CLI 1 + 시간 측정 |
| 3 | KOSCOM cross-check 수동 | 가설 B 최종 확정 (스크립트 외) | 수동 1~2건 |
| 4 | ka10094 (년봉, P2) | C-3 와 동일 패턴 (Migration 1 + UseCase YEARLY 분기 활성화) | Migration 1 + ~200줄 |
| 5 | Phase D 진입 — ka10080 분봉 | 대용량 파티션 결정 선행 필요 | 신규 도메인 + 파티션 전략 |

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

### Phase C 진행 (7 chunks)
- C-1α — ka10081 일봉 OHLCV 인프라 (Migration 005/006) `a98e37b`
- C-1β — ka10081 OHLCV 자동화 `993874c`
- C-2α — ka10086 일별 수급 인프라 (Migration 007) `cddd268`
- C-2β — ka10086 일별 수급 자동화 `e442416`
- C-2γ — Migration 008 (D-E 중복 컬럼 DROP) `f8cece0`
- R1 — 3 도메인 일관 개선 `c3e0952`
- **C-3α** — ka10082/83 주/월봉 인프라 (Migration 009-012 + ORM 4 + Repository + chart.py 확장 + Period enum) `<commit>`

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
