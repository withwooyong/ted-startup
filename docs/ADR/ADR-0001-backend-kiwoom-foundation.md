# ADR-0001 — backend_kiwoom 기반 인프라 (Phase A1)

> **Status**: Accepted
> **Date**: 2026-05-07
> **Deciders**: Ted (single-engineer)
> **Context**: 키움 OpenAPI 25 endpoint 호출 백엔드 신규 구축의 첫 코드화 chunk

## 1. 컨텍스트

`backend_py` 가 KRX 익명 차단 (2026-04~) 으로 데이터 수집 불안정. NXT 거래가도 부재. 이를 해결하려 키움 OpenAPI 를 **독립 출처**로 호출하는 새 백엔드 (`src/backend_kiwoom/`) 를 구축. 25 endpoint 계획서 100% 완성 (직전 세션) 이후 첫 코드화 chunk = **Phase A1 (기반 인프라)**.

A1 범위: 외부 호출 0. Settings + Cipher + structlog + Migration 001 + Repository.

## 2. 핵심 결정

### 2.1 스택 — backend_py 와 동일

| 영역 | 선택 | 근거 |
|------|------|------|
| 언어 | Python 3.12+ | backend_py 동일 — 학습 비용 0 |
| 웹 | FastAPI 0.115+ | (A2~ 사용) |
| ORM | SQLAlchemy 2.0 (asyncpg 런타임 / psycopg2 마이그레이션) | asyncpg 다중 statement 미지원 회피 |
| Pydantic | v2 | strict typing |
| HTTP | httpx + tenacity | (A2~ 사용) |
| 배치 | APScheduler | (A3~ 사용) |
| 패키지 | uv lock | 재현성 |
| 로깅 | structlog + 자동 마스킹 | backend_py PR 6 패턴 복제 |
| 암호화 | cryptography Fernet | KIS 자격증명 처리 패턴 복제 |
| 테스트 | pytest + testcontainers PG16 | 외부 호출 0 |

### 2.2 코드 의존성 — backend_py 미import

`backend_py.app.*` 0 import. **패턴만 복제**, 클래스/모듈 신규 작성. 두 백엔드 독립 배포 가능 + 영향 범위 격리.

### 2.3 DB 분리 — `kiwoom` 스키마

같은 PG 인스턴스 + 별도 schema (`kiwoom`). backend_py 의 default schema (`public`) 와 격리. Alembic `version_table_schema="kiwoom"` 로 마이그레이션 이력 분리.

### 2.4 자격증명 보안 — Fernet 대칭 + 마스터키 fail-fast

- `kiwoom_credential.appkey_cipher` / `secretkey_cipher` BYTEA — 평문 저장 금지
- `KIWOOM_CREDENTIAL_MASTER_KEY` env 빈값 → `MasterKeyNotConfiguredError` (앱 기동 차단)
- `key_version` 다중 관리로 회전 대비 (현재 v1)
- 예외 메시지에 ciphertext / plaintext 포함 금지 — `key_version` 만 노출
- Repository 가 cipher 를 생성자 주입 → 회전 시점에 인스턴스만 교체

### 2.5 로깅 마스킹 — 2층 방어

**1층 (키 매칭)**: `appkey`, `secretkey`, `kiwoom_credential_master_key`, `token`, `authorization`, `admin_api_key` 등 SENSITIVE_KEYS + `_master_key`/`_secret`/`_app_secret`/`_credential` 등 SUFFIXES → `[MASKED]` 자동 치환.

**2층 (정규식 scrub)**: JWT 3-segment (`eyJ...`) + 40+hex 패턴 → `[MASKED_JWT]` / `[MASKED_HEX]`.

structlog `mask_sensitive` processor + stdlib `logging` foreign_pre_chain 통합 → `logging.getLogger(__name__).info()` 호출도 자동 마스킹.

`_scan` 은 dict/list/tuple/set/frozenset/str 재귀. 사용자 정의 객체 (Pydantic model 등) 는 통과 — DTO 는 `__repr__` 마스킹 책임.

### 2.6 Migration 001 — 3 테이블

1. `kiwoom_credential` — alias UNIQUE + env CHECK ('prod'|'mock') + BYTEA cipher 컬럼
2. `kiwoom_token` — credential_id UNIQUE (자격증명당 활성 토큰 1) + CASCADE delete
3. `raw_response` — JSONB request/response payload (재처리·디버깅, 90일 retention 권장)

downgrade 안전판: `kiwoom_credential` row 0 보장. 데이터 보존 시 `RAISE EXCEPTION`.

### 2.7 IssuedToken — tz-aware 강제

`__post_init__` 에서 `expires_at.tzinfo is None` → `ValueError`. 키움 응답 `expires_dt` 가 KST 문자열이라 파싱 시 tzinfo 누락 시 만료 판정 9시간 오차 위험 차단.

## 3. 의도적으로 미적용 (Phase B 진입 전 결정) — **2026-05-07 후속 PR 에서 #1·#2·#3 적용 완료**

| 항목 | 사유 | 결정 시점 | 상태 |
|------|------|-----------|------|
| **secretkey 정규식 보강 (#1)** | 키움 secretkey 형식이 JWT/40+hex 패턴에 매칭 안 됨. f-string 으로 평문 logger 삽입 시 키 매칭 우회 가능 | A2 진입 전 | ✅ **적용** — `_KIWOOM_SECRET_PATTERN` prefix-aware 매칭 도입 (§ 3.1) |
| **DTO 직렬화 우회 방어 (#2)** | `dataclasses.asdict(creds)` / `pickle.dumps(creds)` / `__getstate__()` 등 직렬화 경로 secretkey 평문 노출 위험 | A2 진입 전 | ✅ **적용** — `__reduce__`/`__reduce_ex__`/`__getstate__`/`__setstate__` raise (§ 3.2) |
| **raw_response 토큰 평문 저장 차단 (#3)** | au10001/au10002 응답·요청 본문이 raw_response JSONB 에 평문 저장 위험 | A2 진입 전 | ✅ **적용** — `app/security/scrub.py` 의 `scrub_token_fields(payload, api_id)` helper (§ 3.3) |
| **마스터키 회전 자동화 (#4)** | `_fernets[2] = Fernet(new_key)` 다중 버전 구조는 있지만 실제 회전 마이그레이션 스크립트 부재 | Phase B 후반 | ⏸️ **지연** — 운영 자격증명 발급 후 회전 시점에 결정 (§ 3.4) |
| **assert → raise 적용** | A1 에서 `upsert` 에 적용 완료. 다른 경로는 발견 시 적용 | 발견 시 즉시 | ✅ A1 적용 |

### 3.1 secretkey 정규식 prefix-aware 매칭 (#1 적용 — 2026-05-07)

**최종 형태** (`app/observability/logging.py`):

```python
_KIWOOM_SECRET_PATTERN = re.compile(
    r"(\b(?:secretkey|secret_key|secret|appkey|app_key|access_token|refresh_token|token|password)"
    r"\s*[:=]\s*)[A-Za-z0-9+/]{16,1024}\b",
    re.IGNORECASE,
)
```

**진화 과정** (3-Round 적대적 리뷰 사이클):
1. **Round 1 초기**: `\b[A-Za-z0-9]{40,50}\b` — 키움 secretkey 16~256자 / token 20~1000자 미커버 (CRITICAL-2 발견)
2. **Round 2 확장**: `\b[A-Za-z0-9+/]{16,1024}\b` — 길이/charset 확장. 그러나 trace_id/correlation_id/PascalCase 운영 식별자 광범위 false positive (HIGH-A 발견)
3. **Round 3 prefix-aware**: `secretkey=value` 등 명시 prefix 뒤 value 만 매칭. 운영 식별자 보존 + secret/token 평문 보호 양립

**1차 방어**: dict 키 매칭 (`SENSITIVE_KEYS`). dict 형태 logger 호출은 자동 마스킹 — 운영 코드 80% 처리.
**2차 방어 (본 정규식)**: f-string 평문 prefix 명시 시 보조 안전망.

**Known Limitations** (별도 PR 권장):
- 한국어 prefix (`f"키 {value}"`) / 자연어 변형 (`f"secret is {x}"`) 미매칭 — CI grep 룰로 caller 측 책임 강제 권장
- `client_secret`/`bearer`/`apikey`/`private_key` 등 OAuth 표준 prefix 미포함 — 1차 방어가 커버 중. 별도 PR 에서 화이트리스트 확장

### 3.2 KiwoomCredentials 직렬화 차단 (#2 적용 — 2026-05-07)

**다층 방어** (`app/application/dto/kiwoom_auth.py`):

| 메서드 | 동작 | 차단 대상 |
|--------|------|-----------|
| `__reduce__` | TypeError raise | pickle.dumps (서브클래스 fallback) |
| `__reduce_ex__` | TypeError raise | pickle.dumps |
| `__getstate__` | TypeError raise | jsonpickle/dill/cloudpickle 우회 (Python 3.10+ slots dataclass 자동 생성) |
| `__setstate__` | TypeError raise | 역직렬화 경로 객체 재구성 |
| `__copy__` / `__deepcopy__` | 정상 작동 | 도메인 내부 복제 허용 (`memo[id(self)] = result` 갱신) |
| slots=True | `vars(creds)` TypeError | `__dict__` 자연 차단 |

`dataclasses.asdict(creds)` 는 호출 가능 — 결과를 logger 로 흘리면 `_scan` 의 `secretkey` 키 매칭으로 [MASKED] 처리. 2층 방어.

**Known Limitations**:
- `copyreg.dispatch_table[KiwoomCredentials] = ...` 등록 시 type-level 우회 가능 (Python pickle 본질적 한계). 운영 코드의 의도적 등록은 코드 리뷰에서 차단. 회귀 표시 테스트 `test_kiwoom_credentials_copyreg_dispatch_table_known_limitation` 로 명시.
- `object.__getstate__(creds)` 직접 호출 (Python 3.11+ 의 default `__getstate__`) 우회. 외부 디버거/프로파일러 영역 — 본 PR 책임 영역 외.

### 3.3 raw_response 토큰 scrub helper (#3 적용 — 2026-05-07)

**`app/security/scrub.py`** — `scrub_token_fields(payload, api_id) → dict`

| 동작 | 설계 |
|------|------|
| 화이트리스트 | au10001 → {token, expires_dt}, au10002 → {token, **appkey, secretkey**} |
| api_id 정규화 | `.strip().lower()` — `AU10001`/`au10001 ` 등 동일 처리 |
| 인증 endpoint 미등록 | ValueError raise (fail-closed) — caller 오타·신규 endpoint 누락 차단 |
| 비인증 (`ka*` 등) | 통과 — token 키 의미 다를 수 있음 |
| key 매칭 | case-insensitive (`Token`/`TOKEN` 우회 방어) |
| 원본 보존 | 새 dict 반환 — caller 가 token 다른 경로 사용 가능 |
| 치환 형태 | `[SCRUBBED]` (필드 삭제 X) — 디버깅 시 "있었음" 확인 가능 |

**au10002 의 핵심**: revoke request body 에 appkey/secretkey/token **모두 평문 포함** (계획서 endpoint-02-au10002.md § 3.1) — Fernet 으로 암호화된 `kiwoom_credential` 의 보호가 raw_response JSONB 평문 저장으로 무력화되는 사각지대 차단. 적대적 리뷰 R1 의 CRITICAL-3 발견.

**Known Limitations** (별도 PR 권장):
- `startswith("au")` 가정 — 키움이 향후 `oauth_token` 등 다른 prefix 인증 endpoint 추가 시 누락 위험. allow-list 전환은 별도 PR (R1 의 HIGH-4).
- helper 호출 강제 메커니즘 부재 — UseCase 가 호출 누락 시 평문 저장. SQLAlchemy `before_insert` event listener 추가는 별도 PR.

### 3.4 마스터키 회전 자동화 (#4 지연 — Phase B 후반)

**현황**: `_fernets[v]` 다중 버전 구조는 있지만 실제 회전 미구현.
**지연 사유**: 운영 자격증명 미발급 단계라 회전 시나리오 검증 어려움. Phase B 종목 마스터 적재 완료 + 운영 키움 자격증명 발급 후 회전 시점에 결정.

## 4. 결과

### Phase A1 초기 (2026-05-07, commit 12f46aa)
- 38 파일 / ~1,500줄 (테스트 ~600줄 포함)
- 테스트 117 passed / coverage 94.61% (목표 80% 초과)
- ruff lint 0 / mypy strict 0 / bandit 0 / pip-audit 0 CVE
- alembic upgrade/downgrade 양방향 검증

### Phase A2 사전 보안 PR (2026-05-07, 후속 커밋)
- 4 파일 (logging/kiwoom_auth/scrub) 변경 + 1 파일 신규 (`app/security/scrub.py`)
- 회귀 테스트 +44 (28 + 16) → **161 passed / coverage 94.94%**
- 3-Round 적대적 리뷰 사이클 통과 — CRITICAL 0 / HIGH 0
- ruff lint 0 / mypy strict 0 / bandit 0 (B105 nosec 1) / pip-audit 0 CVE

## 5. 다음 chunk

A2 — KiwoomClient 공통 트랜스포트 + KiwoomAuthClient (au10001/au10002) + IssueKiwoomToken/RevokeKiwoomToken UseCase + TokenManager + auth router + lifespan graceful shutdown.

본 ADR § 3 미적용 4건 중 #1·#2·#3 은 본 PR 에서 적용 완료. #4 (마스터키 회전 자동화) 는 Phase B 후반.

별도 후속 PR 권장 (보안 강화 PR 의 R1·R2·R3 리뷰 발견):
1. `_KIWOOM_SECRET_PATTERN` 화이트리스트 확장 (`client_secret`/`bearer`/`apikey`/`private_key`)
2. `_TOKEN_FIELDS_BY_API` allow-list 전환 (deny-list → allow-list, R1 HIGH-4)
3. SQLAlchemy `before_insert` event listener 로 raw_response scrub 자동 적용
4. CI grep 룰 — f-string 내 평문 secret/token 삽입 PR 차단
5. 자잘한 정리 — deepcopy memo 변조 방어, `expires_dt` 마스킹, `_capture_stdlib_log` 헬퍼 IndexError 가드

---

## 6. Phase A2-α — au10001 발급 경로 (2026-05-07)

### 6.1 결정

**A2 chunk 분할** — α (issue) 먼저, β (revoke + lifespan graceful shutdown) 별도 PR. 이유:
- 작업계획서 1,212줄 (au10001 626 + au10002 586) + 인프라 7~10 신규 파일 + 테스트 4 신규 → 단일 PR 시 리뷰 부담 과다
- 발급 경로만으로 운영 dry-run (DoD § 10.3 — expires_dt timezone 등) 검증 가능
- β 의 graceful shutdown 은 lifespan 에 hook 만 추가 — α 토큰 발급 검증 후 빠르게 적층

### 6.2 핵심 설계 결정

| # | 항목 | 결정 | 이유 |
|---|------|------|------|
| 1 | 401/403 재시도 | **금지** | 자격증명 무차별 시도 timing leak 방어 (계획 §11.2) |
| 2 | 429 재시도 | **금지** | 적대적 리뷰 H3 — RPS overrun + 자격증명 wrong key 가 같은 응답 → timing oracle |
| 3 | tenacity retry 대상 | KiwoomUpstreamError 만 (5xx + 네트워크 + 파싱) | 4xx 는 즉시 fail-fast |
| 4 | 토큰 캐시 | 메모리 only (`TokenManager`) | MVP 단일 워커. 다중 워커는 Phase H 결정 |
| 5 | alias 별 동시 발급 합체 | `asyncio.Lock` + `dict.setdefault` (atomic) | defaultdict race 회피 (적대적 리뷰 H2) |
| 6 | `TokenManager.max_aliases` | 1024 (default) | 적대적 리뷰 H1 — alias 폭증 lock proliferation DoS 방어 |
| 7 | 무효 alias lock cleanup | 즉시 정리 | H1 — `CredentialNotFoundError` 발생 시 `_locks.pop(alias)` |
| 8 | 세션 라이프사이클 | TokenManager 가 `session_provider` 주입 받아 매 발급 시 open + close | 적대적 리뷰 H4 — DB 풀 누수 차단 |
| 9 | DB 쿼리 횟수 | `find_by_alias` + `decrypt_row` 1쿼리 | 1차 리뷰 HIGH — 이중 SELECT 회귀 차단 |
| 10 | Pydantic ValidationError cause chain | `from None` | 적대적 리뷰 H5 — `ValidationError.input` 에 토큰 평문 보존 → cause 노출 차단 |
| 11 | KiwoomBusinessError 메시지 | `super().__init__` 에 `message` 미포함 (attribute only) | 적대적 리뷰 M1 — Kiwoom `return_msg` attacker-influenced 누설 차단 |
| 12 | expires_dt 잘못된 날짜 | `expires_at_kst()` 가 `KiwoomResponseValidationError` 매핑 | M2 — 라우터 500 stack trace 노출 방어 |
| 13 | 응답 토큰 마스킹 | `mask_token` (tail 6, 25% cap) | L1 — 짧은 opaque 토큰 fallback 도 안전 |
| 14 | 응답 expires_at 정밀도 | 분 단위 절단 | M5 — 발급 시각 fingerprint 차단 |
| 15 | admin guard | `hmac.compare_digest` + `admin_api_key=""` fail-closed | timing-safe + 운영 실수 방어 |
| 16 | 라우터 detail | alias / appkey / `return_msg` 평문 미포함 | M1 — HTTPException detail 비식별화 |

### 6.3 결과

- 신규 파일 8개 (코드) + 4개 (테스트, 1개 기존 확장)
- 테스트 +43 → **204 passed / coverage 88.07%** (이전 161)
- 이중 리뷰 사이클 1라운드 — CRITICAL 0 / HIGH 0 (적용 후)
- ruff lint 0 / mypy strict 0 (app + new tests) / bandit 0 / pip-audit 0 CVE
- 5관문 verification 통과 (compile / static / test / security / runtime smoke)

### 6.4 운영 검증 보류 (β 시점에 일괄)

DoD § 10.3 (운영 dry-run 필요) — α 단독 시점에 미수행:
- [ ] `expires_dt` timezone (KST/UTC)
- [ ] `authorization` 헤더 빈 문자열 vs 생략
- [ ] DEBUG 로그로 응답 본문 확인 → JWT/hex/Kiwoom 평문 토큰 마스킹 회귀 검증
- [ ] 자격증명 1쌍 등록 후 실제 토큰 발급/폐기 (β 와 함께)

**β chunk 작업**: au10002 + lifespan graceful shutdown + RevokeKiwoomTokenUseCase + DELETE/POST 폐기 라우터 + revoke-by-raw-token + audit 로그 + 운영 dry-run.

---

## 7. Phase A2-β — au10002 폐기 + lifespan graceful shutdown (2026-05-07)

### 7.1 결정

α (issue) 의 베이스라인 위에 폐기 + 종료 위생을 적층. β 단독으로 운영 dry-run 가능 (α + β 합쳐 전체 토큰 라이프사이클 검증).

### 7.2 핵심 설계 결정

| # | 항목 | 결정 | 이유 |
|---|------|------|------|
| 1 | revoke 재시도 | **0회** | best-effort. 키움이 멱등성 미보장 — 자동 재시도 시 "이미 폐기됨" 응답 동작 모호 |
| 2 | 401/403 → idempotent 변환 | `RevokeResult(revoked=False, reason='already-expired'`) | 이미 만료/폐기된 토큰 폐기 시도는 정상 운영 시나리오 |
| 3 | revoke_by_raw_token 401 변환 | `reason='already-expired-raw'` | 적대적 리뷰 H-2/M-5 — α 의 idempotency 와 일관성 |
| 4 | cache miss 시 동작 | adapter 호출 0 + `reason='cache-miss'` 반환 | 키움 측 폐기 부담 최소화 |
| 5 | revoke_by_raw_token 캐시 무효화 시점 | method 시작 직후 (decrypt 전) | 적대적 리뷰 M-1 — decrypt 실패 시에도 캐시 비움 보장 |
| 6 | lifespan shutdown 타임아웃 | 글로벌 20초 (`asyncio.wait_for`) | 적대적 리뷰 H-3 — k8s SIGKILL 30초 grace 전 마진 |
| 7 | shutdown timeout/cancel 시 | `manager.invalidate_all()` + engine.dispose() 보장 | finally 분리로 dispose 도달 보장 |
| 8 | shutdown 처리 순서 | 활성 alias 별 polling → 실패해도 진행 → invalidate_all → engine.dispose | best-effort + 자원 정리 우선 |
| 9 | `KiwoomRateLimitedError` 라우터 매핑 | 503 (issue + revoke 둘 다) | 적대적 리뷰 H-1 — 이전엔 fallback 500 (α 라우터에도 동일 누락이라 함께 패치) |
| 10 | revoke 라우터 except tuple | 6개 명시 (`KiwoomCredentialRejectedError` / `KiwoomRateLimitedError` 포함) | 모든 도메인 예외 명시 매핑 + fallback 500 미사용 |
| 11 | `RevokeRawTokenRequest` Pydantic 검증 | `extra='forbid'` + token `Field(min_length=20, max_length=1000)` | wire 직전 형식 강제 |
| 12 | 422 응답 input 스크럽 | `app.exception_handler(RequestValidationError)` + sensitive paths 화이트리스트 | **적대적 리뷰 C-1 — `/revoke-raw` 422 응답이 token 평문 echo (Pydantic ValidationError input)** |
| 13 | sensitive paths 정의 | `frozenset({"/api/kiwoom/auth/tokens/revoke-raw"})` 모듈 상수 | 다른 토큰 입력 라우터 추가 시 명시 등록 강제 |
| 14 | 응답 detail 비식별화 | `_map_revoke_exception` 일관 — alias / `return_msg` / token 평문 미포함 | M1 일관 적용 |
| 15 | TokenManager 확장 | `peek` (만료 무관 캐시 조회) / `alias_keys` (snapshot tuple) / `invalidate_all` (전체 비움) | β 라우터 + shutdown hook 진입점 |
| 16 | revoke_all_aliases_best_effort | 함수형 helper — manager + revoke_uc 주입 | lifespan / 운영 사고 대응 / 테스트 모두에서 재사용 |

### 7.3 결과

- 신규 파일 1개 (테스트 `test_lifespan.py`) + 기존 6 파일 확장
- 테스트 +35 → **239 passed / coverage 89.95%** (이전 204)
- 이중 리뷰 사이클 1라운드 — **CRITICAL 1 (C-1) + HIGH 4 + MEDIUM 5** 발견 → 전부 적용 → CRITICAL/HIGH 0 PASS
- ruff lint 0 / mypy strict 0 (app + new tests) / bandit 0 / pip-audit 0 CVE
- 5관문 verification 통과 (lifespan 라우트 등록 + C-1 핸들러 등록 검증)

### 7.4 운영 dry-run 보류

A2 (α + β) 코드 완료. 운영 키움 자격증명 1쌍 등록 후 별도 작업으로 진행 (DoD § 10.3 일괄):
- [ ] `expires_dt` timezone 확정 (KST/UTC)
- [ ] `authorization` 헤더 빈 문자열 vs 생략
- [ ] 401/403 동작 차이
- [ ] 같은 토큰 2회 폐기 멱등성 응답 (200/401/return_code)
- [ ] DEBUG 로그로 응답 본문 검증 → 평문 누설 회귀

### 7.5 별도 후속 PR 권장 (β 적대적 리뷰 follow-up 5건)

A2-β 적대적 리뷰의 FOLLOW-UP — defer-able:

| # | 항목 | 출처 |
|---|------|------|
| F1 | pre-commit grep 가드 — `model_dump` + `logger` 같은 줄 금지 (β body plaintext 회귀 방어) | β 적대적 |
| F2 | `/revoke-raw` 라우터 rate-limiting (`slowapi` per-admin-key) | β 적대적 H-2 |
| F3 | `TokenManager.frozen` 플래그 — shutdown 중 신규 발급 차단 | β 적대적 M-3 |
| F4 | `RevokeRawTokenRequest.token` `Field(pattern=r"^[A-Za-z0-9+/]+$")` 추가 | β 적대적 F-4 |
| F5 | shutdown metric (`kiwoom_shutdown_revoke_attempts_total`) | β 적대적 F-5 |

**다음 chunk**: A3 — KiwoomStkInfoClient (ka10101) + Migration 002 (sector 테이블) + SectorRepository + SyncSectorMasterUseCase + APScheduler weekly job.

---

## 8. Phase A3-α — KiwoomClient 공통 트랜스포트 + KiwoomStkInfoClient (ka10101) (2026-05-07)

### 8.1 결정

A3 chunk 분할: α (KiwoomClient + ka10101 어댑터 단위) → β (Migration 002 + Repository + UseCase + 라우터) → γ (APScheduler weekly cron) 별도 PR. KiwoomClient 가 모든 후속 endpoint(B~G 22개)의 기반이라 단독 검증 후 적층.

### 8.2 핵심 설계 결정

| # | 항목 | 결정 | 이유 |
|---|------|------|------|
| 1 | 토큰 캐시 책임 | `token_provider: Callable[[], Awaitable[str]]` 의존성 주입 | KiwoomClient 는 stateless — TokenManager 가 캐시 책임 (의존성 역전) |
| 2 | token_provider 호출 빈도 | 매 호출마다 호출 | provider 가 캐시 hit 시 fast path. KiwoomClient 가 stale 토큰 캐시 안 함 |
| 3 | Semaphore 의도 | N 동시 in-flight + 1/N RPS | 4 동시 + 250ms 인터벌 = 4 RPS (키움 공식 5 RPS 안전 마진) |
| 4 | `_throttle` lock 정책 | lock 안에서 `_next_slot_ts` atomic 갱신만, sleep 은 lock 밖 | 적대적 리뷰 H2 — 4 코루틴이 0/250/500/750ms 분산 sleep, 의도된 동시성 보장 |
| 5 | tenacity 재시도 대상 | KiwoomUpstreamError + KiwoomRateLimitedError | 401/403/4xx/Pydantic 즉시 fail (α 정책 일관) |
| 6 | 401/403 정책 | 재시도 X | timing leak 방어 (α 정책) |
| 7 | 429 정책 | 재시도 (RPS 회복 대기) | 운영상 합리적 — 토큰 발급은 별도 KiwoomAuthClient 라 timing oracle 우려 없음 |
| 8 | `call_paginated` max_pages | hard cap (어댑터 20, 클라이언트 기본 50) → KiwoomMaxPagesExceededError | 무한 cont-yn=Y DoS 방어 |
| 9 | `call_paginated` break 정책 | caller `break` 시 generator finalize OK | 외부 리소스 미보유 — 안전 |
| 10 | **C-1 토큰 헤더 인젝션** | wire 전 `_VALID_TOKEN_PATTERN` (`^[A-Za-z0-9._\-+/=]+$`) 정규식 검증 | 적대적 리뷰 — 토큰에 \r\n / control char 시 헤더 인젝션 → h11 LocalProtocolError 메시지에 토큰 평문 박혀 leak |
| 11 | **C-1 `__context__` leak 차단** | `raise` 를 except 블록 밖에서 실행 (변수 캡처 패턴) | `from None` 은 `__suppress_context__=True` 만 set. `__context__` 는 살아있어 Sentry/structlog `walk_tb` leak 가능. except 밖 raise 는 PEP 3134 자동 chaining 차단 |
| 12 | **H-1 페이지네이션 헤더 검증** | cont_yn `("Y","N")` 외 reject + next_key 정규식 검증 | 키움 응답이 변조되어 next-key 에 \r\n 인젝션 시 다음 호출 헤더 인젝션 차단 (request 시 + response 시 둘 다) |
| 13 | **M-2 mrkt_tp 시그니처** | `Literal["0","1","2","4","7"]` + 런타임 가드 (belt-and-suspenders) | mypy strict 가 caller (라우터) 까지 강제. SectorListRequest Pydantic 도 wire 직전 검증 |
| 14 | Pydantic 응답 alias | `SectorListResponse.items` (attribute) ↔ `list` (alias). `populate_by_name=True` | builtin `list` shadowing 회피. 키움 JSON 키는 그대로 |
| 15 | KiwoomResponse | frozen + slots dataclass — body + cont_yn + next_key + status_code | 페이지네이션 메타 + 디버깅용 status_code |
| 16 | 응답 본문 보호 일관성 | logger / 예외 메시지 / cause / context 모두 미포함 | α 정책 100% 일관 — Kiwoom 평문 토큰 패턴 마스킹 미보장 가정 |

### 8.3 결과

- 신규 파일 2개 (코드: `_client.py`, `stkinfo.py`) + 2개 (테스트)
- 테스트 +38 → **277 passed / coverage 90.36%** (이전 239)
- 이중 리뷰 사이클 1라운드 — **CRITICAL 1 (C-1) + HIGH 4 (H-1/H-2 + 1차 HIGH-1/HIGH-2) + MEDIUM 7** 발견 → 전부 적용 → CRITICAL/HIGH 0 PASS
- ruff lint 0 / mypy strict 0 (app + new tests) / bandit 0 / pip-audit 0 CVE
- 5관문 verification 통과 (KiwoomClient 인스턴스 + fetch_sectors smoke)

### 8.4 별도 후속 PR (A3-α follow-up)

| # | 항목 | 출처 | 우선순위 |
|---|------|------|------|
| F1 | **auth.py (α/β) 의 동일 `__context__` leak 백포트** — 모든 `from None` 패턴을 변수-캡처 except 밖 raise 로 리팩토링 | A3-α 적대적 C-1 | ✅ **적용** (§ 9 — 다음 커밋) |
| F2 | KiwoomBusinessError.message attribute scrub — `from app.observability.logging import _scrub_string` 적용 | A3-α 적대적 M-3 | low |
| F3 | KiwoomMaxPagesExceededError 라우터 매핑 (503 + Retry-After) — 무한 페이지네이션 부분 데이터 폐기 시 metric | A3-α 적대적 M-1 | A3-β |
| F4 | KiwoomClient instance 단일성 강제 (factory + lock) | A3-α 적대적 F2 | Phase D 사용자 trigger 도입 시 |
| F5 | next-key 응답 헤더 cont-yn=Y 인데 next-key 없는 edge case 명시 처리 (현재는 빈 헤더로 다음 호출) | A3-α 1차 LOW-1 | 운영 검증 후 |

**다음 chunk**: A3-β — Migration 002 (sector 테이블) + Sector ORM + SectorRepository + SyncSectorMasterUseCase + GET/POST `/api/kiwoom/sectors` + GET `/api/kiwoom/sectors/sync` (admin). γ chunk 의 APScheduler 는 그 다음.

---

## 9. F1 — auth.py `__context__` leak 백포트 (2026-05-07)

### 9.1 결정

**A3-α C-1 발견 (`__context__` leak via `from None`) 을 auth.py (α / β) 의 모든 `from None` 위치에 백포트.** 기존 보안 사고 1건 (A3-α C-1) 의 동일 패턴이 인증 클라이언트 (au10001 / au10002) 에 9곳 존재 — 보안 일관성을 위해 단독 PR 로 정리.

### 9.2 핵심 설계 결정

| # | 결정 | 근거 |
|---|------|------|
| 1 | **백포트 범위** | au10001 (`_do_issue_token` 4 + `expires_at_kst` 1) + au10002 (`revoke_token` 4) = 총 **9개 raise site** | A3-α 의 C-1 패턴이 그대로 적용 — Pydantic ValidationError / httpx exception / strptime ValueError 모두 `__context__` 에 currently-handling exception 자동 보존 |
| 2 | **패턴 선택** | 변수 캡처 + except 밖 raise (`network_error_type` / `parse_failed` / `request_validation_failed` / `response_validation_failed`) | `_client.py:212-251` / `stkinfo.py:105-117` 와 100% 일관. `_clear_chain()` helper 호출 대신 동일한 **언어 수준** 패턴 — Python 동작 자체가 예외 chain 안 만듦 |
| 3 | **JSON dict guard 보너스** | `try-except-else: if not isinstance(parsed, dict): raise KiwoomUpstreamError("응답이 dict 아님")` 추가 | `_client.py:271-279` 와 일관. 기존 auth.py 에 부재했던 가드 — 키움 응답이 JSON list/scalar 인 edge case 방어 |
| 4 | **회귀 테스트 8개** | 모든 raise site 에 `assert err.__cause__ is None` + `assert err.__context__ is None` | `from None` 으로 회귀 시 `__context__ != None` 으로 즉시 fail. A3-α `test_call_exception_context_is_cleared_*` 와 동형 |
| 5 | **try-else 안 raise 안전성** | `dict guard` 의 raise 는 try-else 블록 안 — Python 의미상 예외 처리 중이 아니라 `__context__` 자동 설정 안 됨 | PEP 3134 — `__context__` 는 "the exception that was being handled" 로만 설정. try 가 성공한 else 절은 처리 중 X |

### 9.3 결과

- 변경 파일 2개 (`app/adapter/out/kiwoom/auth.py` + `tests/test_kiwoom_auth_client.py`)
- 테스트 +8 → **285 passed / coverage 91.0%** (이전 277 / 90.36%)
- 이중 리뷰 1라운드 — **CRITICAL 0 / HIGH 0 PASS** (변경 범위 작음 — 패턴 백포트만, 새 로직 X)
- ruff lint 0 / format 0 / mypy strict 0 / bandit 0
- `auth.py` 파일 자체 커버리지 91% (이전 ~88%)

### 9.4 보안 일관성 종결 (A2 + A3-α + F1)

본 백포트로 **backend_kiwoom 의 모든 외부 호출 어댑터** (`auth.py`, `_client.py`, `stkinfo.py`) 가 **단일 예외 chain 정책** 으로 수렴:

- 모든 `raise Kiwoom*Error` 는 except 블록 **밖에서** 실행
- `from None` 사용 0건 (코드) — docstring/주석 설명만 잔존 (의도)
- `__context__` 와 `__cause__` 둘 다 None 보장 — Sentry/structlog `walk_tb` leak 차단
- 회귀 테스트: A3-α 4건 + F1 8건 = **총 12 회귀 테스트** 가 패턴 회귀 시 즉시 fail

### 9.5 다음 chunk

A3-β — Migration 002 (sector 테이블) + Sector ORM + SectorRepository + SyncSectorMasterUseCase + 라우터 + KiwoomMaxPagesExceededError 라우터 매핑 (F3 통합).

---

## 10. Phase A3-β — sector 도메인 영속화 + UseCase + 라우터 (2026-05-08)

### 10.1 결정

ka10101 의 도메인 풀 체인을 단일 PR 로 구축. `KiwoomStkInfoClient.fetch_sectors` (A3-α 완료) → `SyncSectorMasterUseCase` (시장 단위 격리) → `SectorRepository` (PG ON CONFLICT upsert + 디액티베이션) → DB. 라우터 (`GET/POST /api/kiwoom/sectors`) 까지 포함. APScheduler weekly cron 은 A3-γ 로 분리.

### 10.2 핵심 설계 결정

| # | 결정 | 근거 |
|---|------|------|
| 1 | **시장 단위 격리** — UseCase 가 `for mrkt_tp in SUPPORTED_MARKETS` 순회, KiwoomError catch 시 `MarketSyncOutcome.error` 기록 + 다음 시장 진행 | 한 시장 호출 실패가 4 시장 적재를 막지 않음 (계획서 § 8.1) |
| 2 | **시장 단위 트랜잭션** — `async with session_provider() as session, session.begin():` 으로 시장마다 새 세션 + 자체 commit | 시장 N DB 실패 시 그 시장만 rollback, 시장 1~N-1 변경 보존. session_provider 패턴은 TokenManager 와 일관 |
| 3 | **디액티베이션 정책 B** (is_active=FALSE marking) | hard DELETE 회피 — FK 참조 안전 + 과거 데이터 보존. 응답 재등장 시 upsert 가 is_active=TRUE 복원 |
| 4 | **upsert ON CONFLICT 갱신 필드** — sector_name / group_no / is_active=TRUE / fetched_at / updated_at | 응답에 등장하면 무조건 활성화 (재등장 복원) — 이름/group 변경도 자동 반영 |
| 5 | **`populate_existing=True`** — list_by_market / list_all SELECT 시 ORM identity map 의 stale 객체 회피 | 같은 세션에서 bulk update 후 SELECT 시 캐싱된 객체가 DB 상태와 mismatch — 회귀 테스트 1건 (`test_upsert_many_reactivates_inactive_row`) 으로 잡힘 |
| 6 | **`MarketCode = Literal["0","1","2","4","7"]`** + `SUPPORTED_MARKETS: tuple[MarketCode, ...]` | UseCase 의 hardcoded tuple 이 fetch_sectors 의 Literal 시그니처와 mypy strict 정합 |
| 7 | **DB CHECK constraint** — `market_code IN ('0','1','2','4','7')` | Pydantic Literal + ORM CheckConstraint + DB CHECK 3중 방어. 무효값 INSERT 차단 (회귀 테스트 1건) |
| 8 | **UNIQUE(market_code, sector_code)** 복합키 | upsert 키. 동일 sector_code 가 시장마다 다르게 등장 가능 — 단일 컬럼 UNIQUE 불가 |
| 9 | **F3 통합** (가벼운 hint) — outcome.error 에 "MaxPages" 흔적 시 응답 헤더 `Retry-After: 60` 추가 | KiwoomMaxPagesExceededError 는 KiwoomError 자식이라 UseCase 가 outcome 으로 격리. 라우터는 200 + hint 헤더로 oncall 알람. 응답 코드/본문 변경 X |
| 10 | **alias query 파라미터** (POST /sync) — admin 이 명시적으로 자격증명 alias 선택 | hardcoded alias 회피 — 운영 dry-run 시점에 자격증명 종류 결정. 다중 자격증명 운영 환경 호환 |
| 11 | **SyncSectorUseCaseFactory** — `alias → AsyncContextManager[UseCase]`, `lifespan` 에서 set | sync 마다 새 KiwoomClient + close 보장 (Semaphore 상태 격리). dependency_overrides 로 테스트 주입 가능 |
| 12 | **GET /sectors admin 불필요** — 조회만 / DB only | 키움 호출 없음. 외부 BFF 가 DB read 직접 — 부담 최소 |
| 13 | **POST /sectors/sync admin 필요** | 키움 호출 발생 + DB 변경 — admin guard 강제 |
| 14 | **`SectorOut.from_attributes=True`** — ORM Sector → API 응답 안전 매핑 | id 노출 — BIGSERIAL fingerprint 미미. 운영 페이징에 미사용 |
| 15 | **`MarketSyncOutcomeOut.from_attributes=True`** — dataclass slots → Pydantic | 풀 체인 통합 테스트 (`test_router_post_sync_full_chain_writes_to_db`) 로 매핑 회귀 검증 |
| 16 | **APScheduler 분리** — A3-γ 별도 PR | β graceful shutdown hook 과 충돌 검증 필요 + scheduler 모듈 새 도입 — chunk 단일 PR 1,500줄 이내 유지 |

### 10.3 결과

- 신규 파일 7개 + 확장 2개:
  - `migrations/versions/002_kiwoom_sector.py` (신규)
  - `app/adapter/out/persistence/models/sector.py` (신규) + `__init__.py` 등록
  - `app/adapter/out/persistence/repositories/sector.py` (신규)
  - `app/application/service/sector_service.py` (신규 — UseCase + 2 dataclass)
  - `app/adapter/web/routers/sectors.py` (신규 — 2 라우터 + 3 Pydantic DTO)
  - `app/adapter/web/_deps.py` (확장 — SyncSectorUseCaseFactory + getter/setter)
  - `app/main.py` (확장 — sector router include + lifespan factory)
  - 테스트: `test_migration_002.py`, `test_sector_repository.py`, `test_sector_service.py`, `test_sector_router.py`, `test_sector_router_integration.py` + `test_models.py` 확장
- 테스트 +47 → **332 passed / coverage 91%** (이전 285 / 91%)
- 핵심 파일 커버리지: sector_service 94% / sector_router 95% / sector_repository 100% / sector_model 100%
- 이중 리뷰 1라운드 — **CRITICAL 0 / HIGH 0 / MEDIUM 3** (모두 정합성 OK, 추가 적용 없음) → PASS
- ruff lint 0 / format 0 / mypy strict 0 (38 source files) / bandit 0
- 5관문 verification 통과 (라우터 → 실 UseCase factory → MockTransport → testcontainers DB 풀 체인 1 케이스)

### 10.4 운영 dry-run 보류 (DoD § 10.3)

A3-α + F1 + A3-β 합산 코드 검증만. 운영 자격증명 1쌍 등록 후 일괄 검증 (DoD § 10.3):
1. 5 시장 호출 성공 + 각 시장 row 수 (KOSPI ~30~50 추정)
2. `code` 길이 분포 (3자리 가정 검증)
3. `marketCode` String 가정 검증 (스펙 LIST 표기 → String 으로 fallback OK 인지)
4. 페이지네이션 발생 여부 (KOSPI 50 미만이면 단일 페이지)
5. 같은 sync 두 번 멱등성 (`total_upserted` 동일, `total_deactivated=0`)
6. F3 hint 동작 — max_pages 한도 초과 케이스 (강제 max_pages=1 로 검증 가능)

### 10.5 별도 후속 PR

| # | 항목 | 우선순위 |
|---|------|------|
| **A3-γ** | APScheduler weekly cron (KST 일 03:00) — `fire_sector_sync` 콜백 + scheduler 모듈 + lifespan 통합 (β graceful shutdown 충돌 검증) | 다음 PR |
| 운영 dry-run | DoD § 10.3 일괄 검증 | 자격증명 등록 후 |
| F2 | KiwoomBusinessError.message scrub | low |
| F4 | KiwoomClient instance 단일성 강제 (factory + lock) | Phase D |
| F5 | next-key 없이 cont-yn=Y edge case | 운영 검증 후 |

### 10.6 다음 chunk

A3-γ — APScheduler weekly + scheduler 모듈 + lifespan 통합. 그 다음 운영 dry-run.

---

## 11. Phase A3-γ — APScheduler weekly cron + lifespan 통합 (2026-05-08)

### 11.1 결정

ka10101 sector sync 의 자동 트리거. 일요일 KST 03:00 cron job 1개 등록 (업종 변경이 잦지 않음 — 주 1회면 충분). AsyncIOScheduler 를 lifespan 에 통합하되 graceful shutdown 순서를 명확히 정의 — scheduler 먼저 정지 → 그 다음 token revoke → engine.dispose.

### 11.2 핵심 설계 결정

| # | 결정 | 근거 |
|---|------|------|
| 1 | **AsyncIOScheduler** (BackgroundScheduler 아님) | FastAPI lifespan 의 동일 이벤트 루프에 묶임 — async UseCase 가 직접 호출 가능. BackgroundScheduler 는 별도 스레드 — `_token_provider` 의 asyncio.Lock 충돌 위험 |
| 2 | **CronTrigger(day_of_week="sun", hour=3, minute=0, timezone=KST)** | 새벽 3시 — DB IO 부담 적은 시간대. 일요일 — KOSPI/KOSDAQ 휴일이라 시장 데이터 안정 |
| 3 | **`max_instances=1` + `coalesce=True`** | 이전 cron 이 길게 늘어져 다음 트리거와 겹치는 상황 방어. 누락된 트리거는 1번으로 축약 |
| 4 | **`replace_existing=True`** + start 멱등성 가드 (`self._started` 플래그) | 재 start 호출해도 job 중복 등록 0건. 회귀 테스트 1건 |
| 5 | **scheduler shutdown → token revoke → engine.dispose 순서** | 진행 중 cron job 의 KiwoomClient 호출이 token revoke 와 충돌하지 않게. `wait=True` 로 진행 중 job 완료 대기 |
| 6 | **`is_running = _started AND scheduler.running`** | AsyncIOScheduler.shutdown(wait=False) 의 비동기 cleanup race 회피 — 호출자 의도 (start/shutdown) 가 진실의 원천 |
| 7 | **fail-fast 가드** — `scheduler_enabled=True + scheduler_sector_sync_alias=""` 면 lifespan startup RuntimeError | 운영 실수 방어 — alias 누락 상태로 cron 이 매주 실패 vs startup 즉시 실패. 후자 안전 |
| 8 | **cron 콜백 (`fire_sector_sync`) 모든 예외 swallow** | APScheduler 가 다음 tick 정상 트리거하도록 보장. logger.exception 만 보고 — 운영 알람 hint |
| 9 | **부분 실패 시 logger.warning** — `all_succeeded=False` 분기 | 5 시장 중 일부 실패 시 oncall 알람용. 정상 완료는 logger.info |
| 10 | **`Settings.scheduler_sector_sync_alias`** — alias 명시 필드 | hardcoded alias 회피 — 운영 환경별 자격증명 alias 다를 수 있음 (prod-main / mock-test 등) |
| 11 | **mypy override `apscheduler.*` ignore_missing_imports** | APScheduler 3.x stubs 미제공. `pyproject.toml` 의 [[tool.mypy.overrides]] 에 추가 |
| 12 | **`SectorSyncScheduler` 단일 책임** — sector sync cron 1개만 관리 | 다른 cron job 추가 시 별도 클래스 또는 generic 래퍼로 분리 — Phase B/C 진입 시 |

### 11.3 결과

- 신규 파일 3개 + 확장 3개:
  - `app/scheduler.py` (신규 — SectorSyncScheduler + KST 상수 + SECTOR_SYNC_JOB_ID)
  - `app/batch/__init__.py` (신규)
  - `app/batch/sector_sync_job.py` (신규 — fire_sector_sync 콜백)
  - `app/config/settings.py` (확장 — `scheduler_sector_sync_alias` 필드)
  - `app/main.py` (확장 — lifespan 통합 + fail-fast 가드)
  - `pyproject.toml` (확장 — apscheduler mypy override)
- 테스트 +13 (`tests/test_scheduler.py` — 신규 13 케이스):
  - fire_sector_sync 정상/예외/부분실패 (3 — monkeypatch 로 logger 직접 mock, caplog 회피)
  - SectorSyncScheduler enabled/disabled/idempotent/shutdown 5
  - 수동 job 호출 1
  - lifespan fail-fast 1 + startup·shutdown 사이클 enabled/disabled 2
- 누적 **345 passed / coverage 93%** (이전 332 / 91%)
- 핵심 파일: `scheduler.py` 96% / `sector_sync_job.py` 100% / `main.py` 75% (lifespan 사이클 커버 +)
- ruff 0 / format 0 / mypy strict 0 (41 source files) / bandit 0
- 5관문 모두 통과 (3-5 런타임 smoke — lifespan startup→shutdown 사이클 enabled/disabled 양방향 검증)

### 11.4 운영 dry-run 으로 보류

`scheduler_enabled` 는 운영 환경에서만 True. 로컬/CI 는 기본 False. 운영 dry-run 시점에 다음 검증:
1. `SCHEDULER_ENABLED=true` + 유효 alias 로 컨테이너 기동 시 cron 등록 확인
2. APScheduler logger 로 다음 트리거 시각 (KST 일 03:00) 확인
3. 수동 트리거 (POST `/sectors/sync?alias=...`) → cron 콜백 결과와 일치 확인
4. 컨테이너 재시작 시 lifespan shutdown → scheduler.shutdown(wait=True) → graceful revoke 순서 정상 도달

### 11.5 다음 chunk

운영 dry-run (DoD § 10.3) — α + β + A3-α + F1 + A3-β + A3-γ 통합 검증. 그 다음 Phase B (종목 마스터 ka10099/ka10100/ka10001).

---

## 12. Phase B-α — ka10099 종목 마스터 + StockMasterScheduler (2026-05-08)

### 12.1 결정

**ka10099 (종목정보 리스트) endpoint 의 어댑터·도메인·라우터·일간 cron 통합**. Phase B 의 첫 chunk — 백테스팅 진입점인 종목 마스터 적재.

### 12.2 핵심 설계 결정

| # | 결정 | 근거 |
|---|------|------|
| 1 | `StockListMarketType` StrEnum (16종) — `ka10101` 의 `0/1/2/4/7` 와 분리 | 같은 mrkt_tp 키인데 endpoint 별 의미 완전히 다름 (master.md § 12). Literal 16 case 길어서 StrEnum 채택 |
| 2 | `STOCK_SYNC_DEFAULT_MARKETS = (0, 10, 50, 60, 6)` 5종 | 작업계획서 §2.3 P0+P1. ETF(8) 는 별도 Phase 결정 (대량) |
| 3 | `to_normalized` 의 `market_code = requested_market_code` (응답 marketCode 영속화 안 함) | **1R H1** — cross-market zombie row 방지 + sector 패턴 일관 + deactivate_missing 격리 보장 |
| 4 | `UNIQUE(stock_code)` 단일키 (sector 의 복합키와 다름) | 한 종목이 여러 시장에 등장해도 ON CONFLICT UPDATE — 운영 dry-run 후 정책 재검토 (§11.1 #2) |
| 5 | `mock_env=True` 시 nxtEnable 강제 False (§4.2) | mock 도메인은 NXT 미지원 — 응답 검증 layer |
| 6 | 빈 응답 시 `deactivate_missing` SKIP | KOSPI 빈 응답으로 모든 KOSPI 종목 비활성화 사고 방지 |
| 7 | `outcome.error` 클래스명 only (sector + stock 둘 다) | **1R M-2** — 응답 본문 echo 차단 (admin 노출 위험). 메시지는 logger 경로로만 |
| 8 | `state` VARCHAR(255) — sector 의 100보다 길게 | **1R M-1** — 키움 다중값 `"증거금20%\|담보대출\|..."` 안전 마진 |
| 9 | `StockMasterScheduler` 별도 클래스 (sector scheduler 와 lifecycle 분리) | KST mon-fri 17:30 (장 마감 후) — sector 의 일 03:00 와 다른 cron. 같은 패턴, 별도 AsyncIOScheduler |
| 10 | mock_env 가 lifespan 1회 결정 (프로세스당 단일 env 가정) | **1R H-1** — 운영 가정 명시. 향후 멀티 env 동시 운영 시 alias 단위 결정으로 변경 필요 |

### 12.3 결과

- **신규/확장 12 파일**:
  - 신규: `app/application/constants.py`, `app/application/service/stock_master_service.py`, `app/adapter/out/persistence/models/stock.py`, `app/adapter/out/persistence/repositories/stock.py`, `app/adapter/web/routers/stocks.py`, `app/batch/stock_master_job.py`, `migrations/versions/003_kiwoom_stock.py`
  - 확장: `app/adapter/out/kiwoom/stkinfo.py` (fetch_stock_list + StockListRow + NormalizedStock + StockListRequest), `app/adapter/web/_deps.py` (SyncStockMasterUseCaseFactory), `app/config/settings.py` (scheduler_stock_sync_alias), `app/main.py` (lifespan stock factory + scheduler), `app/scheduler.py` (StockMasterScheduler), `app/application/service/sector_service.py` (M-2 백포트)
- **테스트**: 99 신규 (어댑터 36 + Repository 17 + UseCase 14 + 라우터 단위 12 + 라우터 통합 1 + 마이그레이션 7 + Scheduler 11 + service property 1)
- **누적**: 443 tests / coverage 93.38% (B-α 신규 모듈 95-100%)
- **이중 리뷰 결과**: 1R 7건 (HIGH 2 / MEDIUM 5 / LOW 5) → 모두 수정 후 2R PASS (CRITICAL/HIGH 0)

### 12.4 운영 dry-run 으로 보류 (DoD § 10.3)

키움 자격증명 1쌍으로 다음 검증 — Phase B-γ 또는 별도 dry-run chunk 에서 일괄:
1. 5 시장 모두 호출 성공 + 시장별 종목 수 (KOSPI ≥ 800, KOSDAQ ≥ 1500 추정)
2. 응답 `marketCode` ↔ 요청 `mrkt_tp` 분포 (§11.2 알려진 위험 — 현재 응답 marketCode 영속화 안 하므로 운영 영향 없음, but 분포 확인은 필요)
3. `nxtEnable` Y/N 비율 (KOSPI vs KOSDAQ 차이)
4. 페이지네이션 발생 횟수 (max_pages=100 마진 충분성)
5. 멱등성 — 같은 sync 두 번 → upserted 동일, deactivated=0
6. 한 종목 여러 시장 중복 (§11.1 #2) — UNIQUE(stock_code) 정책 재검토 트리거 데이터

### 12.5 다음 chunk

Phase B-β (ka10100 종목 정보 리스트) — gap-filler 단건 보강. NormalizedStock 변환 로직 공유 (§11.3).

---

## 13. Phase B-β — ka10100 단건 종목 조회 (gap-filler / lazy fetch) (2026-05-08)

### 13.1 결정

**B-α (ka10099 bulk sync) 의 gap-filler 로 ka10100 단건 보강 endpoint 추가.** 핵심 결정:

1. **단건 endpoint 의 두 진입점 — `execute` + `ensure_exists`**
   - `execute(stock_code)`: admin POST `/stocks/{code}/refresh` 또는 CLI 의 명시 호출. 항상 키움 호출 + DB upsert.
   - `ensure_exists(stock_code)`: 다른 service 의 lazy 보강 진입점. DB hit (active) → 캐시 hit / DB miss/inactive → 키움 호출.
   - Phase C 의 OHLCV ingest 가 stock 마스터 미스 시 `ensure_exists` 로 lazy fetch.

2. **`StockRepository.upsert_one` 추가 — RETURNING + populate_existing**
   - upsert_many 가 다건 + 영향 row 수만 반환하는 반면, 단건은 caller 가 즉시 갱신된 `Stock(.id, .fetched_at)` 을 받아야 함.
   - SQLAlchemy 2.0 `pg_insert(...).on_conflict_do_update(...).returning(Stock)` + `execution_options(populate_existing=True)` 로 session identity map stale 방어.

3. **`HTTP GET /api/kiwoom/stocks/{stock_code}` — DB only, 404 if missing**
   - lazy fetch 는 internal Python API (`ensure_exists`) 만 — HTTP 노출 X. 외부 `auto_lookup` query 는 운영 수단으로 부적합 (alias 결정 모호).
   - 단건 디버깅 / 검증은 admin POST `/refresh?alias=` 로만.

4. **`HTTP POST /api/kiwoom/stocks/{stock_code}/refresh?alias=` — admin, 강제 재조회**
   - `require_admin_key` (`hmac.compare_digest`) — sector/B-α 패턴 일관.
   - `alias` 쿼리 필수 — multi-alias 운영 가정.
   - KiwoomError 매핑: Business → 400 / CredentialRejected → 400 / RateLimited → 503 / Upstream/Validation → 502 / KiwoomError fallback → 502.

5. **`STK_CD_LOOKUP_PATTERN = r"^[0-9]{6}$"` 단일 source — ASCII 0-9 only**
   - 어댑터 validator + Pydantic Request + 라우터 Path pattern 세 곳이 모두 같은 상수 참조. unicode digit (`\d` 매칭) 차단.
   - 1R 2a-H1 — 이전 `(6, 6)` 튜플 미사용 상수 정정.

6. **mock_env 정책 — B-α 와 동일 (lifespan 1회 결정)**
   - `settings.kiwoom_default_env == "mock"` 시 `nxt_enable=False` 강제. 멀티 env 동시 운영 시 alias 단위 결정 필요 — B-α § 12.2 결정 백포트.

7. **단건 `to_normalized()` — 응답 marketCode 그대로 사용 (B-α 와 차이)**
   - ka10100 은 stk_cd 만으로 호출하므로 `requested_market_code` 인자 없음. 응답 `marketCode` 가 권위 source — `requested_market_type` 도 응답값.
   - B-α 의 페이지 응답 `to_normalized` 와 다른 시그니처 — caller 가 mrkt_tp 안 넘기는 단건 endpoint 의 의미 차이 반영.

### 13.2 1R 적대적 이중 리뷰 결과

**HIGH 4 / MEDIUM 9 / LOW 6 — HIGH/MEDIUM 8건 적용 + LOW/일부 MEDIUM defer**

| ID | 항목 | 적용 |
|----|------|------|
| 2a-H1 | `_STK_CD_PATTERN = (6,6)` 미사용 → 정규식 단일 상수 (`STK_CD_LOOKUP_PATTERN`) | ✅ |
| 2a-H2 | `ensure_exists` TOCTOU docstring 정정 (race 시 두 코루틴 모두 execute 진입, ON CONFLICT 흡수) | ✅ |
| 2b-H1 | `KiwoomBusinessError.message` admin 응답 echo 차단 — B-α M-2 백포트 누락 | ✅ |
| 2b-H2 | raw `ValueError` (정규화 실패) → `KiwoomResponseValidationError` 매핑 (flag-then-raise-outside-except 패턴) | ✅ |
| 2a-M2 | `ensure_exists` 의 `is_active=False` 자동 재조회 + 활성 복원 | ✅ |
| 2b-M2 | `ensure_exists` 진입 시 `_validate_stk_cd_for_lookup` 호출 (DB hit 분기 우회 차단) | ✅ |
| 2b-M4 | lifespan teardown 시 `reset_*_factory` 호출 (close 후 stale factory 노출 차단) | ✅ |
| 2b-M5 | `KiwoomError` fallback 에 `logger.warning` (운영 가시성, 메시지 echo 안 함) | ✅ |
| 2a-M1 | `StockListRow` ↔ `StockLookupResponse` 14필드 중복 — mixin 추출 | **defer** (Pydantic ConfigDict 병합 위험) |
| 2a-M3 | `asdict` pop 패턴 — `to_db_dict` 헬퍼 추출 | **defer** (B-α 와 함께 정리) |
| 2b-M1 | **lazy fetch RPS 폭주 (Phase C 미지 종목 100건 동시 호출)** | **defer — Phase C 진입 전 결정** |
| 2b-M3 | `execute` cancel-safety | defer — 트랜스포트 retry 흡수 |
| 2b-L1~3 | Pydantic extra/Path unicode/walk_tb echo | defer — 향후 ADR-0001 § 3 일관 적용 |

**2R 결과**: HIGH 4 + MEDIUM 적용 4건 모두 PASS. 새 결함 도입 없음.

### 13.3 변경 정리

- **신규/확장 7 파일 (코드)**:
  - 확장: `app/adapter/out/kiwoom/stkinfo.py` (`StockLookupResponse`, `StockLookupRequest`, `STK_CD_LOOKUP_PATTERN`, `_validate_stk_cd_for_lookup`, `KiwoomStkInfoClient.lookup_stock`)
  - 확장: `app/adapter/out/persistence/repositories/stock.py` (`upsert_one`)
  - 확장: `app/application/service/stock_master_service.py` (`LookupStockUseCase`)
  - 확장: `app/adapter/web/_deps.py` (`LookupStockUseCaseFactory` set/get/reset)
  - 확장: `app/adapter/web/routers/stocks.py` (`GET /{stock_code}`, `POST /{stock_code}/refresh`)
  - 확장: `app/main.py` (lifespan `_lookup_stock_factory` + teardown reset)
- **테스트**: 55 신규
  - `tests/test_kiwoom_stkinfo_lookup.py` (17) — 어댑터 단건 + 정규화 + Pydantic
  - `tests/test_lookup_stock_service.py` (14) — UseCase 통합 + 1R 회귀 가드 4
  - `tests/test_stock_lookup_router.py` (18) — 라우터 + admin guard + KiwoomError 매핑 + 1R 회귀 가드 2
  - `tests/test_stock_repository_upsert_one.py` (5) — Repository 단위
  - `tests/test_lookup_stock_deps.py` (5) — DI factory 단위
- **누적**: 498 tests / coverage 93.73% (B-β 신규 모듈 86-100%)
- **DB 스키마**: 변경 없음 (`kiwoom.stock` 테이블 재사용 — UNIQUE stock_code 단일키)

### 13.4 Phase C 진입 전 결정 필요 (deferred)

1. **lazy fetch RPS 폭주 보호 (2b-M1)** — Phase C OHLCV ingest 가 미지 종목 100건 응답 시 ka10100 100회 동시 호출. 현재 `KiwoomClient` 인스턴스 단위 RPS 보호 → factory 마다 새 인스턴스라 글로벌 RPS 우회. 결정 옵션:
   - (a) `KiwoomClient` 를 alias 단위 lifespan 싱글톤으로 격상
   - (b) `ensure_exists` 에 stock_code 단위 in-flight cache (asyncio.Lock)
   - (c) Phase C 진입 시 미지 코드 batch 처리 + lazy fetch fail-closed
2. **누락 감지 cron 도입 시점** — 작업계획서 § 7.3. Phase C 후 결정 (sync_log 테이블 추가 필요).
3. **운영 dry-run 통합** — B-α dry-run 항목 (§ 12.4) 에 ka10100 단건 호출 검증 추가:
   - 삼성전자(`005930`), KODEX 200(`069500`), 카카오(`035720`) 응답 14 필드 모두 채워져 있음
   - 존재하지 않는 종목(`999999`) 응답 패턴 확인 (`return_code != 0`?)
   - mock 도메인의 `nxtEnable` 응답 패턴

### 13.5 다음 chunk

Phase B-γ (ka10001 주식 기본 정보) — 펀더멘털 보강. Phase B 마무리. 작업계획서 1,164줄 → chunk 분할 검토 필요.
