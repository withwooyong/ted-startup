# phase-f-3-r2-inherit-cleanup.md — Phase F-3 R2 inherit 7건 정리 chunk

> Phase F-2 (`8f6b453`) R2 재리뷰에서 inherit 된 7건 (ADR § 46.8) 의 일괄 정리 chunk.
> Phase F (순위 5종 — ka10027/30/31/32/23) 진입 _전_ 선처리하여 SkipReason Enum / 분모 정의 / 타입 비대칭 / empty 패턴 등 정착된 패턴을 ranking 적용 전에 정리한다.

---

## 1. 메타

| 항목 | 값 |
|------|-----|
| Chunk ID | Phase F-3 |
| 선행 chunk | Phase F-2 (`8f6b453`, 2026-05-14 — R2 inherit 발생) |
| 후속 chunk | Phase F-4 (5 endpoint 통합) |
| 분류 | 정리 / 리팩토링 (코드 변경 0 산출물 부재) |
| 우선순위 | P1 (Phase F 진입 전 사전 정리) |
| 출처 | ADR § 46.8 R2 inherit 7건 표 |
| 예상 규모 | ~150-200 production line + ~100-200 test line (~250-400 lines) |
| ted-run 적용 여부 | ✅ (정리 chunk 지만 production 코드 변경 동반) |

---

## 2. 현황 (Phase F-2 R2 inherit 7건)

ADR § 46.8 의 7건을 다시 정리:

| # | 출처 (R2 round) | 항목 | 영향 | F-3 처리 옵션 |
|---|---|------|------|--------------|
| 1 | R2 2b M-A | lending 임계치 분모 (`pre_filter_skipped` 포함) vs short 분모 (제외) — _정의 표현_ 불일치 | 의미는 동일 (`len(stocks) + pre_filter_skipped`) 이나 ADR § 46 본문이 두 표현을 다르게 기록 — 코드 docstring/주석 통일 | 코드: 0 / docstring: 통일 |
| 2 | R2 2b M-B | `outcome.error` 매직 스트링 (`"alphanumeric_pre_filter"` / `"sentinel_skip"`) 분산 4 사이트 (실제 7 사이트 — dto docstring 포함) | string typo 위험 / test 단언 brittle | `SkipReason` Enum 도입 + 호출처 일괄 치환 |
| 3 | R2 2a M-R2-1 | `errors_above_threshold` 타입 비대칭 — short=`bool` (DTO 83) / lending=`tuple[str, ...]` (DTO 100) — Phase E 이전 기존 이슈 | router 매핑 차이 + scheduler cron 분기 (`short_selling_job.py:59` bool / `lending_stock_job.py:56,66` tuple) | 양쪽 `tuple[str, ...]` 로 통일 + 호출처 fix |
| 4 | R2 2a M-R2-2 | empty stocks 조기 반환 패턴 비일관 (short 263-269 / lending 301-310) | DTO 필드 set 차이 — short 는 `total_skipped=pre_filter_skipped`, lending 은 `total_alphanumeric_skipped=pre_filter_skipped` | 두 path 의 반환 DTO 가 동일 의미 fields 를 항상 set 하도록 helper 추출 |
| 5 | R2 2a H-R2-1 (자체 강등) | `scripts/backfill_short.py:189` label `alphanumeric_skipped:` 인데 필드 `result.total_skipped` 참조 — label-field 명 mismatch (런타임 OK) | 운영자가 log 보고 short DTO 에 `alphanumeric_skipped` 필드가 있다고 오해 가능 | label 을 DTO 와 일치 (`total_skipped:`) 또는 필드 rename (R2 inherit § 46.8 #5 권고: 합류) |
| 6 | R2 2b L-A / L-B | `test_backfill_short_filter` dead 파라미터 / F-1 `skipped_count` property 부재 | LOW — 테스트 가독성 / DTO 편의 property | 본 chunk 포함 권고 (rename 영향이 같이 가는 게 효율) |
| 7 | R2 2b L-C | 단건 UseCase (`IngestShortSellingForStockUseCase` / `IngestLendingStockUseCase`) 의 `SentinelStockCodeError` 미캐치 — 라우터 정규식이 ASCII 6자리 강제라 도달 경로 0 (defense-in-depth) | LOW — 미캐치 시 500 error 가능성 (라우터 우회 호출 시) | 단건 UseCase 에 try/except 추가 + outcome.error=`SkipReason.SENTINEL_SKIP` 또는 그대로 raise (사용자 결정) |

### 2.1 현재 코드 사이트 (정리 대상)

```
M-B 매직 스트링 (7 사이트)
├── app/application/dto/short_selling.py:73       # docstring
├── app/application/dto/lending.py:86             # docstring
├── app/application/service/short_selling_service.py:258, 309, 362
└── app/application/service/lending_service.py:296, 340

M-R2-1 errors_above_threshold 타입 비대칭
├── app/application/dto/short_selling.py:83       # bool = False
├── app/application/dto/lending.py:100            # tuple[str, ...] = field(default_factory=tuple)
├── app/adapter/web/routers/short_selling.py:88   # bool
├── app/adapter/web/routers/lending.py:197, 463   # tuple[str, ...]
├── app/batch/short_selling_job.py:59             # if result.errors_above_threshold (bool)
└── app/batch/lending_stock_job.py:56, 66         # list(result.errors_above_threshold)

H-R2-1 backfill_short label
└── scripts/backfill_short.py:189                 # f"alphanumeric_skipped:{result.total_skipped}"

L-C 단건 UseCase
├── app/application/service/short_selling_service.py    # IngestShortSellingForStockUseCase.execute
└── app/application/service/lending_service.py          # IngestLendingStockUseCase.execute
```

---

## 3. 범위 외 (out of scope)

| 항목 | 이유 | 후속 chunk |
|------|------|-----------|
| ranking endpoint (ka10027/30/31/32/23) 코드화 | Phase F-4 의 본 작업 | Phase F-4 |
| ADR § 46.9 네이밍 비대칭 (`short.total_skipped` vs `lending.total_alphanumeric_skipped`) 통일 rename | 사용자 확정 (D-2 + plan § 4 #3) 의도된 비대칭. 본 chunk 는 _합산 선호_ 가이드라인 변경 없음 | Phase H 또는 별도 ADR |
| Phase E `short_selling_kw` / `lending_balance_kw` 의 다른 inherit | 본 inherit 표 (§ 46.8) 외 항목은 별도 처리 | 별도 chunk |
| stock_fundamental (F-1 `IngestStockFundamentalUseCase.execute`) 의 sentinel catch 보강 | L-C 단건 UseCase 와 _같은 카테고리_ — 본 chunk 에 포함 권고 (사용자 결정 D-7 시 합류) | 본 chunk 또는 별도 |
| 운영 cron / .env / secret 회전 | § 38.8 #6/#7 — 전체 개발 완료 후 | — |
| 5-15 06:00 cron 자연 검증 | 시점 의존 — Phase F-4 검증 합류 | 5-15 자동 |

---

## 4. 확정 결정 (작성 시점 미확정 — § 9 ted-run input 직전 사용자 확정 필요)

| # | 결정 항목 | 옵션 | 사용자 확정 시점 |
|---|----------|------|------------------|
| **D-1** | `SkipReason` Enum 위치 | (a) `app/application/dto/_shared.py` 신규 (b) `app/application/dto/short_selling.py` 안 + lending 에서 import (c) `app/application/_shared/skip_reason.py` 신규 모듈 | F-3 ted-run 입력 직전 |
| **D-2** | `SkipReason` 값 표현 | (a) StrEnum (`SkipReason.ALPHANUMERIC_PRE_FILTER = "alphanumeric_pre_filter"`) — 직렬화 시 string 유지 (b) Enum + `.value` 변환 (DTO 의 `outcome.error: str` 필드 그대로) | F-3 ted-run 입력 직전 |
| **D-3** | `errors_above_threshold` 통일 방향 | **(a) tuple[str, ...] 로 통일** (lending 패턴 — 정보량 더 많음) (b) bool 로 통일 (short 패턴 — 단순) | F-3 ted-run 입력 직전 |
| **D-4** | 임계치 메시지 통일 위치 | bulk_result DTO 의 `warnings: tuple[str,...]` + `errors_above_threshold: tuple[str,...]` 둘 다 보존 / scheduler 가 둘 다 알람 | F-3 ted-run 입력 직전 |
| **D-5** | empty stocks 조기 반환 helper | (a) `_empty_bulk_result(pre_filter_skipped: int) -> ...` private helper (b) inline 유지 + 주석으로 동등성 명시 | F-3 ted-run 입력 직전 |
| **D-6** | H-R2-1 label rename vs DTO field rename | (a) `scripts/backfill_short.py:189` label `total_skipped:` 로 변경 (DTO 와 매칭) — short 만 (b) DTO field rename — short DTO 의 `total_skipped` → `total_alphanumeric_skipped` (ADR § 46.9 비대칭 해소 동반 — _큰 변경_) | F-3 ted-run 입력 직전 |
| **D-7** | L-C 단건 UseCase catch 정책 | (a) `SentinelStockCodeError` catch + outcome.error=`SkipReason.SENTINEL_SKIP` (단건 outcome 에 error field 가 있으면) (b) catch 안 함 + 라우터 정규식만 의존 (현행) (c) catch + re-raise as `ValueError` (FastAPI 400) | F-3 ted-run 입력 직전 |
| **D-8** | L-B `skipped_count` property | (a) DTO 에 `@property def skipped_count(self) -> int: return self.total_skipped + ...` 도입 (b) 보류 (테스트 가독성 minor) | F-3 ted-run 입력 직전 |

> **D-1~D-8 권고 default** (사용자 별도 입력 없으면):
> - D-1: (a) `app/application/dto/_shared.py` 신규 — DTO layer 의 공유 enum 위치
> - D-2: (a) StrEnum — `outcome.error: str` 그대로 비교 가능 (`outcome.error == SkipReason.SENTINEL_SKIP`)
> - D-3: (a) tuple[str, ...] 로 통일 — 정보량 손실 없음 + lending 이 이미 그 형태
> - D-4: 보존 + cron 둘 다 알람
> - D-5: (a) helper 추출 — 4번째 빈 반환이 발생하면 helper 도입 break-even (Phase F-4 5 endpoint 의 bulk 가 5 곳 더 늘어남)
> - D-6: (a) label 변경 (단순)
> - D-7: (a) catch + outcome.error 분리 — defense-in-depth. 라우터 우회 호출 시에도 일관 (Phase F-4 router 도 동일 패턴 적용 가능)
> - D-8: (a) property 도입 — `skipped_count` 단일 진실값

---

## 5. 변경 면 매핑 (D-1~D-8 권고 default 가정)

### 5.1 DTO (3 파일 — 신규 1 / 갱신 2)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/application/dto/_shared.py` (신규) | `class SkipReason(StrEnum): ALPHANUMERIC_PRE_FILTER = "alphanumeric_pre_filter" / SENTINEL_SKIP = "sentinel_skip"` |
| 2 | `app/application/dto/short_selling.py` | `errors_above_threshold: bool` → `tuple[str, ...]` (M-R2-1). `skipped_count` property 추가 (D-8). docstring 의 매직 스트링 → `SkipReason.*.value` 또는 enum reference |
| 3 | `app/application/dto/lending.py` | `skipped_count` property 추가 (D-8). docstring 매직 스트링 → enum reference |

### 5.2 Service (2 파일)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/application/service/short_selling_service.py` | (a) 라인 258/309/362 매직 스트링 → `SkipReason.ALPHANUMERIC_PRE_FILTER.value` / `SkipReason.SENTINEL_SKIP.value`. (b) empty stocks 반환 helper `_empty_bulk_result` 추출 (D-5). (c) `errors_above_threshold` bool → tuple[str, ...] (M-R2-1). (d) 단건 UseCase `IngestShortSellingForStockUseCase.execute` 에 sentinel catch 추가 (D-7) |
| 2 | `app/application/service/lending_service.py` | (a) 라인 296/340 매직 스트링 → enum. (b) empty stocks 반환 helper (D-5). (c) 단건 UseCase `IngestLendingStockUseCase.execute` 에 sentinel catch 추가 (D-7) |

### 5.3 Router / Batch (4 파일)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/adapter/web/routers/short_selling.py:88` | DTO output `errors_above_threshold: bool` → `tuple[str, ...]` |
| 2 | `app/adapter/web/routers/lending.py` | 변경 0 (이미 tuple[str, ...]) — docstring 검증만 |
| 3 | `app/batch/short_selling_job.py:59` | `if result.errors_above_threshold:` (bool) → `if result.errors_above_threshold:` (tuple — truthy check 가능) + logger 에 `list(result.errors_above_threshold)` 전달 (lending 패턴) |
| 4 | `app/batch/lending_stock_job.py` | 변경 0 (이미 tuple 패턴) |

### 5.4 Script (1 파일)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `scripts/backfill_short.py:189` | label `f"alphanumeric_skipped:{result.total_skipped}"` → `f"total_skipped:{result.total_skipped}"` (D-6 = a) |

### 5.5 테스트 갱신 / 신규 (~5 파일 + 1 신규)

| # | 파일 | 변경 |
|---|------|------|
| 1 | `tests/test_short_selling_service.py` | `errors_above_threshold` bool 단언 → tuple 단언. helper 회귀 |
| 2 | `tests/test_lending_service.py` | 변경 0 또는 helper 회귀만 |
| 3 | `tests/test_short_selling_service_sentinel.py:207, 273` | 매직 스트링 직접 비교 → `SkipReason.SENTINEL_SKIP.value` 비교 (또는 enum 객체) |
| 4 | `tests/test_lending_service_alphanumeric_skipped.py:201, 261` | 동일 |
| 5 | `tests/test_skip_reason.py` (신규) | `SkipReason` enum 값 안정성 회귀 (string 값 변경 시 외부 시스템 영향 — KOSCOM 대조 / log 분석) |
| 6 | `tests/test_short_selling_use_case_sentinel.py` (신규) | 단건 UseCase 에 sentinel catch 추가 회귀 (D-7) |
| 7 | `tests/test_lending_use_case_sentinel.py` (신규) | 동일 |
| 8 | `tests/test_backfill_short_summary.py` (신규 또는 갱신) | label `total_skipped:` 변경 회귀 |

추정 변경 라인:
- DTO 3 파일: ~30줄 (enum 신설 ~15 + property ~10 + tuple 변환 ~5)
- Service 2 파일: ~60줄 (helper ~20 + enum 치환 ~10 + 단건 catch ~30)
- Router/Batch 4 파일: ~10줄
- Script 1 파일: ~1줄
- 테스트 ~8 파일: ~150-200줄

⇒ 총 ~250-300줄 (F-2 의 ~60% 규모)

---

## 6. 적대적 self-check (보안 / 동시성 / 데이터 정합)

### 6.1 보안

- `SkipReason` Enum 도입 — DTO `outcome.error: str` 필드는 그대로 (StrEnum 의 `.value` 또는 string 그대로). 외부 API 응답 / log 출력 값 변동 0 ⇒ ✅
- 단건 UseCase sentinel catch 추가 (D-7) — 기존 라우터 정규식 우회 호출 시 500 error 가 outcome.error 로 변환됨. error response 가 _덜 정보 노출_ ⇒ ✅
- helper `_empty_bulk_result` private — module-private (`_` prefix) ⇒ ✅

### 6.2 동시성 / 운영

- 코드 경로 변경 0 (enum 치환 + helper 추출 + 단건 catch 만). 성능 영향 ~0 ⇒ ✅
- `errors_above_threshold` tuple 통일 — short scheduler cron (`short_selling_job.py:59`) 의 bool 분기가 truthy/falsy 그대로 동작 (빈 tuple = False). 운영 알람 동등성 유지 ⇒ ✅
- single UseCase catch 추가 → 기존 라우터 정규식 우회 호출 (admin tool / curl 직접) 시 500 → 400-like outcome. _덜 fail-loud_ 라 운영 알람 sensitivity 변경 가능 — outcome.error 모니터링 필수
- 단건 UseCase 의 caller (`IngestShortSellingBulkUseCase.execute` loop) 가 _이미_ sentinel catch 를 진행함. 단건 catch 추가는 _중복_ 이라 영향 0 (이미 caller 가 잡으면 단건 UseCase 도달 안 함) — defense-in-depth 의 의미

### 6.3 데이터 정합

- DB 데이터 변경 0 (코드 경로 동일)
- `errors_above_threshold` 의미 변경 (bool → tuple). DTO consumer 모두 _truthy_ 만 본다면 영향 0. 만약 `is True` 체크 사이트 있으면 깨짐 — § 5.3 의 `short_selling_job.py:59` 가 유일 (truthy 체크) ⇒ ✅
- `SkipReason.value` = 기존 매직 스트링 그대로 (`"alphanumeric_pre_filter"` / `"sentinel_skip"`). log 분석 / KOSCOM 대조 영향 0 ⇒ ✅

### 6.4 ADR § 46.9 네이밍 비대칭 (의도된 보존)

본 chunk 는 `short.total_skipped` vs `lending.total_alphanumeric_skipped` 의 _합산 / 분리_ 비대칭을 통일하지 _않는다_. 사용자 확정 (D-2) 이라 D-6 = (a) label 변경 만으로 H-R2-1 해소. 통일 rename 은 별도 ADR 후속.

### 6.5 D-8 `skipped_count` property 우회 위험

`@property def skipped_count(self) -> int: return self.total_skipped` (short) 와 `return self.total_alphanumeric_skipped` (lending) — 같은 의미를 보존하지만 _구현 다름_. 호출처가 `result.skipped_count` 를 쓰면 양쪽 동일. 단, 호출처 일관성 확보 후 D-2 rename 시점에서 property 도 동시 갱신 필요.

### 6.6 단건 UseCase L-C catch — 정책 다양성

`IngestShortSellingForStockUseCase.execute(stock_code: str)` 가 단건 호출. catch 정책 옵션:
- (a) catch + outcome.error 분리 (권고)
- (b) catch + raise `ValueError` (FastAPI 400) — 라우터 친화
- (c) catch 안 함 — 현행 (라우터 정규식만 의존)

(a) 권고 — Phase F-4 ranking endpoint 의 단건 호출에도 동일 패턴 적용 가능 (일관성).

---

## 7. DoD (Definition of Done)

### 7.1 코드 (~10 파일)

- [ ] `app/application/dto/_shared.py` — `SkipReason` StrEnum (값 2종)
- [ ] `app/application/dto/short_selling.py` — `errors_above_threshold` bool → tuple, `skipped_count` property
- [ ] `app/application/dto/lending.py` — `skipped_count` property
- [ ] `app/application/service/short_selling_service.py` — enum 치환 + helper + 단건 catch + tuple 변환
- [ ] `app/application/service/lending_service.py` — enum 치환 + helper + 단건 catch
- [ ] `app/adapter/web/routers/short_selling.py` — `errors_above_threshold: tuple[str, ...]` DTO output
- [ ] `app/batch/short_selling_job.py` — logger tuple 분기 (lending 패턴 복제)
- [ ] `scripts/backfill_short.py:189` — label `total_skipped:` 로 통일

### 7.2 테스트

- [ ] 매직 스트링 enum 치환 회귀 (4 사이트 / 2 파일)
- [ ] `errors_above_threshold` tuple 회귀 (short_selling)
- [ ] 단건 UseCase sentinel catch 회귀 (신규 2 파일)
- [ ] `SkipReason` enum 값 안정성 회귀 (신규 1 파일)
- [ ] 1267 baseline 유지 → ~1280-1290 (신규 ~15-25 케이스)
- [ ] coverage 86.43% baseline 유지 또는 ↑

### 7.3 운영 검증

- [ ] 본 chunk 코드 변경 0 cron 영향 (회귀 테스트 결과로 갈음)
- [ ] H-R2-1 backfill_short label 변경 — 5-13 alphanumeric_skipped log 모니터링 도구 (있다면) 업데이트 필요 알림

### 7.4 문서

- [ ] CHANGELOG: `refactor(kiwoom): Phase F-3 — R2 inherit 7건 정리 (SkipReason Enum / errors_above_threshold 타입 통일 / empty helper / 단건 sentinel catch)`
- [ ] ADR § 47 신규 — R2 inherit 7건 해소 + 잔여 (네이밍 비대칭 § 46.9) 보존 명시
- [ ] STATUS.md § 4 #32 (R2 inherit 7건) 해소 마크
- [ ] HANDOFF.md rewrite

---

## 8. 다음 chunk

| 후보 | 시점 | 비고 |
|------|------|------|
| **Phase F-4 (5 endpoint 통합)** | F-3 완료 직후 | 정리된 패턴 위에서 작업 가능. plan doc = `phase-f-4-rankings.md` (별도) |
| 5-15 06:00 자연 cron 검증 | 5-15 자동 | F-3 코드 변경 후 cron 영향 모니터 (회귀 영향 0 기대) |
| ADR § 46.9 네이밍 비대칭 통일 rename | Phase H 또는 별도 ADR | 사용자 확정 결정 (의도된 보존) — _합산 선호_ 가이드라인 적용 시점 |

---

## 9. ted-run 풀 파이프라인 input

```yaml
chunk: Phase F-3
title: R2 inherit 7건 정리 (SkipReason Enum + errors_above_threshold 타입 통일 + empty helper + 단건 sentinel catch)
선행: Phase F-2 (8f6b453)
plan_doc: src/backend_kiwoom/docs/plans/phase-f-3-r2-inherit-cleanup.md
출처: ADR § 46.8 (R2 inherit 7건)

input:
  결정_사용자_확정_8건:
    D-1: app/application/dto/_shared.py (신규 모듈)
    D-2: StrEnum (`outcome.error` 그대로 string 호환)
    D-3: errors_above_threshold tuple[str, ...] 통일 (short = lending)
    D-4: warnings + errors_above_threshold 둘 다 보존 + cron 알람
    D-5: _empty_bulk_result helper 추출 (short + lending)
    D-6: scripts/backfill_short.py:189 label `total_skipped:` 로 통일 (DTO field rename 아님)
    D-7: 단건 UseCase (Short + Lending) 에 SentinelStockCodeError catch 추가 — outcome.error = SkipReason.SENTINEL_SKIP
    D-8: DTO 양쪽에 `skipped_count` @property 추가 — 단일 진실값
  변경면:
    DTO: 3 파일 (_shared 신규 / short / lending)
    Service: 2 파일 (enum + helper + 단건 catch + tuple 변환)
    Router/Batch: 4 파일 (short router + short scheduler 만 변경)
    Script: 1 파일 (backfill_short label)
    Test: 5 갱신 + 3 신규 = 8 파일

verification:
  - ruff clean
  - mypy --strict 105 files Success
  - pytest 전체 PASS — 1267 → ~1280-1290
  - coverage ≥ 86.43% baseline
  - 매직 스트링 grep 0 결과 (test 제외 production 코드)
  - errors_above_threshold bool 단언 grep 0 결과

scope_out:
  - ranking endpoint (Phase F-4)
  - ADR § 46.9 네이밍 비대칭 통일 rename (Phase H)
  - Phase E 다른 inherit
  - stock_fundamental 단건 sentinel catch (D-7 합류 시 옵션)
```

> 본 chunk 는 _리팩토링_ — 외부 동작 변경 0. 회귀 테스트가 가장 중요.

---

_Phase F (순위 5종) 진입 전 사전 정리. Phase F-2 R2 inherit 7건 (ADR § 46.8) 해소 + Phase F-4 에서 ranking endpoint 들이 정리된 패턴 (SkipReason Enum / tuple errors_above_threshold / empty helper / 단건 catch) 위에서 작업 가능._
