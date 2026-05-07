# Session Handoff

> Last updated: 2026-05-07 (KST) — **backend_kiwoom Phase A2 사전 보안 PR 완료 (ted-run 풀 파이프라인 + 3-Round 적대적 이중 리뷰)**
> Branch: `master` (working tree dirty — 보안 강화 4 파일 + 1 신규 + ADR/CHANGELOG/HANDOFF 미커밋)
> Latest commit: `12f46aa` — feat(kiwoom): Phase A1 기반 인프라
> 세션 시작점: `12f46aa` 동일

## Current Status

`backend_kiwoom` **Phase A2 진입 전 사전 보안 PR 완료**. ADR-0001 § 3 미적용 4건 중 #1 (정규식 보강) / #2 (DTO 직렬화 차단) / #3 (raw_response 토큰 scrub) 적용. #4 (마스터키 회전 자동화) 는 Phase B 후반 지연. 외부 호출 0.

ted-run 풀 파이프라인 모든 게이트 통과 + 3-Round 적대적 이중 리뷰 사이클 완주. **CRITICAL 0건 / HIGH 0건 PASS**.

## Completed This Session (Phase A2 사전 보안 PR — 3-Round 사이클)

### Step 0: TDD (sonnet)

- 28개 회귀 테스트 작성 (red 확인 후 green)
- `tests/test_scrub.py` (신규) — 16 케이스
- `tests/test_kiwoom_auth_dto.py` — 6 케이스 추가 (직렬화 차단)
- `tests/test_logging_masking.py` — 6 케이스 추가 (정규식 보강)

### Step 1: 구현 (opus 메인)

- `app/security/scrub.py` (신규) — `scrub_token_fields(payload, api_id)` helper
- `app/observability/logging.py` — `_KIWOOM_SECRET_PATTERN` 추가 (`{40,50}` → `{16,1024}` → prefix-aware)
- `app/application/dto/kiwoom_auth.py` — `__reduce__`/`__reduce_ex__`/`__getstate__`/`__setstate__` raise + `__copy__`/`__deepcopy__` 명시

### Step 2 — Round 1 (CRITICAL 3 + HIGH 4 발견)

**2a (sonnet)**: HIGH 1건 (mypy LSP), MEDIUM 3건, LOW 3건
**2b (opus 적대적)**: CRITICAL 3건 + HIGH 4건 + MEDIUM 2건 + LOW 1건

CRITICAL 3건:
1. `__getstate__`/`__setstate__` 자동 생성으로 pickle 차단 우회 (Python 3.10+ slots dataclass)
2. secret 정규식 `{40,50}` 이 키움 16~256자 / token 20~1000자 미커버
3. au10002 의 appkey/secretkey 평문 통과 — `_TOKEN_FIELDS_BY_API` 가 token 만 등록

HIGH 4건: api_id 정규화·fail-closed (1) / case-insensitive 키 비교 (2) / 패턴 적용 순서 (3, 별도 PR) / deny-list → allow-list (4, 별도 PR)

### Step 1.5 — CRITICAL 3 + HIGH 1·2 수정 (사용자 결정)

- `__getstate__`/`__setstate__` raise 추가
- 정규식 `\b[A-Za-z0-9+/]{16,1024}\b` 로 확장
- `_TOKEN_FIELDS_BY_API["au10002"]` 에 `appkey`, `secretkey` 추가
- api_id `.strip().lower()` 정규화 + 인증 endpoint(au*) 미등록 시 ValueError fail-closed
- key 매칭 case-insensitive (`.lower()`)
- `__deepcopy__` 의 `memo[id(self)] = result` 갱신 (MEDIUM 동시 처리)

### Step 2 — Round 2 (HIGH-A 신규 발견)

**2a' (sonnet)**: PASS — 1차 수정 모두 정상
**2b' (opus 적대적)**: CONDITIONAL PASS — HIGH-A 신규 발견

HIGH-A: 정규식 `\b[A-Za-z0-9+/]{16,1024}\b` 가 운영 식별자 광범위 false positive
- trace_id 32자 hex / correlation_id / PascalCase 클래스명 / build_id / user_id 모두 마스킹
- 분산 트레이싱·로그 상관 분석 불가 — 운영 디버깅 즉시 마비

### Step 1.6 — HIGH-A prefix-aware 수정 (사용자 결정: 옵션 1)

```python
_KIWOOM_SECRET_PATTERN = re.compile(
    r"(\b(?:secretkey|secret_key|secret|appkey|app_key|access_token|refresh_token|token|password)"
    r"\s*[:=]\s*)[A-Za-z0-9+/]{16,1024}\b",
    re.IGNORECASE,
)
```

- `_scrub_string` 의 sub 호출이 group 1 (prefix+separator) 보존 + value 만 `[MASKED_SECRET]` 치환
- 회귀 테스트 +14 (prefix 매칭 7 + 운영 식별자 보존 7)

### Step 2 — Round 3 (PASS)

**2b'' (opus 적대적)**: PASS — CRITICAL 0 / HIGH 0
- MEDIUM 1건 (`client_secret`/`bearer`/`apikey` 미포함, 별도 PR)
- LOW 1건 (한국어/자연어 prefix 변형, caller 책임 영역, CI grep 룰 별도 PR 권장)

### Step 3: Verification 5관문 (PASS)

- 3-1 컴파일 import smoke OK
- 3-2 ruff 0 / mypy strict 0 (이번 PR 변경분 + 전체 app/)
- 3-3 **161 passed** (이전 117 → +44) / **coverage 94.94%**
- 3-4 bandit 0 (B105 `_MASKED_SECRET` nosec) / pip-audit 0 CVE
- 3-5 마이그레이션 변경 없음 (skip)

### Step 4: E2E

자동 생략 — 백엔드 전용 + UI 변경 없음.

### Step 5: ADR + 커밋 (진행 중)

- `docs/ADR/ADR-0001-backend-kiwoom-foundation.md` § 3 갱신 — #1·#2·#3 적용 기록 + § 3.1·3.2·3.3·3.4 상세 + § 5 후속 PR 권장
- `CHANGELOG.md` prepend
- `HANDOFF.md` overwrite (본 문서)
- 커밋 대기 (사용자 확인 후 진행)

## In Progress / Pending

| # | 항목 | 상태 | Notes |
|---|------|------|-------|
| 1 | **본 세션 결과 커밋** (보안 PR + ADR/CHANGELOG/HANDOFF) | ⏳ 사용자 대기 | 한글 메시지 + Co-Authored-By |
| 2 | **푸시** | ⏳ 별도 확인 | 글로벌 CLAUDE.md 규칙 |
| 3 | **Phase A2 코드화** | 🟡 다음 세션 | KiwoomClient 공통 트랜스포트 + KiwoomAuthClient (au10001/au10002) + Issue/Revoke UseCase + TokenManager + auth router + lifespan |
| 4 | **별도 PR 후속 5건** | 🟢 우선순위 정리 | `_KIWOOM_SECRET_PATTERN` 화이트리스트 확장 / `_TOKEN_FIELDS_BY_API` allow-list / SQLAlchemy event listener / CI grep 룰 / 자잘한 정리 |

## Key Decisions Made (본 세션)

### 보안 강화 PR 의 chunk 분할 결정 (사용자 합의)

1. **사전 PR (본 세션)**: ADR-0001 § 3 #1·#2·#3 만 처리. #4 는 Phase B 후반 지연.
2. **A2 진입 시점**: 본 PR 머지 후, 다음 세션에서 KiwoomClient + au10001/au10002 코드화 시작.
3. **HIGH-3 (정규식 적용 순서) / HIGH-4 (deny-list → allow-list)**: 본 PR 범위 외, 별도 PR.

### 적대적 리뷰 우선 정책

- 보안 민감 분류 → 2b (적대적) 강제 ON
- CRITICAL/HIGH 발견 시 즉시 수정 + Round 재실행 (R1 → R2 → R3)
- MEDIUM/LOW 는 별도 PR — 운영 영향과 PR 크기 trade-off

### prefix-aware 정규식 채택 (R3)

- charset 확장만으로는 운영 식별자 false positive 불가피
- 1차 방어 (dict 키 매칭) 가 운영 코드 80% 처리 → 정규식은 f-string 평문 prefix 명시 시 보조 안전망 sweet spot
- 한국어/자연어 prefix 변형은 정규식 한계로 수용, CI grep 룰로 caller 책임 강제 권장

### Known Limitations (ADR § 3 명시)

- `copyreg.dispatch_table[KiwoomCredentials]` 등록 시 type-level 우회 (Python pickle 본질). 코드 리뷰에서 차단.
- `object.__getstate__(creds)` 직접 호출 (Python 3.11+) 우회. 외부 디버거/프로파일러 영역.
- `startswith("au")` 가정 — 키움이 `oauth_token` 등 다른 prefix 인증 endpoint 추가 시 누락 위험. allow-list 전환 별도 PR.
- helper 호출 강제 메커니즘 부재. SQLAlchemy event listener 별도 PR.

## Files Modified This Session

```
신규:
src/backend_kiwoom/app/security/scrub.py
src/backend_kiwoom/tests/test_scrub.py

변경:
src/backend_kiwoom/app/observability/logging.py
src/backend_kiwoom/app/application/dto/kiwoom_auth.py
src/backend_kiwoom/tests/test_kiwoom_auth_dto.py
src/backend_kiwoom/tests/test_logging_masking.py
docs/ADR/ADR-0001-backend-kiwoom-foundation.md
CHANGELOG.md
HANDOFF.md
```

## Context for Next Session

### 사용자의 원 목적 (본 세션 흐름)

세션 시작 명령: `/ted-run 보안 PR — ADR-0001 § 3 #1·#2·#3 사전작업`. 이전 세션 (Phase A1 코드화) 의 후속으로 Phase A2 진입 전 보안 사각지대 차단.

수행 흐름:
1. **자동 분류** — 보안 민감 (security 키워드 + scrub/credential/token 도메인). 게이트 0/2a/2b/3-1~3-4 모두 ON, 3-5/4 자동 생략
2. **Step 0 TDD** — 28 케이스 작성 (red 확인)
3. **Step 1 구현** — 4 파일 변경 + 1 신규
4. **R1 이중 리뷰** — CRITICAL 3 + HIGH 4 발견 → 사용자 결정 (CRITICAL 3 + HIGH 1·2 수정)
5. **R2 재리뷰** — HIGH-A 신규 발견 → 사용자 결정 (옵션 1: prefix-aware)
6. **R3 적대적 재리뷰** — PASS
7. **Step 3 Verification** — 5관문 모두 통과
8. **Step 5 Ship** — ADR + CHANGELOG + HANDOFF + 커밋 대기

### 선택한 접근과 이유

- **사전 보안 PR 분리**: A2 진입 전에 보안 사각지대 차단 — 코드 작성 시점에 결정 비용 가장 낮음 (ADR-0001 § 3)
- **3-Round 적대적 이중 리뷰**: 보안 민감 분류 강제 정책. 매 round 마다 신규 발견 → 1회만에 종료 안 되는 게 정상
- **prefix-aware 정규식**: 1차 방어 (dict 키) + 2차 방어 (정규식) 의 sweet spot. 운영 노이즈 vs 보안 trade-off 명확화
- **chunk 분리 (HIGH-3·4 별도 PR)**: 단일 PR 비대화 방지, allow-list 전환은 설계 변경이라 독립

### 사용자 선호·제약 (재확인)

- **한국어 커밋 메시지 + Co-Authored-By** (전역 CLAUDE.md)
- **`git push` 명시 요청 시에만** — 커밋 후 푸시 별도 확인
- **선택지 제시 후 사용자 결정** — chunk/options 모두 명시 합의 후 진행
- **체크리스트 + 한 줄 현황** (memory: feedback_progress_visibility) — TaskCreate 9 단계 사용
- **이중 리뷰 라운드별 사용자 결정** — CRITICAL 발견 시 처리 방향 묻기

### 다음 세션에서 먼저 확인할 것

1. **본 세션 결과 커밋**:
   - 추천: 단일 커밋 — `security(kiwoom): Phase A2 사전 보안 PR — ADR-0001 § 3 #1·#2·#3 적용 (3-Round 이중 리뷰, 161 tests / 94.94%)`
   - 또는 분리: (a) 기능 코드 (b) 테스트 (c) ADR/CHANGELOG/HANDOFF — 단일 commit 권장 (기능적 단일성)
2. **Phase A2 코드화 착수** — endpoint-01-au10001.md + endpoint-02-au10002.md 기반:
   - `app/adapter/out/kiwoom/_client.py` (KiwoomClient 공통 트랜스포트)
   - `app/adapter/out/kiwoom/_exceptions.py` (5 예외)
   - `app/adapter/out/kiwoom/auth.py` (KiwoomAuthClient — issue_token / revoke_token)
   - `app/application/service/token_service.py` (Issue/Revoke UseCase + TokenManager)
   - `app/adapter/web/routers/auth.py` (POST/DELETE)
   - `app/main.py` (FastAPI app + lifespan)
   - 테스트: MockTransport 200/401/403/500 + UseCase 통합 + TokenManager 동시성
3. **A2 의 첫 호출 시점에 운영 검증 1순위** — endpoint-01-au10001.md DoD § 10.3:
   - expires_dt timezone 가정 검증 (KST 9시간 오차 위험)
   - authorization 헤더 빈/생략 시 키움 응답 형식
   - 401/403 동작 차이

### A1 → A2 → A3 의존성 그래프 (재확인)

```
A1 (완료, 12f46aa)
   Settings + Cipher + structlog + Migration 001 + KiwoomCredentialRepository + DTO
   ↓
[보안 사전 PR — 본 세션, 미커밋]
   _KIWOOM_SECRET_PATTERN (prefix-aware) + KiwoomCredentials 직렬화 차단 + scrub_token_fields helper
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
```

## Verification Summary

```
Tests:     161 passed (이전 117 → +44)
Coverage:  94.94% (목표 80% 초과)
Lint:      ruff 0 / mypy strict 0
Security:  bandit 0 (B105 nosec) / pip-audit 0 CVE
Migration: 본 PR 변경 없음 (skip)
E2E:       자동 생략 (백엔드 전용 + UI 변경 없음)
Reviews:   3-Round 이중 리뷰 (sonnet 일반품질 + opus 적대적), 최종 CRITICAL 0 / HIGH 0
```
