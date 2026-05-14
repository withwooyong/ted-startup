# Session Handoff

> Last updated: 2026-05-14 (KST) — Phase F-1 ka10001 NUMERIC overflow + sentinel WARN/skipped 분리 ted-run 풀 파이프라인 완료
> Branch: `master`
> Latest commit: `ced66f3` (Phase F-1 + ADR § 45 + 메타 4종)
> 미푸시: **1건** (`ced66f3` — 사용자 명시 요청 시 푸시)
> 본 세션 commit 2건: `b9d32a6` (Phase D 운영 검증 + kiwoom-db restart fix + 5-13 backfill) → ✅ 푸시 / `ced66f3` (Phase F-1) → 미푸시

## Current Status

ADR § 4 #29 (5-13 18:00 cron 7.2% 실패) + § 44.9 (5-14 운영 인시던트 turn 의 backfill 임계치 vs alphanumeric guard 충돌 발견) 의 **ka10001 분기**를 처리하는 ted-run 풀 파이프라인 chunk. F-2 backfill 임계치는 별도 chunk 로 분할 (도메인 분리 권고).

### Phase F-1 핵심 변경

```python
# 1. app/adapter/out/persistence/models/stock_fundamental.py — ORM precision 확대
trade_compare_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), ...)
low_250d_pre_rate:  Mapped[Decimal | None] = mapped_column(Numeric(10, 4), ...)

# 2. app/adapter/out/kiwoom/stkinfo.py — 신규 exception
class SentinelStockCodeError(ValueError):
    """sentinel 종목코드 (0000D0, 0070X0 등) 거부 — 운영 의도된 skip."""

# 3. app/application/service/stock_fundamental_service.py — bulk loop 분기
except SentinelStockCodeError:
    skipped.append(FundamentalSyncOutcome(...))  # failed 미증가

# 4. FundamentalSyncResult — skipped tuple field 추가
skipped: tuple[FundamentalSyncOutcome, ...] = field(default_factory=tuple)
@property
def skipped_count(self) -> int: return len(self.skipped)

# 5. migrations/versions/017_ka10001_numeric_precision.py — ALTER TYPE + downgrade 가드
```

| 항목 | 결과 |
|------|------|
| **Migration 017** | ✅ alembic upgrade head=`017_ka10001_numeric_precision` 운영 컨테이너 적용 |
| **운영 DB 컬럼 검증** | ✅ `trade_compare_rate (12,4)` + `low_250d_pre_rate (10,4)` |
| 코드 변경 | 5 production + Migration 017 신규 = 5 파일 +166/-7 |
| 테스트 변경 | 5 신규 + 2 회귀 보완 = 7 파일 +747/-6 |
| 1R 2a (sonnet) | CONDITIONAL → PASS / MEDIUM 2 즉시 fix |
| 1R 2b (opus) | CONDITIONAL → PASS / MEDIUM 1 즉시 fix |
| Verification 5관문 | ✅ ruff clean / mypy strict 95 files / **1236 tests / cov 86.19%** / runtime check |

### 이중 리뷰 MEDIUM 3건 처리

| # | 출처 | 항목 | 처리 |
|---|------|------|------|
| M-1 | 2a | `refresh_fundamental` 라우터에 `SentinelStockCodeError` catch 누락 → 500 낙하 위험 | router 에 catch + 400 매핑 |
| M-2 | 2a | `stkinfo.py` `__all__` 미정의 | module 상단 13 심볼 명시 |
| M-1 | 2b | `FundamentalSyncResultOut` 의 `skipped` tuple 미노출 (plan § 5.3 부분 누락) | DTO 에 `skipped` field 추가 + router 매핑 |

### LOW 9건 (다음 chunk inherit)

- `SentinelStockCodeError.__doc__` 의도 명확화 (sentinel 패턴 정의)
- Migration 017 `RAISE EXCEPTION` 메시지 `%건` 포맷 (PG `%` anchor 위험 — 실행 OK / 가시성만 영향)
- `test_migration_016.py` head 단언 완화 한계 (`!= pre-016`)
- `test_stock_fundamental_service_sentinel.py` fixture 순서
- Migration 017 "metadata-only" 단정 docstring 완화
- ~~`try/except/pass` → `contextlib.suppress`~~ ✅ **이미 fix** (ruff SIM105)
- `roe_pct Numeric(8,2)` 9999.99% 한계 (기존 issue inherit)
- `SectorBulkSyncResult.skipped: int` vs `FundamentalSyncResult.skipped: tuple` 네이밍 비일관

## Completed This Session

| # | Step | 결과 | 모델 | Files |
|---|------|------|------|-------|
| 0 | TDD | 5 신규 + 1 갱신 / 27 red | sonnet | 6 (test) |
| 1 | 구현 | 5 production + Migration 017 / 1236 PASS | opus | 5 (production) + 2 (test 회귀 보완) |
| 2a | 1차 리뷰 | CONDITIONAL → PASS / MEDIUM 2 fix | sonnet | (MEDIUM fix 2 production) |
| 2b | 적대적 리뷰 | CONDITIONAL → PASS / MEDIUM 1 fix | opus | (MEDIUM fix 1 production) |
| 3 | Verification | 5관문 PASS / 1236 / cov 86.19% | sonnet+haiku | (변경 0) |
| 4 | E2E | ⚪ UI 변경 0 | — | — |
| 5 | Ship | ADR § 45 + 메타 4종 + 커밋 | 메인 | 4 메타 |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| **1** | **F-2 backfill 임계치 / alphanumeric guard 분리** | **다음 세션 1순위** | § 44.9 / `backfill_short.py` + `backfill_lending_stock.py` 5% 임계치 vs alphanumeric 7% 충돌. F-1 의 sentinel 분리 패턴 backfill CLI 에 1:1 적용 (도메인 분리 / 별도 ted-run) |
| **2** | **5-15 (금) 06:00 자연 cron 검증 + 5-14 18:00 ka10001 cron 효과 검증** | 운영 검증 | § 43 + § 44 + § 45 효과 동시. 코드 0 |
| **3** | **Phase F (순위 5종) — ka10027/30/31/32/23** | 신규 endpoint wave | 25 endpoint 60→80% |
| **4** | (조건부) cross-scheduler rate limit race 별도 chunk | 운영 위반 시 진입 | § 43.7 변동 없음 |
| **5** | (5-19 이후) § 36.5 1주 모니터 측정 | § 43 효과 정량화 | 12 scheduler elapsed / catch-up 빈도 |
| **6** | Phase D-2 ka10080 분봉 (마지막) | 대기 | 대용량 파티션 결정 동반 |
| **7** | F-1 후속 LOW chunk (선택) | 후속 | 9 LOW 정리 |
| **8** | secret 회전 / .env.prod 정리 | 전체 개발 완료 후 | — |

## Key Decisions Made (본 chunk)

1. **`trade_compare_rate (8,4) → (12,4)`** — 거래량 비교 큰 종목 대응 (실측 max 8950 × 10000배 여유)
2. **`low_250d_pre_rate (8,4) → (10,4)`** — 250일 저가 대비 100만% 까지 (실측 5745 × 175배 여유)
3. **`SentinelStockCodeError(ValueError)` 신설 (adapter layer)** — application 이 import / `ValueError` 상속으로 기존 caller 호환
4. **`FundamentalSyncResult.skipped: tuple[FundamentalSyncOutcome, ...]` field** — sentinel skip 분리 / `failed` 의미 = 실제 실패 (sentinel 제외)
5. **`FundamentalSyncResultOut.skipped` 응답 노출** (plan § 5.3 / 2b M-1) — 운영자 가시성
6. **`refresh_fundamental` 라우터 sentinel catch 안전망** (2a M-1) — Path pattern 우선 차단되지만 master DB sentinel active 시 도달
7. **다른 NUMERIC 컬럼 (per/pbr/ev/roe) 손대지 않음** — over-engineering 회피. `roe_pct (8,2)` 9999.99% 한계는 known issue inherit

## Known Issues

| # | 항목 | 출처 | 결정 |
|---|------|------|------|
| 13 | 일간 cron 실측 | dry-run § 20.4 | 5-19 이후 |
| 20 | NXT 우선주 sentinel 빈 row 1 | § 32.3 | LOW |
| 22 | `.env.prod` 정리 | § 38.6.2' | 개발 완료 후 |
| 23 | secret 회전 | § 38.8 #6/#7 | 개발 완료 후 |
| ~~24~~ | ~~Mac 절전 시 컨테이너 중단~~ | § 38.8 #1 / § 42 / § 43 / § 44 | 🔄 부분 해소 / 5-15 자연 cron 진정 검증 대기 |
| ~~29~~ | ~~ka10001 stock_fundamental 7.2% 실패~~ | 5-13 18:00 cron | ✅ **해소** (Phase F-1, ADR § 45) — Migration 017 + sentinel 분리 |
| 30 | 2b 2R M-1 cross-scheduler catch-up race | § 43 plan § 5 H-6 | 운영 위반 시 별도 chunk |
| **31** | **backfill 임계치 5% vs alphanumeric guard 7% 충돌** | § 44.9 | **F-2 chunk (다음 1순위)** |

## Context for Next Session

### F-2 진입 시 즉시 할 일

`backfill_short.py` + `backfill_lending_stock.py` 의 5% 임계치 분리. F-1 의 `SentinelStockCodeError` + `result.skipped` 패턴 backfill CLI 에 1:1 적용 가능 — 단, backfill CLI 는 service 가 아니라 CLI 스크립트 layer 라 패턴 fit 검토 필요.

```bash
# F-2 plan doc 위치 (작성 권고)
src/backend_kiwoom/docs/plans/phase-f-2-backfill-alphanumeric-guard.md
```

대안 — alphanumeric pre-filter (CLI 진입 시점에 `^[0-9]{6}$` 종목만 호출, KRX 호출 budget 절약):
- `backfill_short.py` — active stock list fetch 후 numeric-only filter
- `backfill_lending_stock.py` — 동일 패턴

`failed` vs `alphanumeric_skipped` 분리 (F-1 패턴) vs alphanumeric pre-filter — 두 옵션 비교 plan doc 에서 결정.

### 5-15 + 5-14 18:00 검증 (사용자 대기 / 자연 발생)

```bash
# 5-14 18:00 ka10001 cron 효과 검증 (Phase F-1)
docker compose logs kiwoom-app --since 6h 2>&1 | grep -iE "ka10001|stock_fundamental|NumericValueOutOfRange|skipped"
PGPASSWORD=kiwoom psql -h localhost -p 5433 -U kiwoom -d kiwoom_db -c "
SELECT count(*) FROM kiwoom.stock_fundamental WHERE asof_date = CURRENT_DATE;"
# 기대: ~4379 row + 0 NumericValueOutOfRangeError

# 5-15 06:00 cron 검증 (Phase D + 44 + 45 종합)
# (HANDOFF 직전 turn 의 5-15 체크리스트 5종 참조 — git show b9d32a6 -- HANDOFF.md)
```

### 운영 위험 / 주의

- **Migration 017 운영 적용 완료** — 5-14 09:58 KST 시점. 5-14 18:00 ka10001 cron 부터 효과 적용
- **`failed` 의미 변경 영향**: 기존 baseline (7.2% 실패) 과 비교 불가. 본 chunk 적용 후 _실제 failed_ 가 0% 근접 예상 → 임계치 5% 가드 의미 회복
- **Migration 017 downgrade RAISE 메시지 `%건` 포맷 LOW** — PG 실행 자체는 OK / 운영 로그 가시성만 영향. 다음 LOW chunk 시 fix

## Files Modified This Session

### 5 Production
- `app/adapter/out/kiwoom/stkinfo.py` (+39/-2)
- `app/application/service/stock_fundamental_service.py` (+35/-2)
- `app/adapter/out/persistence/models/stock_fundamental.py` (+8/-2)
- `app/adapter/web/routers/fundamentals.py` (+24/-1)
- `migrations/versions/017_ka10001_numeric_precision.py` (신규 89)

### 5 Test 신규
- `tests/test_stkinfo_sentinel.py` (+145)
- `tests/test_stock_fundamental_service_sentinel.py` (+205)
- `tests/test_stock_fundamental_repository_overflow.py` (+165)
- `tests/test_migration_017_numeric_precision.py` (+210)
- `tests/test_fundamental_router.py` (+100)

### 2 Test 회귀 보완
- `tests/test_migration_004.py` (+13/-4)
- `tests/test_migration_016.py` (+9/-2)

### 1 Plan doc 신규
- `src/backend_kiwoom/docs/plans/phase-f-1-ka10001-numeric-sentinel.md`

### 1 ADR 갱신
- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 45 신규 (7 sub-§)

### 3 메타 갱신
- `src/backend_kiwoom/STATUS.md` (§ 0 / § 4 #29 해소 마크 / § 5 우선순위)
- `HANDOFF.md` (본 파일 — rewrite)
- `CHANGELOG.md` prepend

### Verification
- ruff: All checks passed
- mypy --strict: 95 files Success
- pytest: **1236 passed** / coverage **86.19%**
- 컨테이너: alembic head=`017_ka10001_numeric_precision` / kiwoom-app `Up healthy`

---

_Phase F-1 chunk 완결. § 4 #29 (5-13 cron 7.2% 실패) 해소. 다음 = F-2 backfill 임계치 분리 + 5-15 자연 cron 검증._
