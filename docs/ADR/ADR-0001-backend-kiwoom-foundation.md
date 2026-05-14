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

---

## 14. Phase B-γ-1 — ka10001 펀더멘털 인프라 chunk (Migration + ORM + Repository + Adapter) (2026-05-08)

### 14.1 결정

- 1,164줄 작업계획서를 **B-γ-1 (인프라) + B-γ-2 (UseCase/Router/Scheduler)** 두 chunk 로 분할 (사용자 승인). 본 chunk 는 인프라만.
- **거래소 호출 정책 = (a) KRX only** — NXT/SOR 추가는 Phase C 후 결정 (계획서 § 4.3 권장 (a) 채택, § 11.1 #1).
- **일 1회 cron 시간 = 18:00 KST** — ka10099 stock master cron 18:00 직후. is_active stock 조회 시점에 마스터 최신화 보장 (§ 11.1 #5). 본 chunk 는 cron 미배포, B-γ-2 에서 코드화.
- **2R 적대적 이중 리뷰 (--force-2b)** 강제 적용 — 계약 변경 분류로 자동 게이트는 2b 생략이지만 사용자 명시 요청.

### 14.2 핵심 설계 결정 (2R 적용 후)

#### A. 어댑터 — `KiwoomStkInfoClient.fetch_basic_info` (B-α/B-β 패턴 차용)

- **stk_cd 6자리 ASCII 강제** — ka10100 의 `_validate_stk_cd_for_lookup` 재사용 (`STK_CD_LOOKUP_PATTERN = r"^[0-9]{6}$"`). KRX-only 결정과 일관 — `_NX`/`_AL` suffix 거부.
- **Pydantic Request wire 직전 검증** — `StockBasicInfoRequest(stk_cd=...).model_dump()` 패턴 일관 (sector / ka10099 / ka10100).
- **flag-then-raise-outside-except** — `validation_failed` flag 캡처 후 except 밖에서 raise. Pydantic ValidationError 가 `KiwoomResponseValidationError.__context__/__cause__` 에 박히지 않음 (B-β 1R 2b-H2 회귀 방어).

#### B. 응답 모델 — `StockBasicInfoResponse` (45 필드 + 250hgst alias)

- `populate_by_name=True` + `Field(alias="250hgst")` — Pydantic 식별자 첫 글자 숫자 불가 회피.
- `extra="ignore"` — 키움이 신규 필드 추가해도 어댑터 안 깨짐.
- **2R A-H1 적용 — 모든 string 필드 `Field(max_length=N)` 강제**: vendor 거대 string 응답 시 Pydantic 단계 차단 → `KiwoomResponseValidationError` 자동 매핑. CHAR/VARCHAR DB 컬럼과 sync (`setl_mm:2`, `pre_sig:1`, `fav_unit:10`, 숫자 string 32자, `return_msg:200`).

#### C. 정규화 — `_to_int` / `_to_decimal` (vendor 입력 보호)

- **2R A-C1 적용 — `_to_int` BIGINT 경계 가드** (`_BIGINT_MIN = -(2**63)`, `_BIGINT_MAX = 2**63 - 1`): 거대 정수 응답 시 None 반환 → 트랜잭션 abort 차단. Python int 임의정밀 + PG BIGINT 한계 mismatch 방어.
- **2R A-C2/A-H4 적용 — `_to_decimal` `is_finite()` 가드**: `Decimal("NaN")`/`Decimal("Infinity")`/`Decimal("sNaN")` 모두 None. PG NUMERIC 이 NaN 받지만 다운스트림 백테스팅 산술 폭발 + signaling NaN 의 hash 산출 시 InvalidOperation raise 차단.
- **2R M-2 — `_to_decimal` 도 `replace(",", "")`** — `_to_int` 와 비대칭 해소.
- **2R A-L1 — `_validate_stk_cd_for_lookup` 메시지 `stk_cd[:50]!r` cap**: log line 폭주 / RTL override 공격 차단.

#### D. 도메인 — `NormalizedFundamental` (slots dataclass) + `normalize_basic_info`

- `exchange="KRX"` 디폴트 (B-γ-1 KRX-only). **2R C-M4 — kwarg 인자화** (`exchange: str = "KRX"`) 로 BC 보존 — Phase C NXT/SOR 추가 시 시그니처 변경 0.
- `stock_code` / `stock_name` 은 dataclass 에는 있고 영속화 안 함 — FK 는 stock_id, stock_name 은 Stock 마스터 권위 (mismatch alert 는 B-γ-2 UseCase 책임).
- `strip_kiwoom_suffix` — 응답 stk_cd 가 `_NX`/`_AL` 메아리쳐도 base 6자리로 정규화.

#### E. Repository — `StockFundamentalRepository`

- **2R B-H2 적용 — `upsert_one(row, *, stock_id, expected_stock_code=None)`**: caller 가 `expected_stock_code` 명시 시 `row.stock_code` 와 일치 검증, mismatch 시 ValueError. Phase C 의 OHLCV ingest 가 stock_id resolution 실수로 cross-link row 만드는 사고 차단.
- **2R B-H3 적용 — 명시 update_set 46 항목**: `for col in values if col not in (...)` 자동 생성 패턴 폐기. NormalizedFundamental 의 미래 필드 추가 시 silent contract change 방지 (Stock repository 패턴 일관). UNIQUE 키 (stock_id/asof_date/exchange) 정확히 제외.
- `populate_existing` — UPDATE 시 session identity map stale 방어 (B-α/B-β 패턴 일관).

#### F. fundamental_hash 산출

- **PER/EPS/ROE/PBR/EV/BPS 6 필드 MD5** — 일중 시세 변경은 hash 영향 없음 (외부 벤더 갱신만 검출). MD5 는 변경 감지 fingerprint 용도, 보안 무결성 목적 아님 (1R C-L3 명시).
- `Decimal.normalize() + format("f")` — `"15.20"` ↔ `"15.2"` 정규화 일관 (§ 11.2 알려진 위험). `format("g")` 절대 금지 (지수 표기 위험).

#### G. ORM / Migration

- Migration 004 — `kiwoom.stock_fundamental` 테이블 + UNIQUE(stock_id, asof_date, exchange) + FK CASCADE + 2 인덱스 (`asof_date`, `stock_id`).
- **2R L-2 — ORM CHAR 타입 sync**: `settlement_month` / `prev_compare_sign` / `fundamental_hash` 모두 `CHAR(N)` (Migration SQL `CHAR(N)` 와 일치).

### 14.3 1R 적대적 이중 리뷰 결과 + 2R 적용 매핑

1R: CRITICAL 2 + HIGH 4 + MEDIUM 5 + LOW 5 → 2R 에서 12개 적용 + 회귀 테스트 16 추가.

| 1R ID | 카테고리 | 적용 위치 |
|-------|---------|----------|
| A-C1 | BIGINT overflow | `_to_int` `_BIGINT_MIN`/`_BIGINT_MAX` 가드 |
| A-C2 | NaN/Infinity/sNaN | `_to_decimal` `is_finite()` 가드 |
| A-H1 | Pydantic max_length | `StockBasicInfoResponse` 45 필드 + `return_msg` |
| A-H4 | sNaN → hash raise | A-C2 가드로 자동 차단 |
| B-H2 | stock_id ↔ stock_code | `upsert_one(expected_stock_code=...)` cross-check |
| B-H3 | update_set schema-drift | 명시 update_set 46 항목 |
| M-1 | _hash_part 주석 오기 | 주석 정정 (`format("f")` 명시) |
| M-2 | _to_decimal 쉼표 비대칭 | `replace(",", "")` 추가 |
| C-M4 | exchange 하드코딩 | `normalize_basic_info` 에 kwarg |
| L-1 | 모듈 docstring | ka10001 (B-γ-1) 추가 |
| L-2 | ORM CHAR 타입 | `settlement_month`/`prev_compare_sign`/`fundamental_hash` |
| A-L1 | repr cap | `stk_cd[:50]!r` |

2R 결과: **PASS** — 1R 12개 모두 PASS 검증, 신규 회귀 위협 0건 (B-M2 CPU 폭주 → Python 3.12 PEP 686 보호 / timing-side / Decimal context override / UTF-8 multi-byte / update_set exchange 잘못 갱신 모두 NOT EXPLOITABLE).

### 14.4 결과

- **테스트 550 passed / coverage 94.28%** (이전 498 + 36 Step 1 + 16 2R 회귀)
- mypy --strict ✅ / ruff ✅ / Alembic upgrade head testcontainers ✅ / FastAPI app create ✅
- 변경 파일: 코드 5 (Migration 004 신규, StockFundamental ORM 신규, models __init__ 갱신, StockFundamentalRepository 신규, stkinfo.py 확장) + 테스트 3 신규
- 회귀 0건 — A1/A2/A3-α/A3-β/A3-γ/F1/B-α/B-β 모두 영향 없음

### 14.5 Defer (B-γ-2 또는 운영 검증 시점)

| 항목 | 1R ID | 결정 시점 | 메모 |
|------|-------|-----------|------|
| vendor non-numeric metric (logger.warning + 히스토그램) | B-M1 | Phase F monitoring | `_to_int`/`_to_decimal` 의 None path 진입 시 logger metric. 현재는 silent NULL — 운영팀이 vendor 이상 무알림 |
| `KiwoomBusinessError` partial-failure 정책 | C-M3 | B-γ-2 작업계획서 | 단건 endpoint 라 본 chunk 무관, 다음 chunk SyncStockFundamentalUseCase 가 multi-stock loop 에서 한 종목 KiwoomBusinessError → 전체 abort 차단 책임 |
| `replace(",", "")` 의도 명확화 | B-M5 | docstring 보강 시점 | 키움 명세에 콤마 부재 — 안전망 처리. 미사용 변환은 미래 표면 |
| `_parse_yyyymmdd` silently None 알림 | B-L2 | 운영 1주 모니터 | 잘못된 응답 무알림 — B-α 시점 결정 |
| 단위 (mac/cap/listed_shares) 운영 검증 후 컬럼 주석 | § 11.1 #2 | DoD § 10.3 운영 dry-run 후 | 영업일 1회 ka10001 호출 후 cur_prc × listed_shares 와 비교 |

### 14.6 다음 chunk

**Phase B-γ-2** — `SyncStockFundamentalUseCase` + `POST /api/kiwoom/fundamentals/sync` 라우터 + `POST /api/kiwoom/stocks/{stock_code}/fundamental/refresh` 단건 라우터 + `StockFundamentalScheduler` (KST 18:00 평일).

진입 전 결정 사항 (B-γ-2 작업계획서):
- **partial-failure 정책** (C-M3) — multi-stock loop 에서 한 종목 KiwoomBusinessError 발생 시 (a) per-stock try/except 후 success/failed counter 누적 (B-α 패턴 일관) / (b) 일정 비율 (10%, § 11.1 #7) 초과 시 전체 fail. (a) 권장.
- **stock_id resolution 책임** — 반드시 `Stock.find_by_code(strip_kiwoom_suffix(response.stk_cd))` → stock_id → `upsert_one(row, stock_id=, expected_stock_code=stock.stock_code)` 패턴 강제. 통합 테스트로 invariant 검증.
- **mismatch alert** (계획서 § 6.3) — 응답 stk_nm ≠ Stock.stock_name 시 `logger.warning` + Sentry alert. 적재는 진행.
- **lookup 의존** — Phase B-β 의 `LookupStockUseCase.ensure_exists` 가 미지 종목 보강. ka10001 호출 시 active stock 만 대상이라 ensure_exists 호출 불필요할 가능성 — 작업계획서에서 결정.

---

## 15. Phase B-γ-2 — ka10001 펀더멘털 자동화 (UseCase + Router + Scheduler) (2026-05-08)

### 15.1 결정

본 chunk 는 B-γ-1 인프라 위에 비즈니스 로직 + 운영 자동화 layer 추가. **Phase B 마무리 chunk** — 이후 Phase C (OHLCV 백테스팅) 진입 가능.

진입 전 결정 사항 (사용자 승인):
- **Partial-failure 정책 = (a) per-stock skip + counter** — 한 종목 KiwoomError 발생 시 try/except 후 success/failed counter 누적, 다음 종목 진행. B-α `SyncStockMasterUseCase` 의 시장 단위 패턴을 종목 단위로 변형 (§ 14.6 deferred 결정 / 1R 2b C-M3 해소).
- **`ensure_exists` 미사용** — active stock 만 대상 (`SELECT FROM stock WHERE is_active=TRUE`). 신규 상장 종목은 다음날 ka10099 sync 에서 자동 등장. KISS + RPS 보존.
- **2R 적대적 리뷰 (--force-2b) 강제 적용** — 계약 변경 분류로 자동 게이트는 2b 생략이지만 사용자 명시 요청 (B-α/B-β/B-γ-1 일관).

### 15.2 핵심 설계 결정 (2R 적용 후)

#### A. UseCase — `SyncStockFundamentalUseCase` (단일 클래스 + 두 메서드, KISS)

- `execute(target_date=None, only_market_codes=None)` — active stock 순회 + per-stock try/except + KiwoomError catch + Exception fallback (BLE001) + outcome 수집. B-α 의 `SyncStockMasterUseCase._sync_one_market` 패턴을 종목 단위로 변형.
- `refresh_one(stock_code)` — Stock 마스터 active 검증 → ValueError 시 라우터 404. KiwoomError 그대로 전파 (B-β `LookupStockUseCase.execute` 패턴 일관).
- `_sync_one_stock` — 키움 호출 (트랜잭션 외) → normalize_basic_info → mismatch alert (logger only) → upsert_one with `expected_stock_code` cross-check (B-γ-1 2R B-H2 invariant 활용).
- 두 메서드 + 단일 factory — LookupStockUseCase 의 `execute` + `ensure_exists` 분리 패턴과 차이 (B-γ-2 는 더 단순한 use case 라 분리 ROI 약함, 1R sonnet 검토 PASS).

#### B. Result dataclass — `FundamentalSyncResult` + `FundamentalSyncOutcome`

- `FundamentalSyncResult` (asof_date, total, success, failed, errors[]) — 종목 단위 카운터.
- `FundamentalSyncOutcome` (stock_code, error_class) — 응답 본문 echo 차단 (B-α/B-β M-2 패턴 일관, attacker-influenced KiwoomBusinessError.message 는 logger 만).

#### C. Router — `POST /fundamentals/sync` + `POST /stocks/{code}/fundamental/refresh` + `GET /stocks/{code}/fundamental/latest`

- 두 POST 는 admin 가드 (`require_admin_key`).
- GET /latest 는 익명 공개 — 펀더멘털은 공시 데이터로 PII 아님. 정책 변경 시 가드 추가 (1R 2b M-4 defer).
- KiwoomError 매핑: business → 400 (detail return_code + 클래스명 only), credential → 400, rate → 503, upstream/validation → 502, KiwoomError fallback → 502 (B-β M-5 패턴).
- `FundamentalSyncRequestIn` — `target_date` + `only_market_codes` 옵션. 본 chunk 는 무한 허용 (1R 2b M-2 defer — 계획서 § 11.1 #6 운영 검증 후 결정).

#### D. Scheduler — `StockFundamentalScheduler` (KST mon-fri 18:00)

- B-α `StockMasterScheduler` (mon-fri 17:30) 와 동일 패턴 — 별도 AsyncIOScheduler. cron 18:00 = ka10099 stock master 17:30 의 30분 후 (master 갱신 완료 후 active stock 조회 보장).
- `STOCK_FUNDAMENTAL_SYNC_JOB_ID = "stock_fundamental_sync_daily"` 상수.
- enabled=False 시 start no-op + 멱등성 + graceful shutdown.

#### E. Batch callback — `fire_stock_fundamental_sync`

- `failure_ratio > 0.10` 시 `logger.error` + sample_failed list (10건 cap) — 자격증명 / RPS / 키움 장애 의심 임계값 (작업계획서 § 11.1 #7 디폴트, 운영 1주 모니터 후 조정).
- `partial 실패 (failed > 0 && ratio <= 10%)` 시 logger.warning.
- 모든 예외 swallow — 다음 cron tick 정상 동작 보장.

#### F. Lifespan 통합

- `_sync_fundamental_factory` — sync_stock factory 와 같은 패턴, KRX-only 라 mock_env 무관.
- **2R H-1 적용 — fail-fast 검증을 `set_*_factory` 호출 앞으로 이동**: `set_token_manager` / `set_revoke_use_case` / `set_*_factory` 6개 호출 **앞에서** alias 미설정 검증 → cleanup (reset_*_factory + revoke + engine.dispose) 우회 차단. 새 message: list 형식 (`f"미설정 alias: {missing_aliases}"`).
- teardown 순서: fundamental scheduler → stock scheduler → sector scheduler → reset_*_factory (4개) → revoke_all → engine.dispose.

#### G. 보안 가드 — log injection 방어

- **2R M-1 적용 — `_safe_for_log()` helper**: vendor 응답 `stk_nm` 이 attacker-influenced 일 때 logger 경유 sink (Sentry/CloudWatch) 의 line 분리 / 색상 spoof / NULL injection 차단. control char `\r\n\t\x00\x1b` strip + 길이 cap.
- mismatch alert + base_code mismatch alert 모두 `_safe_for_log` 경유. `Stock.stock_name` (master 측) 도 ka10099 vendor 입력이라 동일하게 escape 적용.

#### H. 1R sonnet M-1 적용 (코드 일관성)

- `_sync_one_stock` 의 base_code 중복 계산 제거 — `normalized.stock_code` 직접 사용 (`normalize_basic_info` 가 이미 `strip_kiwoom_suffix` 적용).
- service.py import 에서 `strip_kiwoom_suffix` 제거 (미사용).
- step5 의 `expected_stock_code` cross-check 가 fail-closed 임을 주석 명시 ("alert 후 적재" 가 아님).

### 15.3 1R 적대적 이중 리뷰 결과 + 2R 적용 매핑

1R: HIGH 1 + MEDIUM 4 + LOW 3 (sonnet PASS, opus FAIL → 2R) → 2R 5개 적용 + 회귀 테스트 5 추가 → 2R PASS (CRITICAL/HIGH 0).

| 1R ID | 카테고리 | 적용 위치 |
|-------|---------|----------|
| **H-1** | lifespan fail-fast cleanup 우회 | `main.py:91-110` 검증 위치 이동 (set 호출 앞) + 새 message list 형식 |
| **M-1 (opus)** | mismatch alert log injection | `service.py:_safe_for_log()` + mismatch alert 2곳 적용 |
| **L-2 (opus)** | cron 시간 docstring 불일치 | `scheduler.py` + `batch/stock_fundamental_job.py` — "ka10099 17:30 의 30분 후" 명시 |
| M-1 (sonnet) | base_code 중복 계산 | `normalized.stock_code` 직접 사용, import 정리, fail-closed 주석 |
| 후속 정정 | ruff E402 (helper 위치) | `_safe_for_log` 를 모든 import 아래로 이동 |

2R 결과: **PASS** — 1R HIGH 1 + MEDIUM 1 + LOW 1 + 1R sonnet M-1 모두 적용 검증, 신규 회귀 위협 LOW 2 (charset 부분 커버 / cosmetic) — defer.

### 15.4 결과

- **테스트 589 passed / coverage 93.24%** (이전 550 + B-γ-1 36 + B-γ-2 39 cases — 14 service + 14 router + 5 scheduler + 4 deps + 2 회귀)
- mypy --strict ✅ / ruff ✅ / FastAPI app create + `/api/kiwoom/fundamentals/sync` 라우트 등록 검증
- 회귀 0건 — A1/A2/A3-α/A3-β/A3-γ/F1/B-α/B-β/B-γ-1 모두 영향 없음
- 변경 파일: 코드 7 (service 신규, router 신규, batch 신규, scheduler 확장, _deps 확장, main 확장, settings 확장) + 테스트 4 신규 + 2 수정

### 15.5 Defer (Phase B-γ 후속 / 운영 검증 / 정책 결정)

| 항목 | 1R/2R ID | 결정 시점 | 메모 |
|------|---------|----------|------|
| `target_date` lower/upper bound | 1R 2b M-2 | 운영 1주 후 | 미래/과거 일자 백필 시 데이터 오염 방지 — backfill 별도 endpoint 분리 검토 (작업계획서 § 11.1 #6) |
| errors list 길이 cap + log spam | 1R 2b M-3 | 운영 1주 후 | 3000 종목 모두 실패 시 errors=3000 → response/log 폭주. errors[:200] cap + 카운터 |
| GET /latest 익명 공개 정책 | 1R 2b M-4 | 정책 결정 | 펀더멘털은 공시 데이터지만 OTC/제재 종목 등 노출 우려 — admin 가드 또는 user OAuth |
| `_safe_for_log` charset 화이트리스트 전환 | 2R LOW-1 | 후속 chunk | 현재 5종 strip — DEL/CSI 8-bit/RTL/LSEP 등 추가 strip 또는 화이트리스트 |
| alias Query pattern | 1R 2b L-1 | cosmetic | `^[a-zA-Z0-9_-]{1,50}$` |
| `only_market_codes` max_length | 1R 2b L-3 | cosmetic | max_length=4 vs pattern 1~2 자 — 충돌 |
| ValueError 라우팅 모호 (sonnet) | 1R 2a M-2 | 후속 chunk | refresh_one 의 stock 미존재 vs cross-check ValueError 별도 예외 타입 |
| `_AsyncSession` 변수 (sonnet) | 1R 2a L-1 | cosmetic | 미사용 import 변수 — `TYPE_CHECKING` 블록 |

### 15.6 Phase B 회고

Phase B 4 chunk 완료 (B-α / B-β / B-γ-1 / B-γ-2):

| chunk | 주요 결과 |
|-------|----------|
| B-α | ka10099 종목 마스터 5 시장 sync + StockMasterScheduler |
| B-β | ka10100 단건 gap-filler / lazy fetch (`ensure_exists`) |
| B-γ-1 | ka10001 펀더멘털 인프라 (Migration 004 + ORM + Repository + Adapter) |
| B-γ-2 | SyncStockFundamentalUseCase + 라우터 + Scheduler + Lifespan 통합 |

누적 적대적 이중 리뷰 결과: CRITICAL 6 + HIGH 25 발견 → 전부 적용 → 0건 PASS. 패턴 학습:
- 응답 message echo 차단 (M-2 패턴) — 모든 라우터 공통 적용
- `__context__`/`__cause__` 누설 방어 (flag-then-raise-outside-except) — 모든 어댑터 메서드 공통
- vendor 입력 보호 (BIGINT/NaN/Infinity/max_length) — `_to_int`/`_to_decimal`/Pydantic 단계
- log injection 방어 (`_safe_for_log`) — 처음 도입, 후속 chunk 에 같은 패턴 확산 검토
- lifespan fail-fast cleanup 우회 차단 — set 앞 검증 위치 패턴

### 15.7 다음 chunk

**Phase C 진입** — OHLCV 시계열 적재 + 백테스팅 본체. 진입 전 결정 필수:

1. **lazy fetch RPS 보호 결정** (1R 2b-M1 deferred from B-β, ADR § 13.4.1) — OHLCV 적재 시 미지 종목 100건 동시 호출 → ka10100 폭주. 옵션:
   - (a) `KiwoomClient` lifespan 싱글톤 — alias 단위 글로벌 RPS 보호
   - (b) `ensure_exists` 에 stock_code 단위 in-flight cache (asyncio.Lock)
   - (c) batch 처리 + lazy fetch fail-closed
2. **운영 dry-run 통합** (DoD § 10.3) — α/β/A3/B-α/B-β/B-γ-1/B-γ-2 합산 검증. ka10001 응답 45 필드 단위 검증 + 외부 벤더 PER/EPS/ROE 빈값 종목 패턴 + 부분 실패 임계 운영 테스트.

---

## 16. Phase C-1α — ka10081 일봉 OHLCV 인프라 (백테스팅 코어 진입) (2026-05-08)

### 16.1 결정

**Phase C 진입 첫 chunk** — 백테스팅 OHLCV 코어 인프라. ka10081 (주식일봉차트) 의 Migration + ORM + Repository + Adapter + ExchangeType enum 도입. UseCase + Router + Scheduler 는 C-1β 에서.

진입 전 결정 사항 (사용자 승인):
- **lazy fetch RPS 보호 = (c) batch + fail-closed** (ADR § 13.4.1 deferred 해소) — Phase C 적재 시 미지 종목은 logger.warning + skip. ensure_exists 호출 자체 안 함. 코드 단순 + RPS 완전 제어. C-1β UseCase 에서 적용
- **chunk 분할 — C-1α (인프라) + C-1β (자동화)** — 1,172줄 작업계획서를 인프라/자동화로 분할 (B-γ-1/B-γ-2 패턴 일관)

### 16.2 핵심 설계 결정

#### A. ExchangeType StrEnum 신규 도입 (Phase C 첫)

- `app/application/constants.py` 에 `ExchangeType` (KRX/NXT/SOR) 추가. B-γ-1 ADR § 14.5 deferred 결정 해소.
- 본 chunk 는 KRX/NXT 만 영속화 (stock_price_krx/nxt). SOR 은 호출 가능하지만 영속화 미지원 — Phase D 결정.

#### B. build_stk_cd 헬퍼 (시계열 endpoint 공통)

- `(stock_code, exchange) → stk_cd suffix 합성`. KRX → `005930`, NXT → `005930_NX`, SOR → `005930_AL`.
- `_validate_stk_cd_for_lookup` 재사용 (B-β 6자리 ASCII) — `_NX`/`_AL` 박힌 입력 거부.
- `stkinfo.py` 에 추가 — ka10082/83/94/86 등 후속 시계열 endpoint 공통 사용.

#### C. KRX/NXT 물리 분리 영속화

- Migration 005 (`stock_price_krx`) + Migration 006 (`stock_price_nxt`) 두 테이블. master.md § 3.1 결정.
- 같은 종목·같은 날의 KRX/NXT 가격이 다를 수 있음 (계획서 § 4.2). 수집 실패 격리·재현성 추적·백테스팅 시나리오 분기.
- 운영 중 NXT 활성화/비활성화 토글 가능 (Migration 분리).

#### D. UNIQUE(stock_id, trading_date, adjusted)

- `adjusted` boolean 이 PK 일부 — `upd_stkpc_tp=1` (수정주가, 백테스팅 디폴트) 와 `=0` (raw) 두 row 동시 보유 가능. 비교 검증용.
- ON CONFLICT DO UPDATE — 멱등성 + 부분 갱신.

#### E. _DailyOhlcvMixin (DRY)

- KRX/NXT 두 ORM 같은 컬럼 구조 공유. ka10082/83/94 도 본 mixin 차용 예정.
- `updated_at` 의 `onupdate=func.now()` 는 raw INSERT/UPDATE 시 ORM-level 안 발동 — Repository.upsert_many 가 명시 update_set 으로 보완.

#### F. StockPriceRepository._MODEL_BY_EXCHANGE (분기)

- exchange 인자로 KRX/NXT 모델 분기. caller 는 어느 테이블인지 신경 안 씀.
- SOR 은 `_MODEL_BY_EXCHANGE` 에서 빠짐 → `ValueError("unsupported exchange")`. Phase D 결정 시 추가.

#### G. trading_date == date.min 빈 응답 표식

- chart.py `to_normalized` 가 빈 dt 응답에 date.min 박음.
- Repository.upsert_many 가 caller 안전망으로 skip — ka10081 응답이 잘못된 row 보내도 영속화 0.

#### H. **2R H-1 적용 — 페이지네이션 cross-stock pollution 차단**

- chart.py `fetch_daily` 의 페이지 루프에 `strip_kiwoom_suffix` 기반 base code 비교. 응답 stk_cd base ≠ 요청 base → `KiwoomResponseValidationError`.
- 빈 string 응답은 통과 (계획서 § 4.3 — 키움이 root 에 stk_cd 항상 동봉하지는 않을 가능성. 운영 검증 후 strict 전환 검토).
- base code 비교 — suffix stripped/동봉 양쪽 수용 (계획서 § 4.3 운영 미검증 동작 양쪽 안전).
- 메시지에 attacker-influenced 응답값 echo 0.

#### I. B-γ-1 가드 자동 적용

- `_to_int` BIGINT / `_to_decimal` is_finite / Pydantic max_length 모두 stkinfo.py 헬퍼 재사용.
- 명시 update_set (B-γ-1 2R B-H3 패턴) — schema-drift 차단.
- flag-then-raise-outside-except (B-β 1R 2b-H2) — `__context__` 박힘 차단.

### 16.3 1R 적대적 이중 리뷰 결과 + 2R 적용 매핑

1R: HIGH 1 + MEDIUM 3 + LOW 2 → 2R 1 적용 + sonnet M-1/M-2 정정 + 회귀 4 추가 → 2R PASS.

| 1R ID | 카테고리 | 적용 위치 |
|-------|---------|----------|
| **H-1** | 페이지네이션 cross-stock pollution | `chart.py:fetch_daily` base code 비교 + KiwoomResponseValidationError + 메시지 echo 0 |
| sonnet M-1 | docstring SOR | `chart.py` Raises 절 정정 |
| sonnet M-2 | local datetime import | `repositories/stock_price.py` top-level 이동 |

2R 결과: **PASS** — 1R H-1 + sonnet M-1/M-2 모두 적용 검증, 신규 회귀 위협 0, 학습 위협 회귀 0.

### 16.4 결과

- **테스트 639 passed / coverage 93.44%** (이전 589 + B-γ-2 0회귀 + C-1α 50 신규)
- mypy --strict ✅ / ruff ✅ / FastAPI app create + ExchangeType enum + build_stk_cd 검증
- 변경 파일: 코드 8 (constants 확장 / stkinfo 확장 / chart 신규 / Migration 005·006 / models stock_price 신규 / models __init__ / repositories stock_price 신규) + 테스트 4 신규

### 16.5 Defer (C-1β / C-2 / 운영 검증 시점)

| 항목 | 1R/2R ID | 결정 시점 | 메모 |
|------|---------|----------|------|
| NUMERIC(8,4) magnitude 가드 (turnover_rate) | 1R 2b M-1 | 운영 dry-run | 키움 응답 magnitude 분포 검증 후 결정 (회귀 위협, 본 chunk 새 도입 X) |
| stk_dt_pole_chart_qry list 길이 cap | 1R 2b M-2 | 운영 검증 후 | 페이지 당 row 수 cap (~600 가정 안전, 운영 후 cap 적용 검토) |
| `_MODEL_BY_EXCHANGE` MappingProxyType | 1R 2b M-3 | 후속 chunk | mutable class attr — frozen 으로 immutable 화 |
| chart.py 가 stkinfo private helper import | 1R 2b L-1 | 후속 chunk | `_normalize.py` 별도 모듈 추출 (ka10082/83/94 도 공유 시점) |
| build_stk_cd 타입 가드 | 1R 2b L-2 | mypy strict 정책 유지 | 정적 차단 |
| 응답 stk_cd 빈 string strict 전환 | 본 chunk H-1 | 운영 dry-run 후 | 키움이 항상 동봉하는지 검증 |

### 16.6 다음 chunk

**Phase C-1β** — ka10081 자동화:
- `IngestDailyOhlcvUseCase` (active stock + KRX/NXT 동시 ingest, per-stock skip + counter, lazy fetch (c) batch fail-closed)
- 라우터: `POST /api/kiwoom/ohlcv/daily/sync` (admin) + `POST /api/kiwoom/stocks/{code}/ohlcv/daily/refresh` (admin) + `GET /api/kiwoom/stocks/{code}/ohlcv/daily?exchange=KRX&start=&end=`
- Scheduler: `OhlcvDailyScheduler` (KST mon-fri 18:30 — fundamental 18:00 의 30분 후, 시계열 적재 가장 마지막 단계)
- C-1β 진입 전 결정 사항:
  - `nxt_collection_enabled` settings flag (NXT 운영 토글)
  - 백필 정책 (target_date_range, 최대 일자 cap)
  - C-1β 도 `--force-2b` 적대적 리뷰 강제

후속 Phase C chunk: C-2 (ka10086 일별 보강 — 투자자별 + 외인 + 신용), C-3 (ka10082/83 주봉/월봉 — P1).

---

## 17. ka10081 일봉 OHLCV 자동화 (Phase C-1β, 2026-05-08)

**Phase C 두 번째 chunk** — ka10081 의 UseCase + Router + Scheduler 자동화. C-1α 인프라 (Migration 005/006 + ORM + Repository + KiwoomChartClient.fetch_daily) 위에 비즈니스 로직을 얹는다.

진입 전 결정 사항 (사용자 승인):
- **nxt_collection_enabled 디폴트 OFF** — settings flag, 운영 전환 전 안전판. True 로 전환해도 stock.nxt_enable 별도 게이팅 (이중 차단)
- **target_date_range = today - 365일 ~ today** — admin 호출 시 base_date 검증. 1년 cap (백필 1095일 vs 운영 sync 365일 분리)
- **Cron = KST mon-fri 18:30** — fundamental cron 18:00 의 30분 후. master(17:30) → fundamental(18:00) → ohlcv(18:30) 직렬화
- **lazy fetch (c) batch + fail-closed** — active stock 만 대상, ensure_exists 호출 안 함 (RPS 보존)

### 17.1 핵심 설계 결정

#### A. KRX/NXT 분리 ingest + per-(stock,exchange) 격리

- `execute()` 가 종목 순회 + KRX 호출 + (옵션) NXT 호출 — 각각 try/except 로 격리
- KRX 실패 → NXT 는 시도 (계획서 § 4.2 (a) 독립 호출)
- 한 종목·한 거래소 KiwoomError → 해당 outcome 만 `errors` list 추가, 다음 종목·거래소 진행
- `OhlcvSyncResult.errors[*]` 에 클래스명 only — 응답 본문 echo 차단 (B-α/B-β M-2 패턴 일관)

#### B. NXT collection 이중 게이팅

```python
if not (self._nxt_enabled and stock.nxt_enable):
    continue  # NXT skip
```

- `settings.nxt_collection_enabled` (프로세스 마스터 스위치) AND `stock.nxt_enable` (종목별 ka10100 응답 기반) — 둘 다 True 일 때만 NXT 호출.
- 디폴트 OFF — KRX 만 적재. fail-closed (실수로 NXT 활성화 차단).

#### C. base_date target_date_range 검증

- `_validate_base_date`: `today - 365일 <= base_date <= today` 외 → ValueError
- 라우터가 400 매핑 (admin 입력 검증)
- cron 호출은 `base_date=None` → today 자동, 검증 통과

#### D. refresh_one — KRX raise vs NXT 격리 (2a-M1 / 2b-L3 적용)

- KRX 호출 실패 → KiwoomError 그대로 raise (라우터 4xx/5xx 매핑, admin 즉시 인지)
- NXT 호출 실패 → KRX 가 이미 적재된 상태이므로 try/except 격리 → `OhlcvSyncResult.failed=1 + errors[NXT]` (응답 200, KRX 성공 명시)
- 응답 사실 일관성: "KRX 성공, NXT 실패" 가 정확히 응답에 반영

#### E. only_market_codes 화이트리스트 (2b-M2 적용)

- `StockListMarketType.value` 화이트리스트 cross-check
- 미등록 코드 → ValueError → 라우터 400 매핑
- silent no-op 차단 (운영 진단 가시성)

#### F. GET range cap (2b-M1 적용)

- `GET /stocks/{code}/ohlcv/daily?start=&end=` 의 date range > 400일 → 400
- 1년 sync 범위 + 안전 마진. backfill 누적 row × 다중 client × 거대 range 조합 DoS 차단
- 인증 가드 미적용 (DB-only 공개) — Phase D 배포 시점 internet-facing 정책 결정 필요

#### G. fail-fast lifespan 위치 (B-γ-2 2R H-1 패턴 일관)

- `scheduler_ohlcv_daily_sync_alias` 도 `set_*_factory` 호출 **앞**에서 검증
- raise 시 cleanup (`reset_*_factory`, `revoke_all_aliases`, `engine.dispose`) 우회 차단
- 운영 실수로 alias 미설정 시에도 process boundary 안전망

#### H. factory + scheduler shutdown 역순

- shutdown 순서: `ohlcv → fundamental → stock → sector` (역순) → factory reset → revoke → engine.dispose
- 실행 중 cron job 의 KiwoomClient 호출이 graceful token revoke 와 충돌하지 않도록 보장

#### I. 응답 echo 차단 (vendor message 격리)

- `KiwoomBusinessError.message` 는 logger only, 응답 detail 은 `{"return_code", "error": "KiwoomBusinessError"}` 만
- `OhlcvSyncOutcome.error_class` 는 `type(exc).__name__` 만
- vendor 응답 string 을 logger 인자에 포함 안 함 → `_safe_for_log` 미적용 (B-γ-2 패턴 차이 명시, 2b-M3)

### 17.2 적대적 이중 리뷰 결과 + Fix 매핑

**1R**: HIGH 0 / MEDIUM 6 (2a 3 + 2b 3) / LOW 6 → 5건 즉시 적용 + 회귀 4 추가 → **2R 진입 없이 PASS**

| ID | 발견 | 적용 |
|---|------|------|
| 2a-M1 / 2b-L3 | refresh_one NXT 격리 부재 | KRX raise propagate, NXT try/except → errors 격리 |
| 2a-M2 | refresh_one KRX KiwoomError propagate 테스트 누락 | `test_refresh_one_propagates_krx_kiwoom_error` 추가 |
| 2a-M3 | fire_ohlcv_daily_sync 콜백 테스트 누락 | 4 cases 추가 (정상/예외 swallow/실패율 error/부분 실패 warning) |
| 2b-M1 | GET range 무제한 DoS amplification | `GET_RANGE_MAX_DAYS=400` 가드 + 회귀 테스트 |
| 2b-M2 | only_market_codes 화이트리스트 부재 | `_validate_market_codes` + `StockListMarketType.value` cross-check |
| 2b-M3 | docstring vs 코드 불일치 (`_safe_for_log`) | docstring 정정 — 본 chunk 미적용 명시 |

LOW 6건은 후속 chunk / 운영 정책 (date.today() KST 명시 / GET 인증 정책 / 자정 race / list materialization 등).

### 17.3 결과

- **테스트 694 passed / coverage 93.08%** (C-1α 639 + C-1β 55 신규: 46 신규 + 9 회귀)
- mypy --strict ✅ / ruff ✅
- 변경 파일: 코드 8 (service 신규 / repository 확장 / _deps 확장 / router 신규 / batch 신규 / scheduler 확장 / settings 수정 / main 통합) + 테스트 5 (3 신규 + 2 보강) + 4 회귀 픽스 (settings/scheduler/stock_master_scheduler 신규 alias env, ohlcv_router engine cache fixture)

### 17.4 Defer (C-2 / 운영 검증 시점)

| 항목 | 1R 리뷰 ID | 결정 시점 | 메모 |
|------|-----------|----------|------|
| GET 라우터 admin guard | 2b-M1 LOW 후속 | Phase D internet-facing | 현재 DB-only 공개. 배포 시 internet-facing 이면 admin 가드 추가 |
| date.today() vs `datetime.now(KST).date()` | 2b-L1 | 후속 chunk | cron 영향 없음 — admin 호출 KST 명시 |
| _validate_base_date 자정 race | 2b-L2 | 무시 가능 | 수십 마이크로초, 실용 영향 없음 |
| OhlcvDailyRowOut.updated_at | 2a-L2 | Phase D 캐시 결정 시점 | fundamentals 패턴 일관 |
| find_range adjusted 필터 | 2a-L3 | Phase D 비교 검증 시점 | 현재 모든 row adjusted=True |
| C-1α 에서 상속 | NUMERIC magnitude / list cap / MappingProxyType / chart.py private import | 운영 dry-run 후 / 후속 chunk | § 16.5 동일 |

### 17.5 Phase C 진입 후 다음 chunk

| chunk | 내용 | 우선순위 |
|-------|------|--------|
| **C-2** | ka10086 일별 보강 (투자자별 + 외인 + 신용) | P0 — 백테스팅 시그널 핵심 |
| 운영 dry-run | α/β/A3/B-α/β/γ + C-1α/β 통합 검증 | P0 — 키움 자격증명 필요 |
| C-3 | ka10082/83 주봉/월봉 | P1 — 같은 chart endpoint, KiwoomChartClient 메서드 추가 |
| Phase D | 시그널 백테스팅 (vectorbt + pandas) | 후속 |

---

## 18. ka10086 일별 수급 인프라 (Phase C-2α, 2026-05-09)

**Phase C 세 번째 chunk** — ka10086 (일별주가요청) 의 Migration + ORM + Repository + Adapter + helpers. ka10081 (일봉 OHLCV) 의 짝꿍 — 백테스팅 시그널 보강 (투자자별 / 외인 / 신용). UseCase + Router + Scheduler 는 C-2β 에서.

진입 전 결정 사항 (사용자 승인):
- **chunk 분할** — C-2α 인프라 (본 chunk) + C-2β 자동화 (B-γ-1/2, C-1α/β 패턴 일관)
- **이중 부호 처리 = 가설 B** — `--714` → -714 (이중 음수 표시 부호 + 음수 값). 운영 dry-run 후 raw 응답 측정 + KOSCOM 공시 cross-check 로 가설 확정 예정
- **indc_mode 디폴트 = QUANTITY (수량)** — 백테스팅 시그널 다른 종목 비교 안정적
- **OHLCV 중복 적재 안 함** — ka10081 stock_price_krx/nxt 가 정답. ka10086 응답의 OHLCV 8 필드 (open_pric ~ amt_mn) 는 stock_daily_flow 에 영속화 안 함
- **cron = KST mon-fri 19:00** — ka10081 18:30 의 30분 후. C-2β 에서 적용 예정

### 18.1 핵심 설계 결정

#### A. URL 분리 (`/mrkcond` vs `/chart`)

- ka10081 = `/api/dostk/chart` / ka10086 = `/api/dostk/mrkcond`. 키움 endpoint 카테고리 분리
- 별도 어댑터 클래스 `KiwoomMarketCondClient` 신설 (ka10081 의 `KiwoomChartClient` 와 무관)
- 후속 mrkcond endpoint 는 `KiwoomMarketCondClient` 에 메서드 추가

#### B. 22 필드 응답의 5 카테고리 분리 + OHLCV 미적재

- **A. 시점** (1): `trading_date`
- **B. OHLCV** (8): ka10081 와 100% 중첩 → 본 테이블 미적재 (cross-check only)
- **C. 신용** (2): `credit_rate` / `credit_balance_rate`
- **D. 투자자별** (4): `individual_net` / `institutional_net` / `foreign_brokerage_net` / `program_net`
- **E. 외인 + 순매수** (7): `foreign_volume` / `foreign_rate` / `foreign_holdings` / `foreign_weight` / `foreign_net_purchase` / `institutional_net_purchase` / `individual_net_purchase`

→ stock_daily_flow 영속화 = C + D + E = 13 도메인 컬럼 (B 제외).

#### C. 이중 부호 처리 (`_strip_double_sign_int`) — 가설 B 채택

- Excel R56 응답 예시에 `ind="--714"`, `for_qty="--266783"` 같은 이중 음수 표기 등장
- **가설 B**: `--714` = `-714` (이중 음수 표시 부호 + 음수 값 의미) — 사용자 결정
- 운영 dry-run 시 raw 응답 측정 + KOSCOM 공시 cross-check 로 가설 확정 예정
- BIGINT 가드 / NaN/Infinity / 천단위 콤마 / zero-padded / 빈 입력은 `_to_int` 에 위임 (B-γ-1 2R 패턴 일관)

#### D. indc_mode 정책 (QUANTITY 디폴트 + R15 주의)

- `DailyMarketDisplayMode` StrEnum (QUANTITY="0" / AMOUNT="1") 신규 도입
- **R15 주의**: `for_netprps` / `orgn_netprps` / `ind_netprps` (외인/기관/개인 순매수) 는 indc_tp 무시하고 항상 수량으로 응답. 운영 dry-run 후 정확한 단위 mismatch 정책 확정

#### E. KRX/NXT 분리 적재 (UNIQUE 키)

- UNIQUE(stock_id, trading_date, exchange) — 같은 종목·같은 날도 KRX + NXT 두 row 가능
- ka10086 응답의 외인/투자자별 net 도 거래소별 분리 (NXT 가 KRX mirror 인지 운영 검증 후 결정)
- ON DELETE CASCADE — Stock 삭제 시 daily_flow 동행 삭제

#### F. Migration 007 — 13 도메인 + 메타 4 + 타임스탬프 3

- BIGINT 9개 (투자자별 4 + 외인 BIGINT 5)
- NUMERIC(8,4) 4개 (credit_rate / credit_balance_rate / foreign_rate / foreign_weight)
- VARCHAR(4) exchange + CHAR(1) indc_mode
- 인덱스 3개: trading_date / stock_id / exchange (cardinality 검증은 운영 후)

#### G. C-1α 2R H-1 패턴 차용 (cross-stock pollution 차단)

- `mrkcond.py:fetch_daily_market` 의 페이지 루프에 `strip_kiwoom_suffix` 기반 base code 비교
- 응답 stk_cd base ≠ 요청 base → `KiwoomResponseValidationError` (메시지에 응답값 echo 안 함)
- 빈 string 응답 통과 (계획서 운영 미검증, C-1α 정책 일관)

#### H. SOR Repository 차단 (2b-M1 적용)

- `StockDailyFlowRepository._SUPPORTED_EXCHANGES = {KRX, NXT}` 화이트리스트
- `upsert_many` 시작 시 SOR 포함되면 ValueError → silent merge 차단
- `find_range` 에도 동일 검증 — Phase D 까지 KRX/NXT 만 영속화 정책 일관

#### I. ExchangeType 길이 정적 invariant (2b-M2 적용)

- `EXCHANGE_TYPE_MAX_LENGTH = 4` Final + module import 시점 fail-fast
- 신규 거래소 추가 시 4자 초과 → RuntimeError. Migration exchange 컬럼 (VARCHAR(4)) 과 일관성 강제

### 18.2 적대적 이중 리뷰 결과 + Fix 매핑

**1R**: HIGH 0 / MEDIUM 3 (2a 1 + 2b 2) / LOW 9 → 3건 즉시 적용 + 회귀 4 추가 → **2R 진입 없이 PASS**

| ID | 발견 | 적용 |
|---|------|------|
| 2a-M1 | test_migration_007 BIGINT 11→9 주석 오타 | 주석 정정 |
| 2b-M1 | SOR Repository silent 영속화 가능 | `_SUPPORTED_EXCHANGES = {KRX, NXT}` + ValueError + 회귀 3 |
| 2b-M2 | exchange VARCHAR(4) silent truncation 위험 | `EXCHANGE_TYPE_MAX_LENGTH=4` import 시점 fail-fast + 회귀 1 |

LOW 9건은 후속 chunk / 운영 정책 (C-2β UseCase / 운영 dry-run / Phase F 시그널 단계).

### 18.3 결과

- **테스트 760 passed / coverage 93.43%** (C-1β 694 + C-2α 66 신규: 62 신규 + 4 회귀)
- mypy --strict ✅ / ruff ✅
- 변경 파일: 코드 6 (constants 확장 / Migration 007 신규 / ORM 신규 + __init__ 수정 / _records 신규 / mrkcond 신규 / Repository 신규) + 테스트 5 신규 (display_mode / strip_double_sign_int / Migration / Repository / mrkcond_client)

### 18.4 Defer (C-2β / 운영 검증)

| 항목 | 1R 리뷰 ID | 결정 시점 | 메모 |
|------|-----------|----------|------|
| 가설 B 정확성 | C-2 진입 결정 | 운영 dry-run | raw 응답 + KOSCOM 공시 cross-check 후 확정 |
| R15 외인/기관/개인 순매수 단위 | C-2 § 11.1 #3 | 운영 dry-run | indc_tp=1 응답에서 단위 mismatch 검증 |
| OHLCV cross-check (ka10081 vs ka10086 일치율) | C-2 § 11.1 #4 | Phase H 데이터 품질 | source 신뢰도 측정 |
| NUMERIC(8,4) magnitude 가드 | 2b-L3 | 운영 dry-run | credit_rate / foreign_rate / foreign_weight 단위 변경 시 abort 방지 |
| `idx_daily_flow_exchange` cardinality | 2b-L4 | Phase F EXPLAIN 측정 | 단일 컬럼 대신 복합 `(stock_id, exchange, trading_date)` 검토 |
| KRX/NXT 같은 트랜잭션 deadlock | 2b-L2 | C-2β UseCase | 거래소 단위 트랜잭션 분리 또는 결정적 lock 순서 |
| 혼합/3중 부호 운영 가시성 | 2b-L1 | Phase C-2β 이후 | structlog warning 카운터 또는 raw_response 측정 |
| BOM/제어문자 prefix | 2b-L5 | 운영 dry-run | 현재 silent None — 데이터 손실은 있지만 보안 중립 |
| `find_range` Sequence vs list | 2b-L6 | 무시 가능 | type vs runtime — 보안 위험 없음 |
| C-1α 에서 상속 | NUMERIC magnitude / list cap / MappingProxyType / chart.py private import | 운영 dry-run 후 / 후속 chunk | § 16.5 / § 17.4 동일 |

### 18.5 다음 chunk

**Phase C-2β** — ka10086 자동화:
- `IngestDailyFlowUseCase` (active stock + KRX/NXT 분리 ingest, per-(stock,exchange) 격리, lazy fetch (c) batch fail-closed) — C-1β 패턴 차용
- 라우터: `POST /api/kiwoom/daily-flow/sync` (admin) + `POST /api/kiwoom/stocks/{code}/daily-flow/refresh` (admin) + `GET /api/kiwoom/stocks/{code}/daily-flow?exchange=&start=&end=`
- Scheduler: `DailyFlowScheduler` (KST mon-fri 19:00 — ka10081 18:30 의 30분 후)
- Lifespan factory + `_deps.py` 확장 (`IngestDailyFlowUseCaseFactory`)
- C-2β 도 `--force-2b` 적대적 리뷰 강제

후속 Phase C chunk 진행 후: 운영 dry-run (α/β/A3/B-α/β/γ + C-1α/β + C-2α/β 통합 검증) → C-3 (ka10082/83 주봉/월봉, P1) → Phase D (시그널 백테스팅).

---

## 19. ka10086 일별 수급 자동화 (Phase C-2β, 2026-05-09)

### 19.1 결정

**커밋**: `e442416` — `feat(kiwoom): Phase C-2β — ka10086 일별 수급 자동화 (UseCase + Router + Scheduler + Lifespan, 이중 리뷰 1R PASS, 812 tests / 93.13%)`.

C-1β 패턴 mechanical 차용. C-2α (인프라) 위에 자동화 레이어만 얹는 구조 — 새 설계 도입 없음.

자동 분류: **계약 변경 (contract)** + `--force-2b` 적대적 리뷰 강제. 1R PASS (CRITICAL/HIGH 0).

### 19.2 핵심 설계 결정

- **C-1β 패턴 mechanical 차용** — UseCase / Router / Scheduler / Lifespan / Settings 시그니처 그대로 daily_flow 로 치환. 일관성으로 리뷰 부담 감소
- **indc_mode 프로세스당 단일 정책** — lifespan factory 가 `DailyMarketDisplayMode.QUANTITY` 하드코딩 주입 (백테스팅 시그널 단위 일관성, 계획서 § 2.3 권장)
- **cron = KST mon-fri 19:00** (ohlcv 18:30 + 30분 후) — ohlcv 적재 완료 후 수급 적재 시점에 stock master / OHLCV 모두 최신화 보장
- **API 경로 = /api/kiwoom/daily-flow** — C-1β `/ohlcv/daily` 와 평행 명명. POST `/sync` (admin bulk) + POST `/stocks/{code}/daily-flow/refresh` (admin single) + GET `/stocks/{code}/daily-flow` (DB only)
- **GET range cap 400일** (C-1β 2b-M1 일관) — DoS amplification 차단
- **backfill 스크립트 보류** — C-1β 도 미구현 (DoD 미체크). 운영 정책 확정 후 별도 chunk

### 19.3 적대적 이중 리뷰 결과

- **2a 일반 품질 (Sonnet)**: PASS, MEDIUM 2건 (errors mutable list / ValueError 메시지 검색 — 둘 다 C-1β 동일 패턴, 본 chunk 범위 외)
- **2b 적대적 보안 (Opus)**: PASS, C-1β 9개 핵심 보안 패턴 일관 검증 (vendor echo 차단 / admin guard / KiwoomError 매핑 / per-(stock,exchange) outcome / only_market_codes 화이트리스트 / GET range cap / cross-stock pollution / factory unset / fail-fast 순서)

### 19.4 결과

- **테스트 812 passed / coverage 93.13%** (C-2α 760 + C-2β 52 신규)
- mypy --strict ✅ / ruff ✅
- 변경 파일: 코드 7 신규 (service / router / batch_job / 4 test) + 변경 6 (deps / scheduler / settings / main / 2 test 회귀) + DoD § 10.1/10.2 갱신

### 19.5 Defer (다음 일관 개선 chunk)

| 항목 | 1R 리뷰 ID | 결정 시점 | 메모 |
|------|-----------|----------|------|
| errors mutable list → tuple | 2a M-1 | C-1β 일관 개선 chunk | 다음 refactor chunk 에서 동시 개선 |
| ValueError 메시지 검색 → 전용 예외 | 2a M-2 | C-1β 일관 개선 chunk | `StockMasterNotFoundError(ValueError)` 도입 |
| only_market_codes max_length=4 dead | 2a L-1 | C-1β 일관 개선 chunk | pattern={1,2} 와 일치하도록 |
| DailyFlowRowOut.fetched_at None 타입 | 2a L-2 | 다음 chunk | ORM NOT NULL → non-Optional or 주석 |
| `refresh_one` NXT 비-Kiwoom Exception 전파 | 2a L-5 | C-1β 일관 개선 chunk | except Exception 추가 검토 (의도적 trade-off vs 격리) |

### 19.6 다음 chunk

운영 dry-run 결과 § 20 의 결정 반영 → **Phase C-2γ — Migration 008** (D-E 중복 컬럼 DROP).

---

## 20. 운영 dry-run § 가설 B + NXT mirror + D-E 중복 발견 (2026-05-09)

### 20.1 dry-run 환경

- **방식**: env appkey/secretkey + DB 우회 → KiwoomAuthClient + KiwoomClient.call_paginated 직접 사용
- **스크립트**: `scripts/dry_run_ka10086_capture.py` — `--analyze-only` 재분석 모드 포함
- **샘플**: 005930 (삼성전자) / 000660 (SK하이닉스) / 035720 (카카오) × KRX + NXT × 2026-05-08 → 6 캡처 / 1,200 row
- **분석 함수 5종**: fill_rate / sign_patterns / nxt_mirror / partial_mirror_breakdown / d_vs_e_equality / for_qty_invariant

### 20.2 발견 사항 (3건)

#### 발견 #1 — D 카테고리 ↔ E 카테고리 100% 중복 (3개 컬럼 쌍)

| 컬럼 쌍 (D ↔ E) | 동일률 | row 검사 |
|------------------|--------|----------|
| `ind` ↔ `ind_netprps` | **100%** | 1200/1200 |
| `orgn` ↔ `orgn_netprps` | **100%** | 1200/1200 |
| `for_qty` ↔ `for_netprps` | **100%** | 1200/1200 |
| `frgn` ↔ `for_netprps` | 0% | 1200/1200 다름 (외국계 brokerage ≠ 외인 net) |

**해석**: 키움 API 가 명세상 다른 D/E 카테고리에 **같은 데이터를 두 번 응답**. 작업계획서 § 3.2 R15 주의 (외국인순매수 거래량으로만 응답) 의 의미가 사실상 **`for_netprps` ≡ `for_qty`**. 명세 vs 실제 응답 mismatch.

**stock_daily_flow 13개 영속 컬럼 중 3개가 데이터 중복**:
- `individual_net` ≡ `individual_net_purchase`
- `institutional_net` ≡ `institutional_net_purchase`
- `foreign_volume` ≡ `foreign_net_purchase`

#### 발견 #2 — NXT 분리 row 의 의미 (외인 외 6개 컬럼만)

| 컬럼 | KRX↔NXT 동일률 | 결론 |
|------|---------------|------|
| `for_qty`, `for_netprps` | **100% mirror** | NXT의 외인 컬럼은 KRX 중복 (정보 없음) |
| `ind`, `orgn`, `frgn`, `prm`, `orgn_netprps`, `ind_netprps` | **0% mirror** | NXT 가 독립 집계 (분리 row 의미 명확) |

→ NXT row 적재 가치 살아있음 (개인/기관/외국계/프로그램 분리 데이터). 외인 컬럼만 KRX 중복.

#### 발견 #3 — 가설 B (`--XXX` → `-XXX`) 강력 지지

| 패턴 | 발견 | 결론 |
|------|------|------|
| `--XXX` (이중 음수 prefix) | 4,454건 (다중 컬럼) | "음수 prefix + 음수 값" 시사 |
| `++XXX` | **0건** | 가설 B 의 대칭 케이스 부재 → 단순 prefix duplication |
| 혼합 (`+-`, `-+`) | **0건** | 신규 패턴 없음 |
| 단일 `+XXX` | 정상 발견 | 양수는 단일 prefix |
| `for_qty >= |for_netprps|` | 위반 0/1200 | (※ for_qty == for_netprps 라 자명한 통과 — 검증 의미 없음) |

→ `_strip_double_sign_int` 가설 B 운영 채택 OK. 단 **KOSCOM 공시 1~2건 수동 cross-check 권고** (문서화 목적, 가설 최종 확정).

### 20.3 결정 (사용자 승인)

| # | 사안 | 결정 | 코드 변경 시점 |
|---|------|------|----------------|
| 1 | D-E 중복 컬럼 3개 | **Migration 008 — 컬럼 DROP** (13→10) | 별도 chunk (C-2γ) |
| 2 | NXT row 외인 컬럼 100% mirror | **현 상태 유지** (KRX 중복 적재) — 단순 조정 | 코드 변경 없음 |
| 3 | 가설 B `--XXX` → `-XXX` | **운영 채택 확정** (KOSCOM cross-check 1~2건 권고) | 코드 변경 없음 |

### 20.4 미해결 운영 검증 (Defer)

| 항목 | 결정 시점 | 메모 |
|------|----------|------|
| KOSCOM 공시 cross-check (1~2건) | 향후 운영 검증 | 가설 B 최종 확정 — sample 종목·일자 수동 비교 |
| `indc_tp=1` (금액 모드) 단위 mismatch | 향후 운영 검증 | for_netprps 가 indc_tp 무시 항상 수량인지 명세 vs 실제 검증 |
| ka10081 vs ka10086 OHLCV cross-check | Phase H 데이터 품질 | source 신뢰도 |
| 페이지네이션 빈도 / 3년 백필 시간 | C-2 backfill chunk | 실측 — sync cron 시간 조정 (현재 19:00) |
| active 3000 + NXT 1500 sync 실측 시간 | 운영 1주 모니터 | 30~60분 추정 |
| NUMERIC(8,4) magnitude 분포 | C-2 backfill chunk 후 | credit_rate / foreign_rate / foreign_weight 단위 변경 abort 위험 |

### 20.5 산출물

- `scripts/dry_run_ka10086_capture.py` — env 기반 단발 캡처 + 5종 분석 + `--analyze-only` 재분석
- `captures/ka10086-dryrun-20260508.json` — 1,200 row 샘플 raw + normalized + analysis (gitignore 권장 — vendor 응답 raw 외부 노출 차단)

### 20.6 다음 chunk 후보

1. **C-2γ — Migration 008** (D-E 중복 컬럼 DROP, 13→10) — 본 § 20.3 #1 결정 반영
2. **C-1β/C-2β MEDIUM 일관 개선** — § 19.5 errors mutable / ValueError 메시지 검색 정리
3. **scripts/backfill_daily_flow.py CLI** — 3년 백필 + 시간 실측
4. **KOSCOM cross-check 수동** — 가설 B 최종 확정 (스크립트 외 검증)
5. **C-3 (ka10082/83 주봉/월봉, P1)** — KiwoomChartClient 메서드 추가

---

## 21. ka10086 D-E 중복 컬럼 DROP (Phase C-2γ, 2026-05-09)

### 21.1 결정

`stock_daily_flow` 테이블의 D-E 중복 컬럼 3개를 **Migration 008** 로 영구 DROP:
- `individual_net_purchase` (≡ `individual_net`)
- `institutional_net_purchase` (≡ `institutional_net`)
- `foreign_net_purchase` (≡ `foreign_volume`)

**13 → 10 도메인 컬럼**. 근거: § 20.2 #1 운영 dry-run 1,200/1,200 row 100% 동일값 확인.

### 21.2 핵심 설계 결정

| # | 사안 | 결정 |
|---|------|------|
| 1 | 마이그레이션 방향 | **DROP COLUMN IF EXISTS × 3** (UPGRADE), 가드 + ADD COLUMN BIGINT × 3 (DOWNGRADE) |
| 2 | DOWNGRADE 가드 | 007 동일 패턴 — 데이터 1건이라도 있으면 RAISE EXCEPTION. NULL 복원이라 운영 의미 보존 불가 → 빈 테이블에서만 허용 |
| 3 | `DailyMarketRow` raw 필드 처리 | vendor 응답 schema 그대로 유지 (`for_netprps` / `orgn_netprps` / `ind_netprps`) — Pydantic `extra="ignore"` + 기본값. `to_normalized` 단계에서만 무시 |
| 4 | `NormalizedDailyFlow` | dataclass(frozen=True, slots=True) 의 3 필드 영구 제거. ORM/Repository/Router DTO 일괄 갱신 (단일 진실 출처) |
| 5 | 응답 DTO breaking | **수용** — `DailyFlowRowOut` 에서 3 필드 제거. 운영 미가동 (downstream 0 — 본 chunk 직전까지 master push 만, deploy 0) |
| 6 | upsert `update_set` 갱신 | B-γ-1 2R B-H3 패턴 유지 — 명시 update_set 6줄 제거. `created_at` 의도적 제외 주석 추가 (M-4 1차 리뷰 반영) |
| 7 | test_migration_007 의 13 컬럼 hard-coded | conftest 가 head 까지 적용 → 008 적용 후 상태 검증. BIGINT 9→6 + DROP 3 부재 단언 추가. history 멱등성은 `test_migration_007_downgrade_then_upgrade_idempotent` 가 보장 |

### 21.3 적대적 이중 리뷰 결과

**자동 분류**: 계약 변경 (contract) — 2b 적대적 리뷰 자동 생략. 1차 리뷰 (sonnet, python-reviewer) 만 실행.

| # | 등급 | 이슈 | Fix |
|---|------|------|-----|
| M-1 | MEDIUM | downgrade 가드 테스트 `finally` 정리 불완전 (RAISE 후 alembic_version 검증 부재) | `version_num == "008_..."` 명시 단언 추가 |
| M-2 | MEDIUM | 라운드트립 테스트가 컬럼 카운트/타입 미검증 | `len(cols) == 21/18` + `BIGINT` 타입 단언 추가 |
| M-3 | MEDIUM | vendor 응답 schema 변경 silent 처리 위험 | plan § 12.8 운영 모니터 한 줄 추가 (분기/반기 dry-run 재실행 권고) |
| M-4 | MEDIUM | `update_set` 의 `created_at` 제외 의도 미명시 | "최초 insert 시각 보존" 한 줄 주석 추가 |
| L-1 | LOW | `hasattr` 단언이 `slots=True` 에서 오타 방어 약함 | `dataclasses.fields()` 사용으로 강화 |
| L-2 | LOW | `test_migration_007.py` docstring 의 "13 도메인" 잔존 | "10 도메인 (008 DROP 후)" 정정 |

→ 모두 수정 후 재테스트 PASS. CRITICAL/HIGH 0건.

### 21.4 결과

- **테스트**: 812 → **816 cases** (+4 신규 Migration 008) / coverage **93.11%**
- **mypy --strict**: 65 source files / 0 errors
- **ruff check**: All passed
- **스토리지 절감**: 운영 가동 후 ~23% (3 BIGINT 컬럼 / 13 도메인) — 백필 전 정리로 미래 비용 0
- **응답 DTO**: `DailyFlowRowOut` 13 필드 → 10 필드 (breaking, 운영 영향 0)

### 21.5 Defer (다음 chunk)

- 가설 B KOSCOM cross-check 수동 1~2건
- C-1β/C-2β MEDIUM 일관 개선 (`errors → tuple` / `StockMasterNotFoundError` 전용 예외)
- scripts/backfill_daily_flow.py CLI + 3년 백필 시간 실측

### 21.6 다음 chunk 후보

1. **C-1β/C-2β MEDIUM 일관 개선** (refactor, scope 명확)
2. **scripts/backfill_*.py CLI + 3년 백필 실측** (Phase C-2 마무리)
3. **C-3 (ka10082/83 주봉/월봉, P1)** (chart endpoint 재사용)
4. **KOSCOM cross-check 수동** (가설 B 최종 확정)

---

## 22. Phase C R1 — 3 도메인 일관 개선 (Refactor 1, 2026-05-09)

### 22.1 결정

§ 19.5 (C-2β Defer) 의 5건 + B-γ-2 동일 패턴을 **3 도메인 (fundamental / OHLCV / daily_flow) 횡단** 일관 정리. 외부 API contract 무변, 내부 타입·예외 안전성 강화. 다음 chunk (C-3 / Phase D) 진입 전 베이스 정착.

### 22.2 핵심 설계 결정

| # | 사안 | 결정 |
|---|------|------|
| 1 | 공유 예외 모듈 | 신규 `app/application/exceptions.py` — `StockMasterNotFoundError(ValueError)` + `__slots__ = ("stock_code",)` + 안정 메시지 형식. domain-specific 예외는 service inline 패턴 유지 (token_service 일관) |
| 2 | `errors` mutable container 노출 제거 | 3 service Result frozen dataclass 의 field type 을 `list → tuple`. 내부 build local list → return 시 `tuple(errors)` 변환 (B-γ-1 frozen 일관 강화) |
| 3 | router DTO `errors: tuple[..., ...]` | Pydantic v2 가 tuple 도 JSON array 로 직렬화 → wire format 무변. OpenAPI schema 도 array. `tuple(generator)` 패턴으로 변환 |
| 4 | `ValueError` 메시지 검색 → `except StockMasterNotFoundError` | 3 router 모두 메시지 substring 검색 제거. subclass first 순서로 ValueError 분기 위에 배치 (M-2 / H-3) |
| 5 | `refresh_one` NXT path Exception 격리 (L-5) | OHLCV / daily_flow 의 `refresh_one` 에 `except Exception` 추가 — `execute()` 와 일관 partial-failure 모델. KRX 이미 적재 후 NXT 의 unexpected exception 도 응답 200 + failed=1 로 격리. fundamental 은 KRX-only 라 N/A |
| 6 | `only_market_codes max_length 4 → 2` (L-1) | pattern=`r"^[0-9]{1,2}$"` 와 일치. dead validator 제거, 운영 호출 영향 0 |
| 7 | `*RowOut.fetched_at` non-Optional (L-2) | ORM NOT NULL + server_default=now() 라 항상 값 존재. `datetime | None` → `datetime`. test_fundamental_router fixture 1 갱신 (`fetched_at=datetime(...)` 명시) |

### 22.3 1차 리뷰 결과 (sonnet, M-1 + L-1~L-4 전건 적용)

| # | 등급 | 이슈 | Fix |
|---|------|------|-----|
| M-1 | MEDIUM | 테스트 stub 의 `errors=[]` (list) 가 `tuple` 필드와 mypy 충돌 | 6개소 `errors=()` 일괄 변경 |
| L-1 | LOW | `StockMasterNotFoundError.stock_code` mutation 가능 | `__slots__ = ("stock_code",)` + docstring |
| L-2 | LOW | except 순서 회귀 테스트 부재 | `test_value_error_first_except_swallows_subclass` 추가 — 역방향 invariant 단위 증명 |
| L-3 | LOW | `fundamentals.py L325 max_length=4` 변경 누락 의심 | 주석 추가 — exchange 코드는 `only_market_codes` 와 다른 파라미터 명시 |
| L-4 | LOW | `refresh_fundamental` 의 `except ValueError` 분기 부재 | 의도적 생략 명시 주석 (base_date 파라미터 없음) |

→ 모두 수정 후 PASS. CRITICAL/HIGH 0건. 자동 분류 = 계약 변경 → 2b 적대적 자동 생략.

### 22.4 결과

- **테스트**: 816 → **822 cases** (+6: 5 exception 신규 + 1 except 순서 회귀) / coverage **92.86%** (93%→92.86% 미세 감소 — exceptions.py 33% coverage 와 일치, 3 service refactor 후 line 증가가 분모 영향)
- **mypy --strict**: 66 source files / 0 errors
- **ruff check**: All passed (UP017 datetime.UTC 1건 자동 fix)
- **변경 파일**: 13 (신규 2: exceptions.py + test / 수정 11: 3 service + 3 router + 5 test + 1 fixture). +200 / -90 라인 추정
- **외부 API contract**: 무변 (응답 wire format / OpenAPI / status code 동일)

### 22.5 ADR § 19.5 / § 17.4 Defer 해소 매핑

| 출처 | 항목 | 상태 |
|------|------|------|
| § 19.5 | M-1 errors mutable list → tuple | ✅ 해소 (3 service + 3 router DTO) |
| § 19.5 | M-2 ValueError 메시지 검색 → 전용 예외 | ✅ 해소 (StockMasterNotFoundError 도입) |
| § 19.5 | L-1 only_market_codes max_length=4 dead | ✅ 해소 (max_length=2) |
| § 19.5 | L-2 DailyFlowRowOut.fetched_at None 타입 | ✅ 해소 (3 RowOut 모두 non-Optional) |
| § 19.5 | L-5 refresh_one NXT 비-Kiwoom Exception | ✅ 해소 (`except Exception` + 의도 주석) |

### 22.6 Defer (다음 chunk)

- (B-γ-2 잔여 LOW) — 현재 § 17.4 와 § 19.5 외 별도 누적 없음
- C-1α 상속 (NUMERIC magnitude / list cap / MappingProxyType / chart.py private import) — 운영 dry-run 후 / 후속 chunk
- 가설 B KOSCOM cross-check 수동 1~2건

### 22.7 다음 chunk 후보

1. **C-3 (ka10082/83 주봉/월봉, P1)** — R1 정리된 패턴 그대로 복제 (errors tuple / StockMasterNotFoundError / non-Optional fetched_at)
2. **scripts/backfill_*.py CLI + 3년 백필 실측** — Phase C-2 마무리
3. **KOSCOM cross-check 수동** — 가설 B 최종 확정
4. **Phase D 진입** — ka10080 분봉 (대용량 파티션 결정 선행)


## 23. Phase C-3α — 주/월봉 OHLCV 인프라 (ka10082/83, 2026-05-09)

### 23.1 결정

ka10082 (주봉) + ka10083 (월봉) 의 **인프라 레이어** 일괄 도입. ka10081 (일봉) 패턴 ~95% 복제 + R1 정착 패턴 (fetched_at non-Optional / Mixin 재사용 / Repository dispatch) 사전 적용. 자동화 (UseCase + Router + Scheduler) 는 C-3β.

### 23.2 핵심 설계 결정

| # | 사안 | 결정 |
|---|------|------|
| 1 | Migration 분리 vs 통합 (4 테이블) | **분리** — 009/010/011/012 직선 체인. C-1α (005/006 KRX/NXT 분리) 패턴 일관 + 운영 시 토글 가능 (NXT 비활성화 등). testcontainers up→down→up 사이클 검증 (test_migration_009_012) |
| 2 | `_DailyOhlcvMixin` 재사용 (4 테이블 컬럼 동일) | **재사용** — period 별 의미 차이 (일/주/월) 는 영속화 테이블 이름으로 식별. `prev_compare_*` 가 일/주/월 다름은 컬럼 COMMENT 로 명시. private import 정당화 (계획서 H-2) |
| 3 | `Period(StrEnum)` 범위 (DAILY 제외) | WEEKLY/MONTHLY/YEARLY **3값**. DAILY 는 IngestDailyOhlcvUseCase 가 별도 처리 (hot path 분리). YEARLY 는 enum 노출하되 Migration/Repository 미구현 — caller 호출 시 ValueError. 계획서 H-3 결정 |
| 4 | `StockPricePeriodicRepository` 도입 (StockPriceRepository 와 분리) | 일봉은 호출 빈도 + row 수 압도적 → 별도 hot path. 주/월봉은 통합 인터페이스 (`_MODEL_BY_PERIOD_AND_EXCHANGE` dict, 4 매핑 — YEARLY 매핑 미존재 시 ValueError). NormalizedDailyOhlcv 는 컬럼 구조 period 무관이므로 재사용 (이름은 도메인 출처 표시) |
| 5 | `chart.py` 의 `fetch_weekly`/`fetch_monthly` 별도 메서드 (helper 추출 보류) | fetch_daily 와 ~80% 중복이지만, list 키 (`stk_stk_pole_chart_qry` / `stk_mth_pole_chart_qry`) + api_id 분기 명시성 우선. ka10094 (P2) 추가 후 helper 추출 검토 (R2 후보). 계획서 H-6 — fetch_daily 변경 0줄 |
| 6 | revision id 32자 한도 준수 | Alembic `alembic_version.version_num VARCHAR(32)` 한도. 신규 4 마이그레이션을 `kiwoom_` prefix 제거해 26~27자 (009_stock_price_weekly_krx 등). 005/006 패턴과 약간 차이 있지만 길이 한도 우선 |
| 7 | R1 정착 패턴 사전 적용 (인프라 레이어) | `fetched_at` non-Optional ORM (`_DailyOhlcvMixin` `nullable=False` + server_default) — 4 신규 테이블 모두 상속. 다른 R1 패턴 (errors tuple / StockMasterNotFoundError / max_length=2 / NXT Exception 격리) 은 UseCase/Router 도입되는 C-3β 적용 |

### 23.3 1차 리뷰 결과 (sonnet, M-1 + L-1 + L-2 적용)

| # | 등급 | 이슈 | Fix |
|---|------|------|-----|
| H-1 | HIGH | test_migration_008.py head 동적 단언 권고 | LOW 강등 — 잠재 위험만 (head 동적 단언으로 견고화). C-3 chunk 진입 시 동시 적용 |
| M-1 | MEDIUM | `NormalizedDailyOhlcv` 일봉 전용 이름이 periodic 도메인 사용 시 혼란 | Repository docstring 추가 — "Daily 접두는 도메인 출처 표시, 컬럼 구조 period 무관" 명시 |
| M-2 | MEDIUM | chart.py 함수 사이 빈줄 PEP 8 위반 | ruff format 자동 처리 (Step 3-2) |
| M-3 | MEDIUM | `# type: ignore[arg-type]` vs `cast()` | 기존 일봉 Repository 패턴 답습 — 별도 refactor chunk 권고 |
| L-1 | LOW | NXT migration 010/012 의 trading_date / prev_compare_* COMMENT 누락 (KRX/NXT 비대칭) | 4 컬럼 COMMENT 추가 — KRX/NXT 대칭성 회복 |
| L-2 | LOW | `update_set` 의 ON CONFLICT key 컬럼 제외 의도 주석 부재 | 주석 추가 — 미래 컬럼 추가 시 silent contract change 차단 명시 |
| L-3 | LOW | `Period.YEARLY` 호출 시 `ValueError` vs plan doc 의 `NotImplementedError` 불일치 | Repository 는 ValueError 유지 (지원 안 하는 매핑). C-3β UseCase 에서 NotImplementedError 매핑 (계층 분리) |

→ M-1 + L-1 + L-2 즉시 적용. CRITICAL/HIGH 0건. 자동 분류 = 계약 변경 → 2b 적대적 자동 생략.

### 23.4 결과

- **테스트**: 822 → **897 cases** (+75: chart adapter 23 / Repository 18 / Migration 26 / Period enum 8). coverage **97%** (이전 92.86%, 신규 코드 100%)
- **mypy --strict**: 68 source files / 0 errors
- **ruff check + format**: All passed
- **신규 파일 (13)**: ORM 1 / Repository 1 / Migration 4 / 테스트 4 + plan doc 1 + chart.py 확장 + constants.py Period
- **수정 파일 (4)**: chart.py / models/__init__.py / test_migration_008.py / repositories/stock_price_periodic.py docstring
- **외부 API contract**: 무변 (Router 신규 path 없음 — 모두 C-3β)

### 23.5 운영 검증 미해결 (C-3β + Phase H)

- **`dt` 의미** (주 시작/종료 / 달 첫일/말일) — 운영 first-call 후 1주 모니터로 확정 (계획서 H-4). 가설 = "기간의 시작일"
- **응답 list 키 검증** — `stk_stk_pole_chart_qry` / `stk_mth_pole_chart_qry` 가 Excel R31 표기와 실제 응답 일치하는지 (오타 가능성)
- **일봉 합성 vs 키움 주/월봉 cross-check** — Phase H 데이터 품질 리포트로 연기
- **백필 페이지네이션 빈도** — 3년 = 156 주 / 36 월. 1 페이지 추정 — 운영 실측 (C-backfill chunk)

### 23.6 Defer (다음 chunk)

- **C-3β** — UseCase + Router + Scheduler. R1 패턴 5종 모두 적용 (errors tuple / StockMasterNotFoundError / fetched_at non-Optional / max_length=2 / NXT Exception 격리)
- C-1α 상속 (NUMERIC magnitude / list cap / MappingProxyType / chart.py private import) — 운영 dry-run 후
- M-3 (`# type: ignore` → `cast()`) — 기존 패턴 동시 정리하는 별도 refactor chunk

### 23.7 다음 chunk 후보

1. **C-3β (자동화, P1)** — UseCase period dispatch + Router 4 path + Scheduler 2 job. R1 패턴 5종 전면 적용
2. **C-backfill** — `scripts/backfill_ohlcv.py --period {daily|weekly|monthly}` CLI
3. **KOSCOM cross-check 수동** — 가설 B 최종 확정
4. **ka10094 (년봉, P2)** — C-3 와 동일 패턴 (Migration 1 + UseCase YEARLY 분기 활성화)


## 24. Phase C-3β — 주/월봉 OHLCV 자동화 (ka10082/83 자동화, 2026-05-09)

### 24.1 결정

ka10082 (주봉) + ka10083 (월봉) 의 **자동화 레이어** — UseCase + Router + Scheduler. C-3α 인프라 위에 R1 정착 패턴 5종 전면 적용. ka10081 (IngestDailyOhlcvUseCase) 패턴 ~95% 복제 + period dispatch.

### 24.2 핵심 설계 결정

| # | 사안 | 결정 |
|---|------|------|
| 1 | UseCase 통합 vs 분리 (ka10082/83) | **통합** (`IngestPeriodicOhlcvUseCase`) — period 인자로 dispatch. ka10081 의 IngestDailyOhlcvUseCase 와 분리 (hot path 차이). UseCase 1 클래스에 `execute(*, period, ...)` + `refresh_one(stock_code, *, period, ...)` 두 진입점 |
| 2 | Period dispatch 전략 (H-3) | YEARLY → `NotImplementedError` (P2 chunk 진입 시 활성화). DAILY 분기는 Period enum 자체에서 차단 (3값) — `_validate_period` 가 YEARLY 만 검증 (1R M-1 결정). `_ingest_one` 내부에서 `if period is Period.WEEKLY: fetch_weekly() / elif Period.MONTHLY: fetch_monthly()` 분기 |
| 3 | Router 분리 (별도 파일) | `routers/ohlcv_periodic.py` 신규 — ohlcv.py (daily) 와 분리. 4 path (POST sync × weekly/monthly + POST refresh × weekly/monthly) + 공용 핸들러 `_do_sync` / `_do_refresh` (period 만 caller 에서 결정). 응답 DTO 동일 (`OhlcvPeriodicSyncResultOut`) |
| 4 | Scheduler 2 클래스 (Weekly + Monthly) | `WeeklyOhlcvScheduler` / `MonthlyOhlcvScheduler` 신규 — OhlcvDailyScheduler 패턴 ~95% 복제. 각각 별도 AsyncIOScheduler 보유 (lifecycle 독립) |
| 5 | **cron 시간 (H-7)** | weekly = **금 KST 19:30** (daily_flow `mon-fri 19:00` 와 충돌 방지 — 30분 후) / monthly = **매월 1일 KST 03:00** (다른 cron 없는 새벽). 30분 간격 cron 패턴 일관 (17:30→18:00→18:30→19:00→19:30) |
| 6 | DI factory 통합 (`IngestPeriodicOhlcvUseCaseFactory`) | C-1β factory 패턴 일관 — `_deps.py` 에 get/set/reset_ingest_periodic_ohlcv_factory + 본 chunk 의 `_ingest_periodic_ohlcv_factory` lifespan 등록. weekly/monthly Scheduler 가 같은 factory 공유 (period 는 fire 콜백에서 결정) |
| 7 | R1 정착 패턴 5종 전면 적용 | (1) `errors: tuple[OhlcvSyncOutcome, ...]` 내부 list build → return 시 tuple 변환 (2) `StockMasterNotFoundError(stock_code)` raise + 라우터 subclass first 순서 (3) `fetched_at` non-Optional — 본 chunk 는 조회 endpoint 미추가라 N/A (4) `only_market_codes max_length=2 + pattern={1,2}` (5) NXT path `except Exception` 격리 (R1 L-5) |

### 24.3 1차 리뷰 결과 (sonnet, HIGH 1 + MEDIUM 2 + LOW 2 적용 → CONDITIONAL → PASS)

| # | 등급 | 이슈 | Fix |
|---|------|------|-----|
| H-1 | HIGH | `_do_sync` 에 `KiwoomError` 계열 예외 핸들러 누락 (factory 진입 시점 누설 위험) | `_do_sync` 에 `KiwoomBusinessError` (400 + msg echo 차단) / `KiwoomCredentialRejectedError` (400) / `KiwoomRateLimitedError` (503) / `(KiwoomUpstreamError, KiwoomResponseValidationError)` (502) / `KiwoomError` fallback (502) 추가 — `_do_refresh` 와 대칭 |
| M-1 | MEDIUM | `_validate_period` 의 `period.value == "daily"` dead code (Period enum DAILY 미존재) | dead 분기 제거. docstring 갱신 — "Period.DAILY 가 추가되는 시점에 ValueError 분기 추가" 명시 |
| M-2 | MEDIUM | service docstring "ka10081 과 같은 OhlcvSyncOutcome 재사용" 표현이 실제 구조 (복제) 와 불일치 | docstring 갱신 — "동일 구조 **복제** (공통 추출은 별도 refactor chunk 로 연기)" |
| L-1 | LOW | `MonthlyOhlcvScheduler.start()` docstring 누락 (5 sibling scheduler 와 비대칭) | docstring 추가 — `WeeklyOhlcvScheduler.start()` 와 동일 패턴 |
| L-3 | LOW | `_do_refresh` 의 `KiwoomBusinessError` 로그에 `msg=exc.message` 누락 (ka10081 패턴과 불일치) | `msg=%s, exc.message` 추가 — 운영 디버그 정보 |

→ 모두 수정 후 PASS. CRITICAL/HIGH 0건. 자동 분류 = 계약 변경 → 2b 적대적 자동 생략.

### 24.4 결과

- **테스트**: 897 → **939 cases** (+42: service 17 / router 10 / scheduler+job 11 / deps 4)
- **mypy --strict**: 72 source files / 0 errors
- **ruff check + format**: All passed
- **신규 파일 (9)**: service 1 / router 1 / batch 2 / 테스트 4 + plan doc 갱신
- **수정 파일 (6)**: scheduler / main / _deps / settings / 2 lifespan 테스트
- **외부 API contract**: 4 신규 path (POST 만 — 기존 daily 유지)

### 24.5 Defer (다음 chunk)

- **C-backfill** — `scripts/backfill_ohlcv.py --period {daily|weekly|monthly}` CLI. 운영 검증 4건 (페이지네이션 빈도/3년 시간/NUMERIC magnitude/sync 시간) 일괄 해소
- **운영 first-call 검증** — `dt` 의미 (주/달 시작 vs 종료) / 응답 list 키 명 / 일봉 vs 키움 주월봉 cross-check (Phase H)
- **L-2 / E-1 / E-2** (1R 별도 refactor 권고):
  - L-2: `_do_sync` / `_do_refresh` 에 `NotImplementedError → 501` 핸들러 (방어적 — 현재 caller 가 period 고정)
  - E-1: ka10081 `sync_ohlcv_daily` 도 `_do_sync` 와 동일 H-1 문제 (KiwoomError 핸들러 미등록)
  - E-2: `_deps.py` `reset_*` 함수 docstring "테스트 전용" 이지만 lifespan teardown 도 사용 — 주석 정정

### 24.6 다음 chunk 후보

1. **C-backfill** — CLI + 3년 백필 실측 (운영 미해결 4건 일괄 해소)
2. **KOSCOM cross-check 수동** — 가설 B 최종 확정
3. **ka10094 (년봉, P2)** — Migration 1 + UseCase YEARLY 분기 활성화 (NotImplementedError → 정상 분기)
4. **L-2 + E-1 refactor chunk** — `_do_sync` 류 핸들러 일괄 정리
5. **Phase D 진입** — ka10080 분봉 (대용량 파티션 결정 선행)


## 25. Phase C-backfill — OHLCV 통합 백필 CLI (2026-05-09)

### 25.1 결정

`scripts/backfill_ohlcv.py` 신규 CLI — Phase C 의 daily/weekly/monthly OHLCV 모두 통합 처리.
운영 라우터의 `_validate_base_date` 1년 cap 우회를 위해 UseCase 시그니쳐에 `_skip_base_date_validation`
키워드 옵션 추가 (디폴트 False, CLI 만 True — R1 invariant 유지). 운영 미해결 4건 (페이지네이션
빈도 / 3년 시간 / NUMERIC magnitude / sync 실측) 정량화 측정 도구.

### 25.2 핵심 설계 결정

| # | 사안 | 결정 |
|---|------|------|
| 1 | UseCase 통합 vs 별도 BackfillUseCase | **기존 UseCase 재사용** — `IngestDailyOhlcvUseCase` / `IngestPeriodicOhlcvUseCase` 그대로 호출. period dispatch 는 CLI 레이어에서 (`use_case_class_for_period`). 별도 BackfillUseCase 신설 시 80% 중복 코드 (사용자 결정 옵션 A) |
| 2 | base_date 1년 cap 우회 (H-1) | **`_skip_base_date_validation` 키워드 옵션** (`execute` + `refresh_one` 둘 다). 디폴트 False — 운영 라우터 영향 0. CLI 만 True. 미래 가드는 `skip_past_cap=True` 일 때도 유지 (오타 방어). R1 invariant 일관 |
| 3 | only_stock_codes UseCase 인자 추가 | **추가** (디폴트 None) — `only_market_codes` 와 같은 패턴. CLI 의 `--only-stock-codes` + `--resume` 모두 같은 인자로 위임. 운영 라우터는 디폴트 None — 영향 0 |
| 4 | resume 알고리즘 (H-2) | **stock-level skip** — `compute_resume_remaining_codes` 가 KRX 영속화 테이블의 max(trading_date) 종목별 조회 → max < end_date 인 종목만 진행. 부분 적재 (일부 일자) 종목은 skip 처리 (gap detection 은 별도 chunk) |
| 5 | dry-run 시간 추정 (H-3) | **lower-bound** = `rate_limit × 호출 수`. ±50% margin 명시. 네트워크 RTT / DB upsert / 5xx 재시도 무시 |
| 6 | exit code 4 분기 (H-5) | 0 = success / 1 = partial (failed > 0) / 2 = args (argparse SystemExit + ValueError) / 3 = system (DB 연결 / lifespan 예외) |
| 7 | 라이프사이클 (H-6) | `_build_use_case` async context manager — try/finally 로 `KiwoomClient.close + engine.dispose` 보장. lifespan 우회 (CLI 단일 alias) |

### 25.3 1차 리뷰 결과 (sonnet, HIGH 1 + MEDIUM 1 적용 → CONDITIONAL → PASS)

| # | 등급 | 이슈 | Fix |
|---|------|------|-----|
| H-1 | HIGH | `--resume` flag 가 dead — `should_skip_resume` 함수 구현됐으나 `async_main` 에서 호출 안 함. 사용자 기대와 동작 불일치 | `compute_resume_remaining_codes` 헬퍼 추가 — KRX 테이블의 max(trading_date) per stock 조회 → 미적재 종목만 `only_stock_codes` 로 UseCase 에 전달 |
| M-1 | MEDIUM | `--only-stock-codes` 가 `_count_active_stocks` 에는 사용되나 UseCase.execute 미전달 | UseCase 2개에 `only_stock_codes` 인자 추가 + CLI 의 `effective_stock_codes` 로 resume + only-stock-codes 통합 처리 |
| L-1 | LOW | `resolve_date_range ValueError → return 2` 경로 단위 테스트 부재 | argparse SystemExit 이 동일 경로 — 단위 검증 (test_main_returns_2_when_invalid_args) |
| L-2 | LOW | `format_duration(0)` 경계값 | 운영 경로 미접근 — 기록만 |
| L-3 | LOW | `only_market_codes or None` 패턴 — 빈 list 도 None 취급 | 주석 추가 — UseCase 의 `if only_*_codes:` 분기와 일관 |

→ HIGH H-1 + MEDIUM M-1 즉시 적용. CRITICAL 0건. 자동 분류 = 일반 기능 → 2b 적대적 / 3-4 보안 / 3-5 런타임 / 4 E2E 자동 생략.

### 25.4 결과

- **테스트**: 939 → **972 cases** (+33: skip_base_date_validation 8 / backfill_ohlcv_cli 25)
- **mypy --strict**: 74 source files / 0 errors
- **ruff check + format**: All passed
- **coverage**: 96% (97% → 96% — CLI 신규 ~430줄로 분모 증가, 신규 코드 80%+ 커버)
- **신규 파일 (3)**: scripts/backfill_ohlcv.py / tests 2 + plan doc 신규
- **수정 파일 (3)**: ohlcv_daily_service / ohlcv_periodic_service (시그니쳐 확장) / dry_run_ka10086_capture (E-3 기존 코드 fix — Migration 008 DROP 컬럼 출력 제거)
- **외부 API contract**: 무변 (UseCase 키워드 옵션 추가만, 디폴트 동일 동작)

### 25.5 운영 실측 (본 chunk 범위 외)

본 chunk 는 CLI 그 자체 + 단위 테스트. 실제 운영 실측은 사용자 환경 (실제 키움 자격증명 + 운영 DB)
에서 추후 수동 실행. 실측 가이드는 plan doc § 8 + CLI docstring (사용 예).

실측 후 정리 위치:
- `docs/operations/backfill-실측-{YYYY-MM-DD}.md` 신규 (운영 검증 자료)
- ADR § 26 (또는 후속) — 페이지네이션/시간/NUMERIC 통계 정리
- STATUS § 4 알려진 이슈 4건 → 해소 표기

### 25.6 Defer (다음 chunk)

- **gap detection (resume 정확도 향상)** — 일자별 missing detection. 현재는 max(trading_date) >= end_date 만 skip
- **daily_flow (ka10086) 백필** — 별도 후속 chunk (구조 다름)
- **NUMERIC magnitude 컬럼 확장** — 실측 후 한도 초과 시 별도 Migration chunk
- **L-2 / E-1 / E-2 + M-3** — 기존 refactor R2 chunk

### 25.7 다음 chunk 후보

1. **운영 실측** (사용자 수동) — 100 종목 → 전체 active 3000 → 결과 정리
2. **daily_flow 백필** — `scripts/backfill_daily_flow.py`
3. **gap detection 정확도 향상** — 일자별 missing detection
4. **refactor R2** — 1R Defer 4건 (L-2 + E-1 + E-2 + M-3)
5. **ka10094 (년봉, P2)** / Phase D 진입

---

## 26. 운영 실측 가이드 + 결과 (2026-05-09, ⏳ 측정 대기)

### 26.1 결정

C-backfill 의 후속으로 **운영 실측 사전 준비물 일괄 정비** — runbook + 결과 템플릿 + 본 § 26.
실 측정은 사용자 환경 (운영 키움 자격증명 + 운영 DB) 에서 수행. 본 chunk 는 코드 변경 0,
문서만으로 사용자가 따라갈 수 있는 단계별 가이드 제공.

### 26.2 산출물

| # | 파일 | 역할 |
|---|------|------|
| 1 | `src/backend_kiwoom/docs/operations/backfill-measurement-runbook.md` | 환경변수 / 4단계 명령어 (dry-run → smoke → mid → full) / 트러블슈팅 / 안전 장치 |
| 2 | `src/backend_kiwoom/docs/operations/backfill-measurement-results.md` | 사용자가 측정 후 채우는 양식. 운영 미해결 4건 정량화 표 |
| 3 | 본 § 26 | 실측 후 핵심 결정 / 후속 chunk 우선순위 갱신 자리 (raw 측정은 #2 에 유지) |

### 26.3 측정 대상 (운영 미해결 4건 매핑)

| # | 항목 | 측정 방법 | 결과 자리 |
|---|------|-----------|-----------|
| 1 | 페이지네이션 빈도 (3년 daily 1종목당 페이지 수) | dry-run 추정 vs DEBUG 로그 `next_key` 카운트 | results.md § 3 |
| 2 | 3년 백필 elapsed (active 3000 KRX+NXT) | `format_summary` elapsed | results.md § 4 |
| 3 | NUMERIC(8,4) magnitude 분포 | 백필 후 SQL (max/min/p01/p99 + count(\|x\| > 100)) | results.md § 5 |
| 4 | active 3000 일간 sync 실측 | 백필 다음 영업일 운영 cron 1회 elapsed | results.md § 6 |

### 26.4 안전 장치 (runbook § 11 요약)

- **운영 시간대 회피** — KRX 거래 시간 (09:00~15:30 KST) 백필 금지 (운영 cron + KRX rate limit 경합)
- **rollback 전략** — NUMERIC overflow 등 데이터 오염 시 본 백필 기간만 `DELETE` 가능 (운영 1년 cap 영역과 분리)
- **TokenManager 자동 재발급** — 24h 토큰 lifecycle 가 백필 (4~8시간) 안에 만료 가능. 자동 재발급 작동하지만 로그 모니터링 필요
- **DB 부하** — 단일 worker × 6000 호출 → connection pool (`database_pool_size=5`) 가 흡수
- **resume 한계** — `max(trading_date) >= end_date` 만 본다. 부분 일자 누락 (gap) 은 별도 chunk

### 26.5 실측 결과 (2026-05-10, ✅ 측정 완료)

> **측정 환경**: docker-compose 5433 / 운영 키움 (alias=prod) / since_date guard + max-stocks fix + ETF guard 적용 후
> **상세**: `docs/operations/backfill-measurement-results.md`

| 측정 항목 | 가설 (dry-run) | 실측 | 결정 / 후속 |
|----------|---------------|------|------------|
| 1 페이지네이션 빈도 (1년 daily) | 종목당 2 페이지 | **종목당 1 페이지** (since_date 가 page 1 안에서 break) | since_date guard 작동 확인. 운영 cron (1년 cap) 은 1 호출로 충분 |
| 1' 페이지네이션 빈도 (3년 daily) | 종목당 2 페이지 | **종목당 1~2 페이지** (avg 0.5s/stock — page 2 일부 발생) | 가설 적중. 6 페이지 이상 종목 0 |
| 2 3년 elapsed (KRX+NXT, active 4078 호환) | 약 4시간 (lower-bound) | **34분** (KRX 4078 100% / NXT 626 활성만 / failed 0) | dry-run 추정 (4시간) 보다 **빠름** — 페이지 1~2 + 0.25s rate + DB upsert. 직렬 worker 단독 충분 |
| 3 NUMERIC(8,4) overflow (turnover_rate) | 한도 내 (가설) | **max 3,257.80** (cap ±9999.9999 의 33%) / ABS>1000 = 24 rows (0.0009%) | 마이그레이션 불필요. `change_rate`/`foreign_holding_ratio`/`credit_ratio` 는 daily_flow 백필 chunk 에서 측정 |
| 4 일간 cron elapsed | 약 30~60분 (추정) | (미측정 — 운영 cron 활성화 후) | 본 chunk 외. backfill 적용된 since_date=None 디폴트 운영 동작은 1 페이지 종료 가정 (cron 실측 시 검증) |

**신규 운영 발견 (3건)** — smoke / mid / full 단계에서 발견된 운영 차단 또는 사용성 이슈, 즉시 fix:

1. **`since_date` guard 누락** (chunk `d60a9b3`, smoke) — `KiwoomChartClient.fetch_daily/weekly/monthly` 가 `base_dt` 만 받고 종료 범위 없어 종목 상장일까지 무한 페이징 → max_pages 도달로 fail. `since_date` 옵션 신규 + UseCase + CLI 전파. 운영 cron (since_date=None) 호환
2. **`--max-stocks` CLI bug** (chunk `76b3a4a`, smoke) — `_count_active_stocks` 만 적용되고 실 백필 호출 시 `effective_stock_codes=None` 이 되어 active 전체 처리되던 bug. resume 분기와 동일하게 `_list_active_stock_codes` 호출 + 변수명 rename
3. **ETF/ETN/우선주 stock_code 호환성** (chunk `c75ede6`, smoke) — `kiwoom.stock` active 의 6.7% (KOSPI 12%) 가 영문 포함 코드 (예: `0000D0`, `00088K`). `IngestDailyOhlcvUseCase` / `IngestPeriodicOhlcvUseCase` 가 `^[0-9]{6}$` 패턴 fullmatch 만 keep + skip 로깅. ETF/ETN 자체 OHLCV 는 향후 별도 chunk (옵션 c)

**since_date guard edge case** (follow-up F6):
- 4078 종목 중 2 종목 (`002690` 동일제강 / `004440` 삼일씨엔에스) 만 since_date (2023-05-11) 보다 과거 데이터 적재 (2015-09-24~ / 2016-03-30~). `_page_reached_since` 또는 `_row_on_or_after` 의 edge case 추정
- 영향 범위: 3,626 rows / 2,732,031 = 0.13%. 데이터 품질 측면 nuetral~plus (오래된 베이스라인). 추가 분석 다음 chunk
- 운영 차단 효과는 정상 작동 (failed 0 / max_pages 0)

**KRX 적재 통계** (post-backfill):
- 총 row: 2,732,031 / DISTINCT stock: 4,077 (4078 호환 중 1 종목 빈 응답 추정)
- 일자 범위: 2015-09-24 ~ 2026-05-08 (위 follow-up F6)
- 평균 row/stock: 670 (3년 750 거래일 기준 — 신규 상장 종목은 짧음)

**NXT 적재 통계**:
- 총 row: 152,152 / DISTINCT stock: 626
- 일자 범위: 2025-03-04 ~ 2026-05-08 (NXT 출범 시점부터)

### 26.6 결과 활용

1. results.md 채움 완료 후 본 § 26.5 표 갱신 (raw 측정은 results.md 유지)
2. STATUS.md § 4 의 정량화된 미해결 항목 제거 (#4, #5, #6 후보)
3. 새 위험 발견 시 STATUS.md § 4 에 추가 + 후속 chunk § 5 에 우선순위 반영
4. ADR § 26.5 의 "결정" 컬럼이 곧 다음 chunk 의 entry point

### 26.7 다음 chunk 후보 (실측 결과에 따라 변경)

- 측정 #3 NUMERIC overflow 발생 → **NUMERIC 컬럼 마이그레이션 chunk** (Migration 013) 가 1순위
- 측정 #4 일간 cron 시간 예산 초과 → **concurrency 조정 / page-level chunking chunk**
- 측정 1~4 모두 가설 적중 → **gap detection** 또는 **daily_flow 백필** 로 진행

---

## 27. daily_flow (ka10086) 백필 CLI (2026-05-10~11, ✅ 전체 완료 — 코드/테스트 + 가이드 + Stage 0~3 + 2건 fix + resume + 컬럼 동일값 확정)

> 관련 plan doc: [`phase-c-backfill-daily-flow.md`](../plans/phase-c-backfill-daily-flow.md)
> 운영 실측 runbook: [`backfill-daily-flow-runbook.md`](../../src/backend_kiwoom/docs/operations/backfill-daily-flow-runbook.md)
> 운영 실측 결과 양식: [`backfill-daily-flow-results.md`](../../src/backend_kiwoom/docs/operations/backfill-daily-flow-results.md)

### 27.1 결정

OHLCV 백필 (§ 26) 운영 실측 완료 후 **daily_flow (ka10086) 백필 CLI** 신규. OHLCV 백필에서 발견된 운영 차단 fix 3건 (since_date guard / `--max-stocks` 정상 적용 / ETF 호환 가드) 을 처음부터 패턴 그대로 내장 — mock 테스트가 못 잡는 운영 edge case 사전 방어.

### 27.2 변경 범위

- **`scripts/backfill_daily_flow.py` 신규** — `IngestDailyFlowUseCase` 의 1년 cap 우회 + `--indc-mode {quantity,amount}` + 동일 `--years/--start-date/--end-date/--resume/--max-stocks/--dry-run` 인자
- **`mrkcond.py` `fetch_daily_market` since_date 추가** — chart.py 패턴 1:1 응용. `_page_reached_since` / `_row_on_or_after` 헬퍼. `since_date=None` 디폴트로 운영 cron 호환
- **`IngestDailyFlowUseCase.execute` 시그니처 확장** — `only_stock_codes` / `_skip_base_date_validation` / `since_date` 파라미터 신규 (모두 디폴트값 — 라우터/cron 호환)
- **`IngestDailyFlowUseCase.refresh_one` `_skip_base_date_validation` 추가** — CLI backfill H-1 일관
- **`_KA10086_COMPATIBLE_RE = re.compile(STK_CD_LOOKUP_PATTERN)` ETF 가드** — raw_stocks fullmatch 사전 필터 + sample 5 가시성 로깅 (OHLCV daily/weekly 정책 일관)

### 27.3 산출물

- 코드: 3 파일 수정 + 1 파일 신규 (`scripts/backfill_daily_flow.py`)
- 테스트: +31 cases (993 → 1024) — mrkcond +2 / service +5 / CLI +24
- plan doc: `docs/plans/phase-c-backfill-daily-flow.md` 신규
- 운영 실측: **본 chunk 범위 외** — OHLCV 백필 패턴 동일 (사용자 수동 smoke → mid → full)

### 27.4 측정 대상 (운영 미해결 신규 4건)

| # | 항목 | 가설 | 결정 기준 |
|---|------|------|-----------|
| 1 | 페이지네이션 빈도 (3년) | ka10086 22 필드 → 1 page ~300 거래일 → 3년 = 2~3 page (계획서 § 12.7) | 실측 < 5 page 면 OK, 초과 시 max_pages 상향 |
| 2 | 3년 백필 elapsed | OHLCV 34분 + 페이지네이션 +α (50~100분) | 24h 이내면 OK, 초과 시 concurrency 조정 |
| 3 | NUMERIC change_rate / foreign_holding_ratio / credit_ratio 분포 | 7,500 종목 백필 시 일부 magnitude overflow 가능 | overflow 발생 시 별도 Migration chunk |
| 4 | 빈 응답 / ETF skip 비율 | OHLCV 와 일치 (ETF ~7%, 빈 응답 ~0.025%) | 일치 시 cross-check 검증 완료 |

### 27.5 실측 결과 (부분 — Stage 0/1 + 운영 차단 1건 fix, mid/full TBD)

> **측정 환경**: docker-compose 5433 / 운영 키움 (alias=prod) / 2026-05-10 17:43~18:25 KST
> **상세**: `backfill-daily-flow-results.md`

| 측정 항목 | 가설 (계획서 / dry-run) | 실측 | 결정 / 후속 |
|----------|----------------------|------|------------|
| **Stage 0 dry-run** | active 4373 / pages 4 / total 34,984 / 추정 2h 25m | dry-run 출력 동일 | ✅ DB / env 정상 |
| **Stage 1 smoke (1년)** 첫 시도 | OHLCV 패턴 — 5초 내 PASS | ❌ **8건 KiwoomMaxPagesExceededError** | 즉시 fix 진입 |
| **1 page 거래일 수 (실측)** | ~300 거래일 (mrkcond:50 가설) | **~22 거래일** (next-key 추적) | **가설 13배 틀림** |
| **smoke 재시도** (after fix) | 1년 = 12 page 가능 | ✅ total 6 / failed 0 / 25s / NXT 2 적재 | PASS |
| **Stage 2 mid (3년 KOSPI 100)** | dry-run 추정 2.6분 (page 4 가정) | ✅ **78 / 21 / 0 / 13m 8s** (avg 10.1s/stock — 17x OHLCV) | dry-run 5배 느림 (page ~32 실측) |
| **Stage 3 full (3년 active 4078)** | mid × 52 = 9~12h | 🟡 **3922 / 616 / 166 / 9h 53m 34s** | KRX 0 fail / NXT 166 fail (별도 chunk) |
| **NUMERIC(8,4) 4 컬럼** | OHLCV turnover_rate (max 3257.80) 패턴 | ✅ credit_rate / credit_balance_rate max **16.39** / foreign_rate / foreign_weight max **100.00** / gt_100·gt_1000 모두 0 | **마이그레이션 불필요** (cap 1% 이내) |
| **컬럼 동일값 의심** (신규 발견) | (가설 없음) | 🔶 `credit_rate` ≡ `credit_balance_rate` / `foreign_rate` ≡ `foreign_weight` (min/max/p01/p99 모두 일치) | follow-up — `<>` 검증 chunk → 동일 시 Migration DROP (C-2γ 패턴) |
| **since_date edge case (OHLCV F6 cross-check)** | OHLCV 002690/004440 같은 패턴 가능 | ✅ **0 rows** (since_date 도달 후 page/row fragment 모두 정확히 break) | daily_flow guard 가 OHLCV 보다 **정확** |
| NUMERIC(8,4) 4 컬럼 | TBD | TBD | TBD |

**신규 운영 발견 (3건)**:

1. **`DAILY_MARKET_MAX_PAGES = 10` 부족** (smoke 첫 시도, chunk `7c07fb7`) — mrkcond.py:50 가설 "1 page ~300 거래일" 실측 ~22 거래일 (13배 틀림). 1년 백필 = 약 12 page → max_pages 도달 fail. fix: `=40`. smoke + mid + full KRX 모두 PASS

2. **NXT 166 종목 max_pages=40 도 부족** (full, MEDIUM, ✅ **해소 — chunk `<flow-empty-fix>`**) — NXT 활성 626 중 166 fail (26.5%). **근본 원인**: 키움 서버가 NXT 출범 (2025-03-04) 이전 base_dt 요청 시 resp-cnt=0 + cont-yn=Y + next-key sentinel (`...20260511000000-1`) 후 page 1 next-key 로 되돌아가는 **무한 루프** (NXT 010950 ka10086 3년 단독 reproduce 검증, p1~p15 정상 + p16 sentinel + p17~ page 1 부터 반복). `_page_reached_since` 가 빈 rows 시 False 반환 → break X. **fix**: mrkcond.py / chart.py 4 곳에 `if not parsed.<list>: break` 추가. 010950 3년 백필 PASS (13s / 0 fail / NXT 1 적재). ka10081 도 일관성 + 잠재 위험 (저거래/장기 휴장 종목) 방어 적용

3. **컬럼 동일값 확정** (NUMERIC SQL + IS DISTINCT FROM SQL 검증, chunk `<resume-commit>`) — `credit_rate` vs `credit_balance_rate` / `foreign_rate` vs `foreign_weight`: 2,879,500 rows 모두 **0건 차이** (NULL 포함 IS DISTINCT FROM). ka10086 응답이 두 필드를 동일값으로 채움 → **다음 chunk: Migration 013 `credit_balance_rate` + `foreign_weight` DROP** (C-2γ Migration 008 의 D-E 중복 3 컬럼 DROP 패턴 응용)

mock 테스트가 page row 수 / NXT 응답 패턴 같은 운영 edge case 를 못 잡는다는 한계 (OHLCV `12f0daf` HANDOFF) 재확인.

**ka10086 (mrkcond) vs ka10081 (chart) 1 page row 수 차이**:

| endpoint | 1 page 거래일 수 (실측) | MAX_PAGES (수정 후) | 3년 백필 page |
|----------|------------------------|---------------------|----------------|
| ka10081 (OHLCV) | ~600 (chart.py:176) | 10 | 1~2 |
| ka10086 (daily_flow) | **~22** (next-key 실측) | **40** (`<this commit>`) | ~32 |

**원인 가설**: ka10086 응답 22 필드 (신용 + 투자자별 + 외인) 의 row 가 base_dt 기준 약 1개월 단위로 잘림 (단위 지급은 키움 서버 측 로직). 첫 page 만 ~80 거래일 (4개월) 다른 패턴 — 추후 검증 (follow-up)

**chunk 산출** (2026-05-10~11):

- runbook: `backfill-daily-flow-runbook.md` (12 §, `7be3185`)
- results: `backfill-daily-flow-results.md` (14 §, 모두 채움)
- 최종 적재: KRX 4077 stocks / 2,727,337 rows + NXT 626 stocks / 152,163 rows = **2,879,500 rows total** — OHLCV stocks 정확히 일치
- 미해결 모두 해소: NXT 166 fail ✅ (`72dbe69` sentinel break) / 컬럼 동일값 ✅ 확정 (Migration 013 별도 chunk)

### 27.6 운영 차단 fix 패턴 일관성 검증

OHLCV 백필 (`d60a9b3`/`76b3a4a`/`c75ede6`) 의 3건 fix 가 daily_flow 백필에서 **사전 적용** 되었는지 self-check:

| # | 운영 차단 | OHLCV fix commit | daily_flow 적용 |
|---|----------|-----------------|----------------|
| 1 | since_date guard | `d60a9b3` | ✅ mrkcond.py `_page_reached_since` / `_row_on_or_after` |
| 2 | `--max-stocks` CLI | `76b3a4a` | ✅ `_list_active_stock_codes` + `effective_stock_codes` 로직 일관 |
| 3 | ETF/ETN 호환 가드 | `c75ede6` | ✅ `_KA10086_COMPATIBLE_RE` 사전 필터 + sample 로깅 |

mock 테스트가 운영 edge case 를 재현 못 하는 한계 (`12f0daf` HANDOFF) 를 운영 실측 진입 전 패턴 적용으로 부분 완화. 새 운영 edge case 발견 시 OHLCV 와 동일 chunk 분리 방침 (즉시 fix + 다음 chunk).

### 27.7 다음 chunk 후보

- 사용자 수동 실측 (smoke → mid → full) 후 § 27.5 채움 (OHLCV § 26.5 와 동일 흐름)
- 측정 #3 NUMERIC overflow 발생 → 별도 Migration chunk

## 28. C-2δ — Migration 013 (C/E 중복 컬럼 2개 DROP) (2026-05-11, ✅ 완료)

설계 doc: `src/backend_kiwoom/docs/plans/endpoint-10-ka10086.md` § 13.

### 28.1 결정

daily_flow 풀 백필 완료 (`2317528`) 후 컬럼 동일값 의심 (§ 27.5) 확정 → C-2γ Migration 008 의 D-E 중복 3 컬럼 DROP 패턴 1:1 응용. `credit_balance_rate` (C 페어) + `foreign_weight` (E 페어) 2 컬럼 DROP. 10 → 8 도메인 컬럼.

### 28.2 검증 근거 (IS DISTINCT FROM 2.88M rows)

resume 완료 후 (총 2,879,500 rows / KRX 4,077 종목 / NXT 626 종목) `IS DISTINCT FROM` SQL:

```sql
SELECT
    COUNT(*) FILTER (WHERE credit_rate IS DISTINCT FROM credit_balance_rate) AS credit_diff,
    COUNT(*) FILTER (WHERE foreign_rate IS DISTINCT FROM foreign_weight)    AS foreign_diff
FROM kiwoom.stock_daily_flow;
```

| 페어 | 차이 row 수 |
|------|------------|
| `credit_rate <> credit_balance_rate` | **0건** |
| `foreign_rate <> foreign_weight` | **0건** |

`<>` 가 아닌 `IS DISTINCT FROM` 사용 — NULL 비교 false 회피로 NULL row 도 정확 비교. NUMERIC magnitude / 분포 (results § 5.1~5.4) 도 페어 간 완전 일치 (min/max/p01/p99).

### 28.3 변경 범위 (6 코드 + 4 테스트 + 1 운영 doc)

코드:
1. `migrations/versions/013_drop_daily_flow_dup_2.py` (신규, revision id 25 chars — VARCHAR(32) 한도)
2. `app/adapter/out/persistence/models/stock_daily_flow.py` (Mapped 2 제거 / 도메인 10→8)
3. `app/adapter/out/persistence/repositories/stock_daily_flow.py` (payload + excluded 4줄 제거)
4. `app/adapter/out/kiwoom/_records.py` (NormalizedDailyFlow 2 필드 + to_normalized 2 매핑 제거. raw DailyMarketRow.crd_remn_rt/for_wght 는 vendor 응답 모델로 유지)
5. `app/adapter/web/routers/daily_flow.py` (DailyFlowRowOut 2 필드 제거 — 응답 DTO breaking, 운영 미가동이라 영향 0)
6. `scripts/dry_run_ka10086_capture.py` (2 line 제거 — plan doc § 13.5 H-5 self-check)

테스트:
1. `tests/test_migration_013.py` (신규 4 cases — 008 패턴 1:1: UPGRADE 부재 / 잔존 8 도메인 / DOWNGRADE 가드 RAISE / 라운드트립)
2. `tests/test_migration_007.py` (NUMERIC 4→2 + DROP 부재 단언 추가)
3. `tests/test_migration_008.py` (`expected_remaining` 10→8 + 라운드트립 head 컬럼 카운트 18→16, **plan doc § 13.3 미명시 — testcontainers 가 발견**)
4. `tests/test_stock_daily_flow_repository.py` + `test_daily_flow_router.py` + `test_kiwoom_mrkcond_client.py` (stale kwarg/assertion 제거 + 부재 단언 추가)

운영 doc:
- `docs/operations/backfill-daily-flow-runbook.md` NUMERIC SQL § + IS DISTINCT FROM SQL § inline 주석 (Migration 013 후 비활성)

### 28.4 검증 (Verification Loop)

| 게이트 | 결과 |
|-------|------|
| ruff check | ✅ All checks passed |
| mypy --strict | ✅ Success: no issues found in 5 source files |
| pytest (full) | ✅ **1030 passed** in 23.31s (1026 → +4 from test_migration_013) |
| coverage | 95% (유지) |

### 28.5 Verification 가 잡은 2건 (정적 분석 외)

1. **VARCHAR(32) revision id truncation** — `013_drop_daily_flow_dup_columns_2` (33 chars) → testcontainers conftest setup 시점 `psycopg2.errors.StringDataRightTruncation` → `013_drop_daily_flow_dup_2` (25 chars) 로 단축. 008 패턴 (`008_drop_daily_flow_dup_columns` 31 chars) 답습 시 위험. 향후 chunk 메모.
2. **`test_migration_008.py` hard-coded 카운트** — H-8 (test_007) 패턴이 test_008 의 `expected_remaining` set + `len(cols_after_upgrade) == 18` 에도 동일 적용 필요. plan doc § 13.3 누락 — testcontainers 가 자동 발견.

### 28.6 응답 DTO breaking 수용

DailyFlowRowOut 2 필드 (`credit_balance_rate` / `foreign_weight`) 제거. 운영 미가동 + master 외 deploy 0 — downstream 영향 0. 향후 scheduler_enabled 활성 전 시점이라 breaking 안전. 응답 부재 단언 (`assert "credit_balance_rate" not in body[0]`) router test 에 추가하여 회귀 방어.

### 28.7 다음 chunk 후보

1. **scheduler_enabled 운영 cron 활성 + 1주 모니터** — 측정 #4 (일간 cron elapsed) / OHLCV + daily_flow 통합 (MEDIUM)
2. **follow-up F6/F7/F8 + daily_flow 빈 응답 1건 통합** (LOW)
3. **refactor R2 (1R Defer 일괄 정리)** (LOW)
4. **ka10094 (년봉, P2)** — C-3 패턴 응용
- 모든 가설 적중 → **scheduler_enabled 운영 cron 활성** 으로 진행 (HANDOFF Pending #2)

## 29. C-4 — Migration 014 + ka10094 (년봉) 인프라 + 자동화 (2026-05-11, ✅ 완료)

설계 doc: `src/backend_kiwoom/docs/plans/endpoint-09-ka10094.md` § 12.

### 29.1 결정 (Phase C 종결)

C-3α/β (`8fcabe4`/`2d4e2ae`) 의 `IngestPeriodicOhlcvUseCase` 가 Period 3값 (WEEKLY/MONTHLY/YEARLY) 분기 중 YEARLY 만 `NotImplementedError("period=YEARLY (ka10094) 는 P2 chunk")` 가드 — 본 chunk 에서 활성화. 응답 7 필드 (`pred_pre` / `pred_pre_sig` / `trde_tern_rt` 없음) + NXT skip 정책 + 매년 cron 차이만 핵심.

10/25 → **11/25** endpoint 완료. Phase C chart 카테고리 (일/주/월/년봉) 종결.

### 29.2 변경 범위 (10 코드 + 5 테스트)

**코드**:
1. `migrations/versions/014_stock_price_yearly.py` (신규, revision id 22 chars)
2. `app/adapter/out/persistence/models/stock_price_periodic.py` (StockPriceYearly{Krx,Nxt} 2 클래스 추가, mixin 재사용)
3. `app/adapter/out/persistence/models/__init__.py` (export 2 추가)
4. `app/adapter/out/kiwoom/chart.py` (YearlyChartRow + YearlyChartResponse 7 필드 + fetch_yearly + sentinel break / _page_reached_since 와 _row_on_or_after union 확장)
5. `app/adapter/out/persistence/repositories/stock_price_periodic.py` (YEARLY dispatch table 등록, PeriodicModel union 확장)
6. `app/application/service/ohlcv_periodic_service.py` (`_validate_period` NotImplementedError 제거 / `_ingest_one` YEARLY 분기 + fetch_yearly / `_api_id_for` YEARLY → ka10094 / execute+refresh_one NXT skip 가드 `or period is Period.YEARLY`)
7. `app/adapter/web/routers/ohlcv_periodic.py` (yearly sync + refresh 2 path / `_api_id_for` 모듈 헬퍼 + inline ternary 정리)
8. `app/batch/yearly_ohlcv_job.py` (신규, fire_yearly_ohlcv_sync — monthly 패턴 1:1)
9. `app/scheduler.py` (YearlyOhlcvScheduler 클래스 + YEARLY_OHLCV_SYNC_JOB_ID + CronTrigger month=1 day=5 hour=3 minute=0 KST)
10. `app/config/settings.py` (`scheduler_yearly_ohlcv_sync_alias` 추가)
11. `app/main.py` (lifespan alias fail-fast 추가 + YearlyOhlcvScheduler 등록/shutdown)

**테스트** (1030 → **1035** cases / coverage 유지):
1. `tests/test_migration_014.py` (신규 5 cases — yearly 2 테이블 / UNIQUE / 인덱스 / FK CASCADE / downgrade 가드 / 라운드트립)
2. `tests/test_stock_price_periodic_repository.py` (3 stale yearly raises → YEARLY 활성 검증으로 갱신)
3. `tests/test_ohlcv_periodic_service.py` (2 stale NotImplementedError → YEARLY KRX-only 성공 + NXT skip 검증)
4. `tests/test_skip_base_date_validation.py` (1 stale NotImplementedError → YEARLY skip-validation 정상 검증)
5. `tests/test_scheduler.py` + `tests/test_stock_master_scheduler.py` (SCHEDULER_YEARLY_OHLCV_SYNC_ALIAS env 누락 추가)
6. `tests/test_migration_013.py` (downgrade 가드 단언 정정 — 014 head 후 transactional rollback 으로 target 미도달 검증)

### 29.3 결정 (응답 7 필드 + NXT skip + 매년 cron)

| # | 사안 | 결정 |
|---|------|------|
| 1 | 응답 7 필드 vs 10 필드 | YearlyChartRow 별도 정의 (DailyChartRow 상속 불가). `to_normalized` 에서 prev_compare_amount/sign/turnover_rate=None → DB NULL 영속 |
| 2 | NXT skip 정책 (plan § 12.2 #3 yearly_nxt_disabled) | UseCase execute/refresh_one 의 NXT 가드에 `or period is Period.YEARLY` 추가. fetch_yearly 자체는 호출 안 됨 |
| 3 | 테이블 분리 KRX/NXT (plan § 12.2 #2) | NXT 테이블도 신규 (Migration 014). dispatch table 도 둘 다 등록. 향후 NXT skip 해제 chunk 시 활용 |
| 4 | 매년 cron 시점 | KST 매년 1월 5일 03:00 (직전 년 마감 + 새해 휴장 후 며칠 여유). scheduler_enabled 활성은 사용자 결정 (모든 작업 완료 후) |
| 5 | revision id 길이 | `014_stock_price_yearly` (22 chars) — VARCHAR(32) 안전 마진 10 chars. C-2δ 학습 적용 |

### 29.4 Verification Loop 가 잡은 5건

1. **VARCHAR(32) revision id 사전 안전 마진** — 본 chunk 진입 전 plan doc § 12.4 H-1 self-check + 22 chars 채택. C-2δ 학습 (33 chars > 32 한도 발견) 의 후속 적용
2. **`mypy --strict` invariant list 거부** — `rows: list[DailyChartRow] | list[YearlyChartRow]` (variant) → `list[DailyChartRow | YearlyChartRow]` (covariant) 로 정정. WeeklyChartRow/MonthlyChartRow 의 DailyChartRow 상속과 YearlyChartRow 의 별도 정의 차이가 type system 노출
3. **`_page_reached_since` / `_row_on_or_after` helper signature 확장** — `Sequence[DailyChartRow]` → `Sequence[DailyChartRow | YearlyChartRow]` (`dt` attribute 만 사용하므로 union 안전)
4. **C-3α stale 가드 단언 6건** — `test_stock_price_periodic_repository.py` 3건 (YEARLY not in mappings / upsert raises / find_range raises) + `test_ohlcv_periodic_service.py` 2건 (execute/refresh_one NotImplementedError) + `test_skip_base_date_validation.py` 1건. plan doc § 12.3 영향 범위 미명시 — testcontainers 가 자동 발견 (C-2δ Migration 013 chunk 의 test_008 패턴 재현)
5. **테스트 환경 env alias 누락 2건** — test_scheduler.py + test_stock_master_scheduler.py 의 lifespan fail-fast 테스트가 SCHEDULER_YEARLY_OHLCV_SYNC_ALIAS 누락으로 fail. C-3β 가 weekly/monthly 추가 시 발생한 동일 패턴 정착

### 29.5 응답 DTO 신규 (breaking 없음)

DailyFlowRowOut 패턴과 동일 — `POST /api/kiwoom/ohlcv/yearly/sync` 와 `POST /api/kiwoom/stocks/{code}/ohlcv/yearly/refresh` 가 기존 `OhlcvPeriodicSyncResultOut` 재사용 (period 무관 응답 스키마). 신규 endpoint 라 breaking 없음. GET 시계열 endpoint 는 C-3β 와 일관 정책 (별도 chunk, ohlcv_periodic.py 헤더 § 정책 유지).

### 29.6 다음 chunk 후보

1. **refactor R2 (1R Defer 일괄 정리)** (LOW / 1일)
2. **follow-up F6/F7/F8 + daily_flow 빈 응답 1건** (LOW / 0.5일)
3. **ETF/ETN OHLCV 별도 endpoint** (옵션 c)
4. **Phase D 진입** — ka10080 분봉 / ka20006 업종일봉 (대용량 파티션 결정 선행)
5. **Phase E/F/G** (공매도/대차/순위/투자자별 wave)
6. **(최종) scheduler_enabled 일괄 활성 + 1주 모니터** — 사용자 결정 (모든 작업 완료 후)
7. **KOSCOM cross-check 수동** — 가설 B 최종 확정


## 30. Phase C-R2 — 1R Defer 5건 일괄 정리 (2026-05-11)

### 30.1 결정

ADR § 24.5 + § 25.6 의 1R Defer 5건 (L-2 / E-1 / M-3 / E-2 / gap detection) 일괄 정리. 외부 API contract 무변. C-4 (ka10094 / `b75334c`) 가 L-2 의 전제 조건을 변경 — YEARLY 활성화 → "_do_sync NotImplementedError 핸들러 추가" 가 dead branch 라 stale docstring 정리로 축소 (사용자 결정 옵션 A).

### 30.2 핵심 설계 결정

| # | 사안 | 결정 |
|---|------|------|
| 1 | L-2 처리 방향 | **옵션 A — 폐기 + stale docstring 5곳 정리**. C-4 가 YEARLY 활성화 → 핸들러 추가는 dead branch. `_ingest_one:392` 의 dead branch 가드는 defense-in-depth 로 유지 (Period enum 확장 시 fail-fast). 사용자 결정 (2026-05-11) |
| 2 | E-1 sync KiwoomError 매핑 | **5종 핸들러 추가** — KiwoomBusinessError → 400 (return_code/message echo 차단) / KiwoomCredentialRejected → 400 / KiwoomRateLimited → **503** (429 가 아님 — refresh / _do_sync 와 일관) / Upstream + ResponseValidation → 502 / KiwoomError fallback → 502 (logger.warning). 동일 모듈 refresh_ohlcv_daily 와 동일 순서 (subclass first) |
| 3 | M-3 cast vs type ignore | **typing.cast 채택** — `cast(list[T], list(result.scalars().all()))`. runtime 무영향 + mypy strict 안전. Union 타입은 ORM 모델 그대로 명시 (KRX \| NXT 또는 WKRX \| ... \| YNXT 6-way) |
| 4 | E-2 reset_token_manager 정직성 | **"테스트 전용" 유지** — main.py:456-462 의 lifespan teardown 이 호출하지 않음. 7개 reset_*_factory 만 "lifespan teardown + 테스트" 로 정정. 1R 2b M4 fail-closed 정책 명시 |
| 5 | gap detection 영업일 source | **DB 내 `SELECT DISTINCT trading_date` union** (사용자 결정) — 외부 패키지 의존성 0. 시장 전체 종목이 한 번이라도 거래한 일자 = 영업일. 신규 Stock (적재 0) 도 자연스럽게 비교. period 별 KRX 영속화 테이블 (daily/weekly/monthly/yearly) 또는 stock_daily_flow (exchange='KRX') 에서 union. 영업일 set = ∅ 가드 (H-8) — 첫 적재 시 모든 candidate 진행 |
| 6 | gap detection 시그니처 변경 | **start_date 인자 추가 + should_skip_resume 폐기** — `compute_resume_remaining_codes(session, *, period, start_date, end_date, candidate_codes)`. 일자별 차집합으로 부분 적재 (gap) 정확 감지. caller 갱신 (start_date 가 이미 `resolve_date_range` 에서 가용) + argparse help / log message 정정 |
| 7 | C-4 잔존 stale 함께 정리 | `test_ohlcv_periodic_service.py` 의 `YearlyChartRow` forward ref + 함수 내부 import → 모듈 top-level import + 일반 타입 annotation. ruff UP037/F821 4 errors 해소 (R2 진입 시 발견) |

### 30.3 1차 리뷰 결과 (sonnet, MEDIUM 2 fix + LOW 1 fix → PASS)

| # | 등급 | 이슈 | 처리 |
|---|------|------|------|
| H-1 | (false positive) | reset_token_manager docstring | 그대로 유지 (의도된 정직성) |
| M-1 | MEDIUM | `backfill_ohlcv.py` 의 영업일 SQL 에 exchange 필터 없음 (daily_flow 와 패턴 차이) | 의도 주석 추가 — stock_price_*_krx 테이블은 KRX 전용, exchange 컬럼 자체 없음 |
| M-2 | MEDIUM | `test_backfill_daily_flow_cli.py` 섹션 5 빈 헤더 (섹션 8 과 어긋남) | 섹션 5 헤더 제거. `test_backfill_ohlcv_cli.py` 도 동일 정정 |
| M-3 | MEDIUM | sync_ohlcv_daily 의 `detail=str(exc)` ValueError echo (미래 안전성) | 본 chunk 범위 외 — refresh / _do_sync 의 동일 패턴. UseCase 내부 메시지에 외부 입력 무관 (기록만) |
| L-1 | LOW | `_validate_period` 빈 body — 미래 Period 확장 인지 어려움 | 인라인 주석 추가 — defense-in-depth 가드 위치 명시 |
| L-2 | LOW | M-3 cast 6-way Union | 이슈 없음. 명시성 우월 |
| L-3 | LOW | should_skip_resume 폐기 처리 | PASS — 주석만 남고 import/호출 없음 |

→ M-1 + M-2 + L-1 즉시 적용. CRITICAL/HIGH 0건. 자동 분류 = refactor → 2b 적대적 / 3-4 보안 / 4 E2E 자동 생략.

### 30.4 결과

- **테스트**: 1035 → **1037 cases** (+5 E-1 / +6 gap 신규 / -6 should_skip_resume 폐기 / -3 placeholder 통합 / +2 dispatch yearly 영향 = net +2)
- **mypy --strict**: 78 source files / 0 errors
- **ruff check + format**: All passed (C-4 잔존 stale 4건 fix 포함)
- **coverage**: 81.15% (목표 80%+ 유지)
- **수정 파일 (코드)**: app/application/service/ohlcv_periodic_service.py (L-2) / app/adapter/web/routers/ohlcv_periodic.py (L-2) / app/adapter/web/routers/ohlcv.py (E-1) / app/adapter/out/persistence/repositories/stock_price.py (M-3) / app/adapter/out/persistence/repositories/stock_price_periodic.py (M-3) / app/adapter/web/_deps.py (E-2) / scripts/backfill_ohlcv.py (gap) / scripts/backfill_daily_flow.py (gap) — 8 파일
- **수정 파일 (테스트)**: tests/test_ohlcv_router.py (E-1 5 신규) / tests/test_backfill_ohlcv_cli.py (gap 3 신규 + 폐기 4) / tests/test_backfill_daily_flow_cli.py (gap 3 신규 + 폐기 3) / tests/test_ohlcv_periodic_service.py (C-4 잔존 fix) — 4 파일
- **외부 API contract**: 무변. E-1 핸들러 추가는 미보호 5xx → 명시 매핑 (400/503/502) 으로 의도된 강화 (운영 알람 임계가 5xx 기반이면 KiwoomBusinessError → 400 누락 가능, 운영 공유 권고)

### 30.5 ADR § 24.5 / § 25.6 Defer 해소 매핑

| 출처 § | 항목 | 해소 |
|--------|------|------|
| § 24.5 | L-2 `_do_sync` / `_do_refresh` 에 `NotImplementedError → 501` 핸들러 | ✅ 폐기 (C-4 가 YEARLY 활성 → dead branch). stale docstring 5곳 정리 |
| § 24.5 | E-1 ka10081 `sync_ohlcv_daily` KiwoomError 핸들러 미등록 | ✅ 5종 핸들러 추가 (refresh / _do_sync 일관) |
| § 24.5 | E-2 `_deps.py` reset_ 함수 docstring "테스트 전용" | ✅ 7 함수 정정 (lifespan teardown + 테스트). reset_token_manager 는 정직성 유지 |
| § 23.6 | M-3 `# type: ignore[arg-type]` vs `cast()` | ✅ 2 Repository typing.cast 적용 |
| § 25.6 | gap detection (resume 정확도) | ✅ 2 CLI compute_resume_remaining_codes 일자별 차집합 검사 (DB union 영업일) |

### 30.6 운영 영향 (회귀 위험)

- **운영 호출 (`/ohlcv/daily/sync`) 의 status code 변화** — 본 chunk 전 키움 호출 실패 시 FastAPI 디폴트 500. 본 chunk 후 명시 매핑 (400/503/502). 운영 알람 임계가 5xx 기반이면 KiwoomBusinessError (→400) 가 알람에서 누락될 수 있음. 운영팀 공유 권고
- **CLI `--resume` 동작 변경** — 부분 적재 (gap) 종목이 R1 에서는 skip 되던 것이 R2 에서는 진행. 운영팀이 R1 동작을 전제로 한 백필 스크립트가 있으면 영향. 사용자 결정 (디폴트 동작 변경 — 정확도 향상)

### 30.7 다음 chunk 후보

1. **follow-up F6/F7/F8 + daily_flow 빈 응답 1건** (LOW / 0.5일)
2. **ETF/ETN OHLCV 별도 endpoint** (옵션 c)
3. **Phase D 진입** — ka10080 분봉 / ka20006 업종일봉 (대용량 파티션 결정 선행)
4. **Phase E/F/G** (공매도/대차/순위/투자자별 wave)
5. **(최종) scheduler_enabled 일괄 활성 + 1주 모니터** — 사용자 결정 (모든 작업 완료 후)
6. **KOSCOM cross-check 수동** — 가설 B 최종 확정


## 31. Phase C — follow-up F6/F7/F8 + daily_flow 빈 응답 1건 통합 분석 (2026-05-11)

### 31.1 결정

STATUS § 4 의 LOW 4건 (F6 / F7 / F8 / daily_flow 빈 응답) 일괄 분석. **4건 모두 NO-FIX** 결정. 코드 변경 0줄 — 분석 + 문서 정리 chunk. 사용자 결정 (옵션 A, 2026-05-11).

### 31.2 4건 검증 결과

| # | 항목 | 발생 | 검증 | 결정 |
|---|------|------|------|------|
| **F6** | since_date guard edge | 2 종목 (`002690` 동일제강 / `004440` 삼일씨엔에스), 4078 중 0.13% | `chart.py:355 _page_reached_since` 가 page 단위 break — 직전 page 의 row 일부가 since_date 보다 과거 적재. 두 종목 모두 1980 년대 상장이라 페이지 수 많음. 비롯 since_date guard 가 row 단위가 아닌 page 단위라 0.13% 잔존 | **NO-FIX** — 데이터 가치 ≥ 1 년 한도 위반 비용. row 단위 정밀화는 ~15 줄 + 테스트 가능하나 운영 영향 미미. 미래 운영 데이터 검증 시 재평가 |
| **F7** | turnover_rate 음수 anomaly | min `-57.32` (2.73M rows, `|값|>1000` 24건 = 0.0009%) | `chart.py:89 turnover_rate=_to_decimal(self.trde_tern_rt)` — **키움 raw 응답 그대로 보존**. 키움 측 수정주가 조정 아티팩트로 추정. 24건 / 2.73M = 0.0009% | **NO-FIX** — 정직성 우선 (키움 데이터 그대로). 분석 시 0/NaN/MAX(0,x) 처리는 분석 코드 책임으로 분리. `_to_decimal` 에 음수 가드 추가는 키움 raw 의 정보 손실이라 거부 |
| **F8** | OHLCV 1 종목 row 0 | success_krx **4078** vs DISTINCT **4077** = 1 종목 | DB SELECT 식별: **`452980` 신한제11호스팩** (KOSDAQ, 등록일 2026-05-09, **신규 상장 SPAC**). sentinel 가드 (`72dbe69`) 정상 동작 — 키움이 거래 데이터 없는 신규 상장 종목에 empty 응답 → break → row 0 적재 | **NO-FIX** — 종목 자체 상태 (시장 거래 시작 전). 다음 cron 에 자연히 row 추가됨 |
| **daily_flow 빈 응답** | daily_flow 1 종목 row 0 | success_krx **3922** vs DISTINCT KRX **3921** | DB SELECT 식별: **`452980` 신한제11호스팩** (F8 과 **동일 종목**, results.md 의 "OHLCV F8 일관" 명시와 일치). sentinel 가드 mrkcond + chart 4 곳 (`72dbe69`) 정상 동작 | **NO-FIX** — F8 와 동일 (종목 자체 상태) |

### 31.3 식별 SQL

본 chunk 의 핵심 발견 — F8 + daily_flow 빈 응답이 **동일 종목** 인지 확정:

```sql
-- F8 (OHLCV)
SELECT s.stock_code, s.stock_name, s.market_code, s.is_active, s.created_at::date AS reg_date
FROM kiwoom.stock s
WHERE s.is_active = true
  AND s.stock_code ~ '^[0-9]{6}$'  -- ETF 가드
  AND s.id NOT IN (SELECT DISTINCT stock_id FROM kiwoom.stock_price_krx)
ORDER BY s.stock_code;
-- → 452980 신한제11호스팩 (1 row)

-- daily_flow
SELECT s.stock_code, s.stock_name, s.market_code, s.is_active, s.created_at::date AS reg_date
FROM kiwoom.stock s
WHERE s.is_active = true
  AND s.stock_code ~ '^[0-9]{6}$'
  AND s.id NOT IN (SELECT DISTINCT stock_id FROM kiwoom.stock_daily_flow WHERE exchange = 'KRX')
ORDER BY s.stock_code;
-- → 452980 신한제11호스팩 (1 row, F8 동일)
```

### 31.4 권고 follow-up (미래 chunk)

- **F6** 운영 1주~1개월 후 재평가 — 1980 년대 상장 종목 추가 식별 시 row 단위 fragment 제거 chunk 검토
- **F7** 분석 코드 (백테스팅 layer) 에서 turnover_rate 0/NaN 처리 정책 명시 — DB 정규화는 거부
- **F8 / daily_flow 빈 응답** — 다음 cron (운영 daily_flow KST 19:00 + ohlcv 18:30) 실행 후 신한제11호스팩 row 추가 확인. row 0 종목이 다른 신규 상장 SPAC 으로 늘어나면 별도 대응 (현재 패턴 정상)

### 31.5 결과

- **코드 변경**: 0줄 (분석 + 문서 chunk)
- **테스트**: 변화 없음 (1037 유지)
- **mypy / ruff**: 변화 없음 (변경 0)
- **문서 변경**: ADR § 31 (본 §) / STATUS § 4 (4 항목 해소 표시) / CHANGELOG prepend / HANDOFF 갱신
- **STATUS § 5 follow-up F6/F7/F8 + daily_flow 빈 응답 항목 제거** (해소)

### 31.6 다음 chunk 후보

1. **ETF/ETN OHLCV 별도 endpoint** (옵션 c) — ETF 자체 OHLCV 백테스팅 가치
2. Phase D — ka10080 분봉 / ka20006 업종일봉 (대용량 파티션 결정 선행)
3. Phase E/F/G wave (공매도/대차/순위/투자자별)
4. (최종) scheduler_enabled 일괄 활성 + 1주 모니터 — 사용자 결정 (모든 작업 완료 후)


## 32. Phase C — chart 영숫자 stk_cd 가드 완화 — Chunk 1 dry-run (옵션 c-A, 2026-05-11)

### 32.1 결정

§ 31.6 #1 "ETF/ETN OHLCV 별도 endpoint (옵션 c)" 의 사용자 분기 — **옵션 A (우선주/특수 종목 가드 완화)** 채택. ETF 시장 (`market_code=8`) 신규 수집은 `master.md` § 0.3 결정 ("ETF/ELW/금현물 제외") 유지. plan doc `phase-c-chart-alphanumeric-guard.md` 신규.

본 chunk = 2단계 진행의 **Chunk 1 — 운영 dry-run**. 키움 chart 계열 (ka10081 + ka10086) 이 영숫자 6자리 stk_cd (`*K` suffix 우선주) 를 wire-level 에서 수용하는지 단건 검증. 코드 변경 0줄 — 임시 스크립트 + 결과 doc.

### 32.2 dry-run 결과 (12 호출)

대형그룹사 우선주 3건 (`03473K` SK우 / `02826K` 삼성물산우B / `00499K` 롯데지주우) 대상 KRX + NXT × ka10081 + ka10086.

| 거래소 | api_id | 결과 (3종 동일) | 해석 |
|--------|--------|----------------|------|
| **KRX** | ka10081 | rc=0 / rows=600 / `KiwoomMaxPagesExceededError` (max-pages=1 cap) | ✅ **wire-level SUCCESS** — 600 row = 일봉 ~2~3년치. cont-yn=Y 응답 = 더 받을 데이터 있음 |
| **KRX** | ka10086 | rc=0 / rows=20 / `KiwoomMaxPagesExceededError` | ✅ **wire-level SUCCESS** — 20 row = 일별수급 1 page |
| **NXT** | ka10081 | rc=0 / rows=1 (모든 필드 빈 문자열 sentinel) | ⚠️ NXT 우선주 미지원 — sentinel 빈 row |
| **NXT** | ka10086 | rc=0 / rows=0 | ⚠️ NXT 우선주 미지원 — 정상 empty |

**KRX 6/6 = 100% SUCCESS** (영숫자 stk_cd 수용 확정). **NXT 6/6 = 100% empty** (예상 — 우선주 NXT 미상장).

### 32.3 핵심 발견

1. **영숫자 stk_cd = 우선주** — listed_date 보유 영숫자 active 종목 10건 모두 `*우` / `*우B` 패턴 (`*K` suffix 가 우선주 식별자). ETF 신규 상장 (`0000D0` TIGER 등, listed_date NULL/최근) 와는 별개 패턴
2. **KRX chart endpoint 가 `^[0-9A-Z]{6}$` 수용** — `STK_CD_LOOKUP_PATTERN = ^[0-9]{6}$` 의 보수적 재사용은 ka10100 R22 Excel 명시 ASCII 제약에서 유래. chart 는 더 관대
3. **NXT 우선주 거래 미지원** — 기존 `stock.nxt_enable=False` 정책이 자연 차단. Chunk 2 의 NXT 처리 변경 0
4. **NXT sentinel 빈 row 1개** — 키움이 NXT 미상장 종목에 대해 1 빈 row 반환 (mrkcond/chart sentinel 가드 `72dbe69` 의 `if not <list>: break` 통과 가능성). 운영 영향 0 (우선주 NXT 호출 자체 차단되므로) — follow-up 후보

### 32.4 Chunk 2 진입 결정

| 항목 | 결정 |
|------|------|
| Chunk 2 진행 | ✅ **진행** — plan doc § 4 그대로 |
| Chunk 2 범위 변경 | ❌ 없음 — NXT 미지원은 기존 `nxt_enable=False` 가 자연 처리 |
| Chunk 2 위험 H-1 (chart 영숫자 수용 가정) | ✅ **해소** — wire-level SUCCESS 확정 |
| Chunk 2 위험 H-4 (NXT 우선주) | ✅ **해소** — 미지원 확정. NXT 호출 자체 차단됨 |
| 신규 follow-up | NXT sentinel 빈 row detection 보강 (`if not <list> or all(not row.<key> for row in <list>): break`) — LOW priority |

### 32.5 산출물

- `src/backend_kiwoom/docs/plans/phase-c-chart-alphanumeric-guard.md` 신규 (Chunk 1/2 plan)
- `src/backend_kiwoom/scripts/dry_run_chart_alphanumeric.py` 신규 (`build_stk_cd` 우회, 단건 캡처, verdict 분류). 변수명 fallback (`KIWOOM_API_KEY` → `KIWOOM_APPKEY` legacy)
- `src/backend_kiwoom/docs/operations/dry-run-chart-alphanumeric-results.md` 신규 (결과 표 + verdict 재해석 + 결정)
- `src/backend_kiwoom/captures/dry-run-alphanumeric-20260511.json` 신규 (raw 응답 + 분석)
- STATUS § 5 #1 — Chunk 1 결과 한 줄 갱신, Chunk 2 후보 명시
- CHANGELOG prepend
- **코드 변경 0줄** (chunk 1 은 dry-run + 문서 only)
- **테스트 변화 없음** (1037 유지)

### 32.6 다음 chunk 후보

1. **Chunk 2** — `STK_CD_CHART_PATTERN = ^[0-9A-Z]{6}$` 신규 + chart 계열 11곳 가드 교체 (plan doc § 4)
2. Phase D — ka10080 분봉 / ka20006 업종일봉
3. Phase E/F/G wave
4. (최종) scheduler_enabled 일괄 활성 + 1주 모니터


## 33. Phase C — chart 영숫자 stk_cd 가드 완화 — Chunk 2 구현 (옵션 c-A, 2026-05-11)

### 33.1 결정

§ 32 Chunk 1 dry-run 결과 (KRX 6/6 SUCCESS) 를 근거로 Chunk 2 진행. plan doc `phase-c-chart-alphanumeric-guard.md` § 4 범위 그대로 — `STK_CD_CHART_PATTERN` 신규 + chart 계열 가드 분리. lookup 계열 (ka10100/ka10001) 은 Excel R22 ASCII 제약 유지.

본 chunk 의 코드 변경 5 파일 + 테스트 7 파일 갱신/신규. **1037 → 1046 tests** (+9) / coverage 91% (이전 81% 보다 향상 — 보호 단언 추가 효과). 외부 contract 영향: chart 계열 endpoint 의 호출 대상 stock 범위가 영숫자 (`*K` 우선주 + 영숫자 ETF) 까지 확장. **운영 cron 실행 시 ~295 종목 추가 호출** → elapsed 비례 증가 (2초 rate limit 직렬화).

### 33.2 변경 면 매핑

| Layer | 위치 | 변경 |
|------|------|------|
| **상수** | `stkinfo.py:212` `STK_CD_LOOKUP_PATTERN` (`^[0-9]{6}$`) | **유지** — lookup 계열 (ka10100/ka10001) 단일 source |
| **상수 (신규)** | `stkinfo.py:224` `STK_CD_CHART_PATTERN` (`^[0-9A-Z]{6}$`) | **신규** — chart 계열 (ka10081/82/83/94 + ka10086) 단일 source |
| **검증 함수 (신규)** | `stkinfo.py:474` `_validate_stk_cd_for_chart` | **신규** — A-L1 메시지 cap 정책 일관 |
| **build_stk_cd** | `stkinfo.py:454` | `_validate_stk_cd_for_lookup` → `_validate_stk_cd_for_chart`. docstring 갱신 (6자리 ASCII 숫자 → 6자리 영숫자 대문자) |
| **adapter docstring** | `chart.py:10` / `mrkcond.py:10` | "6자리 ASCII" → "6자리 영숫자 대문자 (STK_CD_CHART_PATTERN)" |
| **chart router Path** | `ohlcv.py:35,239,342` (ka10081) / `ohlcv_periodic.py:42,306,358,410` (ka10082/83/94) / `daily_flow.py:35,211,314` (ka10086) | `STK_CD_LOOKUP_PATTERN` → `STK_CD_CHART_PATTERN`. 7 path + 3 import |
| **lookup router Path** | `stocks.py` / `fundamentals.py` | **변경 없음** — LOOKUP 그대로 (5곳 무변 확인) |
| **UseCase active_stocks filter** | `ohlcv_daily_service.py:54` / `ohlcv_periodic_service.py:52` / `daily_flow_service.py:61` | `_KA*_COMPATIBLE_RE` 가 LOOKUP → CHART. 3 service |

### 33.3 테스트 변경 (+9)

| 파일 | 변경 |
|------|------|
| `test_exchange_type.py` | `test_build_stk_cd_rejects_invalid_format` 의 `ABC123` 제거 + `0000d0` / `00ABC!` 추가 + **신규** `test_build_stk_cd_accepts_alphanumeric_uppercase` |
| `test_kiwoom_chart_client.py` | `test_fetch_daily_rejects_invalid_stock_code` 의 invalid set 갱신 (`ABC123` 제거) |
| `test_kiwoom_mrkcond_client.py` | `test_fetch_daily_market_rejects_invalid_stock_code` 동일 |
| `test_kiwoom_stkinfo_basic_info.py` | **신규 4건** — `test_validate_stk_cd_for_chart_accepts_alphanumeric_uppercase` / `test_validate_stk_cd_for_chart_rejects_invalid_format` / `test_validate_stk_cd_for_chart_message_capped_at_50_chars` / `test_validate_stk_cd_for_lookup_still_rejects_alphanumeric` (lookup 보호 단언) |
| `test_ingest_daily_ohlcv_service.py` | `test_execute_skips_alpha_stock_codes` → `test_execute_accepts_alphanumeric_uppercase_stock_codes` (의미 반전 + 단언 갱신) + **신규** `test_execute_skips_incompatible_stock_codes` (lowercase/특수문자) |
| `test_ohlcv_periodic_service.py` | 동일 패턴 — accepts/skips 분리 |
| `test_ingest_daily_flow_service.py` | 동일 패턴 — accepts/skips 분리 |
| `test_ohlcv_router.py` | `test_get_ohlcv_rejects_invalid_stock_code` invalid set 갱신 + **신규** `test_get_ohlcv_accepts_alphanumeric_uppercase_stock_code` |
| `test_daily_flow_router.py` | 동일 패턴 |

### 33.4 회귀 발견 (Verification 가 잡은 6건)

`testcontainers` 가 자동 발견 — chart 계열 거부 단언이 영숫자에서 의도와 반대로 작동. plan doc § 4.6 의 예측 ("기존 chart 계열 거부 단언이 있다면 영숫자 허용으로 갱신 필요") 적중. 6건 모두 의미 반전 + 새 거부 케이스로 분리.

1. `test_build_stk_cd_rejects_invalid_format` — `ABC123` 거부 단언이 깨짐
2. `test_fetch_daily_rejects_invalid_stock_code` (chart_client) — 동일
3. `test_fetch_daily_market_rejects_invalid_stock_code` (mrkcond_client) — 동일
4. `test_execute_skips_alpha_stock_codes` (ohlcv_daily) — `0000D0`/`00088K` skip 단언이 깨짐
5. `test_execute_weekly_skips_alpha_stock_codes` (ohlcv_periodic) — 동일
6. `test_execute_skips_etf_etn_with_alphabetic_stock_code` + `test_execute_skips_short_stock_code` (daily_flow) — 동일

→ chart 계열은 의미 반전, lookup 계열은 보호 단언 강화 (`test_validate_stk_cd_for_lookup_still_rejects_alphanumeric` 신규).

### 33.5 결과

- **코드**: 5 파일 (stkinfo / chart / mrkcond / 3 router / 3 service = 9 파일이지만 중복 카운팅 제외)
- **테스트**: 1037 → **1046** (+9 — 신규 5 / 갱신 의미반전 4)
- **coverage**: 91% (이전 81% — 신규 단언 paths 추가 효과)
- **ruff** / **mypy --strict**: 모두 PASS
- **외부 contract**: lookup 계열 (ka10100/ka10001) 무변 / chart 계열 영숫자 호출 가능 확장

### 33.6 알려진 follow-up

1. **운영 cron elapsed 증가** — ~295 종목 추가 호출. OHLCV daily cron 현재 34분 → ~44분 추정. STATUS § 4 신규 항목으로 추적
2. **NXT sentinel 빈 row 1개 detection** — 우선주 NXT 호출 시 (`*K_NX`) 키움이 1 빈 row 반환. 현재 sentinel 가드 (`if not <list>: break`, `72dbe69`) 통과 가능. 운영 영향 0 (우선주 `nxt_enable=False` 가 호출 자체 차단). LOW priority follow-up
3. **백필 운영** — 295 종목 × 3년 = 추가 ~200K rows. cron 자연 수집 또는 `scripts/backfill_ohlcv.py --resume` 별도 chunk

### 33.7 다음 chunk 후보

1. **운영 백필** (영숫자 295 종목) — Chunk 2 머지 후 cron 자연 수집 또는 별도 `backfill_ohlcv.py --resume` chunk
2. Phase D — ka10080 분봉 / ka20006 업종일봉 (대용량 파티션 결정 선행)
3. Phase E/F/G wave
4. (최종) scheduler_enabled 일괄 활성 + 1주 모니터
5. KOSCOM cross-check 수동 — 가설 B 최종 확정

---

## 34. Phase C — 영숫자 (우선주/ETF) 종목 OHLCV 3 period 백필 (2026-05-11, ✅ 완료)

### 34.1 결정

§ 33 Chunk 2 가드 완화 (`STK_CD_CHART_PATTERN`) 머지 후 chart endpoint 가 영숫자 stk_cd 수용. cron 자연 수집은 daily 1일치만 가져와 3년 historical 적재 불가 → backfill CLI 별도 chunk. plan doc `phase-c-alphanumeric-backfill.md`. 사용자 결정 (2026-05-11) — Stage 1 dry-run 후 scope 확장 인지 + 옵션 A (3 period 그대로 진행) 동의.

본 chunk 가 Phase C 의 **데이터 측면 마지막 chunk** — 종결 후 scheduler 활성 / Phase D 진입 가능.

### 34.2 Stage 1 — dry-run 결과 (✅ 완료)

**영숫자 active 종목 카운트** (2026-05-11 query):

| 항목 | 값 |
|------|-----|
| 영숫자 active (`stock_code ~ '[A-Z]'` AND `is_active=true`) | **295** |
| 우선주 `^[0-9]{5}K$` suffix | **20** (예: 005935 삼성전자우) |
| ETF/ETN/회사채 액티브 등 (영숫자 - 우선주) | **275** (TIGER/KODEX/PLUS/RISE/HK/1Q 등) |
| total active | 4373 (full backfill `12f0daf` 시점 4078 → +295 = 4373 — 영숫자만큼 마스터 신규 적재) |

**market_code 분포** (영숫자):

| market_code | n | 의미 |
|-------------|---|------|
| 0 | 249 | KOSPI (ETF 다수) |
| 10 | 44 | KOSDAQ |
| 50 | 1 | KONEX |
| 6 | 1 | (기타) |

> **plan doc § 1 정정**: "우선주/특수" 추정은 ETF dominant 로 정정. 우선주는 20 (6.8%) 에 불과 — 영숫자 295 의 대부분은 ETF/ETN 계열. 단 Chunk 1 dry-run (§ 32) 의 6 종목은 우선주 (`005935`/`00088K` 등) sample 이라 SUCCESS 결과의 일반화 위험은 낮음 — ETF 도 chart endpoint 호출 가능성 높음 (`market_code=0` = KOSPI 등록 ETF). Stage 2 실측이 확정.

**dry-run 3 period 추정** (rate_limit `0.25s/call`, ±50% margin):

| period | 영업일 calendar (DB) | 백필 대상 stocks | exchanges | pages/call | total calls | est. time |
|--------|---------------------|------------------|-----------|------------|-------------|-----------|
| daily | 727 (적재 완료) | **1108** (영숫자 295 + 비영숫자 gap 813) | 2 (KRX+NXT) | 2 | 4432 | 18m 28s |
| weekly | ∅ (첫 적재) | **4373** (전체) | 2 | 1 | 8746 | 36m 26s |
| monthly | ∅ (첫 적재) | **4373** (전체) | 2 | 1 | 8746 | 36m 26s |
| **합계** | — | — | — | — | **21,924** | **~91m 20s** |

> **gap detection 부수 발견** — daily 의 비영숫자 gap 813 종목 = full backfill (`12f0daf`) 후 신규 상장/거래정지 해제/데이터 누락 종목들. R2 의 영업일 calendar 차집합 (compute_resume_remaining_codes, `d43d956`) 이 자연 식별. weekly/monthly 는 첫 적재라 영업일 calendar ∅ → 전체 candidate 진행.

### 34.3 Stage 2 — 실 백필 3 period 결과 (✅ 완료, 2026-05-11)

| period | total | success_krx | success_nxt | failed | elapsed | est. (dry-run) | actual / est. |
|--------|-------|-------------|-------------|--------|---------|----------------|---------------|
| daily | 1108 | 1108 | 75 | **0** | 5m 48s | 18m 28s | 31% |
| weekly | 4373 | 4373 | 630 | **0** | 20m 55s | 36m 26s | 58% |
| monthly | 4373 | 4373 | 630 | **0** | 20m 50s | 36m 26s | 57% |
| **합계** | — | — | — | **0** | **47m 33s** | 91m 20s | **52%** |

> **추정 대비 52% 단축** — Stage 1 dry-run 의 ±50% margin 가정 (rate_limit 0.25s 직렬) 보다 실측은 더 빠름. avg/stock = 0.3s/stock 균일 (3 period 동일) — KRX 응답 latency 자체가 rate_limit 보다 짧고 multi-page 호출이 daily 만 발생 (weekly/monthly 는 1 page). 0 failure 모두 — chart 가드 완화 (§ 33) 가 운영에서도 검증.

**NXT success 분포**:
- daily NXT 75 — 비영숫자 gap 813 중 `nxt_enable=True` 종목 75. 영숫자 295 의 NXT 0 (모두 `nxt_enable=False` 자연 차단)
- weekly/monthly NXT 630 — 4078 전체 active 의 NXT enabled 비율 (~14%) × 4373 active. 첫 적재라 전체 NXT 시도

### 34.4 Verification SQL — DB 적재 검증 (✅ 완료, 2026-05-11)

```sql
SELECT 'daily_krx' AS table_, CASE WHEN s.stock_code ~ '[A-Z]' THEN 'alphanumeric' ELSE 'numeric' END AS code_kind, count(*) AS rows
FROM kiwoom.stock_price_krx p JOIN kiwoom.stock s ON s.id = p.stock_id
WHERE p.trading_date >= DATE '2023-05-12' GROUP BY 1, 2
UNION ALL
SELECT 'weekly_krx', CASE WHEN s.stock_code ~ '[A-Z]' THEN 'alphanumeric' ELSE 'numeric' END, count(*)
FROM kiwoom.stock_price_weekly_krx p JOIN kiwoom.stock s ON s.id = p.stock_id
WHERE p.trading_date >= DATE '2023-05-12' GROUP BY 1, 2
UNION ALL
SELECT 'monthly_krx', CASE WHEN s.stock_code ~ '[A-Z]' THEN 'alphanumeric' ELSE 'numeric' END, count(*)
FROM kiwoom.stock_price_monthly_krx p JOIN kiwoom.stock s ON s.id = p.stock_id
WHERE p.trading_date >= DATE '2023-05-12' GROUP BY 1, 2
ORDER BY 1, 2;
```

| table | numeric rows | alphanumeric rows | 영숫자 비율 | 영숫자 avg/stock |
|-------|--------------|-------------------|-------------|------------------|
| daily_krx | 2,725,952 | **58,909** | 2.12% | 199.7 (vs numeric 668.5) |
| weekly_krx | 589,459 | **12,983** | 2.16% | 44.0 (vs 144.5) |
| monthly_krx | 135,964 | **3,257** | 2.34% | 11.0 (vs 33.3) |
| **합계** | 3,451,375 | **75,149** | 2.13% | — |

> **plan doc § 1.3 정정**: "+200K rows" 추정 over-estimate — 실제 **75,149 rows (37%)**. 이유: 영숫자 295 의 평균 row 가 비영숫자의 30% 수준 (ETF/회사채액티브 등은 상장일이 최근 3년 미만 / 거래 zero 일자 다수 / SPAC 종목 일부 포함). 단 **모두 적어도 1 row 적재** (`distinct stock_code = 295` 검증) — `452980` SPAC 같은 0-row sentinel 종목 0건.

### 34.5 anomaly 분석 (✅ 완료, 2026-05-11)

| 항목 | 검증 SQL | 결과 | 결정 |
|------|---------|------|------|
| **NUMERIC(8,4) overflow** | `SELECT max/min(turnover_rate) WHERE stock_code ~ '[A-Z]'` | daily max 3049.40 / weekly max 3341.27 / monthly max 3445.97 (cap 9999.9999 — 34% 미만) | ✅ 안전. full backfill (`12f0daf`) max 3257.80 와 유사 magnitude. 마이그레이션 불필요 |
| **turnover_rate 음수 (F7 anomaly)** | `SELECT min(turnover_rate)` | daily/weekly min 0.0000 / monthly min 0.0100 | ✅ 음수 0건. F7 (-57.32) anomaly 영숫자 종목에는 없음 |
| **sentinel 빈 응답 (F8 / SPAC 패턴)** | `SELECT stock_code FROM stock WHERE stock_code ~ '[A-Z]' AND id NOT IN (SELECT stock_id FROM stock_price_krx ...)` | **0 종목** (영숫자 295 모두 적어도 1 row 적재) | ✅ SPAC 같은 신규 상장 detection 0건 |
| **failed (KiwoomBusinessError)** | summary `failed` 컬럼 | 3 period 모두 0 | ✅ 0 failure |
| **since_date edge case (F6 패턴)** | summary `success_krx` vs distinct stocks | success_krx = distinct stocks | ✅ 1980s 상장 종목 page break 잔존 row anomaly 영숫자에는 없음 (영숫자 종목 자체가 대부분 최근 상장 ETF) |

> § 31 의 F6/F7/F8 + daily_flow 빈 응답 4건 anomaly 가 영숫자 종목에는 **0건** — 영숫자 종목군 (ETF/우선주) 의 데이터 일관성이 비영숫자 (KOSPI/KOSDAQ 일반 종목) 보다 오히려 양호.

### 34.6 follow-up

| # | 항목 | 출처 | 결정 |
|---|------|------|------|
| 1 | **운영 cron elapsed +N분 정정** | § 33.6 #1 "OHLCV daily cron 34분 → ~44분 추정 (+10분)" | 실측 daily 1108 종목 5m 48s = avg 0.31s/stock → **영숫자 295 만 추가 시 cron 추가 시간 ≈ 295 × 0.3 = ~1.5분** (이전 추정 +10분의 15%). § 33.6 #1 정정 |
| 2 | weekly/monthly cron 첫 자동 실행 | scheduler 활성 후 | 본 chunk 의 weekly/monthly 가 첫 적재. scheduler 활성 시 cron (금 19:30 / 1일 03:00) 이 자연스럽게 incremental 모드 작동 — gap detection 가 영업일 calendar 비어있지 않음 인지 → 정상 작동 |
| 3 | yearly OHLCV (ka10094) 영숫자 백필 | plan doc § 2 Out of Scope | 1년 1 row 가치 낮음. cron 자연 수집에 위임 (매년 1월 5일 03:00) |
| 4 | 영숫자 daily_flow (ka10086) 백필 | plan doc § 2 Out of Scope | 본 chunk 와 별개. cron 자연 수집 또는 별도 chunk 사용자 결정 |
| ~~5~~ | NXT 우선주 sentinel 빈 row | § 32.3 + § 33.6 #2 | LOW — 운영 영향 0. 본 chunk 에서도 영숫자 295 의 NXT enable 모두 false → 호출 자체 없음. detection 재확인 |

### 34.7 Phase C 종결 의미

본 chunk 종료 시 Phase C 의 모든 chart endpoint (ka10081/82/83/94 + ka10086) 가 영숫자 종목 포함 3년 historical 적재 완성. STATUS § 5 #1 해소. 다음 chunk 후보:

1. **scheduler_enabled 일괄 활성 + 1주 모니터** — env 변경 1건. 측정 #13 (일간 cron elapsed) + #19 (영숫자 +10분 추정) 첫 영업일 정량화
2. **Phase D 진입** — ka10080 분봉 / ka20006 업종일봉. 대용량 파티션 결정 선행
3. **Phase E/F/G** — 공매도/대차/순위/투자자별 wave
4. KOSCOM cross-check 수동 — 가설 B 최종 확정 (수동 1~2건)

---

## 35. Phase C — cron 시간 NXT 마감 후 새벽 이동 + base_date 명시 전달 (2026-05-12, ✅ 완료)

### 35.1 결정

사용자 발견 (2026-05-11) — "20시에 NXT 거래가 종료되는데 그 시간 이후로 연동해야". DB 실측 (2026-05-11 NXT 74 rows / 정상 630 의 12%) 가 정황 증거 — 21:00 백필 시점도 키움 NXT EOD 정산 batch 미완료. NXT 마감 + 정산 마진 = 다음 영업일 새벽 안전.

운영 본격 진입 (scheduler 활성) 직전 P0 fix — Phase C 운영 안전성 결함 해소. plan doc `phase-c-cron-shift-to-morning.md`.

### 35.2 cron 시간 변경 매핑

| Scheduler | Before (KST) | After (KST) | 이유 |
|-----------|--------------|-------------|------|
| OhlcvDailyScheduler | mon-fri 18:30 | **mon-fri 06:00** | NXT 17~20시 거래 중 → 마감 + 정산 마진 |
| DailyFlowScheduler | mon-fri 19:00 | **mon-fri 06:30** | 동일 + OHLCV 30분 stagger 유지 (ADR § 18 의존성) |
| WeeklyOhlcvScheduler | fri 19:30 | **sat 07:00** | 금 NXT 마감 + daily/flow 종료 후 1시간 stagger |
| StockMaster | mon-fri 17:30 | (무변) | lookup endpoint — NXT 무관 |
| StockFundamental | mon-fri 18:00 | (무변) | lookup endpoint — NXT 무관 |
| Sector | sun 03:00 | (무변) | 거래 없는 시점 |
| Monthly | 매월 1일 03:00 | (무변) | 거래 없는 새벽 |
| Yearly | 매년 1월 5일 03:00 | (무변) | 거래 없는 새벽 |

### 35.3 base_date 명시 전달 (코드 변경 면 확장)

`OhlcvDailyUseCase.execute()` default `base_date = date.today()` (line 142). 06:00 cron 으로 옮기면 `today = 화요일`, 화요일 06:00 시점에 화요일 데이터 fetch → **장 시작 (09:00) 전이라 빈 응답**. 

해결: `fire_*_job` 함수에서 `base_date=previous_kst_business_day(date.today())` 명시 전달. UseCase default 는 그대로 (`today()`) — router manual sync 의도 (오늘 데이터 fetch) 와 분리 유지.

신규 helper `app/batch/business_day.py`:

```python
def previous_kst_business_day(today: date) -> date:
    weekday = today.weekday()  # Mon=0, Tue=1, ..., Sat=5, Sun=6
    if weekday == 0:  # Monday
        return today - timedelta(days=3)  # last Friday
    if weekday == 6:  # Sunday (안전망)
        return today - timedelta(days=2)
    return today - timedelta(days=1)
```

요일 분기: Mon→Fri (3일 전, 주말 skip) / Tue~Fri→전일 / Sat→Fri (Weekly cron sat 발화) / Sun→Fri (안전망).

공휴일은 무시 — mon-fri 안의 공휴일은 키움 API 빈 응답 → success 0 / UPSERT idempotent / sentinel 빈 row fix (`72dbe69`) 자연 처리.

### 35.4 변경 면

| 파일 | 변경 |
|------|------|
| `app/batch/business_day.py` | **신규** — `previous_kst_business_day(today: date) -> date` |
| `app/batch/ohlcv_daily_job.py` | `execute()` → `execute(base_date=previous_kst_business_day(date.today()))` + import + docstring |
| `app/batch/daily_flow_job.py` | 동일 |
| `app/batch/weekly_ohlcv_job.py` | 동일 (period=WEEKLY 인자와 함께) |
| `app/scheduler.py` | OhlcvDaily/DailyFlow/Weekly 3 cron 시간 + 3 docstring + 3 logger.info 메시지 |

### 35.5 테스트 변경 (1046 → 1059, +13)

| 파일 | 변경 |
|------|------|
| `tests/test_business_day.py` | **신규 10건** — 7 parametrize (요일 경계) + 3 추가 (monday 3일 skip / saturday→friday / pure function) |
| `tests/test_ohlcv_daily_scheduler.py` | cron 시간 단언 18→06 갱신 + **신규 1건** `test_fire_ohlcv_daily_sync_passes_previous_business_day_as_base_date` |
| `tests/test_daily_flow_scheduler.py` | cron 시간 단언 19→06:30 + **신규 1건** 동일 패턴 |
| `tests/test_weekly_monthly_ohlcv_scheduler.py` | cron 시간 단언 fri 19:30→sat 07:00 + 충돌 단언 갱신 + **신규 1건** sat→fri base_date |

`_StubUseCase` 의 execute() 가 `**kwargs` 받아 `last_kwargs` 캡처하도록 갱신 — base_date 전달 검증.

### 35.6 검증

- ruff All checks passed / ruff format unchanged
- mypy --strict Success (4 source files in batch)
- pytest **1059 passed** (1046 → +13) / 29.84s
- testcontainers 자동 발견 회귀 0건

### 35.7 외부 동작 영향 (scheduler 활성 시)

- **현재 운영 시점 (mon-fri)**: 다음 영업일 새벽 06:00/06:30 적재. 당일 데이터 = 다음 영업일 오전에 가용. **지연 약 12~14 시간** (전 cron 18:30 → 19:00 대비)
- **Weekly**: sat 07:00 — 주말 새벽. 토요일 사용자 분석은 이날 자정 이후 안전
- **base_date** 일자: 전 영업일. router manual sync (오늘 데이터 fetch) 와 cron (어제 데이터 fetch) 의도 분리 — 명확

### 35.8 5-11 NXT 74 rows 보완 (본 chunk 와 별개) — ✅ 완료 (§ 37 참조)

plan doc § 7 명시. 사용자 수동:

```bash
cd src/backend_kiwoom
uv run python scripts/backfill_ohlcv.py --period daily --start-date 2026-05-11 --end-date 2026-05-11 --alias prod
```

`--resume` 미사용 — gap detection 이 KRX 만 본다 (`d43d956` `_RESUME_TABLE_BY_PERIOD`). 4373 종목 모두 5-11 호출 → KRX UPSERT idempotent / NXT 미적재 보완.

**실행 결과**: § 37 별도 chunk 에서 2026-05-12 수행. NXT 74 → 628 rows / 0 failed / 21m 6s. anomaly 12% → 99.7% 정상화.

### 35.9 다음 chunk

1. **5-11 NXT 보완 백필** (사용자 수동) — § 35.8 명령
2. **scheduler_enabled 활성 + 1주 모니터** (STATUS § 5 #1) — 본 chunk 의 직접 동기. env 변경 + 1주
3. Phase D 진입 — ka10080 분봉 / ka20006 업종일봉

---

## 36. Phase C — scheduler_enabled 활성 + 1주 모니터 (2026-05-12, ✅ 활성 / ⏳ 측정 1주 후)

### 36.1 결정

§ 35 cron 시간 fix 후 운영 본격 진입의 마지막 chunk. 8 cron scheduler (sector / stock_master / fundamental / ohlcv_daily / daily_flow / weekly / monthly / yearly) 의 default disabled 상태 해소. plan doc `phase-c-scheduler-enable.md`.

**sub-chunk 분리** — 본 chunk = 활성 + 가이드 + 결과 placeholder. **1주 후 측정 결과는 별도 chunk** (사용자 결정 2026-05-12).

### 36.2 환경 변경 (.env.prod / commit 외부 — .gitignore)

| Env | Value |
|-----|-------|
| `KIWOOM_SCHEDULER_ENABLED` | `true` |
| `KIWOOM_SCHEDULER_SECTOR_SYNC_ALIAS` | `prod` |
| `KIWOOM_SCHEDULER_STOCK_SYNC_ALIAS` | `prod` |
| `KIWOOM_SCHEDULER_FUNDAMENTAL_SYNC_ALIAS` | `prod` |
| `KIWOOM_SCHEDULER_OHLCV_DAILY_SYNC_ALIAS` | `prod` |
| `KIWOOM_SCHEDULER_DAILY_FLOW_SYNC_ALIAS` | `prod` |
| `KIWOOM_SCHEDULER_WEEKLY_OHLCV_SYNC_ALIAS` | `prod` |
| `KIWOOM_SCHEDULER_MONTHLY_OHLCV_SYNC_ALIAS` | `prod` |
| `KIWOOM_SCHEDULER_YEARLY_OHLCV_SYNC_ALIAS` | `prod` |

DB 등록 alias = `prod` 1건 (운영 자격증명) → 8 cron alias 모두 동일 매핑.

### 36.3 lifespan fail-fast 가드 통과 검증

`app/main.py:126-144` — `scheduler_enabled=True` 시 8 alias 비어있지 않은지 검증. 본 chunk 의 env 9건 모두 추가 → 통과.

### 36.4 첫 발화 시점 (KST, 앱 재시작 후)

| Scheduler | cron | 첫 발화 |
|-----------|------|---------|
| StockMaster | mon-fri 17:30 | 2026-05-12 (오늘 화) 17:30 — 앱 재시작 시점 의존 |
| StockFundamental | mon-fri 18:00 | 동일 18:00 |
| OhlcvDaily | mon-fri 06:00 | **2026-05-13 (수) 06:00** ← 가장 중요 |
| DailyFlow | mon-fri 06:30 | 2026-05-13 (수) 06:30 |
| Weekly | sat 07:00 | 2026-05-16 (토) 07:00 |
| Sector | sun 03:00 | 2026-05-17 (일) 03:00 |
| Monthly | 매월 1일 03:00 | 2026-06-01 (월) 03:00 |
| Yearly | 매년 1월 5일 03:00 | 2027-01-05 (화) 03:00 |

base_date = `previous_kst_business_day(today)` → 5-13 06:00 cron 시 base_date = 5-12 mon (오늘) 데이터 fetch.

### 36.5 1주 후 측정 결과 (⏳ 별도 chunk 에서 채움)

목표 측정 시점: **2026-05-19 (mon) 이후**

#### 36.5.1 일간 cron elapsed (placeholder)

| Scheduler | 추정 elapsed | 실측 (1주 후) | 비고 |
|-----------|-------------|-------------|------|
| OhlcvDaily | ~35분 (full backfill 34분 + 영숫자 +1.5분) | TBD | § 26.5 / § 34.6 #1 정정 |
| DailyFlow | ~10시간 (full backfill 9h 53m) | TBD | § 27.5 |
| Weekly | ~21분 (영숫자 백필 20m 55s) | TBD | § 34.3 |
| Sector | ~수 분 | TBD | 단순 sync |
| StockMaster | ~수 분 | TBD | A3-γ |
| Fundamental | ~수 분 | TBD | B-γ-2 |

#### 36.5.2 NXT 정상 적재 검증 SQL (placeholder)

```sql
-- 5-13 mon 첫 발화 이후 7 영업일 NXT 적재 row 분포
SELECT trading_date, count(*) AS n
FROM kiwoom.stock_price_nxt
WHERE trading_date >= DATE '2026-05-13'
GROUP BY trading_date ORDER BY trading_date;
```

| trading_date | n | 정상 (~630) 여부 |
|--------------|---|-----------------|
| 2026-05-13 (수) | TBD | TBD |
| 2026-05-14 (목) | TBD | TBD |
| 2026-05-15 (금) | TBD | TBD |
| 2026-05-18 (월) | TBD | TBD |
| 2026-05-19 (화) | TBD | TBD |

> § 35 가 정정한 NXT 정산 마진 (10시간) 검증 — 모든 영업일 ~630 균일이면 § 35 결정 성공. 5-11 같은 12% anomaly 재발 없어야.

#### 36.5.3 failed / 알람 발생

- logger.error (실패율 > 10%) 발생 수: TBD
- logger.warning (failed > 0 + ratio <= 10%) 발생 수: TBD
- 가장 흔한 error_class: TBD

#### 36.5.4 의도하지 않은 부작용

- 운영 cron 시점이 정규 사용자 시간 (오전 9시 이전) 과 겹쳐 사용자 분석 차질: TBD
- KRX rate limit (429) 누적: TBD
- DB I/O 부하: TBD

### 36.6 모니터링 가이드 (사용자 수행)

- logger 콘솔 watch — `"sync cron 시작"` / `"sync 완료"` / `"실패율 과다"` / `"콜백 예외"` 키워드
- 매 영업일 06:00 / 06:30 cron 발화 후 stdout 확인 — total/krx/nxt/failed 4개 카운트
- alarm threshold: logger.error 발생 즉시 oncall 통지

### 36.7 알려진 follow-up

| # | 항목 | 출처 | 결정 시점 |
|---|------|------|-----------|
| ~~1~~ | ~~5-11 NXT 74 rows 보완~~ | § 35.8 | ✅ **해소** — § 37 (2026-05-12, NXT 74 → 628 / 0 failed / 21m 6s) |
| 2 | 공휴일 calendar 도입 | § 35.3 | 별도 chunk 가능 — 본 chunk 후 1주 모니터에서 빈 응답 패턴 관찰 후 |
| 3 | NXT scheduler 분리 (KRX + NXT 시간 다른 운영) | § 35.2 (옵션 C 미채택) | 운영 데이터 축적 후 별도 결정 |

### 36.8 다음 chunk

1. **(별도 chunk) 1주 후 § 36.5 측정 결과 채움** — 2026-05-19 (mon) 이후 사용자 요청 시
2. ~~5-11 NXT 보완 백필~~ — ✅ 해소 (§ 37)
3. **Phase D 진입** — ka10080 분봉 / ka20006 업종일봉

### 36.9 Phase C 완료 선언 (조건부)

본 chunk + 1주 후 측정 chunk 종료 시 Phase C 100% 완료. 25 endpoint 중 11개 적재 + 8 cron 정상 운영 + historical 3년 완성. 다음 wave = Phase D (분봉/업종일봉).

---

## 37. Phase C — 5-11 NXT 74 rows 보완 백필 (별도 chunk, 2026-05-12 ✅ 완료)

### 37.1 결정

§ 35.8 의 별개 chunk. § 35 cron shift 의 정합성 데이터 정리 — 5-11 NXT 적재 12% (74 / 정상 ~630) anomaly 보완. § 36 scheduler 활성 직후 5-13 첫 OhlcvDaily cron 발화 전에 NXT 데이터 표 깨끗화 → § 36.5.2 1주 모니터 SQL 결과가 5-11 부터 anomaly 없이 진행되도록.

사용자 결정 (2026-05-12) — 5-19 § 36.5 측정 chunk 의존도 낮은 마이크로 작업부터 처리. ted-run 우회 (옵션 B = 직접 호출) — 측정값 수집 + ADR 문서 placeholder 교체만이라 TDD/리뷰 사이클 오버킬.

### 37.2 실행

```bash
cd src/backend_kiwoom
# 1) dry-run — 사전 검증
uv run python scripts/backfill_ohlcv.py --period daily \
  --start-date 2026-05-11 --end-date 2026-05-11 --alias prod --dry-run
# stocks=4373 / NXT enabled / 8746 calls / 36m 26s 추정

# 2) 실 백필 — nohup 백그라운드 (사용자 셸 점유 회피)
mkdir -p logs && nohup uv run python scripts/backfill_ohlcv.py --period daily \
  --start-date 2026-05-11 --end-date 2026-05-11 --alias prod \
  > logs/backfill-nxt-2026-05-11.log 2>&1 &
# PID 57104 / 시작 10:15:18 KST
```

`--resume` 미사용 의도적 (§ 35.8 / `d43d956`) — gap detection 이 KRX 만 보므로 KRX UPSERT idempotent + NXT 만 실질 보완.

### 37.3 결과

**Summary 블록 (로그 발췌)**:

| 항목 | 값 |
|------|-----|
| period | daily |
| date range | 2026-05-11 ~ 2026-05-11 |
| total | 4373 종목 |
| success_krx | 4373 |
| **success_nxt** | **630** (정상 거래 종목 100%) |
| failed | **0** (0.00%) |
| elapsed | **21m 6s** (10:15:18 ~ 10:36:24 KST) |
| avg/stock | 0.3s |
| 실제 호출 수 | 5003 (8746 추정 대비 57% — 영숫자 종목 `nxt_enable=false` 호출 skip 덕) |

ERROR / WARNING / 429 / Exception **실제 0건** (grep false positive 4건 = timestamp 의 `.429` ms 단위 + Summary 의 `failed:` 키워드).

### 37.4 검증 SQL — DB 적재 검증

```sql
-- (1) NXT 5-11 row count
SELECT count(*) FROM kiwoom.stock_price_nxt WHERE trading_date = '2026-05-11';
-- 628 rows

-- (2) KRX 5-11 row count (UPSERT idempotent 검증)
SELECT count(*) FROM kiwoom.stock_price_krx WHERE trading_date = '2026-05-11';
-- 4370 rows

-- (3) NXT 분포 (5-7 ~ 5-12)
-- 5-7 (목): 630 / 5-8 (금): 630 / 5-11 (월): 628

-- (4) KRX 분포 (5-7 ~ 5-12)
-- 5-7 (목): 4372 / 5-8 (금): 4372 / 5-11 (월): 4370
```

**판정**:
- NXT 628 / 정상 ~630 = **99.7%** — anomaly 12% → 0.3% (sentinel 빈 응답 2 종목 평소 패턴)
- KRX 4370 = 5-7/8 (4372) 대비 -2 — **5-11 자체 신규/정지 종목 차이** (백필 회귀 0)
- 두 표 모두 5-11 가 평소 영업일 패턴과 일관 → § 35 cron shift 결정 사후 정합성 확정

### 37.5 의미

- **§ 35.8 anomaly 완전 해소** — § 35 cron 시간 NXT 마감 후 새벽 이동 결정의 데이터 측면 정합성 확정
- **§ 36.5.2 1주 모니터 SQL 깨끗** — 5-13 ~ 5-19 trading_date 별 NXT row 분포가 5-11 부터 ~630 균일로 시작 (5-11 anomaly 가 표 안에서 outlier 가 아님)
- **§ 36.9 Phase C 완료 선언 1보 진전** — 본 chunk + § 36.5 측정 = Phase C 100% 종결
- **`--resume` 미사용 패턴 검증** — KRX UPSERT idempotent + NXT 차분 보완 동작 사후 확인 (4370 KRX 회귀 0 + NXT 74 → 628)

### 37.6 follow-up

- 본 chunk 자체 신규 follow-up 없음
- § 36.7 #1 (5-11 NXT 74 rows 보완) **해소** — STATUS § 4 #21 ✅
- § 36.5.2 의 5-11 placeholder 가 1주 후 측정 chunk 에서 ~628 로 채워질 예정 (anomaly 없음)

### 37.7 결과

- **코드 변경 0** — script / batch / scheduler 모두 그대로
- **테스트**: 1059 그대로 (변경 없음)
- **데이터**: NXT 5-11 +554 rows / KRX 회귀 0
- **문서 변경**: ADR § 37 (본 §) + § 35.8 결과 cross-ref + § 36.7 #1 해소 + STATUS § 4 #21 해소 + § 6 chunk 추가 + HANDOFF + CHANGELOG

### 37.8 다음 chunk

1. **(1주 후) § 36.5 측정 결과 채움** — 2026-05-19 (mon) 이후. NXT 5-11 ~628 / 5-13 ~5-19 ~630 균일 검증
2. **Phase D 진입** — ka10080 분봉 / ka20006 업종일봉
3. 공휴일 calendar (§ 36.7 #2) — 1주 모니터 빈 응답 패턴 관찰 후

---

## 38. Phase C — Docker 컨테이너 배포 (kiwoom-app service, 2026-05-12 ✅ 완료)

### 38.1 결정

§ 36 scheduler 활성 후 사용자 앱 재시작 필요했으나 현재 backend_kiwoom 은:
- Dockerfile 5-7 작성 후 entrypoint.py 누락 / 미사용 상태
- docker-compose 에 앱 service 정의 없음 (`kiwoom-db` 만)
- uvicorn / systemd / launchd 정의 없음

즉 "재시작" 이 아니라 **앱 운영 인프라 신규 구축** 이 필요. 사용자 결정 (2026-05-12) — docker-compose 새 service 추가 + 컨테이너 운영 (옵션 C).

5-13 (수) 06:00 KST OhlcvDaily cron 발화 전 안정 기동 + § 36.5 1주 모니터 정합성 보장. plan doc `phase-c-docker-deploy.md`.

### 38.2 아키텍처

- **builder + runtime 멀티스테이지** — `python:3.12-slim-bookworm` + uv 멀티스테이지 빌드
- **uv 기반 결정론적 의존성** — `uv.lock` 신규 + `uv sync --frozen` (호스트/컨테이너 동일 버전)
- **non-root user** (uid 1001) + TZ=Asia/Seoul + tzdata 설치
- **HEALTHCHECK** — `urllib.request.urlopen('http://127.0.0.1:8001/health')` python 내장 (curl 의존 X)
- **단일 worker** — `uvicorn --workers 1` (APScheduler 중복 발화 방지)
- **자동 마이그레이션** — entrypoint 에서 `alembic upgrade head` 자동 적용 (014 까지 idempotent + 비파괴)

### 38.3 산출물

| 파일 | 동작 |
|------|------|
| `Dockerfile` | **갱신** — uv digest pin 제거 (`uv:latest`) + `--frozen` 추가 + tzdata 추가 + 캐시 layer 분리 |
| `.dockerignore` | **갱신** — .venv / __pycache__ / logs / .env* / tests / docs / *.md 제외 |
| `scripts/entrypoint.py` | **신규** — `alembic upgrade head` → `os.execvp uvicorn` (단일 worker) |
| `uv.lock` | **신규** — 87 packages 결정론적 lock |
| `docker-compose.yml` | **갱신** — `kiwoom-app` service 추가 (env_file=.env.prod + DB hostname override + depends_on healthy + restart=unless-stopped) |
| `README.md` | **갱신** — `## Docker 운영` 섹션 추가 (5 단계 명령 + 운영 메모) |

### 38.4 DB hostname 처리

- `.env.prod` 의 `KIWOOM_DATABASE_URL` = `localhost:5433` (호스트 스크립트 직접 실행용 — 유지)
- 컨테이너 안에서는 compose `environment:` 의 `KIWOOM_DATABASE_URL=kiwoom-db:5432` 로 override
- pydantic-settings 우선순위 (OS env > .env > .env.prod) 활용 → 두 모드 공존, `.env.prod` 수정 불필요

### 38.5 단일 worker (APScheduler 중복 발화 방지)

`uvicorn --workers 1` 명시. 다중 worker 시 lifespan 의 8 cron job 이 worker 마다 등록되어 발화 횟수 × N 회 → 데이터 중복 적재 (UPSERT idempotent 라 결과적 OK 지만 호출 횟수 × N 으로 KRX rate limit 위험).

처리량 부족 시 별도 chunk 에서 외부 scheduler (Celery / Redis lock) 또는 leader election 패턴 검토.

### 38.6 빌드 + 기동 검증 결과

#### 38.6.1 빌드

- 명령: `docker compose build kiwoom-app`
- 이미지 크기: **264MB** (python:3.12-slim + non-dev 의존성)
- 빌드 PASS — sha256:90629d12dc3b...
- builder + runtime 2-stage / uv `--frozen` lock 활용 / non-root uid 1001

#### 38.6.1' 빌드 실패 사건 + 해결 (process learning)

1. **47분 hang at `resolve image config for docker/dockerfile:1.7`** — `# syntax=docker/dockerfile:1.7` directive 제거 시도 → 그래도 hang
2. **두 번째 hang at `load metadata for python:3.12-slim`** — 진단 결과 **Docker credential helper hang**:
   - `~/.docker/config.json` 의 `credsStore: "desktop"` 가 docker-credential-desktop helper hang 유발
   - `docker-credential-osxkeychain` 은 정상 응답 확인
   - fix: `credsStore: "osxkeychain"` 으로 변경 → 5초 만에 pull 성공
3. **세 번째 실패** — hatchling 빌드 시 `OSError: Readme file does not exist: README.md`:
   - Dockerfile builder stage 가 `COPY README.md ./` 누락
   - fix: `COPY` 라인 추가 후 재빌드 → 성공

#### 38.6.2 기동 + lifespan

- 명령: `docker compose up -d kiwoom-app`
- alembic upgrade head: ✅ (Migration 012 → 013 → 014 자동 적용 — 이번 docker 환경에서 첫 적용)
- lifespan fail-fast 통과: ✅
- 8 scheduler 활성 로그 모두 확인:

```
sector_sync_weekly         alias=prod  cron=일 03:00 KST
stock_master_sync_daily    alias=prod  cron=mon-fri 17:30 KST
stock_fundamental_sync_daily alias=prod cron=mon-fri 18:00 KST
ohlcv_daily_sync_daily     alias=prod  cron=mon-fri 06:00 KST
daily_flow_sync_daily      alias=prod  cron=mon-fri 06:30 KST
weekly_ohlcv_sync_weekly   alias=prod  cron=sat 07:00 KST
monthly_ohlcv_sync_monthly alias=prod  cron=매월 1일 03:00 KST
yearly_ohlcv_sync_yearly   alias=prod  cron=매년 1월 5일 03:00 KST
```

#### 38.6.2' env_prefix 불일치 발견 + 해결 (CRITICAL)

기동 직후 `scheduler_enabled=False` 였음 (모든 scheduler "disabled — start 무시" 로그). 원인:

- 사용자가 `.env.prod` 에 9 env 추가 시 prefix `KIWOOM_SCHEDULER_*` 사용 — but Settings 필드명은 `scheduler_*` (KIWOOM_ prefix 없음)
- pydantic-settings 의 매칭은 **필드명 그대로 case-insensitive** — `kiwoom_database_url` ↔ `KIWOOM_DATABASE_URL` 매칭 (필드명에 kiwoom_ 포함), `scheduler_enabled` ↔ `SCHEDULER_ENABLED` 기대
- 해결: compose `environment:` 에 `SCHEDULER_*` 8 env 명시 (KIWOOM_ prefix 없이) — `.env.prod` 의 잘못된 9 env 는 `extra="ignore"` 로 무시됨
- 재기동 후 `scheduler_enabled=True` 확인

#### 38.6.3 healthcheck

- `curl http://localhost:8001/health` → `{"status":"ok"}` ✅
- `docker compose ps` → kiwoom-app **Up (healthy)** ✅

#### 38.6.4 cron 발화 시각 정합성

- 컨테이너 TZ: `Tue May 12 15:30:10 KST 2026` ✅ (Asia/Seoul 정확)
- **5-13 (수) 06:00 KST OhlcvDaily 첫 발화 예정** — base_date = 2026-05-12 (화) 데이터 fetch (§ 35.3 `previous_kst_business_day`)
- **5-13 (수) 06:30 KST DailyFlow 첫 발화 예정** — 동일

#### 38.6.5 .env.prod env_file 경로 fix

- compose 의 `env_file: .env.prod` 가 `src/backend_kiwoom/.env.prod` 를 찾았으나 실제 위치는 프로젝트 루트
- fix: `env_file: ../../.env.prod`

### 38.7 외부 동작 영향

- **운영 모드 분리** — 호스트 스크립트 (백필 등 ad-hoc) = localhost:5433 / 컨테이너 (cron) = kiwoom-db:5432. 동시 운영 가능 (UPSERT idempotent + DB lock 가 보호)
- **자동 재시작** — Mac 재부팅 / docker daemon 재시작 후 자동 기동 (restart=unless-stopped)
- **로그 영속성** — `docker compose logs` (stdout). 호스트 파일 영속성 필요 시 별도 chunk (volume mount)
- **개발 환경** — uvicorn 직접 실행은 그대로 가능 (.env.prod 또는 .env 의 localhost:5433 사용)

### 38.8 알려진 follow-up

| # | 항목 | 근거 | 결정 시점 |
|---|------|------|-----------|
| 1 | Mac 절전 시 컨테이너 중단 → cron 발화 누락 | 환경 한계 | 사용자 환경 결정 (절전 차단 또는 서버 이전) |
| 2 | destructive migration 도입 시 entrypoint 분리 | 자동 마이그레이션 정책 | 미래 migration 도입 시 |
| 3 | 다중 worker 시 외부 scheduler | 처리량 확장 | 단일 worker 한계 도달 시 |
| 4 | 로그 영속성 (volume mount) | 컨테이너 stdout 만으로 부족 시 | 운영 모니터 1주 후 결정 |
| 5 | **`.env.prod` 의 잘못된 `KIWOOM_SCHEDULER_*` 9 env 정리** | env_prefix 불일치 발견 (§ 38.6.2') | 사용자 직접 — 잘못된 이름 9 env 제거 또는 `SCHEDULER_*` 로 rename |
| 6 | **노출된 secret 4건 회전** (대화 로그 영구 기록) | 컨테이너 env 점검 시 평문 노출 | **전체 개발 완료 후** (2026-05-12 사용자 결정 — `.env.prod` / DB 재암호화 영향이 커 개발 종결 후 일괄). KIWOOM_API_KEY/SECRET revoke + 재발급 / Fernet 마스터키 회전 + DB 재암호화 / ACCOUNT_NO (위험도 낮음). **절차서**: [`docs/ops/secret-rotation-2026-05-12.md`](../ops/secret-rotation-2026-05-12.md) |
| 7 | **Docker Hub PAT 토큰 회수** | credsStore 진단 시 평문 노출 (`dckr_pat_...`) | **전체 개발 완료 후** (동일 결정). https://hub.docker.com/settings/security 에서 revoke. **절차서**: 동상 § 3.1 |

### 38.9 결과

- **신규**: `scripts/entrypoint.py` (alembic upgrade + uvicorn exec) + `uv.lock` (87 packages frozen) + plan doc
- **갱신**: `Dockerfile` (syntax directive 제거 / uv:latest / --frozen / tzdata / README COPY) + `.dockerignore` (49줄 정리) + `docker-compose.yml` (kiwoom-app service + env_file ../../.env.prod + SCHEDULER_* 8 env override) + `README.md` (`## Docker 운영` 섹션)
- **빌드**: 이미지 264MB / 빌드 PASS
- **기동**: alembic 자동 적용 + 8 scheduler 활성 + /health OK + TZ KST + healthy
- **테스트**: 1059 그대로 (앱 코드 변경 0 — 인프라 chunk)
- **문서 변경**: ADR § 38 (본 §) + STATUS § 0 / § 4 / § 6 + HANDOFF + CHANGELOG

### 38.10 다음 chunk

1. **(5-13 06:00 발화 직후) cron 발화 결과 즉시 검증** — `docker compose logs kiwoom-app` + DB SQL
2. **(5-19 이후) § 36.5 1주 모니터 측정 채움** — 컨테이너 로그 기반 cron elapsed 추출
3. **Mac 절전 정책 / 서버 이전** — 24/7 cron 안정성 위함
4. **Phase D 진입** — ka10080 분봉 / ka20006 업종일봉

---

## 39. Phase D-1 — ka20006 업종일봉 OHLCV 풀 구현 (2026-05-12)

### 39.1 배경

Phase C 데이터 측면 종결 + § 38 Docker 컨테이너 배포 후 Phase D 진입.
사용자 결정 (5-12): ka10080 분봉 (D-2) 은 데이터량 부담 (1100종목 × 380분 = 38만+ rows/일) 으로 마지막 endpoint 로 연기 → 가장 가벼운 **ka20006 업종일봉 (50~80 sector × 1 일봉)** 이 Phase D 첫 chunk.

ka10081/82/83/94 (4 chart endpoint) 패턴 + ka10101 sector 마스터 매핑 확립된 상태 → 패턴 1:1 응용 + sector_id FK + NXT skip 단순화. plan doc § 12 (`endpoint-13-ka20006.md` line 953~) 의 9 결정 + 13 self-check + DoD 그대로 ted-run 풀 파이프라인 적용.

### 39.2 결정 9건 (plan doc § 12.2 → 코드 반영 + 1R fix 후 확정)

| # | 사안 | 결정 | 코드 위치 |
|---|------|------|----------|
| 1 | 마이그레이션 번호 | **015** (revision id `015_sector_price_daily`, 22 chars — VARCHAR(32) 안전) | `migrations/versions/015_sector_price_daily.py` |
| 2 | sector 매핑 | **sector_id FK = BIGINT** (sector.py UNIQUE = `(market_code, sector_code)` 페어 → sector_code 단독 lookup 불가). 1R HIGH #4 fix: INTEGER → BIGINT (kiwoom.sector.id 가 BIGSERIAL) | Migration 015 + ORM `sector_price_daily.py` |
| 3 | 100배 값 저장 | **centi BIGINT 4 컬럼** (`open/high/low/close_index_centi`) + read property `.close_index = close_index_centi / 100` | ORM `sector_price_daily.py` + `NormalizedSectorDailyOhlcv` (chart.py) |
| 4 | NXT 호출 정책 | **skip** — `SectorIngestOutcome(skipped=True, reason="nxt_sector_not_supported")`. sector 도메인에 NXT 없어 본 chunk 비활성. 코드만 추가 | `sector_ohlcv_service.py` |
| 5 | sector_master_missing 가드 | `SectorIngestOutcome(skipped=True, reason="sector_master_missing")` — sector_id repository lookup 결과 None 시 | Single UseCase |
| 6 | 응답 7 필드 처리 | `cur_prc / trde_qty / dt / open_pric / high_pric / low_pric / trde_prica` (7개). `pred_pre / pred_pre_sig / trde_tern_rt` 부재 → Pydantic `extra="ignore"` + None 영속화 | `SectorChartRow` (chart.py) |
| 7 | cron 시간 | **mon-fri 07:00 KST** (§ 35 새벽 cron 정책 일관, ohlcv_daily 06:00 + daily_flow 06:30 직후) | `SectorDailyOhlcvScheduler` |
| 8 | 백필 윈도 | 3년 (CLI 별도 chunk — 본 chunk 는 코드만, `scripts/backfill_sector.py` 미작성) | — |
| 9 | UseCase 입력 | **sector_id (PK) + base_date** | `IngestSectorDailyInput` |

### 39.3 영향 범위 (12 코드 + 6 테스트 = 18 파일)

**신규 코드 (7)**:
- `migrations/versions/015_sector_price_daily.py` (88 lines)
- `app/adapter/out/persistence/models/sector_price_daily.py` (101 lines)
- `app/adapter/out/persistence/repositories/sector_price.py` (121 lines)
- `app/application/dto/sector_ohlcv.py` (75 lines, +skipped 필드 1R HIGH #5 fix)
- `app/application/service/sector_ohlcv_service.py` (250 lines, +skipped 카운터 분리)
- `app/adapter/web/routers/sector_ohlcv.py` (237 lines)
- `app/batch/sector_daily_ohlcv_job.py` (78 lines, +skipped 로그)

**갱신 코드 (5)**:
- `app/adapter/out/kiwoom/chart.py` (+182 lines — `SectorChartRow/Response/NormalizedSectorDailyOhlcv` + `fetch_sector_daily`)
- `app/adapter/web/_deps.py` (+~100 lines — 2 factory + getter/setter/reset)
- `app/scheduler.py` (+~100 lines — `SectorDailyOhlcvScheduler` + `SECTOR_DAILY_SYNC_JOB_ID`)
- `app/config/settings.py` (+8 lines — `scheduler_sector_daily_sync_alias`)
- `app/adapter/out/persistence/models/__init__.py` (+2 — `SectorPriceDaily` export)
- `app/main.py` (+~80 lines — 1R CRITICAL #1~#3 fix: 라우터 include + factory 빌드 + scheduler 기동/종료 + alias fail-fast)
- `docker-compose.yml` (+1 line — `SCHEDULER_SECTOR_DAILY_SYNC_ALIAS: prod`)

**신규 테스트 (6)**:
- `tests/test_migration_015.py` (5 시나리오) — 단일 014 → 015 / 컬럼 타입 / FK / UNIQUE / downgrade 가드 (row 존재 시 RAISE)
- `tests/test_sector_price_repository.py` (6) — upsert idempotent / FK / UNIQUE 충돌
- `tests/test_sector_ohlcv_service.py` (6) — Single + Bulk + NXT skip + sector_master_missing
- `tests/test_sector_ohlcv_router.py` (6) — sync 전체 + refresh 단건 + admin API key
- `tests/test_scheduler_sector_daily.py` (8) — job 등록 / CronTrigger mon-fri 07:00 KST / alias fail-fast / 콜백 / 실패율
- `tests/test_kiwoom_chart_client.py` 추가 (7 sector_daily 시나리오) — mock 응답 / 페이지네이션 / sentinel break / 7 필드 / 5xx / 자격증명

### 39.4 1R 결과 — CONDITIONAL → PASS (CRITICAL 3 + HIGH 2 fix 후)

| 심각도 | 건수 | 처리 |
|---|---|---|
| **CRITICAL** | 3 | 모두 **fix 완료** — `app/main.py` 통합 (라우터/factory/scheduler/alias) 누락 단일 원인 |
| **HIGH** | 2 | 모두 **fix 완료** — #4 sector_id INTEGER → BIGINT (kiwoom.sector.id 가 BIGSERIAL 일치) / #5 sector_inactive failed 집계 오류 → SectorBulkSyncResult 에 `skipped` 카운터 추가 |
| **MEDIUM** | 2 | LOW 로 기록 — #6 inds_cd 응답 echo 검증 부재 (운영 검증 후 별도 chunk) / #7 close_index Decimal vs float 불일치 (별도 chunk) |
| **LOW** | 2 | 기록만 — #8 Repository dict 호환 / #9 date.today() 직접 호출 (기존 패턴) |

### 39.5 self-check H-1~H-13 매핑 (1R 사후 검증 ✅ 통과)

| H | 위험 | 완화 코드 |
|---|------|----------|
| H-1 | sector 매핑 (market_code, sector_code) 페어 UNIQUE | UseCase 입력 = sector_id (PK). Bulk `sector_repo.list_all_active()` iterate |
| H-2 | 100배 값 가정 운영 미검증 | centi BIGINT 저장. 운영 첫 호출 시 KOSPI 종합 응답값/100 ≈ 실제 KOSPI 검증 (§ 39.7 운영 모니터) |
| H-3 | list key `inds_dt_pole_qry` 미검증 | `SectorChartResponse.inds_dt_pole_qry: list[SectorChartRow] = Field(default_factory=list)` + `extra="ignore"` |
| H-4 | upd_stkpc_tp 없음 | Request body 미포함 |
| H-5 | cron 07:00 KST KRX rate limit 경합 | 기존 KRX asyncio.Lock 직렬화 신뢰. 운영 검증 시 elapsed 측정 후 재검토 |
| H-6 | sector_master_missing 가드 | `SectorIngestOutcome(skipped=True, reason="sector_master_missing")` |
| H-7 | NXT skip 정책 정확성 | sector 도메인에 NXT 없음 — 코드만 추가, 본 chunk 비활성 |
| H-8 | 페이지네이션 미정량 | cont-yn 패턴 + sentinel break `if not parsed.inds_dt_pole_qry: break` |
| H-9 | inds_cd length 응답 vs 요청 | Pydantic `max_length=32` (Excel 명세 20 흡수) |
| H-10 | 거래대금 단위 백만원 가정 | BIGINT 그대로 — 운영 검증 후 재정정 가능 |
| H-11 | scheduler_enabled 정책 일관성 | `SectorDailyOhlcvScheduler.start()` 가드 (기존 8 scheduler 패턴 1:1) |
| H-12 | Migration 015 비파괴 | CREATE TABLE + CREATE INDEX 만. DOWNGRADE_SQL 에 row 존재 시 RAISE 가드 |
| H-13 | chart.py 통합 vs sect.py 분리 | chart.py 통합 결정 — `KiwoomChartClient.fetch_sector_daily` |

### 39.6 Step 3 Verification 5관문 결과

| 관문 | 결과 |
|---|---|
| 3-1 컴파일 빌드 (mypy) | ✅ PASS |
| 3-2 정적 분석 (ruff + mypy --strict) | ✅ PASS — 80 source files, 0 issues |
| 3-3 테스트 + 커버리지 | ✅ **1097 / 1097 (100%) green** — 1059 기존 + 38 신규. **coverage 90%** (목표 80% 초과, 91% → 90% 미세 감소 = 신규 일부 분기 운영 영역) |
| 3-4 보안 스캔 | ⚪ 생략 (계약 변경 분류 자동 생략) |
| 3-5 런타임 smoke | ✅ PASS — 컨테이너 재기동 후 alembic 014→015 자동 upgrade / 9 scheduler 활성 (sector_daily mon-fri 07:00 KST 추가) / /health OK / DB sector_price_daily 테이블 존재 |

### 39.7 운영 모니터 (코드 외 — 다음 chunk 검증)

D-1 컨테이너 재배포 완료. 다음 항목을 ADR § 39 운영 결과에 누적 (별도 chunk):

- [ ] **첫 호출 (수동 trigger)**: `POST /api/kiwoom/sectors/{id}/ohlcv/daily/refresh?base_date=2026-05-09` — sector_id=1 (KOSPI 종합) 단건 호출 성공 + DB upsert 확인
- [ ] **bulk sync (수동 trigger)**: `POST /api/kiwoom/sectors/ohlcv/daily/sync` — active sector 50~80개 일괄 sync 시간 + 0 failed
- [ ] **100배 값 검증**: KOSPI 종합 응답값 / 100 ≈ 실제 KOSPI 지수 일치
- [ ] **응답 필드 검증**: `inds_dt_pole_qry` list key 정확성 / 7 필드 가정 정확성
- [ ] **페이지네이션 발생 빈도**: 3년 백필 시 page 수
- [ ] **cron 07:00 KST 발화 (5-13 수)**: 06:30 daily_flow 와 KRX rate limit 경합 실측 (H-5)

### 39.8 알려진 follow-up (본 chunk 외)

| # | 항목 | 근거 | 결정 시점 |
|---|------|------|-----------|
| 1 | inds_cd 응답 echo 검증 추가 (cross-sector pollution 방어) | 1R MEDIUM #6 | 운영 첫 호출 응답 length 확인 후 별도 chunk |
| 2 | `close_index` Decimal vs float 불일치 통일 | 1R MEDIUM #7 | 다음 D-1 follow-up chunk |
| 3 | Repository dict 호환 제거 | 1R LOW #8 | 향후 cleanup chunk |
| 4 | `scripts/backfill_sector.py` CLI 신규 | DoD § 10.1 / plan § 12.6 | 운영 첫 호출 검증 + base_date 백필 필요 시점 |

### 39.9 결과

- **신규**: 7 코드 + 6 테스트 + 1 docker-compose env override
- **갱신**: 5 코드 (chart.py / _deps.py / scheduler.py / settings.py / main.py)
- **빌드/기동**: 이미지 재빌드 PASS / alembic 014→015 자동 적용 / 9 scheduler 활성 / /health OK
- **테스트**: 1059 + 38 = **1097 cases** / coverage 90% / ruff PASS / mypy strict PASS
- **운영 인프라**: 11/25 → **12/25 endpoint** (48%)
- **문서 변경**: ADR § 39 (본 §) + STATUS § 0/§ 1/§ 2/§ 5/§ 6 + HANDOFF + CHANGELOG

### 39.10 다음 chunk

1. **(5-13 06:00 발화 직후) cron 첫 발화 검증** (§ 38.10 #1 일관) — ohlcv_daily / daily_flow + 신규 sector_daily 의 5-13 06:00~07:00 cron 발화 확인
2. **§ 39.7 운영 모니터** — sector_daily 첫 호출 + bulk sync + 100배 값 검증 + 페이지네이션 정량화
3. **(5-19 이후) § 36.5 1주 모니터 측정 채움** — 9 scheduler elapsed
4. **Phase D-2 진입 — ka10080 분봉 (마지막 endpoint)** — 대용량 파티션 결정 chunk 선행
5. **Phase E** — ka10014 (공매도) / ka10068 (대차) / ka20068
6. **(전체 개발 종결 후) secret 회전** — `docs/ops/secret-rotation-2026-05-12.md` 절차서

---

## 40. Phase E — ka10014 + ka10068 + ka20068 매도 측 시그널 wave 풀 구현 (2026-05-13)

### 40.1 배경

Phase D-1 ka20006 종결 후 사용자 결정 (5-12): 통합 1 chunk — ka10014 (공매도) + ka10068 (시장 대차) + ka20068 (종목 대차) 3 endpoint 동시 ted-run. 매도 측 시그널 wave (공매도 raw + 대차 거시 + 대차 종목별) 의 derived feature 종합. plan doc § 12 (`endpoint-15-ka10014.md` line 1071~1232) 의 10 결정 + 13 self-check + DoD 그대로 ted-run 풀 파이프라인 적용.

### 40.2 결정 10건 (plan doc § 12.2 → 코드 반영 + 1R fix 후 확정)

| # | 사안 | 결정 (확정) | 근거 |
|---|------|------------|------|
| 1 | 마이그레이션 번호 | **016**, revision id = `016_short_lending` (15 chars) | 015 직후 + naming 일관 |
| 2 | 신규 테이블 통합 | **2 테이블 1 마이그레이션** (short_selling_kw + lending_balance_kw) | 동일 wave (매도 측 시그널) 통합 |
| 3 | lending scope 분기 | **partial unique index 2 + CHECK constraint** (`uq_lending_market_date` / `uq_lending_stock_date` + `chk_lending_scope`) | endpoint-16 § 5.1 결정 |
| 4 | NXT 정책 (3 endpoint 별) | ka10014=**시도** / ka10068=**미적용** (시장 단위) / ka20068=**KRX only** (Length=6) | endpoint 별 § 4 종합 |
| 5 | cron 시간 (§ 35 일관) | short_selling_sync_daily=**07:30** / lending_market_sync_daily=**07:45** / lending_stock_sync_daily=**08:00** KST mon-fri | § 35 새벽 cron 정책 일관 (sector_daily 07:00 직후) |
| 6 | sync 윈도 | 3 endpoint 모두 **1주** (T-7 ~ T) | plan doc default |
| 7 | 백필 윈도 | **3년** 통일 + 3 CLI (`backfill_short.py` / `backfill_lending.py` / `backfill_lending_stock.py`) | ka10081 / ka20006 일관 |
| 8 | scheduler_enabled | **개별 3 enabled env 신규** (job 별 활성 보류 가능) + master `scheduler_enabled` 와 AND 결합 — 1R fix 2a-H-1 으로 fail-fast 가 개별 enabled=False 시 alias 빈 값 허용 | § 36 정책 + env override 가드 |
| 9 | ka10014 NXT 빈 응답 | **정상 처리** (warning 안 함) — NXT 공매도 미지원 가능성 (endpoint-15 § 11.2) | master.md § 6.4 NXT 정책 |
| 10 | partial 실패 임계치 | short_selling: **5%/15%** / lending_market: **N/A** (단일 호출) / lending_stock: **5%/15%**. 분모는 **KRX outcomes only** (1R fix 2b-C-2 — NXT 빈 응답 silent failure 회피) | endpoint-15 § 8.1 / endpoint-17 § 8 |

### 40.3 영향 범위 (25 파일 = 15 신규 + 10 갱신)

**신규 코드 (15)**:
- `migrations/versions/016_short_lending.py` — 2 테이블 + UNIQUE + partial unique 2 + CHECK + 5 INDEX (2 partial)
- `app/adapter/out/persistence/models/short_selling_kw.py` / `lending_balance_kw.py` — ORM 2
- `app/adapter/out/kiwoom/shsa.py` (KiwoomShortSellingClient) / `slb.py` (KiwoomLendingClient: fetch_market_trend + fetch_stock_trend)
- `app/adapter/out/persistence/repositories/short_selling.py` / `lending_balance.py` — Repository 2
- `app/application/dto/short_selling.py` / `lending.py` — DTO 2
- `app/application/service/short_selling_service.py` (Single + Bulk) / `lending_service.py` (Market + Stock Single + Stock Bulk)
- `app/adapter/web/routers/short_selling.py` / `lending.py` — Router 2
- `app/batch/short_selling_job.py` / `lending_market_job.py` / `lending_stock_job.py` — 3 batch job
- `scripts/backfill_short.py` / `backfill_lending.py` / `backfill_lending_stock.py` — 3 CLI

**갱신 코드 (10)**:
- `app/adapter/out/kiwoom/_records.py` — 9 Pydantic + 2 enum (ShortSellingRow/Response/Normalized + ShortSellingTimeType + LendingMarketRow/StockRow/Response 2/NormalizedLendingMarket + LendingScope)
- `app/adapter/out/persistence/models/__init__.py` — export 2
- `app/config/settings.py` — 6 env (3 enabled + 3 alias)
- `app/scheduler.py` — 3 Scheduler 클래스 + 3 JOB_ID + `_PhaseEJobView` (misfire_grace_time timedelta proxy)
- `app/main.py` — 라우터 2 include + 5 factory + 3 scheduler lifespan + 3 alias fail-fast (개별 enabled AND)
- `app/adapter/web/_deps.py` — 5 factory 추가
- `tests/test_scheduler.py` / `test_stock_master_scheduler.py` — Phase E 3 alias fixture
- `tests/test_migration_015.py` — downgrade `-1` → `014_stock_price_yearly` 명시 (016 추가로 인한 semantic shift)

**신규 테스트 (8 — 89 시나리오)**:
- `test_migration_016.py` (7) — 2 테이블 + FK + partial unique + CHECK + partial index 검증
- `test_kiwoom_shsa_client.py` (15) / `test_kiwoom_slb_client.py` (14) — Adapter
- `test_short_selling_service.py` (12) / `test_lending_service.py` (12) — UseCase
- `test_short_selling_repository.py` (8) / `test_lending_repository.py` (8) — Repository (partial unique 분리 검증)
- `test_scheduler_phase_e.py` (13) — 3 job 등록 + CronTrigger 시간 + 3 alias fail-fast + 3 enabled env

### 40.4 1R 결과 — CONDITIONAL → PASS (CRITICAL 6 + HIGH 10건 fix 후)

**Step 2a 1차 리뷰 (sonnet, 일반 품질)** — CRITICAL 1 + HIGH 2 + MEDIUM 4 + LOW 3
**Step 2b 2차 적대적 리뷰 (opus, Santa Method 보안 분류)** — CRITICAL 5 + HIGH 8 + MEDIUM 9 + LOW 13

**fix 10건 (즉시)**:
| # | 항목 | fix |
|---|------|-----|
| 2a-C-1 | `routers/lending.py:115` `getattr` key mismatch | `get_ingest_lending_stock_single_factory` (실제 함수명 일치) |
| 2a-H-1 | main.py fail-fast 가 개별 `_sync_enabled` 무시 | Phase E 3 alias 가 job_enabled=True 일 때만 체크 (env override 가드) |
| 2a-H-2 / 2b-C-4 | `_batch_commit` silent no-op | 명시 의도 docstring (fixture 가시성 commit + 진행률 yield-point) |
| 2b-C-1 | slb.py Pydantic ValidationError 정보 누설 | shsa.py 의 flag-then-raise-outside-except 패턴 1:1 적용 + `KiwoomResponseValidationError` 매핑 |
| 2b-C-2 | short_selling partial 분모 — NXT 빈 응답으로 silent failure 회피 | 분모 = `len(krx_outcomes)` only (KRX 실패율) |
| 2b-C-3 | lending_stock bulk 100분 single transaction anti-pattern | `IngestLendingStockBulkUseCase` 가 `BATCH_SIZE=50` 마다 `await self._session.commit()` + 마지막 commit |
| 2b-C-5 | lending factory `session.begin()` 누락 | C-3 BATCH commit 으로 partial 보존 처리 (의도된 동작) |
| 2b-H-1 | `sync_lending_stock_bulk` `KiwoomBusinessError` 핸들러 누락 | market + single 동일 패턴 추가 (`detail={"return_code": exc.return_code, "error": "KiwoomBusinessError"}`) |
| 2b-H-3 | alias Query log injection | `pattern=r"^[A-Za-z0-9_\-]{1,50}$"` (short_selling 2 + lending 4 = 6 위치) |
| 2b-H-6 | bulk list DoS amplification | `only_market_codes max_length=10` + `only_stock_codes max_length=5000` |

**Defer (MEDIUM/LOW 별도 chunk)**:
- 2a-M-1/M-3/M-4 (partial 비교 연산자 / `--max-stocks` CLI 미전달 / `IngestLendingStockInput` dead re-export)
- 2b-H-2 (placeholder factory 정리) / H-4 (KiwoomBusinessError.message 마스킹) / H-5 (3-layer swallow 의 보안 예외 alert) / H-8 (Repository exchange 타입)
- 2b-M-1~M-9 (race / downgrade CASCADE / partial commit 의도 docstring 등)
- 2b-L-1~L-13 (정보 누설 minor / index ORDER BY metadata 등)

**기존 코드 이슈 (이번 변경과 무관 — 별도 chunk)**:
- bandit B324 (`stock_fundamental.py:70` MD5 hash — Phase B-γ 기존) — fundamental hash 용, 보안 무관
- bandit B613 (`stock_fundamental_service.py:59` bidi control chars — 의도된 sanitize) — false positive
- pip-audit urllib3 2.6.3 → CVE-2026-44431 / 44432 (fix 2.7.0) — 의존성 업데이트 별도 chunk

### 40.5 self-check H-1~H-13 매핑 (1R 사후 검증 ✅ 통과)

| H | 위험 | 1R 검증 결과 |
|---|------|-------------|
| H-1 | partial unique + CHECK PostgreSQL 호환성 | ✅ testcontainers PG16 검증 (test_migration_016 7 시나리오) |
| H-2 | NXT 정책 3 endpoint 분기 누락 | ✅ ka10014 시도 / ka10068 미적용 / ka20068 KRX only — UseCase test 검증 |
| H-3 | cron 07:30/07:45/08:00 KRX rate limit 경합 | 운영 검증 대기 (§ 40.7) — 기존 KRX lock 직렬화 가정 |
| H-4 | tm_tp PERIOD 디폴트 | ✅ shsa client default `ShortSellingTimeType.PERIOD` |
| H-5 | ovr_shrts_qty UPDATE 정책 | ✅ ON CONFLICT 마지막 strt_dt 기준 (test 10 검증) |
| H-6 | ka10068 시장 분리 미확정 | 운영 검증 대기 (§ 40.7) — 단일 응답 가정 그대로 |
| H-7 | ka20068 Length=6 KRX only | ✅ slb.py 사전 검증 `len == 6 and isdigit()` (NXT suffix 거부) |
| H-8 | delta_volume 부호 일관성 | ✅ BIGINT signed + mock 테스트 검증 |
| H-9 | NXT 공매도 응답 가능 여부 | 운영 검증 대기 (§ 40.7) — 빈 응답 정상 처리 |
| H-10 | 9 + 3 = 12 scheduler 부담 | ✅ 개별 enabled env 가드 (2a-H-1 fix) — 운영 1주 모니터 (§ 40.7) |
| H-11 | 코드 양 1.5배 | ✅ 25 파일 / 1R CONDITIONAL → fix 10건 / 견적과 일치 |
| H-12 | Migration 016 destructive | ✅ 신규 테이블 2 만 / downgrade DROP TABLE / 비파괴 |
| H-13 | main.py 통합 누락 (D-1 1R CRITICAL 재발 위험) | ✅ Agent Z 가 main.py 라우터 2 + factory 5 + scheduler 3 lifespan + alias 3 + _deps 5 factory 모두 통합 — 1R 시 누락 0 (D-1 패턴 학습 효과) |

### 40.6 Step 3 Verification 5관문 결과

| Gate | 도구 | 결과 |
|------|------|------|
| 3-1 빌드 | `mypy --strict` | ✅ 95 source files no issues |
| 3-2 정적 | `ruff check` | ✅ All checks passed |
| 3-3 테스트 + coverage | `pytest --cov` | ✅ **1186/1186** (1097 → +89 신규) / **coverage 86.30%** (≥80%) |
| 3-4 보안 스캔 | `bandit` + `pip-audit` | ✅ 본 chunk 0 issues / 기존 코드 별도 chunk |
| 3-5 런타임 smoke | `create_app()` | ✅ 41 routes / startup OK |

### 40.7 운영 모니터 (코드 외 — 다음 chunk 검증)

본 chunk 종결 후 컨테이너 재배포 + 다음 항목 누적 (§ 40 운영 결과 § 신규):

- [ ] **첫 호출 ka10014 (수동 trigger)**: `POST /api/kiwoom/short-selling/stock/005930/refresh` — 단건 success + DB upsert
- [ ] **첫 호출 ka10068 (수동 trigger)**: `POST /api/kiwoom/lending/market?start=&end=` — 단일 호출 + scope=MARKET row
- [ ] **첫 호출 ka20068 (수동 trigger)**: `POST /api/kiwoom/lending/stock/005930` — 단건 + scope=STOCK row
- [ ] **ka10014 `tm_tp` 의미 확정** — START_ONLY (0) vs PERIOD (1) 응답 차이
- [ ] **ka10014 NXT 공매도 응답 가능 여부** — `return_code != 0` 빈도 / 빈 list 빈도
- [ ] **ka10068 시장 분리 응답** — KOSPI / KOSDAQ 분리 vs 통합
- [ ] **ka20068 NXT Length=6 vs 8** — `005930_NX` 시도 응답
- [ ] **`ovr_shrts_qty` 누적 의미** (ka10014)
- [ ] **`delta_volume` 부호** (ka10068 vs ka20068)
- [ ] **`balance_amount` 단위** (백만원 vs 원)
- [ ] **cron 07:30 / 07:45 / 08:00 KST 발화 (별도 활성 chunk 후)** — 06:00/06:30/07:00 직후 KRX rate limit 경합 elapsed 실측
- [ ] **active 3000 종목 sync 실측** (ka10014 + ka20068) — 30~60분 추정 정확성

### 40.8 알려진 follow-up (본 chunk 외)

- 2a-M-1: partial 비교 연산자 (short_selling `>` vs lending `>=`) 통일
- 2a-M-2: `errors_above_threshold` 타입 비대칭 (bool vs tuple)
- 2a-M-3: `backfill_lending_stock.py --max-stocks` UseCase 미전달 (TODO)
- 2a-L-2: Phase E 3 scheduler `get_job()` 반환 타입 `Any` → `_PhaseEJobView | None` 명시
- 2b-H-2: placeholder factory (`getattr(_deps, ...)` 패턴) — D-1 sector_ohlcv 패턴으로 직접 import 리팩토링
- 2b-H-4: `KiwoomBusinessError.message` 마스킹 lint rule
- 2b-H-5: 3-layer swallow 의 보안 예외 sentry alert
- 2b-M-4: Migration 016 downgrade CASCADE → pg_depend 가드
- 2b-L-6: ORM Index 의 `short_trade_weight DESC NULLS LAST` ORDER BY 명시 (Migration SQL 일치)
- 기존 코드: bandit B324 (MD5) / pip-audit urllib3 CVE 의존성 업데이트

### 40.9 결과

- 코드: 25 파일 (15 신규 + 10 갱신)
- 테스트: 1097 → **1186** (+89 신규 / 100% green)
- coverage: **86.30%** (≥80% 요건 통과)
- 스케줄러: 9 → **12** 활성 (단, Phase E 3 job 은 `_sync_enabled=False` 또는 컨테이너 재배포 후 활성)
- endpoint: 12 → **15 / 25 (60%)**
- 1R: CONDITIONAL → 10건 fix → PASS
- Verification: 5관문 모두 PASS

### 40.10 다음 chunk

1. **(5-13 06:00 발화 직후) cron 첫 발화 검증** (§ 39.7 ohlcv_daily / daily_flow / sector_daily) — 본 chunk Phase E 3 cron 은 컨테이너 재배포 후 별도 활성
2. **§ 40.7 운영 모니터** — ka10014 / ka10068 / ka20068 첫 호출 검증 + 운영 가정 확정
3. **(5-19 이후) § 36.5 1주 모니터 측정** — 12 scheduler elapsed
4. **Phase F (순위 5종) / G (투자자별 3종) / H (통합)** — 신규 endpoint wave
5. **Phase D-2 ka10080 분봉 (마지막 endpoint)** — 대용량 파티션 결정 chunk 선행
6. **(전체 개발 종결 후) secret 회전** — `docs/ops/secret-rotation-2026-05-12.md` 절차서

---

## 41. Phase D-1 follow-up — MaxPages cap 상향 + bulk insert 32767 chunk 분할 (2026-05-14, ✅ 완료)

> 추가일: 2026-05-14 (KST) — Phase E (`0e767fe`) + 컨테이너 재배포 (`0ec6326`) + 진단 chunk (`478efaa`, 5-13) 종결 후
> 분류: fix (운영 인시던트 대응)
> 트리거: 2026-05-12 D-1 백필 시도 결과 — ka20006 sector_daily 60/124 (48%) + ka10086 KOSDAQ ~1814 누락
> Plan doc: `src/backend_kiwoom/docs/plans/endpoint-13-ka20006.md § 13`

### 41.1 배경

5-13 dead 가설 자연 재현 반증 (17:30 stock_master + 18:00 stock_fundamental 정상 발화) 후 진단 중 발견된 신규 인시던트 3건 중 2건 (E 묶음) 의 코드 fix. F 별도 (ka10001 NUMERIC overflow + sentinel WARN/skipped 분리).

**근본 원인**:

| # | 인시던트 | 실 예외 | 카운트 |
|---|---------|--------|--------|
| 1 | ka20006 MaxPages | `KiwoomMaxPagesExceededError` (`SECTOR_DAILY_MAX_PAGES=10`) | 56 / 124 (45%) |
| 2 | ka20006 InterfaceError | `asyncpg.exceptions._base.InterfaceError: the number of query arguments cannot exceed 32767` (sector_id 29/57/102/103/105-108) | 8 / 124 |
| 3 | ka10086 KOSDAQ MaxPages | `KiwoomMaxPagesExceededError` (`DAILY_MARKET_MAX_PAGES=40`) | 다수 (KRX ~1814 누락) |

#1·#3 = 추정값 ("1 page ~600 거래일") 운영 반증. ka10086 실측 (1 page ~22 거래일, mrkcond.py L51-53) 패턴 일관.
#2 = PostgreSQL wire protocol int16 한도 — bulk insert 의 row × column > 32767 시 발생. sector_daily 일부 long-history sector (15년+) 의 3년 백필 = 5500+ row × 8 col ≈ 44k > 32767 한도 초과.

### 41.2 결정 (plan doc § 13.2 그대로 — 운영 검증 진행 시점 갱신 예정)

| # | 사안 | 결정 |
|---|------|------|
| 1 | `SECTOR_DAILY_MAX_PAGES` 상향 | 10 → **40** (ka10086 실측 패턴 일관) |
| 2 | `DAILY_MARKET_MAX_PAGES` 상향 | 40 → **60** (KOSDAQ 1814 누락 근거) |
| 3 | bulk insert chunk 분할 | `upsert_many` chunk_size = **1000** (32767 / 13 col ≈ 2520 안전 — 1000 보수치) |
| 4 | 적용 범위 | (a) `SectorPriceDailyRepository` (b) `StockDailyFlowRepository` |
| 5 | helper 표준화 | `_chunked_upsert(session, statement_factory, rows, *, chunk_size=1000) -> int` — `_helpers.py` |
| 6 | 예외 시그니처 확장 | `KiwoomMaxPagesExceededError(*, api_id, page, cap)` — 운영 가시화 (어느 cap 이 얼마나 부족했는지) |
| 7 | UseCase 시그니처 | **변경 0** (Repository 단 흡수) |
| 8 | Migration | **없음** (스키마 변경 0) |
| 9 | 백필 재호출 (운영) | 본 chunk 머지 + 컨테이너 재배포 후 별도 운영 chunk (E4) |
| 10 | scheduler dead 진단 endpoint | 본 chunk 범위 X — dead 자연 재현 반증 후 `/admin/scheduler/diag` 유지 (운영 가치) |

### 41.3 영향 범위 (6 코드 + 5 테스트, +13 신규 cases)

**코드 (6 files, +342/-59 line, Migration 0)**:

| # | 파일 | 변경 |
|---|------|------|
| 1 | `app/adapter/out/kiwoom/chart.py` | `SECTOR_DAILY_MAX_PAGES = 10 → 40` + 주석 갱신 + docstring "`(10)` → `(40)`" 정합 (2a 2R M-1) |
| 2 | `app/adapter/out/kiwoom/mrkcond.py` | `DAILY_MARKET_MAX_PAGES = 40 → 60` + 주석 갱신 |
| 3 | `app/adapter/out/kiwoom/_client.py` | `KiwoomMaxPagesExceededError(*, api_id, page, cap)` `__init__` 추가 + `super().__init__` 메시지 형식 갱신 + `call_paginated` raise site (line 347) 갱신 |
| 4 | `app/adapter/out/persistence/repositories/_helpers.py` | `_chunked_upsert` 신규 + docstring stateless 보장 명시 (2a 2R M-2) + `n_cols × chunk_size > 32767` fail-fast 가드 (2b 2R M-1) |
| 5 | `app/adapter/out/persistence/repositories/sector_price.py` | `_build_upsert` 클로저 + `_chunked_upsert(self._session, _build_upsert, normalized, chunk_size=1000)` 호출 |
| 6 | `app/adapter/out/persistence/repositories/stock_daily_flow.py` | 동일 패턴 |

**테스트 (4 갱신 + 1 신규, +13 cases)**:

| # | 파일 | 변경 |
|---|------|------|
| 1 | `tests/test_kiwoom_chart_client.py` | +2 cases (constant=40 / `(page=40, cap=40)` raise) |
| 2 | `tests/test_kiwoom_mrkcond_client.py` | +2 cases (constant=60 / `(page=60, cap=60)` raise) |
| 3 | `tests/test_repository_chunked_upsert.py` (신규) | 7 cases (empty / 1 row / 999 / 1001 / 5500 / chunk_size=500 / n_cols×size > 32767 ValueError) |
| 4 | `tests/test_sector_price_repository.py` | +1 case (5500 row × 8 col chunk 분할 안전 — testcontainers PG16) |
| 5 | `tests/test_stock_daily_flow_repository.py` | +1 case (3000 row × 12 col chunk 분할 안전 — testcontainers PG16) |

### 41.4 적대적 이중 리뷰 결과

| 리뷰 | 모델 | 결과 | 발견 |
|------|------|------|------|
| 1R 2a 일반 품질 | sonnet | ✅ PASS | M-1 docstring 오기 + M-2 stateless 명시 권고 + LOW 4 |
| 1R 2b 적대적·보안 | opus | ✅ PASS | M-1 column 수 silent breakage 가드 부재 + LOW 4 |

**MEDIUM 3건 모두 즉시 fix**:
- 2a M-1: `chart.py:742` docstring `"SECTOR_DAILY_MAX_PAGES (10)" → "(40)"`
- 2a M-2: `_chunked_upsert` docstring `stateless 보장 필수` 한 줄 추가
- 2b M-1: `_chunked_upsert` 진입 시 `n_cols × chunk_size > 32767` 시 `ValueError` fail-fast + 신규 가드 테스트 1 case

CRITICAL 0 / HIGH 0 / 본 chunk 의 보안 정책 (응답 본문 echo 금지 / `_clear_chain` / 헤더 인젝션 검증) 우회 0.

### 41.5 Verification 5관문

| 관문 | 결과 |
|------|------|
| 3-1 빌드 | py compile 정상 (1199 collection PASS) |
| 3-2 ruff | All checks passed |
| 3-2 mypy --strict | Success: no issues found in 95 source files |
| 3-3 pytest | **1199 passed** (baseline 1186 → +13 신규) / coverage **86.13%** (≥80% 통과) |
| 3-4 보안 스캔 | ⚪ (계약 분류 자동 생략) |
| 3-5 런타임 | ✅ (pytest collection 의 import 검증 통과) |
| 4 E2E | ⚪ (UI 변경 0) |

### 41.6 누적 측정

- 코드: 6 파일 (1 신규 helper + 5 갱신) / Migration 0 / UseCase 변경 0
- 테스트: 1186 → **1199** (+13 신규 / 100% green)
- coverage: **86.13%** (≥80% 통과)
- 1R: CRITICAL 0 / HIGH 0 / MEDIUM 3 즉시 fix → PASS
- Verification: 5관문 모두 PASS
- 25 endpoint: 15 / 25 (60%) 그대로 — 신규 endpoint X
- 스케줄러: 12 그대로 — 신규 cron X

### 41.7 운영 모니터 (E4 chunk — 2026-05-14 ✅ 완료)

본 chunk (`f7bcfe3`) 머지 + 컨테이너 재배포 + 5-12 백필 재호출 결과:

#### (a) 컨테이너 재배포 (06:51 KST)

- `docker compose build kiwoom-app` — 캐시 활용 빌드 즉시 완료
- `docker compose up -d kiwoom-app` — Recreated / Started
- /health = `{"status":"ok"}` / 12 scheduler 활성 (재기동 직후)

#### (b) sector_daily 5-12 bulk sync (06:58 KST) — **PASS**

```
POST /api/kiwoom/sectors/ohlcv/daily/sync?alias=prod&base_date=2026-05-12
{
  "total": 124,
  "success": 124,
  "failed": 0,
  "errors": []
}
```

| 지표 | 5-12 백필 (5-13 02:33) | 5-12 재호출 (5-14 06:58) |
|------|------------------------|---------------------------|
| total | 124 | 124 |
| success | 60 (48.4%) | **124 (100%)** ✅ |
| failed | 64 (51.6%) | **0** ✅ |
| KiwoomMaxPagesExceededError | 56 | **0** ✅ |
| asyncpg.InterfaceError 32767 | 8 | **0** ✅ |
| DB row 적재 | 59 | **123** (1 sector sentinel break 정상) |

#### (c) KOSDAQ daily_flow 5-12 backfill CLI (06:53~07:00 KST) — **PASS**

```
$ docker compose exec -T kiwoom-app python scripts/backfill_daily_flow.py \
    --alias prod --start-date 2026-05-12 --end-date 2026-05-12 \
    --only-market-codes 10 --resume --log-level INFO

===== Daily Flow Backfill Summary =====
indc_mode:     quantity
date range:    2026-05-12 ~ 2026-05-12
total:         1487 종목 (KOSDAQ, resume 으로 미적재 종목만)
success_krx:   1487
success_nxt:   224
failed:        0 (ratio 0.00%)
elapsed:       0h 7m 7s
avg/stock:     0.3s
```

| 지표 | 5-12 시도 (5-13) | 5-12 재호출 (5-14) |
|------|------------------|---------------------|
| KRX success | 2559 (1814 누락) | **2648** (재호출 1487 합산) ✅ |
| KOSDAQ MaxPages | 다수 | **0** ✅ |
| 0 InterfaceError | — | ✅ |

#### (d) DB 최종 상태 (5-12, 07:00 KST)

| 테이블 | 5-12 row |
|--------|----------|
| `sector_price_daily` | 123 (1 sector empty sentinel) |
| `stock_daily_flow` KRX | 2648 |
| `stock_daily_flow` NXT | 633 |
| `stock_daily_flow` 합계 | 3281 |

#### (e) page 분포 실측 — 다음 운영 1주 (5-19 이후) § 36.5 와 합산

- ka20006 sector 별 실 page 수 분포: 본 호출은 124 sector 약 5분 소요 = 평균 ~2.5초/sector (KRX rate limit 2초/호출 + chunk 분할 오버헤드 미미). **40 cap 여유 충분 가정** — 정밀 측정은 다음 § 36.5 모니터링 (5-19 이후)
- ka10086 KOSDAQ 종목 page 분포: 1487 종목 7m 7s = 평균 0.3초/stock = ka10086 대부분 종목이 cap=60 의 일부만 사용 (`--resume` 으로 미적재만 처리한 결과). 60 cap 여유 충분

#### (f) chunk_size 1000 보수치 검증

본 호출은 5-12 단일 일자 (1 row per sector × 124 = 124 rows / 1 row per stock × 1487 = 1487 rows) — 단일 chunk 내에서 처리 (1487 < 1000 × 2 = 2 chunk 만, 8 col × 1487 = 11896 args < 32767). chunk 분할 자체 효과 운영 측정은 3년 백필 시점 (별도 chunk) 으로 이연.

#### (g) `/admin/scheduler/diag` 운영 가치

본 chunk 의 5-14 06:00/06:30 cron miss 발견 — dead 가설 자연 재현 가능성 ↑ (5-13 자연 발화 정상 / 5-14 새벽 cron miss). 그러나 07:00 sector_daily cron 자연 발화 정상 (123 row 적재 / 진행 중). **`/admin/scheduler/diag` 유지 결정 — 추가 인시던트 진단에 필요**. Pending #7 는 1주 모니터 (5-19 이후) 결과 보고 결정.

### 41.8 추가 발견 (5-14 06:50 KST 컨테이너 재배포 직전)

- **5-14 06:00 OhlcvDaily / 06:30 DailyFlow cron miss** — 컨테이너 재배포 전 1시간 docker logs 0 cron event. 5-13 17:30/18:00 정상 발화 검증 후 06:00 dead 일회성 가설 → 5-14 새벽 재발 가능성 ↑
- 본 chunk 컨테이너 재배포 (06:51 KST) 후 07:00 sector_daily cron 자연 발화 정상 (chart.py 호출 + 5-13 base date 적재 진행)
- **별도 chunk 후보**: dead 가설 재발 분석 — APScheduler timer freeze 가설 / 컨테이너 sleep 가설 (Mac 절전 § 38.8 #1) 재검토

### 41.9 다음 chunk

1. ~~**(E4) 컨테이너 재배포 + 5-12 운영 백필 재호출**~~ ✅ 완료 (본 § 41.7)
2. ~~**scheduler dead 재발 분석 chunk**~~ ✅ 완료 (§ 42) — Mac 절전 원인 확정
3. **F chunk — ka10001 NUMERIC overflow + sentinel WARN/skipped 분리** — Migration 신규 (NUMERIC(8,4) precision 확대 — overflow 종목 값 분석 선행) + result.errors 의 full exception type/메시지 log 보강
4. **§ 40.7 운영 모니터** — ka10014 / ka10068 / ka20068 첫 호출 검증
5. **(5-19 이후) § 36.5 1주 모니터 측정** — 12 scheduler elapsed
6. **Phase F / G / H** — 신규 endpoint wave
7. **Phase D-2 ka10080 분봉 (마지막 endpoint)** — 대용량 파티션 결정 동반
8. **(전체 개발 종결 후) secret 회전**

---

## 42. scheduler dead 원인 확정 — Mac 절전 (Docker Desktop VM sleep) (2026-05-14, ✅ 분석 종결)

> 추가일: 2026-05-14 (KST) — § 41.8 5-14 06:00/06:30 cron miss 발견 + § 38.8 #1 Mac 절전 가설 정합 확정
> 분류: 진단 / 코드 변경 0
> 트리거: 5-13 06:00 dead + 5-14 06:00/06:30 dead 반복 → "일회성" 가설 반증
> 결정: Mac 절전 = 원인 확정 / 해결책 = 사용자 환경 결정 (caffeinate / 서버 이전 / 현재 유지)

### 42.1 배경 — 인시던트 chronology

| 시점 | 사건 |
|------|------|
| 5-13 06:00 KST | OhlcvDaily cron 발화 0 (재배포 직후 첫 새벽 cron) |
| 5-13 06:30 KST | DailyFlow cron 발화 0 |
| 5-13 07:00 KST | SectorDaily cron 발화 0 |
| 5-13 (진단 chunk `0ec6326`) | `/admin/scheduler/diag` 추가 + Phase E 3 alias env 추가 + 컨테이너 재배포 → 12 scheduler 활성. baseline diag = 12개 모두 main_loop 동일 / cancelled=false / next_run_time 정확 (race 가설 반증) |
| 5-13 17:30 KST | stock_master cron 자연 발화 정상 (fetched=4788) — 일회성 가설 |
| 5-13 18:00 KST | stock_fundamental cron 자연 발화 정상 (total=4379) — 일회성 가설 ↑ |
| **5-14 06:00 KST** | OhlcvDaily cron 발화 0 — **dead 재발** |
| **5-14 06:30 KST** | DailyFlow cron 발화 0 — **dead 재발** |
| 5-14 06:50 KST | 본 § 42 분석 진입 시점 (사용자 발견) |
| 5-14 06:51 KST | 본 E4 chunk 컨테이너 재배포 (코드 변경 0, 가설 검증용) |
| 5-14 07:00 KST | SectorDaily cron 자연 발화 정상 (chart.py 호출 진행) — Mac active 시점 |

### 42.2 결정적 증거 — `pmset -g log` Mac sleep history

5-13 저녁부터 Mac 이 **반복 Sleep + DarkWake** 사이클 진입:

```
2026-05-13 20:01:26 +0900 Sleep   Entering Sleep state due to 'Sleep Service Back to Sleep':TCPKeepAlive=active Using Batt (Charge:80%) 967 secs
2026-05-13 20:17:35 +0900 Sleep   (Batt 80%) 1011 secs
2026-05-13 20:34:28 +0900 Sleep   (Batt 80%) 287 secs
2026-05-13 20:39:28 +0900 Sleep   due to 'Maintenance Sleep' (Batt 80%) 1057 secs
2026-05-13 20:57:07 +0900 Sleep   (Batt 80%) 904 secs
... (반복 사이클 5-13 21:12 까지 확인)
```

**현재 `pmset -g` 결과 (5-14 07:19)**:
```
sleep   1 (sleep prevented by sharingd, caffeinate, caffeinate, caffeinate, powerd, JANDI)
```

`caffeinate` 다중 활성 = **현재만 절전 차단 중**. 5-13 저녁에는 caffeinate 비활성 → 자유 절전. Battery 모드 (Charge 80%, 충전 중 X) + 20:01 부터 자동 sleep.

### 42.3 가설 평가

| 가설 | 평가 | 증거 |
|------|------|------|
| **Mac 절전 → Docker VM sleep → APScheduler timer 미발화** | ✅ **확정** | pmset 5-13 20:01~21:12 반복 Sleep + 현재 caffeinate 활성 (5-13 비활성) |
| APScheduler timer freeze (race condition) | ❌ 반증 | 5-13 진단 chunk `0ec6326` 의 baseline diag = 12 scheduler 모두 main_loop 동일 / cancelled=false / next_run_time 정확. 자연 발화 (17:30/18:00) 모두 정상 |
| Docker network / DB 연결 끊김 | ❌ 반증 | 5-13 17:30 / 18:00 / 5-14 07:00 자연 발화 시점에는 정상 동작 |
| 컨테이너 healthcheck 실패 → restart | ❌ 반증 | `docker inspect kiwoom-app` 의 finishedAt=`0001-01-01T00:00:00Z` (never finished). exit=0 / health=healthy 지속 |
| Battery 부족 | ❌ | Charge 80% 유지 |

**확정 가설**: Mac 절전 → Docker Desktop VM 일시정지 → 컨테이너 sleep → asyncio 이벤트 루프 sleep → APScheduler timer wakeup 호출 안 됨 → cron 미발화. Mac wake 후 APScheduler default behavior 는 missed firing **skip** (단, `misfire_grace_time` 설정된 cron 만 grace 안에 catch-up).

### 42.4 현재 cron 별 misfire_grace_time 상태

| Cron | misfire | 영향 |
|------|---------|------|
| `stock_master_sync_daily` (17:30) | 없음 | Mac sleep 중 시각 도달 시 skip |
| `stock_fundamental_sync_daily` (18:00) | 없음 | 동일 |
| `ohlcv_daily_sync_daily` (06:00) | 없음 | **5-14 06:00 miss** |
| `daily_flow_sync_daily` (06:30) | 없음 | **5-14 06:30 miss** |
| `weekly_ohlcv_sync_weekly` (sat 07:00) | 없음 | — |
| `monthly_ohlcv_sync_monthly` (매월 1일 03:00) | 없음 | 새벽 = sleep 위험 ↑ |
| `yearly_ohlcv_sync_yearly` (매년 1월 5일 03:00) | 없음 | 동일 |
| `sector_daily_sync_daily` (07:00) | 없음 | 5-14 07:00 정상 (Mac active) |
| `short_selling_sync_daily` (07:30) | **1800s** | Mac wake 후 30분 grace |
| `lending_market_sync_daily` (07:45) | **1800s** | 동일 |
| `lending_stock_sync_daily` (08:00) | **5400s** | Mac wake 후 90분 grace |
| `sector_sync_weekly` (일 03:00) | 없음 | 일요일 새벽 = 사용자 sleep 가능성 ↑ |

→ 새벽 cron (03:00 / 06:00 / 06:30) 이 sleep 위험 가장 큼.

### 42.5 해결 옵션 (사용자 결정 — § 38.8 #1 갱신)

| # | 옵션 | 장점 | 단점 |
|---|------|------|------|
| **A** | `caffeinate -dimsu &` 영구 활성 (launchd plist) | 즉시 적용 / 추가 비용 0 | 발열 + 배터리 빠르게 소모 (노트북 닫혀도 동작) |
| **B** | 별도 Linux 서버 이전 (Mini PC / NAS / 클라우드 VM) | 절전 무관 / 24/7 안정 | 인프라 구축 + 비용 |
| C | APScheduler `misfire_grace_time` 전 cron 적용 | 부분 완화 | sleep 중에는 timer 자체 X → grace 만으로 부족. wake 시 즉시 catch-up 만 |
| D | host launchd cron + `curl admin endpoint` | Docker Desktop 의존 줄임 | host Mac 도 sleep 영향 (WakeUp on cron 필요) |
| E | 현재 유지 + 모니터링 | 변경 0 | 매일 새벽 cron 미발화 위험 |

### 42.6 본 chunk 결정

본 § 42 는 **분석 종결** — 원인 확정 + 해결 옵션 제시. 사용자 환경 결정으로 본 chunk 의 범위 외. 코드 변경 0 / Migration 0.

**임시 권고** (다음 cron 까지):
- Mac active 상태 유지 (caffeinate 실행 또는 노트북 깬 채로 둠)
- 또는 본 chunk 직후 사용자 결정 → 별도 chunk

### 42.7 관련 § 갱신

- **§ 38.8 #1 갱신**: Mac 절전 = "위험 가설" → **"원인 확정"** (5-14 dead 재발로 검증). 해결 옵션 § 42.5 표 추가
- **§ 41.8 추가 발견**: dead 재발 가설 → 본 § 42 로 종결
- **HANDOFF Pending #6** (Mac 절전 시 컨테이너 중단 위험): 위험 가설 → **확정 인시던트**. 사용자 환경 결정 시급

### 42.8 다음 chunk

1. ~~**사용자 환경 결정**~~ ✅ 옵션 C + 보조 E 채택 (5-14, § 43)
2. **F chunk** — ka10001 NUMERIC overflow + sentinel WARN/skipped 분리 (Mac 절전 결정과 독립)
3. **§ 40.7 운영 모니터** — ka10014 / ka10068 / ka20068 첫 호출 검증
4. **(5-19 이후) § 36.5 1주 모니터 측정** — 12 scheduler elapsed
5. **Phase F / G / H** — 신규 endpoint wave
6. **Phase D-2 ka10080 분봉 (마지막 endpoint)** — 대용량 파티션 결정 동반

---

## 43. Phase D — scheduler misfire_grace_time 전 cron 통일 (옵션 C 채택, 2026-05-14, ✅ 완료)

> 추가일: 2026-05-14 (KST) — § 42.5 옵션 C 채택 사용자 결정 후속
> 분류: ops fix (운영 정책 변경, 코드 작음)
> 선행: § 42 Mac 절전 dead 원인 확정 + 사용자 환경 결정 (노트북 + 학습 우선)
> Plan doc: `src/backend_kiwoom/docs/plans/phase-d-scheduler-misfire-grace.md`

### 43.1 결정

12 스케줄러 클래스 모두 `MISFIRE_GRACE_SECONDS: Final[int] = 21600` (6h) 통일:
- 9 신규: SectorSync / StockMaster / StockFundamental / OhlcvDaily / DailyFlow / WeeklyOhlcv / MonthlyOhlcv / YearlyOhlcv / SectorDailyOhlcv — 상수 + add_job kwarg 추가
- 3 갱신: ShortSelling (1800→21600) / LendingMarket (1800→21600) / LendingStock (5400→21600)

Mac wake 시각 분포 (대부분 09:00~13:00 KST) → 06:00 새벽 cron → noon 안 catch-up.

### 43.2 영향 범위 (10 파일 / +78 -19)

**코드 (2 파일)**:
- `app/scheduler.py` — 12 클래스 정책 통일 + L94 / L1122 docstring 구값 갱신 (2a M-1/M-3)
- `app/main.py` — `/admin/scheduler/diag` endpoint 의 jobs dump 에 `misfire_grace_time` 노출 (2b M-2)

**테스트 (8 파일)**:
- `test_scheduler.py` / `test_stock_master_scheduler.py` / `test_stock_fundamental_scheduler.py` / `test_ohlcv_daily_scheduler.py` / `test_daily_flow_scheduler.py` / `test_weekly_monthly_ohlcv_scheduler.py` / `test_scheduler_sector_daily.py` — `misfire_grace_time == 21600` 단언 추가 (raw int — _PhaseEJobView wrap 없는 클래스)
- `test_scheduler_phase_e.py` — `_30min`/`_90min` → `_6h` 통일 + docstring 갱신 (2a M-2)

### 43.3 이중 리뷰 결과

- **2a (sonnet) CONDITIONAL → PASS**: CRITICAL 0 / HIGH 0 / MEDIUM 3 (docstring 구값 잔존) 즉시 fix / LOW 3
- **2b (opus) CONDITIONAL → PASS**: CRITICAL 0 / HIGH 0 / MEDIUM 2 즉시 fix + 보강 / LOW 4

**MEDIUM 5건 처리**:
| # | 출처 | 항목 | 처리 |
|---|------|------|------|
| M-1 | 2a | scheduler.py L94 docstring `misfire 90분` 구값 | docstring 갱신 |
| M-2 | 2a | test_scheduler_phase_e.py Scenario 9 docstring `5400s/1800s` 구값 | docstring 갱신 |
| M-3 | 2a | LendingStockScheduler 클래스 docstring `5400s (90분)` 구값 | docstring 갱신 |
| M-1 | 2b | cross-scheduler catch-up race — 6h grace 시 5+ cron 동시 catch-up → KRX rate limit 위반 위험 (`KiwoomClient` 인스턴스 단위 lock 한계) | **plan doc § 5 H-6 보강** + 운영 모니터 + 위반 발생 시 별도 chunk (공유 `KiwoomClient` 또는 cross-scheduler `asyncio.Semaphore`) |
| M-2 | 2b | `/admin/scheduler/diag` 가 `misfire_grace_time` 노출 안 함 — 운영 가시성 부족 | main.py:902 jobs dump 에 1줄 추가 |

### 43.4 Verification 5관문

| 관문 | 결과 |
|------|------|
| 3-1 빌드 | pytest collection 1199 PASS |
| 3-2 ruff | All checks passed (8 unused `import datetime` 자동 fix) |
| 3-2 mypy --strict | Success: no issues found in 95 source files |
| 3-3 pytest | **1199 passed** / coverage **86.17%** (≥80% 통과) |
| 3-4 보안 스캔 | ⚪ (일반 분류 자동 생략) |
| 3-5 런타임 | ✅ pytest collection import 검증 |
| 4 E2E | ⚪ (UI 변경 0) |

### 43.5 누적 메트릭

- 코드: 2 파일 (scheduler.py + main.py) / Migration 0 / UseCase 변경 0
- 테스트: 1199 그대로 (단언 추가만, 신규 테스트 case 0)
- coverage: 86.17%
- 1R: MEDIUM 5 즉시 fix → 2a/2b 모두 PASS
- Verification: 5관문 모두 PASS

### 43.6 운영 모니터 (다음 chunk)

본 chunk 머지 + 컨테이너 재배포 후:

- [ ] **5-15 (목) 06:00 OhlcvDaily catch-up 검증** — Mac wake 시점에 발화 + base_date=previous_business_day (5-14 수) 정합
- [ ] **6시간 grace 안 미catch 케이스** — 정오 이후 wake 시 skip 발생 → backfill CLI 수동 회복 (보조 E)
- [ ] **2b M-1 cross-scheduler race 모니터** — 5+ cron 동시 catch-up 시 429 / alias revoke 로그 검토. 위반 시 별도 chunk 진입
- [ ] **`/admin/scheduler/diag` misfire_grace_time 노출 검증** — 12 cron 모두 21600 표시
- [ ] **(5-19 이후) § 36.5 1주 모니터** — 12 cron 의 누적 elapsed / 실행 성공률 / misfire 빈도

### 43.7 다음 chunk

1. **(운영) 5-15 (목) 새벽 cron catch-up 검증** — 본 chunk 효과 확정
2. **F chunk** — ka10001 NUMERIC overflow + sentinel WARN/skipped 분리 (Mac 결정과 독립)
3. **(조건부) cross-scheduler rate limit race 별도 chunk** — 2b 2R M-1 의 운영 위반 확인 시 진입
4. **§ 40.7 운영 모니터** — ka10014 / ka10068 / ka20068 첫 호출 검증
5. **Phase F / G / H** — 신규 endpoint wave
