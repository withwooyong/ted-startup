"""KIS 잔고 조회 port — application layer 의 outbound abstraction.

Hexagonal DIP: UseCase 는 이 Protocol 과 예외 타입만 참조해 adapter 구현을 모름.
`KisClient`(adapter) 가 structural typing 으로 `KisHoldingsFetcher` 를 만족 —
명시 상속 없이 메서드 시그니처 일치로 자동 구현체가 된다.

예외 의미 분리:
- `KisUpstreamError`: 5xx / 네트워크 / 파싱 장애 → 라우터 502
- `KisCredentialRejectedError`(KisUpstreamError): HTTP 401/403 자격증명 거부 → 라우터 400
"""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Protocol

from app.application.dto.kis import KisCredentials, KisHoldingRow


class KisUpstreamError(Exception):
    """KIS API 일반 오류 — 토큰 네트워크/파싱/업스트림 5xx.

    Adapter 내부의 HTTP·파싱 에러는 전부 이 타입(또는 서브클래스) 으로 수렴된다.
    UseCase 는 `KisCredentialRejectedError` 를 먼저 catch 해 credential 거부 경로로
    분기하고, 남은 `KisUpstreamError` 는 `SyncError` 로 승격.
    """


class KisCredentialRejectedError(KisUpstreamError):
    """KIS 업스트림이 HTTP 401/403 으로 자격증명을 거부 — 사용자 재등록 필요.

    `KisUpstreamError` 의 서브클래스. UseCase 는 이 예외를 먼저 catch 해
    도메인 `CredentialRejectedError` 로 승격, 라우터가 HTTP 400 매핑.
    """


class KisHoldingsFetcher(Protocol):
    """KIS 잔고 조회 port.

    `KisClient`(adapter) 가 structural 하게 만족. UseCase 는 이 Protocol 과
    port 예외만 import 해 adapter 구현에 직접 의존하지 않는다.

    async context manager 시그니처 포함 — REAL 경로는 요청 스코프로 커넥션 풀
    정리가 필요하므로 `async with fetcher as client:` 패턴을 port 계약으로 명시.
    """

    async def fetch_balance(self) -> list[KisHoldingRow]: ...

    async def test_connection(self) -> None: ...

    async def __aenter__(self) -> KisHoldingsFetcher: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...


KisRealFetcherFactory = Callable[[KisCredentials], KisHoldingsFetcher]
"""실 KIS 호출용 팩토리 — 요청 스코프 `KisHoldingsFetcher` 생성.

계좌별 credential 이 달라 프로세스 공유 불가. `async with factory(creds) as client:`
로 요청 스코프를 열고 `__aexit__` 에서 커넥션 풀 정리.
"""
