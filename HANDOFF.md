# Session Handoff

> Last updated: 2026-05-07 (KST) — **backend_kiwoom Phase A2 (α + β) 완료 — 토큰 라이프사이클 전체 (issue + revoke + lifespan graceful shutdown)**
> Branch: `master` (working tree dirty — β PR 미커밋)
> Latest commit: `115fcce` — feat(kiwoom): Phase A2-α au10001 발급 경로
> 세션 시작점: `115fcce` 동일

## Current Status

`backend_kiwoom` **Phase A2-β (au10002 폐기 + lifespan graceful shutdown) 완료**. β chunk: au10002 폐기 + RevokeKiwoomTokenUseCase + TokenManager 확장 (peek/invalidate_all/alias_keys) + DELETE/revoke-raw 라우터 + lifespan graceful shutdown.

ted-run 풀 파이프라인 5관문 통과 + 적대적 이중 리뷰 1R 사이클. **CRITICAL 1 (C-1) + HIGH 4 + MEDIUM 5** 발견 → 전부 적용 → CRITICAL/HIGH 0 PASS.

## Completed This Session (Phase A2-β — 1R 사이클)

### Step 0: TDD (sonnet)

- 4 신규 케이스 그룹 / +35 케이스 (red 확인 후 green)
- `tests/test_lifespan.py` (신규, 3 케이스)
- `tests/test_kiwoom_auth_client.py` (확장 +8) — revoke adapter
- `tests/test_token_service.py` (확장 +12) — RevokeUseCase + TokenManager 확장
- `tests/test_kiwoom_auth_router.py` (확장 +12) — DELETE/revoke-raw + C-1 + H-1 회귀

### Step 1: 구현 (opus)

- `app/adapter/out/kiwoom/auth.py` 확장 — `revoke_token` + `TokenRevokeRequest`/`TokenRevokeResponse`
- `app/application/service/token_service.py` 확장 — `RevokeKiwoomTokenUseCase` + `RevokeResult` + `TokenManager.peek/invalidate_all/alias_keys` + `revoke_all_aliases_best_effort`
- `app/adapter/web/_deps.py` 확장 — `get_revoke_use_case` / `set_revoke_use_case` 싱글톤
- `app/adapter/web/routers/auth.py` 확장 — DELETE/revoke-raw + `_map_revoke_exception`
- `app/main.py` 확장 — lifespan graceful shutdown + RequestValidationError 핸들러

### Step 2 — Round 1 (이중 리뷰 병렬)

**2a (sonnet python-reviewer)**: HIGH 3 + MEDIUM 5 + LOW 2

HIGH 3건:
1. `_map_revoke_exception` `KiwoomRateLimitedError` 미매핑 → fallback 500
2. `revoke_by_raw_token` `KiwoomCredentialRejectedError` idempotent 변환 누락 → fallback 500
3. session context 의 ORM lazy attr 가정 (architecture fragility) — 코멘트만

**2b (opus security-reviewer 적대적)**: **CRITICAL 1** + HIGH 3 + MEDIUM 5 + LOW 3 + FOLLOW-UP 5

CRITICAL 1건 (가장 위협적):
- **C-1**: `/revoke-raw` 422 응답이 raw_token 평문을 `errors[].input` 으로 echo. β 의 핵심 위협 모델 (body plaintext 비누설) 정확히 깨짐. PoC 재현 완료.

HIGH 3건:
- H-1: `_map_revoke_exception` RateLimited 매핑 부재 (1차와 동일)
- H-2: `revoke_by_raw_token` rate-limit 부재 (admin key 유출 시 키움 무한 펌핑) — defer F2
- H-3: lifespan finally 의 `engine.dispose()` 가 revoke hang/cancel 시 도달 불가

### Step 2 — Round 1 수정 (전부 적용)

**C-1**:
- `app/main.py` — `RequestValidationError` 핸들러 + `_SENSITIVE_VALIDATION_PATHS` 화이트리스트 (`/revoke-raw`)
- 422 응답에서 input/ctx 제거 — type/loc/msg 만 노출
- 회귀 테스트 3건 (alias 빈 / token list-wrap / extra field)

**H-1**: 라우터 양쪽 (`issue_token` + `_map_revoke_exception`) 에 `KiwoomRateLimitedError` → 503 매핑 + except tuple 확장. 회귀 테스트 2건.

**H-2/M-5**: `revoke_by_raw_token` 도 `KiwoomCredentialRejectedError` → `RevokeResult(reason='already-expired-raw')` 변환. `_map_revoke_exception` fallback 도 추가. 회귀 테스트 1건.

**H-3**: lifespan finally 분리 + `asyncio.wait_for(timeout=20s)` + `CancelledError`/`TimeoutError`/`Exception` 모두 swallow → 무조건 `invalidate_all` + `engine.dispose()` 도달.

**M-1**: `revoke_by_raw_token` 의 `invalidate` 를 method 시작 직후로 이동 (decrypt 실패해도 캐시 비움).

**M-3**: `TokenManager.frozen` shutdown 차단 — defer F3.

### Step 3 — Verification Loop (5관문)

- **3-1 컴파일**: `py_compile` clean
- **3-2 정적분석**: `ruff check` 0 / `mypy --strict` 0 (app + new tests)
- **3-3 테스트**: 239 passed / coverage **89.95%** (token_service 99%, auth 91%, routers 83%)
- **3-4 보안 스캔**: bandit 0 / pip-audit 0 CVE
- **3-5 런타임**: FastAPI 라우트 등록 (POST/DELETE/revoke-raw + /health) + `RequestValidationError` 핸들러 등록 확인

### Step 4 — E2E 자동 생략 (백엔드 전용)

### Step 5 — ADR §7 + CHANGELOG + HANDOFF + 커밋

- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 7 추가 (Phase A2-β 16 결정 기록)
- `CHANGELOG.md` 새 항목 (A2-β)
- `HANDOFF.md` 본 문서

## Files Modified

```
app/adapter/out/kiwoom/auth.py              (확장 +revoke_token + Pydantic 2개)
app/application/service/token_service.py    (확장 +RevokeUseCase + TokenManager 확장 + helper)
app/adapter/web/_deps.py                    (확장 +get_revoke_use_case 싱글톤)
app/adapter/web/routers/auth.py             (확장 +DELETE/revoke-raw + _map_revoke_exception)
app/main.py                                 (확장 +graceful shutdown + ValidationError 핸들러)
tests/test_kiwoom_auth_client.py            (확장 +8 — revoke adapter)
tests/test_token_service.py                 (확장 +12 — RevokeUseCase + TokenManager 확장)
tests/test_kiwoom_auth_router.py            (확장 +12 — DELETE/revoke-raw + C-1/H-1/H-2 회귀)
tests/test_lifespan.py                      (신규 — graceful shutdown 3 시나리오)
docs/ADR/ADR-0001-backend-kiwoom-foundation.md (§7 추가)
CHANGELOG.md                                (A2-β 항목 추가)
HANDOFF.md                                  (본 문서)
```

## Next Session Plan

### A2 운영 dry-run (DoD §10.3 일괄)

α + β 코드 완료. 운영 키움 자격증명 1쌍 등록 후 일괄 검증:
1. `expires_dt` timezone (KST/UTC) 확정
2. `authorization` 헤더 빈/생략 확정 (au10001)
3. 401/403 동작 차이
4. 같은 토큰 2회 폐기 응답 (200/401/return_code)
5. JWT/hex/Kiwoom 평문 토큰 마스킹 회귀

### Phase A3 (그 다음)

KiwoomStkInfoClient (ka10101) + Migration 002 (sector 테이블) + SectorRepository + SyncSectorMasterUseCase + APScheduler weekly job (KST 일 03:00).

### A2-β follow-up 5건 (defer)

- F1: pre-commit grep — `model_dump` + `logger` 같은 줄 금지
- F2: `/revoke-raw` rate-limiting (`slowapi`)
- F3: `TokenManager.frozen` shutdown 중 신규 발급 차단
- F4: `RevokeRawTokenRequest.token` Field pattern (`^[A-Za-z0-9+/]+$`)
- F5: shutdown metric (`kiwoom_shutdown_revoke_attempts_total`)

### 의존성 그래프

```
A1 (12f46aa) ─┐
              │
보안 사전 PR (265b720) ─┐
                       │
A2-α (115fcce) ──┐
                 │
A2-β (이번 세션, 미커밋) ─┐
                        │
운영 dry-run (별도) ──→ A3 (sector ka10101) ──→ B (종목 마스터) ──→ C (OHLCV) ──→ D~G
```

## Verification Summary

```
Tests:     239 passed (이전 204 → +35)
Coverage:  89.95% (목표 80% 초과)
Lint:      ruff 0 / mypy strict 0 (app + new tests)
Security:  bandit 0 / pip-audit 0 CVE
Runtime:   FastAPI 라우트 + ValidationError 핸들러 등록 OK
Reviews:   1R 이중 리뷰 (sonnet + opus 병렬 독립) — CRITICAL 1 (C-1) + HIGH 4 → 전부 적용 → 0건 PASS
E2E:       자동 생략 (백엔드 전용 변경)
```

## 미커밋 변경 사항 (이번 세션)

본 세션 변경 — 12 파일 (1 신규 + 11 확장)
- 코드 5 확장 (auth/token_service/_deps/routers/main)
- 테스트 1 신규 (lifespan) + 3 확장 (auth_client/token_service/router)
- ADR / CHANGELOG / HANDOFF 갱신

다음 작업: 사용자 확인 후 커밋. 푸시는 명시적 요청 시만 (글로벌 CLAUDE.md 규칙).
