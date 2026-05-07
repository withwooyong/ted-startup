# Session Handoff

> Last updated: 2026-05-07 (KST) — **backend_kiwoom A2 (α + β) + A3-α + F1 완료 — 단일 세션 누적 4 PR**
> Branch: `master` (working tree clean — 4 PR 모두 커밋 완료)
> Latest commit: F1 — security(kiwoom) auth.py `__context__` leak 백포트
> 이전 마일스톤: `cce855c` — feat(kiwoom) Phase A3-α KiwoomClient 공통 트랜스포트 + ka10101 어댑터
> 세션 시작점: `265b720` — security(kiwoom): Phase A2 사전 보안 PR (이전 세션 마지막)

## Current Status

backend_kiwoom **Phase A 의 인증·트랜스포트 계층 100% 완료**.

| 단계 | 커밋 | 범위 |
|------|------|------|
| A1 기반 인프라 | `12f46aa` (이전 세션) | Settings + Fernet Cipher + structlog 마스킹 + Migration 001 + KiwoomCredentialRepository |
| 보안 사전 PR | `265b720` (이전 세션) | ADR-0001 § 3 #1·#2·#3 적용 (정규식 보강 + 직렬화 차단 + scrub helper) |
| **A2-α 토큰 발급** | **`115fcce`** | KiwoomAuthClient.issue_token + IssueUseCase + TokenManager (alias 별 Lock + max_aliases 캡) + POST /tokens (admin) + FastAPI 진입점 |
| **A2-β 토큰 폐기 + lifespan** | **`0ea955c`** | KiwoomAuthClient.revoke_token + RevokeUseCase + TokenManager 확장 + DELETE/revoke-raw + lifespan graceful shutdown + RequestValidationError 핸들러 |
| **A3-α 공통 트랜스포트 + ka10101** | **`cce855c`** | KiwoomClient (모든 후속 endpoint 의 기반) + KiwoomStkInfoClient.fetch_sectors |
| **F1 auth.py `__context__` 백포트** | **다음 커밋** | `_do_issue_token` 4 + `expires_at_kst` 1 + `revoke_token` 4 = 9개 raise site 변수 캡처 패턴 + 회귀 테스트 8 |

**누적 결과**: **285 tests passed / coverage 91.0%** / 적대적 이중 리뷰 누적 CRITICAL 4 + HIGH 14+ 발견 → 전부 적용 → 0건 PASS.

## Completed This Session

### Phase A2-α (커밋 `115fcce`)

- KiwoomAuthClient.issue_token (httpx + tenacity, 401/403/429 재시도 금지)
- IssueKiwoomTokenUseCase + TokenManager (asyncio.Lock per alias, max_aliases=1024 cap, session_provider 패턴)
- POST /api/kiwoom/auth/tokens (admin only, hmac.compare_digest fail-closed)
- FastAPI 진입점 + lifespan
- ADR-0001 § 6 추가 (16 결정)
- **적대적 1R**: HIGH 5 (lock proliferation / `__context__` leak / 429 timing oracle / 세션 누수 / 이중 SELECT) → 전부 적용

### Phase A2-β (커밋 `0ea955c`)

- KiwoomAuthClient.revoke_token (재시도 0회, best-effort)
- RevokeKiwoomTokenUseCase (revoke_by_alias / revoke_by_raw_token, 401/403 idempotent 변환)
- TokenManager 확장 (peek/invalidate_all/alias_keys)
- DELETE /tokens/{alias} + POST /tokens/revoke-raw (admin only)
- lifespan graceful shutdown (`asyncio.wait_for(20s)` + finally 분리)
- RequestValidationError 핸들러 + sensitive paths (`/revoke-raw`)
- ADR-0001 § 7 추가 (16 결정)
- **적대적 1R**: **CRITICAL 1 (revoke-raw 422 token echo)** + HIGH 4 → 전부 적용

### Phase A3-α (커밋 `cce855c`)

- KiwoomClient 공통 트랜스포트 (httpx + tenacity + Semaphore + paginated + token_provider)
- KiwoomStkInfoClient.fetch_sectors (ka10101) + Pydantic 3개
- ADR-0001 § 8 추가 (16 결정)
- **적대적 1R**: **CRITICAL 1 (`__context__` 토큰 leak)** + HIGH 4 → 전부 적용

### F1 — auth.py `__context__` leak 백포트 (다음 커밋)

- A3-α C-1 패턴을 KiwoomAuthClient (au10001 / au10002) 에 백포트 — **9개 raise site**
  - `_do_issue_token` 4 (request 검증 / 네트워크 / JSON 파싱 / response 검증)
  - `TokenIssueResponse.expires_at_kst` 1 (strptime ValueError)
  - `revoke_token` 4 (au10001 과 동일 4개)
- 변수 캡처 + except 밖 raise — `from None` 코드에서 0건 (docstring만 잔존)
- JSON dict guard 보너스 — `try-except-else: if not isinstance(parsed, dict): raise` 추가
- 회귀 테스트 +8 — `__cause__ is None` + `__context__ is None` 검증
- ADR-0001 § 9 추가 (5 결정 + 보안 일관성 종결 섹션)
- **적대적 1R**: CRITICAL 0 / HIGH 0 PASS (변경 범위 작음)

### 본 세션 핵심 발견 (보안 일관성 차원)

- **`from None` 의 `__context__` leak**: `from None` 은 `__suppress_context__=True` 만 set, `__context__` 는 살아있어 Sentry/structlog `walk_tb` 가 leak 가능. 해결 패턴: `raise` 를 `except` 블록 밖에서 변수 캡처 패턴으로 실행 (PEP 3134 자동 chaining 차단). A3-α 에서 적용 → **F1 에서 auth.py 백포트 완료** (보안 일관성 종결).
- **CRITICAL C-1 (β)**: `/revoke-raw` 422 응답이 raw_token 평문을 `errors[].input` 으로 echo. body plaintext 비누설 위협 모델 핵심 깨짐. RequestValidationError 핸들러 + sensitive paths 화이트리스트로 차단.
- **헤더 인젝션 차단** (A3-α): 토큰 / cont-yn / next-key 모두 wire 전 정규식 화이트리스트 검증 (request + response 양쪽).
- **보안 일관성 종결 (F1)**: backend_kiwoom 의 모든 외부 호출 어댑터 (`auth.py`, `_client.py`, `stkinfo.py`) 가 단일 예외 chain 정책으로 수렴. `from None` 코드에서 0건. 회귀 테스트 누적 12건 (A3-α 4 + F1 8).

## Files Modified (본 세션, 누적 3 PR)

```
A2-α (115fcce):
  app/adapter/out/kiwoom/_exceptions.py         (신규)
  app/adapter/out/kiwoom/auth.py                (신규 — issue_token)
  app/application/service/token_service.py     (신규 — IssueUseCase + TokenManager)
  app/adapter/web/_deps.py                      (신규 — admin guard)
  app/adapter/web/routers/auth.py               (신규 — POST /tokens)
  app/main.py                                   (신규)
  app/application/dto/kiwoom_auth.py            (확장 — mask_token)
  app/adapter/out/persistence/.../kiwoom_credential.py  (확장 — decrypt_row)
  tests/test_kiwoom_auth_client.py              (신규)
  tests/test_token_service.py                   (신규)
  tests/test_kiwoom_auth_router.py              (신규)
  tests/test_logging_masking.py                 (확장 +3)

A2-β (0ea955c):
  app/adapter/out/kiwoom/auth.py                (확장 — revoke_token)
  app/application/service/token_service.py     (확장 — RevokeUseCase + 함수형 helper)
  app/adapter/web/_deps.py                      (확장 — get_revoke_use_case)
  app/adapter/web/routers/auth.py               (확장 — DELETE/revoke-raw)
  app/main.py                                   (확장 — graceful shutdown + ValidationError 핸들러)
  tests/test_kiwoom_auth_client.py              (확장 +8)
  tests/test_token_service.py                   (확장 +12)
  tests/test_kiwoom_auth_router.py              (확장 +12)
  tests/test_lifespan.py                        (신규 — 3 케이스)

A3-α (cce855c):
  app/adapter/out/kiwoom/_client.py             (신규 — KiwoomClient)
  app/adapter/out/kiwoom/stkinfo.py             (신규 — KiwoomStkInfoClient)
  tests/test_kiwoom_client.py                   (신규 — 24 케이스)
  tests/test_kiwoom_stkinfo_client.py           (신규 — 14 케이스)

F1 (다음 커밋):
  app/adapter/out/kiwoom/auth.py                (수정 — 9개 raise site 변수 캡처 패턴 + JSON dict guard)
  tests/test_kiwoom_auth_client.py              (확장 +8 — __context__ 회귀)

문서:
  docs/ADR/ADR-0001-backend-kiwoom-foundation.md (§6, §7, §8, §9 추가)
  docs/research/kiwoom-rest-feasibility.md       (§10.5 / §10.6 현행화)
  CHANGELOG.md                                   (4 항목 prepend)
  HANDOFF.md                                     (본 문서, overwrite)
```

## Context for Next Session

### 다음 작업 우선순위

#### Phase A3-β (다음 PR — F1 완료, 보안 일관성 종결됨)

Migration 002 (sector 테이블 + UNIQUE/index) + Sector ORM + SectorRepository (`upsert_many` / `deactivate_missing`) + SyncSectorMasterUseCase (5 시장 순회 + 시장 단위 격리) + GET `/api/kiwoom/sectors` + POST `/api/kiwoom/sectors/sync` (admin) + 통합 테스트 + KiwoomMaxPagesExceededError 라우터 매핑 (F3 통합).

#### Phase A3-γ

APScheduler weekly cron (KST 일 03:00) + scheduler 모듈 + lifespan 통합.

#### 운영 dry-run (DoD §10.3 일괄)

α + β + A3-α 합쳐 키움 운영 자격증명 1쌍으로 검증 (사용자 등록 후 별도 작업):
1. expires_dt timezone (KST/UTC) 확정
2. authorization 헤더 빈/생략 (au10001)
3. 401/403 동작 차이
4. 같은 토큰 2회 폐기 응답 패턴 (200/401/return_code)
5. ka10101 5 시장 호출 + 페이지네이션 발생 여부
6. JWT/hex/Kiwoom 평문 토큰 마스킹 회귀

### 사용자 선호·제약 (이번 세션 학습)

- **chunk 분할 권장**: 1,500줄 미만이라도 KiwoomClient 같이 후속 의존성 큰 작업은 단독 PR (사용자 합의 후 진행)
- **이중 리뷰 1R 충분**: A2 사전 보안 PR 은 3R 까지 갔으나 이후 PR 들은 1R 적용 후 PASS
- **푸시 분리**: 글로벌 CLAUDE.md 규칙대로 커밋과 푸시는 항상 별도 확인. 본 세션 모든 PR 미푸시 상태
- **운영 dry-run 보류 OK**: 코드 + 테스트 + 이중 리뷰까지 완료한 상태로 진행. 운영 자격증명 등록은 사용자가 별도 시점에

### 누적 follow-up (defer 가능, 별도 PR)

**보안 사전 PR (5건)**:
- `_KIWOOM_SECRET_PATTERN` 화이트리스트 확장 (`client_secret` / `bearer` / `apikey` / `private_key`)
- `_TOKEN_FIELDS_BY_API` allow-list 전환 (deny-list → allow-list)
- SQLAlchemy `before_insert` event listener — raw_response scrub 자동 적용
- CI grep 룰 — f-string 내 평문 secret/token 삽입 PR 차단
- 자잘한 정리 — `_capture_stdlib_log` IndexError 가드 / deepcopy memo 변조 / `expires_dt` 마스킹

**A2-α (5건)**: verify=True 명시 / admin rate-limiting / Kiwoom 평문 토큰 마스킹 회귀 강화 / readiness probe / router-level appkey 누설 회귀

**A2-β (5건)**: pre-commit grep `model_dump+logger` / `/revoke-raw` rate-limiting / `TokenManager.frozen` shutdown 차단 / `RevokeRawTokenRequest.token` Field pattern / shutdown metric

**A3-α (5건 — F1 ✅ 적용 완료, 4건 잔존)**:
- ~~F1: auth.py `__context__` leak 백포트~~ ✅ **적용** (다음 커밋, 회귀 테스트 8 + ADR § 9)
- F2: KiwoomBusinessError.message scrub
- F3: KiwoomMaxPagesExceededError 라우터 매핑 (A3-β 통합)
- F4: KiwoomClient instance 단일성 강제 (Phase D 사용자 trigger 시)
- F5: next-key 없이 cont-yn=Y edge case (운영 검증 후)

### Known Limitations (ADR-0001 누적)

- `copyreg.dispatch_table[KiwoomCredentials]` type-level 우회 (Python pickle 본질)
- `object.__getstate__(creds)` 직접 호출 우회 (Python 3.11+)
- `_KIWOOM_SECRET_PATTERN` prefix 없는 평문 임베딩 미매칭 — A2/A3 는 본문 logger 미전달 fail-closed
- 한국어/자연어 prefix 변형 정규식 보조 한계 (CI grep 룰로 caller 책임 강제)

### 의존성 그래프

```
A1 (12f46aa)
   → 보안 사전 PR (265b720)
   → A2-α (115fcce)
   → A2-β (0ea955c)
   → A3-α (cce855c)
   → F1 auth.py __context__ 백포트 (본 세션 마지막)
   → A3-β (Migration 002 + Repository + UseCase + 라우터, 다음 PR)
   → A3-γ (APScheduler weekly)
   → 운영 dry-run (DoD §10.3)
   → B (종목 마스터) → C (OHLCV) → D~G
```

## Verification Summary (세션 종합)

```
누적 커밋:    4 (A2-α / A2-β / A3-α / F1)
Tests:       285 passed (이전 161 → +124)
Coverage:    91.0% (목표 80% 초과 — token_service 99% / _client 89% / stkinfo 100% / auth 91%)
Lint:        ruff 0 / mypy strict 0 / format 0
Security:    bandit 0 / pip-audit 0 CVE
Runtime:     FastAPI 라우트 + ValidationError 핸들러 + KiwoomClient smoke OK
Reviews:     이중 리뷰 1R x 4 PR — CRITICAL 누적 4 + HIGH 누적 14+ → 전부 적용 → 0건 PASS
             (F1 단독 — CRITICAL 0 / HIGH 0, 패턴 백포트만)
E2E:         자동 생략 (백엔드 전용 변경)
Push:        대기 (사용자 명시 요청 시만)

보안 일관성 종결 (F1 후):
- backend_kiwoom 의 모든 외부 호출 어댑터 단일 예외 chain 정책 수렴
- `from None` 코드에서 0건 (docstring/주석만 잔존)
- __context__ 회귀 테스트 누적 12건 (A3-α 4 + F1 8)
```

## Open Questions / Risks

- **운영 dry-run 보류 누적**: A2 + A3 모두 코드 검증만. 운영 자격증명 등록 후 일괄 검증 필요. 보류 길어질수록 통합 디버깅 부담 ↑
- ~~F1 백포트 우선순위~~ ✅ 본 PR 에서 종결 — A3-β 진입 가능
- **A3-γ APScheduler 통합**: lifespan 변경이 추가로 들어감. β 의 graceful shutdown hook 과 충돌 없는지 검증 필요
