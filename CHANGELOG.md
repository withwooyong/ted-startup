# Changelog

All notable changes to this project are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/).

## [Unreleased]

---

## [2026-04-22] refactor: KIS Hexagonal DIP 완성 + Router account 단일 로드 (`refactor/kis-port-single-account-load`, PR #(예정))

/review 세션 감사에서 발견된 HIGH 2건을 단일 "아키텍처 정돈 PR" 로 통합 해소.

**이전 상태**:
- `portfolio_service.py` 가 `from app.adapter.out.external import KisClient, KisClientError, KisCredentialRejectedError, KisCredentials, KisHoldingRow` 로 **application → infra 직접 참조**. PR #23 에서 `MaskedCredentialView` 만 dto 로 이동했고 KIS 관련은 잔존.
- `sync_from_kis` router 가 account 선로드 후 UseCase 내부에서 `_ensure_kis_real_account` 가 재조회. Repository.get 이 내부적으로 `session.get` (identity map 캐시) 이라 실제 DB round-trip 은 1회이지만, 리뷰 독자에게 자명하지 않음.

### Added
- **`app/application/dto/kis.py`** (신규) — `KisCredentials`, `KisHoldingRow`, `KisEnvironment` 이동. Hexagonal 경계 정합 (application layer 가 DTO 소유).
- **`app/application/port/out/kis_port.py`** (신규) — KIS 잔고 조회 port:
  - `KisHoldingsFetcher` Protocol (structural typing) — `KisClient` 가 명시 상속 없이 자동 만족
  - `KisUpstreamError` (포트 최상위) + `KisCredentialRejectedError` (401/403 전용 서브) — port 레벨 예외 계층
  - `KisRealFetcherFactory = Callable[[KisCredentials], KisHoldingsFetcher]` 타입 별칭

### Changed
- `app/adapter/out/external/kis_client.py`: DTO 정의 제거, port 예외 직접 raise. adapter-internal `KisClientError`/`KisAuthError`/`KisCredentialRejectedError` 삭제 (port 예외로 수렴).
- `app/adapter/out/external/__init__.py`: DTO/port 예외를 `app.adapter.out.external` 네임스페이스에서 re-export (배선·테스트 편의, 기존 호출부 backward-compat).
- `app/adapter/web/_deps.py`: DTO import 경로를 `app.application.dto.kis` 로. `get_kis_real_client_factory` 반환 타입을 `KisRealFetcherFactory` (port 타입) 로.
- `app/application/service/portfolio_service.py`: `from app.adapter.out.external import ...` **완전 제거**. port/dto 만 참조. `_ensure_kis_real_account` + 3 UseCase(`Mock`/`Real`/`TestConnection`) `execute()` 에 optional `account: BrokerageAccount | None = None` 파라미터 추가 — 라우터가 선로드한 account 를 명시 전달 가능.
- `app/adapter/web/routers/portfolio.py`: `sync_from_kis` 의 UseCase 호출이 `account=loaded_account` 를 명시 전달. 시그니처가 `KisHoldingsFetcher` Protocol 참조로 DIP 준수.

### Fixed
- 리뷰 HIGH: `KisNotConfiguredError` 를 `Exception` 직계로 분리 (이전 `KisUpstreamError` 상속) — 서버 설정 오류를 UseCase `except KisUpstreamError` 가 삼켜 `SyncError` → 502 로 오진단하는 경로 차단. 이제 설정 오류는 FastAPI 기본 500 으로 전파.
- 리뷰 MEDIUM: `kis_client.py` `test_connection` docstring 의 삭제된 `KisAuthError` 이름 잔존 → `KisCredentialRejectedError` / `KisUpstreamError` 로 현행화.

### Not Done (intentional)
- **R-03 이름 중복 완화**: port `KisCredentialRejectedError` vs domain `CredentialRejectedError`. `Kis` prefix 로 구분. ruff N818(Error suffix) 때문에 suffix 유지 필요 → 리네이밍은 별도 PR 후보.
- **다른 서비스 DIP 확장**: `notification_service`(TelegramClient), `market_data_service`(KrxClient), `analysis_report_service` 도 adapter 직접 참조 잔존. 본 PR 은 KIS 영역 leading example, 추후 PR 로 확장.
- **Adapter __init__ re-export 제거**: 테스트·배선·기존 호출부 backward-compat 유지. application layer 는 직접 port/dto 경로로만 import 하므로 DIP 훼손 없음.

### Verified
- `uv run ruff check .` ✅
- `uv run ruff format --check .` ✅ 126 files already formatted
- `uv run mypy app` ✅ **83 source files** (신규 2 포함), no issues
- `uv run pytest -q` ✅ **303 passed, 1 deselected** — 회귀 0건

### Decisions
- **Structural typing 우선**: `KisClient` 가 Protocol 을 명시 상속하지 않음. mypy strict 가 `KisClient` → `KisHoldingsFetcher` 할당 지점에서 검증 (factory 반환 경로).
- **Protocol 에 `__aenter__`/`__aexit__` 포함**: "이 port 는 context manager 로만 사용한다" 계약 명시. `typing.AsyncContextManager` 상속 대신 explicit 선언이 가독성 우수.
- **Optional account 파라미터 하위 호환**: `execute(*, account_id, account=None)` — 기존 호출부 수정 불필요. Router 만 명시 전달.
- **`KisRealClientFactory` alias 유지**: `KisRealFetcherFactory` 의 하위 호환 alias, 외부 참조 없음 확인 후 다음 클린업 PR 에서 제거.

---

## [2026-04-22] refactor: KisAuthError 401/5xx 분리 — credential 거부 vs 업스트림 장애 (`77903d9`, PR #24)

**이전 상태**: PR 5 (#16) 리뷰 이월 MEDIUM. KIS 토큰 발급/잔고조회가 HTTP 401/403 (credential 거부) 이든 5xx/네트워크 (업스트림 장애) 이든 모두 `KisAuthError`/`KisClientError` → UseCase 가 `SyncError` 로 래핑 → 라우터에서 **일괄 502** 응답. 사용자가 "KIS 자격증명 틀림" 과 "KIS 서버 다운" 을 구분 못 함.

### Added
- **`KisCredentialRejectedError(KisAuthError)` 서브클래스** — HTTP 401/403 전용. 토큰 발급 + 잔고조회 두 경로 모두 raise.
- **`CredentialRejectedError(PortfolioError)` 도메인 예외** — UseCase 가 `KisCredentialRejectedError` 를 catch 해 도메인 계층으로 승격. 4xx 매핑 대상.
- 테스트 8건 추가:
  - `test_kis_client.py`: 토큰 401/403 파라메트라이즈, 토큰 500 → base KisAuthError (서브클래스 아님 단언), 잔고 401/403 파라메트라이즈
  - `test_kis_real_sync.py`: UseCase 레벨 401/403 → CredentialRejectedError, 500 → SyncError, endpoint 400/502 분리

### Changed
- `SyncPortfolioFromKisMockUseCase` / `SyncPortfolioFromKisRealUseCase` / `TestKisConnectionUseCase` 세 UseCase 의 except 순서: `except KisCredentialRejectedError` 를 `except KisClientError` **앞** 에 배치. 서브클래스가 먼저 잡혀 도메인 `CredentialRejectedError` 로 승격.
- Router `_credential_error_to_http`: `CredentialRejectedError` → **HTTP 400** 분기 추가 (SyncError → 502 분기 앞).
- 기존 `test_connection_token_failure_wrapped_as_sync_error` (401 → SyncError) → `test_connection_credential_reject_raises_credential_rejected` (401/403 → CredentialRejectedError) 로 교체. 기존 `test_endpoint_test_connection_token_failure_502` (401 → HTTP 502) → `_credential_rejected_400` / `_upstream_failure_502` 두 케이스로 분리.

### Fixed
- PR 5 이월 MEDIUM (4xx/5xx 분리) 해소.
- 리뷰 MEDIUM #1 (예외 메시지의 `body=...` HTTP response detail 노출) 예방 — `body=` 제거 후 DEBUG 로그로 분리. PR #20 의 마스킹 파이프라인을 거치도록 해 JWT/hex 패턴 자동 스크럽.

### Verified
- `uv run ruff check .` ✅
- `uv run ruff format --check .` ✅ 124 files already formatted
- `uv run mypy app` ✅ 81 source files, no issues
- `uv run pytest -q` ✅ **303 passed, 1 deselected** — +8 신규, 회귀 0건

### Decisions
- **HTTP 400 (401 아님)**: 서버 인증 실패가 아니라 KIS 업스트림이 credential 거부. 401 은 FE 가 "우리 admin API 인증 실패" 로 오해 유도. 422 Unprocessable Content 도 고려했으나 이 경우 request body 자체는 valid 라 422 semantics 와 안 맞음. 400 + 구체 메시지가 적절.
- **`status_code` 속성 안 추가**: `KisCredentialRejectedError` 는 타입만으로 분기. 인스턴스에 status_code 필드를 얹지 않음 — 도메인 로직이 값 검사 안 함. 단순성 우선.
- **CredentialRejectedError 는 SyncError 의 sibling**: 둘 다 `PortfolioError` 직속 서브클래스. Router `isinstance` 분기가 독립적으로 작동.
- **MOCK 경로도 승격**: 흔치 않지만 고정 mock key 만료 케이스 커버. 메시지에 "서버 env 점검 필요" 문구로 operator 안내.
- **리뷰 MEDIUM 2·3 스킵**: (2) 계층 간 유사 이름 부담 — follow-up 후보. (3) MOCK 401 을 사용자 응답으로 노출 — 메시지 텍스트로 operator 안내로 충분.

---

## [2026-04-22] refactor: Hexagonal 경계 + Sync UseCase mock/real 분리 (`576e9f2`, PR #23)

**이전 상태**: PR 5 (#16) 리뷰에서 HIGH 2건 carry-over.
1. `MaskedCredentialView` 가 `app/adapter/out/persistence/repositories/brokerage_credential.py` 에 정의되고 `portfolio_service` 가 re-export — application → infra 역방향 의존.
2. `SyncPortfolioFromKisUseCase.__init__` 가 `kis_client | None`, `credential_repo | None`, `real_client_factory | None` 세 Optional 로 받아 runtime `RuntimeError` 로 검증 — 타입 안전성 없음.

### Changed
- **`MaskedCredentialView` → `app/application/dto/credential.py` 신규 파일로 이동**. Hexagonal 경계 준수 (application layer 가 DTO 를 소유, infra 가 import 해서 반환).
- **`SyncPortfolioFromKisUseCase` 를 두 UseCase 로 분리**:
  - `SyncPortfolioFromKisMockUseCase` — `kis_client: KisClient` 필수 (non-Optional)
  - `SyncPortfolioFromKisRealUseCase` — `credential_repo: BrokerageAccountCredentialRepository` + `real_client_factory: KisRealClientFactory` 필수 (둘 다 non-Optional)
- **공통 로직 → `_apply_kis_holdings()` 모듈 헬퍼**. holding upsert 루프만 공유, 분기별 fetch 로직은 각 UseCase 에 집중.
- **Router `sync_from_kis` 디스패치**: `account.connection_type` 으로 분기해 적절한 UseCase 선택. 로드된 account 는 동일 세션 내 재조회 (race 안전, 캐시 히트).
- `KisConnectionType = Literal["kis_rest_mock", "kis_rest_real"]` 타입 별칭 도입 — `_apply_kis_holdings` 가 임의 문자열을 `SyncResult.connection_type` 에 흘리지 않도록 타입으로 좁힘.

### Fixed
- PR 5 이월 HIGH #1 (Hexagonal 레이어 위반) 해소
- PR 5 이월 HIGH #2 (Optional 파라미터 퇴화) 해소
- `test_sync_kis_rest_real_requires_real_environment`: 기존 테스트는 mock UseCase 로 `kis_rest_real` 계좌를 검증해 `UnsupportedConnectionError` 가 먼저 터져 실제로는 environment 검증을 테스트하지 못함. 신규 real UseCase 로 전환해 `_ensure_kis_real_account` 환경 검증에 정상 도달. `credential_repo.get_decrypted` + factory 둘 다 AssertionError 스텁으로 호출되면 실패하도록 해 순서 회귀 감지 강화.

### Verified
- `uv run ruff check .` ✅
- `uv run ruff format --check .` ✅
- `uv run mypy app` ✅ 81 source files, no issues
- `uv run pytest -q` ✅ **295 passed, 1 deselected** — 회귀 0건

### Decisions
- **mock/real UseCase 완전 분리**: 리뷰어가 제시한 단일 UseCase + Protocol/Fetcher 패턴은 간접 층 추가로 판단해 채택 안 함. 클래스 2개 + 공통 헬퍼가 더 직관적.
- **account 이중 로드 허용**: Router 선로드 + UseCase 재검증. 동일 세션 1트랜잭션 범위에서 race-safe, SA identity map 캐시 히트.
- **DB 모델 `connection_type: Mapped[str]` Literal 화 분리**: Router `else` dead-path exhaustive check 가능하려면 SQLAlchemy 모델 타입을 `Literal` 로 좁혀야 하나 DB 계층 광범위 변경이라 별도 PR.

---

## [2026-04-22] chore: CI 에 ruff + mypy strict 게이트 추가 (`3f0061e`, PR #22)

**이전 상태**: CI 가 pytest + next build + docker build 만 검증 — ruff/mypy 는 로컬 전용. 개발자별 환경 편차로 master 에 포매팅 누락·타입 에러 유입 위험.

### Added
- `.github/workflows/ci.yml` 에 **`backend-lint`** job 신설
  - `uv run ruff check .` — lint 룰 (E/W/F/I/B/UP/N/SIM)
  - `uv run ruff format --check .` — 포매팅 강제
  - `uv run mypy app` — strict 타입 검증 (plugins: pydantic.mypy)
- `backend-test` job 을 `needs: [backend-lint]` 로 의존 — lint 실패 시 pytest 스킵하여 자원 절감

### Changed
- **`src/backend_py` 전체 ruff format 일괄 적용** (98 파일 재포매팅, 로직 변경 0건). 본 레포에 ruff format 이 처음 도입된 상태였음
- `app/adapter/web/routers/signals.py`: 리스트 컴프리헨션 내 `stocks.get(sig.stock_id)` 2회 호출 → `for` 루프로 풀어 `stock` 로컬 바인딩. mypy union-attr 2건 (pre-existing 부채) 해소 + 중복 `.get()` 호출 제거

### Fixed
- `scripts/fix_stock_names.py`, `scripts/seed_e2e_accounts.py`: ruff SIM117 (중첩 `async with` 결합) 2건 autofix

### Verified
- `uv run ruff check .` ✅
- `uv run ruff format --check .` ✅ (123 files already formatted)
- `uv run mypy app` ✅ (80 source files, no issues)
- `uv run pytest -q` ✅ **295 passed, 1 deselected** — 회귀 0건

### Decisions
- **mypy 범위 `app/` 만**: tests/scripts 는 strict 미적용. 향후 확대 후보 (별도 PR). 테스트 코드는 mock 객체 다량 — strict 게이트 ROI 낮음
- **단일 PR 통합**: format 98 파일 + lint 2건 + mypy 2건 + CI 변경을 한 PR 로 묶음. 분리 시 format PR 이 머지 전에 다른 PR 과 충돌할 위험 + 차기 작업 차단 최소화
- **PR 5 이월 Hexagonal 부채**: 본 PR 에서 해소하지 않음. CI 게이트 추가는 현상 유지 위에서 게이트를 덮는 변경이므로 리팩터링과 분리

---

## [2026-04-21] docs: 모바일 반응형 계획서 현행화 (`7b11d88`, PR #19)

모바일 반응형 개선 작업계획서(`docs/mobile-responsive-plan.md`)를 **착수 전 현행화** — 작성(2026-04-20) 이후 머지된 PR #12·#15·#16 으로 UI 표면 유입 재진단.

### Changed
- 대상 스택: Next.js 15 → **16.2.4** + React 19.2.4 반영
- 수정 공격 지점: 3군데 → 5군데 확장
- **P1 신규**: RealAccountSection 3-버튼 (연결 테스트·수정·삭제) 모바일 레이아웃 (B3), Portfolio sync 버튼 라벨 확장 (C4)
- **D2 스킵**: 푸터 면책 `<details>` 접기 — 실제 3줄 짧은 문구, 필요성 낮음
- 예상 작업량 3~3.5 → **3.5~4 man-day**
- §9 변경 이력 섹션 신설

---

## [2026-04-21] docs: PIPELINE-GUIDE 현행화 + README 프로미넌트 링크 (`57dd562`, PR #18)

신규 프로젝트 진행 시 가장 중요한 엔트리 문서 현행화.

### Changed
- **README**: 상단 "🚨 필독" call-out 박스 + PIPELINE-GUIDE.md 링크 프로미넌트화. 핵심 문서 섹션에서도 이모지 + "신규 프로젝트 진행 시 가장 먼저 읽을 문서" 명시
- **PIPELINE-GUIDE §2 필수 준비물**: Java 21 → **Python 3.12 + FastAPI + Next.js 16** 반영. `.claude/settings.local.json` · `gh` CLI 언급
- **PIPELINE-GUIDE §8 Q3 코드리뷰**: `java-reviewer` 단독 → **언어별 reviewer 매핑 표** (python/typescript/kotlin/java/go/rust). 병렬 리뷰 실전 패턴 섹션 (본 프로젝트 PR #12~#16 에서 검증)
- **PIPELINE-GUIDE §실전 학습**: 🆕 KIS sync 시리즈 (PR #12~#16) 교훈 11건 추가. Sprint 1~3 Java 시대는 참고용 보존. 공통 워크플로우 섹션 (`/ted-run` · feature branch + squash · CI 4/4 게이트 · `/handoff` · Co-Authored-By) 신설

---

## [2026-04-21] chore: .claude/settings.local.json 을 .gitignore 에 추가 (`2a97e27`, PR #17)

### Added
- `.claude/settings.local.json` — 로컬 개인 설정 오버라이드 (`includeCoAuthoredBy` 등). 관례상 `.local` 접미는 "커밋 제외" 의미 → `.gitignore` 명시
- `.gitignore` 에 `.claude/settings.local.json` 한 줄 추가

---

## [2026-04-21] KIS sync PR 6: 로깅 마스킹 (시리즈 최종) (`1483940`, PR #20)

**KIS sync 시리즈 완결** (6/6). PR 5 에서 실 KIS 외부 호출이 열린 직후 노출된 위험을 처리. structlog 기반 구조화 로깅 + 2층 민감 데이터 방어 (키 기반 `[MASKED]` 치환 + JWT/hex 정규식 scrub). 백엔드 테스트 **239 → 295** (+56). 리뷰 HIGH 3건 + MEDIUM 3건 + LOW 1건 수용.

### Added

- **KIS sync PR 6 — 로깅 마스킹** (시리즈 최종): 설계 문서 § 3.5 보안 하드닝 + § 5 PR 6 + § 6 결정 #4.
  - **`app/observability/` 신규 패키지**: 관측 관심사(로깅·메트릭·트레이싱) 집중. `__init__.py` 선제 import 0 유지 (순환 방지, PR 3 `app/security/` 와 동일 규칙).
  - **`app/observability/logging.py`** (~180 lines):
    - `SENSITIVE_KEYS` frozenset — 표준 OAuth2/JWT 키(`app_key`·`app_secret`·`access_token`·`authorization`) + 프로젝트 특이 env 필드(`openai_api_key`·`dart_api_key`·`telegram_bot_token`·`krx_id`·`krx_pw`·`kis_app_key_mock`) 명시
    - `SENSITIVE_KEY_SUFFIXES` tuple — 신규 env 필드 자동 커버용 접미 일치 (`_api_key`·`_app_secret`·`_bot_token`·`_master_key`·`_credential` 등 14종)
    - `_is_sensitive_key(key)` 헬퍼 — 완전 일치 + 접미 일치 OR 검사, 대소문자 무시
    - `_scan(node)` 재귀 스캔 — dict/list/tuple 의 민감 키 값 `[MASKED]`, string leaf 는 `_scrub_string`
    - `_scrub_string(s)` — `eyJ` 접두 JWT 3-segment (`[MASKED_JWT]`) + 40자 이상 hex (`[MASKED_HEX]`). JOSE 표준 준수 덕에 structlog logger 이름 false positive 차단
    - `mask_sensitive` structlog processor — renderer 직전에 event_dict 전체 재귀 마스킹
    - `setup_logging(log_level, json_output)` — stdlib ↔ structlog `ProcessorFormatter` 브릿지. `_configured` guard 로 **1회만 유효** (재호출 no-op) → pytest `caplog` 외부 핸들러 보존
    - `reset_logging_for_tests()` — 테스트 전용 guard 리셋
  - **`app/main.py`**: `create_app()` 앞단에서 `setup_logging(log_level, json_output=app_env!="local")` 호출. idempotent 라 re-invocation 안전.
  - **`app/config/settings.py`**: `log_level: Literal["DEBUG","INFO","WARNING","ERROR","CRITICAL"]` 필드 추가 — 오타 env var 가 Pydantic 검증에서 즉시 실패.
  - **README**:
    - "**KIS OpenAPI 토큰 revoke 한계**" 섹션 신설 — 24h 고정 TTL, 명시적 폐기 엔드포인트 부재. credential 삭제 시 기존 토큰은 만료까지 유효. 유출 의심 시 KIS 웹사이트에서 `app_key` 재발급(roll) 절차 명시 (결정 #4 반영).
    - "**로깅 민감 데이터 보호**" 섹션 — 2층 방어 메커니즘과 `SENSITIVE_KEYS` 확장 방법 안내.
  - **테스트 56건 추가** (백엔드 **239 → 295**):
    - `_scrub_string` 5건 (JWT eyJ 접두 + hex 40자+ + 한국어 보존 + `eyJ` 없는 dotted 식별자 false positive 방어)
    - `_scan` 9건 (parametrized SENSITIVE_KEYS 26 + 중첩 dict/list + 비민감 키 보존 + None 유지)
    - compound keys via suffix 8건 — `openai_api_key`·`dart_api_key`·`kis_app_key_mock`·`telegram_bot_token`·`krx_pw` 등 실제 env 필드 검증
    - `mask_sensitive` processor 2건
    - 통합 4건 (stdlib logger extra drop + JWT scrub + structlog native bind + idempotent guard 강화 — foreign 핸들러 보존 검증)

### Process Notes

- **리뷰 HIGH 3건 전부 수용**:
  - HIGH #1 JWT 패턴 false positive → `eyJ` 접두 제약으로 Python 식별자 오탐 차단
  - HIGH #2 `_configured` dead code → 실제 early-return guard 로 전환 + `reset_logging_for_tests` 헬퍼 노출. pytest `caplog` 같은 외부 핸들러를 silently 제거하던 문제 해결
  - HIGH #3 SENSITIVE_KEYS 누락 → `SENSITIVE_KEY_SUFFIXES` 도입 + 프로젝트 특이 필드 explicit 목록화로 2층 방어
- **리뷰 MEDIUM 3건 + LOW 1건 수용**: `assert` → 방어적 `if isinstance` 분기 (`-O` 환경 안전), `log_level: Literal[...]` Pydantic enum 좁히기, 테스트 `type: ignore` 제거 + `Callable[[], None]` 타입 힌트.
- **Defer (사유)**: LOW #2 hex 40자 임계값 유지 — 현 KIS 도메인 실문제 없음, 56자 상향은 별도 정책 논의. LOW #3 테스트 격리 — `reset_logging_for_tests` + `autouse` fixture 로 해소됨.

### 🎉 KIS sync 시리즈 완결

6 PR 누적 성과:
- PR #12 (엑셀 import, `6ea71fe`)
- PR #13 (어댑터 분기 스캐폴딩, `269651e`)
- PR #14 (Fernet credential 저장소, `3db778f`)
- PR #15 (등록 API + Settings UI, `d470a73`)
- PR #16 (연결 테스트 + 실 sync wire, `1461582`)
- **PR #N (로깅 마스킹, 본 PR)**

백엔드 테스트: 197 → **295** (+98, smoke 1 deselected). CI 6회 연속 4/4 PASS. 외부 호출 0 에서 출발해 실 KIS 호출 개시 + 민감 데이터 로그 누수 방어까지 완결.

---

## [2026-04-21] KIS sync PR 5: 연결 테스트 + 실 sync wire (`1461582`, PR #16)

1-PR 세션: KIS sync 시리즈 5/6. 본 PR 머지부터 **운영 코드에서 실 KIS 외부 호출이 가능** — CI 는 `@pytest.mark.requires_kis_real_account` 마커 + pyproject `addopts` 로 smoke 1건을 skip, 나머지 real 경로 테스트 11건은 `httpx.MockTransport` 로 실 URL 차단. 백엔드 테스트 **227 → 239** (+12, smoke 1 deselected). 리뷰 HIGH 6건 중 4건 수용, 2건 구조적(Hexagonal 위반·Optional 파라미터 런타임 퇴화) defer.

### Added

- **KIS sync PR 5 — 연결 테스트 + 실 sync wire**: 설계 문서 § 3.4 (3단계 온보딩) + § 5 PR 5.
  - **`KisClient.test_connection()`** (`kis_client.py`): OAuth 토큰 발급만 시도하는 dry-run. 잔고 조회 API 호출 안 함 → 계좌 상태 변경 0. 부수 효과: 토큰 캐시에 저장돼 이어지는 `fetch_balance()` 는 재발급 skip. 재시도 없음 ("빠른 1회 검증" 의미).
  - **`TestKisConnectionUseCase`** (`portfolio_service.py`): `__test__ = False` (pytest auto-collection 제외). credential decrypt → `async with factory(credentials) as client: await client.test_connection()`. 토큰 실패는 `SyncError` 로 감싸 router 가 502 로 변환.
  - **`SyncPortfolioFromKisUseCase` wire**: `credential_repo` + `real_client_factory` 주입받아 `kis_rest_real` 분기 실구현. `_fetch_balance_real` / `_fetch_balance_mock` 서브 메서드로 분리. `KisCredentialsNotWiredError` 예외 클래스 삭제.
  - **`_ensure_kis_real_account` 공통 헬퍼**: 계좌 존재 + `connection_type='kis_rest_real'` + `environment='real'` 검증을 한 곳에 집중. `BrokerageCredentialUseCase` · `TestKisConnectionUseCase` · `SyncPortfolioFromKisUseCase` 모두 이 헬퍼 위임.
  - **`KisRealClientFactory`** 타입 별칭 + **`get_kis_real_client_factory()`** DI (`_deps.py`): 요청 스코프 factory. 각 요청이 credential 별 고유 `KisClient(REAL)` 를 생성, `async with` 로 httpx 커넥션 풀 정리. 테스트는 `dependency_overrides` 로 MockTransport 주입한 factory 로 치환.
  - **HTTP 엔드포인트** `POST /api/portfolio/accounts/{id}/test-connection` → `{account_id, environment, ok}` (200) / 404 (계좌·credential 미등록) / 400 (비 `kis_rest_real`) / 403 (env 불일치) / 502 (KIS 토큰 발급 실패) / 500 (cipher 실패). 기존 `/sync` 는 real 분기 정상 동작 + credential 미등록 시 404.
  - **`_credential_error_to_http` 공통 매퍼**: sync + test-connection + credential CRUD 6개 엔드포인트의 예외 핸들러를 단일 함수로 통합 (`SyncError` → 502 포함). 각 엔드포인트의 try/except 블록이 2줄로 간소화.
  - **pytest marker `requires_kis_real_account`** (`pyproject.toml`): `addopts` 에 `-m "not requires_kis_real_account"` 로 기본 skip, 로컬 개발자는 `pytest -m requires_kis_real_account` 로 오버라이드해 실 KIS 검증. `KIS_REAL_APP_KEY`/`SECRET`/`ACCOUNT_NO` env 가 비어있으면 smoke 내부에서 `pytest.skip()`.
  - **FE `RealAccountSection`**: 각 credential 등록 계좌 행에 **"연결 테스트"** 버튼 추가 (민트/그린 `#65D6A1`). 502 응답은 중립 메시지 ("KIS 업스트림 오류. 잠시 후 재시도하거나 자격증명을 확인해주세요").
  - **FE Portfolio 페이지**: sync 버튼이 `kis_rest_real` 계좌에서도 활성화 (기존은 `kis_rest_mock` 만). 버튼 라벨이 connection_type 에 따라 "KIS 실계좌 동기화" / "KIS 모의 동기화" 분기. 404 응답에 `kis_rest_real` 조합이면 "자격증명 미등록 — 설정에서 등록" 맥락 배너 표시.
  - **FE API 클라이언트**: `testKisConnection(accountId)` 추가. `TestConnectionResponse` 타입은 `{ok: true, environment: 'real'}` 리터럴로 좁혀 성공 경로를 타입 계약으로 강제.
  - **테스트 12건 추가** (백엔드 **227 → 239**, smoke 1 deselected):
    - use case 4건 (토큰 성공·credential 미등록·비 real 계좌 거부·토큰 401 → SyncError)
    - real sync 2건 (MockTransport 로 fetch_balance · upstream 500)
    - HTTP 엔드포인트 5건 (test-connection 성공·404·502·400 + sync real 성공·404)
    - smoke 1건 (`@pytest.mark.requires_kis_real_account`, env 없으면 skip, CI deselected)

### Process Notes

- **리뷰 HIGH 4건 수용**: `_raise_for_credential_error` → `_credential_error_to_http` (raise 아닌 return 의미 반영) + `SyncError` 매퍼 포함, `SyncPortfolioFromKisUseCase.execute` 에서 `_ensure_kis_real_account` 통합 (검증 책임 집중), `_credential_response(view: object)` → `MaskedCredentialView` 로 타입 narrow, `TestConnectionResponse.ok: boolean` → `true` 리터럴 + `environment: 'real'` 리터럴 (dead code 제거).
- **리뷰 MEDIUM/LOW 수용**: `test_connection()` docstring 보강 (부수 효과 + 재시도 없음 명시), 포트폴리오 sync 404 분기 (credential 미등록 맥락 메시지), 502 메시지 중립화, `delete_credential` 불필요 `return None` 제거, pyproject addopts 주석 보강.
- **Defer (사유 `HANDOFF.md` 기록)**: Hexagonal 레이어 위반 (`MaskedCredentialView` re-export — 구조 리팩터 별도 PR), `SyncPortfolioFromKisUseCase.__init__` Optional 파라미터 RuntimeError 퇴화 (mock/real UseCase 분리 필요 — 도메인 재설계), `KisAuthError` 별도 HTTP 매핑 (4xx vs 5xx — KIS 응답 status 검증 테스트 필요), `asyncio_mode=auto` + `@pytest.mark.asyncio` 중복 (프로젝트 전반 마이그레이션), `actionPending` 다른 계좌 disabled 이유 시각화 · `window.prompt` · `title` vs `sr-only` (UX 폴리싱 단계).

---

## [2026-04-21] KIS sync PR 4: 실계정 등록 API + Settings UI (`d470a73`, PR #15)

1-PR 세션: KIS sync 시리즈 4/6. 외부 호출 0 유지 — credential 등록·마스킹·삭제 CRUD 만, 실 KIS 호출은 PR 5. 백엔드 테스트 **213 → 227** (+14), Next.js build PASS, mypy strict 0 (내 파일), ruff 0. 리뷰 HIGH 6건 전부 반영.

### Added

- **KIS sync PR 4 — 실계정 등록 API + Settings UI**: 설계 문서 § 3.4 (2단계 온보딩) + § 5 PR 4.
  - **BE 4 엔드포인트** (`app/adapter/web/routers/portfolio.py`):
    - `POST /api/portfolio/accounts/{id}/credentials` → 201, 이미 있으면 409
    - `PUT /api/portfolio/accounts/{id}/credentials` → 200, 없으면 404
    - `GET /api/portfolio/accounts/{id}/credentials` → 마스킹 뷰 (`app_key_masked` / `account_no_masked` + `key_version`·`created_at`·`updated_at`). `app_secret` 은 어떤 경로로도 노출 0.
    - `DELETE /api/portfolio/accounts/{id}/credentials` → 204, 없으면 404
    - 모든 엔드포인트 `require_admin_key` 보호. 계좌는 `connection_type='kis_rest_real'` + `environment='real'` 조합만 허용 — 위반 시 400/403.
  - **`BrokerageCredentialUseCase`** (`portfolio_service.py`): `create`/`replace`/`get_masked`/`delete` + `_ensure_real_account` 공통 전처리. `_require_view` 로 `assert` 대신 `RuntimeError` loud fail (`python -O` 대응).
  - **`RegisterAccountUseCase` 완화**: `environment='real'` 을 `kis_rest_real` 조합에서 허용. 불일치 조합은 `InvalidRealEnvironmentError` → 403.
  - **예외 추가**: `CredentialAlreadyExistsError` (→ 409), `CredentialNotFoundError` (→ 404). `CredentialCipherError` 계층(`DecryptionFailedError`/`UnknownKeyVersionError`)은 router 에서 별도 catch → 500 + 내부 스택트레이스/예외 타입 미노출 (`_cipher_failure_as_http`).
  - **Repository 확장** (`brokerage_credential.py`): `find_row` (복호화 없이 존재 체크), `get_masked_view` (필요 필드만 복호화 후 마스킹 DTO 반환). `_mask_tail` 헬퍼는 **비례 길이 마스킹** — `len(value) - keep` 만큼 불릿 생성해 "얼마나 가렸는지" 가 시각적으로 드러남.
  - **Pydantic 스키마**: `BrokerageCredentialRequest` (app_key `min_length=16` + `\S+`, app_secret 동일, account_no `^\d{8}-\d{2}$`), `BrokerageCredentialResponse` (`_Base` 상속, `app_secret` 필드 없음). `AccountCreateRequest` 패턴 완화 — `connection_type` 에 `kis_rest_real`, `environment` 에 `real` 추가. 조합 검증은 UseCase 로 이관.
  - **FE `RealAccountSection`** (`components/features/RealAccountSection.tsx`, 신규 ~380 lines): 계좌 목록 + 등록 폼 (별칭 · app_key · app_secret · 계좌번호) + 수정(window.prompt × 3) + 삭제 버튼. 비례 길이 마스킹 뷰. `actionPending` state 로 수정/삭제 버튼 중복 클릭 차단. PUT→POST 폴백 + 409 경합 시 PUT 재시도로 race 자동 해소.
  - **FE Settings 페이지**: 기존 알림 설정 아래에 `<RealAccountSection/>` 섹션 추가. 알림 설정 저장 UI 는 불변.
  - **FE API 클라이언트**: `getCredential/createCredential/replaceCredential/deleteCredential`. DELETE 는 204 No Content 본문 없어서 `adminCall` 대신 direct fetch (`adminCall` 의 `res.json()` 강제 실행 한계 회피).
  - **테스트 14건 추가** (백엔드 **213 → 227**):
    - cipher/repo 단위 2건 (비례 마스킹 정확도·부재 시 None)
    - HTTP 엔드포인트 9건 (admin key 강제, POST 201/409, PUT 200/404, GET 마스킹/404 + DELETE 204 → 후속 GET 404, 비 `kis_rest_real` 거부, account_no 형식 검증, 모든 verb unknown account 404, cipher 실패 → 500 + 내부 예외 타입 응답 미노출)
    - `test_portfolio.py` 3건: PR 4 조합 검증 (mismatched env → 403, 역조합 → 403, 정상 `kis_rest_real` → 201)

### Process Notes

- 리뷰 HIGH 6건(BE 2 + FE 4) 전부 반영: CredentialCipherError catch + 500 변환, `assert` → `RuntimeError`, `_mask_tail` 비례 마스킹, `BrokerageCredentialResponse` `_Base` 상속, `handleCreate` 흐름 재구성 (reload 실패와 폼 클로저 분리), `showForm` 토글 stale closure 함수형 업데이터 내부로, `actionPending` 추가.
- 스킵: MEDIUM `MaskedCredentialView` layer re-export (구조 리팩터 PR 5 때), TOCTOU POST race (Admin + DB UNIQUE 보호), DELETE 의 cipher 주입 필수 (repo 생성자 구조 — PR 5 때 재조직), `adminCall` void 지원 (별도 리팩터), toast 중복 (공용 Context 후보), window.prompt UX (MVP 허용).

---

## [2026-04-21] KIS sync PR 3: `brokerage_account_credential` + Fernet 암호화 (`3db778f`, PR #14)

1-PR 세션: KIS sync 시리즈 3/6. 외부 호출 0, credential 저장소만 — 등록 API/UI 는 PR 4. CI 4/4 PASS × 1회. 백엔드 테스트 **204 → 213** (+9).

### Added
- **KIS sync PR 3 — `brokerage_account_credential` + Fernet 암호화**: 설계 문서 § 3.2 / § 5 PR 3. 외부 호출 0, PR 2 머지 후 다음 단계. credential 저장소만 — 등록 API/UI 는 PR 4.
  - **신규 패키지** `app/security/` — 도메인 중립 보안 프리미티브. `__init__.py` 는 선제 import 0 (순환 방지용).
  - **`CredentialCipher`** (`app/security/credential_cipher.py`): Fernet 래퍼. `encrypt(plain) -> (bytes, key_version)` / `decrypt(cipher, version) -> plain`. `key_version` 다중 저장 dict 로 회전 대비 (현재 v1). 예외 계층:
    - `MasterKeyNotConfiguredError`: 빈 env var 시 생성자 loud fail
    - `UnknownKeyVersionError`: 등록 안 된 key_version 복호화 시도
    - `DecryptionFailedError`: Fernet `InvalidToken` 감싸기 (외부로 cryptography 예외 미노출, 메시지에 plaintext/bytes 없음)
  - **신규 테이블** `brokerage_account_credential` (migration `008_brokerage_credential`): `app_key_cipher`/`app_secret_cipher`/`account_no_cipher` BYTEA + `key_version` + `UNIQUE(account_id)` + FK CASCADE. downgrade 에 `DO $$` PL/pgSQL 가드로 데이터 있을 시 RAISE EXCEPTION (운영 안전망).
  - **`BrokerageAccountCredentialRepository`**: cipher 주입, `upsert`/`get_decrypted`/`delete` async 메서드. `CursorResult` 타입 캐스트로 mypy strict 호환.
  - **`get_credential_cipher()`** DI (`_deps.py`): `lru_cache(maxsize=1)` 싱글톤. `conftest.apply_migrations` 가 `cache_clear()` 호출로 테스트 격리 보장.
  - **`Settings.kis_credential_master_key: str`** env var 매핑, default `""` (빈 값이면 cipher 생성자에서 loud fail).
  - **`cryptography>=43.0`** 의존성 추가.
  - **conftest fixture**: 세션 시작 시 빈 env var 면 `Fernet.generate_key()` 로 더미 마스터키 주입 (CI 실 자격증명 없이 테스트 통과).
  - **테스트 9건 추가** (백엔드 **204 → 213**): cipher 유닛 5건 (왕복·잘못된 키·빈 키·잘못된 형식 키·unknown version) + repo 통합 4건 (upsert→get 왕복·재 upsert update·delete·FK CASCADE).

### Process Notes
- 리뷰 CRITICAL 1 + HIGH 2 + MEDIUM 2 모두 반영 (mypy CursorResult 캐스트, DecryptionFailedError 래퍼, ruff import 정렬, conftest cache_clear, downgrade DO$$ 가드).
- 초기 `app/application/service/credential_cipher.py` 위치 → `service/__init__.py` 가 BacktestEngineService→repositories 체인 유발해 circular import. `app/security/` 신규 패키지로 이동 (도메인 중립, `__init__.py` 순수) 해 해결.

---

## [2026-04-21] KIS sync PR 2: `kis_rest_real` 어댑터 분기 스캐폴딩 (`269651e`, PR #13)

1-PR 세션: KIS sync 시리즈 2/6. 외부 호출 0, credential 저장소(PR 3) 미연결 상태에서 분기 구조만 선제 구축. CI 4/4 PASS × 1회. 백엔드 테스트 **197 → 204** (+7).

### Added
- **KIS sync PR 2 — `kis_rest_real` 어댑터 분기 스캐폴딩**: 설계 문서 `docs/kis-real-account-sync-plan.md` § 5 PR 2. 외부 호출 0, credential 저장소(PR 3) 미연결 상태에서 분기 구조만 선제 구축.
  - `KisEnvironment(StrEnum)`: `MOCK` / `REAL` — OpenAPI 환경 구분.
  - `KisCredentials` DTO (`frozen=True, slots=True`): `app_key`·`app_secret`·`account_no`. `__repr__` 마스킹 (`app_secret`/`account_no` `<masked>`, `app_key` 끝 4자리만 노출).
  - `KisClient.__init__(environment, credentials)` 파라미터 추가. MOCK 경로 100% 하위호환 (credentials 미주입 시 Settings 경로 유지). MOCK `base_url` 은 `_MOCK_BASE_URL` 상수 직접 할당 — Settings 커스터마이징으로 실 URL 을 mock 으로 위장하는 경로 차단.
  - REAL 경로: `_REAL_BASE_URL = "https://openapi.koreainvestment.com:9443"`, 잔고 TR_ID `TTTC8434R` (vs MOCK `VTTC8434R`). credentials 미주입 시 `KisNotConfiguredError`.
  - `VALID_CONNECTION_TYPES` 에 `'kis_rest_real'` 추가 + DB CHECK 마이그레이션 `007_kis_real_connection`.
  - `SyncPortfolioFromKisUseCase` 분기: `kis_rest_real` + `environment='real'` 조합이면 `KisCredentialsNotWiredError` (PR 3 대기용 명시 장벽). 라우터는 **HTTP 501 Not Implemented** 로 매핑 (503 대신 — 의미론상 "기능 미구현" 이 정확).
  - 백엔드 테스트 **197 → 204** (+7: REAL URL/TR_ID 1, REAL credentials 필수 1, MOCK credentials 주입 1, `__repr__` 마스킹 1, use case 분기 2, enum/CHECK 동기화 assert 1).

### Process Notes
- 리뷰 HIGH 1 + MEDIUM 4 중 HIGH 1 (MOCK base_url 상수 직접 할당) + MEDIUM 2 (503→501) + MEDIUM 3 (동기화 assert) 반영. MEDIUM 1 (`__str__` 명시) + MEDIUM 4 (downgrade DO$$ 체크) 는 ROI 낮아 기록만.
- Alembic revision ID `007_portfolio_kis_real_connection` 은 VARCHAR(32) 초과 → `007_kis_real_connection` 으로 단축 (테스트 실패로 발견).

---

## [2026-04-20] KIS sync 설계 + 엑셀 거래내역 import (`6ea71fe`, PR #12)

1-PR 세션: **KIS 실계정 sync 6 PR 시리즈** 설계 확정 + **PR 1 (엑셀 거래내역 import)** 완결. 외부 호출 0, 실 자격증명 없이 동작하는 온보딩 1단계. CI 4/4 PASS × 1회. 백엔드 테스트 **185 → 197** (+12).

### Added
- **설계 문서** `docs/kis-real-account-sync-plan.md`: 6 PR 분할 (엑셀 → 어댑터 분기 → Fernet credential → 등록 UI → 실 sync → 로깅 마스킹), 5개 열린 질문 결정 (env var Fernet, 로컬 단일 사용자, 엑셀 포함, token revoke 한계 수용, CI 더미 Fernet fixture).
- **엑셀 거래내역 import** — 온보딩 1단계 완결:
  - `POST /api/portfolio/accounts/{id}/import/excel` (multipart/form-data) — 10MB/10_000행 가드, 컬럼 alias 매칭, 중복 스킵(account·stock·date·type·qty·price tuple), stock 미등록 시 자동 생성.
  - 신규 모듈 `app/application/service/excel_import_service.py` — 파서(`parse_kis_transaction_xlsx`) + 서비스(`ExcelImportService`) 단일 파일. 실 KIS 샘플 부재라 컬럼 alias `(체결일자/거래일자/…, 종목코드/상품번호/…, 체결수량/거래수량/…)` 로 유연 매칭.
  - 프론트 `<ExcelImportPanel>` (Portfolio 페이지) — 파일 선택 → 업로드 → 실패 행 details 펼치기.
  - Next.js admin 릴레이 라우터에 multipart 경로 분기: `arrayBuffer()` 바이너리 포워드 + multipart 만 10MB 허용 (기존 64KB text 경로 유지).

### Changed
- **`portfolio_transaction.source`** CHECK 제약 확장: `('manual', 'kis_sync', 'excel_import')`. Alembic migration `006_portfolio_excel_source.py` (ALTER DROP/ADD). 기존 행 영향 없음.
- `VALID_SOURCES` (Python) + `TransactionSource` (TypeScript) 에 `'excel_import'` 반영.

### Process Notes
- **리뷰 HIGH 3 + MEDIUM 다수 반영** (python-reviewer + typescript-reviewer 병렬). Python HIGH 2 (iterrows 타입 / except 범위) 반영, HIGH 3 (session.begin 부재) 는 `get_session` 이 요청-스코프 관리 → overcall 판정. TS HIGH (Content-Length 스푸핑) 은 `arrayBuffer().byteLength` 2차 가드로 방어.
- **설계 전제 자체 교정**: 초기 "스케일 보존" 표현이 `round(0.0, 4)=0.0` 로 인해 틀렸음이 테스트 실패로 2분 내 드러남. 회귀 방어선을 재정의하고 테스트 재작성 — 설계안 검증에 코드 실행 루프가 중요함 재확인.

---

## [2026-04-20] _dec 리팩터: or Decimal("0") fallback 제거 + NaN loud fail (`e14a27b`, PR #11)

1-PR 세션: PR #9 리뷰 MEDIUM #2 사전 부채 청산. `_dec` 시그니처 단순화 + 도달불가 fallback 제거 + NaN loud fail. 백엔드 테스트 **183 → 185** (+2). CI 4/4 PASS × 1회.

### Changed
- **`_dec` 리팩터 — 도달불가 fallback 제거 + NaN loud fail** (`src/backend_py/app/application/service/backtest_service.py`): 직전 PR #9 리뷰 MEDIUM #2 사전 부채 청산.
  - 시그니처 `(float | None) -> Decimal | None` → `(float) -> Decimal`. None 반환 경로 제거.
  - L151-152 `_dec(hit_rate) or Decimal("0")` → `_dec(hit_rate)`. 호출 컨텍스트에서 `hit_rate`/`avg_ret` 는 `if observed > 0 else 0.0` guard 로 concrete float 보장이라 `or` fallback 이 도달불가였고, Zero Decimal falsy 특성 때문에 의도를 흐리는 안티패턴이었음.
  - NaN 입력은 `ValueError("_dec requires numeric value; caller must pre-guard None/NaN")` 으로 loud fail. `pd.isna` 대신 `math.isnan` 사용 — 시그니처가 `float` 라 stdlib 가 contract 와 자연스럽게 일치, 배열 입력 함정 회피.

### Added
- **`_dec` 유닛 테스트 1건 + 집계 통합 테스트 1건** (`tests/test_services.py`, 백엔드 **183 → 185**):
  - `test_dec_always_returns_decimal_and_rejects_nan`: float → Decimal 반환, NaN ValueError, `round(float, 4)` 가 입력 자연 스케일 보존 (예: `_dec(0.0) == Decimal('0.0')`, exp=-1) 을 문서화.
  - `test_backtest_aggregation_stores_zero_as_decimal`: 모든 수익률 0 시나리오 → `BacktestResult.hit_rate_5d`/`avg_return_5d` 가 None 이 아닌 `Decimal(0)` 으로 저장. 리팩터 후에도 집계 경로가 nullable 컬럼에 None 을 새지 않음을 고정.

---

## [2026-04-20] I6 설정 저장 toast E2E 2건 (`63e992a`, PR #10)

1-PR 세션: HANDOFF 차기 1순위 "I6 (설정 저장 toast) E2E" 완결. E2E 40 → **42 케이스** (I6-1 성공·I6-2 실패 2건 추가). CI 4/4 PASS × 1회.

### Added
- **I6 설정 저장 toast E2E 2건** (`src/frontend/tests/e2e/settings.spec.ts`, PR #10): `page.route('**/api/admin/notifications/preferences')` 로 PUT 만 인터셉트하고 GET URL(`/api/notifications/preferences`, admin 경로 아님) 은 매칭되지 않아 초기 로딩이 실제 백엔드로 pass-through → `notification_preference` 싱글톤 mutation 0건 보장.
  - **I6-1 (성공 경로)**: `waitForRequest + click` 을 `Promise.all` 로 동기화해 race 제거, `postDataJSON()` 로 form payload 검증 (`daily_summary_enabled`, `min_score`, `signal_types` 포함), `role=status` toast 를 `filter({ hasText: '저장되었습니다' })` 로 정밀 매칭.
  - **I6-2 (실패 경로)**: PUT 500 stub → `filter({ hasText: '서버 오류가 발생했습니다' })` toast 검증.

### Changed
- **`docs/e2e-portfolio-test-plan.md`** I 섹션: I6-1·I6-2 행 추가, 격리 전략 주석 갱신 ("별도 PR" → `page.route` 인터셉트), 상태 라인 "40/40 → **42/42**" 로 갱신.

---

## [2026-04-20] 백테스트 Infinity 버그 수정 + close_price 분모 가드 (`74938cf`)

1-PR 세션: 직전 세션 HANDOFF 1순위 차기 후보였던 **TREND_REVERSAL `avg_return=Infinity` INSERT 실패** 를 `/ted-run` 파이프라인으로 처리. master 에 커밋 **1건** 추가 (PR #9 머지 + delete-branch, CI 4/4 PASS). 백엔드 테스트 181 → **183** (신규 2건: close=0 베이스 / future=0 전손).

### Fixed
- **`BacktestEngineService` Infinity 발생 경로 차단** (`74938cf`, PR #9): 상장폐지/정지 종목의 `close_price=0` 이 분모로 쓰여 `(future/0-1) = Infinity` 가 `series.mean()` 으로 전파 → `BacktestResult.avg_return_Nd` NUMERIC(10,4) 범위 초과 → `NumericValueOutOfRangeError`. 2-layer guard 적용.
  - **Layer 1 (분모 마스킹)**: `price_base = price_wide.where(price_wide > 0)`. 분자는 원본 유지해 `future=0 & base>0` 케이스가 `(0/base-1) = -100%` 라는 유효한 전손 수익률로 기록되게 함. 분자·분모 동시 마스킹 시 -100% 가 `None` 으로 유실돼 집계 왜곡 발생 (리뷰 HIGH #1 지적).
  - **Layer 2 (isfinite 필수 가드)**: `returns = {n: df.where(np.isfinite(df)) for n, df in returns.items()}`. 집계 경로의 `series.dropna().mean()` 은 NaN 만 제거하고 inf 는 남기므로 단일 inf 가 평균을 `Decimal('Infinity')` 로 만듦. "방어선" 이 아니라 **필수** (리뷰 HIGH #2 지적).

### Added
- **회귀 테스트 2건** (`74938cf`, `tests/test_services.py`):
  - `test_backtest_handles_zero_close_price_without_infinity`: 기준일 `close=0` → `signal.return_Nd=None`, `BacktestResult` INSERT 성공 (NumericValueOutOfRangeError 미발생).
  - `test_backtest_preserves_minus_hundred_when_future_close_zero`: `base=10000, future=0` (d+5..d+20) → `return_Nd ≈ -100` 유지. 분모만 마스킹하는 설계가 전손 수익률을 보존함을 고정.

### Process Notes
- **`/ted-run` 파이프라인 첫 실측**: 구현 → 리뷰 → 빌드 → 커밋 4단계 자동 연결. 리뷰 단계에서 HIGH 2건 + MEDIUM 1건 지적받고 즉시 수정 반영. 리뷰어가 uncommitted 변경을 git tree 에서 못 읽는 툴링 제약은 있었지만, 지적 사항이 매우 구체적이라 수정 대조 + 회귀 테스트 통과로 효력 검증 가능했음.
- **리뷰 MEDIUM #2 (`_dec(val) or Decimal("0")` fragile 패턴)**: 사전 부채로 분류, 별도 PR 로 이관 가능.

---

## [2026-04-20] 시그널 튜닝 · 알림 가드 · 설정 페이지 복구 (`e6c4345` · `c344e89` · `6b3b56f`)

3-PR 세션: HANDOFF 1·2·3 순위 연속 완결 + 예상 외 프로덕션 버그 복구.
master 에 커밋 **3건** 추가 (PR #6·#7·#8 모두 머지 + delete-branch, CI 4/4 PASS × 3회).
백엔드 테스트 178 → **181** (신규 6건: NotificationService 필터·실패·no-op 5 + batch Step 3 배선 1,
테스트 스위트 내 기존 카운트 편차는 signal tuning 경계 +1 포함). E2E 31 → **38 케이스**
(A4 + F5 + I1~I5 = 7건 신규, 설정 페이지 E2E 최초 도입).

### Changed
- **시그널 탐지 임계값·가중치 재정비** (`e6c4345`, PR #6): 3년 백필 70,609 건에서 저등급 비중 과다(SHORT_SQUEEZE 81% C-grade, TREND_REVERSAL 22% D-grade, RAPID_DECLINE 62% A-grade 편향) 확인 후 기준치 상향.
  - RAPID_DECLINE: 임계 -10% → **-12%**, base 계수 `abs*3` → `abs*2.5`, 버퍼 `+20` → `+10`
  - TREND_REVERSAL: `score >= 50` 필터 신규 추가 (크로스 감지 후 품질 게이트)
  - SHORT_SQUEEZE: `MIN_SCORE` 40 → **60**
  - 예상 감소율: 70,609 → 30,234 (**-57.2%**). 기존 신호는 append 모델로 보존, 월요일 07:00 KST 스케줄러가 새 기준으로 재탐지하며 자연 검증.
- **설정 페이지 snake_case 통일** (`6b3b56f`, PR #8): `types/notification.ts` 만 camelCase 로 작성돼 있어 프로젝트 컨벤션(snake_case)에서 이탈. 전체 프로젝트와 일관화.
- **`.github/workflows/ci.yml` 에는 변경 없음** — 테스트 개수만 늘었고 워크플로는 기존 그대로 동작.

### Added
- **NotificationService 단위 테스트 5건** (`c344e89`, PR #7, `tests/test_notification_service.py`): `test_min_score_filter_drops_below_threshold` / `test_signal_types_filter_drops_disabled_types` / `test_telegram_disabled_skips_db_access` / `test_partial_send_failure_counts_successes_only` / `test_empty_signals_short_circuits_before_db`. 기존 테스트는 포매팅(N+1 방어 / HTML escape / 한글 라벨) 만 검증해 필터 조건 · 실패 처리 · no-op 경로가 회귀 무방비 상태였음.
- **batch 파이프라인 Step 3 통합 테스트** (`c344e89`, `tests/test_batch.py`): `test_pipeline_step3_dispatches_seeded_signal_to_telegram` — 사전 seed 된 시그널이 KRX 빈 응답 상황에서도 MockTransport 로 Telegram 호출까지 도달하는지 검증. `_notify` 콜백 배선 오류로 `sent=0` 조용히 실패하는 회귀를 감지.
- **RAPID_DECLINE 경계 테스트** (`e6c4345`, `tests/test_services.py`): `test_rapid_decline_ignores_minus_eleven_percent` — 새 -12% 임계에서 -11% 는 더 이상 신호가 아님을 명시적으로 고정.
- **E2E 설정 페이지 섹션 신규** (`6b3b56f`, PR #8, `tests/e2e/settings.spec.ts`): I1~I5 5 케이스 — 진입·채널 스위치 토글·시그널 타입 칩 토글·validation(`disabled` + 경고)·슬라이더 값 라벨 갱신. 저장 경로(I6)는 DB 싱글톤 mutation 격리 전략 확정 후 별도 PR.
- **E2E A4 · F5** (`6b3b56f`): `navigation.spec.ts` 에 NavHeader "설정" 링크 테스트 추가, `stocks.spec.ts` 에 차트 기간 배타 선택(1M/6M `aria-pressed` 상호배타) 검증 추가.
- **HomePage POM 확장**: `settingsLink` / `openSettings()` 추가로 설정 네비게이션 재사용 가능.

### Fixed
- **`/settings` 페이지 런타임 크래시 복구** (`6b3b56f`, PR #8): 백엔드 API 응답이 snake_case 인데 `types/notification.ts` 만 camelCase 로 작성돼 있어 `pref.signalTypes` 가 undefined → `.includes()` 호출 시 크래시. 로딩 스켈레톤 후 Chrome 에러 페이지 "This page couldn't load" 로 전환되던 상태. 타입·페이지·form state 를 전부 snake_case 로 통일해 복구. Next Route Handler(`/api/admin/notifications/preferences/route.ts`) 는 passthrough 라 수정 불필요. 기존 E2E 가 이 페이지를 안 건드려서 감지 못 했던 케이스 — I1~I5 가 이후 회귀 방어.

### Technical Notes
- **승인 루프 준수**: PR #6 은 A/B 옵션 제안 → A 선택 → 구현, PR #8 은 스코프 확장 제안(A/B/C) → A 선택 → 구현. 프로덕션 설정 페이지 버그 발견 시 "E2E 만 하고 덮기" 대신 "같이 수정" 을 사용자 확인 후 진행.
- **격리 전략 일관성**: NotificationService 테스트는 `httpx.MockTransport` + testcontainers + `db_cleaner` TRUNCATE, E2E 설정 테스트는 "로컬 React state 만 조작, 저장 PUT 안 누름" 으로 싱글톤 mutation 회피.
- **로컬 실측**: 각 PR 전 전체 pytest 175/181 pass, 최종 E2E 37/37 (H5 는 로컬 seed 미적용 환경 이슈로 제외, CI 에서는 seed 실행되므로 정상). ruff/mypy/tsc 전부 통과.

---

## [2026-04-20] 백테스트 주간 스케줄러 + E2E 실데이터 전환 (`ce0ecba` · `5ffef6d`)

2-PR 세션: 전 세션 carry-over 1순위였던 `backtest_result` 0건 기술부채 해소.
master 에 커밋 **2건** 추가 (PR #4·#5 모두 머지 + delete-branch, CI 4/4 PASS × 2회).
백엔드 테스트 174 → **178** (신규 4건: 스케줄러 등록 2 + 파이프라인 실적재 2),
E2E 30 → **31 케이스** (H5 실데이터 추가).

### Added
- **백테스트 주간 cron** (`ce0ecba`, PR #4): `app/batch/backtest_job.py` 신규 — `run_backtest_pipeline(period_end, period_years)` 래퍼 + `fire_backtest_pipeline` APScheduler 콜백. `app/batch/scheduler.py` 에 `backtest_enabled=True` 일 때 **월요일 07:00 KST** 트리거 등록 (`market_data` 06:00 배치 1시간 후 주 1회 실행, 직전 3년 재계산).
- **`Settings.backtest_*` 필드 5개** (`ce0ecba`): `backtest_enabled`/`backtest_cron_day_of_week`/`backtest_cron_hour_kst`/`backtest_cron_minute_kst`/`backtest_period_years` (기본 True · mon · 07:00 · 3년). `scheduler_enabled` 와 독립 — 전체 스케줄러는 켠 채 backtest 만 끌 수 있음.
- **`scripts/run_backtest.py` CLI** (`ce0ecba`): one-shot 수동 실행. `--from/--to` 명시 또는 `--years N` 로 직전 N년. 시드·수동 재실행 겸용. 엔진을 직접 호출하는 경로와 래퍼 경유 두 분기 분리.
- **`scripts/seed_backtest_e2e.py`** (`5ffef6d`, PR #5): SignalType 3종 × 삼성전자 기준 signal 1건씩 insert → `run_backtest_pipeline(period_years=1)` 호출. `(stock_id, signal_date, signal_type)` 중복 skip 으로 멱등. 005930 stock 미존재 시 graceful skip.
- **E2E H5 실데이터 케이스** (`5ffef6d`): stub 없이 `/backtest` 방문 → "대차 급감"·"추세 전환"·"숏스퀴즈" 3종 라벨 + "보유기간별 평균 수익률" 차트 h2 렌더 확인. H3/H4 는 미래 회귀 방어선으로 stub 유지.
- **유닛 테스트 4건** (`ce0ecba`): `test_build_scheduler_registers_backtest_cron_when_enabled` / `test_build_scheduler_skips_backtest_when_disabled` / `test_backtest_pipeline_persists_result_rows` (testcontainers + 시그널·가격 시드 → `backtest_result` 적재 검증) / `test_backtest_pipeline_handles_empty_period`.

### Changed
- **`.github/workflows/e2e.yml`** (`5ffef6d`): `Seed E2E accounts` 다음 단계로 `Seed backtest signals + run backtest` 추가. H5 가 이 시드 전제로 동작.
- **`app/main.py` lifespan 로그** (`ce0ecba`): backtest 스케줄(day_of_week/hour/minute) 포함하도록 보강.
- **`tests/test_batch.py`** (`ce0ecba`): 기존 `test_build_scheduler_registers_weekday_cron` 를 `backtest_enabled=False` 명시로 단독 검증 유지. unused import(`Any`, `AsyncMock`) 함께 정리.

### Fixed
- **ruff SIM117** (`5ffef6d` 작업 중): `seed_backtest_e2e.py` 의 중첩 `async with` 를 single 로 병합.

---

## [2026-04-19 → 2026-04-20] E2E · 데이터 버그 체인 · KIS mock · CI 녹색 (`99445b3` … `46f08bb`)

3-PR 세션: 포트폴리오 E2E 도입 → CI 첫 실행 녹색화 → 코드 리뷰 MEDIUM 5 + LOW 4 정리.
master 에 커밋 **21건** 추가 (PR #1·#2·#3 모두 머지 + delete-branch).
백엔드 테스트 158 → **175+** (신규 17건), E2E 0 → **30 케이스** 확보.

### Added
- **Playwright E2E 스위트 30 케이스** (`99445b3` · `eff2d65`): A(내비 3) + B(포트폴리오 리스트 7) + C(쓰기 2) + D(얼라인먼트 6) + E(에러 2) + F(주식 상세 4) + G(AI 리포트 2) + H(백테스트 4). Page Object Model 분리(`HomePage`·`PortfolioPage`·`AlignmentPage`). 3회 연속 로컬 통과 + CI 3회 녹색.
- **`GET /api/signals/latest` 엔드포인트**(`9523ee1`): 가장 최근 `signal_date` 기준 응답. 주말/공휴일 대시보드 빈 상태 회피. `SignalRepository.find_latest_signal_date` 추가.
- **시그널 탐지 백필 스크립트** `scripts/backfill_signal_detection.py`(`8712b3f`): `stock_price` DISTINCT trading_date 기반으로 752영업일 순회. 실측 12분 40초로 `signal` 70,609건 (RAPID 21,056 / TREND 6,242 / SQUEEZE 43,311) 적재.
- **KIS in-memory mock 모드**(`59b2320`): `Settings.kis_use_in_memory_mock=True` 시 `httpx.MockTransport` 자동 주입. KIS sandbox 1분 1회 rate limit 회피. 결정론적 보유 3종(삼성전자/SK하이닉스/NAVER) 반환. 유닛 테스트 2건(+5 기존).
- **E2E 전용 seed 스크립트** `scripts/seed_e2e_accounts.py`(`977ce43`): `brokerage_account`(e2e-manual/e2e-kis) + `portfolio_holding`(005930 10주) + 거래 1건 멱등 시드. CI `.github/workflows/e2e.yml` 의 seed 단계 연결.
- **stock_name 원타임 복구 스크립트** `scripts/fix_stock_names.py`(`b5b5119` · `f651a8d`): `get_market_price_change_by_ticker(market="ALL")` 1회 호출로 전종목 이름 확보. 3,098건 중 2,880건 복구.
- **CI 워크플로 `.github/workflows/e2e.yml`** (`99445b3`): compose up → seed → Caddy internal CA 신뢰 → Playwright → 아티팩트. `KIS_USE_IN_MEMORY_MOCK=true` 주입으로 외부 의존 0.
- **루트 `README.md`**(`99445b3`): 프로젝트 개요 · Quickstart · 파이프라인 커맨드.
- **문서 2건**: `docs/e2e-portfolio-test-plan.md` (테스트 계획서), `docs/data-state.md` (218건 미매칭 stock_name 현상유지 근거, 2026-04-16·17 lending T+1 지연 등 알려진 패턴).
- **유닛 테스트**: `test_market_data_lending_deltas.py` 10건(`177f014`) + `test_kis_client.py` in-memory mock 2건(`59b2320`).
- **`/signals` pagination limit** (`b46371b`): `limit` 쿼리 파라미터(기본 500, 최대 5000). `/signals`·`/signals/latest` 양쪽.

### Changed
- **대시보드 `/` 데이터 소스**(`9523ee1`): `getSignals()` → `getLatestSignals()`. 헤더에 실제 `signal_date` 표시 (오늘이 아니라 최근 탐지일).
- **`ci.yml` Java → Python 이전 반영**(`e7a39ae`): 삭제된 `src/backend/`(Gradle) 참조를 `src/backend_py/`(uv + pytest) 로 교체. `--extra dev`(`e69cfa3`) 로 pytest/testcontainers 설치 보장.
- **lending deltas 헬퍼 모듈 레벨 승격**(`235ab06`, M4+M5): `_fetch_prev_lending` / `_compute_lending_deltas` 를 `MarketDataCollectionService` 에서 모듈 레벨 private 함수로 추출. `prev: object | None` → `LendingBalance | None` 로 타입 정밀화 — `getattr` 우회 제거, mypy strict 가 향후 필드 리네임 감지.
- **`build_stock_name_map` public 승격**(`f651a8d`, M2): 외부 스크립트가 `noqa: SLF001` 로 호출하던 private 메서드를 정식 API 로.
- **E2E D3/D4 실데이터 전제 반영**(`795f3b3`): 시그널 재탐지로 삼성전자에 시그널이 채워짐 → D3 계좌 id=1→2(e2e-kis, 보유 0) 로 전환, D4 초기 empty state 단언 제거.
- **E2E D1 하드코딩 제거**(L3, `ce1044c`): `/portfolio/1/alignment` → `/portfolio/\d+/alignment` 정규식 매칭으로 seed 순서 독립.
- **E2E C2 KIS 응답 stub**(`eff2d65`): 실 sandbox 의존 제거.

### Fixed
- **대차잔고 pykrx 컬럼 오매핑**(`9ed7d86`): `_to_lending_balance_row` 가 `잔고수량`/`BAL_QTY` 만 찾던 것을 **`공매도잔고` / `공매도금액`** 최우선으로 변경. 기존 컬럼명은 fallback 유지. 668,322행이 전부 `balance_quantity=0` 이던 원인 제거.
- **change_rate / change_quantity / consecutive_decrease_days 계산 누락**(`9ed7d86`): `market_data_service` 가 대차잔고 upsert 시 변동률을 계산하지 않던 버그 → `_fetch_prev_lending` + `_compute_lending_deltas` 추가. 3년 재수집 후 `change_rate` 335,863건, RAPID_DECLINE 후보(≤-10%) 21,056건.
- **stock_name 수집 누락**(`b5b5119`): `get_market_ohlcv_by_ticker` 가 종목명 컬럼을 반환하지 않아 α 초기부터 3,093건이 공백이던 문제 → `build_stock_name_map()` 추가 호출로 영구 해결.
- **`_IN_MEMORY_TOKEN` 문서화 주석** (M1, `7e48e01`): 보안 스캐너 false-positive 예방 주석 추가.
- **`backfill_signal_detection.py` 루프 내부 `import json`** (L1, `ce1044c`): 파일 헤더로 이동.
- **`seed_e2e_accounts.py` 경고 메시지 명확화** (L2, `ce1044c`): "보유·거래 시드 모두 skip" 명시.
- **CI `.env.prod` cleanup** (L4, `ce1044c`): Tear down 단계에 `rm -f .env.prod` 추가.

---

## [2026-04-19 — 저녁] E2 + i + 3년 백필 스크립트 (`93a88ec` … `c71a0fc`)

차기 세션 carry-over 2건(DART 단축명 필터 · KRX stock_name/market_type)을 병렬 처리하고, 3년(752영업일) 실데이터 백필 스크립트를 구현·기동. 백필 자체는 백그라운드 약 2시간 실행(완료 보고는 차기 세션). 백엔드 테스트 146 → **158**.

### Added
- **`EXCLUDED_STOCK_CODES` 블랙리스트**(`93a88ec`): `sync_dart_corp_mapping` 에 명시 제외 코드 셋 (`088980` 맥쿼리인프라, `423310` KB발해인프라). DART 단축명이 기존 이름 패턴에 매칭되지 않는 케이스 보완. "인프라" 로 패턴 확장 시 "현대인프라코어" 등 오탐 위험으로 지양.
- **KRX market_type 매핑**(`93a88ec`): `KrxClient._build_market_type_map` 가 KOSPI/KOSDAQ 티커 리스트 2회 조회로 dict 구성. `_to_stock_price_row` 가 market_type 을 주입받아 row 컬럼 미존재 시에도 정확 매핑.
- **`StockRepository.upsert_by_code` 보호 규칙**(`93a88ec`): 빈 `stock_name` 은 기존 row 의 이름을 덮어쓰지 않음. β 가 시드한 5 핵심 종목 이름이 α 재실행으로 공백화되는 회귀 차단.
- **`scripts/backfill_stock_prices.py`**(`c71a0fc`): urllib 기반 CLI. `POST /api/batch/collect?date=...` 를 영업일 역순(오름차순 정렬 후 실행)으로 순회. 기본 752영업일. 중간 실패는 개별 날짜만 기록하고 진행. 배치 내부가 upsert 멱등이라 재실행 안전.
- **테스트 8건**: E2 2건(코드 블랙리스트 경계값) + i 3건(KOSDAQ 매핑·upsert 이름 보존 2종) + 백필 3건(business_days_back) + 기존 KRX 테스트 3건에 `get_market_ticker_list` stub 확장.

### Verified (실측)
- **E2 블랙리스트 동작 확인** — `sync_dart_corp_mapping --dry-run` 재실행 시 DART 기본 3,654 → 3,653 (088980 제거), KRX 교차 후 2,538 → 2,537. 블랙리스트 1건 반영(423310 은 DART corpCode.xml 미등재이거나 KRX 상장 리스트 외로 이미 제거된 상태로 추정).
- **3년 백필 완료** — Bash id `bh6enx6xu`, 총 **752영업일 · 성공 752 · 실패 0 · 소요 125분 38초**. DB 최종 상태: `stock_price` 2,130,316 rows × 752 days (2023-06-01~2026-04-17), `short_selling` 718,997 rows × 752 days, `lending_balance` 668,322 rows × 699 days(공휴일/스키마 이슈 53일 제외), `distinct stock` 3,098 (현재 상장 2,879 + 과거 상장/폐지 219).
- **`lending_balance` 스키마 불일치 범위 축소 관찰** — α 에서 2026-04-17 은 0건이었지만 과거 날짜(2023-11~)는 952건 정상. 즉 pykrx 의 schema drift 가 최근 날짜에 국한되어 과거 시계열에는 영향 없음. carry-over 범위 대폭 축소.

---

## [2026-04-19 — 오후] α 부분 성공 + KRX 어댑터 버그 2건 긴급 수정 (`bb8d2f2`)

α(KRX 실데이터 배치 실행 → stock 마스터 복구) 시도 중 pykrx 1.2.x 와 어댑터 간 스키마 드리프트 2건을 발견·수정. 배치 재실행으로 KOSPI+KOSDAQ stock 마스터 2,879건과 2026-04-17 주가를 실데이터로 적재. 단 `get_market_ohlcv_by_ticker(market=ALL)` 이 종목명·시장구분을 반환하지 않아 2,874건의 `stock_name` 이 공백·`market_type` 이 단일 'KOSPI' 로 저장되는 잔여 이슈 발생(carry-over i). β 재실행으로 5 핵심 종목 이름만 긴급 복구해 UI 회귀는 차단.

### Fixed
- **pykrx 1.2.x 시가총액 컬럼 충돌**(`bb8d2f2`): `fetch_stock_prices` 에서 `get_market_ohlcv_by_ticker` 가 이미 `시가총액` 컬럼을 반환하는 상황에서 `get_market_cap_by_ticker` 결과를 무조건 join 해 `pandas.merge` 가 `ValueError: columns overlap` 으로 실패. `ohlcv.columns` 에 `시가총액` 이 있으면 cap 조회 자체를 건너뛰도록 조건부 분기. HANDOFF carry-over "KRX pykrx 스키마 불일치" 의 일부.
- **KOSDAQ 누락**(`bb8d2f2`): `get_market_ohlcv_by_ticker` 의 `market` 기본값 `"KOSPI"` 때문에 KOSDAQ/KONEX 가 통째로 빠져 `stocks_upserted` 가 949(KOSPI만)에 머물렀음. `market="ALL"` 명시로 2,879건으로 확대.

### Verified (실측)
- **배치 재실행 결과**: `POST /api/batch/collect?date=2026-04-17` HTTP 200. `stocks_upserted=2879 · stock_prices_upserted=2879 · short_selling_upserted=949 · lending_balance_upserted=0 · elapsed_ms=5302`.
- **5 핵심 종목 이름 복구**: β 재실행으로 005930/000660/035420/035720/068270 의 `stock_name` 복구 확인. 나머지 2,874건은 공백 유지.
- **신규 테스트 1건**: inline `시가총액` 케이스에서 `get_market_cap_by_ticker` 호출 0회 확인. KRX 테스트 4 → 5로 확장.

### Known Issues (carry-over)
- **i. stock_name·market_type 대량 누락** — `get_market_ohlcv_by_ticker(market=ALL)` 이 DataFrame 에 종목명/시장구분을 포함하지 않음. `get_market_ticker_list(market=KOSPI|KOSDAQ)` 로 시장별 티커 집합을 얻어 market_type 을 매핑하고, `get_market_ticker_name(ticker)` 루프 또는 batch API 로 이름을 병합해야 한다. 2,874건 영향. 별도 작업으로 이관.

---

## [2026-04-19 — 낮] Z(E 실측) + β(UI 시드) 병렬 수행 — UI 파생 지표 복구 (`a494863`)

직전 커밋에서 구현한 E(KRX 교차 필터)의 실측과, 데이터 부재로 `—` 를 표시하던 포트폴리오 UI 의 수익률/MDD 카드를 복구하기 위한 데모 시드를 병렬로 처리. backend 재빌드 → Z 실측 → β 스크립트 구현 → DB 적재 → 브라우저 확인까지 한 트랙에서 완결.

### Added
- **`scripts/seed_ui_demo.py`**(`a494863`): UI 회귀 검증 전용 CLI. 5개 대표 종목(삼성전자/SK하이닉스/NAVER/카카오/셀트리온) × 최대 90 영업일 OHLCV 를 결정론적 random-walk(seed 고정)로 생성해 `stock_price` 에 upsert. 활성 계좌 × 날짜별 `portfolio_snapshot` 을 현재 보유수량 × 해당일 종가로 재구성. `--wipe` 는 stock 마스터를 건드리지 않고 기간 내 시세/스냅샷만 정리(portfolio_holding 참조 관계 보존).
- **신규 테스트 10건**: `business_days_back` 주말 제외/순서/개수, `generate_price_series` 결정론/시드별 차이/OHLC 불변식/충분한 변동폭, `DEMO_STOCKS` 유효성 등.

### Verified (실측)
- **Z: KRX 교차 필터 실환경 동작** — `scripts.sync_dart_corp_mapping --dry-run` 결과 DART 3,654 → KRX 교집합 **2,538건**(1,116건 축소). pykrx 로그인 성공 로그 확인 (`KRX 로그인 ID: withwooyong` · 만료 1시간).
- **β: 시드 적재 및 UI 복구** — `stock 5 · stock_price 450 · portfolio_snapshot 90` 적재. `https://localhost/portfolio` 에서 누적 수익률(3M) = **+5.31%** (빨강, 한국 관습), MDD(3M) = **-10.23%** (파랑) 정상 렌더링. UI 의 파생 지표 경로(Metric 카드·색상 코딩·포맷팅) 전부 동작 확인.

### Observed (차후 개선)
- **`.env.prod` KRX 크리덴셜 이미 존재** — Z 실측 중 드러남. α 작업이 사실상 즉시 실행 가능 상태이며 stock 마스터를 실데이터로 복구 가능.
- **DART 단축명 매칭 누락** — 필터 패턴 `"인프라투융자회사"` 가 DART 가 저장한 단축명 `"맥쿼리인프라"` 와 매칭 실패. 해당 종목(088980)이 그대로 통과. 패턴에 단축명 추가 필요.
- **wipe 가 stock 마스터 보존해야 하는 제약** — `portfolio_holding.stock_id` FK 때문에 stock 선삭제 불가. 시드 스크립트는 기간 내 `stock_price`/`portfolio_snapshot` 만 정리하고 stock 은 upsert 경로로 덮도록 설계.

---

## [2026-04-19 — 오전] P13-3 AI 리포트 rate limiting + P13-4 KRX 교차 필터 + DB 벌크 upsert 실행 + UI 실측 (`3e44ab6` … `e6d79e6`)

바로 전 세션에서 구현한 P13-1/P13-2 의 실측 검증을 마무리한 뒤, 동일 세션 내에서 **(A) DART 벌크 sync 본실행 → (B) AI 리포트 엔드포인트 slowapi rate limiting → (D) 포트폴리오 UI 실측 → (E) KRX 현재 상장 교차 필터** 4건을 순차·병렬 처리. DB 에 실데이터 3,654건 적재, 백엔드 테스트 131→135건으로 확장.

### Added
- **slowapi rate limiting**(`3e44ab6`): `POST /api/reports/{stock_code}` 에 관리자 키 단위 쿼터(기본 30/min). `app/adapter/web/_rate_limit.py` 의 Limiter 싱글톤은 `X-API-Key` 우선, 부재 시 remote IP fallback. `RateLimitExceeded` → 429 + `Retry-After: 60` 헤더. 설정값 `AI_REPORT_RATE_LIMIT` 로 env override.
- **KRX 현재 상장 교차 필터**(`e6d79e6`): `scripts/sync_dart_corp_mapping.py` 에 `fetch_krx_listed_codes()` 추가 — pykrx 로 KOSPI+KOSDAQ 조회 후 DART 결과와 교집합. `--no-cross-filter-krx` 로 비활성화 가능. pykrx 실패 시 빈 집합 반환 + stderr 경고로 fallback.
- **테스트 5건**: rate limit(1) + KRX 교차·fallback·pykrx 성공·실패(4).

### Verified (실측)
- **A: DART 벌크 sync 본실행** — `docker compose exec backend python -m scripts.sync_dart_corp_mapping` 로 3,654건 upsert 완료. 주요 종목 005930/000660/035420 매핑 확인. 배치 500건 단위 8회 반복, 총 소요 ~30초.
- **D: 포트폴리오 UI** — `https://localhost/portfolio` 접속 → 계좌 탭(`e2e-manual`/`e2e-kis`) 렌더링 · 삼성전자 10주 보유 테이블 정확 · AI 리포트 버튼 동작 → `/reports/005930` 캐시 본문 렌더링 확인. 단 수익률/MDD 카드는 `—` (stock 마스터 0 rows + 주가 시계열 없음 — KRX 익명 차단 carry-over 파급).

### Observed (차후 개선)
- **UI 실측의 데이터 의존 한계** — 라우팅/컴포넌트/상태 층은 UI 만으로 검증 가능하지만, 파생 지표(수익률, MDD, 시그널 정합도, 백테스트)는 stock_price 시계열 필요. 근본 원인은 KRX 익명 차단 2026-04 전면화. 해결 경로: α) KRX 회원 크리덴셜, β) 수동 시드, γ) KIS REST 주가 조회 전환.
- **slowapi 메모리 스토리지** — 단일 uvicorn 프로세스 전제. multi-worker 확장 시 Redis 백엔드 전환 필요.
- **상장폐지 종목 3,654건 혼재** — E 구현으로 해소 가능. 다음 sync 실행 시 KRX 상장 ~2,500건 수준으로 축소 예상(실측은 차기 과제).

---

## [2026-04-18 — 새벽] P13-1 DART 벌크 sync 스크립트 + P13-2 운영 보안 M1~M4 + 실측 검증 (`43f07fd` … `1c27c65`)

수동 시드 3건에 머물던 `dart_corp_mapping` 을 전체 bulk sync 할 수 있는 CLI 스크립트를 구현하고, 이전 세션에서 carry-over 된 운영 보안 4건(M1 /metrics IP 게이팅 · M2 /health 마스킹 · M3 uv digest 고정 · M4 nologin 셸)을 일괄 처리. backend 재빌드 + Caddy reload 후 실 환경에서 **DART API 호출**과 **외부/내부 경로 차단 동작**을 실측 검증 완료.

### Added
- **`DartClient.fetch_corp_code_zip()`**(`43f07fd`): DART `/api/corpCode.xml` ZIP 바이너리 다운로드. `PK\x03\x04` 매직으로 성공 분기, JSON 바디는 `DartUpstreamError` 승격. 읽기 타임아웃 60초(수 MB 전송 고려), tenacity 3회 재시도.
- **`scripts/sync_dart_corp_mapping.py`**(`43f07fd`): CLI 진입점. `--dry-run` / `--batch-size` 옵션. 필터 2단: ① 종목코드 6자리 + 끝자리 `0` (보통주) ② 이름에 스팩·기업인수목적·리츠·부동산투자회사·인프라투융자회사·ETF·ETN·상장지수 미포함. 500건 배치 upsert.
- **`/internal/info` 엔드포인트**(`1c27c65`): app/env 상세 응답. Caddy 에서 `/internal/*` 차단하므로 Docker 네트워크 내부에서만 접근.
- **신규 테스트 31건**(`43f07fd`): 필터 파라미터라이즈 (보통주/우선주/스팩/리츠/ETF 경계값) + ZIP/XML 파싱 + `fetch_corp_code_zip` httpx.MockTransport 3종.

### Changed
- **`/health` 응답 본문 마스킹**(`1c27c65`): `{"status":"UP","app":...,"env":...}` → `{"status":"UP"}` 만. 운영 메타는 `/internal/info` 로 이동.
- **Caddy `/metrics`, `/internal/*` 외부 404**(`1c27c65`): `@blocked` matcher + `handle` 블록. frontend 프록시 경로와 무관하게 defense-in-depth.
- **uv 이미지 digest 고정**(`1c27c65`): `ghcr.io/astral-sh/uv:0.11` → `@sha256:240fb85a…516a` (multi-arch index). 공급망 공격 방어. 업그레이드 절차 주석 명시.
- **appuser 로그인 셸**(`1c27c65`): `/bin/bash` → `/usr/sbin/nologin`. login/su/sshd 경로 차단.

### Verified (실측)
- **E: DART 벌크 sync `--dry-run`** — 실 API 호출 성공. ZIP 3.5 MB · 전체 116,503 법인 → stock_code 보유 3,959건 → 필터 통과 **3,654건**. 샘플 10건 출력에서 과거 상장폐지 종목이 다수 혼재 확인(예상보다 많은 이유: corpCode.xml 이 폐지 이력도 유지).
- **F-1/F-2: 외부 차단** — `curl -k https://localhost/metrics` → HTTP 404 · `/internal/info` → HTTP 404. Caddy `@blocked` matcher 동작 확인.
- **F-3: 내부 응답 분리** — 컨테이너 내부에서 `/health` = `{"status":"UP"}`, `/internal/info` = `{"status":"UP","app":"ted-signal-backend","env":"prod"}` 정상.
- **F-4: nologin 적용 범위** — `/etc/passwd` 에 `/usr/sbin/nologin` 확인. `docker exec backend /bin/bash` 는 여전히 실행됨(설계 범위 밖 — nologin 은 login/su/sshd 경로 차단 전용). MVP 단계 적정.

### Observed (차후 개선)
- **Docker Desktop bind mount 휘발성** — 에디터의 rename-on-save 로 inode 가 바뀌면 컨테이너 mount 가 stale. Caddy reload 전에 **컨테이너 재시작 필수**(`docker compose restart caddy`). Caddyfile 수정 절차에 반영 필요.
- **상장폐지 종목 혼재** — `dart_corp_mapping` 에 과거 폐지 종목도 포함. AI 리포트 대상은 실제 호출자가 현재 상장 종목만 쿼리하므로 실사용 영향 없음. 필요 시 KRX 현재 상장 리스트와 교차 필터 추가 가능.

---

## [2026-04-18 — 심야] 실 E2E 검증 + 3건의 크리티컬/MEDIUM 버그 수정 (`2febdf2` … `510fa1c`)

`.env.prod` 의 실 DART/OpenAI/KIS 모의 키로 `docker compose --env-file .env.prod up -d --build` 풀 재빌드 후 엔드투엔드 검증. 포트폴리오 계좌 생성 → 수동 거래 → KIS 모의 동기화(OAuth+VTTC8434R) → **삼성전자 AI 리포트 실생성 (gpt-4o, 6.3초, 18524/530 토큰, DART 공시 5건 자동 소스 보강)** 까지 풀 체인 성공. 2차 호출 `cache_hit=true` 0.02초. 검증 과정에서 발견한 3건의 실버그를 같은 세션에 수정·검증 완료.

### Fixed
- **CRITICAL: entrypoint.py 레거시 경로가 003/004/005 누락**(`2febdf2`): `alembic_version` 없고 `stock` 있는 레거시 Java Flyway DB 에서 `stamp head` 만 실행 → P10~P13b 의 portfolio_* / dart_corp_mapping / analysis_report 5 테이블이 생성되지 않음. 수정: `stamp 002_notification_preference` (V1+V2 완료 마킹) → `upgrade head` (003/004/005 적용). Phase 7 E2E 테스트(testcontainers fresh DB) 가 stamp 경로를 타지 않아 놓친 사각지대. runbook §2.4 동시 갱신.
- **MEDIUM: `scripts/validate_env.py` KIS 계좌번호 기준 느슨**(`2febdf2`): `acct_digits >= 8` → 8자리도 PASS. 어댑터 실요구는 CANO(8) + ACNT_PRDT_CD(2) = `== 10`. 거짓 음성 버그. 수정: `== 10` 으로 정확히 + 미달/초과별 안내 메시지.
- **CRITICAL: REPORT_JSON_SCHEMA sources.items 의 required 에 `published_at` 누락**(`510fa1c`): OpenAI strict mode 는 `required` 배열에 **모든** properties 키가 포함되어야 함. `/chat/completions` 가 HTTP 400 "Missing 'published_at'" 으로 거부해 리포트 생성 실패. 수정: required 에 published_at 추가 (type: [string, null] 로 이미 nullable 선언).

### Known Outcomes (E2E 검증 통과)
- 관리자 릴레이: `POST /api/admin/portfolio/accounts` 201 (Caddy HTTPS + Next.js Route Handler + backend 경로 전체 동작)
- 포트폴리오 거래 등록: 매수 10주@72000 → `GET /holdings` 200 (평단·수량 정확)
- KIS 모의 동기화: OAuth client_credentials 토큰 발급 → VTTC8434R 잔고 조회 rt_cd=0 → `fetched_count=0` (모의 잔고 없음, 정상 응답)
- AI 리포트 실생성: gpt-4o 모델 · 6.3초 · 토큰 18,524↓/530↑ · opinion=HOLD · sources 7건 전부 Tier1 (DART 공시 5 + 공식 홈페이지) · 자동 소스 보강 검증 · 24h 캐시 2차 호출 0.02s
- 레거시 DB 위에서 entrypoint 자동 마이그레이션 003/004/005 적용 확인

---

## [2026-04-18 — 저녁~밤] Phase 8/9 마무리 + §11 신규 도메인(P10~P15) + 프론트 UI + 리뷰 대응 (`24b43ba` … `7f4f3d1`)

이전 세션에서 Phase 1~7 으로 Java→Python 런타임 이전을 마친 데 이어, 본 세션은 **Phase 8/9 정리 + §11 (포트폴리오·AI 분석 리포트) 신규 도메인 전체 + 프론트 UI + 코드 리뷰 대응** 을 단일 세션에 완결. 커밋 12개 · 약 +7,120 / -5,141 라인 (Java 삭제 4,710 포함) · 백엔드 98/98 PASS · mypy strict 0 · ruff 0 · 프론트 build/tsc/lint clean.

### Removed
- **Phase 8 — Java 스택 물리 제거**(`24b43ba`): `src/backend/` 디렉토리 전량 삭제 (Spring Boot 3.5 + Java 21 + Gradle + 테스트 69개 포함 4,710 라인). 2026-04 Java→Python big-bang 이전 완결. Python 52/52 PASS 로 대체 검증 완료.

### Added
- **Phase 9 — 기술스택 문서/에이전트 Python 전환**(`005011e`): `CLAUDE.md` Tech Stack 표 + Backend Conventions(PEP 8·ruff·mypy strict·Pydantic v2·SQLAlchemy 2.0 async·APScheduler) + Key Design Decisions 전면 재작성. `docs/design/ai-agent-team-master.md` 기술 스택 확정 표 FastAPI/Python 전환 + Part V(부록 I~L, Java 21 Virtual Threads/JPA/QueryDSL) **역사적 기록·비활성** 배너 부착. `agents/08-backend/AGENT.md` 전면 재작성. `pipeline/artifacts/10-deploy-log/runbook.md` 내부 포트 8080→8000, /actuator/health→/health, Flyway→Alembic + entrypoint, KRX_AUTH_KEY→KRX_ID/KRX_PW 등 갱신.
- **P10 — 포트폴리오 도메인**(`97203c2`, +1,439): Alembic 003 (brokerage_account/portfolio_holding/portfolio_transaction/portfolio_snapshot 4 테이블 + UNIQUE/CHECK/인덱스). 모델 4종 + Repository 4종 + UseCase 4종 (RegisterAccount/RecordTransaction(가중평균 평단가)/ComputeSnapshot/ComputePerformance — pandas cummax/pct_change 벡터 연산으로 MDD·Sharpe). FastAPI 라우터 7 엔드포인트. 테스트 11 케이스.
- **P11 — KIS 모의투자 REST 연동**(`c003fc8`, +774): `KisClient` (httpx + OAuth2 `client_credentials` 토큰 캐시·300초 전 자동 재발급, TR_ID VTTC8434R 모의 전용, 실거래 URL 진입 차단, tenacity 재시도). `SyncPortfolioFromKisUseCase` — connection_type='kis_rest_mock' + environment='mock' 이중 검증, 잔고→holding 직접 upsert. Settings 에 KIS_APP_KEY_MOCK/SECRET/ACCOUNT + base_url 하드코드. 테스트 9 케이스.
- **P12 — 포트폴리오↔시그널 정합도 리포트**(`11e80c2`, +343): `SignalRepository.list_by_stocks_between` — IN + 기간 + min_score 복합 쿼리로 N+1 회피. `SignalAlignmentUseCase` — 종목별 max_score·hit_count 집계·정렬. `GET /api/portfolio/accounts/{id}/signal-alignment` 라우터. 테스트 5 케이스.
- **P13a — DART OpenAPI Tier1 어댑터**(`b2c20f4`, +711): Alembic 004 (`dart_corp_mapping` — KRX 6자리↔DART 8자리 매핑). `DartClient` — fetch_company/fetch_disclosures/fetch_financial_summary 3 엔드포인트, status='000'|'013' 만 통과 (그 외 `DartUpstreamError` 승격), 괄호 표기 음수·천단위 쉼표 Decimal 안전 변환, populate_existing upsert 패턴. 테스트 9 케이스.
- **P13b — AI 분석 리포트 파이프라인**(`caf8355`, +1,484): Alembic 005 (`analysis_report` JSONB content/sources, (stock_code, report_date) UNIQUE 로 24h 캐시). `LLMProvider` Protocol (`app/application/port/out/llm_provider.py`) + Tier1/Tier2 dataclass + REPORT_JSON_SCHEMA strict JSON. `OpenAIProvider` (Plan B, httpx `/v1/chat/completions` + `response_format=json_schema`, 역할 분리 시스템 프롬프트 "숫자는 Tier1 만, 정성은 Tier2 만 인용"). `AnalysisReportService` — 24h 캐시 조회 → dart_corp_mapping 해결 → DART 3종(company/disclosures 90d/financials 전년 CFS) + KRX 가격·시그널 Tier1 수집 → provider.analyze → 자동 소스 보강(공식 홈페이지 + 최근 공시 3건) → upsert. `POST /api/reports/{stock_code}` 라우터 (Admin Key 보호, force_refresh 쿼리, 404/400/502 매핑). 테스트 9 케이스.
- **P14 — 프론트 포트폴리오·AI 리포트 UI**(`3cd5c75`, +1,349): Next.js 16 + React 19. `/portfolio` (계좌 스위처 + 4 지표 카드 + 스냅샷/KIS 동기화 액션 + 보유 테이블 + AI 리포트 바로가기), `/portfolio/[accountId]/alignment` (시그널 정합도 상세, 스코어 슬라이더 필터), `/reports/[stockCode]` (AI 리포트 본문 — BUY/HOLD/SELL 컬러 뱃지, 강점/리스크 2열, 출처 Tier1/2 뱃지 + 외부 링크, 재생성 버튼). 제네릭 Route Handler `/api/admin/[...path]` (GET/POST/PUT/DELETE/PATCH, ADMIN_API_KEY 서버 측 부착, 64KB 본문 상한). API 클라이언트 2 (portfolio/reports) + 타입 2 (portfolio/report, snake_case 백엔드 정렬). NavHeader 에 '포트폴리오' 메뉴 추가.
- **P15 — 키움 REST 가용성 조사**(`7f4f3d1`, +177): `docs/research/kiwoom-rest-feasibility.md` — 문서 스파이크 전용 (구현 없음). 2026-04 공식 도메인 `openapi.kiwoom.com`, 모의 `mockapi.kiwoom.com`, Python SDK `kiwoom-rest-api` 0.1.12 미성숙 확인. KIS vs 키움 11항목 비교 매트릭스. **결론: No-Go**. Go 조건 3/3 (개인 키움 계좌 수요 + SDK 0.2+ 성숙 + KIS 어댑터 계약 고정) 충족 시 재평가. 플랜 §11.1 의 `developers.kiwoom.com` 오기 정정.

### Fixed
- **P13b 리뷰 fix**(`185dfaf`): mypy strict HIGH 5 (cast dict[str, Any], list[ReportSource] 제네릭, -> ReportSource 반환 타입) + 보안 MEDIUM 4 (`is_safe_public_url` 유틸로 javascript:/ftp:/file: 스킴 차단, OpenAI 에러 본문 외부 누설 제거 — body 는 logger.warning 만, `openai_base_url` HTTPS 스킴 강제로 SSRF 차단, `<tier1_data>`/`<tier2_data>` XML-like fence 로 프롬프트 인젝션 완화). 테스트 3 케이스 추가.
- **P14 리뷰 fix**(`c008592`): HIGH 3 (릴레이 path 세그먼트 `^[A-Za-z0-9_\-.]+$` allowlist + `.`/`..` 명시 거부 — undici collapse 로 /api/ 스코프 탈출 SSRF 차단, reports 페이지 `cancelled` 플래그 + `refreshTick` idempotent 재생성 패턴으로 race 제거, `SourceRow` `safeHref` 로 javascript: URI 브라우저 실행 차단) + MEDIUM 4 (refreshCurrent 에러 투명 전파, `aria-label` 새 탭 안내, `ADMIN_BASE`/adminCall 공용 헬퍼 추출, accountId NaN 가드).

### Changed
- **cleanup: mypy strict 0 · ruff 0 · frontend 타입 스키마 정합**(`51bfe10`, +332/-232): 백엔드 mypy 23→0, ruff 17→0. `pandas-stubs`/`types-python-dateutil` dev deps. StrEnum 4종 전환. Repository 공용 `rowcount_of()` 헬퍼. 외부 클라이언트 forward-ref 따옴표 제거(UP037). KIS/DART Any 반환 isinstance/cast 좁히기. market_data_job 파라미터 full 타입 힌트. 프론트 `signal.ts`/`SignalCard`/`page.tsx`/`stocks/[code]/page.tsx`/`backtest/page.tsx` snake_case 백엔드 응답과 정렬, `SignalDetail` + `detailNumber()` JSONB 안전 접근, `StockDetail` 가짜 `latestPrice/timeSeries` 구조 → 실제 `stock{}/prices[]` 로 정정, CountUp `queueMicrotask` 로 React 19 린트 해소.

### Known Issues / Follow-up
- `POST /api/reports/{stock_code}?force_refresh=true` 에 rate limiting 없음 — 관리자 키만으로 LLM 호출 폭주 가능. `slowapi` 도입 권고 (리뷰 LOW).
- 실 E2E 검증 미완: `.env.prod` 의 실 DART/OpenAI/KIS 키로 브라우저에서 `/portfolio` → AI 리포트 생성까지 1회 검증 필요.

---

## [2026-04-18 — 오후~저녁] Java→Python 전면 이전 Phase 1~7 일괄 완료 (`c417977` … `610918a`)

본 세션의 주제: **Spring Boot 3.5 + Java 21** 백엔드를 **FastAPI + Python 3.12** 로 전면 이전.
사전-운영 단계라는 결정적 이점으로 big-bang 재작성 경로를 선택. 18 영업일 추정 중 ~7일 분량을 진행.
전체 52/52 PASS · 로컬 Docker 스모크 확인 · 커밋 13회 · 약 7,400+ 라인 신규.

### Added
- **작업계획서 확정**(`f66cfdd`): `docs/migration/java-to-python-plan.md` — 9 결정 잠금, §11 포트폴리오 + AI 분석 스코프, Perplexity+Claude Plan A / OpenAI GPT-5.4 단독 Plan B 구분, DART+KRX+ECOS Tier1 / web_search 화이트리스트 Tier2 신뢰 출처 3-Tier 설계. 루트 `.env.prod.example` DOMAIN/ACME_EMAIL/DART/OPENAI/KIS 변수 확장.
- **환경변수 검증 스크립트**(`cb5bd24`): `scripts/validate_env.py` — `.env.prod` 의 DART/OpenAI/KIS 키를 API 실호출로 검증. 키 값 절대 로그에 노출되지 않도록 pykrx 내부 print 까지 `contextlib.redirect` 로 차폐.
- **KRX 계정 유효성 검증 스크립트**(`127625d`): `scripts/validate_krx.py` — pykrx 로그인 + OHLCV·공매도·대차잔고 수신 실측.
- **픽스처 베이스**(`cb5bd24`): `pipeline/artifacts/fixtures/` — `capture_krx.py` + 합성 JSON 3종 + Telegram 모의본 + KRX 익명 차단 블로커 문서.
- **Phase 1 Python 백엔드 스캐폴딩**(`e669fed`): `src/backend_py/` Hexagonal 구조, uv + FastAPI + pydantic-settings + prometheus-fastapi-instrumentator + structlog + pytest + ruff + mypy strict, Dockerfile (python:3.12-slim 멀티스테이지 + 비루트 uid 1001). Health/CORS 테스트 6종.
- **Phase 2 DB 계층**(`f00b2cf`): SQLAlchemy 2.0 async + asyncpg(런타임) + psycopg2(마이그레이션), Alembic V1/V2 리비전 이식, 모델 7종(Stock/StockPrice/ShortSelling/LendingBalance/Signal/BacktestResult/NotificationPreference) + Repository 7종, testcontainers PG16 통합 테스트 7종, macOS Docker Desktop 소켓 자동 감지.
- **Phase 3 외부 어댑터**(`e9f3c75`): `KrxClient` (pykrx async 래퍼 + asyncio.Lock + 2초 rate limit + stdout 차폐 + tenacity 재시도), `TelegramClient` (httpx AsyncClient + HTML parse_mode + no-op fallback). 어댑터 테스트 8종.
- **Phase 4 UseCase/서비스**(`3724d1e`): `MarketDataCollectionService`, `SignalDetectionService` (pandas rolling MA 벡터화), `BacktestEngineService` (피벗 테이블 + shift(-N) 벡터 리라이트 — Java TreeMap 순회를 행렬 1회 연산으로 대체), `NotificationService`. Port Protocol 정의. pandas/numpy/vectorbt 의존성 추가. 서비스 통합 테스트 5종.
- **Phase 5 API 계층**(`31ea518`): `app/adapter/web/` — FastAPI 라우터 8개(GET `/api/signals`, GET `/api/stocks/{code}`, POST `/api/signals/detect`, GET·POST `/api/backtest`, GET·PUT `/api/notifications/preferences`, POST `/api/batch/collect`), Admin API Key `hmac.compare_digest` timing-safe 검증, RequestValidationError → 400 통일 응답. 라우터 통합 테스트 14종.
- **Phase 6 배치**(`65b4bb6`): `app/batch/trading_day.py` (주말 제외), `market_data_job.py` (3-Step 오케스트레이션 — collect → detect → notify, 각 Step 독립 세션·트랜잭션), `scheduler.py` (AsyncIOScheduler CronTrigger mon-fri KST 06:00, max_instances=1, coalesce=True), FastAPI lifespan 연동. 배치 테스트 7종.
- **Phase 7 컨테이너 전환**(`b5e3cc8`): `scripts/entrypoint.py` — alembic_version/stock 테이블 존재 여부로 `stamp head` vs `upgrade head` 분기 후 `os.execvp` 로 uvicorn 전환(PID 1 유지). E2E 플로우 테스트 2종(`/api/batch/collect` → `/api/signals/detect` → GET `/api/signals` 체인).

### Changed
- **운영 설정 소소한 정리**(`c417977`): `ops/caddy/Caddyfile` X-Forwarded-* header_up 중복 제거, `docker-compose.prod.yml` Caddy 헬스체크 `localhost:2019/config/` 로 단순화, `src/backend/src/main/resources/application.yml` management.endpoint.health.show-details 및 management.prometheus.* 중복 설정 제거.
- **docker-compose.prod.yml Python 전환**(`b5e3cc8`): backend 서비스 build context `./src/backend` → `./src/backend_py`, 환경변수 Spring 계열 제거 + DATABASE_URL(asyncpg DSN) / KRX_ID/KRX_PW / DART/OPENAI/KIS / SCHEDULER_ENABLED=true 추가, healthcheck `/actuator/health` → `/health` 전환(curl 대신 python urllib), frontend BACKEND_INTERNAL_URL 포트 8080→8000, db initdb Java migration mount 제거(Alembic 전담), Caddyfile 주석 포트 8080→8000.
- **CORS 보안 설계**(`e669fed` 이후 유지): 빈 화이트리스트면 미들웨어 미탑재, `"*"` + credentials 조합 코드상 차단.
- **NotificationPreferenceRepository**(`31ea518`): `save()` 이후 `session.refresh()` 로 server_default `updated_at` 동기화 — Pydantic model_validate 중 MissingGreenlet 회피.
- **app/adapter/in/web/** → **app/adapter/web/**(`31ea518`): Python 예약어 `in` 때문에 `from app.adapter.in.web...` 파싱 실패 → 경로 평탄화.

### Fixed
- **코드 리뷰 H1·M1·M4 (Phase 4 후)**(`bda6e42`): NotificationService N+1 쿼리 제거(`StockRepository.list_by_ids` IN 쿼리 1회), SignalDetectionService `_trend_reversal` 의 `is None` 죽은 조건 제거(pd.isna 일원화), Telegram 메시지에 `html.escape` 적용 + 영문 enum → 한글 라벨("대차잔고 급감"/"추세전환"/"숏스퀴즈"). 회귀 테스트 3종 추가.
- **코드 리뷰 M1·M2·M3 (Phase 7 후)**(`610918a`): entrypoint uvicorn `--forwarded-allow-ips "*"` → Docker 사설 대역(127.0.0.1,10/8,172.16/12,192.168/16), `FORWARDED_ALLOW_IPS` env 로 오버라이드 가능. 스케줄러 `date.today()` → `datetime.now(KST).date()` 로 TZ 명시화. market_data_job 의 죽은 코드 `detected_signal_ids` 블록 삭제(DB 쿼리 1회 절감).

### Known Issues (Carry-over)
- **KRX 익명 접근 차단(2026-04 확인)**: `data.krx.co.kr` 가 익명 요청을 `HTTP 400 LOGOUT` 으로 거부. pykrx 도 `KRX_ID/KRX_PW` 요구로 전환 완료. 프로덕션 Java 배치가 수개월간 실제 데이터를 못 가져오고 있었음(DB 3개 테이블 0 rows 로 확인). 사용자가 회원가입 후 `.env.prod` 에 `KRX_ID/KRX_PW` 주입, `scripts/validate_krx.py` 로 OHLCV 2879종목 + 공매도 949종목 수신 확인. 대차잔고는 pykrx 스키마 불일치로 0 rows → Phase 3 어댑터에서 예외 격리 + fallback 경고 로그, 본격 복구는 후속 작업.
- **Phase 8/9 미완**: `src/backend/` Java 스택 물리 제거, `docs/design/ai-agent-team-master.md` 기술스택 표, `CLAUDE.md` Backend Conventions, `agents/08-backend/AGENT.md`, `pipeline/artifacts/10-deploy-log/runbook.md` 갱신이 남아 있음.

---

## [2026-04-18 — 새벽] 로컬 Docker Desktop 첫 배포 스모크 테스트 + runbook 정정 + MCP lockdown (`4a9d448`, `a89c6fe`)

### Added
- `.mcp.json` (신규): 빈 `mcpServers`로 프로젝트 스코프 MCP 기본값 잠금 — 외부 MCP 서버 주입 차단
- `docs/context-budget-report.md` (신규): `/context-budget --verbose` 산출물. 세션 오버헤드 ~24.4K tokens / 1M의 2.4% 집계, Top 1~5 절감안(~4.1K tokens / 17%) 제시

### Changed
- `.claude/settings.json`: `enabledMcpjsonServers: []` + `enableAllProjectMcpServers: false` — 프로젝트 레벨 MCP 자동활성화 차단 (보안 순기능)
- `pipeline/artifacts/10-deploy-log/runbook.md` §2.5 스모크 테스트:
  - test #0 신설: `.env.prod`에서 `ADMIN_API_KEY`를 현재 셸로 `export`하는 절차
  - test #4 GET 공개 읽기(`/api/notifications/preferences`, proxy.ts 경유)로 분리
  - test #5 PUT 쓰기(`/api/admin/notifications/preferences`, Route Handler)로 유효 payload 예시 명시
  - signalTypes 열거값(RAPID_DECLINE/TREND_REVERSAL/SHORT_SQUEEZE), minScore 범위(0~100) 힌트 추가
- `CHANGELOG.md` / `HANDOFF.md`: 세션 운영 현행화

### Fixed
- runbook §2.5 test #4: GET은 Route Handler에서 405 반환 — HTTP method 정정(GET → PUT). 로컬 Docker Desktop 스모크 테스트로 5/5 경로 HTTP 200 확인 후 반영

### Verified (not committed)
- 로컬 Docker Desktop 첫 배포 성공 — 3 컨테이너(db/backend/frontend) 전부 `healthy`
- 스모크 테스트 5종 전부 2xx
  - `GET /` → 200 (16KB SSR HTML)
  - backend `/actuator/health` → `{"status":"UP"}`
  - `GET /api/signals` → 200 (빈 배열, DB 초기 상태)
  - `GET /api/notifications/preferences` → 200 (공개, proxy.ts 경유)
  - `PUT /api/admin/notifications/preferences` → 200 (ADMIN_API_KEY 인증 통과, 값 수정→원복 확인)
- `.env.prod` 로컬 생성 (chmod 600, gitignore 확인) — POSTGRES_PASSWORD/ADMIN_API_KEY 랜덤 생성, Telegram/KRX 실값 주입

---

## [2026-04-17 — 저녁] 코드 리뷰 블로커(H-1) 수정 + Next.js 16 canonical proxy 적용 (`ef8c267`)

### Added
- `src/frontend/src/proxy.ts`: 런타임 `/api/*` → `BACKEND_INTERNAL_URL` 프록시 (Next.js 16 canonical, 구 middleware 대체). `/api/admin/*`는 Route Handler 우선 통과

### Changed
- `src/frontend/next.config.ts`: `rewrites()` 제거 — build time에 routes-manifest.json으로 고정되어 런타임 env 반영 불가. 주석으로 proxy.ts 선택 이유 명시
- `src/frontend/src/lib/api/client.ts`: `NEXT_PUBLIC_API_URL` → `NEXT_PUBLIC_API_BASE_URL` 정합, 기본값 `/api`
- `src/frontend/src/app/api/admin/notifications/preferences/route.ts`: `BACKEND_API_URL` → `BACKEND_INTERNAL_URL` 정합, `/api` path prefix 추가, 16KB body 상한(M-4)
- `src/backend/Dockerfile`: `./gradlew dependencies || true` → `./gradlew dependencies` (M-1, 의존성 해석 실패 은폐 제거)

### Fixed
- **[HIGH H-1]** compose / client.ts / route.ts 간 env 변수명 3중 불일치 — 프로덕션에서 브라우저→proxy→backend 경로가 끊어지는 블로커. `NEXT_PUBLIC_API_BASE_URL` + `BACKEND_INTERNAL_URL` 단일 네임스페이스로 통일

---

## [2026-04-17 — 오후] Phase 4 Verify + Phase 5 Ship + 프로토타입 효과 Next.js 이식 — v1.0 배포 준비 완료

### Added
- 프로토타입 효과 3종 Next.js 이식 (`871ff57`)
  - `src/frontend/src/components/ui/AuroraBackground.tsx`: 4-blob radial-gradient + drift keyframes, pure CSS, 서버 안전
  - `src/frontend/src/components/ui/CountUp.tsx`: rAF 기반 easeOutCubic 카운트업, `prefers-reduced-motion` 가드
  - `src/frontend/src/components/ui/Magnetic.tsx`: 커서 인력 버튼 래퍼, `coarse-pointer`/reduced-motion 가드
  - `src/frontend/src/app/globals.css`: `.aurora` + `@keyframes aurora-drift-1~4` + `.magnetic` 블록 추가
- Phase 4 Verify 산출물 3종 + Judge 평가 (`eb5fc15`)
  - `pipeline/artifacts/07-test-results/qa-report.md` (CONDITIONAL)
  - `pipeline/artifacts/08-review-report/review-report.md` (CONDITIONAL, CRITICAL 1 + HIGH 4)
  - `pipeline/artifacts/09-security-audit/audit-report.md` (CONDITIONAL, HIGH 1)
  - `pipeline/artifacts/07-test-results/verify-judge-evaluation.md` (7.6/10)
- Phase 5 Ship 인프라 (`764d6d3`)
  - `src/backend/Dockerfile` / `src/frontend/Dockerfile` (multi-stage, non-root, healthcheck)
  - `docker-compose.prod.yml` (3 서비스, 내부 네트워크, DB 미노출)
  - `.env.prod.example` + `.gitignore` 갱신
  - `.github/workflows/ci.yml` (backend-test + frontend-build + docker-build with GHA cache)
  - `pipeline/artifacts/10-deploy-log/runbook.md` (배포 / 롤백 / 백업 cron / AWS 5-step 이관)
  - `pipeline/artifacts/11-analytics/launch-report.md` (D+7 Top KPI 3종 + Week 1~4 모니터링)
  - `pipeline/artifacts/10-deploy-log/ship-judge-evaluation.md` (PASS 8.1/10)
- 백엔드 트랜잭션 리팩터
  - `src/backend/.../application/service/MarketDataPersistService.java`: `persistAll` 전담 빈 분리 — Spring AOP 자기호출 프록시 우회 문제 해결
- Admin API 서버 릴레이
  - `src/frontend/src/app/api/admin/notifications/preferences/route.ts`: Next.js Route Handler — 서버 측 `ADMIN_API_KEY`로 backend 프록시

### Changed
- `src/frontend/src/app/layout.tsx`: `<AuroraBackground>` 주입 + 본문 z-index:1 레이어링 + footer backdrop-blur
- `src/frontend/src/app/page.tsx`: metric 카드 값에 `CountUp`, 필터 버튼에 `Magnetic` 래핑, 카드 배경 `bg-[#131720]/85 backdrop-blur`로 전환
- `src/backend/.../MarketDataCollectionService.java`: `persistAll` 로직 제거, `MarketDataPersistService`에 위임
- `src/frontend/src/app/settings/page.tsx`: `NEXT_PUBLIC_ADMIN_API_KEY` 의존 제거, `updateNotificationPreferences(form)`로 간소화
- `src/frontend/src/lib/api/client.ts`: `updateNotificationPreferences` apiKey 인자 제거, `/api/admin/notifications/preferences` Route Handler 호출로 전환
- `pipeline/state/current-state.json`: `status: "deployed"`, `human_approvals #3 passed 7.6`, `ship_artifacts` + `post_ship_recommendations` 추가
- `docs/sprint-4-plan.md`: Phase 4/5 통과 반영

### Fixed
- **[CRITICAL B-C1]** `NEXT_PUBLIC_ADMIN_API_KEY` 브라우저 번들 노출 — Review+Security 공동 지목. Route Handler로 서버 전환, 관리자 API 4개(batch/collect, signals/detect, backtest/run, PUT preferences) 공개 상태 해소
- **[HIGH B-H1]** `MarketDataCollectionService.persistAll` 자기호출로 `@Transactional` 무효 — `MarketDataPersistService` 신규 빈으로 분리해 프록시 정상 적용
- **[HIGH B-H2]** `persistAll` 데드 코드 (`findByStockId(null, date, date)` 미사용 결과) 제거
- **[HIGH B-H3]** 배치 재실행 시 유니크 제약 충돌 — 일자별 기존 `stockId` 집합 1회 조회 후 INSERT skip, 건수 로깅으로 멱등성 확보

---

## [2026-04-17] Sprint 4 Task 4 — 알림 설정 페이지 (백엔드 + 프론트) + 프로토타입 합류본 확정 + 리뷰 반영

### Security / Review Fixes (HIGH 4 + MEDIUM 9)
- **HIGH-1**: `PUT /api/notifications/preferences`에 `X-API-Key` 인증 추가 — 공개 API에서 공격자의 알림 무력화 방지 (Security 리뷰)
- **HIGH-2**: `NotificationPreferenceService.loadOrCreate` race condition — `DataIntegrityViolationException` catch + 재조회 recover 패턴 적용 (Java 리뷰)
- **HIGH-3**: `GlobalExceptionHandler`에서 `IllegalArgumentException` 전역 캐치 제거 — JDK 내부 오류가 400으로 마스킹되던 문제 해소 (Java 리뷰)
- **HIGH-4**: Hexagonal 위반 수정 — `sanitizeSignalTypes` 검증 책임을 Controller에서 `UpdateCommand` compact constructor로 이동, `DomainException(DomainError.InvalidParameter)` 경로 사용 (Java 리뷰)
- **MEDIUM**: `@Size(min=1, max=3)` 제약 추가 (DoS 방지), 에러 메시지 사용자 입력 반사 제거(고정 문자열), `getPreferenceForFiltering`에 `@Transactional(readOnly=true)` 명시, 도메인 `update()` 자체 검증(minScore 범위, 빈 리스트), `sendBatchFailure` 로그에서 `errorMessage` 제거
- **MEDIUM (프론트)**: `aria-valuemin/max/now` 3줄 중복 제거(input[type=range] 자동 제공), `client.ts` `cache: 'no-store'` spread 후위 재명시(caller override 방어), 에러 메시지 직접 노출 → `friendlyError()` 매핑 함수로 status 기반 사용자 메시지 반환
- **테스트**: `NotificationApiIntegrationTest` 9개로 확장 (인증 2 + 업데이트 1 + 400 검증 5 + 기본값 1). 알 수 없는 타입이 응답에 반사되지 않는지 검증 포함
- **부수 개선**: `BacktestController`/`SignalDetectionController`/`BatchController`의 API Key 검증 로직 중복 제거 → 신규 `ApiKeyValidator` 컴포넌트로 추출

### Added
- `src/backend/.../domain/model/NotificationPreference.java`: 싱글 로우 엔티티(id=1 고정) — 4채널 플래그 + `minScore`(0-100) + `signalTypes` JSONB
- `src/backend/.../application/port/in/GetNotificationPreferenceUseCase`, `UpdateNotificationPreferenceUseCase`: 조회/업데이트 유스케이스 포트
- `src/backend/.../application/port/out/NotificationPreferenceRepository`: Spring Data JPA 리포지토리
- `src/backend/.../application/service/NotificationPreferenceService`: `loadOrCreate` 지연 생성 + `getPreferenceForFiltering` 기본값 fallback
- `src/backend/.../adapter/in/web/NotificationPreferenceController`: `GET/PUT /api/notifications/preferences` + Bean Validation(`@Min/@Max/@NotNull`)
- `src/backend/src/main/resources/db/migration/V2__notification_preference.sql`: 테이블 DDL + 기본 row INSERT (Flyway 도입 시 바로 적용 가능, 현재는 참고용)
- `src/backend/src/test/.../NotificationApiIntegrationTest`: 5개 통합 테스트 (기본값 생성 / 전체 업데이트 / minScore 범위 / 알 수 없는 타입 / 필수 필드 누락)
- `src/frontend/src/types/notification.ts`: `NotificationPreference` 타입 + 채널 라벨 상수
- `src/frontend/src/app/settings/page.tsx`: 4개 토글(switch role) + 3개 시그널타입 필터(aria-pressed) + minScore 슬라이더 + 저장 버튼 + 토스트

### Changed
- `src/backend/.../application/service/TelegramNotificationService`: 4개 시나리오 전부 preference 필터 반영
  - `sendDailySummary`: toggle + signalTypes + minScore 삼중 필터
  - `sendUrgentAlerts`: toggle + signalTypes (A등급 자체가 minScore 상회)
  - `sendBatchFailure`, `sendWeeklyReport`: toggle
- `src/backend/.../adapter/in/web/GlobalExceptionHandler`: `@Valid @RequestBody` 검증 실패를 400으로 변환 — `MethodArgumentNotValidException` + `HttpMessageNotReadableException` + `IllegalArgumentException` 핸들러 신규
- `src/frontend/src/lib/api/client.ts`: `fetchApi`에 `RequestInit` 옵션 추가, `getNotificationPreferences` + `updateNotificationPreferences` 노출
- `src/frontend/src/components/NavHeader.tsx`: `/settings` 링크 추가

### Decision
- **D-4.11 알림 설정 = 싱글 로우 패턴**: id=1 고정, 4개 채널 플래그 + minScore + signalTypes JSONB. 사용자/인증 도입 시 user_id FK로 확장 가능
- **D-4.10 프로토타입 합류본 = ambient**: `prototype/index-ambient.html`(1332줄, aurora + skeleton + tilt + magnetic + count-up 누적)을 최종 합류본으로 확정 → `prototype/index.html`에 복사

### Testing
- 백엔드: JUnit 5 + Testcontainers 25개 전체 통과 (기존 20 + 신규 5)
- 프론트: `tsc --noEmit` + `eslint` + `next build` 전부 clean — `/settings` 라우트 정적 생성 확인

---

## [2026-04-17] Sprint 4 Task 5-6 — 프론트엔드 반응형 + ErrorBoundary + 글로벌 네비 + 접근성

### Added
- `src/frontend/src/components/NavHeader.tsx`: 글로벌 네비게이션 — sticky + 햄버거 + ESC + `aria-current` + render-time 리셋 패턴 (`9436772`)
- `src/frontend/src/components/ErrorBoundary.tsx`: class 컴포넌트 + `resetKeys` 자동 복구 + `role="alert"` (`9436772`)

### Changed
- `src/frontend/src/app/layout.tsx`: 글로벌 `<NavHeader />` 삽입 (`9436772`)
- `src/frontend/src/app/page.tsx`: 중복 헤더 제거(sr-only H1), 시그널 리스트 `grid-cols-1 lg:grid-cols-2`, `<ul>/<li>` 시맨틱, 필터 `role="group" + aria-pressed` (`9436772`)
- `src/frontend/src/app/stocks/[code]/page.tsx`: `ResponsiveContainer aspect={2}` 비율 기반 차트, ErrorBoundary 래핑, 기간 버튼 `role="group"`, render-time 상태 리셋 (`9436772`)
- `src/frontend/src/app/backtest/page.tsx`: 모바일 `<dl/dt/dd>` 카드 ↔ 데스크탑 `<table>` 이중 렌더, ErrorBoundary 래핑 (`9436772`)
- `src/frontend/src/components/features/SignalCard.tsx`: `<Link>`가 직접 그리드 컨테이너 (중첩 `<div role="article">` 제거), `aria-label` 상세화 (`9436772`)

### Fixed
- `react-hooks/set-state-in-effect` ESLint 3건(Next 16 신규 룰): `NavHeader.pathname`, `StockDetail.code+period`, `Dashboard` 초기 `setLoading` 중복 → render-time 리셋 패턴 (`9436772`)
- `role="tablist"/"tab"` 스펙 위반 2건 → `role="group" + aria-pressed` (필터, 기간 버튼) (`9436772`)
- ErrorBoundary 재발 루프: `resetKeys` + `componentDidUpdate` 자동 리셋 (리뷰 MEDIUM-1) (`9436772`)
- `role="alert"` + `aria-live="assertive"` 중복 제거 (`9436772`)
- 백테스트 YAxis formatter 음수 처리 (`+-1.5%` → `-1.5%`) (`9436772`)
- `aria-current="page"`는 exact match만, 관련 경로는 시각 강조로 분리 (`9436772`)

### Committed
- Sprint 4 Task 5-6 (`9436772`): 7 files, +330/-73, `tsc + eslint + next build` 전부 ok

### Pending (Task 4 + 프로토타입 선정 다음 세션)
- Task 4: 알림 설정 페이지 (`NotificationPreference` 엔티티 + `/settings` 프론트, 1.5일)
- 프로토타입 5종 중 합류본 선정 → `prototype/index.html`로 통합

---

## [2026-04-17] 프로토타입 UI 실험 5종 + 코드리뷰 보안 패치 전면 적용

### Added
- `prototype/index-before-skeleton.html`: 원본 스냅샷 (baseline, 보안 패치만) (`7a5b750`)
- `prototype/index-tilt-magnetic.html`: 3D 틸트 카드 + 마그네틱 버튼 — `prefers-reduced-motion` + 터치 자동 비활성 (`7a5b750`)
- `prototype/index-counter.html`: 카운트업 애니메이션 32개 카운터 (data 속성 선언형 엔진) (`7a5b750`)
- `prototype/index-ambient.html`: 배경 3층 — Aurora 메시 + 커서 스포트라이트 + 파티클 네트워크 캔버스 (`7a5b750`)

### Changed
- `prototype/index.html`: 스켈레톤 UI 적용 (시그널 리스트/상세 차트/백테스트 차트 로딩 + shimmer, 라이트/다크 대응) (`7a5b750`)

### Fixed
- **[CRITICAL] XSS 싱크 3종 차단**: `escapeHtml()` + `num()` 헬퍼, `onclick` 인라인 → `data-code` + `addEventListener` (`7a5b750`)
- **[HIGH] `showPage()` 허용목록**: `VALID_PAGES = Set` early return (`7a5b750`)
- **[HIGH] DOM 엘리먼트 캐싱**: `cacheEls()` INIT 1회 → `els[id]` 룩업 (`7a5b750`)
- **[MEDIUM] CDN SRI**: Chart.js 4.4.7 / Pretendard 1.3.9 `integrity="sha384-..."` + `crossorigin="anonymous"` (`7a5b750`)
- **[MEDIUM] 스켈레톤 접근성**: `role="list"` + `aria-busy` 토글 + `aria-live="polite"` + 카드 `role="button"` + 키보드 (`7a5b750`)
- **[LOW] matchMedia 동적 리스너**: `prefers-reduced-motion`/`pointer: coarse`에 `change` 리스너 (tilt/counter/ambient 3종) (`7a5b750`)

> 5종 HTML 모두 단독 실행 가능. 코드리뷰 재검증 CRITICAL/HIGH 0건 + 회귀 0건. 다음 세션에서 최종 합류본 결정 → `prototype/index.html` 통합 예정.

---

## [2026-04-17] Sprint 4 Task 1-3 — N+1 쿼리 최적화 + 백테스팅 3년 제한 + CORS X-API-Key

### Added
- `src/backend/src/test/java/com/ted/signal/config/CorsConfigTest.java`: CORS preflight 테스트 1개 신규 (`33b6cf1`)
- `BacktestApiIntegrationTest.runBacktestRejectsPeriodOverThreeYears`: 3년 초과 기간 rejection 테스트 추가 (`33b6cf1`)
- `StockPriceRepository.findAllByStockIdsAndTradingDateBetween`: 종목 IN 절 기반 벌크 주가 조회 (`33b6cf1`)
- `StockPriceRepository.findAllByTradingDate`: 일자별 주가 전체 조회 (JOIN FETCH stock) (`33b6cf1`)
- `ShortSellingRepository.findAllByTradingDate`: 일자별 공매도 전체 조회 (JOIN FETCH stock) (`33b6cf1`)
- `LendingBalanceRepository.findAllByStockIdsAndTradingDateBetween`: 종목 IN 기반 대차잔고 히스토리 (`33b6cf1`)
- `SignalRepository.findBySignalDateWithStockOrderByScoreDesc`: 일자별 시그널 JOIN FETCH 조회 (`33b6cf1`)

### Changed
- `SignalDetectionService.detectAll`: 종목당 7쿼리 × 2500 = 17,500쿼리 → 전체 7쿼리 (활성 종목 1 + 벌크 5 + 기존 시그널 1). 메모리 루프 기반 재작성 (`33b6cf1`)
- `TelegramNotificationService.sendDailySummary`: `findBySignalDateOrderByScoreDesc` → `findBySignalDateWithStockOrderByScoreDesc` (stock LAZY 로딩 N+1 해소) (`33b6cf1`)
- `BacktestController`: 최대 기간 5년 → **3년**, `to` 미래 날짜 차단 검증 추가 (`33b6cf1`)
- `BacktestEngineService`: 종목별 주가 조회 N쿼리 → `findAllByStockIdsAndTradingDateBetween` 단일 쿼리 (`33b6cf1`)
- `WebConfig`: CORS `allowedHeaders`에 `X-API-Key` 추가, `OPTIONS` 메서드, `allowCredentials(true)`, `exposedHeaders` 명시 (`33b6cf1`)
- `SignalDetectionService` detail의 `volumeChangeRate`: 점수(int) 중복 저장 → 실제 거래량 비율(BigDecimal) 저장 (`33b6cf1`)

### Committed
- Sprint 4 Task 1-3 (`33b6cf1`): 성능/보안 HIGH 3건 해소 (11 files, +245/-114, 테스트 20개 전부 통과)

### Pending (Task 4-5 다음 세션 이관)
- Task 4: 알림 설정 페이지 (`NotificationPreference` 엔티티 + 프론트 `/settings`)
- Task 5: 모바일 반응형 + ErrorBoundary + 접근성 감사

---

## [2026-04-17] 모델 운용 전략 전환 — Max 구독자 Opus 4.7 단일 운영

### Changed
- `docs/PIPELINE-GUIDE.md`: "Phase 1~3 Sonnet, Phase 4 Opus" 분기 전략 → **Max 구독자 Opus 4.7 단일 운영**으로 전환. API 종량제 사용자용 Option B 병기 (`d55738d`)
- `docs/design/ai-agent-team-master.md`: §11 "비용 최적화" 섹션을 **Option A (Max 구독) / Option B (API 종량제)** 이원화. Judge 비용 설명 보강 (`d55738d`)
- `.claude/commands/init-agent-team.md`: CLAUDE.md 템플릿에 "모델 운용 전략" 섹션 추가 + 최종 안내 메시지에 구독 유형별 가이드 포함 (`d55738d`)
- `pipeline/decisions/decision-registry.md`: D-0.1 "모델 운용 전략" 의사결정 추가 (23 → 24건) (`d55738d`)

> 근거: Claude Code Max $200 구독 활용 시 모델 분기로 얻는 비용 이득 없음. Sprint 3에서 Opus 4.7이 N+1 쿼리 17,500건 등 HIGH 이슈 7건 포착 → Phase 1~3에서도 Opus 사용 시 품질 우위 확인.

---

## [2026-04-17] 파이프라인 플랫폼 정합화 + 팀 공유 전환 + 문서 현행화

### Added
- `docs/PIPELINE-GUIDE.md`: 개발 플로우 사용설명서 신규 (9개 섹션, 다른 프로젝트 이식 체크리스트 포함) (`cdbacc5`)
- `docs/sprint-4-plan.md`: Sprint 4 작업계획서 (N+1 최적화 + CORS + 알림 설정 페이지 + 모바일 반응형, 4.5일 예상) (`da85ba2`)
- `pipeline/state/current-state.json`: Sprint 3 완료 상태 현행화 (진행 sprint 4종 + 테스트 커버리지 + 알려진 이슈) (`eecdb7c`)
- `pipeline/artifacts/06-code/summary.md`: Sprint 1~3 구현 요약 (Compaction 방어 영속화) (`eecdb7c`)
- `pipeline/decisions/decision-registry.md`: Phase 1~3 의사결정 23개 누적 (Discovery 3, Design 4, Build 15, Sprint 4 계획 1) (`da85ba2`)
- 글로벌 `~/.claude/settings.json` statusLine: 현재 모델 / 비용 / 200k 초과 / CWD 실시간 표시 (Opus→Sonnet fallback 즉시 인지)

### Changed
- `.gitignore`: `pipeline/state/`, `pipeline/artifacts/` 제외 규칙 제거 → 팀 공유 대상화 (`eecdb7c`)
- `CLAUDE.md`: 소규모 스타트업 팀 공유 전제 명시 + PIPELINE-GUIDE.md 참조 추가 + Spring Boot 3.4 → 3.5.0 일관성 (`eecdb7c`, `cdbacc5`)
- `docs/design/ai-agent-team-master.md`: `Opus 4.6` → `Opus 4.7` 14곳 치환 (1M 컨텍스트, 비용, MRCR 설명 전반) (`cdbacc5`)
- `.claude/commands/init-agent-team.md`: 기본 스택 `Spring Boot 3.4` → `3.5.0` (새 프로젝트 scaffolding 현행값) (`cdbacc5`)

### Committed
- Sprint 3 구현 (`022284e`): 백테스팅 엔진 + 텔레그램 알림 + 통합 테스트 (19 files, +1346)
- Sprint 3 핸드오프 (`88aba9a`): CHANGELOG + HANDOFF
- 파이프라인 영속화 (`da85ba2`): decision-registry + sprint-4-plan
- 팀 공유 전환 (`eecdb7c`): pipeline/ 커밋 대상화 (22 files, +2369)
- 문서 업데이트 (`cdbacc5`): Opus 4.7 + Spring Boot 3.5.0 + PIPELINE-GUIDE

---

## [2026-04-17] Phase 3 Build Sprint 3 — 백테스팅 엔진 + 텔레그램 알림 + 통합 테스트

### Added
- BacktestEngineService: 과거 3년 시그널 수익률 계산 + SignalType별 적중률/평균수익률 집계
- RunBacktestUseCase 포트 + POST /api/backtest/run API (API Key 보호, 기본 3년, 최대 5년)
- TelegramClient: RestClient 기반 Telegram Bot API 연동 (환경변수 비활성화 지원)
- TelegramNotificationService: 4가지 알림 시나리오 (일일 요약/A등급 긴급/배치 실패/주간 리포트)
- NotificationScheduler: 08:30 일일 요약 (월~금), 토요일 10:00 주간 리포트
- MarketDataBatchConfig notifyStep: 배치 완료 후 A등급 시그널 긴급 알림 자동 발송
- SignalRepository.findBySignalDateBetweenWithStock: JOIN FETCH 벌크 조회
- Testcontainers PostgreSQL 16 통합 테스트 인프라 (싱글톤 컨테이너 패턴)
- SignalDetectionServiceTest: 시그널 탐지 로직 5개 테스트 (급감/임계값/추세전환/숏스퀴즈/중복방지)
- BacktestEngineServiceTest: 수익률 계산 + 적중률 집계 + 데이터 부족 처리 4개 테스트
- BacktestApiIntegrationTest: API 인증/실행 5개 테스트
- SignalApiIntegrationTest: 시그널 조회/필터/인증 3개 테스트
- application.yml: telegram.bot-token, telegram.chat-id 환경변수 설정

### Changed
- API Key 비교: String.equals → MessageDigest.isEqual 상수 시간 비교 (타이밍 공격 방지, 3개 컨트롤러)
- API Key 미인증 시 403 → 401 UNAUTHORIZED 반환 (3개 컨트롤러)
- @Value 필드 주입 → 생성자 주입 전환 (BacktestController, BatchController, SignalDetectionController)
- BacktestEngineService: save() 루프 → saveAll() 일괄 저장
- MarketDataBatchConfig: SignalRepository 직접 주입 제거 → TelegramNotificationService.sendUrgentAlerts() 위임 (Hexagonal 경계 준수)
- MarketDataScheduler: 배치 실패 시 e.getMessage() 노출 → 클래스명만 텔레그램 발송
- BacktestController: @Validated 추가 + from/to 날짜 범위 검증 (최대 5년)
- TelegramNotificationService.sendBatchFailure: LocalDate → LocalDateTime (시간 정밀도)

---

## [2026-04-16] Phase 3 Build Sprint 2 — 시그널 엔진 + 대시보드

### Added
- SignalDetectionService: 3대 시그널 탐지 엔진 (급감/추세전환/숏스퀴즈) (`7902cfd`)
- POST /api/signals/detect 수동 시그널 탐지 API (`7902cfd`)
- Spring Batch detectStep 추가 (collectStep → detectStep 순차) (`7902cfd`)
- 프론트엔드 대시보드: 메트릭 카드 + 필터 탭 + 시그널 리스트 (`7902cfd`)
- 프론트엔드 종목 상세: 주가/대차잔고 듀얼 축 차트 (Recharts) (`7902cfd`)
- SignalCard 컴포넌트, TypeScript 타입 정의, API 클라이언트 (`7902cfd`)
- BacktestResult Entity + Repository + BacktestQueryService (`63407cd`)
- GET /api/backtest 백테스팅 결과 조회 API (`63407cd`)
- 프론트엔드 /backtest 페이지: 성과 테이블 + 보유기간별 수익률 Bar 차트 (`63407cd`)

### Changed
- 관리자 API 인증: IP allowlist → API Key 헤더(X-API-Key) 전환 (`e6754cb`)
- detail.volumeChangeRate 매핑 오류 수정 (`e6754cb`)
- scoreVolumeChange 음수 방지 Math.max(0, ...) 추가 (`e6754cb`)
- params.code 안전한 타입 처리 (Array.isArray 체크) (`e6754cb`)
- 프론트엔드 API 클라이언트 단일화 (중복 fetch 제거) (`e6754cb`)
- 미사용 변수 signalDates 제거 (`e6754cb`)

---

## [2026-04-16] Phase 3 Build Sprint 1 — 데이터 파이프라인 구축

### Added
- 16개 에이전트 AGENT.md + 공유 프로토콜 + 7개 슬래시 커맨드 scaffolding (`1908310`)
- Phase 1 Discovery 산출물 8건: 요구사항, PRD, 로드맵, 스프린트 플랜, GTM, 경쟁사 분석, 고객여정, 알림 시나리오 (`1908310`)
- Phase 2 Design 산출물 6건: 기능명세, 디자인 토큰, 컴포넌트 명세, ERD, DDL, 쿼리 전략 (`1908310`)
- Spring Boot 3.5.0 + Java 21 백엔드 프로젝트 (Hexagonal Architecture) (`33d7676`)
- Domain Entity 5개: Stock, StockPrice, LendingBalance, ShortSelling, Signal (`33d7676`)
- Repository 5개 (JPA 3단계 쿼리 전략), UseCase 2개, SignalQueryService (`33d7676`)
- REST API: GET /api/signals, GET /api/stocks/{code} (`33d7676`)
- GlobalExceptionHandler + sealed interface DomainError (`33d7676`)
- KRX 크롤러: 공매도/대차잔고/시세 수집 (요청 간격 2초) (`620f2bf`)
- Spring Batch Job + MarketDataScheduler (매일 06:00 스케줄) (`620f2bf`)
- 수동 배치 API: POST /api/batch/collect (localhost 제한) (`620f2bf`)
- docker-compose.yml: PostgreSQL 16 + DDL 자동 적용 (`620f2bf`)
- Next.js 15 + TypeScript 프론트엔드 프로젝트 초기화 (`33d7676`)
- UI/UX 프로토타입: Dark Finance Terminal 디자인 (prototype/index.html) (`33d7676`)
- .env.example (`620f2bf`)

### Changed
- Spring Boot 버전 3.4 → 3.5.0 (Spring Initializr 호환) (`33d7676`)
- JPA ddl-auto: validate → none (파티션 테이블 호환) (`140694b`)
- CORS allowedOrigins → allowedOriginPatterns + 헤더 제한 (`620f2bf`)
- MarketDataCollectionService: HTTP 수집을 트랜잭션 밖으로 분리 (`d710aa1`)
- 대차잔고 전 영업일 계산: minusDays(1) → 주말 건너뛰기 (`d710aa1`)
- 대차잔고 벌크 조회: 종목별 개별 쿼리 → findAllByTradingDate 1회 쿼리 (`d710aa1`)
- saveAll 벌크 저장으로 개별 exists/save 쿼리 제거 (`d710aa1`)
- BatchConfig → BatchConfig + Scheduler 분리 (Job Bean 직접 주입) (`d710aa1`)

---

## [2026-04-16] 프로젝트 초기 설정

### Added
- CLAUDE.md 생성 — 프로젝트 개요, 기술스택, 파이프라인, 에이전트 구조 가이드 (`fd26e75`)
- .gitignore 생성 — 빌드/IDE/환경파일 제외 설정 (`fd26e75`)
- GitHub 저장소 생성 (withwooyong/ted-startup, private) (`fd26e75`)
- AI Agent Team Platform 설계서 및 scaffolding 생성기 커밋 (`fd26e75`)
