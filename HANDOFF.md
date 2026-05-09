# Session Handoff

> Last updated: 2026-05-09 (KST) — Phase C-3α
> Branch: `master`
> Latest commit (커밋 대기): `feat(kiwoom): Phase C-3α — 주/월봉 OHLCV 인프라`
> 직전 푸시: `c3e0952` — Phase C R1

## Current Status

**Phase C-3α (주/월봉 OHLCV 인프라) 완료** — ka10082 (주봉) + ka10083 (월봉) 의 인프라 레이어 일괄 도입. ka10081 (일봉) 패턴 ~95% 복제 + R1 정착 패턴 사전 적용. ted-run 풀 파이프라인 1회 통과, **822 → 897 cases / 92.86% → 97% coverage**. 자동화 (UseCase + Router + Scheduler) 는 다음 chunk **C-3β**.

## Completed This Session (커밋 대기)

| # | Task | 산출물 | Notes |
|---|------|--------|-------|
| 1 | plan doc 신규 (chunk 단위) | `docs/plans/phase-c-3-weekly-monthly-ohlcv.md` (신규, 340줄) | 영향 범위 / self-check H-1~H-7 / DoD α/β 분리 / 다음 chunk 후보 |
| 2 | Period(StrEnum) 추가 | `app/application/constants.py` | WEEKLY/MONTHLY/YEARLY 3값. DAILY 제외 (H-3) |
| 3 | 4 ORM 모델 (Mixin 재사용) | `app/adapter/out/persistence/models/stock_price_periodic.py` (신규) | `_DailyOhlcvMixin` 재사용 (H-2). Weekly KRX/NXT + Monthly KRX/NXT |
| 4 | models/__init__.py re-export | `app/adapter/out/persistence/models/__init__.py` | 4 신규 모델 추가 |
| 5 | Migration 009-012 (4 테이블) | `migrations/versions/009-012_*.py` (신규 4) | 005/006 패턴 복제. UNIQUE + FK CASCADE + 인덱스 2 each. revision id 32자 한도 (kiwoom_ prefix 제거) |
| 6 | StockPricePeriodicRepository | `app/adapter/out/persistence/repositories/stock_price_periodic.py` (신규) | period+exchange dispatch (4 매핑). upsert_many + find_range. NormalizedDailyOhlcv 재사용 |
| 7 | KiwoomChartClient.fetch_weekly + fetch_monthly | `app/adapter/out/kiwoom/chart.py` (확장) | fetch_daily 패턴 복제. list 키 분기 + 클래스 상수. fetch_daily 변경 0줄 (H-6) |
| 8 | Pydantic 4 (Weekly/MonthlyChartRow + Response) | `app/adapter/out/kiwoom/chart.py` | DailyChartRow 상속 (`pass`) |
| 9 | 4 신규 테스트 + 1 수정 | tests (5 파일, +75 cases) | period_enum 8 / chart_periodic 23 / repository 18 / migration 26 / migration_008 head 동적 단언 |
| 10 | 1차 코드 리뷰 (sonnet) | python-reviewer | CRITICAL/HIGH 0 / MEDIUM 3 / LOW 3 → M-1 + L-1 + L-2 적용. M-2 ruff format 자동 / M-3 + L-3 별도 chunk |
| 11 | Verification 5관문 | mypy / ruff / pytest+coverage / testcontainers | 68 files 0 errors / All passed / 897 cases / 97% / Migration up→down(008)→up cycle PASS |
| 12 | ADR-0001 § 23 추가 | `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` | 핵심 결정 7건 + 1R 결과 + 결과 + 운영 검증 미해결 + Defer + 다음 chunk |
| 13 | STATUS.md 갱신 | `src/backend_kiwoom/STATUS.md` | Phase C 75→80%, chunk 20 누적, ka10082/83 인프라 완료, § 6 Phase C 진행 7 chunks |
| 14 | CHANGELOG prepend | `CHANGELOG.md` | C-3α 항목 |
| 15 | HANDOFF 갱신 | `HANDOFF.md` | 본 파일 |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | 본 세션 산출물 커밋 | pending | 사용자 승인 후 — 한 commit |
| 2 | 푸시 | pending | 별도 사용자 승인 (글로벌 CLAUDE.md 규칙) |
| 3 | **C-3β (자동화)** | not started | UseCase period dispatch + Router 4 path + Scheduler 2 job. R1 패턴 5종 전면 적용 (다음 chunk) |
| 4 | scripts/backfill_*.py CLI + 3년 백필 실측 | pending | C-1β/C-2β/C-3β 통합 |
| 5 | KOSCOM 공시 수동 cross-check (1~2건) | pending | 가설 B 최종 확정 |
| 6 | ka10094 (년봉, P2) | pending | C-3 와 동일 패턴 (Migration 1 + UseCase YEARLY 분기 활성화) |

## Key Decisions Made (C-3α)

### 핵심 설계 (ADR § 23.2)

- **Migration 분리 (4건)** — 009/010/011/012 직선 체인. C-1α 패턴 일관 + 운영 시 거래소 토글 가능. testcontainers up→down→up 사이클 검증
- **`_DailyOhlcvMixin` 재사용** — period 별 의미 차이는 영속화 테이블 이름으로 식별. private import 정당화 (H-2). `prev_compare_*` 의 일/주/월 다른 의미는 컬럼 COMMENT 명시
- **`Period(StrEnum)` 3값** — WEEKLY/MONTHLY/YEARLY. DAILY 는 hot path 분리 (IngestDailyOhlcvUseCase). YEARLY 는 enum 노출하되 미구현 (P2 chunk 진입 시 활성화)
- **`StockPricePeriodicRepository` 분리** — 일봉 vs 주/월봉 호출 빈도 + row 수 차이 → 별도 hot path. NormalizedDailyOhlcv 는 컬럼 구조 period 무관이라 재사용 (Daily 접두는 도메인 출처 표시)
- **`fetch_weekly`/`fetch_monthly` 별도 메서드** — fetch_daily 와 ~80% 중복이지만 list 키 + api_id 분기 명시성 우선. helper 추출은 ka10094 후 R2 검토. fetch_daily 변경 0줄 (H-6)
- **revision id 32자 한도** — Alembic `version_num VARCHAR(32)` 한도. 신규는 `kiwoom_` prefix 제거 (009_stock_price_weekly_krx 등). 005/006 패턴과 약간 차이 있지만 길이 우선
- **R1 정착 패턴 사전 적용 (인프라 레이어)** — `fetched_at` non-Optional ORM. 다른 R1 패턴 (errors tuple / StockMasterNotFoundError / max_length=2 / NXT Exception 격리) 은 C-3β UseCase/Router 적용

### 1차 리뷰 결과 (M-1 + L-1 + L-2 적용)

- **M-1**: Repository docstring — NormalizedDailyOhlcv 의 Daily 접두 의도 명시
- **L-1**: NXT Migration 010/012 의 trading_date / prev_compare_* COMMENT 추가 (KRX/NXT 대칭성)
- **L-2**: update_set 위 주석 — ON CONFLICT key 컬럼 의도적 제외 + silent contract change 차단

## Known Issues

### C-3α 후 잔여

- **C-3β 미진입**: UseCase + Router + Scheduler 미작성. R1 패턴 5종 적용 대상
- **운영 검증 미해결**:
  - `dt` 의미 가설 (주 시작/종료, 달 첫일/말일) — 운영 first-call 후 1주 모니터로 확정
  - 응답 list 키 (`stk_stk_pole_chart_qry` / `stk_mth_pole_chart_qry`) Excel R31 표기 vs 실제 응답 일치 검증
  - 일봉 합성 vs 키움 주/월봉 cross-check — Phase H
  - 백필 페이지네이션 빈도 (C-backfill chunk)
- **C-1α 상속**: NUMERIC magnitude / list cap / MappingProxyType / chart.py private import (운영 dry-run 후)
- **M-3 (`# type: ignore` → `cast()`)**: 기존 일봉 Repository 패턴과 함께 별도 refactor chunk

## Context for Next Session

### 사용자의 원래 의도 / 목표

backend_kiwoom Phase C 의 신규 도메인 (주봉/월봉) 진입 — R1 정착 직후 동일 패턴 그대로 복제. ka10082/83 둘 다 같은 KiwoomChartClient + Mixin + Repository + UseCase 공유 → α (인프라) / β (자동화) 분할 원칙으로 1 chunk 안에 두 endpoint 인프라 일괄 도입.

### 선택된 접근 + 이유

- **chunk 분할 = α (인프라) + β (자동화)** — C-1α/β / C-2α/β/γ 의 정착된 패턴 일관. 단일 chunk 1,200~1,600줄 부담 회피. α 통과 후 β 의존성 명확
- **두 endpoint (ka10082/83) 동시 처리** — UseCase / Repository / Mixin / Adapter class 모두 공유. 분리 시 중복 작업
- **ted-run 풀 파이프라인** — TDD red → 구현 green → 1차 리뷰 → 5관문. 자동 분류 = 계약 변경 → 2b 적대적 / 3-4 보안 자동 생략 / 4 E2E 백엔드 전용 자동 생략
- **Quality-First** — testcontainers 4 마이그레이션 사이클 검증 / chart adapter 23 시나리오 / Repository 18 시나리오. 신규 코드 100% coverage

### 사용자 제약 / 선호

- 한글 커밋 메시지 (~/.claude/CLAUDE.md 글로벌 규칙)
- 푸시는 명시적 요청 시만 (커밋과 분리)
- 큰 Phase 는 chunk 분할 후 ted-run 풀 파이프라인 (메모리)
- 진행 상황 가시화 — 체크리스트 + 한 줄 현황
- backend_kiwoom CLAUDE.md — STATUS.md / HANDOFF.md / CHANGELOG.md 3 문서 동시 갱신 (chunk 커밋과 동일 commit)

### 다음 세션 진입 시 결정 필요

사용자에게 옵션 확인 권장:

1. **C-3β (ka10082/83 자동화, P1)** (권고 1순위) — IngestPeriodicOhlcvUseCase (period dispatch) + Router 4 path (단건/일괄 × weekly/monthly) + Scheduler (금 KST 19:00 / 매월 1일 03:00). R1 패턴 5종 전면 적용. ted-run 풀 파이프라인 적합
2. **scripts/backfill_*.py CLI + 3년 백필 실측** — C-1β/C-2β/C-3β 공용 chunk
3. **KOSCOM cross-check 수동** — 가설 B 최종 확정
4. **ka10094 (년봉, P2)** — C-3β 직후 자연스러운 후속

## Files Modified This Session (커밋 대기)

```
src/backend_kiwoom/app/application/constants.py                                 (Period 추가)
src/backend_kiwoom/app/adapter/out/kiwoom/chart.py                              (Pydantic 4 + fetch_weekly/monthly + 클래스 상수)
src/backend_kiwoom/app/adapter/out/persistence/models/__init__.py               (4 모델 re-export)
src/backend_kiwoom/app/adapter/out/persistence/models/stock_price_periodic.py   (신규)
src/backend_kiwoom/app/adapter/out/persistence/repositories/stock_price_periodic.py (신규)
src/backend_kiwoom/migrations/versions/009_stock_price_weekly_krx.py            (신규)
src/backend_kiwoom/migrations/versions/010_stock_price_weekly_nxt.py            (신규)
src/backend_kiwoom/migrations/versions/011_stock_price_monthly_krx.py           (신규)
src/backend_kiwoom/migrations/versions/012_stock_price_monthly_nxt.py           (신규)
src/backend_kiwoom/tests/test_period_enum.py                                    (신규, 8 cases)
src/backend_kiwoom/tests/test_kiwoom_chart_client_periodic.py                   (신규, 23 cases)
src/backend_kiwoom/tests/test_stock_price_periodic_repository.py                (신규, 18 cases)
src/backend_kiwoom/tests/test_migration_009_012.py                              (신규, 26 cases)
src/backend_kiwoom/tests/test_migration_008.py                                  (head 동적 단언 보정)
src/backend_kiwoom/STATUS.md                                                    (Phase C 75→80%, chunk 20)
src/backend_kiwoom/docs/plans/phase-c-3-weekly-monthly-ohlcv.md                 (신규)
docs/ADR/ADR-0001-backend-kiwoom-foundation.md                                  (§ 23 추가)
CHANGELOG.md                                                                    (prepend)
HANDOFF.md                                                                      (본 파일)
```

총 19 파일 / 신규 11 + 수정 8 / 추정 +2,000 줄
