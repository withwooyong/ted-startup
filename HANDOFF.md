# Session Handoff

> Last updated: 2026-05-07 (KST) — **backend_kiwoom Phase A3-α (KiwoomClient 공통 트랜스포트 + ka10101) 완료**
> Branch: `master` (working tree dirty — α PR 미커밋)
> Latest commit: `0ea955c` — feat(kiwoom): Phase A2-β au10002 폐기 + lifespan graceful shutdown
> 세션 시작점: `0ea955c` 동일

## Current Status

`backend_kiwoom` **Phase A3-α 완료**. KiwoomClient 공통 트랜스포트 (모든 후속 endpoint B~G 22개의 기반) + KiwoomStkInfoClient.fetch_sectors (ka10101) + 단위 테스트만. β/γ 별도 PR.

ted-run 풀 파이프라인 5관문 통과 + 적대적 이중 리뷰 1R. **CRITICAL 1 (C-1) + HIGH 4 + MEDIUM 7** 발견 → 전부 적용 → CRITICAL/HIGH 0 PASS.

## Completed This Session (Phase A3-α — 1R 사이클)

### Step 0: TDD (sonnet)

- 2 신규 테스트 파일 / +38 케이스 (red 확인 후 green)
- `tests/test_kiwoom_client.py` (신규, 24 케이스 — 트랜스포트 + 회귀)
- `tests/test_kiwoom_stkinfo_client.py` (신규, 14 케이스 — 어댑터)

### Step 1: 구현 (opus)

- `app/adapter/out/kiwoom/_client.py` (신규) — KiwoomClient + KiwoomResponse + KiwoomMaxPagesExceededError
- `app/adapter/out/kiwoom/stkinfo.py` (신규) — KiwoomStkInfoClient + Pydantic 3개

### Step 2 — Round 1 (이중 리뷰 병렬, sonnet + opus)

**2a (sonnet python-reviewer)**: HIGH 2 + MEDIUM 5 + LOW 5

HIGH 2건:
1. `call_paginated` AsyncGenerator + break 계약 문서화 부족
2. Semaphore + interval Lock 의도와 실제 동작 불일치 — 적대적 H-2와 동일

**2b (opus security-reviewer 적대적)**: **CRITICAL 1** + HIGH 2 + MEDIUM 3 + LOW 3 + FOLLOW-UP 4

CRITICAL 1건 (가장 위협적):
- **C-1**: `from None` 의 `__context__` leak. h11 LocalProtocolError 가 토큰 평문을 메시지에 박아 raise → cause/context chain 에 토큰 leak. Sentry/structlog `walk_tb(__context__)` 노출.

HIGH 2건:
- H-1: `next-key` / `cont-yn` 헤더 인젝션 (키움 응답 변조 시)
- H-2: Semaphore + interval Lock 의도/실제 불일치 (1차와 동일)

### Step 2 — Round 1 수정 (전부 적용)

**C-1 (CRITICAL)**:
- 토큰 wire 전 `_VALID_TOKEN_PATTERN` 정규식 검증 (헤더 인젝션 사전 차단)
- `raise` 를 `except` 밖에서 실행 — 변수 캡처 패턴 (PEP 3134 자동 chaining 차단)
- 회귀 테스트 4건: 토큰 \r\n reject / control char reject / `__context__` None on network / 401

**H-1**: cont_yn `("Y","N")` 외 reject + next_key 정규식 검증 (request + response). 회귀 3건.

**H-2**: `_throttle()` lock 안에서 `_next_slot_ts` atomic 갱신만, sleep 은 lock 밖. 4 코루틴 0/250/500/750ms 분산 sleep — 의도된 동시성 보장.

**M-2**: `mrkt_tp: Literal["0","1","2","4","7"]` 시그니처 (mypy strict 가 caller 까지 강제). SectorListRequest Pydantic 사용. 테스트는 `cast(Any, ...)` 로 안전망 검증.

**1차 HIGH-1**: AsyncGenerator + break 계약 docstring 추가.

**1차 MEDIUM**: `time.monotonic()` 한 번 호출 (`now` 변수 캡처) / SectorListRequest 사용 / max_pages 어댑터 회귀 테스트 추가.

**bandit B101**: `assert` 대신 explicit `if ... raise RuntimeError(...) # pragma: no cover` 패턴.

### Step 3 — Verification Loop (5관문)

- **3-1 컴파일**: py_compile clean
- **3-2 정적분석**: `ruff check` 0 / `mypy --strict` 0 (app 34 + new tests 2)
- **3-3 테스트**: 277 passed / coverage **90.36%** (_client.py 96%, stkinfo.py 97%)
- **3-4 보안 스캔**: bandit 0 / pip-audit 0 CVE
- **3-5 런타임**: KiwoomClient + KiwoomStkInfoClient 인스턴스 smoke OK

### Step 4 — E2E 자동 생략 (백엔드 전용)

### Step 5 — ADR §8 + CHANGELOG + HANDOFF + 커밋

- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 8 추가 (Phase A3-α 16 결정 + follow-up 5건)
- `CHANGELOG.md` 새 항목 (A3-α)
- `HANDOFF.md` 본 문서

## Files Modified

```
app/adapter/out/kiwoom/_client.py             (신규)
app/adapter/out/kiwoom/stkinfo.py             (신규)
tests/test_kiwoom_client.py                   (신규, 24 케이스)
tests/test_kiwoom_stkinfo_client.py           (신규, 14 케이스)
docs/ADR/ADR-0001-backend-kiwoom-foundation.md (§8 추가)
CHANGELOG.md                                  (A3-α 항목 추가)
HANDOFF.md                                    (본 문서)
```

## Next Session Plan

### F1 (다음 PR — 보안 일관성, 우선순위 높음)

auth.py (α/β) 의 동일 `__context__` leak 백포트:
- 모든 `from None` 패턴을 변수-캡처 except 밖 raise 로 리팩토링
- α (au10001): `_do_issue_token` / `expires_at_kst` 의 except 블록
- β (au10002): `revoke_token` 의 except 블록
- 회귀 테스트 추가 (`__context__` is None)

### Phase A3-β (그 다음)

Migration 002 (sector 테이블 + UNIQUE/index) + Sector ORM + SectorRepository (upsert_many / deactivate_missing) + SyncSectorMasterUseCase (5 시장 순회 + 시장 단위 격리) + GET `/api/kiwoom/sectors` + POST `/api/kiwoom/sectors/sync` (admin) + 통합 테스트.

### Phase A3-γ (그 다음)

APScheduler weekly cron (KST 일 03:00) + scheduler 모듈 + lifespan 통합.

### A3-α follow-up 5건 (defer)

- F1: auth.py `__context__` leak 백포트 (위 — 다음 PR)
- F2: KiwoomBusinessError.message scrub
- F3: KiwoomMaxPagesExceededError 라우터 매핑 (A3-β 통합)
- F4: KiwoomClient instance 단일성 강제 (Phase D)
- F5: next-key 없이 cont-yn=Y edge case (운영 검증 후)

### 의존성 그래프

```
A1 (12f46aa) → 보안 사전 PR (265b720) → A2-α (115fcce) → A2-β (0ea955c)
   → A3-α (이번 세션, 미커밋)
   → F1 auth.py __context__ 백포트 (다음 PR — 보안 일관성)
   → A3-β (Migration 002 + Repository + UseCase + 라우터)
   → A3-γ (APScheduler weekly)
   → 운영 dry-run (DoD §10.3)
   → B (종목 마스터) → C (OHLCV) → D~G
```

## Verification Summary

```
Tests:     277 passed (이전 239 → +38)
Coverage:  90.36% (목표 80% 초과; _client.py 96%, stkinfo.py 97%)
Lint:      ruff 0 / mypy strict 0 (app + new tests)
Security:  bandit 0 / pip-audit 0 CVE
Runtime:   KiwoomClient + adapter smoke OK
Reviews:   1R 이중 리뷰 (sonnet + opus 병렬 독립) — CRITICAL 1 + HIGH 4 + MEDIUM 7 → 전부 적용
E2E:       자동 생략 (백엔드 전용 변경)
```

## 미커밋 변경 사항 (이번 세션)

본 세션 변경 — 7 파일 (4 신규 + 3 갱신)
- 코드 2 신규 (_client + stkinfo)
- 테스트 2 신규 (test_kiwoom_client + test_kiwoom_stkinfo_client)
- ADR / CHANGELOG / HANDOFF 갱신

다음 작업: 사용자 확인 후 커밋. 푸시는 명시적 요청 시만 (글로벌 CLAUDE.md 규칙).
