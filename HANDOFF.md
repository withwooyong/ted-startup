# Session Handoff

> Last updated: 2026-05-09 (KST) — **backend_kiwoom A1 ~ A3-γ + F1 + B-α/β + B-γ-1/2 + C-1α/β + C-2α 완료 — Phase C-2 인프라 진입, 누적 15 chunk, 커밋 대기**
> Branch: `master` (uncommitted — Step 5 커밋 진행 예정)
> 이전 마일스톤: `993874c` — Phase C-1β 자동화
> 세션 시작점: `993874c` 직후 (이번 세션 C-2α 인프라)

## Current Status

backend_kiwoom **Phase A 100% + Phase B 100% + Phase C-1 100% + Phase C-2α (ka10086 인프라)**. 백테스팅 시그널 보강 (투자자별/외인/신용) 인프라 — Migration 007 (`stock_daily_flow`) + StockDailyFlow ORM + Repository + KiwoomMarketCondClient.fetch_daily_market + DailyMarketDisplayMode enum + `_strip_double_sign_int` (가설 B) + ExchangeType 길이 invariant. 자동화 (UseCase + Router + Scheduler) 는 **C-2β** 에서.

| 단계 | 커밋 | 범위 |
|------|------|------|
| A1~A3-γ + F1 | (생략) | 인증 / 트랜스포트 / 섹터 마스터 |
| B-α | `bf9956a` | ka10099 종목 마스터 + StockMasterScheduler |
| B-β | `abce7e0` | ka10100 단건 gap-filler / lazy fetch |
| B-γ-1 | `a287172` | ka10001 펀더멘털 인프라 |
| B-γ-2 | `56dbad9` | ka10001 펀더멘털 자동화 |
| C-1α | `a98e37b` | ka10081 OHLCV 인프라 |
| C-1β | `993874c` | ka10081 OHLCV 자동화 |
| **C-2α** | **(이번 세션)** | ka10086 일별 수급 인프라 |

**누적 결과**: **760 tests passed / coverage 93.43%** / 적대적 이중 리뷰 누적 PASS (CRITICAL/HIGH 0건). **Phase C 절반 완성**.

## Completed This Session

### Phase C-2α — ka10086 일별 수급 인프라

- 자동 분류: **계약 변경 (contract)** + `--force-2b` 적대적 리뷰 강제
- 1R: HIGH 0 / MEDIUM 3 (2a 1 + 2b 2) / LOW 9 → 3건 즉시 적용 + 회귀 4 추가 → **2R 진입 없이 PASS**
- 사용자 결정: chunk 분할 / 가설 B 이중 부호 / cron 19:00 / indc_mode QUANTITY / OHLCV 미적재

**신규/수정 파일 (코드 6 + 테스트 5)**

- `app/application/constants.py` (확장) — `DailyMarketDisplayMode` StrEnum + `EXCHANGE_TYPE_MAX_LENGTH=4` Final + import 시점 fail-fast (2b-M2)
- `migrations/versions/007_kiwoom_stock_daily_flow.py` (신규) — Migration 007 (KRX/NXT 분리, FK CASCADE, 인덱스 3개)
- `app/adapter/out/persistence/models/stock_daily_flow.py` (신규) — `StockDailyFlow` ORM (13 도메인 + 메타)
- `app/adapter/out/persistence/models/__init__.py` (수정) — export 추가
- `app/adapter/out/kiwoom/_records.py` (신규):
  - `DailyMarketRow` Pydantic 22 필드 (max_length=32 강제)
  - `DailyMarketResponse` wrapper
  - `NormalizedDailyFlow` slots dataclass (OHLCV 8 무시)
  - `_strip_double_sign_int` 가설 B 헬퍼
- `app/adapter/out/kiwoom/mrkcond.py` (신규) — `KiwoomMarketCondClient.fetch_daily_market`:
  - C-1α 2R H-1 cross-stock pollution 차단 (base code 비교)
  - flag-then-raise-outside-except (B-β 1R 2b-H2)
  - response message echo 차단 (B-α/B-β M-2)
- `app/adapter/out/persistence/repositories/stock_daily_flow.py` (신규) — `StockDailyFlowRepository`:
  - `_SUPPORTED_EXCHANGES = {KRX, NXT}` 화이트리스트 (2b-M1)
  - upsert_many ON CONFLICT 명시 update_set 16 항목 (B-γ-1 2R B-H3)
  - trading_date == date.min 자동 skip
  - find_range — exchange 필터 + asc 정렬 + start>end / SOR → ValueError

**신규 테스트 5 파일 / 66 cases**
- `tests/test_daily_market_display_mode.py` (7 — 6 신규 + 1 회귀)
- `tests/test_strip_double_sign_int.py` (23 — 가설 B + BIGINT overflow + 혼합/이중 부호 + edge cases)
- `tests/test_migration_007.py` (8 — 테이블/UNIQUE/FK/인덱스/컬럼/server_default/CASCADE/downgrade)
- `tests/test_stock_daily_flow_repository.py` (13 — 10 신규 + 3 회귀)
- `tests/test_kiwoom_mrkcond_client.py` (15)

**1R 적대적 이중 리뷰 fix 매핑**
| ID | 발견 | 적용 |
|---|------|------|
| 2a-M1 | test_migration_007 BIGINT 11→9 주석 오타 | 주석 정정 |
| 2b-M1 | SOR Repository silent 영속화 | `_SUPPORTED_EXCHANGES` 화이트리스트 + ValueError + 회귀 3 |
| 2b-M2 | exchange VARCHAR(4) silent truncation | `EXCHANGE_TYPE_MAX_LENGTH=4` import 시점 fail-fast + 회귀 1 |

**문서**
- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 18 (C-2α 결정 + 1R 매핑 + Defer 9 + 다음 chunk)
- `CHANGELOG.md` prepend (이번 세션)

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | **Phase C-2β (UseCase + Router + Scheduler + Lifespan)** | pending | C-1β 패턴 차용. 가설 B / R15 / NUMERIC magnitude 등 운영 dry-run 후 확정 항목 다수 |
| 2 | 운영 dry-run | pending | α/β/A3/B-α/β/γ + C-1α/β + C-2α 통합 검증 — 가설 B 정확성, R15 단위, NUMERIC magnitude 분포, OHLCV cross-check (ka10081 vs ka10086) |
| 3 | Phase C-3 (ka10082/83 주봉/월봉, P1) | pending | 같은 chart endpoint, KiwoomChartClient 메서드 추가 |
| 4 | Phase D~G | pending | 시그널 백테스팅 / 결과 / 운영 |

## Key Decisions Made (이번 세션)

- **chunk 분할** — C-2α 인프라 + C-2β 자동화 (B-γ-1/2, C-1α/β 패턴 일관)
- **가설 B 이중 부호** — `--714` → -714. 운영 dry-run 후 raw 응답 + KOSCOM 공시 cross-check 로 확정
- **indc_mode 디폴트 QUANTITY** — 백테스팅 시그널 다른 종목 비교 안정적
- **OHLCV 중복 적재 안 함** — ka10081 정답. ka10086 의 OHLCV 8 필드 (open_pric ~ amt_mn) 미적재
- **cron = KST mon-fri 19:00** — ka10081 18:30 의 30분 후. C-2β 에서 적용
- **SOR Repository 차단** (2b-M1) — Phase D 까지 KRX/NXT 만 영속화. silent merge 위험 차단
- **ExchangeType 길이 invariant** (2b-M2) — VARCHAR(4) silent truncation 차단. 신규 거래소 추가 시 import 시점 fail-fast

## Known Issues

- **가설 B 정확성 미확정** — `--714` → -714 가설. 운영 raw 응답 측정 + KOSCOM cross-check 후 확정 (잘못 처리 시 net 매매 부호 반전 → 백테스팅 시그널 정반대 동작)
- **R15 외인/기관/개인 순매수 단위** — `for_netprps` / `orgn_netprps` / `ind_netprps` 가 indc_tp 무시 항상 수량인지 운영 검증 필요
- **OHLCV cross-check** — ka10081 vs ka10086 의 같은 날 close_price 가 다르면 어느 source 정답? Phase H 데이터 품질 단계
- **NUMERIC(8,4) magnitude 가드 부재** — credit_rate / foreign_rate / foreign_weight 단위 변경 시 트랜잭션 abort cascading 위험. C-2β 또는 운영 dry-run 후 결정
- **idx_daily_flow_exchange cardinality** — KRX/NXT 2개 값만 → planner 가 sequential scan 선호 가능성. EXPLAIN 측정 후 Phase F 결정
- **혼합/3중 부호 운영 가시성** (`+++714` / `--+714` 등) — 모두 silent None. structlog warning 카운터 또는 raw_response 측정 후 결정
- **C-1α/β 알려진 이슈 상속** — NUMERIC magnitude / list cap / MappingProxyType / chart.py private import / GET 라우터 익명 공개 / date.today() KST 명시
- **B-γ-2 알려진 이슈 상속** — target_date 무한 / errors list 무제한 / GET /latest 익명 공개

## Context for Next Session

### 사용자의 원래 의도 / 목표
backend_kiwoom Phase C-2 (백테스팅 시그널 보강 — 투자자별/외인/신용) 진행. C-2α 인프라 완성, 다음은 C-2β 자동화 또는 운영 dry-run.

### 선택된 접근 + 이유
- **chunk 분할 + ted-run 풀 파이프라인**: B-γ-1/2, C-1α/β, C-2α 패턴 일관. 인프라/자동화 분리로 적대적 리뷰 부담 감소
- **B-α/β/γ + C-1α/β 패턴 mechanical 차용**: 22 필드 → 13 도메인 영속화 (OHLCV 미적재) / KRX/NXT 분리 row / per-(stock,exchange) 격리는 C-2β 에서
- **2R 적대적 리뷰 (--force-2b)**: 본 chunk 도 1R PASS (CRITICAL/HIGH 0). 이전 chunk 학습 효과 누적
- **Quality-First** (장애 없이 / 정확한 구조로 / 확장 가능)

### 사용자 제약 / 선호
- 한글 커밋 메시지 (~/.claude/CLAUDE.md 글로벌 규칙)
- 푸시는 명시적 요청 시만 (커밋과 분리)
- 큰 Phase 는 chunk 분할 후 ted-run 풀 파이프라인 (메모리)
- 진행 상황 가시화 — 체크리스트 + 한 줄 현황

### 다음 세션 진입 시 결정 필요
사용자에게 옵션 확인 권장:
1. **Phase C-2β (UseCase + Router + Scheduler + Lifespan)** — C-1β 패턴 차용. lazy fetch (c) batch fail-closed 적용. 진입 전 결정: NUMERIC magnitude 가드, idx_daily_flow_exchange 복합 인덱스 전환, indc_mode 변경 정책
2. **운영 dry-run** — α/β/A3/B-α/β/γ + C-1α/β + C-2α 통합 검증. 가설 B 정확성 + R15 단위 + NUMERIC magnitude 분포 + OHLCV cross-check
3. **Phase C-3 (ka10082/83 주봉/월봉, P1)** — 같은 chart endpoint, KiwoomChartClient 메서드 추가

## Files Modified This Session

이번 세션 한정 (커밋 대기):
```
docs/ADR/ADR-0001-backend-kiwoom-foundation.md     | § 18 추가
CHANGELOG.md                                        | prepend (C-2α)
HANDOFF.md                                          | 전체 갱신
src/backend_kiwoom/app/application/constants.py                            (확장)
src/backend_kiwoom/migrations/versions/007_kiwoom_stock_daily_flow.py      (신규)
src/backend_kiwoom/app/adapter/out/persistence/models/stock_daily_flow.py  (신규)
src/backend_kiwoom/app/adapter/out/persistence/models/__init__.py          (수정)
src/backend_kiwoom/app/adapter/out/kiwoom/_records.py                      (신규)
src/backend_kiwoom/app/adapter/out/kiwoom/mrkcond.py                       (신규)
src/backend_kiwoom/app/adapter/out/persistence/repositories/stock_daily_flow.py (신규)
src/backend_kiwoom/tests/test_daily_market_display_mode.py                 (신규, 7 cases)
src/backend_kiwoom/tests/test_strip_double_sign_int.py                     (신규, 23 cases)
src/backend_kiwoom/tests/test_migration_007.py                             (신규, 8 cases)
src/backend_kiwoom/tests/test_stock_daily_flow_repository.py               (신규, 13 cases)
src/backend_kiwoom/tests/test_kiwoom_mrkcond_client.py                     (신규, 15 cases)
```

13 files changed (코드 6 신규 + 테스트 5 신규 + 문서 3 + __init__ 수정).
