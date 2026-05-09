# Session Handoff

> Last updated: 2026-05-09 09:50 (KST)
> Branch: `master`
> Latest commit (커밋 대기): `docs(kiwoom): 운영 dry-run § ka10086 + ADR § 19/20`
> 직전 푸시: `1da7fda` — Phase C-2β 핸드오프

## Current Status

**Phase C-2β 완료 + 운영 dry-run 1회차 완료**. ka10086 자동화 (UseCase/Router/Scheduler/Lifespan) 가 커밋·푸시됨 (`e442416`/`1da7fda`). 그 위에 운영 dry-run 으로 ka10086 응답 raw 1,200 row 분석 결과 3건의 발견사항 (D-E 중복 / NXT mirror 부분 / 가설 B 확정) 을 ADR-0001 § 19/20 에 기록. 코드 변경은 다음 chunk (C-2γ Migration 008) 로 이월. 본 세션은 dry-run 스크립트 + ADR + CHANGELOG + .gitignore 만 커밋 예정.

## Completed This Session (커밋 대기)

| # | Task | 산출물 | Notes |
|---|------|--------|-------|
| 1 | dry-run capture 스크립트 작성 | `src/backend_kiwoom/scripts/dry_run_ka10086_capture.py` | env appkey/secretkey 기반, DB 우회. 5종 분석 + `--analyze-only` 재분석 모드. ruff/mypy strict 통과 |
| 2 | 운영 dry-run 1회차 실행 (사용자) | 1,200 row 샘플 (3 종목 × KRX/NXT × 2026-05-08) | KiwoomMaxPagesExceededError → max-rows=200 early termination 으로 보강 후 정상 캡처 |
| 3 | 분석 결과 → ADR-0001 § 19/20 추가 | `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` | § 19 = C-2β 자동화 결정 기록 / § 20 = dry-run 발견 3건 + 결정 |
| 4 | CHANGELOG/HANDOFF/.gitignore 갱신 | `CHANGELOG.md` / `HANDOFF.md` / `src/backend_kiwoom/.gitignore` | captures/ 디렉토리 gitignore (vendor raw 응답 외부 노출 차단) |

## In Progress / Pending

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1 | 본 세션 산출물 커밋 + 푸시 | pending | 사용자 승인 후 — 한 commit 으로 묶어서 |
| 2 | C-2γ Migration 008 — D-E 중복 컬럼 DROP | pending | 13→10. NormalizedDailyFlow + ORM + Repository + Pydantic Out 갱신. 별도 chunk |
| 3 | KOSCOM 공시 수동 cross-check (1~2건) | pending | 가설 B 최종 확정. 외부 데이터 비교 — 스크립트 외 |
| 4 | C-1β/C-2β MEDIUM 일관 개선 | pending | errors → tuple / StockMasterNotFoundError 전용 예외. C-1β와 함께 |
| 5 | scripts/backfill_daily_flow.py CLI | pending | 3년 백필 + 시간 실측. C-1β backfill 도 함께 |
| 6 | C-3 (ka10082/83 주봉/월봉, P1) | not started | 같은 chart endpoint 재사용 |
| 7 | indc_tp=1 (금액 모드) 단위 mismatch 검증 | pending | 향후 운영 검증 — for_netprps 가 indc_tp 무시 항상 수량인지 |

## Key Decisions Made (운영 dry-run 결과)

### dry-run 실행 방식 결정
- **DB 우회 + env appkey/secretkey 직접 사용** — TokenManager / DB / alias 등록 우회. 최소 setup 으로 운영 raw 응답 캡처
- **call_paginated 직접 호출 + early termination** — `fetch_daily_market` 의 max_pages=10 cap 우회 + `--max-rows`/`--max-pages` 도입. 가설 B / NXT mirror 분석엔 200 row 충분
- **5종 분석** — fill_rate / sign_patterns / nxt_mirror / partial_mirror_breakdown / d_vs_e_equality / for_qty_invariant. JSON 재분석 모드 (`--analyze-only`) 로 API 재호출 없이 분석 추가 가능

### 발견 결정 (3건)
1. **D-E 중복 컬럼 3개 → Migration 008 DROP** (사용자 승인) — `individual_net_purchase` / `institutional_net_purchase` / `foreign_net_purchase` 제거. 13→10. 별도 chunk (C-2γ)
2. **NXT row 외인 컬럼 100% mirror → 현 상태 유지** (사용자 승인) — KRX 중복 적재. 단순 조정. 코드 변경 없음
3. **가설 B 운영 채택 확정** (사용자 승인) — `_strip_double_sign_int` 그대로. KOSCOM cross-check 1~2건 권고 (문서화 목적)

### 산출물 보관 정책
- **captures/ gitignore** — vendor (Kiwoom) 응답 raw 는 외부 노출 위험 → 로컬 보관만. 분석 결과는 ADR / CHANGELOG 요약으로만

## Known Issues

### dry-run 발견 사항 (코드 미반영)

- **D-E 중복 3개 컬럼**: stock_daily_flow 의 13 영속 컬럼 중 3개가 키움 API 응답 단계에서 동일값. Migration 008 DROP 까지는 NULL 적재 또는 중복 적재 (현재 후자) — DB 스토리지 낭비 ~23%
- **NXT 외인 컬럼 KRX 중복**: NXT row 의 `foreign_volume`/`foreign_net_purchase` 가 KRX 와 동일값. 정보 가치 없으나 정책 단순화 위해 현 상태 유지 결정
- **가설 B KOSCOM 미검증**: `--XXX` → `-XXX` 변환은 운영 응답 패턴으로 강력 지지되지만, 외부 source (KOSCOM 공시) 와 cross-check 미완. 잘못 처리 시 백테스팅 시그널 부호 반전 위험 — 1~2건 수동 비교 권고
- **for_qty invariant 검증 무의미**: `for_qty == for_netprps` 라 abs 비교가 자명한 통과. 의미 있는 검증은 KOSCOM cross-check 후 가능

### 이전 chunk 알려진 이슈 상속

- **C-1β/C-2β MEDIUM**: errors mutable list / ValueError 메시지 검색 (다음 일관 개선 chunk)
- **C-2α 상속**: NUMERIC magnitude 가드 부재 / idx_daily_flow_exchange cardinality
- **운영 검증 미해결**: indc_tp=1 단위 mismatch / OHLCV cross-check (Phase H) / 페이지네이션 빈도 / 3년 백필 시간 / active 3000 + NXT 1500 sync 실측

## Context for Next Session

### 사용자의 원래 의도 / 목표

backend_kiwoom Phase C (백테스팅 코어 데이터) 구축 + 운영 검증으로 데이터 품질 확정. ka10081 (가격) + ka10086 (수급) 짝꿍은 자동화 완료, 이번 세션은 dry-run 으로 ka10086 응답의 알려진 위험 (가설 B / NXT mirror) 검증. 발견된 D-E 중복은 다음 chunk 로 정리 후 운영 활성화.

### 선택된 접근 + 이유

- **dry-run 1회차 = 코드 변경 0** — 검증 결과로 ADR 결정만 기록. 즉각 코드 변경 (Migration 008) 은 별도 chunk 로 분리해 적대적 리뷰 + ted-run 풀 파이프라인 적용
- **DB 우회 + env 직접** — 최소 setup, 운영 안전. 단발 dry-run 에 적합
- **Quality-First** (장애 없이 / 정확한 구조로 / 확장 가능) — 가설 검증을 코드 변경보다 먼저

### 사용자 제약 / 선호

- 한글 커밋 메시지 (~/.claude/CLAUDE.md 글로벌 규칙)
- 푸시는 명시적 요청 시만 (커밋과 분리)
- 큰 Phase 는 chunk 분할 후 ted-run 풀 파이프라인 (메모리)
- 진행 상황 가시화 — 체크리스트 + 한 줄 현황

### 다음 세션 진입 시 결정 필요

사용자에게 옵션 확인 권장:

1. **C-2γ — Migration 008 + 컬럼 정리** (권고 1순위) — 본 세션 결정 (D-E 중복 DROP) 즉시 반영. 13→10 컬럼. ted-run 풀 파이프라인 (인프라/자동화 동시 변경 — 1 chunk 로 충분)
2. **KOSCOM cross-check 수동** — 가설 B 최종 확정. 1~2건 sample 종목·일자 외부 source 비교
3. **scripts/backfill_daily_flow.py CLI + 3년 백필 실측** — Phase C-2 마무리. C-1β backfill 도 함께
4. **C-1β/C-2β MEDIUM 일관 개선 (refactor chunk)** — errors → tuple / StockMasterNotFoundError. 두 chunk 동시 정리
5. **C-3 (ka10082/83 주봉/월봉, P1)** — chart endpoint 재사용

## Files Modified This Session (커밋 대기)

```
src/backend_kiwoom/scripts/dry_run_ka10086_capture.py   (신규, ~530 lines, ruff/mypy strict 통과)
docs/ADR/ADR-0001-backend-kiwoom-foundation.md          (§ 19 + § 20 추가, ~120 lines)
src/backend_kiwoom/.gitignore                           (captures/ 추가)
CHANGELOG.md                                            (prepend)
HANDOFF.md                                              (전체 갱신)
```

5 files changed (신규 1 + 수정 4). captures/ 자체는 gitignore — 커밋 안 함.
