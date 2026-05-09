# Session Handoff

> Last updated: 2026-05-09 11:30 (KST)
> Branch: `master`
> Latest commit (커밋 대기): `refactor(kiwoom): Phase C-2γ — Migration 008 (D-E 중복 컬럼 DROP)`
> 직전 푸시: `8b46a49` — C-2γ 진입 준비 (STATUS.md + CLAUDE.md + plan § 12)

## Current Status

**Phase C-2γ 완료** — Migration 008 으로 stock_daily_flow 의 D-E 중복 3 컬럼 (`individual_net_purchase` / `institutional_net_purchase` / `foreign_net_purchase`) 영구 DROP. 13 → 10 도메인 컬럼. ted-run 풀 파이프라인 (TDD → 구현 → 1차 리뷰 → Verification → ADR/문서) 1회 통과. **812 → 816 cases / 93.11% coverage**. dry-run § 20.2 #1 결정의 즉시 반영 — 운영 가동 전 정리로 향후 스토리지 ~23% 절감.

## Completed This Session (커밋 대기)

| # | Task | 산출물 | Notes |
|---|------|--------|-------|
| 1 | Migration 008 작성 | `migrations/versions/008_drop_daily_flow_dup_columns.py` | DROP IF EXISTS × 3 + DOWNGRADE 가드 (007 동일 패턴) + ADD COLUMN BIGINT × 3 NULL 복원 |
| 2 | 5 코드 파일 컬럼 정리 | ORM / Repository / `_records.py` / `daily_flow.py` 라우터 + 주석 (M-4) | `created_at intentionally excluded` / vendor raw 유지 정책 명시 |
| 3 | 4 테스트 갱신 + 1 신규 | `test_migration_008.py` (+4) / 007 BIGINT 9→6 / 3 fixture 정리 | 라운드트립 컬럼 카운트 + BIGINT 타입 단언 강화 / `dataclasses.fields()` 단언 |
| 4 | 1차 코드 리뷰 (sonnet) | python-reviewer | MEDIUM 4 + LOW 2 → 전건 적용 → PASS |
| 5 | Verification 5관문 | mypy / ruff / pytest+coverage | 65 files 0 errors / All passed / 816 cases / 93.11% |
| 6 | ADR-0001 § 21 추가 | `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` | 핵심 결정 7건 + 1R 결과 + Defer + 다음 chunk |
| 7 | STATUS.md 갱신 (CLAUDE.md 자동 규칙 첫 적용) | `src/backend_kiwoom/STATUS.md` | Phase C 60→70%, chunk 18 누적, 다음 후보 5건 재정렬 |
| 8 | plan doc § 12 정정 | `endpoint-10-ka10086.md` § 12.3 / § 12.5 H-4 / § 12.6 / § 12.8 신규 | test_migration_007 컬럼 정정 명시 + 운영 모니터 권고 |
| 9 | CHANGELOG prepend | `CHANGELOG.md` | C-2γ 항목 |
| 10 | HANDOFF 갱신 | `HANDOFF.md` | 본 파일 |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | 본 세션 산출물 커밋 + 푸시 | pending | 사용자 승인 후 — 한 commit 으로 묶어서 |
| 2 | C-1β/C-2β MEDIUM 일관 개선 (refactor chunk) | pending | errors → tuple / StockMasterNotFoundError 전용 예외. 두 chunk 동시 정리 |
| 3 | C-3 (ka10082/83 주봉/월봉, P1) | not started | chart endpoint 재사용. 새 도메인 2개 + Migration 1 |
| 4 | scripts/backfill_*.py CLI + 3년 백필 실측 | pending | C-1β/C-2β backfill 통합 |
| 5 | KOSCOM 공시 수동 cross-check (1~2건) | pending | 가설 B 최종 확정. 외부 데이터 비교 |
| 6 | indc_tp=1 (금액 모드) 단위 mismatch 검증 | pending | 향후 운영 검증 — for_netprps 가 indc_tp 무시 항상 수량인지 |

## Key Decisions Made (C-2γ)

### 핵심 설계 (ADR § 21.2)

- **DROP COLUMN IF EXISTS × 3** (UPGRADE) / 데이터 가드 + ADD COLUMN BIGINT × 3 (DOWNGRADE) — 007 동일 패턴
- **NULL 복원 의미 보존 불가** 명시 가드 (운영 데이터 1건이라도 있으면 RAISE EXCEPTION)
- **vendor raw 필드 유지** — `for_netprps` / `orgn_netprps` / `ind_netprps` 는 `DailyMarketRow` 에 그대로. `to_normalized` 단계에서만 무시. vendor schema 변경 silent 차단은 운영 모니터 (분기/반기 dry-run 재실행, plan § 12.8)
- **응답 DTO breaking 수용** — `DailyFlowRowOut` 13→10 필드. 운영 미가동 (downstream 0)
- **upsert `update_set` 의 `created_at` 제외** 의도 명시 — 최초 insert 시각 보존 (M-4)
- **test_migration_007** 컬럼 검증부 정정 — conftest 가 head 까지 적용하므로 008 적용 후 상태 (BIGINT 9→6) 가 정답. history 멱등성은 별도 라운드트립 테스트 (`test_migration_007_downgrade_then_upgrade_idempotent`) 가 보장

### 1차 리뷰 결과 (M-1~M-4 + L-1~L-2 전건 적용)

- **M-1**: downgrade 가드 테스트의 `finally` 에서 `alembic_version == "008_..."` 명시 단언 추가 (테스트 격리)
- **M-2**: 라운드트립 테스트에 컬럼 카운트 (21/18) + BIGINT 타입 단언 추가
- **M-3**: plan § 12.8 운영 모니터 권고 추가 (vendor schema 변경 silent 처리 차단)
- **M-4**: Repository `update_set` 의 `created_at` 제외 의도 주석 1줄
- **L-1**: `hasattr` → `dataclasses.fields()` 단언 (slots 환경 오타 방어)
- **L-2**: `test_migration_007.py` docstring "13 도메인" → "10 도메인 (008 DROP 후)"

## Known Issues

### dry-run 발견 사항 (C-2γ 후 부분 해소)

- **D-E 중복 3개 컬럼**: ✅ Migration 008 로 영구 DROP. 본 세션 해소
- **NXT 외인 컬럼 KRX 중복**: 정책 단순화 위해 현 상태 유지 (코드 변경 없음). § 20.3 #2 결정대로
- **가설 B KOSCOM 미검증**: 미해결 — KOSCOM 공시 1~2건 수동 cross-check 권고 (script 외 운영 검증)

### 이전 chunk 상속

- **C-1β/C-2β MEDIUM**: errors mutable list / ValueError 메시지 검색 (다음 일관 개선 chunk)
- **C-2α 상속**: NUMERIC magnitude 가드 부재 / idx_daily_flow_exchange cardinality
- **운영 검증 미해결**: indc_tp=1 단위 mismatch / OHLCV cross-check (Phase H) / 페이지네이션 빈도 / 3년 백필 시간 / active 3000 + NXT 1500 sync 실측

## Context for Next Session

### 사용자의 원래 의도 / 목표

backend_kiwoom Phase C (백테스팅 코어 데이터) 를 운영 가동 가능 상태로 가져가기. ka10086 (수급) 도메인은 본 chunk 로 마무리 (C-2α 인프라 / C-2β 자동화 / C-2γ 데이터 모델 정리 / dry-run 검증). 다음은 (a) 두 phase 의 MEDIUM 잔여 정리 또는 (b) C-3 (주봉/월봉) 신규 도메인.

### 선택된 접근 + 이유

- **ted-run 풀 파이프라인 1회 통과** — 작업계획서 § 12 input → TDD → 구현 → 1차 리뷰 → Verification → ADR/STATUS/HANDOFF/CHANGELOG → (커밋 대기). 자동 분류 = 계약 변경 → 2b 적대적 자동 생략. 1차 리뷰만으로 MEDIUM 4 + LOW 2 모두 잡혀 추가 라운드 불필요
- **CLAUDE.md 자동 갱신 규칙 첫 적용** — STATUS.md 가 본 chunk 와 함께 자동으로 동시 갱신됨 (3 문서 동시 갱신 정책)
- **Quality-First** — 운영 미가동 시점에 데이터 모델 breaking change 정리. 백필 전이라 비용 0. dry-run 1,200 row 분석을 코드 결정의 단일 근거로 사용 (가설 → 검증 → 적용)

### 사용자 제약 / 선호

- 한글 커밋 메시지 (~/.claude/CLAUDE.md 글로벌 규칙)
- 푸시는 명시적 요청 시만 (커밋과 분리)
- 큰 Phase 는 chunk 분할 후 ted-run 풀 파이프라인 (메모리)
- 진행 상황 가시화 — 체크리스트 + 한 줄 현황
- backend_kiwoom CLAUDE.md — STATUS.md / HANDOFF.md / CHANGELOG.md 3 문서 동시 갱신 (chunk 커밋과 동일 commit)

### 다음 세션 진입 시 결정 필요

사용자에게 옵션 확인 권장:

1. **C-1β/C-2β MEDIUM 일관 개선** (권고 1순위) — 두 chunk 동시 refactor. errors → tuple / StockMasterNotFoundError 전용 예외. scope 명확, 외부 동작 변화 없음
2. **C-3 (ka10082/83 주봉/월봉, P1)** — chart endpoint 재사용. 새 도메인 2개 + Migration 1. ted-run 풀 파이프라인 적합
3. **scripts/backfill_*.py CLI + 3년 백필 실측** — Phase C-2 마무리. 운영 시간 측정으로 cron 시간 조정 / 페이지네이션 부담 정량화
4. **KOSCOM cross-check 수동** — 가설 B 최종 확정 (스크립트 외 1~2건 비교)
5. **C-2γ 변경 운영 적용** (사실상 N/A — 운영 미가동)

## Files Modified This Session (커밋 대기)

```
src/backend_kiwoom/migrations/versions/008_drop_daily_flow_dup_columns.py  (신규)
src/backend_kiwoom/tests/test_migration_008.py                              (신규, +4 cases)
src/backend_kiwoom/app/adapter/out/persistence/models/stock_daily_flow.py  (-3 컬럼)
src/backend_kiwoom/app/adapter/out/persistence/repositories/stock_daily_flow.py  (-6줄 + 주석)
src/backend_kiwoom/app/adapter/out/kiwoom/_records.py                       (-3 필드 + 주석)
src/backend_kiwoom/app/adapter/web/routers/daily_flow.py                    (-3 필드)
src/backend_kiwoom/tests/test_migration_007.py                              (BIGINT 9→6 + DROP 부재 단언)
src/backend_kiwoom/tests/test_stock_daily_flow_repository.py                (-3 fixture)
src/backend_kiwoom/tests/test_daily_flow_router.py                          (-3 fixture + 부재 단언)
src/backend_kiwoom/tests/test_kiwoom_mrkcond_client.py                      (-3 assertion → fields 단언)
src/backend_kiwoom/STATUS.md                                                (Phase C 60→70%, chunk 18)
src/backend_kiwoom/docs/plans/endpoint-10-ka10086.md                        (§ 12 정정 + § 12.8 신규)
docs/ADR/ADR-0001-backend-kiwoom-foundation.md                              (§ 21 추가)
CHANGELOG.md                                                                 (prepend)
HANDOFF.md                                                                   (전체 갱신)
```

15 files changed (신규 2 + 수정 13).
