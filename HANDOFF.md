# Session Handoff

> Last updated: 2026-05-14 (KST) — Phase F-2 backfill 임계치 / alphanumeric guard 분리 ted-run 풀 파이프라인 완료
> Branch: `master`
> Latest commit: `<this commit>` (Phase F-2 + ADR § 46 + 메타 4종)
> 미푸시: **2건** (`ced66f3` F-1 + `<this commit>` F-2 — 사용자 명시 요청 시 푸시)
> 본 세션 commit 1건: `<this commit>` (Phase F-2) → 미푸시

## Current Status

ADR § 4 #31 (backfill 5% 임계치 vs alphanumeric 6.75% 자연 분포 충돌) + § 44.9 (5-14 운영 인시던트 turn 발견) 의 **backfill_short.py + backfill_lending_stock.py 분기**를 처리하는 ted-run 풀 파이프라인 chunk. F-1 의 `SentinelStockCodeError` 패턴 (§ 45) 을 shsa/slb adapter + service bulk + scheduler cron + CLI 까지 1:1 확장.

### Phase F-2 핵심 변경

```python
# 1. app/adapter/out/kiwoom/shsa.py + slb.py — adapter raise type 교체
from app.adapter.out.kiwoom.stkinfo import SentinelStockCodeError
if not (len(stock_code) == 6 and stock_code.isdigit()):
    raise SentinelStockCodeError(f"stock_code 6자리 숫자만 허용 — 입력={stock_code!r}")

# 2. app/application/dto/short_selling.py — DTO 신규 필드 (합산)
@dataclass(frozen=True)
class ShortSellingBulkResult:
    total_skipped: int = 0
    skipped_outcomes: tuple[ShortSellingIngestOutcome, ...] = field(default_factory=tuple)
    # ... (기존 필드)

# 3. app/application/dto/lending.py — DTO 신규 필드 (분리)
@dataclass(frozen=True)
class LendingStockBulkResult:
    total_alphanumeric_skipped: int = 0  # 신규 — alphanumeric pre-filter + sentinel catch
    alphanumeric_skipped_outcomes: tuple[LendingStockIngestOutcome, ...] = field(default_factory=tuple)
    # total_skipped 유지 (empty 응답 의미, Phase E 부터)

# 4. service bulk loop — pre-filter + sentinel catch + 임계치 메시지
_NUMERIC_STOCK_CODE_RE = re.compile(r"^[0-9]{6}$")

async def execute(..., filter_alphanumeric: bool = False) -> ...:
    if filter_alphanumeric:
        stocks = [s for s in stocks if _NUMERIC_STOCK_CODE_RE.fullmatch(s.stock_code)]
        # 제외 종목 outcome 적재 (error="alphanumeric_pre_filter")
    for stock in stocks:
        try:
            ...
        except SentinelStockCodeError:
            outcome = ShortSellingIngestOutcome(..., error="sentinel_skip")
            skipped_outcomes_list.append(outcome); total_skipped += 1
        except KiwoomError as exc:
            ...
    # 임계치 메시지에 (alphanumeric_skipped=N) 명시

# 5. CLI — UseCase 호출 시 filter_alphanumeric=True
result = await use_case.execute(start_date=..., end_date=..., filter_alphanumeric=True)
print(f"alphanumeric_skipped:{result.total_skipped}")  # or total_alphanumeric_skipped

# 6. scheduler cron log — total_skipped / alphanumeric_skipped 가시성 추가 (3 분기 × 2 파일)
```

| 항목 | 결과 |
|------|------|
| 코드 변경 | 9 production + 1 infra = 10 파일 +236 / -29 |
| 테스트 변경 | 6 신규 (31 케이스) + 2 회귀 보완 = 8 파일 +~940 |
| 1R 2a (sonnet) | CONDITIONAL → PASS / HIGH 2 + MEDIUM 3 + LOW 3 → 8 fix |
| 1R 2b (opus) | CONDITIONAL → PASS / HIGH 2 + MEDIUM 4 + LOW 3 → 8 fix |
| 2R 2a (sonnet) | CONDITIONAL → 병합 가능 / HIGH 1 자체 강등 / MEDIUM 2 inherit |
| 2R 2b (opus) | CONDITIONAL → 병합 가능 / HIGH 0 / MEDIUM 2 inherit |
| Verification 5관문 | ✅ ruff clean / mypy strict 105 files / **1267 tests / cov 86.43%** / 런타임 smoke |

### Step 2 fix 8건 (사용자 4 확정 D-1~D-4 후)

| # | 항목 | 처리 |
|---|------|------|
| H-1 A | lending `is_active` SQL 필터 복원 + test 재설계 | `total_stocks` 분모 active-only 회복 / `test_bulk_total_skipped_distinct_from_alphanumeric_skipped` 시나리오 변경 |
| MED-1 | F-1 `skipped: tuple[...]` 패턴 1:1 이식 | `skipped_outcomes` / `alphanumeric_skipped_outcomes` tuple + outcome.error 값 `"alphanumeric_pre_filter"` / `"sentinel_skip"` |
| MED-2 | scheduler cron log 가시성 | `short_selling_job.py` `total_skipped=%d` / `lending_stock_job.py` `alphanumeric_skipped=%d` (3 분기 × 2 파일) |
| 2a H-1 | 정규식 앵커 명시 | `r"[0-9]{6}"` → `r"^[0-9]{6}$"` |
| 2a M-1 | 키워드 정렬 자동 충족 | 변경 0 |
| 2b M-4 | alembic env.py 결정 | `disable_existing_loggers=False` 유지 (필요한 안전 조치, 운영 alembic 은 subprocess) |
| H-2 | short/lending SQL 패턴 통일 | H-1 처리로 자동 해소 |
| 2a M-2 | 분모 정의 통일 | H-1 처리로 자동 해소 |

### R2 inherit 7건 (다음 chunk, ADR § 46.8)

| # | 출처 | 항목 |
|---|------|------|
| 1 | 2b M-A | lending 임계치 분모 pre_filter_skipped 포함 vs short 제외 — 정의 통일 |
| 2 | 2b M-B | `outcome.error` 매직 스트링 → `SkipReason` Enum 도입 |
| 3 | 2a M-R2-1 | `errors_above_threshold` 타입 비대칭 (short=bool / lending=tuple) |
| 4 | 2a M-R2-2 | empty stocks 조기 반환 패턴 비일관 |
| 5 | 2a H-R2-1 (자체 강등) | `backfill_short.py:189` label-field 명 mismatch |
| 6 | 2b L-A/L-B | dead 파라미터 / `skipped_count` property 부재 |
| 7 | 2b L-C | 단건 UseCase `SentinelStockCodeError` 미캐치 (defense-in-depth) |

## Completed This Session

| # | Step | 결과 | 모델 | Files |
|---|------|------|------|-------|
| 0 | TDD | 6 신규 / 31 케이스 / 29 red + 2 green guard | sonnet (3 sub-agent 병렬) | 6 (test) |
| 1 | 구현 | 9 production + 1 infra / 1267 PASS / ruff+mypy clean | opus | 9 (production) + 1 (infra) |
| 2a R1 | 1차 리뷰 | CONDITIONAL — HIGH 2 / MEDIUM 3 | sonnet | (변경 0) |
| 2b R1 | 적대적 리뷰 | CONDITIONAL — HIGH 2 / MEDIUM 4 | opus | (변경 0) |
| 2 fix | 8건 일괄 | H-1 A SQL 복원 + MED-1 F-1 패턴 + MED-2 cron + 등 | opus | (production + test 보완) |
| 2a R2 | 재리뷰 1회 | CONDITIONAL → 병합 가능 / inherit 5 | sonnet | (변경 0) |
| 2b R2 | 재리뷰 1회 | CONDITIONAL → 병합 가능 / inherit 5 | opus | (변경 0) |
| 3 | Verification | 5관문 PASS / 1267 / cov 86.43% | sonnet+haiku | (변경 0) |
| 4 | E2E | ⚪ UI 변경 0 | — | — |
| 5 | Ship | ADR § 46 + 메타 4종 + 커밋 | 메인 | 4 메타 |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| **1** | **Phase F (순위 5종) — ka10027/30/31/32/23** | **다음 세션 1순위** | 신규 endpoint wave (25 endpoint 60→80%). F-1/F-2 ops fix 완료로 도메인 확장 진입 가능 |
| **2** | **5-15 (금) 06:00 자연 cron 검증** | 운영 검증 | § 43 + § 44 + § 45 + § 46 효과 동시. 5-14 07:30/08:00 short/lending cron 도 sentinel catch 효과 확인. 코드 0 |
| **3** | **F-2 R2 inherit 7건** (ADR § 46.8) | 정리 chunk | M-A 분모 통일 / M-B Enum / M-R2-1 타입 / M-R2-2 패턴 / H-R2-1 label / L-A~C |
| 4 | (5-19 이후) § 36.5 1주 모니터 측정 | § 43 효과 정량화 | 12 scheduler elapsed / catch-up 빈도 |
| 5 | Phase D-2 ka10080 분봉 (마지막) | 대기 | 대용량 파티션 결정 동반 |
| 6 | (조건부) cross-scheduler rate limit race 별도 chunk | 운영 위반 시 진입 | § 43.7 변동 없음 |
| 7 | secret 회전 / .env.prod 정리 | 전체 개발 완료 후 | — |

## Key Decisions Made (본 chunk)

1. **D-1: A + B 하이브리드 채택** — service catch (cron 임계치 회복) + CLI pre-filter (호출 budget -73s) 동시
2. **D-2: `total_alphanumeric_skipped` 분리 신규 필드** (lending) — 기존 `total_skipped` (empty 응답 의미) 유지. DTO breaking 최소
3. **D-3: 임계치 분모 유지 + error 메시지에 `(alphanumeric_skipped=N)` 명시** — sentinel catch 효과로 분모 의미 자연 회복
4. **D-4: UseCase `filter_alphanumeric: bool = False` 신규 파라미터** — CLI True / scheduler cron False (backward compat). plan § 4 #10
5. **R2 H-1 A: lending `is_active` SQL 필터 복원** — short 와 SQL 패턴 통일. `test_bulk_total_skipped_distinct_from_alphanumeric_skipped` 시나리오 재설계
6. **MED-1: F-1 `skipped: tuple[FundamentalSyncOutcome, ...]` 패턴 1:1 이식** — 종목 명세 보존 (KOSCOM 대조 / 사후 디버깅)
7. **MED-3: short `total_skipped` (합산) vs lending `total_alphanumeric_skipped` (분리) 네이밍 비대칭 ADR § 46.9 명시 + 현행 유지** — DTO breaking 회피. future-service 진입 시 _합산_ 선호
8. **migrations/env.py `disable_existing_loggers=False`** — `fileConfig` 후 "app" logger disabled=True 회귀 차단. 운영 alembic 은 subprocess 라 영향 0
9. **scheduler cron `filter_alphanumeric=False` 기본값 유지** (변경 0) — A 의 sentinel catch 만으로 임계치 의미 회복

## Known Issues

| # | 항목 | 출처 | 결정 |
|---|------|------|------|
| 13 | 일간 cron 실측 | dry-run § 20.4 | 5-19 이후 |
| 20 | NXT 우선주 sentinel 빈 row 1 | § 32.3 | LOW |
| 22 | `.env.prod` 정리 | § 38.6.2' | 개발 완료 후 |
| 23 | secret 회전 | § 38.8 #6/#7 | 개발 완료 후 |
| ~~24~~ | ~~Mac 절전 시 컨테이너 중단~~ | § 38.8 #1 / § 42 / § 43 / § 44 | 🔄 부분 해소 / 5-15 자연 cron 진정 검증 대기 |
| ~~29~~ | ~~ka10001 stock_fundamental 7.2% 실패~~ | 5-13 18:00 cron | ✅ 해소 (Phase F-1, ADR § 45) |
| 30 | 2b 2R M-1 cross-scheduler catch-up race | § 43 plan § 5 H-6 | 운영 위반 시 별도 chunk |
| ~~31~~ | ~~backfill 임계치 5% vs alphanumeric guard 7% 충돌~~ | § 44.9 | ✅ **해소** (Phase F-2, ADR § 46) — F-1 sentinel 패턴 1:1 확장 |
| **32** | **R2 inherit 7건** (ADR § 46.8) | R2 재리뷰 | 다음 chunk 정리 또는 Phase F 합류 |

## Context for Next Session

### Phase F 진입 시 즉시 할 일

Phase F (순위 5종) plan doc 작성 — `src/backend_kiwoom/docs/plans/phase-f-rankings.md` (또는 endpoint 별 5 doc). 5 endpoint 통합 1 chunk 검토 — `ka10027` (전일대비등락률상위) / `ka10030` (당일거래량상위) / `ka10031` (전일거래량상위) / `ka10032` (거래대금상위) / `ka10023` (거래량급증). 공통 패턴 = 순위 응답 row × N (변동 columns 동일?) — Phase E `short_selling_kw` 패턴 검토 권고.

```bash
# 사전 분석
src/backend_kiwoom/docs/plans/endpoint-18-ka10027.md ~ endpoint-22-ka10023.md
src/backend_kiwoom/docs/plans/master.md § 4 (Phase F)
```

### 5-15 (금) 06:00 + 07:30 + 08:00 자연 cron 검증

```bash
# 5-15 06:00 cron 검증 (Phase D + 44 + 45 종합)
docker compose logs kiwoom-app --since 12h 2>&1 | grep -iE "OhlcvDaily|DailyFlow|StockMaster|SectorDaily" | head -20

# 5-14 07:30 short_selling cron + 08:00 lending_stock cron 검증 (Phase F-2 효과 — sentinel catch)
docker compose logs kiwoom-app --since 12h 2>&1 | grep -iE "ka10014|ka20068|short_selling|lending_stock|alphanumeric_skipped|total_skipped" | head -40

# 5-14 18:00 stock_fundamental cron 검증 (Phase F-1 효과 — NumericValueOutOfRangeError 0)
docker compose logs kiwoom-app --since 6h 2>&1 | grep -iE "ka10001|stock_fundamental|NumericValueOutOfRange|skipped"
PGPASSWORD=kiwoom psql -h localhost -p 5433 -U kiwoom -d kiwoom_db -c "
SELECT count(*) FROM kiwoom.stock_fundamental WHERE asof_date = CURRENT_DATE;"
# 기대: ~4379 row + 0 NumericValueOutOfRangeError + alphanumeric_skipped > 0 (cron 은 filter_alphanumeric=False 유지)

# backfill 재실행 smoke (alphanumeric pre-filter 효과 확인)
docker compose exec -T kiwoom-app python scripts/backfill_short.py --alias prod --start 2026-05-12 --end 2026-05-13 2>&1 | tail -10
# 기대: total_failed=0 / exit code 0 / alphanumeric_skipped > 0 / elapsed -73s 단축
```

### 운영 위험 / 주의

- **Phase F-2 cron 효과**: 5-14 07:30/08:00 short_selling/lending_stock cron 부터 sentinel catch 적용 — `total_failed` 의미 = 실제 KRX/DB 오류만. baseline (5-13 fail 307 / 303) 비교 시 _대폭 감소_ 예상 (운영 알람 정상화)
- **`filter_alphanumeric=False` 유지 (cron 기본)**: cron 은 alphanumeric 종목 호출 자체 계속 (KRX 호출 budget 변동 0). sentinel catch 만 활성 — 임계치 의미 회복 + log 가시성
- **R2 inherit 5건 MEDIUM**: 다음 chunk 또는 Phase F 합류 시 일괄 정리. 본 chunk 차단 0 (양쪽 합의)

## Files Modified This Session

### 9 Production
- `app/adapter/out/kiwoom/shsa.py` (+9/-2)
- `app/adapter/out/kiwoom/slb.py` (+6/-1)
- `app/application/dto/short_selling.py` (+11/-2)
- `app/application/dto/lending.py` (+8/-2)
- `app/application/service/short_selling_service.py` (+85/-7)
- `app/application/service/lending_service.py` (+88/-7)
- `app/batch/short_selling_job.py` (+6/-3)
- `app/batch/lending_stock_job.py` (+6/-3)
- `scripts/backfill_short.py` (+9/-1) + `scripts/backfill_lending_stock.py` (+4/-0)

### 6 Test 신규 (31 케이스)
- `tests/test_shsa_sentinel.py` (16) / `tests/test_slb_sentinel.py` (16)
- `tests/test_short_selling_service_sentinel.py` (4) / `tests/test_lending_service_alphanumeric_skipped.py` (5)
- `tests/test_backfill_short_filter.py` (3) / `tests/test_backfill_lending_stock_filter.py` (3)

### 2 Test 회귀 보완
- `tests/test_short_selling_service.py` / `tests/test_lending_service.py` (mock fixture skipped_outcomes 단언 보완)

### 1 Infra
- `migrations/env.py` (+4/-1) — `disable_existing_loggers=False`

### 1 Plan doc 신규
- `src/backend_kiwoom/docs/plans/phase-f-2-backfill-alphanumeric-guard.md` (§ 4 확정 결정 + § 9 ted-run input)

### 1 ADR 갱신
- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 46 신규 (9 sub-§)

### 3 메타 갱신
- `src/backend_kiwoom/STATUS.md` (§ 0 / § 4 #31 해소 / § 5 우선순위 / § 6 누적 3 chunk 추가)
- `HANDOFF.md` (본 파일 — rewrite)
- `CHANGELOG.md` prepend

### Verification
- ruff: All checks passed
- mypy --strict: 105 files Success
- pytest: **1267 passed** / coverage **86.43%** (+0.24%p)
- 컨테이너: kiwoom-app + kiwoom-db `Up healthy 5h` (본 chunk 코드 적용 안 됨 — 커밋 후 redeploy 시점 사용자 결정)

---

_Phase F-2 chunk 완결. § 4 #31 (backfill 5% 임계치 vs alphanumeric 6.75% 충돌) 해소. § 44.9 해소. 다음 = Phase F 순위 5종 (ka10027/30/31/32/23) + 5-15 자연 cron 검증._
