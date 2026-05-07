# Session Handoff

> Last updated: 2026-05-07 (KST) — **backend_kiwoom Phase A2-α (au10001 발급) 완료 (ted-run 풀 파이프라인 + 적대적 이중 리뷰 1R)**
> Branch: `master` (working tree dirty — α PR 미커밋)
> Latest commit: `265b720` — security(kiwoom): Phase A2 사전 보안 PR
> 세션 시작점: `265b720` 동일

## Current Status

`backend_kiwoom` **Phase A2-α (au10001 KiwoomAuthClient 발급 경로) 완료**. au10001 접근토큰 발급 + KiwoomAuthClient + IssueKiwoomTokenUseCase + TokenManager + admin POST 라우터 + FastAPI 진입점. β chunk (au10002 폐기 + lifespan graceful shutdown) 별도 PR. 외부 호출 0 — `httpx.MockTransport` + testcontainers PG16. 운영 dry-run (DoD §10.3) 은 β 와 일괄.

ted-run 풀 파이프라인 5관문 모두 통과 + 적대적 이중 리뷰 1R 사이클 완료. **CRITICAL 0건 / HIGH 0건 PASS**.

## Completed This Session (Phase A2-α — 1R 사이클)

### Step 0: TDD (sonnet)

- 4 신규 테스트 파일 + 1 확장 / +43 케이스 (red 확인 후 green)
- `tests/test_kiwoom_auth_client.py` (신규, 14)
- `tests/test_token_service.py` (신규, 12)
- `tests/test_kiwoom_auth_router.py` (신규, 10)
- `tests/test_logging_masking.py` (확장, +3 au10001 회귀)

### Step 1: 구현 (opus)

- `app/adapter/out/kiwoom/_exceptions.py` (신규) — 5 도메인 예외
- `app/adapter/out/kiwoom/auth.py` (신규) — KiwoomAuthClient + Pydantic 모델
- `app/application/service/token_service.py` (신규) — IssueKiwoomTokenUseCase + TokenManager
- `app/adapter/web/_deps.py` (신규) — admin guard + 싱글톤
- `app/adapter/web/routers/auth.py` (신규) — POST 라우터
- `app/main.py` (신규) — FastAPI 진입점 (α 최소)
- `app/application/dto/kiwoom_auth.py` (확장) — `mask_token` helper
- `app/adapter/out/persistence/repositories/kiwoom_credential.py` (확장) — `decrypt_row`

### Step 2 — Round 1 (이중 리뷰 병렬, sonnet + opus)

**2a (sonnet python-reviewer)**: HIGH 4 + MEDIUM 4 + LOW 1

HIGH 4건:
1. Dead `TokenIssueRequest` Pydantic 모델 (사용 안 됨) → request body 검증 누락
2. `import logging` 대신 `structlog` 권고 (확인 결과 stdlib 도 동일 파이프라인 — 기각)
3. 세션 누수 — `_factory` 에서 AsyncSession 생성 후 close 안 함
4. 이중 SELECT — `find_by_alias` + `get_decrypted` (내부 `find_by_alias` 재호출)

**2b (opus security-reviewer 적대적)**: HIGH 5 + MEDIUM 5 + LOW 3 + FOLLOW-UP 5

HIGH 5건:
- H1 lock proliferation (alias 폭증으로 무한 lock 생성 → DoS)
- H2 `defaultdict[Lock]` race + 동시 테스트가 sync handler 라 의미 없음
- H3 429 retry 가 timing oracle (잘못된 키 vs RPS 초과 구분 가능)
- H4 세션 누수 (DB 풀 고갈 — 1차도 발견)
- H5 Pydantic ValidationError cause chain 이 토큰 평문 보존 (`from None` 미적용)

### Step 2 — Round 1 수정 (전부 적용)

- 세션 라이프사이클 재설계 — `TokenManager(session_provider)` 주입 + 매 발급마다 `async with`
- `max_aliases=1024` 캡 + 무효 alias lock cleanup (`_locks.pop`)
- `dict.setdefault` (atomic) → defaultdict race 회피
- 429 retry 제거 — `KiwoomUpstreamError` 만 재시도
- `from None` — `KiwoomResponseValidationError`, `KiwoomUpstreamError` 모두
- `KiwoomBusinessError.message` super-message 미포함
- `expires_at_kst` ValueError 도메인 매핑
- `mask_token` 25% cap (L1)
- expires_at 응답 분 단위 절단 (M5)
- 라우터 detail 비식별화 (alias / return_msg / appkey 평문 미포함)
- monkeypatch 픽스처 (M3)
- `OSError` broader catch (M4)
- 동시성 테스트 real async yield (`asyncio.Event` 게이트)
- F5 회귀 테스트 추가 (router 레벨 appkey/secretkey/return_msg 누설 방어)

### Step 3 — Verification Loop (5관문)

- **3-1 컴파일**: `py_compile` 32 files clean
- **3-2 정적분석**: `ruff check` 0 / `mypy --strict` 0 (app + new tests)
- **3-3 테스트**: 204 passed / coverage **88.07%** (token_service 100%, _exceptions 100%, auth 91%)
- **3-4 보안 스캔**: `bandit` 0 / `pip-audit` 0 CVE
- **3-5 런타임**: uvicorn FastAPI 기동 OK / `/health` 200 / admin guard 401

### Step 4 — E2E 자동 생략 (백엔드 전용 변경, UI 0)

### Step 5 — ADR + CHANGELOG + 커밋

- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 6 추가 (Phase A2-α 16 결정 기록)
- `CHANGELOG.md` 새 항목 (A2-α)
- `HANDOFF.md` 본 문서

## Files Modified

```
app/adapter/out/kiwoom/__init__.py            (신규, 빈)
app/adapter/out/kiwoom/_exceptions.py         (신규)
app/adapter/out/kiwoom/auth.py                (신규)
app/adapter/out/persistence/repositories/kiwoom_credential.py  (확장 — decrypt_row)
app/adapter/web/__init__.py                   (신규, 빈)
app/adapter/web/_deps.py                      (신규)
app/adapter/web/routers/__init__.py           (신규, 빈)
app/adapter/web/routers/auth.py               (신규)
app/application/dto/kiwoom_auth.py            (확장 — mask_token)
app/application/service/__init__.py           (신규, 빈)
app/application/service/token_service.py      (신규)
app/main.py                                   (신규)
tests/test_kiwoom_auth_client.py              (신규)
tests/test_kiwoom_auth_router.py              (신규)
tests/test_logging_masking.py                 (확장 +3)
tests/test_token_service.py                   (신규)
docs/ADR/ADR-0001-backend-kiwoom-foundation.md (§6 추가)
CHANGELOG.md                                  (A2-α 항목 추가)
HANDOFF.md                                    (본 문서)
```

## Next Session Plan

### Phase A2-β (예정)

au10002 폐기 + KiwoomAuthClient.revoke_token + RevokeKiwoomTokenUseCase + TokenManager.peek/invalidate_all/alias_keys + DELETE /tokens/{alias} + POST /tokens/revoke-raw + lifespan graceful shutdown.

운영 dry-run (DoD §10.3) — α + β 함께 키움 운영 자격증명 1쌍으로 검증:
1. expires_dt timezone (KST/UTC) 확정
2. authorization 헤더 빈/생략 확정
3. 401/403 동작 차이
4. 같은 토큰 2회 폐기 멱등성 응답 (200/401/return_code)
5. JWT/hex/Kiwoom 평문 토큰 마스킹 회귀

### Phase A3 (그 다음)

KiwoomStkInfoClient (ka10101) + Migration 002 (sector 테이블) + SectorRepository + SyncSectorMasterUseCase + APScheduler weekly job.

### A1 → A2-α → A2-β → A3 의존성 그래프

```
A1 (12f46aa) ─┐
              │
보안 사전 PR (265b720) ─┐
                       │
A2-α (이번 세션, 미커밋) ─┐
                        │
A2-β (다음 세션) ─┐
                 │
A3 (그 다음) ──→ B (종목 마스터) ──→ C (OHLCV) ──→ D~G
```

## Verification Summary

```
Tests:     204 passed (이전 161 → +43)
Coverage:  88.07% (목표 80% 초과)
Lint:      ruff 0 / mypy strict 0 (app + new tests)
Security:  bandit 0 / pip-audit 0 CVE
Runtime:   uvicorn 기동 OK + /health + admin guard
Reviews:   1R 이중 리뷰 (sonnet + opus 병렬 독립) — CRITICAL 0 / HIGH 0 (수정 후)
E2E:       자동 생략 (백엔드 전용 변경)
```

## 미커밋 변경 사항 (이번 세션)

본 세션 변경 — 17 파일 (12 신규 + 5 확장)
- 코드 8 신규 + 2 확장
- 테스트 3 신규 + 1 확장
- ADR / CHANGELOG / HANDOFF 갱신

다음 작업: 사용자 확인 후 커밋. 푸시는 명시적 요청 시만 (글로벌 CLAUDE.md 규칙).
