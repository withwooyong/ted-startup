"""KiwoomClient — 모든 키움 데이터 endpoint 의 공통 트랜스포트.

설계: master.md § 6.1 / 6.2 / 6.3 / 6.4. au10001/au10002 는 별도 KiwoomAuthClient 사용.

책임:
- httpx.AsyncClient 1개 — caller 가 `async with` 로 수명 관리
- 토큰 자동 헤더 — `token_provider` 매 호출마다 호출 (캐시는 provider 책임 = TokenManager)
- tenacity 재시도 — KiwoomUpstreamError + KiwoomRateLimitedError. 401/403/4xx 비즈니스 즉시 fail
- Rate limit — `asyncio.Semaphore(N)` + 호출 간 최소 인터벌 분산 (의도: N 동시 + 1/N RPS)
- Pagination — `cont-yn=Y` 인 동안 `next-key` 헤더 반복. `max_pages` hard cap

에러 분류 정책 (α 와 일관):
- 401/403 → KiwoomCredentialRejectedError (재시도 X)
- 429 → KiwoomRateLimitedError (재시도 후 fail)
- 5xx · 네트워크 · 파싱 → KiwoomUpstreamError (재시도)
- return_code != 0 → KiwoomBusinessError
- Pydantic 검증 → caller 책임 (어댑터 단계)

응답 본문 보호 정책 (α 정책 일관 + α3-α 1R 적대적 리뷰 C-1 보강):
- body 어떤 경로로도 logger / 예외 메시지에 미포함
- HTTP status / api_id / return_code 만 디버깅 메타로 사용
- 헤더 인젝션 차단: 토큰 / cont-yn / next-key 모두 화이트리스트 정규식 검증
- exception cause/context 차단: `_clear_chain()` 으로 `__cause__`/`__context__`/`__suppress_context__` 모두 정리
  (이유: `from None` 은 `__suppress_context__=True` 만 set, `__context__` 는 살아있음 → Sentry/structlog
   `walk_tb(exc.__context__)` 가 토큰 평문 노출 위험)

페이지네이션 계약 (1R 1차 리뷰 HIGH-1 보강):
- `call_paginated` 는 async generator. caller 가 `break` 또는 미완 iteration 시 generator 가
  GC 또는 `aclose()` 로 finalize. 내부에 외부 리소스 미보유 — break 안전.
- max_pages 도달 시 `KiwoomMaxPagesExceededError` raise (무한 cont-yn=Y 방어).
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Final

import httpx
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
    KiwoomError,
    KiwoomRateLimitedError,
    KiwoomUpstreamError,
)

logger = logging.getLogger(__name__)

# C-1 적대적 리뷰: 토큰 / 페이지네이션 헤더 값에 \r\n / control char 가 들어가면
# httpx h11 의 LocalProtocolError 가 본문(토큰 평문 포함)을 메시지에 박아 raise.
# wire 전 정규식 검증으로 차단 — 화이트리스트 charset (base64 + url-safe + JWT prefix).
_VALID_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._\-+/=]+$")
_VALID_NEXT_KEY_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._\-+/=]+$")


def _clear_chain(exc: BaseException) -> None:
    """exception cause / context 완전 차단 — `from None` 의 __context__ leak 우회.

    Python 동작:
    - `raise NewExc from None` → __cause__ = None, __suppress_context__ = True
    - 그러나 __context__ 는 자동으로 currently-raised exception 으로 채워짐
    - traceback formatting 은 suppress 되지만 raw attribute 는 살아있어 walk_tb 가 leak

    해결: 새 exception 의 __context__ 를 명시 None, __suppress_context__ True 둘 다 set.
    """
    exc.__cause__ = None
    exc.__context__ = None
    exc.__suppress_context__ = True


@dataclass(frozen=True, slots=True)
class KiwoomResponse:
    """파싱된 키움 응답 — body + pagination 메타."""

    body: dict[str, Any]
    cont_yn: str | None
    next_key: str | None
    status_code: int


class KiwoomMaxPagesExceededError(KiwoomError):
    """`call_paginated` 가 `max_pages` 한도 도달 — 무한 cont-yn=Y 위험 차단.

    의도: 키움 응답이 영원히 cont-yn=Y 를 반환하는 상황 방어. 운영 모니터링 알람.

    필드 (D-1 follow-up § 13.2 #6):
        api_id: 비식별 메타 (어떤 endpoint 가 초과했는지).
        page:   도달한 페이지 수 (cap 과 동일 — 마지막 page 가 cont-yn=Y).
        cap:    `max_pages` 한도 값.
    """

    def __init__(self, *, api_id: str, page: int, cap: int) -> None:
        super().__init__(
            f"{api_id} call_paginated max_pages={cap} 초과 (page={page}) — 무한 페이지네이션 위험"
        )
        self.api_id = api_id
        self.page = page
        self.cap = cap


class KiwoomClient:
    """모든 키움 데이터 endpoint (`/api/dostk/*`) 의 공통 트랜스포트.

    토큰 처리:
    - `token_provider` 가 매 호출마다 호출됨 → 항상 fresh 토큰 사용
    - TokenManager 가 제공: `lambda: token_manager.get(alias=alias).then(.token)`
    - 만료된 토큰은 호출 전 token_provider 가 재발급 책임 (margin=300s)

    동시성:
    - `Semaphore(concurrent_requests)` 로 동시 호출 수 제한 (기본 4 RPS 마진)
    - 호출 간 `min_request_interval_seconds` (기본 0.25s) 유지 — `_last_call_ts` lock 보호

    재시도:
    - tenacity AsyncRetrying — KiwoomUpstreamError + KiwoomRateLimitedError 만 재시도
    - 401/403 (`KiwoomCredentialRejectedError`) / 비즈니스 에러 / 검증 실패는 즉시 fail
    """

    def __init__(
        self,
        base_url: str,
        *,
        token_provider: Callable[[], Awaitable[str]],
        timeout_seconds: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
        max_attempts: int = 3,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 8.0,
        concurrent_requests: int = 4,
        min_request_interval_seconds: float = 0.25,
    ) -> None:
        timeout = httpx.Timeout(
            connect=5.0,
            read=timeout_seconds,
            write=timeout_seconds,
            pool=5.0,
        )
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, transport=transport)
        self._token_provider = token_provider
        self._max_attempts = max_attempts
        self._retry_min_wait = retry_min_wait
        self._retry_max_wait = retry_max_wait
        self._semaphore = asyncio.Semaphore(concurrent_requests)
        self._min_interval = min_request_interval_seconds
        # 다음 호출 가능 시각 — `_throttle` 이 lock 안에서 atomic 갱신
        self._next_slot_ts = 0.0
        self._interval_lock = asyncio.Lock()

    def _wait_strategy(self) -> wait_base:
        if self._retry_max_wait <= 0.0:
            return wait_fixed(0)
        return wait_exponential(
            multiplier=1.0,
            min=self._retry_min_wait,
            max=self._retry_max_wait,
        )

    async def _throttle(self) -> None:
        """호출 간 최소 인터벌 보장 — H2 적대적 리뷰 보강.

        의도: N 동시 호출 + 1/N RPS — 4 코루틴이 0/250/500/750ms 간격으로 분산 호출.
        설계: `_interval_lock` 안에서 `_next_slot_ts` **만** atomic 갱신 (sleep 없음),
        sleep 은 lock 밖에서 수행 → 다른 코루틴이 동시에 자기 슬롯 계산 가능.
        결과: Semaphore(4) + 인터벌 250ms = 4 동시 in-flight + 4 RPS 준수.
        """
        if self._min_interval <= 0.0:
            return
        async with self._interval_lock:
            now = time.monotonic()
            wait_until = max(self._next_slot_ts, now)
            self._next_slot_ts = wait_until + self._min_interval
            sleep_for = wait_until - now
        if sleep_for > 0:
            await asyncio.sleep(sleep_for)

    async def call(
        self,
        *,
        api_id: str,
        endpoint: str,
        body: dict[str, Any],
        cont_yn: str | None = None,
        next_key: str | None = None,
    ) -> KiwoomResponse:
        """단일 키움 endpoint 호출. 재시도 후에도 실패 시 도메인 예외 전파."""
        retrying = AsyncRetrying(
            retry=retry_if_exception_type((KiwoomUpstreamError, KiwoomRateLimitedError)),
            stop=stop_after_attempt(self._max_attempts),
            wait=self._wait_strategy(),
            reraise=True,
        )
        async for attempt in retrying:
            with attempt:
                return await self._do_call(
                    api_id=api_id,
                    endpoint=endpoint,
                    body=body,
                    cont_yn=cont_yn,
                    next_key=next_key,
                )
        raise RuntimeError("unreachable")  # pragma: no cover

    async def _do_call(
        self,
        *,
        api_id: str,
        endpoint: str,
        body: dict[str, Any],
        cont_yn: str | None,
        next_key: str | None,
    ) -> KiwoomResponse:
        # H1 적대적 리뷰: caller 에서 받은 페이지네이션 헤더 값 사전 검증 (헤더 인젝션 차단)
        # `raise` 가 except 밖이라 __context__ 자동 설정 안 됨 (PEP 3134)
        # 빈 문자열은 정상 (페이지네이션 미시작 또는 종료 — 키움 운영 응답 실측 2026-05-09)
        if cont_yn is not None and cont_yn.upper() not in ("Y", "N"):
            raise KiwoomUpstreamError(f"{api_id} cont-yn 형식 오류")
        if next_key not in (None, "") and not _VALID_NEXT_KEY_PATTERN.fullmatch(next_key or ""):
            raise KiwoomUpstreamError(f"{api_id} next-key 형식 오류")

        # Semaphore + 인터벌 — 키움 RPS 안전 마진
        # 네트워크 오류 정보는 변수 캡처 후 Semaphore 밖에서 raise — `__context__` leak 차단 (C-1)
        network_error_type = ""
        async with self._semaphore:
            await self._throttle()
            token = await self._token_provider()

            # C-1 적대적 리뷰: 토큰 형식 사전 검증 — \r\n / control char 헤더 인젝션 차단
            if not _VALID_TOKEN_PATTERN.fullmatch(token):
                # except 밖 raise — __context__ None 보장
                raise KiwoomCredentialRejectedError(f"{api_id} 토큰 형식 검증 실패 — 발급 흐름 점검 필요")

            headers: dict[str, str] = {
                "Content-Type": "application/json;charset=UTF-8",
                "api-id": api_id,
                "authorization": f"Bearer {token}",
            }
            if cont_yn is not None:
                headers["cont-yn"] = cont_yn
            if next_key is not None:
                headers["next-key"] = next_key

            resp_or_none: httpx.Response | None = None
            try:
                resp_or_none = await self._client.post(endpoint, json=body, headers=headers)
            except (httpx.HTTPError, OSError) as exc:
                # C-1: 변수만 캡처. raise 는 except 밖에서 — __context__ 자동 설정 차단.
                # exc 의 메시지에 토큰 평문 박혀 있을 수 있어 cause/context 모두 차단 필요.
                network_error_type = type(exc).__name__

        # except 블록 종료 후 raise → __context__ 자동 설정 안 됨 (C-1 핵심)
        if network_error_type:
            raise KiwoomUpstreamError(f"{api_id} 네트워크 오류: {network_error_type}")
        # mypy narrowing — network_error_type 비었으면 resp_or_none 은 항상 non-None
        if resp_or_none is None:  # pragma: no cover — except 분기와 mutex
            raise RuntimeError("unreachable: resp_or_none None without network error")
        resp = resp_or_none

        # 응답 본문은 logger / 예외 메시지에 미포함 — α 정책 일관. 모두 except 밖 raise.
        if resp.status_code in (401, 403):
            logger.debug("%s status=%d", api_id, resp.status_code)
            raise KiwoomCredentialRejectedError(f"키움 자격증명 거부: HTTP {resp.status_code} ({api_id})")
        if resp.status_code == 429:
            logger.debug("%s status=429 rate-limited", api_id)
            raise KiwoomRateLimitedError(f"{api_id} 429 — 키움 RPS 초과")
        if resp.status_code != 200:
            logger.debug("%s status=%d", api_id, resp.status_code)
            raise KiwoomUpstreamError(f"{api_id} 호출 실패: HTTP {resp.status_code}")

        # JSON 파싱 — 같은 패턴 (변수 캡처 후 except 밖 raise)
        json_parse_error_type = ""
        body_json: dict[str, Any] = {}
        try:
            parsed = resp.json()
        except ValueError as exc:
            json_parse_error_type = type(exc).__name__
        else:
            if not isinstance(parsed, dict):
                # 직접 raise OK — except 밖
                raise KiwoomUpstreamError(f"{api_id} 응답이 dict 아님 — {type(parsed).__name__}")
            body_json = parsed

        if json_parse_error_type:
            raise KiwoomUpstreamError(f"{api_id} 응답 JSON 파싱 실패: {json_parse_error_type}")

        return_code = body_json.get("return_code", 0)
        if not isinstance(return_code, int):
            raise KiwoomUpstreamError(f"{api_id} 응답 return_code 타입 오류")
        if return_code != 0:
            raise KiwoomBusinessError(
                api_id=api_id,
                return_code=return_code,
                message=str(body_json.get("return_msg", "")),
            )

        # H1: 응답 헤더의 cont-yn / next-key 값도 검증 (다음 호출 시 헤더로 들어감)
        # 빈 문자열은 정상 — 키움이 페이지네이션 종료 시 next-key="" 반환 (실측 2026-05-09)
        cont_yn_resp = resp.headers.get("cont-yn")
        next_key_resp = resp.headers.get("next-key")
        if cont_yn_resp is not None and cont_yn_resp.upper() not in ("Y", "N"):
            raise KiwoomUpstreamError(f"{api_id} 응답 cont-yn 형식 오류")
        if next_key_resp not in (None, "") and not _VALID_NEXT_KEY_PATTERN.fullmatch(next_key_resp or ""):
            raise KiwoomUpstreamError(f"{api_id} 응답 next-key 형식 오류")

        return KiwoomResponse(
            body=body_json,
            cont_yn=cont_yn_resp,
            next_key=next_key_resp,
            status_code=resp.status_code,
        )

    async def call_paginated(
        self,
        *,
        api_id: str,
        endpoint: str,
        body: dict[str, Any],
        max_pages: int = 50,
    ) -> AsyncIterator[KiwoomResponse]:
        """`cont-yn=Y` 인 동안 페이지네이션. 첫 호출엔 페이지 헤더 없음.

        무한 루프 차단: `max_pages` 도달 시 KiwoomMaxPagesExceededError raise.
        """
        cont_yn: str | None = None
        next_key: str | None = None
        page_count = 0

        while page_count < max_pages:
            page_count += 1
            page = await self.call(
                api_id=api_id,
                endpoint=endpoint,
                body=body,
                cont_yn=cont_yn,
                next_key=next_key,
            )
            yield page

            # 종료 조건: cont-yn 헤더 없음 / "N" / 빈 문자열
            if not page.cont_yn or page.cont_yn.upper() != "Y":
                return

            # 다음 페이지 — next-key 헤더 세팅
            cont_yn = "Y"
            next_key = page.next_key

        # 여기 도달 = max_pages 한도 초과 (마지막 페이지가 cont-yn=Y)
        raise KiwoomMaxPagesExceededError(api_id=api_id, page=page_count, cap=max_pages)

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> KiwoomClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()
