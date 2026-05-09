# phase-c-backfill-ohlcv.md — Phase C-backfill (OHLCV 통합 백필 CLI)

## 0. 메타

| 항목 | 값 |
|------|-----|
| chunk 명 | **C-backfill** (OHLCV 통합 백필) |
| 범위 | `scripts/backfill_ohlcv.py` 신규 CLI — daily/weekly/monthly period dispatch |
| 분할 | **단일 chunk** — CLI 1개 + 테스트 |
| 선행 chunk | C-1β (`993874c`) / C-3α (`8fcabe4`) / C-3β (`2d4e2ae`) 모두 완료 |
| 우선순위 | **P1** — Phase C 의 운영 미해결 4건 일괄 해소 (페이지네이션/3년 시간/NUMERIC magnitude/sync 시간) |
| 분류 | **일반 기능 (general)** — scripts 신규, 보안/계약/Migration 변경 없음 |
| 운영 실측 | **본 chunk 범위 외** — CLI 코드 + 단위/통합 테스트만. 실측은 사용자 수동 실행 후 별도 결과 정리 |
| daily_flow (ka10086) 백필 | **본 chunk 범위 외** — 별도 후속 chunk |
| 관련 plan doc | [`endpoint-06-ka10081.md`](./endpoint-06-ka10081.md) § 6.5 (BackfillDailyOhlcvUseCase 초안) |

> **본 doc 의 역할**: chunk 단위 응집 정보 (영향 범위 / self-check / DoD). CLI 인자 명세 / 알고리즘은 본 § 3 에 직접 명시.

---

## 1. 목적

**3년 OHLCV 백필 스크립트** — Phase C-1β/C-3β 의 daily/weekly/monthly cron 진입 전 또는 운영 신규 종목 추가 시점에 과거 시계열을 일괄 적재. 또한 운영 미해결 4건의 정량화 측정 도구로 사용:

1. **페이지네이션 빈도** — ka10081 일봉 1 페이지 ~600 거래일 가정 vs 실측 (3년 = 750 거래일 → 2 페이지 추정)
2. **3년 백필 시간** — active 3000 종목 × 3년 daily / 156 weekly / 36 monthly. KRX rate-limit 2초 직렬화 가정 시 6,000~10,000초 (1.5~3시간) 추정
3. **NUMERIC(8,4) magnitude 분포** — turnover_rate / credit_rate / foreign_rate / foreign_weight 의 실제 값 분포. 한도 초과 시 컬럼 확장 결정
4. **active 3000 + NXT 1500 sync 시간** — daily cron 의 일별 sync 실측 (현재 30~60분 추정)

**본 chunk 의 산출물**: CLI 그 자체 + dry-run mode (DB 미적재, 시간/페이지 추정만) + 단위/통합 테스트. 실제 운영 실측은 사용자 환경 (실제 키움 자격증명 + 운영 DB) 에서 추후 수동 실행.

---

## 2. 범위 외 (Out of Scope)

- **daily_flow (ka10086) 백필** — 별도 후속 chunk. ka10086 은 indc_mode + 다른 컬럼 구조라 통합 시 dispatch 복잡. 단독 처리 우선
- **운영 실측 자체** — 사용자 수동 실행. 본 chunk 는 CLI 가 실측 가능한 도구를 제공하기까지
- **NUMERIC magnitude 컬럼 확장** — 실측 후 필요 시 별도 Migration chunk
- **CLI 의 KRX 직접 호출 (인증 우회)** — 메모리: 2026-04 KRX 전면 인증화. 본 CLI 는 키움 API 만 사용 (ka10081/82/83) — KRX 의존 없음
- **resume 의 분산 lock** — 단일 프로세스 가정. 동시 다중 실행 차단은 사용자 운영 책임
- **백필 진행률을 metrics 로 export** — Prometheus 등 별도 chunk

---

## 3. CLI 명세

### 3.1 인자

```bash
python scripts/backfill_ohlcv.py \
    --period {daily,weekly,monthly}     # 필수
    --alias <kiwoom_credential_alias>   # 필수
    [--years N]                          # 디폴트 3
    [--start-date YYYY-MM-DD]            # 명시 시 --years 무시
    [--end-date YYYY-MM-DD]              # 디폴트 today
    [--only-market-codes 0,10,...]       # 디폴트 전체 5 시장 (KOSPI/KOSDAQ/KONEX/ETN/REIT)
    [--only-stock-codes 005930,000660]   # 디폴트 active 전체. 디버그 용
    [--dry-run]                          # 종목 수 + 페이지 추정 + 시간 추정만, DB 미적재
    [--resume]                           # 마지막 적재된 종목 이후부터 재개 (DB 의 max(trading_date) 기반)
    [--max-stocks N]                     # 디버그 — 처음 N 종목만 처리
    [--log-level {DEBUG,INFO,WARNING}]   # 디폴트 INFO
```

### 3.2 동작 흐름

```
1. 인자 검증
   - period in {daily,weekly,monthly}
   - alias 비어있지 않음
   - start_date <= end_date (지정 시)
   - only_market_codes 가 StockListMarketType.value 화이트리스트
   - alias 가 DB 에 등록된 active 자격증명인지 (CLI 진입 시 즉시 검증)

2. settings + DB 연결 + KiwoomClient 빌드 (lifespan 없이 직접 컨텍스트)
   - get_settings()
   - TokenManager 직접 빌드 (alias 1개만 사용)
   - KiwoomChartClient 빌드

3. period 별 UseCase 결정
   - daily → IngestDailyOhlcvUseCase (chart_client, nxt_collection_enabled=settings.nxt_collection_enabled)
   - weekly/monthly → IngestPeriodicOhlcvUseCase

4. base_date 시계열 생성
   - end_date 부터 start_date 까지 역순 (한 번 호출에 1 페이지 = base_date 기준 과거 N건)
   - daily: end_date 1회 호출이면 ka10081 가 cont-yn=Y 로 페이지 자동 진행 → ~600 거래일 / 페이지
     → 3년이면 base_date=end_date 만 호출, max_pages=10 으로 충분 (예상 2 페이지)
   - weekly: 156 주봉 / 페이지 추정 → 1 페이지 충분
   - monthly: 36 월봉 → 1 페이지

5. 종목 순회
   - active stock 조회 (only_market_codes / only_stock_codes 필터)
   - --resume: stock_price_{period}_{exchange} 의 max(trading_date) 가 end_date 이상이면 skip
   - per stock per exchange (KRX → NXT) try/except — UseCase 의 _ingest_one 직접 호출 또는
     refresh_one 으로 재사용

6. 진행률 / summary
   - 진행률: 1초 단위 logger.info "처리 중 X/Y (X.X%)"
   - summary (종료 시):
     * total / success_krx / success_nxt / failed
     * 총 호출 수 / 페이지네이션 발생 빈도
     * 총 row 수
     * 소요 시간 / 평균 종목당 시간
     * NUMERIC magnitude 통계 (max(turnover_rate) 등) — period=daily 만

7. dry-run 모드
   - 위 5,6 의 actual call 을 mock — KiwoomChartClient.fetch_* 호출 안 함, DB upsert 안 함
   - 대신: 대상 종목 수 / 추정 페이지 / 추정 시간 (rate_limit × 호출수) 출력
```

### 3.3 종료 코드

- 0: 모든 종목 success (failed = 0)
- 1: 부분 실패 (failed > 0)
- 2: 인자 검증 실패 / alias 미등록
- 3: 시스템 오류 (DB 연결 실패 / settings 누락)

---

## 4. 영향 범위

### 4.1 신규 (3 파일)

| # | 파일 | 라인 추정 | 비고 |
|---|------|-----------|------|
| 1 | `scripts/backfill_ohlcv.py` | ~400 | argparse + main + period dispatch + dry-run + resume + summary |
| 2 | `tests/test_backfill_ohlcv_cli.py` | ~250 | argparse 단위 + period dispatch + dry-run + resume + 에러 격리 |
| 3 | `tests/test_backfill_ohlcv_integration.py` (선택) | ~150 | testcontainers + 키움 MockTransport + 실제 DB upsert 검증 |

### 4.2 수정 (0~1 파일)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `pyproject.toml` 또는 `Makefile` (선택) | `[project.scripts] backfill-ohlcv = "scripts.backfill_ohlcv:main"` 등록 (선택) |

### 4.3 문서 (3 파일)

| 파일 | 갱신 시점 |
|------|-----------|
| `STATUS.md` | C-backfill 완료 후 |
| `HANDOFF.md` | 본 chunk 종료 후 |
| `CHANGELOG.md` | 커밋 직전 prepend |
| `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 25 | 핵심 결정 + 1R 결과 + 운영 실측 자료 위치 |

---

## 5. 적대적 사전 self-check (H-1 ~ H-7)

### H-1 — `IngestDailyOhlcvUseCase.execute` 재사용 vs 직접 호출

- **위험**: CLI 가 `execute(*, base_date, only_market_codes)` 그대로 호출하면 active stock 전체 sync 이지만 base_date 가 과거이므로 1회 호출이 전체 3년 시계열 적재 (페이지네이션). 즉, 별도 backfill UseCase 불필요
- **결정**: 기존 UseCase 재사용 — `execute(base_date=end_date)`. ka10081 `_validate_base_date` 가 today - 365 cap → CLI 에서는 이 검증 우회 필요 (--years 3 의도)
- **해법**: CLI 가 직접 `IngestDailyOhlcvUseCase._ingest_one` 호출 (private 우회) 또는 `_validate_base_date` 우회 옵션 추가. 우회 옵션 추가가 깔끔
- **결정 (최종)**: `execute(*, base_date, only_market_codes, *, _skip_base_date_validation=False)` 키워드 추가. CLI 에서만 True. R1 정착 전용 옵션 — 운영에서는 안전 기본값 유지

### H-2 — resume 동작 정확성

- **위험**: --resume 이 max(trading_date) 만 본다면 부분 적재 종목 (예: 750 일자 중 600 만 적재됨) 의 누락 일자 미인식. 또는 KRX 만 적재된 종목의 NXT 누락
- **결정**: 본 chunk 의 resume 은 단순 모델 — `max(trading_date) >= end_date` 면 skip. 누락 일자 백필은 사용자가 별도 stock-code 리스트로 재실행. 복잡한 gap detection 은 별도 chunk
- **검증**: resume mode 에서 부분 적재 종목 → skip + warning 로그 (사용자 가시성)

### H-3 — Rate limit / 시간 추정 정확성

- **위험**: dry-run 시간 추정이 keyword="2초 rate limit × 호출 수" 만 보면 실제와 차이 (네트워크 RTT / 페이지네이션 / DB upsert 시간 무시)
- **결정**: dry-run 의 시간 추정은 lower-bound (rate_limit × 호출수). 상한 추정은 사용자 운영 실측 후 보정. 추정값에 ±50% margin 명시
- **검증**: `_estimate_seconds(stocks, exchanges, pages_per_stock)` 단위 테스트 — 입력별 추정값

### H-4 — KRX/NXT 양쪽 호출 시 NXT 활성 게이트

- **위험**: CLI 가 nxt_enable=False 종목까지 NXT 호출 시도 → 응답 에러 누적
- **결정**: UseCase 가 이미 stock.nxt_enable + settings.nxt_collection_enabled 게이트 — CLI 가 그대로 위임 (회귀 0)
- **검증**: 단위 테스트에서 nxt_enable=False 종목은 NXT 호출 0 검증

### H-5 — exit code 분기

- **위험**: failed > 0 인데 exit 0 (성공) 으로 간주되면 cron / Make / CI 가 실패 인지 못 함
- **결정**: § 3.3 — failed > 0 → exit 1. 인자 오류 → exit 2. 시스템 오류 → exit 3
- **검증**: 각 exit code 단위 테스트

### H-6 — DB 연결 / TokenManager 라이프사이클

- **위험**: CLI 는 lifespan 없이 직접 빌드 — 종료 시 graceful close 누락 시 connection leak 또는 alembic_version lock
- **결정**: `try/finally` 로 engine.dispose() + token revoke + KiwoomClient.close() 보장. lifespan 의 reset 로직은 CLI 에서 호출하지 않음 (singleton 영향 없음)
- **검증**: 통합 테스트에서 CLI 종료 후 connection 누수 0 검증

### H-7 — Settings 의 nxt_collection_enabled 영향

- **위험**: CLI 운영 시 settings.nxt_collection_enabled=False 면 NXT 종목 0 — 의도와 어긋남
- **결정**: CLI 는 settings 그대로 사용 (운영 정책 일관). NXT 강제 옵션 (`--force-nxt`) 추가 시 별도 chunk
- **검증**: dry-run 시 "NXT collection: enabled / disabled" 명시 출력

---

## 6. DoD (Definition of Done)

**코드**:
- [ ] `scripts/backfill_ohlcv.py` — argparse + main + period dispatch + dry-run + resume + summary + exit code
- [ ] `IngestDailyOhlcvUseCase.execute` 의 `_skip_base_date_validation` 키워드 추가 (H-1)
- [ ] `IngestPeriodicOhlcvUseCase.execute` 의 `_skip_base_date_validation` 키워드 추가 (H-1, 일관성)

**테스트**:
- [ ] `tests/test_backfill_ohlcv_cli.py` — argparse 검증 (10+ cases) / period dispatch / dry-run / resume / 에러 격리 / exit code (4 분기)
- [ ] (선택) `tests/test_backfill_ohlcv_integration.py` — testcontainers + 키움 MockTransport + DB upsert
- [ ] coverage `scripts/backfill_ohlcv.py` ≥ 80%
- [ ] 939 → 970+ cases / coverage ≥ 95% 유지

**Verification 5관문**:
- [ ] mypy --strict 0 errors
- [ ] ruff check + format clean
- [ ] pytest 전건 PASS
- [ ] coverage ≥ 95%
- [ ] 1차 리뷰 (sonnet) PASS

**문서**:
- [ ] CHANGELOG: `feat(kiwoom): Phase C-backfill — OHLCV 통합 백필 CLI (--period dispatch + dry-run + resume)`
- [ ] STATUS.md § 0 / § 1 / § 5 / § 6 갱신 (Phase C 90% → 95%)
- [ ] HANDOFF.md C-backfill 완료 단면
- [ ] ADR § 25 — C-backfill 결정 (CLI 인자 / dry-run / resume / `_skip_base_date_validation` 추가)
- [ ] `master.md` § 12 — 운영 실측 자료 위치 + 사용자 수동 실행 가이드

---

## 7. 진행 흐름 (체크리스트)

- [x] plan doc 본 § 검토 + 사용자 승인
- [x] `/ted-run` C-backfill 실행 (TDD → 구현 → 리뷰 → Verification → ADR/CHANGELOG/STATUS/HANDOFF → commit)
- [x] commit 메시지: `feat(kiwoom): Phase C-backfill — OHLCV 통합 백필 CLI (--period dispatch + dry-run + resume)`
- [x] 사용자 검토 후 push (요청 시만)
- [ ] (사용자 별도 작업) 운영 실측 — 100 종목 sample → 자료 정리

---

## 8. 운영 실측 (본 chunk 범위 외 — 사용자 수동 실행 가이드)

### 8.1 사전 준비

- 키움 자격증명 1개 등록 (alias 예: `backfill-prod`)
- DB 연결 (운영 PostgreSQL 또는 staging)
- `settings.nxt_collection_enabled=True` (NXT 시계열도 측정 시)

### 8.2 실측 시나리오

```bash
# 1. dry-run 으로 추정값 확인 (KOSPI 100 종목)
python scripts/backfill_ohlcv.py --period daily --years 3 --alias backfill-prod \
    --only-market-codes 0 --max-stocks 100 --dry-run

# 2. 실제 백필 (KOSPI 100 종목, 1년 — 짧게 시작)
python scripts/backfill_ohlcv.py --period daily --years 1 --alias backfill-prod \
    --only-market-codes 0 --max-stocks 100

# 3. 결과 분석
#    - summary 의 페이지네이션 빈도 / 평균 종목당 시간 / NUMERIC max
#    - DB query: SELECT COUNT(*), MAX(turnover_rate), MAX(credit_rate) FROM kiwoom.stock_price_krx;

# 4. 전체 active 3000 백필 (3년) — 추정 1.5~3시간
python scripts/backfill_ohlcv.py --period daily --years 3 --alias backfill-prod
```

### 8.3 실측 결과 정리 (별도 자료)

- `docs/operations/backfill-실측-{YYYY-MM-DD}.md` 신규 — 페이지네이션 / 시간 / NUMERIC 통계
- ADR § 25 (또는 § 26) 운영 검증 자료 링크 추가
- STATUS § 4 알려진 이슈 4건 → 해소 표기

---

_C-backfill = OHLCV 통합 백필 CLI. 단일 chunk + 운영 실측은 추후 사용자 수동. 다음 chunk = daily_flow 백필 또는 ka10094 (년봉) 또는 refactor R2._
