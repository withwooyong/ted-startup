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

## 3. 의도적으로 미적용 (Phase B 진입 전 결정)

| 항목 | 사유 | 결정 시점 |
|------|------|-----------|
| **secretkey 정규식 보강 (M1)** | 키움 secretkey 형식 (40~50자 영숫자) 이 JWT/40+hex 패턴에 매칭 안 됨. f-string 으로 평문 logger 삽입 시 키 매칭 우회 가능 | A2 진입 전 — KiwoomAuthClient 작성 직전 |
| **DTO 직렬화 우회 방어 (M2)** | `dataclasses.asdict(creds)` 로 dict 변환 후 키 rename 하면 secretkey 노출 가능. SecretStr wrapper 또는 `__reduce__` 차단 | A2 진입 전 |
| **raw_response 토큰 평문 저장 차단 (M4)** | au10001 응답을 raw_response 에 저장하면 access_token 평문 BYTEA 가 아닌 JSONB 에 보관됨. UseCase 레이어에서 api_id == "au10001" 응답은 raw_response skip 또는 토큰 필드 제거 후 저장 | A2 진입 전 (au10001 코드 작성 직전) |
| **마스터키 회전 자동화** | `_fernets[2] = Fernet(new_key)` 다중 버전 구조는 있지만 실제 회전 마이그레이션 스크립트 부재. Settings 다중 키 필드 (`KIWOOM_CREDENTIAL_MASTER_KEY_V1`, `_V2`) 도 미정의 | Phase B 후반 |
| **assert → raise 적용** | A1 에서 `upsert` 에 적용 완료. 다른 경로는 발견 시 적용 | 발견 시 즉시 |

## 4. 결과

- 38 파일 / ~1,500줄 (테스트 ~600줄 포함)
- 테스트 117 passed / coverage 94.61% (목표 80% 초과)
- ruff lint 0 / mypy strict 0 / bandit 0 / pip-audit 0 CVE
- alembic upgrade/downgrade 양방향 검증

## 5. 다음 chunk

A2 — KiwoomClient 공통 트랜스포트 + KiwoomAuthClient (au10001/au10002) + IssueKiwoomToken/RevokeKiwoomToken UseCase + TokenManager + auth router + lifespan graceful shutdown.

본 ADR 의 § 3 미적용 항목 4건은 A2 진입 전 결정.
