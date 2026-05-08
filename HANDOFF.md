# Session Handoff

> Last updated: 2026-05-08 (KST) — **backend_kiwoom A1 ~ A3-γ + F1 + B-α/β + B-γ-1/2 + C-1α 완료 — Phase C 진입, 누적 13 chunk, 커밋 대기**
> Branch: `master` (uncommitted — Step 5 커밋 진행 예정)
> 이전 마일스톤: `56dbad9` — Phase B-γ-2 펀더멘털 자동화 (Phase B 마무리)
> 세션 시작점: `56dbad9` 직후 (이번 세션 Phase C 진입)

## Current Status

backend_kiwoom **Phase A 100% + Phase B 100% + Phase C-1α (ka10081 OHLCV 인프라) 완료**. 백테스팅 OHLCV 코어 인프라 — Migration 005/006 + StockPriceKrx/Nxt + KiwoomChartClient.fetch_daily + ExchangeType enum + build_stk_cd 헬퍼 도입. 자동화 (UseCase + Router + Scheduler) 는 **C-1β** 에서.

| 단계 | 커밋 | 범위 |
|------|------|------|
| A1~A3-γ + F1 | (생략) | 인증 / 트랜스포트 / 섹터 마스터 |
| B-α | `bf9956a` | ka10099 종목 마스터 + StockMasterScheduler |
| B-β | `abce7e0` | ka10100 단건 gap-filler / lazy fetch |
| B-γ-1 | `a287172` | ka10001 펀더멘털 인프라 (Migration 004 + ORM + Repository + Adapter) |
| B-γ-2 | `56dbad9` | ka10001 펀더멘털 자동화 — Phase B 마무리 |
| **C-1α** | **(이번 세션)** | ka10081 OHLCV 인프라 — ExchangeType enum + build_stk_cd 헬퍼 + Migration 005/006 (KRX/NXT 분리) + _DailyOhlcvMixin + StockPriceRepository + KiwoomChartClient.fetch_daily + 2R H-1 cross-stock pollution 차단 |

**누적 결과**: **639 tests passed / coverage 93.44%** / 적대적 이중 리뷰 누적 CRITICAL 6 + HIGH 26 발견 → 전부 적용 → 0건 PASS. **Phase C 진입**.

## Completed This Session

### Phase C-1α — ka10081 일봉 OHLCV 인프라

- 자동 분류: **계약 변경 (contract)** + `--force-2b` 적대적 리뷰 강제
- 1R: HIGH 1 + MEDIUM 3 + LOW 2 → 2R 1 적용 + sonnet M-1/M-2 정정 + 회귀 4 추가 → 2R PASS
- 사용자 결정: **lazy fetch RPS = (c) batch + fail-closed** (ADR § 13.4.1 deferred 해소) / **chunk 분할 = C-1α (인프라) + C-1β (자동화)**

**확장/신규 파일 (코드 8 + 테스트 4)**

- `app/application/constants.py` (확장) — `ExchangeType` StrEnum (KRX/NXT/SOR) Phase C 첫 도입 (B-γ-1 ADR § 14.5 deferred 해소)
- `app/adapter/out/kiwoom/stkinfo.py` (확장) — `build_stk_cd(stock_code, exchange)` 헬퍼 — `_validate_stk_cd_for_lookup` 재사용 + suffix 합성
- `app/adapter/out/kiwoom/chart.py` (신규) — `KiwoomChartClient.fetch_daily` + `DailyChartRow`/`Response` Pydantic + `NormalizedDailyOhlcv` slots dataclass + 2R H-1 base code 메아리 검증
- `migrations/versions/005_kiwoom_stock_price_krx.py` (신규)
- `migrations/versions/006_kiwoom_stock_price_nxt.py` (신규) — KRX/NXT 분리 마이그레이션 (운영 토글)
- `app/adapter/out/persistence/models/stock_price.py` (신규) — `_DailyOhlcvMixin` + `StockPriceKrx` + `StockPriceNxt`
- `app/adapter/out/persistence/models/__init__.py` (수정) — export 추가
- `app/adapter/out/persistence/repositories/stock_price.py` (신규) — `StockPriceRepository`:
  - `_MODEL_BY_EXCHANGE` 분기 (KRX/NXT, SOR 은 ValueError)
  - `upsert_many` ON CONFLICT (stock_id, trading_date, adjusted) DO UPDATE
  - `trading_date == date.min` 빈 응답 row 자동 skip
  - 명시 update_set 11 항목 (B-γ-1 패턴 일관)

**신규 테스트 4 파일 / 50 cases**
- `tests/test_exchange_type.py` (7)
- `tests/test_kiwoom_chart_client.py` (20)
- `tests/test_stock_price_repository.py` (8)
- `tests/test_migration_005_006.py` (15 parametrize)

**문서**
- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 16 (C-1α 결정 + 1R/2R 매핑 + Defer 6 + C-1β 진입 결정)
- `CHANGELOG.md` prepend (이번 세션)

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | **Phase C-1β (UseCase + Router + Scheduler)** | pending | IngestDailyOhlcvUseCase + 라우터 (sync/refresh/조회) + OhlcvDailyScheduler (KST mon-fri 18:30) + lazy fetch (c) batch fail-closed 적용 |
| 2 | Phase C-2 (ka10086 일별 보강) | pending | 투자자별 + 외인 + 신용 — 백테스팅 시그널 핵심 (P0). 별도 endpoint path (`/api/dostk/mrkcond`) |
| 3 | Phase C-3 (ka10082/83 주봉/월봉, P1) | pending | 같은 chart endpoint, KiwoomChartClient 메서드 추가 |
| 4 | 운영 dry-run | pending | 키움 자격증명으로 α/β/A3/B-α/β/γ + C-1α 통합 검증 — 응답 stk_cd 메아리 동작 (suffix stripped/full), turnover_rate magnitude 분포, 페이지 row 수 |
| 5 | Phase D~G | pending | 시그널 백테스팅 / 결과 / 운영 |

## Key Decisions Made (이번 세션)

- **Phase C 진입 첫 chunk 는 인프라만** — Migration 005/006 + ORM + Repository + Adapter. 1,172줄 작업계획서를 인프라/자동화로 분할 (B-γ-1 패턴 일관)
- **lazy fetch RPS 보호 = (c) batch + fail-closed** (사용자 승인) — Phase C 적재 시 미지 종목 logger.warning + skip. ensure_exists 호출 자체 안 함. 코드 단순 + RPS 완전 제어
- **ExchangeType StrEnum 신규** (KRX/NXT/SOR) Phase C 첫 도입 — B-γ-1 ADR § 14.5 deferred 결정 해소
- **build_stk_cd 헬퍼** — 시계열 endpoint 공통 (ka10082/83/86/94 도 사용 예정)
- **KRX/NXT 물리 분리** — Migration 005 + 006 두 테이블, _DailyOhlcvMixin DRY. 운영 중 NXT 토글 가능
- **adjusted boolean PK 일부** — 같은 일자 raw + adjusted 두 row 동시 보유 (비교 검증용)
- **2R H-1 cross-stock pollution 차단** — `strip_kiwoom_suffix` 기반 base code 비교. page N 의 stk_cd 가 다른 종목으로 박혀와도 차단. base 비교 정책 — suffix stripped/동봉 양쪽 수용 (계획서 § 4.3 운영 미검증)
- **trading_date == date.min 빈 응답 표식** — chart.py to_normalized + Repository skip 양쪽 인지 (caller 안전망)

## Known Issues

- **NUMERIC(8,4) magnitude 가드 미적용** (1R 2b M-1 defer) — turnover_rate 가 운영 응답에서 magnitude 초과 시 DataError. 운영 dry-run 후 결정
- **stk_dt_pole_chart_qry list 길이 cap 미적용** (1R 2b M-2 defer) — 키움 ~600 row/page 가정 안전. 운영 검증 후 cap 적용 검토
- **`_MODEL_BY_EXCHANGE` mutable class attr** (1R 2b M-3 defer) — MappingProxyType 적용은 후속 chunk
- **chart.py 가 stkinfo private helper import** (1R 2b L-1 defer) — `_normalize.py` 별도 모듈 추출은 후속 chunk (ka10082/83 도 공유 시점)
- **응답 stk_cd 빈 string 통과 정책** (본 chunk H-1) — 키움이 root 에 stk_cd 항상 동봉하는지 운영 검증 후 strict 전환 검토
- **B-γ-2 알려진 이슈 상속** — target_date 무한 / errors list 무제한 / GET /latest 익명 공개 / `_safe_for_log` charset 부분 커버 / vendor non-numeric metric

## Context for Next Session

### 사용자의 원래 의도 / 목표
backend_kiwoom Phase B 완료 후 Phase C 진입 — OHLCV 시계열 백테스팅 본체. C-1α 인프라 완료, 다음은 C-1β 자동화 또는 C-2 (ka10086) 또는 운영 dry-run.

### 선택된 접근 + 이유
- **chunk 분할 + ted-run 풀 파이프라인**: 1,172줄 → C-1α (인프라, ~700줄) + C-1β (자동화). B-γ-1/B-γ-2 패턴 일관
- **B-α/β/γ 패턴 mechanical 차용**: KRX/NXT 분리 영속화는 master.md § 3.1 결정. _DailyOhlcvMixin 으로 ka10082/83/94 도 같은 mixin 차용 예정
- **2R 적대적 리뷰 (--force-2b)**: 모든 chunk 일관 적용. 본 chunk 는 H-1 (페이지네이션 cross-stock pollution) 발견 → base code 비교로 즉시 fix
- **Quality-First** (장애 없이 / 정확한 구조로 / 확장 가능)

### 사용자 제약 / 선호
- 한글 커밋 메시지 (~/.claude/CLAUDE.md 글로벌 규칙)
- 푸시는 명시적 요청 시만 (커밋과 분리)
- 큰 Phase 는 chunk 분할 후 ted-run 풀 파이프라인 (메모리)
- 진행 상황 가시화 — 체크리스트 + 한 줄 현황

### 다음 세션 진입 시 결정 필요
사용자에게 옵션 확인 권장:
1. **Phase C-1β (UseCase + Router + Scheduler)** — IngestDailyOhlcvUseCase + 라우터 (sync/refresh/조회) + OhlcvDailyScheduler. lazy fetch (c) batch fail-closed 적용. 진입 전 결정: nxt_collection_enabled settings flag, 백필 정책, target_date_range 검증
2. **Phase C-2 (ka10086 일별 보강 — 투자자별/외인/신용)** — 백테스팅 시그널 핵심 (P0). 별도 endpoint (`/api/dostk/mrkcond`)
3. **운영 dry-run** — α/β/A3/B-α/β/γ + C-1α 통합 검증

## Files Modified This Session

이번 세션 한정 (커밋 대기):
```
docs/ADR/ADR-0001-backend-kiwoom-foundation.md     | § 16 추가
CHANGELOG.md                                        | prepend (C-1α)
HANDOFF.md                                          | 전체 갱신
src/backend_kiwoom/app/application/constants.py                            (확장 — ExchangeType)
src/backend_kiwoom/app/adapter/out/kiwoom/stkinfo.py                       (확장 — build_stk_cd)
src/backend_kiwoom/app/adapter/out/kiwoom/chart.py                         (신규)
src/backend_kiwoom/app/adapter/out/persistence/models/stock_price.py       (신규)
src/backend_kiwoom/app/adapter/out/persistence/models/__init__.py          (수정)
src/backend_kiwoom/app/adapter/out/persistence/repositories/stock_price.py (신규)
src/backend_kiwoom/migrations/versions/005_kiwoom_stock_price_krx.py       (신규)
src/backend_kiwoom/migrations/versions/006_kiwoom_stock_price_nxt.py       (신규)
src/backend_kiwoom/tests/test_exchange_type.py                             (신규, 7 cases)
src/backend_kiwoom/tests/test_kiwoom_chart_client.py                       (신규, 20 cases)
src/backend_kiwoom/tests/test_stock_price_repository.py                    (신규, 8 cases)
src/backend_kiwoom/tests/test_migration_005_006.py                         (신규, 15 parametrize)
```

13 files changed (코드 8 + 테스트 4 + 문서 3).
