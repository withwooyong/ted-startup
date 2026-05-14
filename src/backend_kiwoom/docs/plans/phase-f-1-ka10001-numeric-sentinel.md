# Phase F-1 — ka10001 NUMERIC overflow + sentinel WARN/skipped 분리

> 출처: STATUS.md § 4 #29 (5-13 18:00 cron 7.2% 실패) + 본 chunk pre-flight 분석 (2026-05-14)
> 분류: ops fix + 운영 안정성 (도메인 = stock_fundamental + stkinfo)
> 의존: 없음 (독립 chunk)
> ted-run 풀 파이프라인 input

---

## 1. 메타

| 항목 | 값 |
|------|------|
| Chunk 명 | Phase F-1 ka10001 NUMERIC overflow + sentinel WARN/skipped 분리 |
| 추가일 | 2026-05-14 (KST) |
| 선행 | 5-13 18:00 cron 결과 (success=4063 / failed=316 / fail-ratio 7.2%) + 본 chunk pre-flight 컬럼 magnitude 분석 |
| 후속 | F-2 backfill 임계치 / alphanumeric guard 분리 (별도 chunk, 도메인 다름) |

---

## 2. 현황 (5-13 cron 18:00 실측 → 본 chunk pre-flight 분석)

### 2.1 5-13 cron 실패 분포

```
total=4379 / success=4063 / failed=316 (ratio 7.2%)
- ASYNCPG NumericValueOutOfRangeError: 11건 — precision 8 scale 4 < 10^4
  (대표 종목: 468760 / 474930 / 0070X0)
- sentinel `_validate_stk_cd_for_lookup` 거부: 2건 — 0000D0 / 0000H0
- 나머지 ~303건: 본 chunk 진입 시 추가 분석 (TBD — 알려진 sentinel pattern 추정)
```

### 2.2 NUMERIC(8,4) 컬럼 magnitude 분포 (2026-05-14 운영 DB 측정)

| 컬럼 | 현재 type | 실측 max | 한계 (9999.9999) 대비 | 판정 |
|------|----------|---------|---------------------|------|
| **`trade_compare_rate`** | `Numeric(8,4)` | **8,950.0000** | **89.5% 사용** | ⚠️ **overflow 임박** |
| **`low_250d_pre_rate`** | `Numeric(8,4)` | **5,745.7100** | **57.5% 사용** | ⚠️ **안전권 끝** |
| `high_250d_pre_rate` | `Numeric(8,4)` | 1.85 | 0.02% | ✅ 여유 |
| `change_rate` | `Numeric(8,4)` | 30.0000 | 0.3% | ✅ |
| `market_cap_weight` | `Numeric(8,4)` | NULL | — | ✅ |
| `foreign_holding_rate` | `Numeric(8,4)` | 100.0000 | 1% | ✅ |
| `credit_rate` | `Numeric(8,4)` | 9.83 | 0.1% | ✅ |
| `circulating_rate` | `Numeric(8,4)` | 99.0000 | 1% | ✅ |
| `per_ratio` / `pbr_ratio` / `ev_ratio` | `Numeric(10,2)` | (확인 권고) | — | 추정 ✅ |
| `roe_pct` | `Numeric(8,2)` | (확인 권고) | — | 추정 ✅ |

⇒ **확대 대상 = `trade_compare_rate` + `low_250d_pre_rate` 2 컬럼**. 다른 NUMERIC 컬럼은 안전권 (over-engineering 회피).

### 2.3 sentinel pattern 인식

| 종목 패턴 | 정체 | 처리 |
|---|---|---|
| `0000D0` / `0000H0` / `0000J0` / `0000Y0` / `0000Z0` | NXT 우선주 sentinel (4자리 0 + 1문자 + 1자리 0) | `_validate_stk_cd_for_lookup` ValueError ⇒ **운영 의도된 skip** |
| `26490K` / `28513K` / `0070X0` 등 | KRX 우선주 / ETN K/L suffix 종목 | 동일 ValueError ⇒ **운영 의도된 skip** |

**현재 처리**: ValueError → service layer try/except → `result.errors` 적재 → `result.failed_count++`. 운영자 입장에서 _실제 실패_ 와 _의도된 skip_ 구분 불가 ⇒ 알람·임계치 의미 오염.

---

## 3. 범위 외 (out of scope)

- F-2 backfill 임계치 / alphanumeric guard 분리 (별도 chunk — `backfill_short.py` + `backfill_lending_stock.py`)
- 5-13 cron 의 나머지 ~303건 실패 원인 분석 (TBD — Step 0 TDD 진입 시 raw_response 또는 logs 추가 분석)
- per/pbr/ev/roe 4 컬럼 magnitude 정밀 분석 (별도 운영 검증 — 본 chunk 변경 0)
- ka20006 1R HIGH #5 의 정확한 처리 패턴 재방문 (이미 정리된 패턴 1:1 적용)

---

## 4. 결정

| # | 결정 | 근거 |
|---|------|------|
| 1 | **`trade_compare_rate` (8,4) → (12,4)** | max 99,999,999.9999 — 거래량 비율 큰 종목 (무거래일 다음 점프) 대응 + 충분한 안전 마진. 실측 max 8950 의 약 10,000배 여유 |
| 2 | **`low_250d_pre_rate` (8,4) → (10,4)** | max 999,999.9999 — 250일 저가 대비 100만 % 까지 대응. 실측 max 5745 의 약 175배 여유 (테마주 250일 점프 대응) |
| 3 | scale=4 유지 | 데이터 호환성 보존 + 기존 Decimal 표현 유지 |
| 4 | **sentinel detect → 새 exception type `SentinelStockCodeError(ValueError)`** | service layer 의 가드 분기 명확. `ValueError` 상속 → 기존 caller 호환 유지 |
| 5 | service layer 의 bulk loop — `SentinelStockCodeError` 캐치 후 `result.skipped` 적재 (별도 field) | 운영 알람·임계치에서 _실제 실패_ ↔ _의도 skip_ 분리 |
| 6 | `result.failed_count` 의미 = 실제 실패 (HTTP 4xx/5xx / DB 오류 / 알 수 없는 예외) — sentinel skip 제외 | 알람 임계치 의미 정확화 |
| 7 | Migration scope = 컬럼 ALTER TYPE 만 (데이터 손실 0 / 확대 방향) | 위험 0. Postgres 의 ALTER TABLE ALTER COLUMN TYPE 은 metadata 변경만 |
| 8 | 다른 NUMERIC 컬럼 손대지 않음 (over-engineering 회피) | 안전권 / 실측 magnitude 여유 |

---

## 5. 변경 면 매핑

### 5.1 코드 (3 파일)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/adapter/out/kiwoom/stkinfo.py` | 새 exception `SentinelStockCodeError(ValueError)` 추가. `_validate_stk_cd_for_lookup` 가 `ValueError` → `SentinelStockCodeError` 로 변경 (그러나 ValueError 상속이라 caller 호환). exports 갱신 |
| 2 | `app/application/service/stock_fundamental_service.py` | bulk loop 의 try/except 분기 추가 — `SentinelStockCodeError` 별도 catch → `result.skipped` 적재. `result.failed_count` 의미 명확화 (sentinel 제외). result DTO 갱신 |
| 3 | `app/adapter/out/persistence/models/stock_fundamental.py` | `trade_compare_rate: Numeric(8,4)` → `Numeric(12,4)`. `low_250d_pre_rate: Numeric(8,4)` → `Numeric(10,4)`. ORM 만 (DTO 의 Decimal 은 무관) |

### 5.2 Migration (신규 017)

```sql
-- alembic/versions/017_ka10001_numeric_precision_expansion.py
ALTER TABLE kiwoom.stock_fundamental
  ALTER COLUMN trade_compare_rate TYPE NUMERIC(12, 4);
ALTER TABLE kiwoom.stock_fundamental
  ALTER COLUMN low_250d_pre_rate TYPE NUMERIC(10, 4);

-- downgrade 가 데이터 손실 위험 — 9999 초과 데이터가 있으면 fail.
-- downgrade 정책: CHECK 위반 안전 fail (사용자 결정 필요 시 별도 운영 chunk)
```

### 5.3 DTO 응답 (1 파일)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/adapter/web/_dto.py` (또는 stock_fundamental result DTO 위치) | `BulkResult` 의 `skipped_count` + `skipped` (list 종목) 필드 추가. `failed_count` docstring 갱신 (의미 명확화) |

### 5.4 테스트 신규 / 갱신 (~5 파일 / +200줄)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `tests/test_stock_fundamental_service.py` | bulk loop sentinel skip 분리 + `result.skipped` 단언. failed_count 의미 회귀 |
| 2 | `tests/test_stkinfo.py` | `SentinelStockCodeError` 발생 + ValueError 상속 호환 |
| 3 | `tests/test_repository_stock_fundamental.py` (또는 Migration 017 회귀) | trade_compare_rate=10000.0001 / low_250d_pre_rate=99999.5 적재 + 회수 verify |
| 4 | `tests/test_migration_017.py` | Migration 017 upgrade/downgrade 회귀 (alembic apply + revert) |
| 5 | `tests/conftest.py` (또는 fixture) | bulk fixture 에 sentinel 종목 1~2건 + overflow 값 1건 추가 |

추정 변경 라인 (총 ~400-500줄):
- 코드: 3 파일 — sentinel exception (~20줄) + service bulk 분기 (~30줄) + ORM type (~2줄) = ~50줄
- Migration: 1 파일 — 신규 ~30줄
- DTO: 1 파일 — ~10줄
- 테스트: 5 파일 — ~200-300줄

---

## 6. 적대적 self-check (보안 / 동시성 / 데이터 정합)

### 6.1 보안

- 새 exception type 노출 시 stack trace 또는 종목코드 일부 leak ⇒ 로그만 영향, response body 안전 (DTO 가드 통과)
- Migration 017 alembic credentials = 기존 DB 사용자. 신규 권한 없음 ⇒ ✅

### 6.2 동시성 / 운영

- Migration ALTER TYPE 실행 시간 — Postgres 의 NUMERIC type 확대는 metadata-only operation (rewrite 불필요). 운영 시간 0 영향. 단, 쓰기 트래픽이 있을 때 lock 짧게 보유 ⇒ scheduler 발화 시각 (mon-fri 18:00 KST) 안 운영. **운영 시간 외 (현재 09:58~) 적용 권고**
- 신규 exception type 의 caller 영향 — `ValueError` 상속이라 기존 `except ValueError:` 캐치 그대로 동작 ⇒ ✅ backward compat
- `result.skipped` 신규 field — 기존 caller 무시 가능 (optional default=`[]`) ⇒ ✅
- bulk loop 분기 추가 — 성능 영향 0 (try/except 동일 cost)

### 6.3 데이터 정합

- Migration 017 = NUMERIC 확대만 → 데이터 손실 0 (downgrade 시 9999 초과 row 있으면 alembic downgrade fail, 운영 가드)
- 8125 row + 4078 unique stocks 안 9999 초과 값 0건 (실측 max 8950) ⇒ Migration 안전
- 추후 cron 발화 시 9999~99999 값이 들어오면 `Numeric(12,4)` 안에 정상 적재

### 6.4 ka20006 1R HIGH #5 와의 일관성

ka20006 (D-1) 1R HIGH #5 패턴 = `result.errors` 와 _의도된 skip_ 분리. 본 chunk 의 `result.skipped` 분리는 그 패턴 1:1 확장 ⇒ 도메인 일관성 ✅

---

## 7. DoD (Definition of Done)

- [ ] Migration 017 작성 + alembic upgrade head 적용 검증
- [ ] `trade_compare_rate Numeric(12,4)` + `low_250d_pre_rate Numeric(10,4)` ORM 갱신
- [ ] `SentinelStockCodeError(ValueError)` 신설 + `_validate_stk_cd_for_lookup` raise type 변경
- [ ] `stock_fundamental_service` bulk loop 의 sentinel 분기 — `result.skipped` 적재
- [ ] `BulkResult` DTO 의 `skipped_count` + `skipped` 필드 추가 + docstring 갱신
- [ ] 테스트 5종 신규/갱신 — 회귀 PASS
- [ ] Verification 5관문 PASS (ruff + mypy --strict + pytest coverage ≥80%)
- [ ] 1R+2R 이중 리뷰 PASS (force-2b, backend_kiwoom 표준)
- [ ] ADR § 45 신규 (또는 § 44.11 추가 결정)
- [ ] STATUS / HANDOFF / CHANGELOG 메타 3종 갱신
- [ ] 운영 검증 — Migration 적용 후 cron 발화 / DB 적재 정상

---

## 8. 다음 chunk

| 순위 | chunk | 근거 |
|------|-------|------|
| 1 | **F-2 backfill 임계치 / alphanumeric guard 분리** | 본 turn § 44.9 / `backfill_short.py` + `backfill_lending_stock.py` 5% 임계치 vs alphanumeric 7% 충돌 |
| 2 | **Phase F (순위 5종) — ka10027/30/31/32/23** | 신규 endpoint wave (25 endpoint 60→80%) |
| 3 | Phase D-2 ka10080 분봉 | 대용량 파티션 결정 동반 |

---

## 9. ted-run 풀 파이프라인 input

- **분류**: contract 변경 (Migration + DTO 필드 추가)
- **모델 전략**: 기본값 (구현 Opus / 1R Sonnet / 2R Opus / Verification 분담)
- **2b 강제**: backend_kiwoom 표준 (`--force-2b`)
- **메타**: ADR 신규 § / STATUS / HANDOFF / CHANGELOG 4종 갱신 (chunk 종결 시 일괄)

```
/ted-run docs/plans/phase-f-1-ka10001-numeric-sentinel.md --force-2b
```
