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
