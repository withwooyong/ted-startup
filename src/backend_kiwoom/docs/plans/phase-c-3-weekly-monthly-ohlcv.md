# phase-c-3-weekly-monthly-ohlcv.md — Phase C-3 (ka10082/83 주봉/월봉)

## 0. 메타

| 항목 | 값 |
|------|-----|
| chunk 명 | **C-3** (Phase C 의 신규 도메인) |
| 범위 | ka10082 (주봉) + ka10083 (월봉) — KRX/NXT 둘 다 |
| 분할 | **C-3α (인프라)** + **C-3β (자동화)** — 2 chunk / 2 commit |
| 선행 chunk | C-1β (`993874c`) / C-2β (`e442416`) / C-2γ (`f8cece0`) / **R1 (`c3e0952`) 모두 완료** |
| 우선순위 | **P1** — Phase C 잔여 (75% → 90%+) |
| 동시 처리 이유 | UseCase / Repository / Mixin / Adapter class 모두 공유 (ka10082 ↔ ka10083 차이 = list 키 + cron 시간 + 영속화 테이블만) |
| 관련 endpoint plan doc | [`endpoint-07-ka10082.md`](./endpoint-07-ka10082.md) / [`endpoint-08-ka10083.md`](./endpoint-08-ka10083.md) |
| 모델 패턴 출처 | [`endpoint-06-ka10081.md`](./endpoint-06-ka10081.md) (~95% 패턴 복제) |

> **본 doc 의 역할**: chunk 단위 응집 정보 (영향 범위 / self-check / DoD / 분할 경계). endpoint 단위 상세 명세는 endpoint-07/08 plan doc 참조.

---

## 1. 목적

**주봉/월봉 OHLCV 시계열 적재** — 백테스팅 중장기 시그널 (20주 이동평균 / 12개월 모멘텀 / 52주 신고가) 의 입력. 일봉 합성 대신 키움 자체 주/월봉 사용 — 키움 백테스팅 기준일과의 정합성 확보.

**왜 신규 chunk 1건이 아닌 α/β 분할인가**:
- 정착된 패턴 — C-1α/β / C-2α/β/γ 이 인프라/자동화 분할로 안정. R1 이후 패턴 일관성 회복 직후라 선례 그대로 유지
- ted-run 풀 파이프라인이 chunk 당 1회 실행 — 1,200~1,600줄 단일 chunk 는 context 부담. α/β 로 나눠 각각 700~900 / 500~700줄
- α 통과 시 β 가 의존 — α 실패 시 β 손대기 전에 멈출 수 있음

---

## 2. 범위 외 (Out of Scope)

- **ka10094 (년봉)** — Period.YEARLY 스켈레톤만 enum 에 노출. 본 chunk 에서 fetch_yearly / Migration / Router / Scheduler **추가 안 함**. 향후 P2 chunk 에서 동일 패턴으로 처리
- **`scripts/backfill_ohlcv.py --period weekly|monthly`** — C-backfill chunk 로 연기 (C-1β/C-2β 와 통합)
- **일봉 vs 키움 주/월봉 cross-check** — Phase H 데이터 품질 리포트로 연기
- **`dt` 의미 (주 시작/종료 / 달 첫/말일) 운영 검증** — 첫 운영 호출 후 KOSCOM cross-check 와 묶어서 처리. plan doc 에 가설 명시 + 검증 항목 등록만
- **분봉 / 틱** — Phase D
- **R1 같은 cross-cutting refactor** — 본 chunk 는 신규 도메인 진입. R1 정착 패턴 그대로 복제 (errors=tuple / StockMasterNotFoundError / fetched_at non-Optional / max_length=2)

---

## 3. 영향 범위

### 3.1 C-3α — 인프라 (~700~900줄)

**신규 (8 파일)**:

| # | 파일 | 라인 추정 | 비고 |
|---|------|-----------|------|
| 1 | `migrations/versions/009_kiwoom_stock_price_weekly_krx.py` | ~80 | _DailyOhlcvMixin 컬럼 동일, weekly KRX 테이블 |
| 2 | `migrations/versions/010_kiwoom_stock_price_weekly_nxt.py` | ~80 | weekly NXT 테이블 |
| 3 | `migrations/versions/011_kiwoom_stock_price_monthly_krx.py` | ~80 | monthly KRX 테이블 |
| 4 | `migrations/versions/012_kiwoom_stock_price_monthly_nxt.py` | ~80 | monthly NXT 테이블 |
| 5 | `app/adapter/out/persistence/models/stock_price_periodic.py` | ~80 | StockPriceWeeklyKrx/Nxt + StockPriceMonthlyKrx/Nxt (기존 stock_price.py 의 _DailyOhlcvMixin 재사용) |
| 6 | `app/adapter/out/persistence/repositories/stock_price_periodic.py` | ~120 | StockPricePeriodicRepository — period+exchange dispatch (4 모델 매핑) |
| 7 | `app/application/constants.py` 의 Period enum (or 신규 `app/application/_period.py`) | ~20 | `Period(StrEnum) = WEEKLY / MONTHLY / YEARLY` (DAILY 는 별도 UseCase 라 본 enum 외) |
| 8 | `tests/test_stock_price_periodic_repository.py` | ~150 | upsert / period dispatch / unique constraint |

**수정 (3 파일)**:

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/adapter/out/kiwoom/chart.py` | `KiwoomChartClient.fetch_weekly` / `fetch_monthly` 추가 (~140줄, ka10081 패턴 복제). list 키만 분기 |
| 2 | `app/adapter/out/kiwoom/_records.py` | `WeeklyChartRow` / `MonthlyChartRow` (DailyChartRow 상속, pass) + `WeeklyChartResponse` / `MonthlyChartResponse` (~40줄) |
| 3 | `app/adapter/out/persistence/models/__init__.py` | 신규 4 모델 re-export |

**테스트 (2 파일)**:

| # | 파일 | 라인 추정 | 비고 |
|---|------|-----------|------|
| 1 | `tests/test_chart_adapter.py` (기존) 확장 | +60 | fetch_weekly / fetch_monthly 응답 list 키 검증 + 에러 처리 |
| 2 | `tests/test_stock_price_periodic_repository.py` 신규 | ~150 | (위 § 3.1 #8) |

**소계**: 신규 8 + 수정 3 + 테스트 2 = 13 파일 / ~900줄

---

### 3.2 C-3β — 자동화 (~500~700줄)

**신규 (4 파일)**:

| # | 파일 | 라인 추정 | 비고 |
|---|------|-----------|------|
| 1 | `app/application/service/ohlcv_periodic_service.py` | ~250 | IngestPeriodicOhlcvUseCase (period dispatch — WEEKLY/MONTHLY) + RefreshOnePeriodicOhlcvUseCase (단건). R1 정착 패턴 (errors=tuple / StockMasterNotFoundError / fetched_at non-Optional) 적용 |
| 2 | `app/batch/weekly_ohlcv_job.py` | ~70 | APScheduler 등록 — 금 KST 19:00 |
| 3 | `app/batch/monthly_ohlcv_job.py` | ~70 | APScheduler 등록 — 매월 1일 KST 03:00 |
| 4 | `tests/test_ohlcv_periodic_service.py` | ~250 | 단건 / 일괄 / period dispatch / NXT 가드 / inactive / nxt_enable / R1 invariant 회귀 |

**수정 (3 파일)**:

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/adapter/web/routers/ohlcv.py` | `POST /ohlcv/{stock_code}/weekly` / `POST /ohlcv/weekly/sync` / `POST /ohlcv/{stock_code}/monthly` / `POST /ohlcv/monthly/sync` 라우터 추가. R1 패턴 — DTO `errors: tuple[str, ...] = ()` / `fetched_at: datetime` 명시 / `max_length=2` |
| 2 | `app/scheduler.py` | weekly + monthly job 등록 lifespan 추가 |
| 3 | `app/main.py` | (가능 시) weekly/monthly UseCase DI 등록 |

**테스트 (1 파일)**:

| # | 파일 | 라인 추정 | 비고 |
|---|------|-----------|------|
| 1 | `tests/test_ohlcv_router.py` (기존) 확장 | +120 | weekly/monthly 4 path 응답 + R1 contract 회귀 (errors tuple / fetched_at 필드 / 422 max_length=2) |

**소계**: 신규 4 + 수정 3 + 테스트 1 = 8 파일 / ~700줄

---

### 3.3 문서 (C-3α/β 모두 갱신)

| 파일 | 갱신 시점 |
|------|-----------|
| `STATUS.md` | C-3α 커밋 / C-3β 커밋 직후 (2회 갱신) |
| `HANDOFF.md` | C-3β 마무리 후 (chunk 묶음 종료 시) |
| `CHANGELOG.md` | 각 chunk 커밋 직전 prepend (2회) |
| `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 23 (C-3α) / § 24 (C-3β) | 핵심 결정 + 1R 결과 + Defer 매핑 |
| `docs/plans/master.md` § 12 | `dt` 의미 가설 명시 + 운영 first-call 후 검증 항목 등록 |

---

## 4. 적대적 사전 self-check (H-1 ~ H-7)

> **목적**: chunk 진입 전 알려진 위험 / 가정 / R1 정착 패턴 위반 가능성을 사전 점검. 각 항목은 ted-run TDD/구현/리뷰 단계에서 명시적으로 검증.

### H-1 — Migration 4건 분리 vs 통합

- **위험**: Alembic Migration 4 파일이 분리되면 down_revision 체인이 직선 (009 → 010 → 011 → 012). 중간에 실패하면 부분 적용
- **결정**: 분리 유지. 이유 — C-1α (Migration 005/006) 가 KRX/NXT 분리. 패턴 일관성 우선. up/down 모두 idempotent. 운영은 적용 시 한 번에 4건 실행 (롤백 시 down 4번)
- **검증**: testcontainers 통합 테스트에서 4 마이그레이션 모두 up → down → up 사이클 PASS

### H-2 — `_DailyOhlcvMixin` 재사용 (4 테이블 컬럼 동일)

- **위험**: 일봉/주봉/월봉 의미가 다른데 컬럼 동일 (`trading_date`, `prev_compare_amount`, `prev_compare_sign`). `prev_compare_*` 가 일봉에서는 직전 거래일 대비, 주봉에서는 직전 주 대비 — 의미가 다른데 같은 컬럼명
- **결정**: Mixin 재사용 유지. 이유 — 키움 응답 의미가 period 별로 다른 것이지 컬럼 자체는 raw 적재. 컬럼 주석에 "period 별 의미는 영속화 테이블 이름으로 식별" 명시
- **검증**: ORM 모델 `__doc__` 에 period 별 의미 한 줄 + plan doc § 5.3 의 trading_date 의미 표

### H-3 — `Period.YEARLY` enum 만 추가하고 미구현 — DAILY 분리 처리

- **위험**: enum 에 YEARLY 노출 → UseCase.execute(period=YEARLY) 호출 시 미구현. 또는 누군가 DAILY 를 본 UseCase 로 호출
- **결정**: `IngestPeriodicOhlcvUseCase.execute` 에서 `if period is Period.DAILY: raise ValueError("DAILY 는 IngestDailyOhlcvUseCase 사용")` + `if period is Period.YEARLY: raise NotImplementedError("ka10094 미구현 — 향후 P2 chunk")` 명시. enum 자체는 DAILY 포함하지 않거나 (4 값) 별도로 (3 값 — WEEKLY/MONTHLY/YEARLY) 정의
- **검증**: 단위 테스트 — `period=DAILY` ValueError / `period=YEARLY` NotImplementedError

### H-4 — `dt` 의미 가설 (주 시작 / 달 첫 거래일)

- **위험**: ka10082 응답 `dt` 가 주 시작일(월) 인지 종료일(금) 인지 운영 검증 미완료. ka10083 도 동일
- **결정**: 본 chunk 에서는 **"기간의 시작일"** 가설로 적재. trading_date = `dt` 값 그대로. 운영 first-call 후 1주 모니터로 확정. 가설이 틀리면 트리거 cron 시간 / DB 의미만 갱신 (스키마 변경 없음)
- **검증**: ka10082/83 plan doc § 10.3 운영 검증 항목으로 등록. 본 chunk DoD 에서는 가설 명시 + 검증 미완 표기

### H-5 — R1 정착 패턴 적용 누락 위험

- **위험**: 신규 service / router 가 R1 의 5가지 패턴을 빠뜨릴 가능성:
  1. errors `list` → `tuple` (mutable container 노출 제거)
  2. `StockMasterNotFoundError(ValueError)` + subclass first except
  3. `fetched_at: datetime` non-Optional (DTO + ORM)
  4. `only_market_codes max_length=2` (pattern={1,2} 일치)
  5. NXT path `except Exception` 격리 + 의도 주석 (partial-failure)
- **결정**: 본 chunk 는 신규 service 추가지만 **patterns 1~5 모두 처음부터 적용**. ted-run 1차 리뷰가 검증
- **검증**:
  - 단위 테스트 — `result.errors` 가 tuple 인지 (`assert type(result.errors) is tuple`)
  - 단위 테스트 — `except StockMasterNotFoundError` first 순서 invariant 회귀
  - DTO 단위 — `RowOut.fetched_at` non-Optional + ORM 동기화
  - DTO 단위 — `only_market_codes max_length=2` (3건 시 422)

### H-6 — chart.py 응답 list 키 분기

- **위험**: ka10081 의 `KiwoomChartClient` 가 단일 메서드 fetch_daily 만 사용 — `stk_dt_pole_chart_qry` 키 hardcode. fetch_weekly/monthly 도 같은 클래스에 추가 시 list 키 추출 로직 분기 필요
- **결정**: 메서드 별로 `XXXChartResponse.model_validate(page.body)` → `parsed.<list_key>` 직접 attribute 접근 (Pydantic). 공통 helper 안 만듦 — ka10081 부분 재작성 안 함
- **검증**: chart.py 의 `fetch_daily` 변경 0 줄 (회귀 0). fetch_weekly/monthly 만 신규

### H-7 — Scheduler cron 시간 충돌

- **위험**: 기존 cron — `ohlcv_daily` (KST 18:30 추정), `daily_flow`, `stock_master_*`, `sector_*`, `stock_fundamental_*`. weekly (금 19:00) 와 monthly (매월 1일 03:00) 가 기존 job 과 시간 겹칠 위험
- **결정**: weekly = 금 19:00 (daily 18:30 후 30분 여유), monthly = 매월 1일 KST 03:00 (한밤 — 다른 job 0). KRX 2초 rate limit 고려해 코루틴 직렬화 (asyncio.Lock 글로벌)
- **검증**: 통합 테스트에서 daily + weekly 가 동시 실행 안 함 (max_instances=1, coalesce=True). cron 충돌 시 plan doc 에 시간 재조정

---

## 5. DoD (Definition of Done)

### 5.1 C-3α DoD

**코드**:
- [ ] Migration 009/010/011/012 — 4 테이블 (UniqueConstraint + idx)
- [ ] StockPriceWeeklyKrx / StockPriceWeeklyNxt / StockPriceMonthlyKrx / StockPriceMonthlyNxt ORM (`_DailyOhlcvMixin` 재사용)
- [ ] `Period(StrEnum) = WEEKLY/MONTHLY/YEARLY` (또는 DAILY 포함 4값 — H-3 결정)
- [ ] `StockPricePeriodicRepository.upsert_many` (period+exchange dispatch — 4 모델 매핑)
- [ ] `KiwoomChartClient.fetch_weekly` / `fetch_monthly` (api_id="ka10082"/"ka10083", list 키 분기)
- [ ] `WeeklyChartRow` / `MonthlyChartRow` / `WeeklyChartResponse` / `MonthlyChartResponse` Pydantic

**테스트**:
- [ ] `test_chart_adapter.py` 확장 — fetch_weekly / fetch_monthly 응답 list 키 + 페이지네이션 + 에러
- [ ] `test_stock_price_periodic_repository.py` 신규 — upsert / period dispatch / unique constraint
- [ ] testcontainers up/down 4 마이그레이션 사이클 PASS (H-1)
- [ ] 822 → 880 cases / coverage ≥ 92% 유지

**Verification 5관문**:
- [ ] mypy --strict 0 errors
- [ ] ruff check + format clean
- [ ] pytest 전건 PASS
- [ ] coverage ≥ 92%
- [ ] 1차 리뷰 (sonnet) PASS

**문서**:
- [ ] CHANGELOG: `feat(kiwoom): Phase C-3α — 주/월봉 OHLCV 인프라 (Migration 009-012 + Period enum + Periodic Repository)`
- [ ] STATUS.md § 0 / § 1 / § 3 / § 5 / § 6 갱신
- [ ] ADR § 23 — C-3α 결정 7건 (Migration 분리 / Mixin 재사용 / Period enum 범위 / list 키 분기 / R1 패턴 사전 적용)

---

### 5.2 C-3β DoD

**코드**:
- [ ] `IngestPeriodicOhlcvUseCase` (`ohlcv_periodic_service.py`) — period dispatch (WEEKLY/MONTHLY/YEARLY 분기, DAILY ValueError, YEARLY NotImplementedError)
- [ ] `RefreshOnePeriodicOhlcvUseCase` (단건 갱신, R1 정착 — except StockMasterNotFoundError first / errors tuple / NXT Exception 격리)
- [ ] `routers/ohlcv.py` 확장 — 4 path (단건/일괄 × weekly/monthly). DTO `errors: tuple[str, ...]` / `fetched_at: datetime` non-Optional / `only_market_codes: ... max_length=2`
- [ ] `weekly_ohlcv_job.py` (금 KST 19:00) + `monthly_ohlcv_job.py` (매월 1일 KST 03:00)
- [ ] `scheduler.py` 의 lifespan — weekly/monthly job 등록

**테스트**:
- [ ] `test_ohlcv_periodic_service.py` 신규 — 단건 / 일괄 / period dispatch / NXT 가드 / inactive / nxt_enable / R1 invariant (errors tuple / except 순서)
- [ ] `test_ohlcv_router.py` 확장 — weekly/monthly 4 path + R1 contract (errors tuple / fetched_at / 422 max_length=2)
- [ ] period dispatch — `period=DAILY` ValueError / `period=YEARLY` NotImplementedError (H-3)
- [ ] R1 invariant 회귀 (H-5) — `except StockMasterNotFoundError` first / `errors` tuple / `fetched_at` non-None / `max_length=2`
- [ ] 880 → 950 cases / coverage ≥ 92% 유지

**Verification 5관문**:
- [ ] mypy --strict / ruff / pytest / coverage / 1차 리뷰 PASS

**문서**:
- [ ] CHANGELOG: `feat(kiwoom): Phase C-3β — 주/월봉 OHLCV 자동화 (UseCase + Router 4 path + Scheduler 금 19:00 / 월 03:00)`
- [ ] STATUS.md § 0 / § 1 / § 2 (ka10082/83 → 완료) / § 3 / § 5 / § 6
- [ ] HANDOFF.md — C-3 묶음 종료 (다음 chunk = C-backfill / Phase D 진입)
- [ ] ADR § 24 — C-3β 결정 (UseCase period dispatch / cron 시간 / R1 패턴 적용 결과)
- [ ] `master.md` § 12 — `dt` 의미 가설 + 운영 first-call 검증 항목 등록

---

## 6. 다음 chunk (C-3 이후)

| 순위 | chunk | 근거 | 예상 규모 |
|------|-------|------|-----------|
| 1 | **C-backfill** — `scripts/backfill_ohlcv.py --period {daily|weekly|monthly}` CLI | C-1β/C-2β/C-3β 통합 마무리 + 운영 미해결 이슈 4건 (페이지네이션 빈도/3년 시간/NUMERIC magnitude/sync 시간) 일괄 해소 | CLI 1 + 시간 측정 |
| 2 | KOSCOM 공시 수동 cross-check | dry-run § 20.4 가설 B 최종 확정 (코드 변경 0) | 수동 1~2건 |
| 3 | ka10094 (년봉, P2) | C-3 와 동일 패턴 — Migration 4 + UseCase YEARLY 분기 활성화 | Migration 1 + ~200줄 |
| 4 | Phase D 진입 — ka10080 분봉 | 대용량 파티션 결정 선행 | 신규 도메인 + 파티션 전략 |

---

## 7. 진행 흐름 (체크리스트)

### 7.1 C-3α 진행

- [x] plan doc 본 § 검토 + 사용자 승인
- [x] `/ted-run` C-3α 실행 (TDD → 구현 → 리뷰 → Verification → ADR/CHANGELOG/STATUS/HANDOFF → commit)
- [x] commit 메시지: `feat(kiwoom): Phase C-3α — 주/월봉 OHLCV 인프라 (Migration 009-012 + Period enum + Periodic Repository)`
- [ ] 사용자 검토 후 push (요청 시만)

### 7.2 C-3β 진행

- [ ] C-3α PASS 확인 후 진입
- [ ] `/ted-run` C-3β 실행
- [ ] commit 메시지: `feat(kiwoom): Phase C-3β — 주/월봉 OHLCV 자동화 (UseCase + Router 4 path + Scheduler 금 19:00 / 월 03:00)`
- [ ] STATUS.md § 2 ka10082/83 완료 이동
- [ ] HANDOFF.md C-3 묶음 종료 갱신
- [ ] 사용자 검토 후 push

---

_C-3 = ka10082/83 신규 도메인. ka10081 패턴 ~95% 복제 + R1 정착 패턴 사전 적용. α (인프라) → β (자동화) → C-backfill → ka10094 (P2) → Phase D._
