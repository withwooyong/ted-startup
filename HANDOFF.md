# Session Handoff

> Last updated: 2026-05-09 13:30 (KST)
> Branch: `master`
> Latest commit (커밋 대기): `refactor(kiwoom): Phase C R1 — 3 도메인 일관 개선`
> 직전 푸시: `f8cece0` — Phase C-2γ Migration 008

## Current Status

**Phase C R1 (Refactor 1) 완료** — ADR-0001 § 19.5 (C-2β Defer 5건) + B-γ-2 동일 패턴을 3 도메인 (fundamental / OHLCV / daily_flow) 횡단 일관 정리. 외부 API contract 무변, 내부 타입·예외 안전성 강화. ted-run 풀 파이프라인 1회 통과, **816 → 822 cases / 92.86% coverage**. 다음 chunk (C-3 / Phase D) 진입 전 베이스 정착 완료.

## Completed This Session (커밋 대기)

| # | Task | 산출물 | Notes |
|---|------|--------|-------|
| 1 | 신규 공유 예외 모듈 | `app/application/exceptions.py` + `tests/test_application_exceptions.py` (+6 cases) | StockMasterNotFoundError(ValueError) + __slots__ + 안정 메시지 + except 순서 역방향 회귀 |
| 2 | 3 service errors → tuple + StockMasterNotFoundError | `ohlcv_daily_service.py` / `daily_flow_service.py` / `stock_fundamental_service.py` | frozen dataclass 일관 + build-then-freeze 패턴 |
| 3 | 3 service refresh_one NXT Exception 격리 | OHLCV / daily_flow 만 (fundamental KRX-only) | `except Exception` + R1 L-5 의도 주석 |
| 4 | 3 router DTO tuple + max_length=2 + fetched_at non-Optional | `ohlcv.py` / `daily_flow.py` / `fundamentals.py` | 응답 wire format 무변 (Pydantic v2 tuple → JSON array) |
| 5 | 3 router except StockMasterNotFoundError 분기 | subclass first 순서 (ValueError 분기 위) | 메시지 검색 (`if "stock master not found" in msg:`) 제거 |
| 6 | 6 테스트 갱신 + 7개소 `errors=()` | service 3 + router 3 + fixture 1 | mypy strict + tuple 필드 일치 (R1 1R M-1) |
| 7 | 1차 코드 리뷰 (sonnet) | python-reviewer | MEDIUM 1 + LOW 4 → 전건 적용 → PASS |
| 8 | Verification 5관문 | mypy / ruff / pytest+coverage | 66 files 0 errors / All passed / 822 cases / 92.86% |
| 9 | ADR-0001 § 22 추가 | `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` | 핵심 결정 7건 + 1R 결과 + § 19.5 / § 17.4 Defer 해소 매핑 (5/5 ✅) |
| 10 | STATUS.md 갱신 (CLAUDE.md 자동 규칙) | `src/backend_kiwoom/STATUS.md` | Phase C 70→75%, chunk 19 누적, 알려진 이슈 1건 해소 |
| 11 | plan doc | `docs/plans/phase-c-refactor-r1-error-handling.md` (신규) | 영향 범위 / 사전 self-check H-1~H-7 / DoD |
| 12 | CHANGELOG prepend | `CHANGELOG.md` | R1 항목 |
| 13 | HANDOFF 갱신 | `HANDOFF.md` | 본 파일 |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | 본 세션 산출물 커밋 + 푸시 | pending | 사용자 승인 후 — 한 commit |
| 2 | C-3 (ka10082/83 주봉/월봉, P1) | not started | chart endpoint 재사용 + R1 정리된 패턴 그대로 복제 |
| 3 | scripts/backfill_*.py CLI + 3년 백필 실측 | pending | C-1β/C-2β 통합 |
| 4 | KOSCOM 공시 수동 cross-check (1~2건) | pending | 가설 B 최종 확정 |
| 5 | indc_tp=1 (금액 모드) 단위 mismatch 검증 | pending | 향후 운영 검증 |
| 6 | ka10094 (년봉, P2) | pending | C-3 와 동일 패턴 |

## Key Decisions Made (R1)

### 핵심 설계 (ADR § 22.2)

- **공유 예외 모듈** — `app/application/exceptions.py` 신규. 3 service 가 공유하는 예외만 본 모듈. domain-specific 예외는 service inline 패턴 유지 (token_service 일관)
- **`StockMasterNotFoundError(ValueError)`** + `__slots__ = ("stock_code",)` — backward compat (subclass) + 안정 메시지 형식 + 속성 mutation 방어
- **errors mutable container 노출 제거** — 3 service Result frozen dataclass field type 을 `list → tuple`. 내부 build local list → return 시 `tuple(errors)` (B-γ-1 frozen 강화)
- **router DTO `tuple[..., ...]`** — Pydantic v2 가 tuple 도 JSON array 직렬화. wire format 무변 + OpenAPI schema 동일
- **subclass first except 순서** — `except StockMasterNotFoundError` 가 `except ValueError` 보다 먼저. 메시지 substring 검색 (`if "stock master not found" in msg:`) 제거. 역방향 invariant 단위 회귀 추가
- **NXT path Exception 격리 (L-5)** — OHLCV / daily_flow `refresh_one` 에 `except Exception` 추가. partial-failure 모델 의도 주석. KRX 적재 후 NXT unexpected exception 도 응답 200 + failed=1 로 격리 (전체 500 대신)
- **`only_market_codes max_length=2`** — pattern={1,2} 와 일치. dead validator 정리, 운영 호출 영향 0
- **`fetched_at` non-Optional** — 3 RowOut DTO 모두 ORM NOT NULL + server_default 일관 명시. fixture 1 갱신 (`fetched_at=datetime(...)`)

### 1차 리뷰 결과 (M-1 + L-1~L-4 전건 적용)

- **M-1**: 7개소 `errors=[]` (list) → `errors=()` (mypy strict + tuple 필드 일치)
- **L-1**: `__slots__ = ("stock_code",)` + docstring "읽기 전용 권고"
- **L-2**: `test_value_error_first_except_swallows_subclass` — 역방향 invariant 단위 증명
- **L-3**: `fundamentals.py:325` exchange max_length=4 주석 (only_market_codes 와 다른 파라미터)
- **L-4**: `refresh_fundamental` 의 `except ValueError` 분기 의도적 생략 명시 (base_date 파라미터 없음)

### Defer 해소 매핑 (ADR § 22.5 — 5/5 ✅)

- § 19.5 M-1 (errors mutable list) ✅
- § 19.5 M-2 (ValueError 메시지 검색) ✅
- § 19.5 L-1 (only_market_codes max_length=4 dead) ✅
- § 19.5 L-2 (DailyFlowRowOut.fetched_at None 타입) ✅
- § 19.5 L-5 (refresh_one NXT 비-Kiwoom Exception) ✅

## Known Issues

### R1 후 잔여

- **C-2α 상속**: NUMERIC magnitude 가드 부재 / idx_daily_flow_exchange cardinality (C-backfill chunk)
- **C-1α 상속**: NUMERIC magnitude / list cap / MappingProxyType / chart.py private import (운영 dry-run 후 / 후속 chunk)
- **운영 검증 미해결**: KOSCOM cross-check / indc_tp=1 단위 mismatch / OHLCV cross-check (Phase H) / 페이지네이션 빈도 / 3년 백필 시간 / active 3000 + NXT 1500 sync 실측

## Context for Next Session

### 사용자의 원래 의도 / 목표

backend_kiwoom Phase C 의 모든 잔여 일관성 이슈를 다음 신규 도메인 (C-3 주봉/월봉) 진입 전 정리. 3 도메인이 같은 패턴을 공유하므로 한 chunk 로 일괄 정리 (B-γ-2 / C-1β / C-2β 모두 같은 mutable list / message-search 패턴).

### 선택된 접근 + 이유

- **ted-run 풀 파이프라인 + 자동 분류 = 계약 변경 fallback** — plan doc 의 self-classification "refactor" 보다 보수적. 응답 DTO `fetched_at: datetime | None → datetime` (OpenAPI Optional 변경) + max_length=4→2 (validator 변경) 이 schema 변경에 해당
- **`StockMasterNotFoundError(ValueError)`** — backward compat 우선. `except ValueError` 가 여전히 캐치하므로 점진적 마이그레이션. router 에서만 subclass first 분기 추가
- **CLAUDE.md 자동 갱신 규칙 두 번째 적용** — STATUS.md 가 본 chunk 와 함께 동시 갱신 (3 문서 동시 갱신 정책)
- **Quality-First** — refactor 분류라 게이트 적게 갈 수도 있었으나, ted-run 자동 분류가 contract 로 fallback 해 TDD + 1R + 5관문 모두 실행. 운영 미가동 시점에 잔여 일관성 정리

### 사용자 제약 / 선호

- 한글 커밋 메시지 (~/.claude/CLAUDE.md 글로벌 규칙)
- 푸시는 명시적 요청 시만 (커밋과 분리)
- 큰 Phase 는 chunk 분할 후 ted-run 풀 파이프라인 (메모리)
- 진행 상황 가시화 — 체크리스트 + 한 줄 현황
- backend_kiwoom CLAUDE.md — STATUS.md / HANDOFF.md / CHANGELOG.md 3 문서 동시 갱신 (chunk 커밋과 동일 commit)

### 다음 세션 진입 시 결정 필요

사용자에게 옵션 확인 권장:

1. **C-3 (ka10082/83 주봉/월봉, P1)** (권고 1순위) — chart endpoint 재사용. R1 정리된 패턴 그대로 복제. 신규 도메인 2 + Migration 1 + ted-run 풀 파이프라인 적합
2. **scripts/backfill_*.py CLI + 3년 백필 실측** — Phase C-2 마무리. 운영 시간 측정 / 페이지네이션 빈도 정량화 / cron 시간 조정
3. **KOSCOM cross-check 수동** — 가설 B 최종 확정 (스크립트 외 1~2건 비교)
4. **ka10094 (년봉, P2)** — C-3 직후 자연스러운 후속

## Files Modified This Session (커밋 대기)

```
src/backend_kiwoom/app/application/exceptions.py                            (신규)
src/backend_kiwoom/tests/test_application_exceptions.py                     (신규, +6 cases)
src/backend_kiwoom/app/application/service/ohlcv_daily_service.py           (errors→tuple + raise + NXT Exception)
src/backend_kiwoom/app/application/service/daily_flow_service.py            (동일 3 변경)
src/backend_kiwoom/app/application/service/stock_fundamental_service.py     (errors→tuple + raise)
src/backend_kiwoom/app/adapter/web/routers/ohlcv.py                         (DTO tuple + max_length=2 + fetched_at + except 분기)
src/backend_kiwoom/app/adapter/web/routers/daily_flow.py                    (동일 4 변경)
src/backend_kiwoom/app/adapter/web/routers/fundamentals.py                  (동일 4 변경 + L-3/L-4 주석)
src/backend_kiwoom/tests/test_ingest_daily_ohlcv_service.py                 (raises StockMasterNotFoundError)
src/backend_kiwoom/tests/test_ingest_daily_flow_service.py                  (동일)
src/backend_kiwoom/tests/test_stock_fundamental_service.py                  (동일)
src/backend_kiwoom/tests/test_ohlcv_router.py                               (mock + errors=())
src/backend_kiwoom/tests/test_daily_flow_router.py                          (mock + errors=())
src/backend_kiwoom/tests/test_fundamental_router.py                         (mock + errors=() + fetched_at fixture)
src/backend_kiwoom/STATUS.md                                                (Phase C 70→75%, chunk 19)
src/backend_kiwoom/docs/plans/phase-c-refactor-r1-error-handling.md         (신규)
docs/ADR/ADR-0001-backend-kiwoom-foundation.md                              (§ 22 추가)
CHANGELOG.md                                                                 (prepend)
HANDOFF.md                                                                   (전체 갱신)
```

19 files changed (신규 4 + 수정 15).
