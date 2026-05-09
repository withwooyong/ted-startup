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
