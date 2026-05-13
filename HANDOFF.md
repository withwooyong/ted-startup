# Session Handoff

> Last updated: 2026-05-14 (KST) — Phase D-1 follow-up 풀 구현 (ted-run) 완료 / 컨테이너 재배포 + 5-12 백필 재호출 (E4) 다음 세션 대기.
> Branch: `master`
> Latest commit: `478efaa` (5-13 dead 가설 반증 + 신규 인시던트 3건 진단 + plan doc § 13 추가)
> 미푸시: 본 ted-run 풀 파이프라인 commit 1건 예정 — 사용자 push 명시 요청

## Current Status

**Phase D-1 follow-up 풀 구현 완료 — MaxPages cap 상향 + bulk insert 32767 chunk 분할** (ted-run 풀 파이프라인). 1R+2R 이중 리뷰 PASS + Verification 5관문 PASS + ADR § 41 신규. 코드 6 파일 + 테스트 5 (+13 cases) / Migration 0 / UseCase 변경 0.

### Pipeline 진행 현황

| Step | 상태 | 모델 | 비고 |
|------|------|------|------|
| 0. TDD | ✅ | sonnet | 5 신규/갱신 (4 기존 + 1 신규) — 7 cases red 확인 |
| 1. 구현 | ✅ | opus (메인 직접) | 6 파일 / Migration 0 / UseCase 변경 0 |
| 2a. 1차 리뷰 | ✅ PASS | sonnet | CRITICAL 0 / HIGH 0 / MEDIUM 2 (즉시 fix) / LOW 4 |
| 2b. 적대적 리뷰 | ✅ PASS | opus | CRITICAL 0 / HIGH 0 / MEDIUM 1 (즉시 fix) / LOW 4 |
| 3. Verification | ✅ PASS | sonnet | ruff clean / mypy strict 95 files / 1199 passed / cov **86.13%** |
| 4. E2E | ⚪ 생략 | — | UI 변경 0 |
| 5. Ship | ✅ ADR § 41 + 메타 3종 | — | 커밋 예정 / 푸시 보류 |

### 본 chunk 핵심 fix

1. `SECTOR_DAILY_MAX_PAGES = 10 → 40` (`chart.py:350`)
2. `DAILY_MARKET_MAX_PAGES = 40 → 60` (`mrkcond.py:53`)
3. `KiwoomMaxPagesExceededError(*, api_id, page, cap)` 시그니처 확장 + `_client.py:347` raise site 갱신
4. `_chunked_upsert(session, statement_factory, rows, *, chunk_size=1000) -> int` helper 신규 (`_helpers.py`)
   - **2a 2R M-2 fix**: docstring 에 "factory 는 stateless 보장 필수" 명시
   - **2b 2R M-1 fix**: `n_cols × chunk_size > 32767` 시 ValueError fail-fast (미래 schema growth silent breakage 차단)
5. `SectorPriceDailyRepository.upsert_many` → `_chunked_upsert` 호출 (8 col × 1000 = 8000 args/chunk)
6. `StockDailyFlowRepository.upsert_many` → 동일 패턴 (12 col × 1000 = 12000 args/chunk)

### 본 chunk 테스트 변경 (+13 cases)

| 파일 | 신규/갱신 | cases |
|------|----------|-------|
| `tests/test_kiwoom_chart_client.py` | 갱신 | +2 (constant=40 / `(page=40, cap=40)` raise) |
| `tests/test_kiwoom_mrkcond_client.py` | 갱신 | +2 (constant=60 / `(page=60, cap=60)` raise) |
| `tests/test_repository_chunked_upsert.py` | **신규** | 7 (empty / 1 row / 999 / 1001 / 5500 / chunk_size=500 / n_cols×size > 32767 ValueError) |
| `tests/test_sector_price_repository.py` | 갱신 | +1 (5500 row × 8 col chunk 분할 안전 — testcontainers PG16) |
| `tests/test_stock_daily_flow_repository.py` | 갱신 | +1 (3000 row × 12 col 동일 패턴) |

### 누적 메트릭

- 테스트: 1186 → **1199** (+13 / 100% green)
- coverage: **86.13%** (≥80% 통과)
- ruff: clean / mypy --strict: 95 files Success
- 25 endpoint: 15 / 25 (60%) — 신규 endpoint X
- 스케줄러: 12 그대로 — 신규 cron X
- 컨테이너: 12 scheduler 활성 (16 시간 healthy) — 본 chunk 재배포는 E4

## Completed This Session

| # | Task | 결과 | Files |
|---|------|------|-------|
| 1 | dead 재현 모니터 + 진단 (이전 chunk `478efaa`) | dead 반증 + 신규 인시던트 3건 + plan doc § 13 작성 | 5 / `478efaa` |
| 2 | **(E3) Phase D-1 follow-up ted-run 풀 파이프라인** | TDD (sonnet) + 구현 (opus 직접) + 이중 리뷰 + Verification 5관문 + ADR § 41 + 메타 3종 | 코드 6 + 테스트 5 + ADR 1 + 메타 3 / `<pending commit>` |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| **1** | **(E4) 컨테이너 재배포 + 5-12 운영 백필 재호출** | **다음 세션 1순위** | `docker compose build` + `docker compose up -d` → cap 상향 + chunk 분할 적용. sector_daily 64 sector + KOSDAQ ~1814 종목 재호출 (admin endpoint 호출) → 0 MaxPages / 0 InterfaceError 검증. ADR § 41.7 운영 결과 채움 |
| **2** | **F chunk — ka10001 NUMERIC overflow + sentinel WARN/skipped 분리** | E4 후 별도 ted-run | Migration 신규 (NUMERIC(8,4) precision 확대 — overflow 종목 값 분석 선행) + sentinel detect 종목 ERROR → WARN/skipped 분리 + result.errors full exception type/메시지 log 보강 |
| ~~**Pending #1 (이전)**~~ | ~~5-13 17:30 dead 재현 모니터~~ | ~~`478efaa` 종결 ✅~~ | 자연 발화 정상 |
| ~~**Pending #2 (이전)**~~ | ~~ka20006 60% 실패 follow-up~~ | ~~본 chunk 코드 fix 완료 ✅~~ | E4 운영 재호출 대기 |
| ~~**Pending #3 (이전)**~~ | ~~ka10086 KOSDAQ 1814 누락~~ | ~~본 chunk 코드 fix 완료 ✅~~ | E4 운영 재호출 대기 |
| **3** | **노출된 secret 4건 회전** | **전체 개발 완료 후** | API_KEY/SECRET revoke + Fernet 마스터키 회전 + DB 재암호화 + Docker Hub PAT revoke (ADR § 38.8 #6/#7). 절차서: [`docs/ops/secret-rotation-2026-05-12.md`](docs/ops/secret-rotation-2026-05-12.md) |
| **4** | `.env.prod` 의 `KIWOOM_SCHEDULER_*` 9 env 정리 + alias 추가 | 전체 개발 완료 후 | compose env override 로 우회 완료 |
| **5** | (5-19 이후) § 36.5 1주 모니터 측정 채움 | 대기 | 컨테이너 로그 기반 12 scheduler elapsed |
| **6** | Mac 절전 시 컨테이너 중단 → cron 누락 위험 | 사용자 환경 결정 | 절전 차단 또는 서버 이전 (ADR § 38.8 #1) |
| **7** | scheduler dead 진단 endpoint 정리 (`/admin/scheduler/diag` 유지/제거) | dead 가설 자연 재현 반증 후 | 운영 가치 평가 + ADR 신규 § 후보 (코드 변경 0) |
| 8 | D-1 follow-up: inds_cd echo 검증 / close_index Decimal 통일 / `backfill_sector` CLI | ADR § 39.8 | 운영 첫 호출 후 결정 |
| 9 | Phase F / G / H (순위/투자자별/통합) | 대기 | 신규 endpoint wave |
| 10 | Phase D-2 ka10080 분봉 (**마지막 endpoint**) | 대기 | 사용자 결정 (5-12) — 데이터량 부담. 대용량 파티션 결정 동반 |
| 11 | §11 포트폴리오·AI 리포트 (P10~P15) | 대기 | CLAUDE.md next priority — KIS + DART + OpenAI 기반 |

## Key Decisions Made (본 chunk)

1. **분류 = 계약 변경 (contract) + --force-2b 강제** — `KiwoomMaxPagesExceededError` 시그니처 확장 + Repository 트랜잭션 경계 변경. 사용자 메모리 [[feedback-keep-existing-workflow]] = backend_kiwoom 표준 1R+2R 일관.
2. **`_chunked_upsert` 시그니처 = `statement_factory` callback 패턴** — Repository 마다 다른 `update_set` / `index_elements` 를 closure 로 흡수. helper 는 chunk loop + rowcount 합산만 책임. caller 의 single `session.begin()` 트랜잭션 안에서 수행 → partial 실패 시 caller 가 rollback 결정 (원자성 유지).
3. **2b M-1 `n_cols × chunk_size > 32767` fail-fast 가드 채택** — `assert` 가 아닌 명시 `raise ValueError` (production -O 무력화 차단). 미래 schema growth 시 silent breakage 차단.
4. **chunk_size = 1000 보수치 유지** — 32767 / 평균 13 col ≈ 2520 안전. 1000 이 보수치 — 8/12/22 col 모두 안전. 큰 row count 시 chunk 분할 횟수만 증가 (성능 영향 작음).
5. **`KiwoomMaxPagesExceededError(*, api_id, page, cap)` keyword-only** — 기존 positional `str` 호출이 raise site 1곳 (`_client.py:347`) 만이라 함께 갱신. tests/test_*_router.py 의 mock outcome `error="..."` 는 actual raise 아니라 영향 없음 (2b 검증).
6. **ADR § 41 채택** (계획서 표기 § 42 → § 41 정합) — dead 가설 § 은 후속 별도 (코드 변경 0).
7. **운영 재호출은 E4 별도 chunk** — 본 chunk 는 코드만. 운영 5-12 sector_daily 64 + KOSDAQ 1814 재호출은 컨테이너 재배포 + admin endpoint 호출 별도 chunk.
8. **푸시 보류** — 본 chunk 커밋만. 사용자 명시 요청 시까지 push X (global CLAUDE.md 규칙).

## Known Issues

| # | 항목 | 출처 | 결정 |
|---|------|------|------|
| 13 | 일간 cron 실측 (운영 cron elapsed) | dry-run § 20.4 → § 36 / § 38 | 🔄 5-19 이후 측정 |
| 20 | NXT 우선주 sentinel 빈 row 1개 detection | § 32.3 + § 33.6 | LOW |
| **22** | `.env.prod` 의 `KIWOOM_SCHEDULER_*` 9 env 정리 | § 38.6.2' | **전체 개발 완료 후** |
| **23** | 노출된 secret 4건 회전 | § 38.8 #6/#7 | **전체 개발 완료 후** |
| **24** | Mac 절전 시 컨테이너 중단 → cron 누락 | § 38.8 #1 | 사용자 환경 결정 |
| ~~**26**~~ | ~~5-13 06:00/06:30/07:00 cron dead~~ | 5-13 17:30 재현 모니터 | ✅ **자연 재현 반증** (`478efaa`) |
| ~~**27**~~ | ~~ka20006 sector_daily 60% 실패~~ | 본 chunk 코드 fix 완료 | ✅ **코드 fix 완료** (`<this commit>`) — 운영 재호출 E4 |
| ~~**28**~~ | ~~ka10086 KOSDAQ 1814 누락~~ | 본 chunk 코드 fix 완료 | ✅ **코드 fix 완료** (`<this commit>`) — 운영 재호출 E4 |
| **29** | ka10001 stock_fundamental 7.2% 실패 (5-13 18:00) | 진단 chunk `478efaa` | **F chunk 별도** — Migration 신규 + WARN/skipped 분리 |

## Context for Next Session

### 다음 세션 진입 (E4) 시 즉시 할 일

```bash
# 1) 컨테이너 재빌드 + 재배포 (alembic 변경 0, 단순 컨테이너 교체)
cd /Users/heowooyong/cursor/learning/ted-startup/src/backend_kiwoom
docker compose build kiwoom-app
docker compose up -d kiwoom-app

# 2) 12 scheduler 활성 + /health 확인
docker compose ps
curl -sS http://localhost:8001/health
docker compose logs kiwoom-app --since 2m 2>&1 | grep -E "scheduler 시작|cron" | head -20

# 3) 5-12 sector_daily 재호출 (64 sector — 실패 sector_id 명시)
# 실패 sector_id 추출: 5-13 02:33~02:37 KST 로그의 sector_id 패턴 (1~25, 29, 32~48, 57, 102, 103, 105~108, ...)
# 또는 전체 sector bulk sync 재시도 (idempotent)
curl -sS -X POST -H "X-Admin-API-Key: $KIWOOM_ADMIN_API_KEY" "http://localhost:8001/api/kiwoom/sectors/ohlcv/daily/sync?alias=prod&base_date=2026-05-12"

# 4) 5-12 ka10086 KOSDAQ 1814 종목 재호출 (실패 종목 명시 또는 mrkt_tp=10 KOSDAQ 전체 재호출)
# 백그라운드 daily_flow 백필이 이미 진행 중일 수 있음 — 먼저 확인
docker compose logs kiwoom-app --since 5m 2>&1 | grep -E "ka10086.*완료|daily_flow.*완료|MaxPages" | tail -10

# 5) DB row count 검증 — 0 MaxPages / 0 InterfaceError 후
PGPASSWORD=kiwoom psql -h localhost -p 5433 -U kiwoom -d kiwoom_db -c "
SELECT trading_date, count(*) FROM kiwoom.sector_price_daily WHERE trading_date >= DATE '2026-05-11' GROUP BY trading_date ORDER BY trading_date;
SELECT trading_date, count(*) FROM kiwoom.stock_daily_flow WHERE trading_date >= DATE '2026-05-11' GROUP BY trading_date ORDER BY trading_date;
SELECT trading_date, count(*) FROM kiwoom.stock_price_krx WHERE trading_date >= DATE '2026-05-11' GROUP BY trading_date ORDER BY trading_date;
"

# 6) ADR § 41.7 운영 결과 채움 — page 분포 실측 / chunk_size 1000 elapsed 오버헤드 / sector grade 별 성공률
```

기대:
- sector_price_daily 5-12: 60 → **124 row** (0 failed)
- stock_daily_flow 5-12: 1038+ → **~4370 row** (KOSDAQ 1814 누락 회복)
- stock_price_krx 5-12: 2559 → **~4370 row** (별도 backfill 운영 필요 시)

### 사용자의 의도 (본 세션)

`/ted-run` 으로 Phase D-1 follow-up 풀 파이프라인 1순위 진행 → TDD + 구현 + 이중 리뷰 + Verification + ADR + 메타 = 표준 backend_kiwoom 워크플로우. 풀 사이클 ~3-5h 견적 그대로.

### 채택한 접근

1. **자동 분류 = 계약 변경 (contract) + --force-2b** — backend_kiwoom 표준 일관 (사용자 메모리 [[feedback-keep-existing-workflow]])
2. **TDD sub-agent (sonnet)** — 5 테스트 작성 (4 기존 + 1 신규) → 7 cases red 확인
3. **구현 메인 세션 (opus) 직접** — 6 파일 ~80줄 / 짧은 fix 모음이라 sub-agent 분할 불필요
4. **2a (sonnet) + 2b (opus) 병렬 sub-agent** — 독립 리뷰, 둘 다 PASS
5. **MEDIUM 3건 즉시 fix + 가드 테스트 1 case 추가** — silent breakage 차단
6. **Verification 5관문 직접** — ruff/mypy/pytest 병렬, 5관문 PASS
7. **ADR § 41 작성 + plan/메타 § 42 → § 41 정합화**
8. **푸시 보류** — 사용자 push 명시 요청 시까지

### 운영 위험 / 주의

- **본 chunk 머지 + 컨테이너 재배포 (E4)**: alembic 마이그레이션 없음 → 단순 컨테이너 재기동만. 12 scheduler 유지
- **운영 5-12 재호출 시 KRX rate limit**: sector_daily 64 + KOSDAQ ~1814 = ~1900 호출 × 2초 RPS 마진 ≈ 1시간+. 컨테이너 sync lock 으로 직렬화 안전
- **chunk_size 1000 보수치 운영 검증**: long-history sector (15년+) 의 실제 chunk 분할 횟수 + 단일 INSERT 대비 elapsed 오버헤드 — ADR § 41.7 운영 결과 표 채움

## Files Modified This Session (본 chunk = ted-run)

### 6 코드 (Migration 0)
- `src/backend_kiwoom/app/adapter/out/kiwoom/_client.py` — `KiwoomMaxPagesExceededError(*, api_id, page, cap)` 시그니처 + raise site
- `src/backend_kiwoom/app/adapter/out/kiwoom/chart.py` — `SECTOR_DAILY_MAX_PAGES = 10 → 40` + docstring 정합 (2a 2R M-1)
- `src/backend_kiwoom/app/adapter/out/kiwoom/mrkcond.py` — `DAILY_MARKET_MAX_PAGES = 40 → 60`
- `src/backend_kiwoom/app/adapter/out/persistence/repositories/_helpers.py` — `_chunked_upsert` 신규 + stateless docstring (2a 2R M-2) + col 가드 (2b 2R M-1)
- `src/backend_kiwoom/app/adapter/out/persistence/repositories/sector_price.py` — chunk 적용
- `src/backend_kiwoom/app/adapter/out/persistence/repositories/stock_daily_flow.py` — chunk 적용

### 5 테스트 (4 갱신 + 1 신규, +13 cases)
- `src/backend_kiwoom/tests/test_kiwoom_chart_client.py` (+2)
- `src/backend_kiwoom/tests/test_kiwoom_mrkcond_client.py` (+2)
- `src/backend_kiwoom/tests/test_repository_chunked_upsert.py` (**신규**, 7)
- `src/backend_kiwoom/tests/test_sector_price_repository.py` (+1, testcontainers PG16)
- `src/backend_kiwoom/tests/test_stock_daily_flow_repository.py` (+1, testcontainers PG16)

### 1 ADR 갱신
- `docs/adr/ADR-0001-backend-kiwoom-foundation.md` § 41 신규 (Phase D-1 follow-up 결과)

### 3 메타 갱신
- `src/backend_kiwoom/STATUS.md` § 0 / § 4 #27 #28 (resolved) / § 5 / § 6
- `HANDOFF.md` (본 파일)
- `CHANGELOG.md` prepend

### 4 plan/메타 § 42 → § 41 정합화
- `src/backend_kiwoom/docs/plans/endpoint-13-ka20006.md` § 13.2 + § 13.3 + § 13.5 + § 13.7
- (HANDOFF / STATUS / CHANGELOG 동일 sed)

### Verification 측정

- 빌드 (py compile): pytest collection 1199 PASS = import 정상
- ruff: All checks passed
- mypy --strict: Success — no issues in 95 source files
- pytest: 1199 passed / coverage 86.13% (≥80% 통과)
- 보안 스캔: ⚪ (계약 분류 자동 생략)
- 런타임: ✅ (FastAPI import + scheduler factory 가 pytest fixture 에서 검증됨)
- E2E: ⚪ (UI 변경 0)

---

_Phase D-1 follow-up chunk 풀 구현 완료. 운영 5-12 백필 재호출은 E4 별도 chunk — 컨테이너 재배포 후 sector_daily 64 + KOSDAQ ~1814 재호출 → 0 MaxPages / 0 InterfaceError 검증 → ADR § 41.7 운영 결과 채움._
