# phase-f-4-rankings.md — Phase F-4 5 ranking endpoint 통합 chunk

> Phase F (순위 5종) 의 _본 chunk_. ka10027/30/31/32/23 5 endpoint 를 단일 chunk 로 통합 도입.
> 공유 인프라 (Migration 007 + `ranking_snapshot` 테이블 + `KiwoomRkInfoClient` + `RankingType` enum + JSONB payload) + 5 endpoint UseCase + scheduler + 라우터.
> 사용자 확정: 5 endpoint 통합 1 chunk (옵션 A) + F-3 inherit 정리 선행.

---

## 1. 메타

| 항목 | 값 |
|------|-----|
| Chunk ID | Phase F-4 |
| 선행 chunk | Phase F-3 (R2 inherit 정리 — `phase-f-3-r2-inherit-cleanup.md`) |
| 후속 chunk | Phase G (투자자별 — ka10058/59/10131) |
| 분류 | 도메인 확장 (5 endpoint 동시) |
| 우선순위 | P2 (백테스팅 시그널 검증 + 시장 흐름 monitoring) |
| 출처 | `endpoint-18-ka10027.md` (Phase F reference) + 19~22 (차이점만) |
| 예상 규모 | ~1,200-1,500 production line + ~800-1,000 test line (~2,000-2,500 lines) |
| ted-run 적용 여부 | ✅ (메모리 `feedback_chunk_split_for_pipelines` 임계 ~1,500줄 근처 — _주의_) |
| 25 endpoint 진행률 | 60% → **80%** (17 → 22 endpoint) |

> **chunk 분할 주의**: 본 chunk 가 plan doc § 5 견적 ~2,000줄 초과 시 사용자 합의 후 F-4a (인프라 + ka10027) / F-4b (ka10030/31) / F-4c (ka10032/23) 등 sub-chunk 로 분할. ted-run 진입 시 사용자 재확인.

---

## 2. 현황 (Phase F 진입 전 상태)

### 2.1 기존 자산 (재사용)

| 자산 | 위치 | 본 chunk 활용 |
|------|------|--------------|
| `KiwoomClient` (httpx + 토큰 + tenacity + pagination) | `app/adapter/out/kiwoom/_client.py` | `KiwoomRkInfoClient` 가 wrapping |
| `StockRepository.find_by_codes` | `app/adapter/out/persistence/repositories/stock.py` | stk_cd → stock_id lookup batch |
| `strip_kiwoom_suffix` (`_NX` suffix) | `app/adapter/out/kiwoom/_codes.py` | NXT 코드 → KRX 마스터 lookup |
| `SentinelStockCodeError` + `SkipReason` enum (F-3) | `app/application/dto/_shared.py` (F-3 신규) | ranking 응답 row 의 stk_cd 가드 |
| `errors_above_threshold: tuple[str, ...]` (F-3 통일) | DTO 패턴 | RankingBulkResult 적용 |
| `_empty_bulk_result` helper (F-3) | service helper | ranking BulkUseCase 가 동일 패턴 |
| APScheduler cron + `misfire_grace_time` (Phase D) | `app/batch/_scheduler.py` | 5 ranking cron 추가 |
| Pydantic Settings + Fernet credential | `config/settings.py` | 기존 credential 그대로 |

### 2.2 endpoint-18~22 reference 요약

ADR § 4 #5 / endpoint-18 § 11.3 의 5 endpoint 비교 표 재인용:

| 항목 | ka10027 (등락률) | ka10030 (당일거래량) | ka10031 (전일거래량) | ka10032 (거래대금) | ka10023 (거래량 급증) |
|------|---|---|---|---|---|
| URL | `/api/dostk/rkinfo` | 동일 | 동일 | 동일 | 동일 |
| Body 필드 수 | 9 | 9 | 5 | 3 | 8 |
| 응답 list 키 | `pred_pre_flu_rt_upper` | `tdy_trde_qty_upper` | `pred_trde_qty_upper` | `trde_prica_upper` | `trde_qty_sdnin` |
| 응답 필드 수 | 12 | **23** (장중/장후/장전) | **6** (단순) | 13 | 10 |
| 응답 정렬 기준 | flu_rt | trde_qty | trde_qty | trde_prica | sdnin_qty |
| `primary_metric` | flu_rt | trde_qty | trde_qty | trde_prica | sdnin_qty / sdnin_rt |
| `RankingType` enum | FLU_RT | TODAY_VOLUME | PRED_VOLUME | TRDE_PRICA | VOLUME_SDNIN |
| 우선순위 | P2 | P2 | P3 | P2 | P2 |

### 2.3 Phase F-3 정착 패턴 (본 chunk 가 적용)

- `SkipReason` StrEnum — ranking 응답 row 의 stk_cd 가드 실패 시 outcome.error 분리
- `errors_above_threshold: tuple[str, ...]` — RankingBulkResult 도 동일 형태
- `_empty_bulk_result` helper — empty stocks/empty response 조기 반환
- 단건 UseCase `SentinelStockCodeError` catch — defense-in-depth

---

## 3. 범위 외 (out of scope)

| 항목 | 이유 | 후속 chunk |
|------|------|-----------|
| Phase G (투자자별 — ka10058/59/10131) | 별도 Phase | Phase G |
| Phase H (백테스팅 view + Grafana) | Phase F 5 endpoint 완성 후 derived feature | Phase H |
| 순위 변동 알람 시그널 (어제 5위 → 오늘 50위) | derived feature — Phase H | Phase H |
| ka10027 (등락률) 의 5 sort_tp 모두 sync | 운영 default = UP_RATE + DOWN_RATE 2종 (master § 5) — 추가는 운영 검증 후 | Phase F-5 (선택) |
| 다중 시점 sync (장 시작 / 장중 / 종가 후 3 시점) | 운영 default = 19:30 종가 후 1회 — 다중 시점은 정책 결정 후 | Phase F-5 (선택) |
| 백필 (과거 시점 스냅샷) | 키움이 과거 시점 응답 가능 여부 _운영 검증 필요_ — endpoint-18 § 10.3 DoD | 운영 검증 후 |
| ka10030 의 `opmr_/af_mkrt_/bf_mkrt_` 시간대 분리 derived feature | JSONB payload 그대로 보존. derived view 는 Phase H | Phase H |

---

## 4. 확정 결정 (작성 시점 미확정 — § 9 ted-run input 직전 사용자 확정 필요)

| # | 결정 항목 | 옵션 | 권고 default |
|---|----------|------|--------------|
| **D-1** | 5 endpoint chunk 분할 vs 통합 | (a) 통합 1 chunk (현 plan) (b) 인프라 + 5 endpoint = 6 sub-chunk (c) F-4a/b/c 3 sub-chunk | (a) — 사용자 확정 |
| **D-2** | `ranking_snapshot` 테이블 통합 vs 분리 | (a) 단일 테이블 + JSONB payload + `ranking_type` 컬럼 (현 plan) (b) endpoint 별 5 테이블 | (a) — 새 ranking 추가 시 enum + UseCase 만 |
| **D-3** | 운영 default `mrkt_tp` | (a) `{001, 101}` (KOSPI + KOSDAQ) (b) `{000, 001, 101}` (전체 추가) (c) `{000}` 만 (전체 합산) | (a) — endpoint-18 § 4.1 |
| **D-4** | 운영 default `stex_tp` | (a) 3 (통합) (b) `{1, 2, 3}` 모두 (KRX/NXT/통합) | (a) — 단순. NXT 별도는 운영 검증 후 |
| **D-5** | ka10027 운영 default `sort_tp` | (a) `{1, 3}` (UP_RATE + DOWN_RATE) (b) 5 sort 모두 | (a) |
| **D-6** | sync 시점 cron | (a) 19:30 (종가 후 1시간) 5 endpoint 5분 간격 chain (b) 19:30 + 09:30 (시작 + 종가) 다중 (c) 종가 후 1회만 + 5 endpoint 병렬 동시 | (a) — endpoint-18 § 7.2. 5분 간격 chain = 19:30/35/40/45/50 |
| **D-7** | `snapshot_time` precision | (a) 초 단위 (`HH:MM:SS`) (b) 분 단위 (`HH:MM:00`) | (a) — UNIQUE 키 충돌 위험 0 |
| **D-8** | stock lookup miss 정책 | (a) stock_id = NULL + stock_code_raw 보관 (현 plan) (b) lazy `ka10100` fetch 후 적재 (c) lookup miss alert | (a) — 운영 1주 모니터 후 (c) 추가 검토 |
| **D-9** | ka10030 의 23 필드 → JSONB payload 평탄 vs 구조 | (a) 평탄 (모든 필드 root level) (b) 시간대 별 nested (`{"opmr": {...}, "af_mkrt": {...}, "bf_mkrt": {...}}`) | (b) — 23 필드 중 4 그룹 분리. derived feature 쿼리 단순화 |
| **D-10** | F-3 의 `SkipReason` 확장 vs 신규 | (a) `SkipReason.STOCK_LOOKUP_MISS` 추가 — lookup miss 도 outcome 분리 (b) 추가 안 함 (lookup miss 는 stock_id=NULL 로 처리 — 별개 의미) | (b) — lookup miss 는 _skip_ 이 아님 (적재됨) |
| **D-11** | `RankingBulkResult` 임계치 정책 | (a) `failure_ratio = total_failed / total_calls` 5%/15% (lending/short 패턴) (b) endpoint 별 다른 임계치 (c) 임계치 없음 (5 endpoint 신규라 baseline 없음) | (c) — 운영 1주 모니터 후 임계치 도입 |
| **D-12** | Migration 007 의 `primary_metric` 정밀도 | (a) `NUMERIC(20, 4)` — endpoint-18 plan (b) `NUMERIC(20, 2)` — KRX 호가 최소단위 (c) `NUMERIC(28, 8)` — 거래대금 큰 수 대응 | (a) — endpoint-18 합의 |
| **D-13** | JSONB payload 의 indexing | (a) GIN index 1개 (`payload`) — ad-hoc 쿼리 (b) typed view 별도 — Phase H derived | (a) — 첫 도입 |
| **D-14** | 5 endpoint scheduler cron 동시 vs chain | (a) 5분 간격 chain (19:30/35/40/45/50) (b) 동시 발화 + asyncio.gather (c) misfire 시 잔여 endpoint 만 retry | (a) — RPS 4 충돌 회피. 5 endpoint × 4 호출 = 20 호출 / chain ⇒ 호출당 250ms × 20 = 5초 / endpoint |

> **D-1~D-14 권고 default 가 모두 합의되면** § 5 변경면이 확정.

---

## 5. 변경 면 매핑 (D-1~D-14 권고 default 가정)

### 5.1 Migration (1 신규)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `migrations/versions/007_ranking_snapshot.py` (신규) | `kiwoom.ranking_snapshot` 테이블 + UNIQUE 키 6개 + 3 인덱스 (date+type / stock_id / payload GIN) |

### 5.2 ORM Model (1 신규)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/adapter/out/persistence/models/ranking_snapshot.py` (신규) | `RankingSnapshot` declarative |

### 5.3 Repository (1 신규)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/adapter/out/persistence/repositories/ranking_snapshot.py` (신규) | `RankingSnapshotRepository.upsert_many` + `get_at_snapshot` + (선택) `get_rank_history` |

### 5.4 Adapter (2 신규)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/adapter/out/kiwoom/rkinfo.py` (신규) | `KiwoomRkInfoClient.fetch_flu_rt_upper / fetch_today_volume_upper / fetch_pred_volume_upper / fetch_trde_prica_upper / fetch_volume_sdnin` — 5 메서드. `SentinelStockCodeError` 가드는 _stk_cd 비교 보다는 응답 row 정규화 시점_ (NXT `_NX` strip 후 6자리 숫자 가드) |
| 2 | `app/adapter/out/kiwoom/_records.py` (갱신) | `FluRtUpperRow / FluRtUpperResponse` + ka10030/31/32/23 의 Row/Response 4쌍 추가. `RankingType` / `RankingMarketType` / `RankingExchangeType` / `FluRtSortType` / `TodayVolumeSortType` / `VolumeSdninSortType` / `VolumeSdninTimeType` enum |

### 5.5 DTO (1 신규)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/application/dto/ranking.py` (신규) | `NormalizedRanking` dataclass + `RankingIngestOutcome` (단건) + `RankingBulkResult` (bulk — `tuple errors_above_threshold` 패턴 F-3 적용) |

### 5.6 Service (1 신규)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/application/service/ranking_service.py` (신규) | `IngestFluRtUpperUseCase` / `IngestTodayVolumeUpperUseCase` / `IngestPredVolumeUpperUseCase` / `IngestTrdePricaUpperUseCase` / `IngestVolumeSdninUseCase` (단건 5종) + 각 Bulk 5종. `_empty_bulk_result` (F-3) 패턴. 단건 sentinel catch (F-3 D-7) |

### 5.7 Router (1 신규)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/adapter/web/routers/rankings.py` (신규) | 5 endpoint × (POST 단건 / POST sync bulk / GET snapshot) = ~15 라우터. `require_admin_key` 의존성 (POST). `dependencies` 도 admin |

### 5.8 Batch (1 신규)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/batch/ranking_jobs.py` (신규) | 5 cron — `fire_flu_rt_sync` / ... / `fire_volume_sdnin_sync`. 19:30/35/40/45/50 KST mon-fri. `misfire_grace_time=60*30` |

### 5.9 Scheduler 등록 (1 갱신)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/batch/_scheduler.py` | 5 ranking cron import + scheduler.add_job 5건 |

### 5.10 DI 갱신 (1 갱신)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/adapter/web/dependencies.py` | `get_ranking_repo` / `get_kiwoom_rkinfo_client` / 5 단건 UseCase + 5 Bulk UseCase factory |

### 5.11 App entry (1 갱신)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/main.py` | rankings router include |

### 5.12 테스트 신규 (~12 파일)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `tests/test_rkinfo_client.py` (신규) | 5 fetch 메서드 — 정상 / 페이지네이션 / 빈 응답 / sentinel / business error (~25 케이스) |
| 2 | `tests/test_ranking_repository.py` (신규) | upsert INSERT/UPDATE 멱등성 / lookup miss NULL / NXT `_NX` 보존 / get_at_snapshot (~15 케이스) |
| 3 | `tests/test_ingest_flu_rt_use_case.py` (신규) | ka10027 단건 + bulk (4 호출 매트릭스) + 단건 sentinel catch (~12 케이스) |
| 4 | `tests/test_ingest_today_volume_use_case.py` (신규) | ka10030 (23 필드 + 시간대 nested payload) (~10 케이스) |
| 5 | `tests/test_ingest_pred_volume_use_case.py` (신규) | ka10031 (rank_strt/end 페이지네이션) (~8 케이스) |
| 6 | `tests/test_ingest_trde_prica_use_case.py` (신규) | ka10032 (`now_rank/pred_rank` 직접 응답) (~8 케이스) |
| 7 | `tests/test_ingest_volume_sdnin_use_case.py` (신규) | ka10023 (`sdnin_rt` + tm_tp 1/2) (~10 케이스) |
| 8 | `tests/test_rankings_router.py` (신규) | 5 endpoint × 3 라우터 = 15 — admin key 회귀 + Pydantic validation (~15 케이스) |
| 9 | `tests/test_ranking_jobs.py` (신규) | 5 cron — fire 시 BulkUseCase 호출 / misfire / errors_above_threshold tuple 알람 (~10 케이스) |
| 10 | `tests/integration/test_ranking_snapshot_e2e.py` (신규 — testcontainers PG16) | INSERT 50 row + UPDATE 멱등 / JSONB payload 쿼리 / lookup miss NULL (~8 케이스) |
| 11 | `tests/test_records_ranking.py` (신규) | Pydantic row 5종 — to_payload / _NX strip / 부호 (`+/-`) 처리 (~15 케이스) |
| 12 | `tests/test_ranking_dto.py` (신규) | `RankingBulkResult.errors_above_threshold` tuple 패턴 회귀 (~5 케이스) |

추정 변경 라인:
- Migration + ORM + Repository = ~300줄
- Adapter (rkinfo + _records) = ~400줄
- DTO + Service (5 단건 + 5 bulk) = ~500줄
- Router + Batch + DI = ~300줄
- 테스트 ~12 파일 = ~800-1,000줄

⇒ 총 ~2,300-2,500줄 (메모리 `feedback_chunk_split_for_pipelines` 임계 ~1,500줄 _초과_ — **사용자 확정 시 D-1 분할 옵션 재논의**)

> _대안 D-1 (b)_ 분할 시:
> - F-4a: 인프라 + ka10027 (~1,000줄)
> - F-4b: ka10030 + ka10031 (~700줄)
> - F-4c: ka10032 + ka10023 (~700줄)

---

## 6. 적대적 self-check (보안 / 동시성 / 데이터 정합)

### 6.1 보안

- 5 라우터 POST 모두 `require_admin_key` 의존성 — admin only ⇒ ✅
- JSONB payload — 사용자 입력 직접 저장 아님. 키움 응답을 정규화 후 dict 저장 ⇒ ✅ (단, `model_validate` 가 schema 외 필드 reject 하지 않으면 unintended payload 흡수 가능 — `FluRtUpperRow.model_config = ConfigDict(extra="ignore")` 검증)
- `request_filters` JSONB 보관 — 호출자 인증 정보는 포함 안 함 (mrkt_tp/sort_tp/... 8 필터만) ⇒ ✅
- structlog 자동 마스킹 — appkey / secretkey / authorization / token / access_token / secret ⇒ ✅

### 6.2 동시성 / 운영

- 5 cron chain (19:30/35/40/45/50) — RPS 4 충돌 회피. 단, 다른 cron (ka10014 19:45 공매도) 와 시간 충돌 → endpoint-18 § 7.2 가 `19:50 으로 조정` 명시. **확인 필요**: ka10014 cron 시점 (현재 18:00 stock_fundamental 다음 cron 위치)
- ranking BulkUseCase 의 4 호출 (2 market × 2 sort) — `asyncio.gather` 또는 sequential? 권고: sequential (RPS guard 자체 충족 + 임계치 명확)
- misfire_grace_time=60*30 (30분) — Phase D 패턴 유지
- 단건 UseCase sentinel catch (F-3 D-7) — ranking 응답 row 의 stk_cd 가 alphanumeric 가능성 (NXT `_NX` strip 후에도 ETF 코드 등 4-5자리) — _운영 검증 항목 추가_

### 6.3 데이터 정합

- UNIQUE 키 6개 (`snapshot_date / snapshot_time / ranking_type / sort_tp / market_type / exchange_type / rank`) — 멱등성 보장
- NXT `_NX` suffix — `stock_code_raw` 보존 + stock_id lookup 은 strip 후 — 분석 시 NXT vs KRX 분리 가능
- lookup miss → stock_id=NULL — 운영 1주 모니터로 비율 확인 (D-8 (c) lookup miss alert 도입 검토)
- 응답 정렬 가정 — list 순서 = rank — **첫 호출 검증** (endpoint-18 § 11.2)
- 5 endpoint 의 `mrkt_tp` 의미 통일 (000/001/101) — ka10099 (0/10/30/...) / ka10101 (0/1/2/4/7) 과 _다른 의미_. `RankingMarketType` enum 분리 적용 ⇒ ✅

### 6.4 5 endpoint 통합 1 chunk 의 위험

- chunk 크기 ~2,500줄 — 메모리 `feedback_chunk_split_for_pipelines` 임계 초과. _ted-run 입력 시점에 사용자 재확인_
- 5 endpoint 의 응답 schema 가 _운영 검증 안 됨_ — Excel 명세와 실제 응답 차이 발생 시 1 chunk 안에서 5번 반복 수정 — _D-1 분할 옵션 (b/c) 의 동기_
- 5 endpoint 동시 도입 시 verification 5관문 (ruff/mypy/pytest/cov/smoke) 모두 5배 크기 — sonnet 검토 한도 도달 가능 (`ted-run` step 2a sub-agent 분리 검토)

### 6.5 ka10030 의 23 필드 nested payload (D-9 = b)

```json
{
  "stk_cd_raw": "005930",
  "stk_nm": "삼성전자",
  "cur_prc": 74800,
  "opmr": {"trde_qty": 446203, "trde_prica": 333000000},
  "af_mkrt": {"trde_qty": 0, "trde_prica": 0},
  "bf_mkrt": {"trde_qty": 0, "trde_prica": 0},
  "trde_tern_rt": "1.25"
}
```

→ derived feature 쿼리 단순화 (`payload->'opmr'->>'trde_qty'`).
→ Phase H typed view 의 backbone.

### 6.6 운영 검증 의존 (DoD § 10.3 검증 후 결정)

- `stk_cls` 코드 의미 (5 endpoint 공통?)
- `cnt` (횟수) 의미 (ka10027 unique?)
- `cntr_str` (체결강도) 의미
- 응답 row 수 (한 페이지 ~100? 200?)
- NXT 응답에서 stk_cd `_NX` 보존 여부
- ka10030 의 23 필드 실제 응답 schema (Excel 와 일치?)

---

## 7. DoD (Definition of Done)

### 7.1 코드 (~15 파일 — 신규 12 / 갱신 3)

- [ ] Migration 007 — `kiwoom.ranking_snapshot` 테이블 + UNIQUE/INDEX
- [ ] ORM Model — `RankingSnapshot`
- [ ] Repository — `upsert_many` + `get_at_snapshot`
- [ ] `KiwoomRkInfoClient` — 5 fetch 메서드
- [ ] `_records.py` 갱신 — 5 Row/Response + 4 enum + `NormalizedRanking`
- [ ] `ranking.py` DTO — Outcome + BulkResult (F-3 tuple 패턴)
- [ ] `ranking_service.py` — 5 단건 + 5 Bulk UseCase (F-3 helper + 단건 catch)
- [ ] `rankings.py` Router — 15 endpoint (5 × 3)
- [ ] `ranking_jobs.py` — 5 cron
- [ ] `_scheduler.py` 갱신 — 5 add_job
- [ ] `dependencies.py` 갱신 — 10 factory
- [ ] `main.py` — router include
- [ ] **Migration 운영 적용 dry-run** — kiwoom-db `alembic upgrade head` smoke

### 7.2 테스트

- [ ] Unit ~12 파일 / ~140 케이스 PASS
- [ ] Integration (testcontainers PG16) e2e PASS — JSONB payload 쿼리 + GIN index 활용 검증
- [ ] coverage ≥ 86.43% baseline → ~85-87% (대량 신규 코드라 dip 가능)
- [ ] ruff clean
- [ ] mypy --strict 신규 ~15 파일 Success
- [ ] pytest 전체 ~1,400-1,420 케이스 PASS

### 7.3 운영 검증 (5-15 이후)

- [ ] **첫 cron 발화 (19:30)** ka10027 — 응답 row 수 / lookup miss 비율 / payload schema (Excel vs 실제)
- [ ] 5 endpoint 모두 첫 cron 발화 — 5분 chain 정상
- [ ] `stk_cls` / `cnt` / `cntr_str` 의미 master.md § 12 기록
- [ ] NXT 응답 stk_cd `_NX` 보존 검증
- [ ] ka10030 의 23 필드 실제 응답 (Excel 와 일치?)
- [ ] `errors_above_threshold` 발화 0 (5 endpoint 신규 — baseline 없음)

### 7.4 문서

- [ ] CHANGELOG: `feat(kiwoom): Phase F-4 — 5 ranking endpoint 통합 (ka10027/30/31/32/23) + ranking_snapshot 테이블 + JSONB payload`
- [ ] ADR § 48 신규 — Phase F-4 결정 + 운영 검증 결과 (5-15 이후)
- [ ] STATUS.md § 0 (25 endpoint 60% → 80%) + § 2 카탈로그 5종 완료 + § 5 다음 chunk (Phase G) + § 6 누적 chunk +1
- [ ] HANDOFF.md rewrite — Phase G plan doc 작성 권고 + 운영 검증 follow-up
- [ ] `master.md § 12` 결정 기록 — `stk_cls` / `cnt` / `cntr_str` / 응답 row 수 / NXT 코드 형식

---

## 8. 다음 chunk

| 후보 | 시점 | 비고 |
|------|------|------|
| **Phase G — 투자자별 (ka10058/59/10131)** | F-4 완료 직후 | 다음 도메인 — stock_daily_flow / investor_flow_daily / frgn_orgn_consecutive |
| Phase F-5 (선택) — 5 endpoint 운영 검증 fix + 다중 시점 sync | F-4 운영 1주 후 | sort_tp 추가 / mrkt_tp=000 추가 / 다중 시점 cron / lookup miss alert (D-8 (c)) |
| ka10080 분봉 (Phase D-2 마지막) | 별도 chunk | 대용량 파티션 결정 동반 |
| derived feature — 순위 변동 시그널 | Phase H | ranking_snapshot 의 cross-snapshot 분석 |

---

## 9. ted-run 풀 파이프라인 input

```yaml
chunk: Phase F-4
title: 5 ranking endpoint 통합 (ka10027/30/31/32/23) + ranking_snapshot + JSONB payload
선행: Phase F-3 (SkipReason Enum / errors_above_threshold tuple 정착)
plan_doc: src/backend_kiwoom/docs/plans/phase-f-4-rankings.md
reference: src/backend_kiwoom/docs/plans/endpoint-18-ka10027.md + 19~22

input:
  결정_사용자_확정_14건:
    D-1: 5 endpoint 통합 1 chunk (옵션 A) — _chunk 크기 ~2,500줄 임계 초과 검토_
    D-2: ranking_snapshot 단일 테이블 + JSONB payload
    D-3: 운영 default mrkt_tp = {001, 101}
    D-4: 운영 default stex_tp = 3 (통합)
    D-5: ka10027 운영 default sort_tp = {1, 3}
    D-6: cron 19:30/35/40/45/50 KST mon-fri (5분 chain)
    D-7: snapshot_time 초 단위
    D-8: stock lookup miss → stock_id=NULL + stock_code_raw 보관 (alert 후속)
    D-9: ka10030 23 필드 nested payload ({opmr, af_mkrt, bf_mkrt} 분리)
    D-10: SkipReason.STOCK_LOOKUP_MISS 추가 안 함
    D-11: 임계치 도입 안 함 (운영 1주 모니터 후)
    D-12: primary_metric NUMERIC(20, 4)
    D-13: GIN index payload 1개
    D-14: 5 endpoint scheduler chain sequential (asyncio.gather 아님)
  변경면:
    Migration: 007 신규
    ORM/Repository: 신규 1 + 1
    Adapter: rkinfo 신규 + _records 갱신
    DTO: ranking.py 신규
    Service: ranking_service.py 신규 (5 단건 + 5 bulk)
    Router: rankings.py 신규 (15 endpoint)
    Batch: ranking_jobs.py 신규 + _scheduler.py 갱신
    DI: dependencies.py 갱신
    App entry: main.py 갱신
    Test: ~12 신규

verification:
  - alembic upgrade head smoke (kiwoom-db)
  - ruff clean
  - mypy --strict ~120 files Success
  - pytest 전체 ~1,400-1,420 PASS
  - coverage ≥ 85% (대량 신규라 dip 허용)
  - 5 cron 등록 확인 (`scheduler.print_jobs()`)
  - Integration e2e (testcontainers) PASS

scope_out:
  - Phase G (투자자별)
  - 다중 시점 sync (Phase F-5)
  - 백필 (운영 검증 후)
  - 순위 변동 derived feature (Phase H)
  - lookup miss alert (D-8 c — 별도 chunk)

postdeploy:
  - 5-15 (또는 다음 평일) 19:30 첫 cron 발화 모니터
  - stk_cls / cnt / cntr_str 의미 master.md 기록
  - NXT stk_cd _NX 보존 검증
  - lookup miss 비율 1주 측정
  - ka10030 23 필드 실제 응답 schema 검증
```

> **chunk 크기 주의**: 본 chunk ~2,500줄 — `feedback_chunk_split_for_pipelines` 임계 초과. ted-run 진입 직전 사용자 재확인. _D-1 (a) 통합_ 유지 vs _(b) 분할_ 재논의 권고.

---

## 10. 위험 / 메모 (운영 결정 사항)

- **첫 cron 발화 시점 (5-15 또는 다음 평일 19:30)** — Phase F-4 chunk 완료 직후 redeploy 시점 사용자 결정. _5-14 21:00 redeploy 가능_ vs _5-15 06:00 cron 자연 검증 후 redeploy_
- **endpoint-18 § 11.2 운영 검증 항목** — 본 chunk 코드화 후 첫 cron 발화로 자동 검증 가능 (응답 schema / row 수 / 정렬 가정 / lookup miss / NXT)
- **JSONB payload disk 사용량** — 5 endpoint × 1 시점 × 150 row × 365일 × 3년 ≈ 2.27M row × ~2KB = ~4.5GB. 단일 테이블 + GIN index ⇒ 5년 시점 분리 검토
- **ka10014 (Phase E 공매도) cron 시점 충돌** — ranking 5 cron 의 19:50 과 ka10014 cron 시점 비교. **확인 필요** (`grep ka10014 app/batch/`)
- **chunk 분할 옵션 (D-1 b/c)** — ted-run 입력 직전 사용자 재논의. F-3 완료 직후 본 chunk 크기 견적 정확화 후 결정

---

_Phase F (순위 5종) 의 본 chunk. 5 endpoint × Migration 007 × KiwoomRkInfoClient × ranking_snapshot 테이블 × JSONB payload × 15 라우터 × 5 cron. 25 endpoint 진행률 60% → 80%. F-3 정착 패턴 (SkipReason Enum / tuple errors_above_threshold / empty helper / 단건 catch) 위에서 작업._
