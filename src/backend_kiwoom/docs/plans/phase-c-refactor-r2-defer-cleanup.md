# phase-c-refactor-r2 — 1R Defer 5건 일괄 정리 (L-2 / E-1 / M-3 / E-2 / gap detection)

## 0. 메타

| 항목 | 값 |
|------|-----|
| 분류 | refactor (외부 API 동작 무변, 내부 정리 + CLI 정확도 향상) |
| 범위 | 5건 — service docstring / router 핸들러 / repository cast / deps docstring / 백필 CLI gap detection |
| 출처 | ADR-0001 § 24.5 (Defer 표) + § 25.6 (R2 chunk 명시). 1R Defer 의 후속 (R1 = `c3e0952`) |
| 선행 chunk | C-2δ (`8dd5727`) / C-4 ka10094 (`b75334c`) 완료 |
| 우선순위 | P1 — Phase D 진입 전 베이스 정리 (LOW 위험) |
| 선택 시점 | 2026-05-11 (사용자 결정 — STATUS § 5 #1) |
| 분량 추정 | ~400~500줄 (코드 5 + 테스트 3 + 문서 4) |

## 1. 목적

1R 에서 Defer 처리된 5건을 일괄 정리. C-4 (`b75334c`) 가 의도하지 않게 L-2 의 전제를 변경 (YEARLY 활성 → NotImplementedError 발생 경로 사라짐) — L-2 의 작업 정의가 변경됨. ADR § 24.5 원안의 "방어적 핸들러 추가" 는 dead branch 가 되므로 stale docstring 정리로 축소.

1. **L-2 stale docstring 정리** — C-4 후 docstring/주석에 남은 "YEARLY → NotImplementedError" 표현 5곳 정정. `_validate_period` dead branch (`service.py:395`) 는 defense-in-depth 로 유지
2. **E-1 ka10081 sync_ohlcv_daily KiwoomError 핸들러** — 동일 모듈 `refresh_ohlcv_daily` 와 동일 패턴 일관화 (B-β M-5)
3. **M-3 `# type: ignore[arg-type]` → `cast()`** — 2 Repository 의 `list(result.scalars().all())` 패턴 통일
4. **E-2 `_deps.py` reset_ docstring 정정** — 9개 함수 "테스트 전용" → "lifespan teardown + 테스트" (의도 명시)
5. **gap detection** — `compute_resume_remaining_codes` 가 일자별 검사로 동작. DB 내 trading_date union 을 영업일 calendar 로 사용 (외부 의존성 0)

다음 chunk (Phase D 분봉 / 업종일봉) 진입 전 1R 잔존 정리.

## 2. 범위 외 (Out of Scope)

- 외부 API contract 변화 (응답 status/body)
- 신규 endpoint / 신규 도메인 / 신규 Migration
- KRX 공식 휴장일 calendar 외부 패키지 도입 (사용자 결정 — DB union 방식)
- backfill CLI 의 다른 미해결 옵션 (NUMERIC magnitude / since_date edge / turnover_rate 음수 등)
- ADR § 24.5 원안의 "_do_sync / _do_refresh NotImplementedError → 501 핸들러" 추가 (사용자 결정 옵션 A — 폐기)

> **외부 동작 불변 보장**: (a) docstring/주석만 정정 (L-2/E-2) (b) E-1 핸들러 추가는 기존 미보호 5xx 경로를 명시 매핑으로 정정 — KRX 외부 응답 패턴 동일 (c) M-3 cast 는 mypy 만 영향, 런타임 무변 (d) gap detection 은 CLI resume mode 의 정확도 향상이며 라우터/UseCase 영향 0.

## 3. 영향 범위 (코드 5 + 테스트 3 + 문서 4)

### 3.1 service / router (L-2)

| 파일 | 위치 | 변경 |
|------|------|------|
| `app/application/service/ohlcv_periodic_service.py` | line 8 (module docstring) | `"YEARLY → NotImplementedError (P2 chunk 진입 시 활성화, H-3)"` → `"YEARLY → 활성 (C-4 / b75334c)"` |
| 동 | line 124 (`_validate_period` docstring) | `"YEARLY → NotImplementedError"` 제거 |
| 동 | line 135 (Raises 절) | `"NotImplementedError: period=YEARLY (P2 chunk 미구현)"` 제거 |
| 동 | line 281 (refresher Raises 절) | 동일 정정 |
| 동 | line 395 (`_ingest_one` 가드) | **유지** — defense-in-depth (`_validate_period` 누락 시 fail-fast) |
| 동 | line 414 (주석) | `"# C-4 Phase 진입으로 YEARLY 활성. NotImplementedError 제거."` → 단순화 또는 제거 (이미 dead context) |
| `app/adapter/web/routers/ohlcv_periodic.py` | line 20 (module docstring) | `"NotImplementedError (period=YEARLY) → caller 에서 발생 안 함"` 제거 |

### 3.2 router KiwoomError 핸들러 (E-1)

| 파일 | 위치 | 변경 |
|------|------|------|
| `app/adapter/web/routers/ohlcv.py` | `sync_ohlcv_daily:138` | `refresh_ohlcv_daily:204` / `ohlcv_periodic._do_sync:120` 와 동일 5종 핸들러 추가 — `KiwoomBusinessError` → 400 (return_code + message echo 차단) / `KiwoomCredentialRejectedError` → 400 / `KiwoomRateLimitedError` → 503 / `(KiwoomUpstreamError, KiwoomResponseValidationError)` → 502 / `KiwoomError` → 502 fallback (logger.warning) |

### 3.3 repository cast (M-3)

| 파일 | 위치 | 변경 |
|------|------|------|
| `app/adapter/out/persistence/repositories/stock_price.py` | line 141 | `return list(result.scalars().all())  # type: ignore[arg-type]` → `return cast(list[StockPriceKrx], list(result.scalars().all()))` (반환 타입 ORM 모델에 맞춤). `from typing import cast` import 추가 필요 |
| `app/adapter/out/persistence/repositories/stock_price_periodic.py` | line 182 | 동일 패턴 (`PeriodicModel` union 타입에 cast) |

### 3.4 deps docstring (E-2)

| 파일 | 위치 | 변경 |
|------|------|------|
| `app/adapter/web/_deps.py` | line 271-333 (9개 reset_* 함수) | docstring `"테스트 전용 — ..."` → `"lifespan teardown + 테스트 — ..."` (lifespan `main.py:456-462` 가 호출). 각 함수의 구체 대상 (sector / stock / ...) 표현 유지 |

### 3.5 backfill CLI gap detection (gap detection)

| 파일 | 위치 | 변경 |
|------|------|------|
| `scripts/backfill_ohlcv.py` | `compute_resume_remaining_codes:252` | (1) 영업일 set 조회 — `SELECT DISTINCT trading_date FROM <KRX 영속화 테이블> WHERE trading_date BETWEEN ? AND ?` (전체 종목 union, period 별 적용 테이블 — daily=stock_price_krx, weekly=stock_price_weekly_krx, monthly=stock_price_monthly_krx, yearly=stock_price_yearly_krx). (2) 종목별 trading_date set 조회 — `SELECT DISTINCT trading_date WHERE stock_id=? AND trading_date BETWEEN ? AND ?`. (3) 차집합 ≥ 1 → 진행. = 0 → skip. (4) docstring + log 메시지 갱신 (`max(trading_date) >= end_date` → `gap detected (missing N dates)`) |
| `scripts/backfill_daily_flow.py` | `compute_resume_remaining_codes:240` | 동일 변경. 단일 테이블 `kiwoom.stock_daily_flow` (KRX/NXT 통합 테이블) |

> **영업일 calendar = DB union**: `SELECT DISTINCT trading_date FROM <영속화 테이블>` 결과를 영업일로 간주. 시장 전체 종목이 한 번이라도 거래한 일자 = 영업일 (휴장일 제외). 신규 Stock (적재 0) 도 자연스럽게 비교 대상이 됨 (영업일 set 만큼은 다른 종목들이 채움). period (weekly/monthly/yearly) 도 동일 패턴 — period 별 영속화 테이블에서 union.

### 3.6 테스트 (3 갱신/신규)

| 파일 | 변경 |
|------|------|
| `tests/test_ohlcv_router.py` (또는 `test_ohlcv_router_*`) | E-1 신규 5 cases — `sync_ohlcv_daily` 가 KiwoomBusinessError/CredentialRejected/RateLimited/Upstream/KiwoomError 에 각각 400/400/429/502/502 응답 단언 |
| `tests/test_backfill_ohlcv.py` | gap detection 신규 — 부분 적재 종목 (영업일 set 의 일부만 적재) 이 `compute_resume_remaining_codes` 결과에 포함되는지 + 완전 적재 종목 (영업일 set 와 동일) 이 skip 되는지 + 적재 0 종목 진행 검증 |
| `tests/test_backfill_daily_flow.py` | 동일 gap detection 신규 |

> M-3 (cast) / E-2 (docstring) / L-2 (docstring) 은 단위 테스트 신규 없음 — mypy/ruff PASS + 기존 테스트 회귀 무 검증.

### 3.7 문서 (4)

- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 30 신규 (R2 결과)
- `src/backend_kiwoom/STATUS.md` 갱신 — chunk § 6 누적 + § 5 다음 후보 재정렬 + § 4 알려진 이슈 정리
- `HANDOFF.md` 전체 갱신
- `CHANGELOG.md` prepend (`refactor(kiwoom): Phase C-R2 — 1R Defer 5건 일괄 정리 (L-2/E-1/M-3/E-2/gap detection)`)

## 4. 적대적 사전 self-check (H-1 ~ H-10)

| # | 위험 | 완화 |
|---|------|------|
| H-1 | L-2 docstring 정정이 누락된 곳 잔존 | grep `NotImplementedError\|YEARLY.*미구현\|P2 chunk 미구현` 으로 전체 검사 — 본 chunk 종료 전 0 hit (단, `_ingest_one:395` dead branch 의 raise NotImplementedError 메시지는 의도된 fail-fast 라 유지) |
| H-2 | E-1 sync_ohlcv_daily KiwoomError 핸들러 추가가 외부 응답 변경 | 기존 미보호 경로는 FastAPI 디폴트 500 응답. 핸들러 추가 후 명시 매핑 (400/429/502) — 더 안전. message echo 차단 (refresh 와 동일 contract). 기존 통과 테스트 변화 0 (try/except 가 위에서 catch) |
| H-3 | E-1 핸들러 순서 회귀 — KiwoomBusinessError 가 KiwoomError 보다 먼저 와야 | refresh_ohlcv_daily:255-282 패턴 그대로 복제 (subclass first). 코드 리뷰에서 명시 검증 |
| H-4 | M-3 `cast()` 가 런타임 동작 변화 | `cast` 는 typing helper — 런타임 no-op. mypy 검증만 영향. 단 import 추가 필요 (`from typing import cast`) |
| H-5 | M-3 cast 타입이 ORM 다형성과 충돌 — Repository 가 union 반환 시 (e.g. `list[StockPriceKrx \| StockPriceNxt]`) | 현재 Repository 는 단일 모델 반환 (`StockPriceKrx` 또는 `StockPriceNxt` 분리) — cast target 명확. `stock_price_periodic.py:182` 는 PeriodicModel union 이지만 단일 호출 컨텍스트에서 단일 모델 — Generic + cast 로 안전 |
| H-6 | E-2 docstring 정정이 lifespan + 테스트 양쪽 호출 의도 명확화 | `main.py:456-462` 가 8개 reset_*_factory 호출 확인. reset_token_manager 도 lifespan 사용 여부 확인 (`main.py` grep) — 만약 미사용이면 docstring 은 "테스트 전용" 유지 |
| H-7 | gap detection 의 영업일 set 이 미래 일자 포함 가능 (영업일이 아직 안 옴) | end_date 까지의 영업일만 SELECT. 미래 일자는 자연스럽게 제외 (DB 에 미래 일자 적재 없음) |
| H-8 | gap detection 영업일 set 이 비어 있는 edge — 첫 적재 (DB 0 rows) | 영업일 set = ∅ → 모든 종목이 차집합 = ∅ 로 skip 위험. 가드 — 영업일 set 이 비면 모든 종목 진행 (= 기존 동작과 동일) |
| H-9 | gap detection 이 단일 종목 부분 적재 (gap 있음) 을 단위 테스트 어떻게 검증 | testcontainers + 단위 테스트 — 영속화 테이블에 (영업일 set 5일 / 종목 A 5일 적재 / 종목 B 3일 적재) 시나리오 → 종목 B 만 결과에 포함 단언 |
| H-10 | gap detection 변경이 기존 운영 호출 차단 — `--resume` 시 기존 정상 적재 종목까지 진행 | 영업일 set 와 종목 trading_date set 가 일치하면 차집합 = ∅ → skip. 기존 정상 적재는 그대로 skip. 단 부분 적재 (1+ gap) 은 진행 — 의도된 정확도 향상. 사용자 결정 (CLI 디폴트 동작 변경) |

## 5. DoD (R2)

**코드** (목표: ruff/mypy strict PASS / 외부 contract 무변):

- [ ] L-2 — service/router docstring 5곳 정정 (`grep "NotImplementedError\|YEARLY 미구현"` 0 hit)
- [ ] E-1 — `sync_ohlcv_daily` 에 KiwoomError 핸들러 5종 추가 (`refresh_ohlcv_daily` 와 동일 패턴)
- [ ] M-3 — 2 Repository `# type: ignore[arg-type]` → `cast(list[T], ...)` (typing.cast import 추가)
- [ ] E-2 — `_deps.py` 9개 reset_* docstring 정정 (lifespan teardown 사용 여부 확인 후)
- [ ] gap detection — 2 CLI `compute_resume_remaining_codes` 일자별 검사 변환 (DB union 영업일 + per-stock 차집합)

**테스트** (목표: 1035 → ~1043 / coverage 유지):

- [ ] E-1 신규 5 cases — sync_ohlcv_daily KiwoomError 핸들러 5종 응답 단언
- [ ] gap detection 신규 6 cases — backfill_ohlcv (3 cases — 부분/완전/0 적재) + backfill_daily_flow (3 cases 동일)
- [ ] 기존 회귀 0 — refresh_ohlcv_daily / 기타 router 테스트 그대로 PASS

**Verification**:

- [ ] mypy --strict 0 errors
- [ ] ruff check + format All passed
- [ ] pytest 전체 PASS (1035 → ~1043 cases)
- [ ] coverage 유지 (≥ 93%)

**리뷰**:

- [ ] 1R 리뷰 PASS (refactor 분류라 2b 자동 생략 가능 / 사용자 `--force-2b` 권한)
- [ ] Verification Loop — 회귀 / docstring 누락 / cast 타입 불일치 검사

**문서**:

- [ ] ADR § 30 추가 (R2 결과)
- [ ] CHANGELOG: `refactor(kiwoom): Phase C-R2 — 1R Defer 5건 일괄 정리 (L-2/E-1/M-3/E-2/gap detection)`
- [ ] STATUS.md 갱신 — § 6 chunk 누적 / § 5 다음 후보 재정렬 / § 4 알려진 이슈 정리
- [ ] HANDOFF.md 전체 갱신
- [ ] ADR-0001 § 24.5 / § 25.6 의 Defer 표에서 5건 ✅ 마킹

## 6. 다음 chunk (R2 이후)

1. **follow-up F6/F7/F8 + daily_flow 빈 응답 1건 통합** — since_date edge / turnover_rate 음수 / 빈 응답 1 종목 (LOW)
2. **ETF/ETN OHLCV 별도 endpoint** (옵션 c) — 신규 도메인
3. **Phase D 진입** — ka10080 분봉 / ka20006 업종일봉 (대용량 파티션 결정 선행)
4. **Phase E/F/G** — 공매도/대차/순위/투자자별 (신규 endpoint wave)
5. **scheduler_enabled 운영 cron 활성 + 1주 모니터** (사용자 결정: 모든 작업 완료 후)

---

_R2 = Refactor 2. 1R Defer 5건 (L-2 / E-1 / M-3 / E-2 / gap detection) 일괄 정리. ADR § 24.5 / § 25.6 출처._
