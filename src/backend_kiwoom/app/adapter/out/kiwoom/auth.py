"""KiwoomAuthClient — au10001 (issue) / au10002 (revoke 는 β chunk).

설계: endpoint-01-au10001.md § 6.

책임:
- httpx.AsyncClient 기반 단일 호출 트랜스포트 (KiwoomClient 공통 트랜스포트와 분리)
- 토큰 캐시 의존성 0 — 발급 자체이므로 stateless
- tenacity 재시도: 5xx · 네트워크 만. 401/403 (timing leak) / 429 (timing oracle, H3) / 비즈니스 / 검증 실패는 재시도 금지
- httpx.MockTransport 주입으로 테스트 외부 호출 0
- 응답 본문은 절대 로그/예외 메시지에 포함 안 됨 — Kiwoom 토큰은 plain alphanumeric 이라 패턴 마스킹 미보장

α chunk 범위: issue_token. revoke_token 은 β.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_fixed,
)
from tenacity.wait import wait_base

from app.adapter.out.kiwoom._exceptions import (
    KiwoomBusinessError,
    KiwoomCredentialRejectedError,
    KiwoomRateLimitedError,
    KiwoomResponseValidationError,
    KiwoomUpstreamError,
)
from app.application.dto.kiwoom_auth import KiwoomCredentials

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")


class TokenIssueRequest(BaseModel):
    """au10001 요청 본문. frozen + extra='forbid' 로 정적 안전성 강제.

    Pydantic 검증으로 사전 차단 — appkey/secretkey 길이·공백 제약을 wire 직전 강제.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    grant_type: Literal["client_credentials"] = "client_credentials"
    appkey: Annotated[str, Field(min_length=16, max_length=128, pattern=r"^\S+$")]
    secretkey: Annotated[str, Field(min_length=16, max_length=256, pattern=r"^\S+$")]

    def __repr__(self) -> str:
        tail = self.appkey[-4:] if len(self.appkey) >= 4 else "****"
        return f"TokenIssueRequest(appkey=••••{tail}, secretkey=<masked>)"


class TokenIssueResponse(BaseModel):
    """au10001 응답 본문. extra='ignore' — 키움 신규 필드 추가 호환.

    `__repr__` 에서 token 평문 마스킹 — 우발적 print/logging 노출 방어.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

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
        """`expires_dt` (YYYYMMDDHHMMSS) → KST tz-aware datetime.

        regex 가 `^\\d{14}$` 만 검증 — 논리상 잘못된 날짜(99991399999999) 는 strptime 이 ValueError.
        도메인 예외로 매핑 — 라우터에서 502 fail-fast (M2).

        F1 백포트: `from None` 은 `__suppress_context__=True` 만 set — `__context__` 는
        currently-raised exception 으로 자동 채워져 Sentry/structlog `walk_tb` leak 가능.
        변수 캡처 후 except 밖 raise 로 PEP 3134 자동 chaining 차단.
        """
        parse_failed = False
        parsed: datetime | None = None
        try:
            parsed = datetime.strptime(self.expires_dt, "%Y%m%d%H%M%S").replace(tzinfo=KST)
        except ValueError:
            parse_failed = True

        if parse_failed:
            raise KiwoomResponseValidationError("au10001 expires_dt 파싱 실패")
        if parsed is None:  # pragma: no cover — parse_failed 와 mutex
            raise RuntimeError("unreachable: parsed None without parse_failed")
        return parsed


class TokenRevokeRequest(BaseModel):
    """au10002 요청 본문. body 에 appkey + secretkey + token **3개 모두 평문**.

    `__repr__` 가 우발적 print/logging 시 secretkey/token 마스킹.
    실제 마스킹은 structlog `_scan` (1차) + `scrub_token_fields` helper (raw_response 2차).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    appkey: Annotated[str, Field(min_length=16, max_length=128, pattern=r"^\S+$")]
    secretkey: Annotated[str, Field(min_length=16, max_length=256, pattern=r"^\S+$")]
    token: Annotated[str, Field(min_length=20, max_length=1000)]

    def __repr__(self) -> str:
        tail = self.appkey[-4:] if len(self.appkey) >= 4 else "****"
        return f"TokenRevokeRequest(appkey=••••{tail}, secretkey=<masked>, token=<masked>)"


class TokenRevokeResponse(BaseModel):
    """au10002 응답 본문. extra='ignore' — 키움 신규 필드 추가 호환."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    return_code: int = 0
    return_msg: str = ""

    @property
    def succeeded(self) -> bool:
        return self.return_code == 0


class KiwoomAuthClient:
    """OAuth 발급/폐기 전용 어댑터.

    스코프: KiwoomClient 공통 트랜스포트와 분리 — 토큰 캐시 의존성 없는 독립 호출 가능.
    동시성: 인스턴스가 httpx.AsyncClient 1개 보유. caller 가 `async with` 로 수명 관리.

    재시도 정책 (issue_token):
    - KiwoomUpstreamError (5xx · 네트워크 · 파싱) → 재시도
    - KiwoomCredentialRejectedError (401/403) → 재시도 금지 (timing leak)
    - KiwoomRateLimitedError (429) → 재시도 금지 (timing oracle, H3 적대적 리뷰)
    - KiwoomBusinessError (return_code != 0) → 재시도 금지 (비즈니스 거부)
    - KiwoomResponseValidationError (Pydantic) → 재시도 금지

    예외 cause/context 정책 (H5 + F1 백포트):
    - Pydantic ValidationError 의 `errors()` / `input` 에 응답 본문(토큰 포함) 평문 들어 있음.
      Kiwoom 토큰은 plain alphanumeric 이라 structlog 패턴 매칭으로 마스킹 미보장.
    - F1 백포트 이전: `from None` 사용 → `__suppress_context__=True` 만 set, `__context__`
      는 currently-raised exception 으로 자동 채워져 Sentry/structlog `walk_tb(__context__)`
      가 토큰 평문 노출 위험 (A3-α C-1 발견 — _client.py 와 동일 패턴).
    - F1 백포트 후: 변수 캡처 + except 밖 raise — PEP 3134 자동 chaining 차단.
      `__context__ is None` + `__cause__ is None` 둘 다 보장.
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
        max_attempts: int = 3,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 8.0,
    ) -> None:
        timeout = httpx.Timeout(
            connect=5.0,
            read=timeout_seconds,
            write=timeout_seconds,
            pool=5.0,
        )
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, transport=transport)
        self._max_attempts = max_attempts
        self._retry_min_wait = retry_min_wait
        self._retry_max_wait = retry_max_wait

    def _wait_strategy(self) -> wait_base:
        if self._retry_max_wait <= 0.0:
            return wait_fixed(0)
        return wait_exponential(
            multiplier=1.0,
            min=self._retry_min_wait,
            max=self._retry_max_wait,
        )

    async def issue_token(self, credentials: KiwoomCredentials) -> TokenIssueResponse:
        """au10001 호출. 재시도 후에도 실패 시 도메인 예외 전파."""
        retrying = AsyncRetrying(
            retry=retry_if_exception_type(KiwoomUpstreamError),
            stop=stop_after_attempt(self._max_attempts),
            wait=self._wait_strategy(),
            reraise=True,
        )
        async for attempt in retrying:
            with attempt:
                return await self._do_issue_token(credentials)
        raise RuntimeError("unreachable")  # pragma: no cover

    async def _do_issue_token(self, credentials: KiwoomCredentials) -> TokenIssueResponse:
        # F1: `from None` → 변수 캡처 + except 밖 raise (PEP 3134 자동 chaining 차단).
        # 이유: `from None` 은 `__suppress_context__=True` 만 set, `__context__` 는 살아있어
        # Sentry/structlog `walk_tb(__context__)` 가 토큰/평문 노출 가능.
        # _client.py / stkinfo.py 패턴 일관.

        # Pydantic 사전 검증 — wire 전에 appkey/secretkey 형식 강제 (HIGH 1차 리뷰)
        request_validation_failed = False
        request_body: dict[str, Any] = {}
        try:
            request_body = TokenIssueRequest(
                appkey=credentials.appkey,
                secretkey=credentials.secretkey,
            ).model_dump()
        except ValidationError:
            request_validation_failed = True

        if request_validation_failed:
            raise KiwoomResponseValidationError("au10001 요청 검증 실패")

        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "api-id": "au10001",
        }

        # 네트워크 호출 — 변수 캡처 후 except 밖 raise
        network_error_type = ""
        resp_or_none: httpx.Response | None = None
        try:
            resp_or_none = await self._client.post("/oauth2/token", json=request_body, headers=headers)
        except (httpx.HTTPError, OSError) as exc:
            # OSError 포함 — ssl.SSLError, 일부 transport 가 raw OSError 를 raise (M4)
            network_error_type = type(exc).__name__

        if network_error_type:
            raise KiwoomUpstreamError(f"au10001 네트워크 오류: {network_error_type}")
        if resp_or_none is None:  # pragma: no cover — network_error_type 와 mutex
            raise RuntimeError("unreachable: resp_or_none None without network error")
        resp = resp_or_none

        # 응답 본문은 어떤 경로로도 메시지/로그에 포함 안 됨 — Kiwoom 토큰 plain alphanumeric 마스킹 미보장
        if resp.status_code in (401, 403):
            logger.debug("au10001 status=%d", resp.status_code)
            raise KiwoomCredentialRejectedError(f"키움 자격증명 거부: HTTP {resp.status_code}")
        if resp.status_code == 429:
            logger.debug("au10001 status=429 rate-limited")
            # 재시도 금지 — 429 timing oracle 방어 (H3)
            raise KiwoomRateLimitedError("au10001 429 — 키움 RPS 초과")
        if resp.status_code != 200:
            logger.debug("au10001 status=%d", resp.status_code)
            raise KiwoomUpstreamError(f"au10001 발급 실패: HTTP {resp.status_code}")

        # JSON 파싱 — 변수 캡처 후 except 밖 raise
        json_parse_error_type = ""
        body_json: dict[str, Any] = {}
        try:
            parsed = resp.json()
        except ValueError as exc:
            json_parse_error_type = type(exc).__name__
        else:
            if not isinstance(parsed, dict):
                raise KiwoomUpstreamError(f"au10001 응답이 dict 아님 — {type(parsed).__name__}")
            body_json = parsed

        if json_parse_error_type:
            raise KiwoomUpstreamError(f"au10001 응답 JSON 파싱 실패: {json_parse_error_type}")

        return_code = body_json.get("return_code", 0)
        if not isinstance(return_code, int):
            raise KiwoomResponseValidationError("au10001 응답 return_code 타입 오류")
        if return_code != 0:
            raise KiwoomBusinessError(
                api_id="au10001",
                return_code=return_code,
                message=str(body_json.get("return_msg", "")),
            )

        # Pydantic 응답 검증 — 변수 캡처 후 except 밖 raise (input 에 토큰 평문 보존, H5)
        response_validation_failed = False
        validated: TokenIssueResponse | None = None
        try:
            validated = TokenIssueResponse.model_validate(body_json)
        except ValidationError:
            response_validation_failed = True

        if response_validation_failed:
            # 본문 미포함 + cause/context chain 차단 — Pydantic ValidationError input 에 토큰 평문
            logger.debug("au10001 response validation failed — body suppressed")
            raise KiwoomResponseValidationError("au10001 응답 검증 실패")
        if validated is None:  # pragma: no cover — response_validation_failed 와 mutex
            raise RuntimeError("unreachable: validated None without validation failure")
        return validated

    # =========================================================================
    # au10002 — revoke_token (β chunk)
    # =========================================================================

    async def revoke_token(
        self,
        credentials: KiwoomCredentials,
        token: str,
    ) -> TokenRevokeResponse:
        """접근토큰 폐기. **재시도 없음** — best-effort.

        설계 (endpoint-02-au10002.md § 6.1):
        - 멱등성 보장이 키움 측에서 안 되므로 caller 가 swallow/throw 결정
        - 자동 재시도 시 "이미 폐기됨" 응답에 대한 동작이 모호해짐
        - 401/403 은 UseCase 가 idempotent (already-expired) 변환 책임

        F1 백포트: 모든 `from None` 위치를 변수 캡처 + except 밖 raise 패턴으로
        리팩토링 (PEP 3134 자동 `__context__` chaining 차단 — _client.py 일관).
        """
        # Pydantic 사전 검증 — appkey/secretkey/token 형식 강제 (au10001 과 동일 패턴)
        request_validation_failed = False
        request_body: dict[str, Any] = {}
        try:
            request_body = TokenRevokeRequest(
                appkey=credentials.appkey,
                secretkey=credentials.secretkey,
                token=token,
            ).model_dump()
        except ValidationError:
            request_validation_failed = True

        if request_validation_failed:
            raise KiwoomResponseValidationError("au10002 요청 검증 실패")

        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "api-id": "au10002",
            "authorization": f"Bearer {token}",
        }

        # 네트워크 호출 — 변수 캡처 후 except 밖 raise
        network_error_type = ""
        resp_or_none: httpx.Response | None = None
        try:
            resp_or_none = await self._client.post("/oauth2/revoke", json=request_body, headers=headers)
        except (httpx.HTTPError, OSError) as exc:
            network_error_type = type(exc).__name__

        if network_error_type:
            raise KiwoomUpstreamError(f"au10002 네트워크 오류: {network_error_type}")
        if resp_or_none is None:  # pragma: no cover — network_error_type 와 mutex
            raise RuntimeError("unreachable: resp_or_none None without network error")
        resp = resp_or_none

        if resp.status_code in (401, 403):
            logger.debug("au10002 status=%d", resp.status_code)
            raise KiwoomCredentialRejectedError(f"키움 폐기 거부: HTTP {resp.status_code} (이미 만료된 토큰일 수 있음)")
        if resp.status_code == 429:
            logger.debug("au10002 status=429 rate-limited")
            raise KiwoomRateLimitedError("au10002 429 — 키움 RPS 초과")
        if resp.status_code != 200:
            logger.debug("au10002 status=%d", resp.status_code)
            raise KiwoomUpstreamError(f"au10002 폐기 실패: HTTP {resp.status_code}")

        # JSON 파싱 — 변수 캡처 후 except 밖 raise
        json_parse_error_type = ""
        body_json: dict[str, Any] = {}
        try:
            parsed = resp.json()
        except ValueError as exc:
            json_parse_error_type = type(exc).__name__
        else:
            if not isinstance(parsed, dict):
                raise KiwoomUpstreamError(f"au10002 응답이 dict 아님 — {type(parsed).__name__}")
            body_json = parsed

        if json_parse_error_type:
            raise KiwoomUpstreamError(f"au10002 응답 JSON 파싱 실패: {json_parse_error_type}")

        return_code = body_json.get("return_code", 0)
        if not isinstance(return_code, int):
            raise KiwoomResponseValidationError("au10002 응답 return_code 타입 오류")
        if return_code != 0:
            raise KiwoomBusinessError(
                api_id="au10002",
                return_code=return_code,
                message=str(body_json.get("return_msg", "")),
            )

        # Pydantic 응답 검증 — 변수 캡처 후 except 밖 raise
        response_validation_failed = False
        validated: TokenRevokeResponse | None = None
        try:
            validated = TokenRevokeResponse.model_validate(body_json)
        except ValidationError:
            response_validation_failed = True

        if response_validation_failed:
            logger.debug("au10002 response validation failed — body suppressed")
            raise KiwoomResponseValidationError("au10002 응답 검증 실패")
        if validated is None:  # pragma: no cover — response_validation_failed 와 mutex
            raise RuntimeError("unreachable: validated None without validation failure")
        return validated

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> KiwoomAuthClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()
