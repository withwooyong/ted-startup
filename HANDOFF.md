# Session Handoff

> Last updated: 2026-05-14 (KST) — Phase F-3 R2 inherit 7건 정리 ted-run 풀 파이프라인 완료
> Branch: `master`
> Latest commit: `<this commit>` (Phase F-3 + ADR § 47 + 메타 4종)
> 미푸시: **3건** (`ced66f3` F-1 + `8f6b453` F-2 + `<this>` F-3 — 사용자 명시 요청 시 푸시)
> 본 세션 commit: 1건 (Phase F-3) → 미푸시

## Current Status

ADR § 46.8 R2 inherit 7건 전부 해소 + § 47 신규. Phase F-4 (5 ranking endpoint 통합) 진입 _전_ 정착 패턴 정리 완료. F-1 (sentinel WARN/skipped) → F-2 (alphanumeric guard 분리) → **F-3 (SkipReason Enum + 패턴 통일)** 까지 wave 종결. ted-run 풀 파이프라인 (`--force-2b`) + 사용자 8 확정 D-1~D-8 (권고 default 일괄 채택).

### Phase F-3 핵심 변경

```python
# 1. app/application/dto/_shared.py (신규)
class SkipReason(StrEnum):
    """bulk loop / pre-filter 의 skip 사유 분류 (Phase F-3 D-2)."""
    ALPHANUMERIC_PRE_FILTER = "alphanumeric_pre_filter"
    SENTINEL_SKIP = "sentinel_skip"

# 2. 매직 스트링 7 사이트 → SkipReason.*.value
# short_selling_service.py 258/309/362 + lending_service.py 296/340 + 양쪽 DTO docstring

# 3. errors_above_threshold 타입 통일 (D-3)
@dataclass(frozen=True)
class ShortSellingBulkResult:
    errors_above_threshold: tuple[str, ...] = field(default_factory=tuple)  # bool → tuple
    # router DTO 도 동일 (Pydantic Field default_factory=tuple)
    # service: errors_above_threshold: list[str] = [] 누적 후 tuple(...) 반환

# 4. _empty_bulk_result private helper (D-5, keyword-only)
def _empty_bulk_result(*, pre_filter_skipped: int, skipped_outcomes: list[...]) -> ShortSellingBulkResult:
    """active 종목 0개 시 조기 반환 DTO 빌더."""
    return ShortSellingBulkResult(...)

# 5. 단건 UseCase D-7 catch (defense-in-depth)
class IngestShortSellingUseCase:
    async def execute(self, stock_code: str, ...) -> ShortSellingIngestOutcome:
        """...
        Phase F-3 D-7 — defense-in-depth:
            라우터 정규식 우회 호출 시에도 SentinelStockCodeError 를 catch 하여
            outcome.error = SkipReason.SENTINEL_SKIP.value 로 변환 + upserted=0 반환.
        """
        try:
            ...
        except SentinelStockCodeError:
            return ShortSellingIngestOutcome(stock_code=stock_code, exchange=exchange,
                                              error=SkipReason.SENTINEL_SKIP.value)

# 6. skipped_count property 양쪽 (D-8, 비대칭 흡수)
@property
def skipped_count(self) -> int:
    """skip 카운터 표준 인터페이스. ADR § 46.9 비대칭 historical alias."""
    return self.total_skipped  # short / self.total_alphanumeric_skipped (lending)

# 7. backfill_short.py:189 label fix (D-6)
f"total_skipped:       {result.total_skipped}"  # 기존: f"alphanumeric_skipped:..."

# 8. dead path # pragma: no cover (M-1 fix)
except SentinelStockCodeError:  # pragma: no cover — dead path after F-3 D-7
    # 단건 UseCase 가 D-7 catch 로 도달 차단. 향후 wrap 변경 대비 안전망.
    sentinel_skipped += 1
    ...
```

| 항목 | 결과 |
|------|------|
| 코드 변경 | 8 production + 4 갱신 + 3 신규 + 1 회귀 = 16 파일 +573/-230 |
| 신규 케이스 | 17 (4 + 3 + 3 + 7 갱신 일부) |
| 1R 2a (sonnet) | PASS / LOW 2 (lending direct-catch + F401 noqa) |
| 1R 2b (opus) | CONDITIONAL / HIGH 2 + MEDIUM 3 + LOW 2 → fix 6건 |
| 2R 2a (sonnet) | PASS / inherit 2 LOW |
| 2R 2b (opus) | CONDITIONAL → ruff auto-fix 3건 / inherit 5건 |
| Verification 5관문 | ✅ ruff clean / mypy strict **106 files** / **1284 tests** (+17) / cov **86.56%** (+0.13%p) / 런타임 imports OK |

### Step 2 fix 6건 (R1 결과)

| # | 항목 | 처리 |
|---|------|------|
| H-1 | lending `else` 블록 sentinel commit 중복 | commit 블록 제거. loop tail 단일 commit 흡수. short_selling 자연흐름 일관 |
| M-1 | bulk loop 기존 except 분기 dead path | short(KRX/NXT) + lending 3 사이트에 `# pragma: no cover — dead path after F-3 D-7` + 주석 강화 |
| M-2 | 단건 UseCase silent skip docstring | 두 UseCase execute docstring 끝에 D-7 defense-in-depth 문단 (한국어) |
| M-3 | skipped_count property 비대칭 docstring | 두 DTO property docstring 강화 (§ 46.9 보존 + 미래 rename 후보) |
| L-1 | `_empty_bulk_result` 시그니처 일관성 | short positional → keyword-only. 호출처 갱신. lending 이미 keyword-only |
| L-3 | F401 noqa (R1 2a) | DTO 양쪽 `SkipReason` import + `__all__` 추가 (re-export 명시) |

### R2 fix (ruff auto)

ruff F401/I001 회귀 3건 — `ruff check --fix` 자동 해소:
- `tests/test_lending_service.py:33` (I001 import 정렬)
- `tests/test_short_selling_service.py:36` (I001 import 정렬)
- `tests/test_short_selling_service.py:688` (F401 `from unittest.mock import patch` unused)

### R2 inherit 5건 (다음 chunk, § 47.8)

| # | 출처 | 항목 | 권고 |
|---|------|------|------|
| 1 | 2b H-2 | router DTO `bool → tuple[str, ...]` breaking 외부 호출자 식별 | Phase F-4 합류 (ranking router 진입 시) |
| 2 | 2b M-1 | `pyproject.toml` `[tool.coverage]` 명시 설정 부재 — coverage.py default 의존 | coverage 설정 chunk (별도) |
| 3 | 2b L-2 | `SkipReason` 위치 `dto/_shared.py` vs `application/constants.py` 통일 결정 | 향후 enum 모듈 통합 결정 |
| 4 | R1 기존 (R2 보존) | lending bulk progress log `total_skipped` 카운터 이름 혼선 (R1 기존 코드 부채) | 후속 정리 chunk (코드 변경 0 가능) |
| 5 | 2b NEW (해소됨) | ruff F401/I001 회귀 3건 — ✅ 본 chunk 해소 (auto) | 기록 보존만 |

## Completed This Session

| # | Step | 결과 | 모델 | Files |
|---|------|------|------|-------|
| 0 | TDD | 17 신규 / 5 collection error + 4 FAILED 의도된 red | sonnet | 3 신규 + 5 갱신 |
| 1 | 구현 | 8 production + 1 test 회귀 / 1284 PASS / ruff+mypy clean | opus | 9 |
| 2a R1 | 1차 리뷰 | PASS / LOW 2 | sonnet | (변경 0) |
| 2b R1 | 적대적 리뷰 | CONDITIONAL — HIGH 2 + MEDIUM 3 + LOW 2 | opus | (변경 0) |
| 2 fix R1 | 6건 일괄 | H-1 commit / M-1 마커 / M-2 D-7 docstring / M-3 property / L-1 keyword-only / L-3 F401 | opus | 4 (production + test) |
| 2a R2 | 재리뷰 | PASS / inherit 2 LOW | sonnet | (변경 0) |
| 2b R2 | 재리뷰 | CONDITIONAL → ruff auto-fix / inherit 5건 | opus | (변경 0) |
| 2 fix R2 | ruff auto | F401/I001 3건 | (auto) | 2 (test) |
| 3 | Verification | 5관문 PASS / 1284 / cov 86.56% / mypy 106 files / 런타임 imports OK | sonnet+haiku | (변경 0) |
| 4 | E2E | ⚪ UI 변경 0 | — | — |
| 5 | Ship | ADR § 47 + 메타 4종 + 커밋 | 메인 | 4 메타 |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| **1** | **Phase F-4 — 5 ranking endpoint 통합** (ka10027/30/31/32/23) | **다음 세션 1순위** | plan doc 작성됨 (`phase-f-4-rankings.md`). D-1~D-14 사용자 확정 + 견적 ~2,500줄 분할 재검토 (옵션 a/b/c). F-3 정착 패턴 (SkipReason / tuple errors_above_threshold / empty helper / 단건 catch) 위에서 작업 |
| **2** | **5-15 (금) 06:00 자연 cron 검증** | 운영 검증 | § 43 + § 44 + § 45 + § 46 + § 47 효과 동시. 5-14 07:30/08:00 short/lending cron 도 F-3 patterns 적용 효과 확인. 코드 0 |
| **3** | **F-3 R2 inherit 5건** (ADR § 47.8) | 정리 또는 합류 | inh-1 router DTO breaking consumer 식별 / inh-2 coverage 설정 / inh-3 SkipReason 위치 / inh-4 lending progress log / inh-5 ruff auto-fix (해소됨) — Phase F-4 합류 가능 |
| 4 | (5-19 이후) § 36.5 1주 모니터 측정 | § 43 효과 정량화 | 12 scheduler elapsed / catch-up 빈도 |
| 5 | Phase D-2 ka10080 분봉 (마지막) | 대기 | 대용량 파티션 결정 동반 |
| 6 | (조건부) cross-scheduler rate limit race 별도 chunk | 운영 위반 시 진입 | § 43.7 변동 없음 |
| 7 | secret 회전 / .env.prod 정리 | 전체 개발 완료 후 | — |

## Key Decisions Made (본 chunk)

1. **D-1: `app/application/dto/_shared.py` 신규 모듈** — DTO layer 공유 enum 의 표준 위치. `app/application/constants.py` (도메인 상수) 와 분리
2. **D-2: StrEnum** — `outcome.error: str` 그대로 string 호환 (`outcome.error == SkipReason.SENTINEL_SKIP` 호환). value = 기존 매직 스트링 그대로 (KOSCOM/log 분석 영향 0)
3. **D-3: short DTO `errors_above_threshold: bool` → `tuple[str, ...]` (lending 패턴 통일)** — router DTO breaking 변경 (§ 47.6 명시). dev pre-release 가정 하 진행
4. **D-4: warnings + errors_above_threshold 둘 다 보존 + cron 둘 다 알람** — 의미 분리 유지
5. **D-5: `_empty_bulk_result` private helper (keyword-only)** — Phase F-4 5 endpoint bulk 가 5 곳 더 늘어남 — break-even 명확
6. **D-6: `backfill_short.py:189` label `total_skipped:` 일치** — DTO field rename 아님 (§ 46.9 보존)
7. **D-7: 단건 UseCase `SentinelStockCodeError` catch + outcome.error = `SkipReason.SENTINEL_SKIP.value`** — defense-in-depth. Phase F-4 ranking router 에도 동일 패턴 적용 가능
8. **D-8: `skipped_count` property 양쪽** — 비대칭 흡수. caller 가 동일 인터페이스로 두 DTO 접근. § 46.9 historical alias 보존
9. **R1 H-1: lending `else` 블록 commit 중복 제거** — loop tail 단일 commit 흡수. short_selling 자연흐름과 commit 모델 일관
10. **R1 M-1: dead path `# pragma: no cover` 마커 3 사이트** — 단건 UseCase D-7 catch 가 도달 차단 / 향후 wrap 변경 대비 안전망

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
| ~~31~~ | ~~backfill 임계치 5% vs alphanumeric guard 7% 충돌~~ | § 44.9 | ✅ 해소 (Phase F-2, ADR § 46) |
| ~~32~~ | ~~F-2 R2 inherit 7건~~ | ADR § 46.8 | ✅ **해소** (Phase F-3, ADR § 47) — D-1~D-8 사용자 확정 일괄 채택. SkipReason StrEnum + tuple 통일 + empty helper + 단건 catch + skipped_count property + backfill label fix. 16 파일 / 1284 tests / cov 86.56% |
| **33** | Phase F-4 chunk 크기 ~2,500줄 임계 초과 | 견적 | ted-run 입력 직전 분할 (b/c) 재논의 권고 |
| **34** | F-3 R2 inherit 5건 | ADR § 47.8 | inh-1 router DTO breaking consumer / inh-2 coverage 설정 / inh-3 SkipReason 위치 / inh-4 lending progress log / inh-5 ruff auto-fix 기록. Phase F-4 합류 가능 |

## Context for Next Session

### Phase F-4 진입 시 즉시 할 일

1. **chunk 분할 재검토** — F-4 견적 ~2,500줄 = `feedback_chunk_split_for_pipelines` 임계 초과. ted-run 입력 직전 D-1 답 갱신:
   - (a) 통합 1 chunk 유지 (현 plan)
   - (b) F-4a (인프라+ka10027) / F-4b (10030/31) / F-4c (10032/23) = 3 sub-chunk
   - (c) F-4a (인프라+ka10027) / F-4b (나머지 4) = 2 sub-chunk
2. **D-1~D-14 사용자 확정** — `phase-f-4-rankings.md § 4` 표 (14 결정)
3. **endpoint-18-ka10027.md reference** + 19~22 (차이점) 와 cross-reference
4. **Migration 007 운영 적용 dry-run** — kiwoom-db alembic upgrade head smoke 필수
5. **F-3 정착 패턴 활용** — SkipReason / tuple errors_above_threshold / empty helper / 단건 catch 를 ranking adapter / service / router 에 1:1 이식
6. **첫 cron 발화 (5-19 다음 평일 19:30)** — 운영 검증 항목 (stk_cls / cnt / cntr_str 의미 / 응답 row 수 / NXT 코드 / ka10030 23 필드)

### 5-15 (금) 06:00 + 07:30 + 08:00 자연 cron 검증

```bash
# 5-15 06:00 cron 검증 (Phase D + 44 + 45 + 47 종합)
docker compose logs kiwoom-app --since 12h 2>&1 | grep -iE "OhlcvDaily|DailyFlow|StockMaster|SectorDaily" | head -20

# 5-15 07:30 short_selling cron + 08:00 lending_stock cron 검증
# Phase F-3 효과: skipped_count property + errors=list(...) logger.error 가시성
docker compose logs kiwoom-app --since 12h 2>&1 | grep -iE "ka10014|ka20068|short_selling|lending_stock|total_skipped|alphanumeric_skipped|errors=" | head -40

# 18:00 stock_fundamental cron (Phase F-1 효과 — NumericValueOutOfRangeError 0)
docker compose logs kiwoom-app --since 6h 2>&1 | grep -iE "ka10001|stock_fundamental|NumericValueOutOfRange|skipped"
```

### 운영 위험 / 주의

- **Router DTO breaking (H-2)**: `POST /api/kiwoom/short-selling/bulk/sync` 응답 `errors_above_threshold` schema 변경 (bool → array[string]). dev pre-release 가정 하 진행. 외부 호출자 식별은 inherit (Phase F-4 시점에 Grafana / 모니터링 dashboard 검증)
- **F-3 코드 redeploy 시점**: `kiwoom-app` 컨테이너 redeploy 필요. 사용자 명시 시점 결정. 미푸시 3건 (F-1 + F-2 + F-3) 누적 — 5-15 06:00 cron 자연 검증 결과 PASS 후 일괄 푸시 가능
- **본 chunk 코드는 런타임 영향 0**: StrEnum value = 기존 매직 스트링 그대로. KOSCOM 대조 / log 분석 / DB 저장 영향 0
- **R2 inherit 5건**: Phase F-4 합류 시 일괄 정리 가능

## Files Modified This Session

### 8 Production
- `app/application/dto/_shared.py` (신규, +24/-0) — `SkipReason` StrEnum
- `app/application/dto/short_selling.py` (+25/-11) — `errors_above_threshold` tuple + `skipped_count` property + `__all__`
- `app/application/dto/lending.py` (+18/-6) — `skipped_count` property + `__all__`
- `app/application/service/short_selling_service.py` (+85/-20) — SkipReason 치환 / `_empty_bulk_result` / D-7 catch / `# pragma: no cover` 마커
- `app/application/service/lending_service.py` (+65/-16) — 동일 + R1 H-1 commit 제거
- `app/adapter/web/routers/short_selling.py` (+3/-3) — `errors_above_threshold: tuple[str, ...]`
- `app/batch/short_selling_job.py` (+4/-1) — `errors=list(...)` logger.error 인자
- `scripts/backfill_short.py` (+3/-1) — label `total_skipped:` 일치

### 4 Test 갱신
- `tests/test_short_selling_service.py` (+62/-34) — tuple 단언 + helper / skipped_count 회귀
- `tests/test_lending_service.py` (+50/-26) — 동일
- `tests/test_short_selling_service_sentinel.py` (+5/-6) — `SkipReason.SENTINEL_SKIP.value` 비교
- `tests/test_lending_service_alphanumeric_skipped.py` (+5/-6) — 동일

### 3 Test 신규 (17 케이스)
- `tests/test_skip_reason.py` (+25/-0, 4 케이스) — enum 값 안정성
- `tests/test_short_selling_use_case_sentinel.py` (+73/-0, 3 케이스) — 단건 D-7 catch
- `tests/test_lending_use_case_sentinel.py` (+75/-0, 3 케이스) — 동일

### 1 Test 회귀 보완
- `tests/test_backfill_short_filter.py` (+10/-4) — label `total_skipped:` 회귀

### 1 Plan doc 신규 (이전 turn)
- `src/backend_kiwoom/docs/plans/phase-f-3-r2-inherit-cleanup.md` (~280 line) — § 4 D-1~D-8 표 + § 9 ted-run input
- `src/backend_kiwoom/docs/plans/phase-f-4-rankings.md` (~330 line) — Phase F-4 reference

### 1 ADR 갱신
- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 47 신규 (9 sub-§)

### 3 메타 갱신
- `src/backend_kiwoom/STATUS.md` (§ 0 + § 4 #32 해소 / #34 신규 + § 5 우선순위 + § 6 누적 1 chunk 추가)
- `HANDOFF.md` (본 파일 — rewrite)
- `CHANGELOG.md` prepend

### Verification
- ruff: All checks passed!
- mypy --strict: **106 files** Success (+1 `_shared.py`)
- pytest: **1284 passed** (+17) / coverage **86.56%** (+0.13%p)
- 런타임 smoke: imports OK / `SkipReason.value` = 기존 매직 스트링 동일
- 컨테이너: `kiwoom-app` + `kiwoom-db` 본 chunk 코드 적용 안 됨 (커밋 후 redeploy 시점 사용자 결정)

---

_Phase F-3 chunk 완결. § 46.8 R2 inherit 7건 전부 해소. Phase F (순위 5종) 진입 _전_ 정착 패턴 정리 완료. 다음 = Phase F-4 (ka10027/30/31/32/23 통합 1 chunk) + 5-15 자연 cron 검증._
