# endpoint-01-au10001.md — 접근토큰 발급

## 0. 메타

| 항목 | 값 |
|------|-----|
| API ID | `au10001` |
| API 명 | 접근토큰 발급 |
| 분류 | Tier 1 (인증 — 모든 호출의 전제) |
| Phase | **A** |
| 우선순위 | **P0 (블로커)** |
| Method | `POST` |
| URL | `/oauth2/token` |
| 운영 도메인 | `https://api.kiwoom.com` |
| 모의투자 도메인 | `https://mockapi.kiwoom.com` (KRX 만 지원) |
| Content-Type | `application/json;charset=UTF-8` |
| 의존 endpoint | 없음 (전체 의존 그래프의 루트) |
| 후속 endpoint | au10002 (폐기), 24개 모든 데이터 endpoint |

---

## 1. 목적

키움 OpenAPI 의 모든 호출은 `Authorization: Bearer <token>` 헤더를 요구한다. 이 토큰은 `client_credentials` grant 방식 OAuth 2.0 으로 `appkey + secretkey` 를 교환해 발급받는다.

**왜 별도 endpoint 로 분리해 계획하는가**:
- 토큰 만료 시간 관리(`expires_dt`) 와 자동 재발급 로직이 모든 후속 호출의 전제 조건
- 자격증명(appkey/secretkey) 이 DB 에 Fernet 암호화 저장되므로, 그 복호화·주입 흐름이 여기서 정의되어야 후속 endpoint 가 재사용 가능
- 토큰 자체도 민감 정보 — 로깅·에러 메시지·예외에 노출되지 않도록 처음부터 마스킹 파이프라인을 검증해야 함

---

## 2. Request 명세

### 2.1 Header

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `api-id` | TR 명 | String | Y | 10 | `"au10001"` 고정 |
| `authorization` | 접근토큰 | String | Y | 1000 | **본 endpoint 는 발급 자체이므로 빈 문자열 허용**. 다른 endpoint 에서는 `Bearer <token>` 형식 |
| `cont-yn` | 연속조회 여부 | String | N | 1 | 본 endpoint 미사용 |
| `next-key` | 연속조회 키 | String | N | 50 | 본 endpoint 미사용 |

> **Note**: 키움 공식 스펙은 `authorization` 을 Required 로 표기하지만, 발급 시점에는 토큰이 없으므로 실무는 빈 문자열 또는 헤더 자체 생략. 운영 검증으로 확정 필요 (DoD 단계).

### 2.2 Body

| Element | 한글명 | Type | Required | Description |
|---------|-------|------|----------|-------------|
| `grant_type` | grant_type | String | Y | **`client_credentials`** 고정 |
| `appkey` | 앱키 | String | Y | 키움 발급 |
| `secretkey` | 시크릿키 | String | Y | 키움 발급 |

### 2.3 Request 예시

```json
POST https://api.kiwoom.com/oauth2/token
Content-Type: application/json;charset=UTF-8
api-id: au10001
authorization:

{
    "grant_type": "client_credentials",
    "appkey": "AxserEsdcredca.....",
    "secretkey": "SEefdcwcforehDre2fdvc...."
}
```

### 2.4 Pydantic 모델

```python
# app/adapter/out/kiwoom/auth.py
class TokenIssueRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    grant_type: Literal["client_credentials"] = "client_credentials"
    appkey: Annotated[str, Field(min_length=16, max_length=128, pattern=r"^\S+$")]
    secretkey: Annotated[str, Field(min_length=16, max_length=256, pattern=r"^\S+$")]

    def __repr__(self) -> str:
        # 안전 가드 — 우발적 print/logging 도 plaintext 노출 차단
        tail = self.appkey[-4:] if len(self.appkey) >= 4 else "****"
        return f"TokenIssueRequest(appkey=••••{tail}, secretkey=<masked>)"
```

---

## 3. Response 명세

### 3.1 Header

| Element | 한글명 | Type | Description |
|---------|-------|------|-------------|
| `api-id` | TR 명 | String | `"au10001"` 에코 |
| `cont-yn` | 연속조회 여부 | String | 본 endpoint 미사용 |
| `next-key` | 연속조회 키 | String | 본 endpoint 미사용 |

### 3.2 Body

| Element | 한글명 | Type | Required | Description |
|---------|-------|------|----------|-------------|
| `expires_dt` | 만료일 | String | Y | **`YYYYMMDDHHMMSS`** 14 자리. 운영 확인 필요: 시각이 KST 인지 UTC 인지 |
| `token_type` | 토큰 타입 | String | Y | `"bearer"` 소문자 (예시 기준) |
| `token` | 접근토큰 | String | Y | base64 류 문자열, ~150 자 추정 |
| `return_code` | 처리 코드 | Integer | (예시 포함) | `0` = 정상. 스펙 표에는 없으나 응답 예시에 등장 |
| `return_msg` | 처리 메시지 | String | (예시 포함) | 한글 메시지. 예: `"정상적으로 처리되었습니다"` |

### 3.3 Response 예시 (Excel 원문 그대로)

```json
{
    "expires_dt": "20241107083713",
    "token_type": "bearer",
    "token": "WQJCwyqInphKnR3bSRtB9NE1lv...",
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다"
}
```

### 3.4 Pydantic 모델

```python
class TokenIssueResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")  # 추가 필드 등장 대비
    expires_dt: Annotated[str, Field(min_length=14, max_length=14, pattern=r"^\d{14}$")]
    token_type: str
    token: Annotated[str, Field(min_length=20)]
    return_code: int = 0
    return_msg: str = ""

    def __repr__(self) -> str:
        return (
            f"TokenIssueResponse(expires_dt={self.expires_dt}, "
            f"token_type={self.token_type}, token=<masked>, "
            f"return_code={self.return_code})"
        )

    def expires_at_kst(self) -> datetime:
        # 운영 검증 후 tz 확정. 우선 KST 가정.
        return datetime.strptime(self.expires_dt, "%Y%m%d%H%M%S").replace(tzinfo=KST)
```

---

## 4. NXT 처리

| 항목 | 적용 여부 |
|------|-----------|
| `stk_cd` 에 `_NX` suffix | N (인증 endpoint, 종목코드 없음) |
| `nxt_enable` 게이팅 | N |
| `mrkt_tp` 별 분리 호출 | N |

**Note**: 모의투자(`mockapi.kiwoom.com`) 환경에서 발급된 토큰은 **모의 호출 전용**이며 운영 호출에 사용 불가. 반대도 마찬가지. → `kiwoom_credential.env` 컬럼이 토큰의 유효 도메인을 결정.

---

## 5. DB 스키마

### 5.1 신규 테이블 (Migration 001 의 일부)

#### `kiwoom_credential` — 자격증명 저장

```sql
CREATE TABLE kiwoom.kiwoom_credential (
    id              BIGSERIAL PRIMARY KEY,
    alias           VARCHAR(50) NOT NULL UNIQUE,           -- 'prod-main' / 'mock-test' 등
    env             VARCHAR(10) NOT NULL CHECK (env IN ('prod', 'mock')),
    appkey_cipher   BYTEA NOT NULL,                        -- Fernet 암호화
    secretkey_cipher BYTEA NOT NULL,
    key_version     INT NOT NULL DEFAULT 1,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_kw_cred_env_active ON kiwoom.kiwoom_credential(env, is_active);
```

#### `kiwoom_token` — 토큰 캐시 (선택)

> **결정 필요**: 토큰을 DB 에 저장할지 vs 인스턴스 메모리 캐시만 둘지.
>
> - **메모리 캐시 only**: 단일 워커 + 재시작 빈도 낮음 → 충분. 단순.
> - **DB 캐시**: 다중 워커 / Kubernetes 다중 파드에서 토큰 공유. 키움 RPS 가 발급 호출도 카운트한다면 도움.
>
> **MVP 기본값**: 메모리 캐시 only. DB 테이블은 **Phase A 에서 정의만** 하고 사용은 Phase 통합(H) 단계에서 결정.

```sql
CREATE TABLE kiwoom.kiwoom_token (
    id              BIGSERIAL PRIMARY KEY,
    credential_id   BIGINT NOT NULL REFERENCES kiwoom.kiwoom_credential(id) ON DELETE CASCADE,
    token_cipher    BYTEA NOT NULL,                        -- Fernet 암호화 (토큰도 평문 저장 금지)
    token_type      VARCHAR(20) NOT NULL DEFAULT 'bearer',
    expires_at      TIMESTAMPTZ NOT NULL,
    issued_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (credential_id)                                  -- 자격증명당 활성 토큰 1개
);

CREATE INDEX idx_kw_token_expires ON kiwoom.kiwoom_token(expires_at);
```

### 5.2 영향 받는 ORM 모델

`app/adapter/out/persistence/models/credential.py`:

```python
class KiwoomCredential(Base):
    __tablename__ = "kiwoom_credential"
    __table_args__ = ({"schema": "kiwoom"},)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    alias: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    env: Mapped[str] = mapped_column(String(10), nullable=False)
    appkey_cipher: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    secretkey_cipher: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class KiwoomToken(Base):
    __tablename__ = "kiwoom_token"
    __table_args__ = (UniqueConstraint("credential_id"), {"schema": "kiwoom"})
    # ... (DB 캐시 사용 결정 후 활성화)
```

---

## 6. UseCase / Service / Adapter

### 6.1 Adapter 메서드 — `KiwoomAuthClient.issue_token()`

```python
# app/adapter/out/kiwoom/auth.py
class KiwoomAuthClient:
    """OAuth 발급/폐기 전용 어댑터. KiwoomClient(공통 트랜스포트) 와 분리해
    토큰 캐시 의존성이 없는 독립 호출이 가능하게 한다."""

    def __init__(
        self,
        base_url: str,                                   # prod or mock
        *,
        timeout_seconds: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        timeout = httpx.Timeout(connect=5.0, read=timeout_seconds, write=timeout_seconds, pool=5.0)
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, transport=transport)

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1.0, min=1.0, max=8.0),
        reraise=True,
    )
    async def issue_token(self, credentials: KiwoomCredentials) -> TokenIssueResponse:
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "api-id": "au10001",
        }
        body = {
            "grant_type": "client_credentials",
            "appkey": credentials.appkey,
            "secretkey": credentials.secretkey,
        }
        try:
            resp = await self._client.post("/oauth2/token", json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise KiwoomUpstreamError(f"토큰 발급 네트워크 오류: {exc}") from exc

        # 응답 본문은 DEBUG 로그로만 (structlog 가 토큰 패턴 자동 스크럽)
        if resp.status_code in (401, 403):
            logger.debug("au10001 401/403 body: %s", resp.text[:200])
            raise KiwoomCredentialRejectedError(
                f"키움 자격증명 거부: HTTP {resp.status_code}"
            )
        if resp.status_code != 200:
            logger.debug("au10001 %d body: %s", resp.status_code, resp.text[:200])
            raise KiwoomUpstreamError(f"토큰 발급 실패: HTTP {resp.status_code}")

        body_json = resp.json()
        return_code = body_json.get("return_code", 0)
        if return_code != 0:
            raise KiwoomBusinessError(
                api_id="au10001",
                return_code=return_code,
                message=body_json.get("return_msg", ""),
            )

        return TokenIssueResponse.model_validate(body_json)

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> KiwoomAuthClient: return self
    async def __aexit__(self, *exc_info: object) -> None: await self.close()
```

### 6.2 도메인 DTO

```python
# app/application/dto/kiwoom_auth.py
@dataclass(frozen=True, slots=True)
class KiwoomCredentials:
    """평문 자격증명 — UseCase 스코프 안에서만 존재.

    `__repr__` 가 secretkey 를 마스킹하지만, 더 안전하게는 dataclass 가 logger 호출에 직접
    들어가지 않도록 caller 가 dict 로 변환하지 않는 것이 원칙.
    """
    appkey: str
    secretkey: str

    def __repr__(self) -> str:
        tail = self.appkey[-4:] if len(self.appkey) >= 4 else "****"
        return f"KiwoomCredentials(appkey=••••{tail}, secretkey=<masked>)"


@dataclass(frozen=True, slots=True)
class IssuedToken:
    """발급된 토큰 + 만료 시각 (KST 가정)."""
    token: str
    token_type: str
    expires_at: datetime  # tz-aware

    def authorization_header(self) -> str:
        return f"{self.token_type.capitalize()} {self.token}"

    def is_expired(self, *, margin_seconds: float = 300.0) -> bool:
        now = datetime.now(self.expires_at.tzinfo)
        return (self.expires_at - now).total_seconds() < margin_seconds

    def __repr__(self) -> str:
        return f"IssuedToken(token=<masked>, expires_at={self.expires_at.isoformat()})"
```

### 6.3 UseCase — `IssueKiwoomTokenUseCase`

```python
# app/application/service/token_service.py
class IssueKiwoomTokenUseCase:
    """credential alias → 평문 복호화 → au10001 호출 → IssuedToken 반환.

    DB 토큰 캐시 사용 여부와 무관 — 캐시 레이어는 호출자(`TokenManager`) 책임.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        cipher: KiwoomCredentialCipher,
        auth_client_factory: Callable[[str], KiwoomAuthClient],   # base_url → client
    ) -> None:
        self._session = session
        self._cipher = cipher
        self._factory = auth_client_factory
        self._cred_repo = KiwoomCredentialRepository(session, cipher)

    async def execute(self, *, alias: str) -> IssuedToken:
        cred_row = await self._cred_repo.find_by_alias(alias)
        if cred_row is None:
            raise CredentialNotFoundError(f"alias={alias} 등록되지 않음")
        if not cred_row.is_active:
            raise CredentialInactiveError(f"alias={alias} 비활성 상태")

        creds = await self._cred_repo.decrypt(cred_row)  # KiwoomCredentials
        base_url = (
            settings.kiwoom_base_url_prod if cred_row.env == "prod"
            else settings.kiwoom_base_url_mock
        )
        async with self._factory(base_url) as client:
            resp = await client.issue_token(creds)
        return IssuedToken(
            token=resp.token,
            token_type=resp.token_type,
            expires_at=resp.expires_at_kst(),
        )
```

### 6.4 토큰 매니저 (메모리 캐시) — `TokenManager`

```python
# app/application/service/token_manager.py
class TokenManager:
    """프로세스 수명 토큰 캐시. credential alias 단위로 IssuedToken 보관.

    동시성: asyncio.Lock 이 alias 별로 1개 — 같은 alias 의 동시 재발급 호출이
    1회로 합쳐진다. 다른 alias 끼리는 병행.
    """

    def __init__(self, issue_use_case_factory: Callable[[], IssueKiwoomTokenUseCase]) -> None:
        self._factory = issue_use_case_factory
        self._cache: dict[str, IssuedToken] = {}
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def get(self, *, alias: str) -> IssuedToken:
        token = self._cache.get(alias)
        if token is not None and not token.is_expired():
            return token
        async with self._locks[alias]:
            # double-check — 락 대기 중 다른 코루틴이 갱신했을 수 있음
            token = self._cache.get(alias)
            if token is not None and not token.is_expired():
                return token
            uc = self._factory()
            new_token = await uc.execute(alias=alias)
            self._cache[alias] = new_token
            return new_token

    def invalidate(self, *, alias: str) -> None:
        self._cache.pop(alias, None)
```

---

## 7. 배치 / 트리거

| 트리거 | 설명 |
|--------|------|
| **자동 재발급** | `TokenManager.get()` 가 만료 5분 전 자동 호출 — 별도 cron 없음 |
| **수동 발급** | `POST /api/kiwoom/auth/tokens?alias=prod-main` (admin) — 디버깅·강제 갱신용 |
| **수동 폐기** | au10002 endpoint 계획서 참조 |
| 수동 dry-run | `python scripts/issue_token.py --alias prod-main` — credential 검증용 CLI |

### 7.1 라우터 (선택적, 운영 디버깅용)

```python
# app/adapter/web/routers/auth.py
router = APIRouter(prefix="/api/kiwoom/auth", tags=["kiwoom-auth"])


@router.post(
    "/tokens",
    response_model=IssueTokenResponse,
    dependencies=[Depends(require_admin_key)],
)
async def issue_token(
    alias: str = Query(..., min_length=1, max_length=50),
    manager: TokenManager = Depends(get_token_manager),
) -> IssueTokenResponse:
    """강제 토큰 갱신 — 캐시 무효화 후 새로 발급."""
    manager.invalidate(alias=alias)
    token = await manager.get(alias=alias)
    return IssueTokenResponse(
        alias=alias,
        token_masked=f"••••{token.token[-6:]}",
        token_type=token.token_type,
        expires_at=token.expires_at,
    )
```

> `IssueTokenResponse` 는 토큰 평문을 반환하지 않음 — tail 6자리만 노출. 진짜 토큰이 필요하면 운영자가 DB cipher 를 직접 복호화.

---

## 8. 에러 처리

| HTTP / 응답 | 도메인 예외 | 라우터 매핑 | 비고 |
|-------------|-------------|-------------|------|
| 401 / 403 | `KiwoomCredentialRejectedError` | 400 | 자격증명 잘못/회수됨 → 사용자가 alias 재등록 |
| 429 | (tenacity 자동 재시도) → 최종 실패 시 `KiwoomRateLimitedError` | 503 | 키움 RPS 초과 |
| 5xx, 네트워크, JSON 파싱 실패 | `KiwoomUpstreamError` | 502 | tenacity 3회 재시도 후 |
| `return_code != 0` | `KiwoomBusinessError(api_id="au10001", code, msg)` | 400 + detail | 비즈니스 에러 |
| 응답 `expires_dt` 형식 오류 | `KiwoomResponseValidationError` | 502 | Pydantic 검증 실패 |
| `CredentialNotFoundError` | — | 404 | alias 미등록 |
| `CredentialInactiveError` | — | 400 | is_active=false |
| `MasterKeyNotConfiguredError` | (Cipher init) | 500 (loud) | 기동 시 차단 권장 |

### 8.1 응답 본문 보호

키움이 자격증명 거부 시 응답 본문에 자격증명 힌트가 들어갈 가능성이 있다 (메시지에 appkey 일부 포함 등). 따라서:

- 응답 본문은 **DEBUG 로그로만** 분리 — `logger.debug("au10001 %d body: %s", status, resp.text[:200])`
- structlog `mask_sensitive` processor 가 JWT/hex 패턴 자동 스크럽
- 예외 메시지에는 HTTP status code 만 — body 절대 미포함
- HTTPException detail 에는 한국어 일반 메시지만

---

## 9. 테스트

### 9.1 Unit (MockTransport)

`tests/adapter/kiwoom/test_auth_client.py`:

| 시나리오 | 입력 | 기대 |
|----------|------|------|
| 정상 발급 | 200 + 정상 응답 JSON | `TokenIssueResponse` 반환, expires_at KST 파싱 |
| 401 | 401 응답 | `KiwoomCredentialRejectedError` |
| 403 | 403 응답 | `KiwoomCredentialRejectedError` |
| 500 | 500 응답 | tenacity 3회 재시도 후 `KiwoomUpstreamError` |
| 네트워크 오류 | `httpx.ConnectError` raise | tenacity 3회 후 `KiwoomUpstreamError` |
| `return_code=1` | 200 + 비즈니스 에러 | `KiwoomBusinessError(code=1)` |
| 토큰 누락 | 200 + `token` 빈 문자열 | `KiwoomResponseValidationError` (Pydantic) |
| `expires_dt` 잘못된 형식 | 200 + `"expires_dt": "abcd"` | `KiwoomResponseValidationError` |
| 응답 본문 마스킹 | 401 with body containing JWT | structlog 출력에 `[MASKED_JWT]` 확인 |

### 9.2 Integration (testcontainers + MockTransport)

`tests/application/test_token_service.py`:

| 시나리오 | 셋업 | 기대 |
|----------|------|------|
| `IssueKiwoomTokenUseCase` 정상 | credential seed + MockTransport 200 | `IssuedToken.is_expired()=False` |
| credential 미등록 | seed 없음 | `CredentialNotFoundError` |
| credential 비활성 | `is_active=false` seed | `CredentialInactiveError` |
| credential 거부 (401) | MockTransport 401 | `KiwoomCredentialRejectedError` |
| `TokenManager` 캐시 hit | get → get | adapter 호출 1회만 |
| `TokenManager` 만료 후 재발급 | freeze_time 으로 expires_at 과거 | adapter 호출 2회, 새 토큰 |
| `TokenManager` 동시 재발급 합체 | asyncio.gather([get, get, get]) on cold cache | adapter 호출 1회 |
| `TokenManager.invalidate` | invalidate → get | adapter 호출 발생 |

### 9.3 Smoke (`@pytest.mark.requires_kiwoom_real`)

CI 기본 skip. 로컬에서 운영 자격증명으로 1회 검증:

```python
@pytest.mark.requires_kiwoom_real
async def test_real_issue_token():
    creds = KiwoomCredentials(
        appkey=os.environ["KIWOOM_PROD_APPKEY"],
        secretkey=os.environ["KIWOOM_PROD_SECRETKEY"],
    )
    async with KiwoomAuthClient(base_url="https://api.kiwoom.com") as client:
        resp = await client.issue_token(creds)
    assert resp.token
    assert resp.token_type.lower() == "bearer"
    assert resp.expires_dt.startswith("20")
    # 즉시 폐기 — 운영 토큰을 테스트가 남기지 않음
    # (au10002 계획서의 KiwoomAuthClient.revoke_token 호출)
```

### 9.4 픽스처

```python
# tests/conftest.py
@pytest.fixture
def kiwoom_auth_mock_200() -> httpx.MockTransport:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "expires_dt": "20251107083713",
                "token_type": "bearer",
                "token": "X" * 150,
                "return_code": 0,
                "return_msg": "정상적으로 처리되었습니다",
            },
        )
    return httpx.MockTransport(handler)
```

---

## 10. 완료 기준 (DoD)

### 10.1 코드

- [ ] `app/security/kiwoom_credential_cipher.py` 작성 + 단위 테스트
- [ ] `app/application/dto/kiwoom_auth.py` (`KiwoomCredentials`, `IssuedToken`)
- [ ] `app/adapter/out/kiwoom/_exceptions.py` (5개 예외 클래스)
- [ ] `app/adapter/out/kiwoom/auth.py` (`KiwoomAuthClient.issue_token`) + Pydantic 모델
- [ ] `app/adapter/out/persistence/repositories/kiwoom_credential.py`
- [ ] `app/application/service/token_service.py` (`IssueKiwoomTokenUseCase`, `TokenManager`)
- [ ] `app/adapter/web/routers/auth.py` (`POST /api/kiwoom/auth/tokens` — 디버깅용)
- [ ] `app/adapter/web/_deps.py` 에 `get_token_manager` 추가
- [ ] `migrations/versions/001_init_kiwoom_schema.py` (`kiwoom_credential` + `kiwoom_token`)

### 10.2 테스트

- [ ] Unit 9 시나리오 (§9.1) 모두 PASS
- [ ] Integration 8 시나리오 (§9.2) 모두 PASS
- [ ] structlog 마스킹 검증 — `appkey`, `secretkey`, `token`, `authorization` 키가 `[MASKED]` 로 노출
- [ ] coverage `app/adapter/out/kiwoom/auth.py` ≥ 80%

### 10.3 운영 검증

- [ ] 운영 자격증명 1쌍을 `seed_credentials.py` 로 등록 (Fernet 암호화 확인)
- [ ] `POST /api/kiwoom/auth/tokens?alias=prod-main` 호출 → 200 + 마스킹 응답
- [ ] 키움 응답 `expires_dt` 의 timezone 확정 (KST/UTC) — 메모로 기록
- [ ] `authorization` 헤더 빈 문자열 vs 헤더 생략 둘 다 시도해 어느 쪽이 맞는지 확정
- [ ] DEBUG 로그로 응답 본문 확인 → JWT/hex 패턴이 모두 마스킹됐는지 grep

### 10.4 문서

- [ ] CHANGELOG 항목: `feat(kiwoom): au10001 access token issuance`
- [ ] `master.md` § 12 결정 기록에 `expires_dt` timezone 결정 추가
- [ ] `SPEC.md` 초안에 인증 섹션 작성

---

## 11. 위험 / 메모

### 11.1 결정 필요 항목

| # | 항목 | 옵션 | 권장 | 결정 시점 |
|---|------|------|------|-----------|
| 1 | `expires_dt` timezone | KST / UTC | 운영 dry-run 후 | DoD § 10.3 |
| 2 | `authorization` 헤더 | 빈 문자열 / 생략 | 운영 dry-run 후 | DoD § 10.3 |
| 3 | DB 토큰 캐시 사용 | 메모리 only / DB 병행 | 메모리 only (단순) | Phase H |
| 4 | 자격증명 라우터 노출 | yes / no | yes (admin only) | 본 endpoint 내 |
| 5 | 토큰 평문 응답 노출 | 절대 X / debug only | 절대 X | 본 endpoint 내 |

### 11.2 알려진 위험

- **응답 본문 마스킹 누락**: structlog 가 `token` 키는 잡지만, JSON 본문이 `dict` 가 아닌 `str` 로 들어가면 키 기반 매칭 실패. 정규식 fallback 이 토큰 패턴을 잡아내는지 검증 필요 (§9.1 마지막 시나리오)
- **재시도 시 타이밍 leak**: tenacity 가 401 도 재시도하면 자격증명 무차별 시도처럼 보일 위험. **401/403 은 재시도 금지** — `retry_if_exception_type(httpx.HTTPError)` 가 `KiwoomCredentialRejectedError` 를 catch 하지 않도록 확인
- **모의 vs 운영 토큰 혼용**: 같은 `TokenManager` 가 alias 별로 분리하므로 안전하지만, alias 명명 규칙(`prod-*` / `mock-*`) 을 README 에 강제 명시
- **토큰 만료 시점 race**: 만료 5분 전 재발급 마진이 키움 응답 시간(통상 200~500ms) 보다 충분히 큰지 운영 검증
- **expires_dt 가 14자리 미만 / 비숫자**: Pydantic 검증으로 즉시 fail → `KiwoomResponseValidationError` → 502
- **여러 워커 동시 발급**: 단일 워커 가정 (FastAPI uvicorn `--workers 1`). 다중 워커 전환 시 DB 토큰 캐시 필수

### 11.3 모의투자 한계

- **모의 도메인은 KRX 만**: `mockapi.kiwoom.com` 으로 발급한 토큰은 NXT 데이터 호출 시 키움이 어떻게 응답하는지 운영 검증 필요. 추정: 4xx 또는 빈 응답
- **권장 alias**: `prod-nxt-collector`, `mock-krx-tester` — env 와 용도를 alias 에 명시

### 11.4 향후 확장

- **2FA / IP 화이트리스트**: 키움이 추가 인증을 요구하면 `KiwoomAuthClient` 에 IP/HMAC 헤더 주입 옵션 추가
- **토큰 회전 자동화**: `expires_at` 1시간 전 백그라운드 사전 발급 → 만료 시점 race 완전 제거 (현재는 lazy 만료 후 발급)
- **다중 자격증명 풀**: 같은 운영 환경에 `prod-main`, `prod-backup` 등 여러 alias 등록 후 RPS 제한 우회 (키움 약관 확인 필요)

---

_Phase A 의 핵심 endpoint. 이 계획서가 완료되어야 나머지 24개 endpoint 가 모두 진행 가능하다._
