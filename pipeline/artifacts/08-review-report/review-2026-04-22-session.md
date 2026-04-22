# Code Review Report — 2026-04-22 세션 통합

**Scope**: 2026-04-22 세션에 머지된 3 PR 통합 재감사
**Commit range**: `3f0061e..77903d9` (master)
**Reviewer**: `everything-claude-code:python-reviewer` (sub-agent)
**Purpose**: 개별 PR 실시간 리뷰에서 놓칠 수 있는 누적 효과·잔존 부채·상호 간섭 발견

## PR 구성

| PR | 제목 | 커밋 |
|---|---|---|
| #22 | chore: CI 에 ruff + mypy strict 게이트 추가 + 전체 ruff format 적용 | `3f0061e` |
| #23 | refactor: Hexagonal 경계 정돈 + SyncPortfolioFromKis mock/real UseCase 분리 | `576e9f2` |
| #24 | refactor: KisAuthError 4xx/5xx 분리 — credential 거부 vs 업스트림 장애 | `77903d9` |

## Executive Summary

- CRITICAL: **0**
- HIGH: **2**
- MEDIUM: **3**
- LOW: **1**

정적 분석 결과: `ruff check` All checks passed / `mypy --strict` 81 files no issues / `pytest` 303 passed.

**결론**: 머지 BLOCK 없음. HIGH 2건은 기능 정확성이 아닌 아키텍처 부채 + 성능 명확성 이슈로 MVP 운영에 즉각 위험 없음. 다음 사이클 첫 PR 로 DIP 완성을 예약 권고.

---

## SOLID 원칙

### [HIGH] R-01 — DIP 미완성: application layer 가 adapter.out.external 을 직접 import

**File**: `src/backend_py/app/application/service/portfolio_service.py:24-30`

`portfolio_service.py` 가 `KisClient`, `KisClientError`, `KisCredentialRejectedError`, `KisCredentials`, `KisHoldingRow` 를 `from app.adapter.out.external import ...` 로 직접 참조. 동일 문제가 `notification_service.py`(TelegramClient), `market_data_service.py`(KrxClient), `analysis_report_service.py` 에도 존재. PR #23 의 `MaskedCredentialView` 이동은 올바른 방향이지만 절반만 완료.

**Fix**: `app/application/port/out/kis_port.py` 에 Protocol 정의 → UseCase 는 Protocol 만 참조. `KisCredentialRejectedError` → Port 예외로 래핑 (변환 지점을 adapter 측 Port 구현체로 이동).

### OCP / SRP — 대응 완료

- 예외 계층 `PortfolioError` sibling 구조 + `_credential_error_to_http` isinstance 체인은 현재 규모에서 확장 가능.
- Mock/Real UseCase 분리 후 각 클래스는 단일 책임. `_apply_kis_holdings` 파라미터 6개(keyword-only) 는 허용 범위.

---

## 성능·동시성

### [HIGH] R-02 — Router account 이중 로드: SA identity map 보장 조건 미명시

**Files**: `app/adapter/web/routers/portfolio.py:278`, `app/application/service/portfolio_service.py:738` (`_ensure_kis_real_account`)

`sync_from_kis` 라우터가 `BrokerageAccountRepository(session).get(account_id)` 로 account 선로드 후, `SyncPortfolioFromKisRealUseCase._ensure_kis_real_account` 가 동일 session 에서 `self._account_repo.get(account_id)` 재호출.

SQLAlchemy 2.0 identity map 은 `session.get(Model, pk)` 경로에서만 캐싱 확정. Repository 가 내부적으로 `execute(select(...).where(...))` 를 쓰면 캐시 미스.

**Fix**: `_ensure_kis_real_account` 시그니처에 `account: BrokerageAccount` 파라미터 추가로 Router 선로드 결과 전달. 최소한 Repository.get 이 `session.get` 을 쓴다는 점을 docstring 에 명시.

### _apply_kis_holdings N+1 (주석 부재)

`find_by_account_and_stock` per-row 루프는 종목 수 증가 시 N+1. MVP 가정(≤50) 이 주석으로 없어 스케일 임계값 불투명. 이전 리뷰 지적이나 주석 반영 없이 머지.

**Fix**: `_apply_kis_holdings` docstring 에 "MVP: ≤50 종목 가정, 배치 upsert 는 P-후속 PR" 추가.

---

## 에러 핸들링

### [MEDIUM] R-03 — 이름 중복 혼동: `KisCredentialRejectedError` vs `CredentialRejectedError`

**File**: `src/backend_py/app/application/service/portfolio_service.py` (양쪽 import)

Import 충돌·ruff/mypy 경고 없음 (이름이 다르므로). 단 stack trace 에서 혼동 가능. 신규 기여자가 두 예외를 혼용할 회귀 위험.

**Fix**: `CredentialRejectedError` → `KisCredentialRejectedDomainError` 리네이밍 또는 `as` alias. 별도 PR 후보 (공수 30분).

### [MEDIUM] R-04 — MOCK 경로 `CredentialRejectedError`: 운영자 오류를 사용자 응답으로 흘림

**File**: `src/backend_py/app/application/service/portfolio_service.py:697-700`

`SyncPortfolioFromKisMockUseCase.execute` 가 MOCK 환경의 401/403 을 `CredentialRejectedError` → HTTP 400 으로 변환. MOCK 401 은 운영자 설정 오류(MOCK 환경 설정 불일치) 가 원인인데 사용자에게 "Settings 에서 재등록" 안내는 오해 유발. 이전 리뷰 MEDIUM #3 미해소.

**Fix**: MOCK 경로 401/403 → 500 (Internal) 또는 SyncError(502) 유지. 메시지 "서버 환경 변수 점검 — 운영팀 문의" 로 변경.

### except 순서 / 분기 순서 — 대응 완료

- 3 UseCase 모두 `except KisCredentialRejectedError` → `except KisClientError` 순서 일관
- `_credential_error_to_http` 분기 순서는 `PortfolioError` sibling 관계라 순서 의존성 없음. 안전.

---

## 테스트 커버리지

### [MEDIUM] R-05 — `/sync` endpoint 의 `CredentialRejectedError → 400` 직접 테스트 부재

**File**: `src/backend_py/tests/test_kis_real_sync.py`

`test-connection` 엔드포인트는 `test_endpoint_test_connection_credential_rejected_400` 으로 400 경로 커버. 그러나 **`/sync` endpoint** 에는 해당 경로 endpoint 테스트 없음.

**Fix**: `test_endpoint_sync_real_account_credential_rejected_400` 추가 — `token_status=401` transport, `resp.status_code == 400` + `"자격증명 거부" in detail`.

### 5xx 범위 커버 + MOCK 경로 테스트 부재 — 평가

- `test_connection_upstream_5xx_wrapped_as_sync_error` 는 500 단일. kis_client 분기가 `status_code not in (401, 403)` → KisAuthError 이므로 501/503 도 자동 동일 경로. 회귀 안전.
- MOCK 경로 `CredentialRejectedError` 테스트 부재 — R-04 의 재분류 시 함께 추가.

---

## CI / 파이프라인 영향

### [LOW] R-06 — ruff format 일괄 적용 git blame 오염

PR #22 의 98파일 일괄 format 이 `git blame` 을 단일 커밋으로 소멸. 후속 PR 의 L-by-L 고고학 어려워짐.

**Fix**: repo root 에 `.git-blame-ignore-revs` 파일 신설 — `3f0061e` 추가. `git config blame.ignoreRevsFile .git-blame-ignore-revs` 로 local setup 가이드.

CI 속도 영향(~30초 추가) 은 허용 범위.

---

## 잔존 부채 & 권고 (우선순위 순)

| # | 우선순위 | 항목 | 파일 | 비고 |
|---|---|---|---|---|
| R-01 | HIGH | DIP 완성 — KisPort Protocol 정의 | `app/application/port/out/kis_port.py` (신규) | 단독 PR, 전 서비스 영향 |
| R-02 | HIGH | Router account 이중 로드 제거 | `portfolio.py:278` · `portfolio_service.py:738` | 1-sprint 수정 |
| R-04 | MEDIUM | MOCK 401/403 → 500/502 재분류 | `portfolio_service.py:697` | 2줄 수정 |
| R-05 | MEDIUM | `/sync` 400 endpoint 테스트 추가 | `test_kis_real_sync.py` | 테스트 1개 |
| R-03 | MEDIUM | 이름 중복 완화 (KisCredentialRejectedError → KisUpstreamCredentialRejectedError 등) | 예외 정의 + 사용처 | 별도 PR |
| R-06 | LOW | `.git-blame-ignore-revs` 추가 | repo root | 1파일 |
| — | LOW | `Mapped[str]` → `Mapped[Literal[...]]` (connection_type) | `models/portfolio.py:42` | PR #23 리뷰에서 이월됨 |

**결론: BLOCK 없음.** HIGH 2건은 기능 정확성이 아닌 아키텍처 부채 + 성능 명확성 이슈. MVP 운영에 즉각 위험 없음. DIP 완성 PR 을 다음 사이클 첫 PR 로 예약 권고.
