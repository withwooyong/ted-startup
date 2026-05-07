# endpoint-02-au10002.md — 접근토큰 폐기

## 0. 메타

| 항목 | 값 |
|------|-----|
| API ID | `au10002` |
| API 명 | 접근토큰 폐기 |
| 분류 | Tier 1 (인증 — 위생 관리) |
| Phase | **A** |
| 우선순위 | **P0** |
| Method | `POST` |
| URL | `/oauth2/revoke` |
| 운영 도메인 | `https://api.kiwoom.com` |
| 모의투자 도메인 | `https://mockapi.kiwoom.com` (KRX 만 지원) |
| Content-Type | `application/json;charset=UTF-8` |
| 의존 endpoint | `au10001` (발급된 토큰이 있어야 폐기 가능) |
| 후속 endpoint | 없음 (cleanup 역할) |

---

## 1. 목적

발급된 접근토큰을 키움 측에서 무효화한다.

**왜 필요한가**:
- **자격증명 회전 (rotation)**: appkey/secretkey 를 교체할 때 기존 토큰을 즉시 무력화
- **운영 사고 대응**: 토큰이 로그/외부에 노출되었을 경우 즉시 폐기 → 키움 측 무효화 보장
- **테스트 위생**: smoke 테스트(`requires_kiwoom_real`)가 발급한 토큰을 즉시 폐기해 TTL(통상 24h) 까지 활성화된 토큰을 남기지 않음
- **Graceful shutdown**: 프로세스 종료 시 메모리 캐시의 토큰을 폐기 → 좀비 토큰 최소화

**왜 별도 endpoint 로 분리하는가**:
- au10001 발급과 의미·실패 시점이 완전히 다름 (cleanup vs 블로커)
- 테스트 종료 hook 이 본 endpoint 를 호출하므로 안정성과 idempotency 가 중요
- 폐기 실패가 후속 호출을 막아서는 안 됨 — UseCase 가 best-effort 로 동작해야 함

---

## 2. Request 명세

### 2.1 Header

| Element | 한글명 | Type | Required | Length | Description |
|---------|-------|------|----------|--------|-------------|
| `api-id` | TR 명 | String | Y | 10 | `"au10002"` 고정 |
| `authorization` | 접근토큰 | String | Y | 1000 | `Bearer <token>` 형식. **폐기 대상 토큰을 헤더로도 보내야 하는지 운영 검증 필요** (스펙은 Y, body 에도 token 있음 → 중복 가능성) |
| `cont-yn` | 연속조회 여부 | String | N | 1 | 미사용 |
| `next-key` | 연속조회 키 | String | N | 50 | 미사용 |

### 2.2 Body

| Element | 한글명 | Type | Required | Description |
|---------|-------|------|----------|-------------|
| `appkey` | 앱키 | String | Y | 발급 시와 동일한 값 |
| `secretkey` | 시크릿키 | String | Y | 발급 시와 동일한 값 |
| `token` | 접근토큰 | String | Y | 폐기할 토큰 (au10001 응답의 `token`) |

> **주의**: au10001 과 달리 `grant_type` 은 없다.

### 2.3 Request 예시

```json
POST https://api.kiwoom.com/oauth2/revoke
Content-Type: application/json;charset=UTF-8
api-id: au10002
authorization: Bearer WQJCwyqInphKnR3bSRtB9NE1lv...

{
    "appkey": "AxserEsdcredca.....",
    "secretkey": "SEefdcwcforehDre2fdvc....",
    "token": "WQJCwyqInphKnR3bSRtB9NE1lv..."
}
```

### 2.4 Pydantic 모델

```python
# app/adapter/out/kiwoom/auth.py
class TokenRevokeRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    appkey: Annotated[str, Field(min_length=16, max_length=128, pattern=r"^\S+$")]
    secretkey: Annotated[str, Field(min_length=16, max_length=256, pattern=r"^\S+$")]
    token: Annotated[str, Field(min_length=20, max_length=1000)]

    def __repr__(self) -> str:
        tail = self.appkey[-4:] if len(self.appkey) >= 4 else "****"
        return f"TokenRevokeRequest(appkey=••••{tail}, secretkey=<masked>, token=<masked>)"
```

---

## 3. Response 명세

### 3.1 Header

| Element | 한글명 | Type | Description |
|---------|-------|------|-------------|
| `api-id` | TR 명 | String | `"au10002"` 에코 |
| `cont-yn` | 연속조회 여부 | String | 미사용 |
| `next-key` | 연속조회 키 | String | 미사용 |

### 3.2 Body

스펙 표는 Body 필드를 명시하지 않지만, 응답 예시에 `return_code`, `return_msg` 가 등장.

| Element | 한글명 | Type | Description |
|---------|-------|------|-------------|
| `return_code` | 처리 코드 | Integer | `0` = 정상 폐기 |
| `return_msg` | 처리 메시지 | String | 한글 메시지 |

### 3.3 Response 예시

```json
{
    "return_code": 0,
    "return_msg": "정상적으로 처리되었습니다"
}
```

### 3.4 Pydantic 모델

```python
class TokenRevokeResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
    return_code: int = 0
    return_msg: str = ""

    @property
    def succeeded(self) -> bool:
        return self.return_code == 0
```

---

## 4. NXT 처리

| 항목 | 적용 여부 |
|------|-----------|
| `stk_cd` 에 `_NX` suffix | N |
| `nxt_enable` 게이팅 | N |
| `mrkt_tp` 별 분리 호출 | N |

토큰 폐기는 도메인(prod/mock) 단위 — au10001 과 동일 도메인으로 호출해야 함.

---

## 5. DB 스키마

### 5.1 영향 받는 테이블

신규 테이블 없음. 단, **`kiwoom_token` 테이블을 사용 중이라면**(Phase H 결정) 폐기 성공 시 해당 row 삭제.

### 5.2 (선택) 폐기 감사 로그

운영 사고 추적용 — 누가/언제/어떤 alias 의 토큰을 폐기했는지 기록.

```sql
-- Phase A 에서는 미생성. 필요해지면 나중에 추가.
CREATE TABLE kiwoom.kiwoom_token_audit (
    id              BIGSERIAL PRIMARY KEY,
    credential_id   BIGINT NOT NULL,
    action          VARCHAR(20) NOT NULL CHECK (action IN ('issued', 'revoked', 'expired')),
    actor           VARCHAR(50),                          -- 'admin-api', 'shutdown-hook', 'test-cleanup' 등
    reason          TEXT,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

> MVP 에서는 structlog 로그로 대체. 필요 시 Phase H 에서 도입.

---

## 6. UseCase / Service / Adapter

### 6.1 Adapter 메서드 — `KiwoomAuthClient.revoke_token()`

```python
# app/adapter/out/kiwoom/auth.py (au10001 과 동일 모듈)

class KiwoomAuthClient:
    # ... issue_token (au10001) 생략 ...

    async def revoke_token(
        self,
        credentials: KiwoomCredentials,
        token: str,
    ) -> TokenRevokeResponse:
        """접근토큰 폐기. 재시도 없음 — 멱등성 보장이 키움 측에서 안 되므로 안전판.

        실패 시 caller 가 best-effort 로 swallow 할지 throw 할지 결정한다.
        """
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "api-id": "au10002",
            "authorization": f"Bearer {token}",
        }
        body = {
            "appkey": credentials.appkey,
            "secretkey": credentials.secretkey,
            "token": token,
        }
        try:
            resp = await self._client.post("/oauth2/revoke", json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise KiwoomUpstreamError(f"토큰 폐기 네트워크 오류: {exc}") from exc

        if resp.status_code in (401, 403):
            # 이미 만료된 토큰을 폐기 시도 → 멱등 성공으로 간주할지 운영 검증
            logger.debug("au10002 401/403 body: %s", resp.text[:200])
            raise KiwoomCredentialRejectedError(
                f"키움 폐기 요청 거부: HTTP {resp.status_code} (이미 만료된 토큰일 수 있음)"
            )
        if resp.status_code != 200:
            logger.debug("au10002 %d body: %s", resp.status_code, resp.text[:200])
            raise KiwoomUpstreamError(f"토큰 폐기 실패: HTTP {resp.status_code}")

        body_json = resp.json()
        return_code = body_json.get("return_code", 0)
        if return_code != 0:
            raise KiwoomBusinessError(
                api_id="au10002",
                return_code=return_code,
                message=body_json.get("return_msg", ""),
            )
        return TokenRevokeResponse.model_validate(body_json)
```

> **재시도 없음 의도**: 폐기는 best-effort. 네트워크 오류 시 caller 가 결정. 자동 재시도하면 "이미 폐기됨" 응답에 어떻게 반응할지 모호해짐.

### 6.2 UseCase — `RevokeKiwoomTokenUseCase`

```python
# app/application/service/token_service.py

class RevokeKiwoomTokenUseCase:
    """alias 또는 명시 token 으로 폐기 + 메모리 캐시 무효화.

    두 모드:
      - by_alias: 캐시에 있는 토큰을 폐기. 캐시에 없으면 no-op (이미 만료/없음).
      - by_token: 외부에서 들어온 임의 토큰을 폐기 (운영 사고 대응).
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        cipher: KiwoomCredentialCipher,
        auth_client_factory: Callable[[str], KiwoomAuthClient],
        token_manager: TokenManager,
    ) -> None:
        self._session = session
        self._cipher = cipher
        self._factory = auth_client_factory
        self._token_manager = token_manager
        self._cred_repo = KiwoomCredentialRepository(session, cipher)

    async def revoke_by_alias(self, *, alias: str) -> RevokeResult:
        """캐시에 있는 토큰을 키움 측에 폐기 + 캐시 무효화.

        캐시에 없으면 best-effort 성공 반환 (이미 폐기/만료 가정).
        """
        token = self._token_manager.peek(alias=alias)  # 캐시 조회 only, 발급 안 함
        if token is None:
            logger.info("revoke skipped: alias=%s 캐시에 토큰 없음 (already-revoked 가정)", alias)
            return RevokeResult(alias=alias, revoked=False, reason="cache-miss")

        cred_row = await self._cred_repo.find_by_alias(alias)
        if cred_row is None:
            raise CredentialNotFoundError(f"alias={alias} 미등록")
        creds = await self._cred_repo.decrypt(cred_row)
        base_url = (
            settings.kiwoom_base_url_prod if cred_row.env == "prod"
            else settings.kiwoom_base_url_mock
        )

        try:
            async with self._factory(base_url) as client:
                await client.revoke_token(creds, token.token)
        except KiwoomCredentialRejectedError as exc:
            # 이미 만료된 토큰을 폐기 시도 — 멱등 성공으로 간주
            logger.info("revoke 401/403 → idempotent success: alias=%s", alias)
            self._token_manager.invalidate(alias=alias)
            return RevokeResult(alias=alias, revoked=False, reason="already-expired")
        finally:
            # 키움 측 결과와 무관하게 로컬 캐시는 무효화
            self._token_manager.invalidate(alias=alias)

        return RevokeResult(alias=alias, revoked=True, reason="ok")

    async def revoke_by_raw_token(
        self,
        *,
        alias: str,
        raw_token: str,
    ) -> RevokeResult:
        """캐시 외부의 임의 토큰을 폐기 — 운영 사고 대응.

        예: 토큰이 외부 로그에 노출됨 → DBA 가 평문으로 들고 와서 즉시 폐기 요청.
        """
        cred_row = await self._cred_repo.find_by_alias(alias)
        if cred_row is None:
            raise CredentialNotFoundError(f"alias={alias} 미등록")
        creds = await self._cred_repo.decrypt(cred_row)
        base_url = (
            settings.kiwoom_base_url_prod if cred_row.env == "prod"
            else settings.kiwoom_base_url_mock
        )
        async with self._factory(base_url) as client:
            await client.revoke_token(creds, raw_token)
        # 캐시 무효화 — 같은 토큰이면 정리, 다른 토큰이면 무영향
        self._token_manager.invalidate(alias=alias)
        return RevokeResult(alias=alias, revoked=True, reason="ok-raw")


@dataclass(frozen=True, slots=True)
class RevokeResult:
    alias: str
    revoked: bool                          # 키움 측에서 실제로 폐기 발생했는가
    reason: str                            # 'ok' | 'cache-miss' | 'already-expired' | 'ok-raw'
```

### 6.3 `TokenManager` 확장

au10001 계획서의 `TokenManager` 에 두 메서드 추가:

```python
class TokenManager:
    # ... 이전 코드 생략 ...

    def peek(self, *, alias: str) -> IssuedToken | None:
        """캐시 조회만 — 만료 여부 무관. 폐기 UseCase 가 사용."""
        return self._cache.get(alias)

    async def invalidate_all(self) -> None:
        """프로세스 종료 hook 용 — 모든 alias 의 캐시 비움.

        실제 키움 측 폐기는 호출자가 RevokeKiwoomTokenUseCase 로 별도 수행.
        """
        self._cache.clear()
```

---

## 7. 배치 / 트리거

| 트리거 | 설명 |
|--------|------|
| **Graceful shutdown hook** | FastAPI `lifespan` 종료 단계에서 활성 alias 전부 폐기 시도 |
| **수동 폐기 라우터** | `DELETE /api/kiwoom/auth/tokens/{alias}` (admin) |
| **자격증명 회전 시** | `BrokerageCredentialUseCase.replace` 같은 경로에서 호출 |
| **테스트 cleanup** | smoke 테스트의 fixture teardown |

### 7.1 라우터

```python
# app/adapter/web/routers/auth.py

@router.delete(
    "/tokens/{alias}",
    response_model=RevokeTokenResponse,
    dependencies=[Depends(require_admin_key)],
)
async def revoke_token_by_alias(
    alias: str = Path(..., min_length=1, max_length=50),
    use_case: RevokeKiwoomTokenUseCase = Depends(get_revoke_use_case),
) -> RevokeTokenResponse:
    """alias 의 캐시 토큰을 키움 측 폐기 + 로컬 캐시 무효화."""
    try:
        result = await use_case.revoke_by_alias(alias=alias)
    except CredentialNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return RevokeTokenResponse(
        alias=result.alias,
        revoked=result.revoked,
        reason=result.reason,
    )


@router.post(
    "/tokens/revoke-raw",
    response_model=RevokeTokenResponse,
    dependencies=[Depends(require_admin_key)],
)
async def revoke_raw_token(
    body: RevokeRawTokenRequest,
    use_case: RevokeKiwoomTokenUseCase = Depends(get_revoke_use_case),
) -> RevokeTokenResponse:
    """긴급 — 외부에 노출된 토큰을 명시 폐기.

    Body 의 token 평문은 router 에서만 보유, 응답에 재노출 금지.
    """
    try:
        result = await use_case.revoke_by_raw_token(alias=body.alias, raw_token=body.token)
    except CredentialNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return RevokeTokenResponse(
        alias=result.alias,
        revoked=result.revoked,
        reason=result.reason,
    )
```

### 7.2 Graceful shutdown

```python
# app/main.py
@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    # 종료 단계 — 활성 토큰 폐기 (best-effort)
    manager: TokenManager = app.state.token_manager
    factory: Callable[[], RevokeKiwoomTokenUseCase] = app.state.revoke_use_case_factory
    aliases = list(manager.alias_keys())
    for alias in aliases:
        try:
            uc = factory()
            await uc.revoke_by_alias(alias=alias)
        except Exception:
            logger.warning("shutdown 폐기 실패 alias=%s — 키움 TTL 까지 활성", alias, exc_info=True)
    await manager.invalidate_all()
```

---

## 8. 에러 처리

| HTTP / 응답 | 도메인 예외 | 라우터 매핑 | 처리 정책 |
|-------------|-------------|-------------|-----------|
| 200 + `return_code=0` | — | 200 | 정상 폐기 |
| 401 / 403 | `KiwoomCredentialRejectedError` (UseCase 가 idempotent 처리) | 200 (`revoked=False, reason='already-expired'`) | 이미 만료/폐기된 토큰 → 멱등 성공으로 변환 |
| 5xx, 네트워크 | `KiwoomUpstreamError` | 502 | 재시도 없음 — caller 가 swallow 결정 |
| `return_code != 0` | `KiwoomBusinessError` | 400 + detail | 비즈니스 에러 (예: 잘못된 appkey) |
| `CredentialNotFoundError` | — | 404 | alias 미등록 |
| 캐시 miss (revoke_by_alias) | — | 200 (`revoked=False, reason='cache-miss'`) | best-effort — 이미 없는 토큰은 폐기 불필요 |

### 8.1 멱등성 정책

키움이 "이미 만료/폐기된 토큰"을 어떻게 응답하는지 운영 검증으로 확정 필요. 후보:
- **A** — 200 + `return_code=0` (멱등 응답): UseCase 가 변환 불필요
- **B** — 401/403: UseCase 가 `KiwoomCredentialRejectedError` 를 catch 해 `RevokeResult(revoked=False, reason='already-expired')` 로 변환 (현재 구현)
- **C** — `return_code != 0` + 특정 코드: 그 코드를 화이트리스트로 idempotent 처리 추가

운영 dry-run (DoD § 10.3) 후 결정.

### 8.2 본문 보호

au10001 과 동일 — Body 에 `appkey/secretkey/token` 3개 모두 포함되므로 마스킹 검증이 더 중요.

```python
# 결과 검증 (수동 grep)
$ python scripts/issue_token.py --alias prod-main 2>&1 | grep -E "(appkey|secret|token)"
# → 모든 출력이 [MASKED] 또는 [MASKED_HEX] / [MASKED_JWT] 여야 함
```

---

## 9. 테스트

### 9.1 Unit (MockTransport)

`tests/adapter/kiwoom/test_auth_client.py` (au10001 와 같은 파일):

| 시나리오 | 입력 | 기대 |
|----------|------|------|
| 정상 폐기 | 200 + `return_code=0` | `TokenRevokeResponse.succeeded=True` |
| 401 (만료된 토큰 폐기) | 401 응답 | `KiwoomCredentialRejectedError` (UseCase 가 idempotent 변환) |
| 403 | 403 응답 | `KiwoomCredentialRejectedError` |
| 500 | 500 응답 | `KiwoomUpstreamError` (재시도 없음 → 1회 호출 확인) |
| `return_code=1` | 200 + 비즈니스 에러 | `KiwoomBusinessError(code=1)` |
| 본문 마스킹 | logger.debug capture | `appkey`/`secretkey`/`token` 모두 마스킹 |

### 9.2 Integration

`tests/application/test_token_service.py`:

| 시나리오 | 셋업 | 기대 |
|----------|------|------|
| `revoke_by_alias` 정상 | 캐시에 토큰 있음 + MockTransport 200 | `RevokeResult(revoked=True, reason='ok')` + 캐시 비워짐 |
| `revoke_by_alias` 캐시 miss | 캐시 비어있음 | `RevokeResult(revoked=False, reason='cache-miss')` + adapter 호출 0 |
| `revoke_by_alias` 401 (만료) | 캐시 토큰 + MockTransport 401 | `RevokeResult(revoked=False, reason='already-expired')` + 캐시 비워짐 |
| `revoke_by_raw_token` | 외부 토큰 주입 | adapter 호출 1회 + 캐시 무효화 |
| `revoke_by_alias` credential 미등록 | seed 없음 | `CredentialNotFoundError` |
| Graceful shutdown 다중 alias | 캐시 3개 토큰 | adapter 호출 3회 + 모두 캐시 비워짐 |
| Graceful shutdown 한 개 실패 | alias B 가 502 | A/C 는 폐기, B 는 경고 로그 + 진행 계속 |

### 9.3 Smoke

```python
@pytest.mark.requires_kiwoom_real
async def test_real_issue_then_revoke():
    creds = KiwoomCredentials(
        appkey=os.environ["KIWOOM_PROD_APPKEY"],
        secretkey=os.environ["KIWOOM_PROD_SECRETKEY"],
    )
    async with KiwoomAuthClient(base_url="https://api.kiwoom.com") as client:
        issued = await client.issue_token(creds)
        revoke_resp = await client.revoke_token(creds, issued.token)
    assert revoke_resp.succeeded
    # 같은 토큰 재폐기 → idempotency 확인 (운영 응답 결정 → 표 § 8.1 업데이트)
    async with KiwoomAuthClient(base_url="https://api.kiwoom.com") as client:
        # 두 번째 호출 — 키움이 어떻게 응답하는지 기록
        try:
            await client.revoke_token(creds, issued.token)
            print("idempotent: 200 응답")
        except KiwoomCredentialRejectedError:
            print("idempotent: 401/403 응답")
```

---

## 10. 완료 기준 (DoD)

### 10.1 코드

- [ ] `KiwoomAuthClient.revoke_token` 메서드 + Pydantic 모델
- [ ] `RevokeKiwoomTokenUseCase` (`revoke_by_alias`, `revoke_by_raw_token`)
- [ ] `TokenManager.peek`, `TokenManager.invalidate_all`, `TokenManager.alias_keys`
- [ ] `RevokeResult` dataclass
- [ ] 라우터: `DELETE /api/kiwoom/auth/tokens/{alias}` + `POST /api/kiwoom/auth/tokens/revoke-raw`
- [ ] `app/main.py` lifespan 에 graceful shutdown hook
- [ ] `tests/conftest.py` 에 `kiwoom_auth_revoke_mock_200` 픽스처

### 10.2 테스트

- [ ] Unit 6 시나리오 (§9.1) PASS
- [ ] Integration 7 시나리오 (§9.2) PASS
- [ ] coverage `revoke_token` 경로 ≥ 80%
- [ ] 마스킹: `appkey`, `secretkey`, `token` 3개 키 모두 로그에서 `[MASKED]` 확인

### 10.3 운영 검증

- [ ] 발급 → 폐기 → 같은 토큰으로 ka10001 호출 → 401/403 받는지 확인 (실제 폐기 작동)
- [ ] 같은 토큰 2회 폐기 → 키움 응답 패턴 결정 (§8.1 표 업데이트)
- [ ] Graceful shutdown 시 운영 환경에서 토큰이 실제로 폐기되는지 docker stop 후 키움 활성 토큰 수 확인 (가능하다면)
- [ ] `authorization` 헤더 + body 의 `token` 중복이 키움에서 허용되는지 확인

### 10.4 문서

- [ ] CHANGELOG: `feat(kiwoom): au10002 access token revocation + graceful shutdown`
- [ ] `master.md` § 12 결정 기록에 키움 멱등성 응답 패턴 추가

---

## 11. 위험 / 메모

### 11.1 결정 필요 항목

| # | 항목 | 옵션 | 결정 시점 |
|---|------|------|-----------|
| 1 | 만료된 토큰 폐기 시 키움 응답 (200 / 401 / return_code) | 운영 dry-run | DoD § 10.3 |
| 2 | `authorization` 헤더 + body `token` 중복 허용 여부 | 운영 dry-run | DoD § 10.3 |
| 3 | Graceful shutdown 폐기 timeout | 5s / 10s / skip | 본 endpoint 내 (현재 default) |
| 4 | `kiwoom_token_audit` 테이블 도입 | yes / no | Phase H |

### 11.2 알려진 위험

- **Shutdown hook 타임아웃**: K8s 가 SIGTERM 후 30s grace period 안에 lifespan 이 끝나야 함. alias 가 많으면(예: 10+) 각 폐기에 1~2s 소요. 동시 폐기로 단축 또는 timeout 설정 필요
- **재발급 race**: 폐기 직후 같은 alias 로 `TokenManager.get` 호출이 들어오면 자동 재발급 → 의도와 어긋남. shutdown 시 `manager.invalidate_all` 후 새 발급 차단 플래그 필요할 수 있음
- **로컬 캐시 vs 키움 측 상태 불일치**: 캐시는 비웠는데 키움 측 폐기 실패 → 좀비 토큰. structlog 경고 + 운영 모니터링 (alias 별 활성 토큰 수가 1을 초과하면 알람)
- **재시도 없음의 trade-off**: 일시 네트워크 오류로 폐기 실패 시 운영 사고 대응이 늦어짐. 운영 검증 후 retry 1~2회 추가 검토
- **본문 마스킹 회귀**: au10002 는 body 에 `appkey/secretkey/token` 3개를 모두 평문으로 보냄. 향후 코드 변경 시 본문이 INFO 로그로 누출되지 않게 핵심 회귀 테스트 1건 (`test_logging_masking.py::test_au10002_body_masked`)
- **테스트 토큰 격리**: smoke 테스트는 매번 새 토큰을 발급·폐기. 잊고 폐기 안 하면 키움 측에 24h 살아있는 토큰 누적 → 항상 try/finally 로 폐기

### 11.3 알리아스 명명 규칙

운영 사고 대응이 빠르려면:

```
prod-main          : 운영 데이터 수집 메인
prod-backup        : RPS 우회 (필요 시)
prod-on-call       : 운영자 임시 디버깅용
mock-ci            : CI 환경
mock-dev           : 개발자 로컬
```

폐기 라우터를 호출할 때 alias 가 prod-* 이면 추가 confirmation 헤더 (예: `X-Confirm-Prod: yes`) 를 요구하는 가드 검토.

### 11.4 향후 확장

- **Bulk revoke**: `POST /api/kiwoom/auth/tokens:revoke-all?env=prod` — 운영 사고 시 한 방
- **Audit log persistence**: §5.2 의 `kiwoom_token_audit` 도입 + Grafana 대시보드
- **Auto-revoke on credential change**: `kiwoom_credential` UPDATE 트리거로 기존 토큰 자동 폐기

---

_au10001 과 짝을 이루는 cleanup endpoint. graceful shutdown / 자격증명 회전 / 운영 사고 대응 3가지 시나리오에서 작동 보장이 필요._
