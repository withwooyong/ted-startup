# Phase F-2 — backfill 임계치 / alphanumeric guard 분리

> 출처: ADR § 44.9 (5-14 운영 인시던트 turn 발견) + STATUS § 4 Known Issue #31 + Phase F-1 후속 (도메인 분리)
> 분류: ops fix + 운영 안정성 (도메인 = backfill CLI + short_selling/lending bulk service)
> 의존: Phase F-1 완료 (`ced66f3`) — `SentinelStockCodeError(ValueError)` 패턴 확립
> ted-run 풀 파이프라인 input

---

## 1. 메타

| 항목 | 값 |
|------|------|
| Chunk 명 | Phase F-2 backfill 임계치 / alphanumeric guard 분리 |
| 추가일 | 2026-05-14 (KST) |
| 선행 | 5-13 backfill 실행 결과 (short fail 307 / lending_stock fail 303 — 둘 다 alphanumeric guard) + § 44.9 (임계치 5% < alphanumeric 비율 ~7% 충돌 발견) + Phase F-1 `SentinelStockCodeError` 패턴 (`ced66f3`) |
| 후속 | Phase F (순위 5종 ka10027/30/31/32/23) 신규 endpoint wave |

---

## 2. 현황 (5-13 backfill 실측 + 본 chunk pre-flight)

### 2.1 5-13 backfill 결과 (ADR § 44.7 / § 44.9)

| backfill | total | success row | failed | exit | 비고 |
|----------|-------|-------------|--------|------|------|
| `backfill_short.py` | 4,373 | 2,441 | **307** (alphanumeric guard) | 1 | 22m / 임계치 5% < 7% — error |
| `backfill_lending_stock.py` | 4,373 | 4,072 | **303** (alphanumeric guard) | 1 | 17m / 임계치 5% < 6.9% — error |

⇒ 본 turn 첫 시도 시 `set -e` 단계 차단. 두 번째 시도부터 `|| true` 우회 운영.

### 2.2 alphanumeric guard 위치 (코드 추적)

| layer | 파일:line | 동작 |
|-------|-----------|------|
| **adapter** | `app/adapter/out/kiwoom/shsa.py:92` | `raise ValueError(f"stock_code 6자리 숫자만 허용 — 입력={stock_code!r}")` (KiwoomShortSellingClient.fetch_trend) |
| **adapter** | `app/adapter/out/kiwoom/slb.py:142` | 동일 패턴 (KiwoomLendingClient.fetch_stock_trend) |
| **service bulk** | `short_selling_service.py:305` | `except Exception` 가 ValueError 캐치 → `nxt_outcomes/krx_outcomes.append(... error=err_class)` |
| **service bulk** | `lending_service.py:299` | 동일 — `total_failed += 1` |
| **임계치** | `lending_service.py:368` | `LENDING_STOCK_ERROR_THRESHOLD = 0.05` (5%) → `errors_above_threshold=True` |
| **임계치** | `short_selling_service.py:340` | `PARTIAL_ERROR_THRESHOLD = 0.15` (15%) — short 는 error 안 됨 / **but** CLI exit code 1 |
| **CLI** | `backfill_short.py:186` | `return 1 if result.total_failed > 0 else 0` (단순) |
| **CLI** | `backfill_lending_stock.py:203` | 동일 패턴 |

### 2.3 의미 충돌 (§ 44.9 의 근본 원인)

- alphanumeric 종목 (00088K / 005935 / TIGER ETF / KODEX ETN 등) ≈ **295 / 4,373 = 6.75%** 가 active stock 의 자연 분포
- shsa/slb 가드가 의도적으로 ValueError raise (Excel R22 ASCII 제약 / KRX wire 거부 회피)
- 그러나 service bulk 는 **모든 Exception 을 `total_failed` 로 합산** — 의도된 skip 이 실패와 섞임
- 임계치 5% (lending) 는 _실제 실패_ 5% 발생 시 알람을 의도했으나, alphanumeric 7% 가 무조건 임계치 초과 → **false positive**
- CLI exit code 1 → CI/shell `set -e` 단계 차단

### 2.4 Phase F-1 패턴과의 비교

| 측면 | F-1 (ka10001 stkinfo) | F-2 (shsa + slb) |
|------|----------------------|------------------|
| guard 위치 | `stkinfo.py:_validate_stk_cd_for_lookup` | `shsa.py:fetch_trend` + `slb.py:fetch_stock_trend` |
| guard 정규식 | sentinel 패턴 (`0000D0` 등) — _좁은_ 거부 | `^[0-9]{6}$` — _넓은_ alphanumeric 거부 |
| 호출 layer | service → adapter (단건 lookup) | service bulk loop → adapter (단건 호출 × 4373) |
| skip 발생률 | 매우 낮음 (sentinel 2~3건 / 4379) | **높음 (~295 / 4373 = 6.75%)** — 일상적 |
| 임계치 영향 | 5% 임계치 거의 도달 못 함 (sentinel 낮음) | 5% 임계치 항상 초과 (alphanumeric 일상적) |
| F-1 해결 | `SentinelStockCodeError(ValueError)` + `result.skipped` 분리 | F-1 패턴 1:1 이식 가능. 단, scope 가 bulk × CLI |

⇒ **F-1 패턴 이식이 자연**. 단, _alphanumeric_ 은 sentinel 보다 _일상적_ 이라 분리 효과가 크고, CLI 측 exit code 정책도 함께 손봐야 한다.

---

## 3. 범위 외 (out of scope)

- **chart 계열 alphanumeric 가드** — Phase C-2 `phase-c-chart-alphanumeric-guard.md` 가 이미 `STK_CD_CHART_PATTERN` 으로 분리 마침. 본 chunk 는 _lookup_ 계열 (shsa/slb) 만
- **stkinfo.py / fundamentals (ka10001)** — Phase F-1 이 이미 처리. 본 chunk 는 손대지 않음
- **`backfill_ohlcv.py`** — chart 계열이라 이미 가드 완화 적용. 본 chunk 외
- **순위 5종 (Phase F) / 투자자별 (Phase G) 의 alphanumeric 정책** — 본 chunk 는 backfill_short + backfill_lending_stock 만
- **`scheduler` cron 발화 시의 동일 충돌** — scheduler 는 임계치 발화 시 ERROR 로그만, exit 안 함. CLI 만 exit code 1. 단, 임계치 의미 회복은 cron 에도 적용됨 (부수 효과)
- **임계치 수치 변경 (5% → 다른 값)** — 임계치 의미를 _실제 실패_ 로 회복하면 5% 그대로 적정. 수치 조정은 별도 운영 chunk

---

## 4. 확정 결정 (2026-05-14 사용자 확정)

| # | 결정 | 근거 |
|---|------|------|
| 1 | **옵션 A + B 하이브리드 채택** | cron 임계치 회복 (A 의 service catch) + CLI budget 73s 절감 (B 의 pre-filter) 둘 다 |
| 2 | `shsa.py` + `slb.py` 가드 raise type → `SentinelStockCodeError` (F-1 신설 type 재사용) | F-1 패턴 일관성 / adapter layer 안 import (`stkinfo.py` 와 동일 layer) |
| 3 | `short_selling_service.py` + `lending_service.py` bulk loop 에 `SentinelStockCodeError` 별도 catch | sentinel skip 과 실제 실패 분리 |
| 4 | `ShortSellingBulkResult` 에 `total_skipped: int = 0` 신규 필드 | 현재 부재 / lending 과 일관성 |
| 5 | **`LendingStockBulkResult.total_alphanumeric_skipped: int = 0` 신규 필드 (의미 분리)** | D-2 결정 — 기존 `total_skipped` (empty 응답 의미) 유지. DTO breaking 최소 |
| 6 | **임계치 분모 유지 + error 메시지에 `(of which alphanumeric_skipped=N)` 명시** | D-3 결정 — `failure_ratio = total_failed / total_stocks` 분모 그대로. 임계치 발화 회복은 sentinel catch 효과로 _실제 실패만_ 카운트되어 자연 회복 |
| 7 | **UseCase `filter_alphanumeric: bool = False` 신규 파라미터** | D-4 결정 — `IngestShortSellingBulkUseCase` + `IngestLendingStockBulkUseCase` 둘 다. service 내부에서 stock list filter 시점 (`^[0-9]{6}$`). 신규 옵션이라 기존 caller backward compat |
| 8 | CLI 두 파일에서 `filter_alphanumeric=True` 호출 + summary 에 `alphanumeric_skipped: <N>` 라인 추가 | B 의 호출 budget 절감 실현 |
| 9 | CLI exit code — `return 1 if result.total_failed > 0` 유지 | total_failed 의미 회복으로 자동 fix |
| 10 | scheduler cron 은 `filter_alphanumeric` 기본값 False 유지 (변경 0) | A 의 sentinel catch 만으로도 임계치 의미 회복. cron 가시성에 alphanumeric_skipped 로그 추가는 별도 chunk |

---

## 5. 변경 면 매핑 (옵션 A+B 가정)

### 5.1 코드 (4 파일)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/adapter/out/kiwoom/shsa.py` | `raise ValueError(...)` → `raise SentinelStockCodeError(...)` (F-1 import). 메시지 유지 |
| 2 | `app/adapter/out/kiwoom/slb.py` | 동일 |
| 3 | `app/application/service/short_selling_service.py` | bulk loop 에 `SentinelStockCodeError` 별도 catch → `skipped_outcomes` 분리 추적. 임계치 분모 = krx_outcomes 중 sentinel 제외. `ShortSellingBulkResult.total_skipped` 신규 필드 |
| 4 | `app/application/service/lending_service.py` | bulk loop 에 `SentinelStockCodeError` 별도 catch (현재 `total_skipped` 는 _outcome.skipped (응답 empty)_ 의미 — sentinel skip 과 의미 분리 필요. 신규 `total_alphanumeric_skipped` 또는 `total_skipped` 통합 — 사용자 결정) |

### 5.2 DTO (2 파일)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/application/service/short_selling_service.py` (ShortSellingBulkResult) | `total_skipped: int` 필드 추가. 임계치 의미 변경 docstring |
| 2 | `app/application/service/lending_service.py` (LendingStockBulkResult) | `total_skipped` 의미 분기 — _empty 응답 skip_ 과 _alphanumeric guard skip_ 의미 충돌. 신규 `total_alphanumeric_skipped` 또는 통합 (4.2 결정 시 확정) |

### 5.3 CLI (2 파일)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `scripts/backfill_short.py` | active stock fetch 후 `^[0-9]{6}$` pre-filter. summary 에 `alphanumeric_skipped: <N>` 라인 추가 |
| 2 | `scripts/backfill_lending_stock.py` | 동일 |

> CLI 의 active stock fetch 는 현재 service UseCase 내부에서 발생. CLI 단계에서 pre-filter 하려면 UseCase 의 `only_stock_codes` 파라미터 사용 권장 (lending 은 이미 지원, short 는 추가 검토). 또는 UseCase 가 stock list 받기 전에 filter — 사용자 결정.

### 5.4 테스트 신규 / 갱신 (~5-6 파일 / +250-350줄)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `tests/test_short_selling_service.py` | bulk loop sentinel skip 분리 + `total_skipped` 단언. 임계치 분모 회귀 |
| 2 | `tests/test_lending_service.py` | bulk loop sentinel skip 분리 + `total_skipped` 또는 신규 필드 단언 |
| 3 | `tests/test_shsa_sentinel.py` (신규) | shsa.py `SentinelStockCodeError` raise + ValueError 상속 호환 (F-1 의 `test_stkinfo_sentinel.py` 와 동일 패턴) |
| 4 | `tests/test_slb_sentinel.py` (신규) | slb.py 동일 |
| 5 | `tests/test_backfill_short_cli.py` (신규 또는 갱신) | pre-filter + summary alphanumeric_skipped 라인 검증 (smoke) |
| 6 | `tests/test_backfill_lending_stock_cli.py` (신규 또는 갱신) | 동일 |

추정 변경 라인:
- 코드 4 파일: shsa/slb raise type (~6줄) + service bulk catch (~40줄 × 2) + DTO field (~6줄) = ~90줄
- CLI 2 파일: pre-filter + summary 라인 = ~40줄
- 테스트 5~6 파일: ~250-350줄

⇒ 총 ~400-500줄 (F-1 과 동급 규모)

---

## 6. 적대적 self-check (보안 / 동시성 / 데이터 정합)

### 6.1 보안

- `SentinelStockCodeError` import 확산 — adapter layer 가 application layer exception 을 import 하지 않음 (역방향). F-1 이 adapter 의 `stkinfo.py` 에 신설했으므로 동일 adapter (`shsa.py`/`slb.py`) 에서 import 가능 ⇒ layer 침범 0
- alphanumeric pre-filter 의 정규식 `^[0-9]{6}$` — ReDoS 위험 없음 (입력 길이 6 고정). DB 쿼리 시 SQL injection 없음 (filter 는 Python in-memory) ⇒ ✅

### 6.2 동시성 / 운영

- service bulk loop 의 catch 분기 추가 — 성능 영향 0 (try/except 동일 cost)
- CLI pre-filter 추가 — active stock list (~4373) 의 Python 정규식 매칭 ~5ms ⇒ ✅
- scheduler cron 발화 시 service 변경 (옵션 A) 동시 적용 — 임계치 알람이 실제 실패 시에만 발화하도록 회복. **부수 효과 양호**
- 임계치 의미 변경 (분모에서 sentinel 제외) 으로 운영 baseline (5-13 fail 7%) 과 비교 불가. _실제 실패_ 는 0% 근접 예상 ⇒ 임계치 5% 의미 회복

### 6.3 데이터 정합

- alphanumeric pre-filter 가 적용된 backfill 결과 = 영숫자 295 종목 데이터 0 row (현재와 동일) — 데이터 손실 0
- service 의 sentinel catch 분기 추가 = bulk 결과 set 동일 (skipped 으로 옮길 뿐). DB 데이터 동일
- scheduler cron 도 동일 (응답 동일 / DB 데이터 동일)

### 6.4 lending_stock 의 기존 `total_skipped` 와 의미 충돌

`LendingStockIngestOutcome.skipped` = _응답이 empty 인 경우 (정상 휴장 etc.)_ 의 skip. 현재 `total_skipped` 카운터는 이 의미. 본 chunk 의 alphanumeric skip 과 의미가 다름 — _두 종류 skip_ 을 어떻게 합칠지 결정 필요:

| 결정 A | 결정 B |
|--------|--------|
| `total_skipped` 통합 (모든 skip) + `skipped_breakdown: {empty_response, alphanumeric_guard}` dict | `total_skipped` (기존 empty) 유지 + `total_alphanumeric_skipped` 신규 |

⇒ ted-run 진입 시 사용자 확정. **권장 = B (의미 분리, breaking 최소)**.

### 6.5 short_selling 측의 `total_skipped` 부재

`ShortSellingBulkResult` 는 현재 `total_skipped` 필드 없음. 본 chunk 가 신규 추가하므로 default=0 으로 backward compat.

---

## 7. DoD (Definition of Done)

- [ ] `shsa.py` + `slb.py` 의 `raise ValueError` → `raise SentinelStockCodeError` 변경 (F-1 신설 type 재사용)
- [ ] `short_selling_service.py` bulk loop — `SentinelStockCodeError` 별도 catch → `total_skipped` 분리. 임계치 분모 = sentinel 제외
- [ ] `lending_service.py` bulk loop — `SentinelStockCodeError` 별도 catch → `total_alphanumeric_skipped` (또는 통합 — 결정 후) 분리. 임계치 분모 동일 보정
- [ ] `ShortSellingBulkResult` 에 `total_skipped: int = 0` 필드 추가
- [ ] `LendingStockBulkResult` 에 alphanumeric skip 분리 필드 (4.2 결정대로)
- [ ] `backfill_short.py` + `backfill_lending_stock.py` — numeric-only pre-filter (UseCase `only_stock_codes` 또는 신규 파라미터) + summary 에 `alphanumeric_skipped: <N>` 라인
- [ ] 테스트 5~6종 신규/갱신 — 회귀 PASS
- [ ] Verification 5관문 PASS (ruff + mypy --strict + pytest coverage ≥80%)
- [ ] 1R+2R 이중 리뷰 PASS (force-2b, backend_kiwoom 표준)
- [ ] ADR § 46 신규 (또는 § 44.10 추가 결정)
- [ ] STATUS / HANDOFF / CHANGELOG 메타 3종 갱신
- [ ] 운영 검증 — 변경 후 backfill 재실행 (smoke 100 종목) → exit 0 + alphanumeric_skipped 카운트 일치
- [ ] cron 자연 발화 시 임계치 알람 정상 (false positive 0)

---

## 8. 다음 chunk

| 순위 | chunk | 근거 |
|------|-------|------|
| 1 | **Phase F (순위 5종) — ka10027/30/31/32/23** | 신규 endpoint wave (25 endpoint 60→80%). Phase F-1/F-2 가 ops fix 라 핵심 도메인 확장 미진행 |
| 2 | Phase D-2 ka10080 분봉 (마지막 endpoint) | 대용량 파티션 결정 동반 |
| 3 | Phase G — 투자자별 3종 (ka10058/59/131) | 25 endpoint 80→92% |
| 4 | (조건부) 임계치 수치 재조정 (5% → 데이터 기반) | F-2 적용 후 1주 모니터 + 실제 실패율 측정 후 |

---

## 9. ted-run 풀 파이프라인 input

- **분류**: contract 변경 (DTO 필드 추가 + UseCase 신규 파라미터 + CLI behavior)
- **모델 전략**: 기본값 (구현 Opus / 1R Sonnet / 2R Opus / Verification 분담)
- **2b 강제**: backend_kiwoom 표준 (`--force-2b`)
- **메타**: ADR 신규 § / STATUS / HANDOFF / CHANGELOG 4종 갱신 (chunk 종결 시 일괄)
- **결정점 확정 (2026-05-14)**: D-1 A+B 하이브리드 / D-2 분리 신규 필드 (`total_alphanumeric_skipped`) / D-3 분모 유지 + 메시지 명시 / D-4 `filter_alphanumeric` 신규 파라미터

```
/ted-run docs/plans/phase-f-2-backfill-alphanumeric-guard.md --force-2b
```
