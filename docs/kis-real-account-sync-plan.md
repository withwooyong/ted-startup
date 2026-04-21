# KIS 실계정 sync 설계안

- **작성일**: 2026-04-20
- **최종 수정**: 2026-04-21 (PR 1~6 구현 완료 — 시리즈 최종 PR 6 커밋 대기)
- **상태**: PR 1~5 머지 완료 (`1461582`). **PR 6 (로깅 마스킹, 시리즈 최종)** 구현·검증 완료, 커밋/PR 대기
- **범위**: 한국투자증권(KIS) 실계좌 REST API 연동으로 `portfolio_holding` 자동 동기화 + 엑셀 거래내역 import
- **전제**: PR 5 머지부터 운영 코드에서 실 KIS 외부 호출 가능. CI 는 smoke 마커 skip + `httpx.MockTransport` 로 실 URL 차단 유지.

---

## 1. 현재 상태 (As-Is)

| 영역 | 구현 |
|---|---|
| Adapter | `app/adapter/out/external/kis_client.py` — 모의 URL(`openapivts.koreainvestment.com:29443`) + TR_ID `VTTC8434R` 하드코딩. 실 URL 진입 시 `KisNotConfiguredError` |
| Credentials | 프로세스 전역 env var (`KIS_APP_KEY_MOCK`, `KIS_APP_SECRET_MOCK`, `KIS_ACCOUNT_NO_MOCK`). DB 저장 없음 |
| Token | 단일 클라이언트 인스턴스가 24h 토큰 캐싱 + 5분 만료 margin |
| Use Case | `SyncPortfolioFromKisUseCase` — `connection_type != "kis_rest_mock"` OR `environment != "mock"` 이면 하드 블록 |
| DB 스키마 | `brokerage_account.connection_type` VARCHAR(20) CHECK in ('manual', 'kis_rest_mock'). `environment` CHECK in ('mock', 'real') — 'real' 은 DB 허용하지만 코드 블록 |
| Mock | `kis_use_in_memory_mock=True` 시 `httpx.MockTransport` 로 완전 내부화 — CI/E2E 용 |

---

## 2. 갭 분석 (To-Be 대비 빠진 것)

| # | 갭 | 현재 | 필요 |
|---|---|---|---|
| G1 | Base URL / TR_ID | 모의 고정 | 실거래 URL(`openapi.koreainvestment.com:9443`) + 실TR_ID(`TTTC8434R`) 분기 |
| G2 | Credential 저장 | 전역 env var | 계좌별 저장 (다중 실계정 지원) — 암호화 at-rest 필수 |
| G3 | Token 캐시 | 프로세스 전역 단일 | 계좌별 (credential 이 다르므로) |
| G4 | `connection_type` enum | `('manual', 'kis_rest_mock')` | `+ 'kis_rest_real'` |
| G5 | `environment` guard | `'real'` 일괄 차단 | `kis_rest_real` 일 때만 허용 |
| G6 | Rate limit | MVP 에서 페이징 생략 (≤50 가정) | 실계좌 1분 1회·초당 20회 규격 존중 — 전역 token bucket |
| G7 | 로깅 보안 | 현 `logger.info` 에 masking 없음 | app_key/secret/token 값 **절대 로그 미노출** (structlog filter) |
| G8 | 온보딩 UX | 없음 (env var 만) | "엑셀 import → API key 입력 → OAuth 발급" 단계별 신뢰 빌드업 |
| G9 | 테스트 격리 | 전체 mock 기반 | 실계정 smoke 테스트는 별도 pytest mark + CI skip |

---

## 3. 제안 아키텍처

### 3.1 어댑터 일반화 — `KisClient` 2환경 지원

```python
class KisClient:
    def __init__(
        self,
        credentials: KisCredentials,  # 새 DTO: app_key, app_secret, account_no
        *,
        environment: KisEnvironment,  # Enum: MOCK | REAL
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        ...
```

- `environment=MOCK` → base_url=`openapivts`, TR_ID 접두=`VTTC`
- `environment=REAL` → base_url=`openapi`, TR_ID 접두=`TTTC`
- Credentials 를 생성자 파라미터로 받아 **전역 Settings 의존 제거** (인스턴스별 독립)
- In-memory MockTransport 경로는 유지 (E2E 안정성)
- Client lifetime: use case 스코프 (with 컨텍스트) — 기존 프로세스 전역 캐시 해체

### 3.2 Credentials 저장 — 신규 테이블 + 대칭 암호화

```sql
CREATE TABLE brokerage_account_credential (
    id               BIGSERIAL PRIMARY KEY,
    account_id       BIGINT NOT NULL UNIQUE REFERENCES brokerage_account(id) ON DELETE CASCADE,
    app_key_cipher   BYTEA  NOT NULL,
    app_secret_cipher BYTEA NOT NULL,
    account_no_cipher BYTEA NOT NULL,
    key_version      INT    NOT NULL DEFAULT 1,  -- 마스터키 회전 대비
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

- **대칭 암호화**: `cryptography.fernet.Fernet` 사용 (AES-128-CBC + HMAC-SHA256)
- **마스터 키**: env var `KIS_CREDENTIAL_MASTER_KEY` (32 bytes base64). 컨테이너 기동 시 주입, 로그 미노출
- **key_version**: 회전 시 신·구 버전 공존 허용. 초기 v1
- **읽기 권한**: Admin API Key 인증된 요청만. 반환 시 `app_key` 는 마지막 4자리만 노출(`"••••1234"`), secret 은 조회 불가

### 3.3 Use Case 확장

```python
class SyncPortfolioFromKisUseCase:
    async def execute(self, *, account_id: int, asof: date | None = None) -> SyncResult:
        account = await self._account_repo.get(account_id)
        if account.connection_type not in ("kis_rest_mock", "kis_rest_real"):
            raise UnsupportedConnectionError(...)

        if account.connection_type == "kis_rest_real":
            if account.environment != "real":
                raise InvalidRealEnvironmentError("kis_rest_real 은 environment='real' 필수")
            credentials = await self._cred_repo.get_decrypted(account_id)
            env = KisEnvironment.REAL
        else:  # mock
            if account.environment != "mock":
                raise InvalidRealEnvironmentError(...)
            credentials = self._settings.kis_mock_credentials()  # 기존 env var 경로 유지
            env = KisEnvironment.MOCK

        async with KisClient(credentials, environment=env) as client:
            rows = await client.fetch_balance()
        # 이후 upsert 로직은 기존 동일
```

### 3.4 온보딩 UX (엑셀 → API key → OAuth)

**3단계 신뢰 빌드업** — 실계좌 부담 최소화:

1. **1단계 엑셀 import** (수동, 부수효과 낮음)
   - 사용자가 증권사 웹에서 내보낸 거래내역 `.xlsx` 업로드
   - `portfolio_transaction` 에 `source='excel_import'` 로 적재
   - 자동 동기화 없음 — 순수 과거 기록만 반영

2. **2단계 API key 등록** (자격증명만, 호출 없음)
   - Settings 페이지에서 실계좌 브로커리지 추가 폼
   - 입력: 계좌 별칭, KIS app_key, app_secret, 10자리 계좌번호
   - 저장 시 즉시 암호화 + `brokerage_account_credential` INSERT
   - 이 단계에선 외부 API 호출 없음 (credentials 는 저장만)

3. **3단계 OAuth 발급 + 첫 sync** (실제 외부 호출 시작)
   - "연결 테스트" 버튼 → 토큰 발급만 시도 → 성공/실패 피드백
   - "잔고 동기화" 버튼 → `fetch_balance` → `portfolio_holding` upsert
   - 이후 사용자가 원할 때만 수동 sync (자동화는 v2)

### 3.5 보안 하드닝

| 항목 | 조치 |
|---|---|
| 로그 마스킹 | structlog processor 에서 `app_key`/`app_secret`/`access_token` 키가 있는 딕트를 `"[MASKED]"` 로 치환. 정규식 기반 문자열 매칭 추가 (JWT 형태·hex 40+자리 패턴) |
| Rate limit | 전역 `KisRateLimiter` — 실계좌 초당 1회 이하로 보수적 제한 (공식 20 req/sec 지만 MVP 는 안전 마진) |
| Error sanitization | `KisClientError` 메시지에 token/key/secret 포함되지 않게 — 응답 body 200자 slice 이미 있으므로 추가 scrub |
| Admin 권한 | credential CRUD 엔드포인트는 `hmac.compare_digest` Admin API Key 필수 (기존 패턴 재사용) |
| DB 권한 | `brokerage_account_credential.app_secret_cipher` 컬럼은 읽기 API 미노출 — use case 내부에서만 복호화 |
| 감사 로그 | credential 수정 시 `audit_log` 테이블에 account_id + timestamp + action 만 기록 (값은 기록 금지) — v2 |

### 3.6 테스트 전략

| 계층 | 접근 |
|---|---|
| 단위 | `KisClient(credentials, environment=MOCK, transport=MockTransport)` — 현재 구조 유지. `environment=REAL` 도 MockTransport 로 URL/TR_ID 분기만 검증 |
| 통합 | testcontainers PG16 + 암호화 왕복 검증. 모의 fixtures 는 그대로 사용 |
| E2E | 기존 `kis_use_in_memory_mock=True` 경로 유지 — CI 는 실 KIS 호출 0 |
| 실계좌 smoke | `@pytest.mark.requires_kis_real_account` 마크 — CI skip, 개발자 로컬에서 `pytest -m requires_kis_real_account` 로 1회 실행 |

---

## 4. MVP 범위

**IN SCOPE (이번 과제):**
- G1, G3, G4, G5: 어댑터 2환경 분기 + Use Case 확장 + connection_type enum 추가
- G2: `brokerage_account_credential` 테이블 + Fernet 암호화
- G7: 로깅 마스킹 (최소 structlog processor + 문자열 scrub)
- G8: 3단계 온보딩 UX **전부** (1단계 엑셀 import + 2·3단계 API key·OAuth) — 결정 #3 반영

**OUT OF SCOPE (후속 과제):**
- G6 rate limiter: MVP 는 사용자 수동 sync 만 — 자동 스케줄링 도입 시 추가
- Credential 마스터 키 회전 운영 절차: 설계만 언급, 자동화는 v2
- output2 파싱 (예수금·평가요약): MVP 는 holdings 만
- 거래 내역 역추적: KIS 잔고 API 는 스냅샷이라 transaction 재구성 불가 (기존 한계 유지)
- Order 실행 (매수/매도): 조회만. 실거래는 명시적으로 **금지**
- 다중 사용자 권한 분리: 로컬 단일 사용자 (Admin API Key 인증) 만 지원 — 결정 #2 반영

---

## 5. PR 분할 계획 (확정)

온보딩 UX 순서(엑셀 → API key → OAuth)에 맞춰 **PR 순서를 사용자 여정 순서로** 정렬. 낮은 위험도(엑셀 import, 외부 호출 0건) 부터 단계적으로 도입.

| PR | 제목 | 범위 | 의존 | 상태 |
|----|---|---|---|---|
| 1 | 엑셀 거래내역 import (1단계 온보딩) | `openpyxl` 파서, 컬럼 매핑 규칙, `portfolio_transaction` 에 `source='excel_import'` 로 적재. 증권사별 엑셀 포맷 차이는 1~2종만 (KIS 국내주식 체결내역 우선). API·UI 포함 | — | ✅ #12 (`6ea71fe`) |
| 2 | `kis_rest_real` 어댑터 분기 | KisClient `environment` 파라미터, `kis_rest_real` connection_type enum, use case 분기. In-memory mock 통합 테스트로 real URL/TR_ID 검증 (외부 호출 0) | — | ✅ #13 (`269651e`) |
| 3 | `brokerage_account_credential` 스키마 + Fernet 암호화 | Alembic 마이그레이션, Credential repository, Fernet wrapper, CI fixture (더미 마스터키 주입), 암호화 왕복 테스트 | PR 2 | ✅ #14 (`3db778f`) |
| 4 | 실계정 등록 API + Settings UI (2단계 온보딩) | POST/PUT/GET/DELETE credential 엔드포인트, Settings 페이지 "실계좌 연동" 섹션, 비례 길이 마스킹 (`••…1234`), 외부 호출 여전히 0 | PR 3 | ✅ 머지 (`d470a73`, #15) |
| 5 | "연결 테스트" + 실 sync (3단계 온보딩) | `POST /test-connection` (토큰만 dry-run), `SyncPortfolioFromKisUseCase` 에 credential_repo + real_client_factory 주입, `@pytest.mark.requires_kis_real_account` smoke 마커 | PR 4 | ✅ 머지 (`1461582`, #16) |
| 6 | 로깅 마스킹 + 문자열 scrub | structlog processor 추가 (`app/observability/logging.py`), 기존 로그 호출 점검, token revoke 한계 README 명시 (결정 #4 반영) | PR 5 | ✅ 구현 완료 (커밋 대기) |

**예상 작업 시간 (1인 기준):**
- PR 1: 3~4h (엑셀 포맷 탐색 + 파서 + UI)
- PR 2: 2~3h
- PR 3: 3~4h (Fernet + 마이그레이션 + 왕복 테스트 + CI fixture)
- PR 4: 3~4h (FE + BE + 마스킹 뷰)
- PR 5: 2~3h (smoke + 피드백)
- PR 6: 1~2h
- **총 14~20h** — 세션 6~7개 분할

---

## 6. 결정 사항 (2026-04-20 확정)

| # | 질문 | 결정 | 구현 영향 |
|---|------|------|-----------|
| 1 | Fernet 마스터 키 관리 | **env var** (`KIS_CREDENTIAL_MASTER_KEY`) | PR 3: 로컬·CI·prod 모두 env var 주입. KMS 연동 없음 |
| 2 | 사용자 권한 모델 | **로컬 단일 사용자** (Admin API Key 만) | PR 4: per-user 분리 스키마 불필요. `brokerage_account_credential.account_id` UNIQUE 로 충분 |
| 3 | 엑셀 import 포함 여부 | **포함** (PR 1 로 선행) | PR 1 신설 — 외부 호출 0 이라 가장 낮은 위험부터 진입 |
| 4 | 토큰 revoke 불가 | **한계 수용 + README 명시** | PR 6: KIS OpenAPI 는 24h TTL 만 제공. credential 삭제 시 만료 대기 외 방법 없음을 docs 에 명시 |
| 5 | CI Fernet fixture | **더미 키 주입 패턴 확정** | PR 3: `conftest.py` 에서 `os.environ["KIS_CREDENTIAL_MASTER_KEY"] = Fernet.generate_key()` — session scope fixture |

---

## 7. 공식 문서 확인 필요 사항

구현 착수 전 한국투자증권 OpenAPI 공식 문서로 확인할 것 (knowledge cutoff 2026-01 기준 가정치):

- [ ] 실거래 base_url 정확한 host/port (`openapi.koreainvestment.com:9443` 로 알려져있으나 v2 엔드포인트 업데이트 여부)
- [ ] 실거래 잔고조회 TR_ID (`TTTC8434R` 로 알려져있으나 API v2/v3 마이그레이션 여부)
- [ ] Rate limit 정확 수치 (실거래 분당/초당 request 한도)
- [ ] OAuth 토큰 revoke 엔드포인트 존재 여부 재확인
- [ ] CANO + ACNT_PRDT_CD 포맷 변경 여부 (계좌번호 체계 개편 이력 확인)

---

## 8. 다음 액션

1. ~~본 설계안 사용자 리뷰 + "6. 열린 질문" 5건 결정~~ ✅ **완료 (2026-04-20)**
2. ~~PR 1 (엑셀 import)~~ ✅ **완료 (2026-04-20, #12)**
3. ~~PR 2 (`kis_rest_real` 어댑터 분기)~~ ✅ **완료 (2026-04-21, #13)**
4. ~~PR 3 (`brokerage_account_credential` + Fernet)~~ ✅ **완료 (2026-04-21, #14)**
5. ~~PR 4 (실계정 등록 API + Settings UI)~~ ✅ **머지 (2026-04-21, `d470a73`, #15)**
6. ~~PR 5 (연결 테스트 + 실 sync)~~ ✅ **머지 (2026-04-21, `1461582`, #16)**
7. ~~PR 6 (로깅 마스킹, 시리즈 최종)~~ ✅ **구현 완료 (2026-04-21, 커밋 대기)** — `app/observability/logging.py` 신규 (structlog + masking processor). 2층 방어: (a) 민감 키 기반 치환 (`app_key`·`app_secret`·`access_token`·`authorization` 등 20+ 키) (b) 정규식 scrub (JWT 3-segment + 40자+ hex). stdlib logging 브릿지로 기존 `logger.info` 호출도 자동 마스킹 혜택. README 에 KIS 토큰 revoke 한계(24h TTL, roll 절차) + 로깅 보호 메커니즘 명시. 백엔드 테스트 239 → 278 (+39). **KIS sync 시리즈 완결.**

## 9. 운영 메모 (PR 3 머지 후 추가)

- **마스터키 배포**: 운영 환경에 `KIS_CREDENTIAL_MASTER_KEY` env var 주입 필수. `Fernet.generate_key()` 출력 (32 bytes url-safe base64). 미설정 시 앱 기동 시 `get_credential_cipher()` DI 가 `MasterKeyNotConfiguredError` 로 fail-fast.
- **downgrade 주의**: `alembic downgrade -1` 시도 시 `brokerage_account_credential` 에 데이터가 있으면 `DO $$` 가드가 `RAISE EXCEPTION` → 수동 삭제 후 재시도 필요. 실 자격증명 복구 불가 상태 방지 설계.
- **실 sync 여전히 봉쇄**: PR 5 까지 `SyncPortfolioFromKisUseCase` 의 `kis_rest_real` 분기는 `KisCredentialsNotWiredError` → HTTP 501. Credential 저장소는 완성됐지만 use case 에 wire 되지 않았음 (의도적 단계 분리).
