# Session Handoff

> Last updated: 2026-05-07 (KST) — **backend_kiwoom Phase A1 코드화 완료 (ted-run 풀 파이프라인)**
> Branch: `master` (working tree dirty — A1 코드 38 파일 + ADR + CHANGELOG/HANDOFF 미커밋)
> Latest commit: `36ac6d1` — docs(kiwoom): Phase D·E·F·G 14건
> 세션 시작점: `36ac6d1` 동일

## Current Status

`backend_kiwoom` Phase A1 (기반 인프라) **코드화 완료**. ted-run 풀 파이프라인 0/1/2a/2b/3-1/3-2/3-3/3-4/3-5 모두 통과. 117 테스트 / coverage 94.61% / 0 CVE / 0 bandit issue. 다음은 Phase A2 (KiwoomClient + au10001/au10002 인증 클라이언트).

## Completed This Session (Phase A1 — ted-run 풀 파이프라인)

### Step 0: TDD (sonnet)

- 7 테스트 파일 / 117 케이스 작성 (red 확인)
- testcontainers PG16 픽스처 + master_key 세션 픽스처
- 단위 (Cipher / Settings / DTO / 마스킹 / Models) + 통합 (Repository / Migration)

### Step 1: 구현 (opus 패턴 재사용)

- 38 파일 / ~1,500줄
- backend_py PR 6 패턴 복제 (KIS → 키움 도메인). `backend_py.app.*` 0 import.
- 디렉토리: `app/{config,security,observability,application/dto,adapter/out/persistence/{models,repositories}}`
- DB: `kiwoom` 스키마 분리. Migration 001 (3 테이블 + 인덱스 6개)

### Step 2a: 1차 리뷰 (sonnet)

- HIGH 1건 + MEDIUM 5건 발견 → 즉시 수정
  - HIGH: `excluded.updated_at` NULL 주입 → `func.now()` 교체
  - MED: `_scan` set/frozenset 미처리 → 분기 추가
  - MED: `is_active=False` 비활성화 부재 → `deactivate(alias)` 추가
  - MED: `IssuedToken` tz-naive 통과 → `__post_init__` 검증
  - MED: `env: str` 도메인 미검증 → `Literal["prod", "mock"]`
  - MED: `assert` `python -O` 무력화 → `if None: raise`
- 재리뷰 PASS (CRITICAL/HIGH 0건)

### Step 2b: 적대적 보안 리뷰 (opus, 보안 민감 분류)

- CRITICAL/HIGH 0건 PASS
- MEDIUM 5건 (Phase B 진입 전 결정 권고):
  1. secretkey 평문이 정규식 sclub 사각지대 (M1)
  2. KiwoomCredentials dict 직렬화 우회 가능 (M2)
  3. `_scan` set/frozenset 미처리 (M3) — 2a 와 공통, 즉시 수정
  4. raw_response.response_payload 가 au10001 토큰 평문 저장 위험 (M4)
  5. `assert` `python -O` 무력화 (M5) — 2a 와 공통, 즉시 수정

### Step 3: Verification 5관문

- 3-1 컴파일: `python -c "import ..."` smoke OK
- 3-2 정적분석: ruff 0 + mypy strict 0
- 3-3 테스트: 117 passed / coverage **94.61%** (목표 80% 초과)
- 3-4 보안: bandit 0 issues + pip-audit **0 known CVE**
- 3-5 마이그레이션: alembic upgrade/downgrade 양방향 OK + 멱등성

### Step 4: E2E

자동 생략 — A1 은 백엔드 전용 + UI 변경 없음. 분류 매트릭스 기준.

### Step 5: ADR + 커밋 (진행 중)

- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` — 본 세션 결정 5건 + Phase B 진입 전 미적용 4건 기록
- CHANGELOG.md prepend
- HANDOFF.md overwrite (본 문서)
- 커밋 대기 (사용자 확인 후 진행)

## In Progress / Pending

| # | 항목 | 상태 | Notes |
|---|------|------|-------|
| 1 | **본 세션 결과 커밋** (A1 코드 + ADR + CHANGELOG/HANDOFF) | ⏳ 사용자 대기 | 한글 메시지 + Co-Authored-By. 푸시는 별도 확인 |
| 2 | **Phase A2 코드화** | 🟡 다음 세션 | KiwoomClient 공통 트랜스포트 + KiwoomAuthClient (au10001/au10002) + Issue/Revoke UseCase + TokenManager + auth router + lifespan |
| 3 | **A2 진입 전 보안 정책 4건** | 🔴 A2 코드 작성 직전 | ADR-0001 § 3 |
| 4 | **운영 검증 1순위 정리** | 🟡 A2 첫 호출 시점 | endpoint-01-au10001.md DoD § 10.3 (expires_dt timezone, authorization 헤더 빈/생략 등) |

## Key Decisions Made (본 세션)

### Phase A1 핵심 설계

1. **backend_py 와 동일 스택 + 0 import**: Python 3.12 / FastAPI / SQLAlchemy 2.0 (asyncpg) / Pydantic v2 / structlog / Fernet / pytest+testcontainers PG16. `backend_py.app.*` 미import — 패턴만 복제
2. **DB 스키마 분리 (`kiwoom`)**: 같은 PG 인스턴스 + 별도 schema. Alembic `version_table_schema="kiwoom"` 로 마이그레이션 이력도 분리
3. **Fernet + key_version 회전 대비**: `_fernets[v] = Fernet(key)` 다중 버전 dict. 현재 v1 만, 회전 자동화는 Phase B 후반
4. **structlog 2층 마스킹**: 키 매칭 (17 SENSITIVE_KEYS + 19 SUFFIXES) + 정규식 (JWT/40+hex). `_scan` 이 dict/list/tuple/**set/frozenset**/str 재귀
5. **IssuedToken tz-aware 강제**: `__post_init__` 에서 `expires_at.tzinfo is None` → `ValueError`. 키움 응답 KST 파싱 시 9시간 오차 차단
6. **Repository ON CONFLICT 의 `updated_at`**: `excluded.updated_at` 은 NULL — `func.now()` 명시 (HIGH 수정)
7. **Repository deactivate 추가**: `is_active.is_(True)` 필터 + 멱등성 (이미 비활성이면 False). `list_active_by_env` 가 의미 가짐
8. **mypy strict 통과 helper**: `rowcount_of(result)` — `Result[Any]` 의 `.rowcount` attr-defined 우회. backend_py 의 `_helpers.py` 패턴 복제
9. **downgrade 안전판**: `kiwoom_credential` row 0 보장. 데이터 있으면 `RAISE EXCEPTION` — 운영 사고 방어
10. **설계 의도적 미적용 4건** (ADR-0001 § 3): secretkey 정규식 보강 / DTO 직렬화 우회 방어 / raw_response 토큰 평문 차단 / 마스터키 회전 자동화 — A2 진입 전 결정

## Known Issues

### Phase B (A2~) 진입 전 결정 (ADR-0001 § 3)

| # | 항목 | 영향 | 결정 시점 |
|---|------|------|-----------|
| 1 | **secretkey 정규식 sclub 사각지대** (logging.py) | 키움 secretkey 형식이 JWT/40+hex 패턴에 매칭 안 됨 — f-string 으로 logger 에 평문 삽입 시 1차 키 매칭 우회. 정규식 보강 또는 ruff custom rule | A2 KiwoomAuthClient 작성 직전 |
| 2 | **KiwoomCredentials 직렬화 우회** (kiwoom_auth.py) | `dataclasses.asdict(creds)` 후 키 rename 하면 secretkey 노출 가능. SecretStr wrapper 또는 `__reduce__`/`__getstate__` raise | A2 진입 전 |
| 3 | **raw_response 토큰 평문 저장** (raw_response.py) | au10001 응답을 raw_response 에 저장하면 access_token 평문 JSONB. UseCase 가 api_id == "au10001" skip 또는 토큰 필드 제거 후 저장 | A2 au10001 코드 작성 직전 |
| 4 | **마스터키 회전 자동화 부재** | `_fernets[2] = Fernet(new_key)` 구조는 있지만 실제 회전 마이그레이션 스크립트 + Settings 다중 키 필드 부재 | Phase B 후반 |

### 알려진 위험 (계획 단계 — 본 세션 추가)

- **운영 자격증명 alias 명명 혼동**: `prod-*` / `mock-*` 명명 규칙 강제 부재. 잘못된 alias 로 prod 자격증명을 mock 도메인 호출에 사용 가능
- **DB 백업 ↔ 마스터키 분리 정책 부재**: BYTEA 백업본만 유출되면 복호화 불가하나, K8s secret 이 마스터키 + DB password 같이 보관 시 1점 실패. 운영 정책 문서 필요
- **raw_response retention 자동화 부재**: 90일 retention 권장만 코멘트, 자동 drop job 미정의 — 평문 응답 누적 위험
- **timing attack 가능성 (alias 비교)**: PostgreSQL `=` 연산자 + 인덱스 — leak 영향 미미. admin_api_key 비교는 A2 라우터에서 `hmac.compare_digest` 사용 필수

## Context for Next Session

### 사용자의 원 목적 (본 세션 흐름)

세션 시작 명령: `/ted-run Phase A 코드화 착수`. AskUserQuestion 으로 chunk 분할 합의 → A1 (기반 인프라만) 선택 → ted-run 풀 파이프라인.

수행 흐름:
1. **자동 분류** — 보안 민감 (auth/credential/token/Fernet 키워드 + KiwoomAuthClient/Cipher 도메인). 게이트 0/2a/2b/3-1~3-5 모두 ON, 4 자동 생략
2. **Step 0 TDD** — 7 파일 / 117 테스트 작성. testcontainers PG16 픽스처
3. **Step 1 구현** — 38 파일 / ~1,500줄. backend_py 패턴 복제
4. **Step 2a/2b 병렬** — sonnet + opus 독립 리뷰. HIGH 1건 즉시 수정
5. **Step 3 Verification** — 5관문 모두 통과
6. **Step 5 Ship** — ADR + CHANGELOG + HANDOFF + 커밋 대기

### 선택한 접근과 이유

- **A1 chunk 한정**: Phase A 전체 (3,800+줄) 는 단일 PR 부적절. A1 (기반 인프라 — 외부 호출 0) → A2 (인증) → A3 (sector) 순으로 chunk 분할 + 각 chunk 풀 파이프라인 통과
- **backend_py 패턴 복제 전략**: KIS 도메인 처리를 키움으로 이름만 변경 + 클래스 신규 작성. 학습 비용 0, import 의존성 0
- **이중 리뷰 독립 실행**: sonnet 1차 + opus 2차를 단일 메시지에 병렬 호출. 결과 공유 안 함 — Santa Method 의 핵심
- **3-2 mypy strict 우선**: `Result[Any].rowcount` attr-defined 에러를 helper 로 우회 (backend_py 의 `rowcount_of` 패턴)
- **테스트 환경 격리**: monkeypatch 로 conftest 가 주입한 KIWOOM_* env 격리 → default 검증 가능

### 사용자 선호·제약 (재확인)

- **한국어 커밋 메시지 + Co-Authored-By** (전역 CLAUDE.md)
- **`git push` 명시 요청 시에만** — 본 세션도 커밋 후 푸시 별도 확인
- **선택지 제시 후 사용자 결정** — chunk 분할은 명시 합의 후 진행
- **체크리스트 + 한 줄 현황** (memory: feedback_progress_visibility) — TaskCreate 7 단계 사용
- **block-no-verify heredoc 오탐지 대응** — 본 세션 커밋 시 적용

### 다음 세션에서 먼저 확인할 것

1. **본 세션 결과 커밋**:
   - 추천: 단일 커밋 — `feat(kiwoom): Phase A1 — 기반 인프라 (Settings + Cipher + structlog + Migration 001 + Repository, 117 tests / 94.61% coverage)`
   - 또는 분리: (a) 골격/Settings (b) Cipher/structlog (c) Models/Migration (d) Repository (e) tests — A1 은 단일 commit 권장 (기능적 단일성)
2. **A2 진입 전 ADR-0001 § 3 결정 4건**:
   - secretkey 정규식 보강 → 키움 자격증명 형식 (40~50자 영숫자) 매칭 가능 패턴 추가
   - KiwoomCredentials 직렬화 차단 → SecretStr 또는 `__reduce__` raise
   - raw_response 의 au10001 토큰 필드 제거 → UseCase 분기
   - 마스터키 회전 자동화 → `scripts/rotate_master_key.py` 초안
3. **A2 코드화 착수 합의** — endpoint-01-au10001.md + endpoint-02-au10002.md 기반:
   - `app/adapter/out/kiwoom/_client.py` (KiwoomClient 공통 트랜스포트)
   - `app/adapter/out/kiwoom/_exceptions.py` (5 예외: KiwoomCredentialRejectedError, KiwoomRateLimitedError, KiwoomUpstreamError, KiwoomBusinessError, KiwoomResponseValidationError)
   - `app/adapter/out/kiwoom/auth.py` (KiwoomAuthClient — issue_token / revoke_token)
   - `app/application/service/token_service.py` (IssueKiwoomTokenUseCase / RevokeKiwoomTokenUseCase / TokenManager)
   - `app/adapter/web/routers/auth.py` (POST /api/kiwoom/auth/tokens / DELETE /api/kiwoom/auth/tokens/{alias})
   - `app/main.py` (FastAPI app + lifespan + graceful shutdown)
   - 테스트: MockTransport 200/401/403/500/network_error + IssueKiwoomTokenUseCase 통합 + TokenManager 동시성

### A1 → A2 → A3 의존성 그래프

```
A1 (완료)
   Settings + Cipher + structlog + Migration 001 (kiwoom_credential / kiwoom_token / raw_response)
   + KiwoomCredentialRepository + DTO (KiwoomCredentials / IssuedToken / MaskedKiwoomCredentialView)
   ↓
A2 (다음)
   KiwoomClient (httpx + tenacity + Semaphore)
   + KiwoomAuthClient (au10001/au10002)
   + Issue/Revoke UseCase + TokenManager (메모리 캐시 + alias 별 asyncio.Lock)
   + auth router + lifespan graceful shutdown
   ↓
A3 (그 다음)
   KiwoomStkInfoClient (ka10101)
   + Migration 002 (sector 테이블) + SectorRepository + SyncSectorMasterUseCase
   + APScheduler weekly job (KST 일 03:00)
   ↓
B (Phase B 종목 마스터)
   ka10099 / ka10100 / ka10001 + nxt_enable + 일일 마스터 배치
```

## Files Modified This Session

```
신규 디렉토리:
src/backend_kiwoom/{app/*, migrations/versions, tests, scripts}
docs/ADR/

신규 파일 (38 코드 + 8 테스트 + 1 ADR + 1 CHANGELOG/HANDOFF 갱신):
src/backend_kiwoom/
├ pyproject.toml
├ alembic.ini
├ .env.example
├ Dockerfile
├ README.md
├ app/__init__.py
├ app/config/{__init__.py, settings.py}
├ app/security/{__init__.py, kiwoom_credential_cipher.py}
├ app/observability/{__init__.py, logging.py}
├ app/adapter/__init__.py
├ app/adapter/out/__init__.py
├ app/adapter/out/persistence/{__init__.py, base.py, session.py}
├ app/adapter/out/persistence/models/{__init__.py, credential.py, raw_response.py}
├ app/adapter/out/persistence/repositories/{__init__.py, _helpers.py, kiwoom_credential.py}
├ app/application/{__init__.py, dto/{__init__.py, kiwoom_auth.py}}
├ migrations/{env.py, script.py.mako}
├ migrations/versions/001_init_kiwoom_schema.py
└ tests/
   ├ __init__.py
   ├ conftest.py
   ├ test_kiwoom_credential_cipher.py
   ├ test_settings.py
   ├ test_logging_masking.py
   ├ test_kiwoom_auth_dto.py
   ├ test_models.py
   ├ test_kiwoom_credential_repository.py
   └ test_migration_001.py

docs/ADR/ADR-0001-backend-kiwoom-foundation.md  (신규)

기존 파일 갱신:
CHANGELOG.md   prepend
HANDOFF.md     overwrite (본 문서)
```

**0 commits (사용자 확인 대기), 38 코드 + 8 테스트 + 1 ADR + 2 갱신.**

### Context to Load (다음 세션 — A2 코드화 착수)

```
src/backend_kiwoom/docs/plans/master.md                    # 25 endpoint 카탈로그
src/backend_kiwoom/docs/plans/endpoint-01-au10001.md       # A2 — 토큰 발급
src/backend_kiwoom/docs/plans/endpoint-02-au10002.md       # A2 — 토큰 폐기
src/backend_kiwoom/SPEC.md                                  # (생성 예정 — 코드 진화에 따라)
src/backend_py/SPEC.md                                      # 패턴 reference
docs/ADR/ADR-0001-backend-kiwoom-foundation.md             # 본 세션 결정 + 미적용 4건
```

다음 세션 첫 명령 추천:
- (A) `A1 결과 커밋 + 푸시` → A2 진입 전 보안 정책 4건 결정
- (B) `ADR-0001 § 3 의 4건 즉시 처리 + A2 진입` → secretkey 정규식 / DTO 차단 / raw_response 분기 + 회전 스크립트
- (C) `A2 코드화 시작 (au10001/au10002)` → 보안 정책은 A2 코드 작성 중 병행
