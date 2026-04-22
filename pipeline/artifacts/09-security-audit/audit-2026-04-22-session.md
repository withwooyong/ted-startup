# Security Audit — 2026-04-22 세션 통합

**Scope**: 2026-04-22 세션에 머지된 3 PR 통합 보안 감사
**Commit range**: `3f0061e..77903d9` (master)
**Reviewer**: `everything-claude-code:security-reviewer` (sub-agent)
**Frameworks**: OWASP Top 10 + 의존성 취약점 + Security Headers

## PR 구성

| PR | 제목 | 커밋 |
|---|---|---|
| #22 | chore: CI 에 ruff + mypy strict 게이트 추가 + 전체 ruff format 적용 | `3f0061e` |
| #23 | refactor: Hexagonal 경계 정돈 + SyncPortfolioFromKis mock/real UseCase 분리 | `576e9f2` |
| #24 | refactor: KisAuthError 4xx/5xx 분리 — credential 거부 vs 업스트림 장애 | `77903d9` |

## Executive Summary

- CRITICAL: **0**
- HIGH: **0**
- MEDIUM: **1**
- LOW: **2**
- INFO: **2**

**머지 가능 여부**: 가능. CRITICAL / HIGH 발견 없음.

---

## Findings

### [MEDIUM] F-01 — DEBUG 로그의 structlog 마스킹 체인 연결 검증 필요

**OWASP**: A02 — Cryptographic Failures / Sensitive Data Exposure
**File**: `src/backend_py/app/adapter/out/external/kis_client.py` L310, L313, L384, L387

**Description**:
PR #24 가 KIS 응답 body 를 예외 메시지에서 제거하고 `logger.debug(...)` 로 이동한 것은 올바른 방향이다. 그러나 `logger = logging.getLogger(__name__)` (stdlib) 가 structlog `mask_sensitive` processor 를 실제로 경유하는지 설정 의존적이다.

`/app/observability/logging.py` 의 `setup_logging()` 을 읽은 결과:
- stdlib root logger 에 `ProcessorFormatter(foreign_pre_chain=shared_processors)` 설치
- `shared_processors` 에 `mask_sensitive` 포함
- 즉 `setup_logging()` 이 반드시 앱 시작 시 1회 호출되어야 체인 연결

**잠재 위험 경로**:
1. `setup_logging()` 이 호출되기 **전에** 로깅 발생 (`_configured` 가드는 재호출을 no-op 으로 만들지만 첫 호출 전은 보호 없음)
2. `setup_logging()` 이 전혀 호출되지 않는 경로 (Lambda 핸들러, 독립 스크립트 등) 에서 DEBUG 레벨로 실행되면 raw KIS response body 가 비구조 로그로 그대로 남음

`resp.text[:200/300]` 에는 KIS 가 반환하는 오류 세부(계좌 상태, 권한 코드) 포함 가능.

**Remediation**:
1. 앱 진입점(`main.py` / `lifespan`) 에서 `setup_logging()` 이 최초 DB 연결/라우터 등록보다 먼저 호출됨을 단위 테스트로 보장.
2. 또는 `kis_client.py` DEBUG 로그를 structlog bound logger 로 변경해 event dict 경유를 강제:
   ```python
   logger.debug("KIS token rejected", status=resp.status_code, kis_body=resp.text[:200])
   ```
   (stdlib `%s` 포맷이 아닌 키-값 로깅으로 `_scrub_string` 경유 보장)

---

### [LOW] F-02 — `CredentialRejectedError` HTTP 400 매핑의 열거형 힌트 가능성

**OWASP**: A04 — Insecure Design
**File**: `src/backend_py/app/adapter/web/routers/portfolio.py` L463-L464

**Description**:
`CredentialRejectedError` → HTTP 400 매핑 시 `detail=str(exc)` 를 그대로 반환. 현재 메시지는 필드 힌트가 없어 (`app_key/app_secret/account_no 재확인`) 공격자에게 실질 열거 힌트 미제공. Admin API Key 인증을 통과한 내부 관리 경로에만 노출. 수용 가능.

**Remediation**:
향후 KIS 가 오류 body 에 계좌 상태 코드를 반환하고 UseCase 가 이를 메시지에 포함시키는 리팩터링 시 `detail` 을 고정 문자열로 단순화:
```python
return HTTPException(status_code=400, detail="KIS 자격증명이 거부되었습니다. 설정에서 재등록하세요.")
```
즉각 조치 불필요.

---

### [LOW] F-03 — `type: ignore[assignment]` 잔존 — mypy strict 부분 회피

**OWASP**: A05 — Security Misconfiguration
**File**: `src/backend_py/app/adapter/out/persistence/repositories/brokerage_credential.py` L94

**Description**:
PR #22 에서 mypy strict 게이트 추가됐지만 `delete()` 메서드의 `CursorResult` 타입 캐스트는 `# type: ignore[assignment]` 회피. 코드 주석에 SQLAlchemy async 타입 제한이 이유로 명기, `rowcount` 접근 로직은 None 가드가 있어 런타임 안전 확보. 보안 취약점으로 이어지는 경로 없음.

단, `type: ignore` 축적 시 mypy strict 게이트 실질 방어 범위 감소. SQLAlchemy 2.1+ 타입 개선 시 제거 권고.

**Remediation**: `rowcount` 접근 전 `isinstance(result, CursorResult)` 런타임 가드 추가, 또는 SQLAlchemy 버전 업그레이드 시 제거.

---

### [INFO] F-04 — PR #22 대량 포맷 diff: 로직 불변 검증됨

**OWASP**: A08 — Software and Data Integrity Failures
**File**: 전체 98 파일 (`3f0061e` 커밋)

**Description**:
`ruff format` 기계 적용에 따른 대량 diff 가 실질 로직 변경을 은폐할 우려 검토. `kis_client.py`·`portfolio_service.py`·`brokerage_credential.py`·`portfolio.py` 4개 파일 샘플 검증 결과, 모든 변경이 들여쓰기/줄 길이/따옴표 정규화 수준. 제어 흐름·조건 분기·반환값·예외 처리 구조 동일.

CI `backend-lint` 게이트가 PR #22 이후 모든 커밋에 강제되므로 향후 포맷 위반은 자동 차단.

---

### [INFO] F-05 — 새 의존성 추가 없음 / `uv.lock` 변경 없음

**OWASP**: A06 — Vulnerable and Outdated Components
**File**: `src/backend_py/pyproject.toml`

**Description**:
PR #22~#24 는 기존 스택(FastAPI, SQLAlchemy, httpx, structlog, tenacity, cryptography) 만 사용하며 신규 패키지 추가 없음. `uv.lock` 변경 없음. 의존성 취약점 신규 노출 없음.

---

## Sign-off

**머지 가능 여부**: 가능. **CRITICAL / HIGH 발견 0**.

**운영 배포 전 조치 권고 항목**:

| # | 심각도 | 항목 | 조치 시점 |
|---|---|---|---|
| F-01 | MEDIUM | `setup_logging()` 호출 순서 통합 테스트 추가 / 또는 kis_client.py DEBUG 로그를 structlog bound logger 로 전환 | **배포 전 권장** |
| F-02 | LOW | 향후 KIS 오류 메시지 확장 시 `detail` 고정 문자열 적용 | 다음 리팩터 사이클 |
| F-03 | LOW | `type: ignore[assignment]` 런타임 가드 추가 | SQLAlchemy 버전 업그레이드 시 |

**총평**:
이번 세션 3 PR 은 모두 방어적 설계 개선 (CI lint 게이트 / Hexagonal 경계 / 예외 분리) 이며 공격면 신규 확장 없음. F-01 만 DEBUG 로깅 경로에서 조건부 데이터 유출 가능성으로 남아 있어 배포 전 검증 권고.
