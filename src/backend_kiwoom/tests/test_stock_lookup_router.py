"""GET /api/kiwoom/stocks/{stock_code} + POST .../refresh 라우터 (B-β).

httpx.AsyncClient + ASGITransport 패턴 (test_stock_router 와 일관).

GET /{stock_code} 시나리오:
1. 존재하는 stock 조회 → 200 + StockOut
2. 미존재 stock 조회 → 404
3. stock_code 형식 위반 (5자리, 영문) → 422
4. _NX suffix → 422

POST /{stock_code}/refresh 시나리오:
5. admin key 누락 → 401
6. admin key 잘못 → 401
7. ADMIN_API_KEY 미설정 → 401 (fail-closed)
8. 정상 refresh → 200 + StockOut
9. KiwoomBusinessError (존재하지 않는 종목) → 400 + return_code/msg detail
10. KiwoomCredentialRejectedError → 400
11. KiwoomUpstreamError → 502
12. KiwoomRateLimitedError → 503
13. alias 미등록 → 404
14. alias 비활성 → 400
15. alias 한도 초과 → 503
16. alias 쿼리 누락 → 422
17. stock_code 형식 위반 → 422
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.web._deps import get_lookup_stock_factory
from app.adapter.web.routers.stocks import router as stocks_router

# =============================================================================
# 픽스처
# =============================================================================


@pytest.fixture(autouse=True)
def _clear_global_engine_cache() -> Iterator[None]:
    """전역 get_engine/get_sessionmaker lru_cache 의 stale event loop binding 해소.

    테스트마다 새 engine 을 그 테스트의 event loop 에 바인딩 — 다른 테스트 파일에서
    먼저 호출된 캐시가 남아있을 수 있음. test_stock_router.py 의 combined GET 테스트도
    같은 이슈를 안고 있어 ka10100 추가로 노출됨. 라우터가 Depends 로 sessionmaker 를
    주입받지 않는 한 테스트 단계의 캐시 클리어가 필요.
    """
    from app.adapter.out.persistence.session import get_engine, get_sessionmaker

    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    yield
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()


@pytest.fixture
def admin_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    key = "test-admin-key-lookup"
    monkeypatch.setenv("ADMIN_API_KEY", key)
    from app.config.settings import get_settings

    get_settings.cache_clear()
    yield key
    get_settings.cache_clear()


def _make_app(factory=None) -> FastAPI:
    app = FastAPI()
    app.include_router(stocks_router)
    if factory is not None:
        app.dependency_overrides[get_lookup_stock_factory] = lambda: factory
    return app


def _async_client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


def _stock_row(stock_code: str = "005930") -> Any:
    """가짜 Stock ORM-like 객체 (StockOut.from_attributes 호환)."""

    class _FakeStock:
        id = 42
        stock_code = "005930"
        stock_name = "삼성전자"
        list_count = 26034239
        audit_info = "정상"
        listed_date = date(2009, 8, 3)
        last_price = 136000
        state = "정상"
        market_code = "0"
        market_name = "거래소"
        up_name = "전기전자"
        up_size_name = "대형주"
        company_class_name = ""
        order_warning = "0"
        nxt_enable = True
        is_active = True
        fetched_at = datetime(2026, 1, 1, tzinfo=UTC)

    f = _FakeStock()
    f.stock_code = stock_code  # type: ignore[assignment]
    return f


class _StubLookupUseCase:
    def __init__(self, *, execute_result=None, execute_error=None) -> None:
        self._result = execute_result
        self._error = execute_error
        self.execute_calls: list[str] = []

    async def execute(self, stock_code: str):
        self.execute_calls.append(stock_code)
        if self._error is not None:
            raise self._error
        return self._result if self._result is not None else _stock_row(stock_code)


def _stub_factory(*, execute_result=None, execute_error=None):
    @asynccontextmanager
    async def _factory(alias: str) -> AsyncIterator[Any]:
        yield _StubLookupUseCase(execute_result=execute_result, execute_error=execute_error)

    return _factory


def _failing_factory(exception: Exception):
    @asynccontextmanager
    async def _factory(alias: str) -> AsyncIterator[Any]:
        raise exception
        yield  # pragma: no cover

    return _factory


# =============================================================================
# GET /{stock_code} — DB only
# =============================================================================


@pytest.mark.asyncio
async def test_get_stock_by_code_404_and_path_validations(session: AsyncSession) -> None:
    """빈 DB 단건 GET 의 4 케이스를 한 client lifetime 안에서 검증.

    분리 시 module-level get_sessionmaker() lru_cache 의 stale asyncpg connection 이
    다음 테스트의 다른 event loop 에서 close 되며 RuntimeError 발생 — test_stock_router
    의 기존 combined GET 테스트와 같은 이슈 (`session` fixture 동반).

    검증:
    - 미존재 6자리 종목 → 404 (DB hit)
    - 5자리 → 422 (Path pattern 검증)
    - 영문 포함 → 422
    - `_NX` suffix → 422
    """
    app = _make_app()

    async with _async_client(app) as client:
        resp_404 = await client.get("/api/kiwoom/stocks/999999")
        resp_short = await client.get("/api/kiwoom/stocks/00593")
        resp_alpha = await client.get("/api/kiwoom/stocks/ABC123")
        resp_nx = await client.get("/api/kiwoom/stocks/005930_NX")

    assert resp_404.status_code == 404
    assert resp_short.status_code == 422
    assert resp_alpha.status_code == 422
    assert resp_nx.status_code == 422


# =============================================================================
# POST /{stock_code}/refresh — admin guard
# =============================================================================


@pytest.mark.asyncio
async def test_refresh_rejects_missing_admin_key(admin_key: str) -> None:
    app = _make_app(factory=_stub_factory())

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/005930/refresh",
            params={"alias": "test"},
        )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rejects_wrong_admin_key(admin_key: str) -> None:
    app = _make_app(factory=_stub_factory())

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/005930/refresh",
            params={"alias": "test"},
            headers={"X-API-Key": "WRONG-KEY"},
        )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_fails_closed_when_admin_key_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    from app.config.settings import get_settings

    get_settings.cache_clear()
    try:
        app = _make_app(factory=_stub_factory())
        async with _async_client(app) as client:
            resp = await client.post(
                "/api/kiwoom/stocks/005930/refresh",
                params={"alias": "test"},
                headers={"X-API-Key": "anything"},
            )
        assert resp.status_code == 401
    finally:
        get_settings.cache_clear()


# =============================================================================
# POST /refresh — 정상/오류 매핑
# =============================================================================


@pytest.mark.asyncio
async def test_refresh_returns_stock_out_on_success(admin_key: str) -> None:
    app = _make_app(factory=_stub_factory())

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/005930/refresh",
            params={"alias": "prod-main"},
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["stock_code"] == "005930"
    assert body["stock_name"] == "삼성전자"
    assert body["nxt_enable"] is True
    assert body["is_active"] is True


@pytest.mark.asyncio
async def test_refresh_business_error_returns_400(admin_key: str) -> None:
    """KiwoomBusinessError → 400.

    1R 2b H1 — return_msg 평문 echo 차단. detail 에는 return_code + 클래스명만.
    return_msg 본문은 절대 응답 body 에 포함되면 안 됨 (B-α M-2 정책 일관).
    """
    from app.adapter.out.kiwoom._exceptions import KiwoomBusinessError

    secret_msg = "키움-내부-자격증명-hint-AAA-BBB-CCC"
    err = KiwoomBusinessError(api_id="ka10100", return_code=1, message=secret_msg)
    app = _make_app(factory=_stub_factory(execute_error=err))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/999999/refresh",
            params={"alias": "prod-main"},
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 400
    body = resp.json()
    detail = body.get("detail")
    assert isinstance(detail, dict)
    assert detail.get("return_code") == 1
    assert detail.get("error") == "KiwoomBusinessError"
    # 1R 2b H1 회귀 가드 — 응답 본문에 키움 message 평문 포함 금지
    assert secret_msg not in resp.text, "return_msg 평문 echo 회귀 — B-α M-2 백포트 깨짐"
    assert "return_msg" not in detail, "detail 에 return_msg 키 노출 금지"


@pytest.mark.asyncio
async def test_refresh_value_error_mapped_not_500(admin_key: str) -> None:
    """1R 2b H2 회귀 — listCount/lastPrice 비숫자 시 raw ValueError → 500 누설 차단.

    LookupStockUseCase.execute 내부에서 KiwoomResponseValidationError 로 매핑되어야 함.
    라우터 except 망에서 502 로 응답.
    """
    from app.adapter.out.kiwoom._exceptions import KiwoomResponseValidationError

    app = _make_app(factory=_stub_factory(execute_error=KiwoomResponseValidationError("정규화 실패")))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/005930/refresh",
            params={"alias": "prod-main"},
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 502, "ValueError → KiwoomResponseValidationError → 502"
    assert resp.status_code != 500, "raw ValueError 누설 회귀 — H2 fix 깨짐"


@pytest.mark.asyncio
async def test_refresh_credential_rejected_returns_400(admin_key: str) -> None:
    from app.adapter.out.kiwoom._exceptions import KiwoomCredentialRejectedError

    app = _make_app(factory=_stub_factory(execute_error=KiwoomCredentialRejectedError("401")))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/005930/refresh",
            params={"alias": "prod-main"},
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_refresh_upstream_error_returns_502(admin_key: str) -> None:
    from app.adapter.out.kiwoom._exceptions import KiwoomUpstreamError

    app = _make_app(factory=_stub_factory(execute_error=KiwoomUpstreamError("HTTP 502")))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/005930/refresh",
            params={"alias": "prod-main"},
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_refresh_rate_limited_returns_503(admin_key: str) -> None:
    from app.adapter.out.kiwoom._exceptions import KiwoomRateLimitedError

    app = _make_app(factory=_stub_factory(execute_error=KiwoomRateLimitedError("429")))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/005930/refresh",
            params={"alias": "prod-main"},
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 503


# =============================================================================
# POST /refresh — alias 매핑
# =============================================================================


@pytest.mark.asyncio
async def test_refresh_alias_not_found_returns_404(admin_key: str) -> None:
    from app.application.service.token_service import CredentialNotFoundError

    app = _make_app(factory=_failing_factory(CredentialNotFoundError("alias=missing")))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/005930/refresh",
            params={"alias": "missing"},
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_refresh_alias_inactive_returns_400(admin_key: str) -> None:
    from app.application.service.token_service import CredentialInactiveError

    app = _make_app(factory=_failing_factory(CredentialInactiveError("alias=inactive")))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/005930/refresh",
            params={"alias": "inactive"},
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_refresh_alias_capacity_exceeded_returns_503(admin_key: str) -> None:
    from app.application.service.token_service import AliasCapacityExceededError

    app = _make_app(factory=_failing_factory(AliasCapacityExceededError("max=5")))

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/005930/refresh",
            params={"alias": "test"},
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_refresh_alias_query_required(admin_key: str) -> None:
    """alias 쿼리 누락 → 422."""
    app = _make_app(factory=_stub_factory())

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/005930/refresh",
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_refresh_rejects_invalid_stock_code(admin_key: str) -> None:
    """5자리 stock_code → 422."""
    app = _make_app(factory=_stub_factory())

    async with _async_client(app) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/ABC123/refresh",
            params={"alias": "prod-main"},
            headers={"X-API-Key": admin_key},
        )

    assert resp.status_code == 422
