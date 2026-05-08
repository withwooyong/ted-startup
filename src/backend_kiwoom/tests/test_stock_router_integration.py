"""POST /api/kiwoom/stocks/sync 풀 체인 통합 — 라우터 → 실 UseCase → MockTransport → DB.

#1 stock_master_service 단위 테스트가 UseCase 풀 체인을 다루고, #2 stock_router
단위 테스트가 admin guard / DTO / F3 hint 를 다룸. 본 모듈은 그 둘을 묶은 회귀 1
케이스 — main.py lifespan 의 factory 패턴이 라우터에서 정상 동작하는지.

KiwoomCredential row 생성 + ASGI 라우터 → 실 SyncStockMasterUseCase → MockTransport
→ testcontainers PG16 → stock 테이블 적재 검증.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.adapter.out.kiwoom._client import KiwoomClient
from app.adapter.out.kiwoom.auth import KiwoomAuthClient
from app.adapter.out.kiwoom.stkinfo import KiwoomStkInfoClient
from app.adapter.out.persistence.models import Stock
from app.adapter.out.persistence.repositories.kiwoom_credential import (
    KiwoomCredentialRepository,
)
from app.adapter.out.persistence.repositories.stock import StockRepository
from app.adapter.web._deps import get_sync_stock_factory
from app.adapter.web.routers.stocks import router as stocks_router
from app.application.dto.kiwoom_auth import KiwoomCredentials
from app.application.service.stock_master_service import SyncStockMasterUseCase
from app.application.service.token_service import TokenManager
from app.security.kiwoom_credential_cipher import KiwoomCredentialCipher


@pytest.fixture
def admin_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    key = "test-admin-stock-integration"
    monkeypatch.setenv("ADMIN_API_KEY", key)
    from app.config.settings import get_settings

    get_settings.cache_clear()
    yield key
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def commit_engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(database_url, pool_pre_ping=True)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def commit_sessionmaker(
    commit_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=commit_engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def cleanup_db(
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[None]:
    """stock + credential 테이블 매 테스트마다 비움."""
    from app.adapter.out.persistence.models import KiwoomCredential

    async with commit_sessionmaker() as s:
        await s.execute(delete(Stock))
        await s.execute(delete(KiwoomCredential))
        await s.commit()
    yield
    async with commit_sessionmaker() as s:
        await s.execute(delete(Stock))
        await s.execute(delete(KiwoomCredential))
        await s.commit()


@pytest.mark.asyncio
async def test_router_post_sync_full_chain_writes_to_db(
    admin_key: str,
    cleanup_db: None,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
    master_key: str,
) -> None:
    """라우터 POST /stocks/sync → 실 UseCase factory → MockTransport → DB 적재."""
    cipher = KiwoomCredentialCipher(master_key=master_key)

    # 1. 자격증명 시드
    async with commit_sessionmaker() as s:
        repo = KiwoomCredentialRepository(s, cipher)
        await repo.upsert(
            alias="test-stock-integration",
            env="prod",
            credentials=KiwoomCredentials(
                appkey="A" * 20,
                secretkey="S" * 30,
            ),
        )
        await s.commit()

    # 2. MockTransport — au10001 + ka10099 (5 시장 응답)
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/oauth2/token":
            return httpx.Response(
                200,
                json={
                    "expires_dt": "20991231235959",
                    "token_type": "bearer",
                    "token": "T" * 50,
                    "return_code": 0,
                    "return_msg": "ok",
                },
            )
        if path == "/api/dostk/stkinfo":
            body = request.content.decode()
            for mrkt in ("0", "10", "50", "60", "6"):
                if f'"mrkt_tp": "{mrkt}"' in body or f'"mrkt_tp":"{mrkt}"' in body:
                    return httpx.Response(
                        200,
                        json={
                            "return_code": 0,
                            "return_msg": "ok",
                            "list": [
                                {
                                    "code": f"M{mrkt}001",
                                    "name": f"종목-{mrkt}",
                                    "marketCode": mrkt,
                                    "listCount": "0000000000001000",
                                    "regDay": "20200101",
                                    "lastPrice": "00010000",
                                    "nxtEnable": "Y" if mrkt in ("0", "10") else "N",
                                    "state": "정상",
                                    "marketName": "거래소",
                                    "upName": "전기전자",
                                    "upSizeName": "대형주",
                                    "auditInfo": "",
                                    "companyClassName": "",
                                    "orderWarning": "0",
                                }
                            ],
                        },
                    )
            raise AssertionError(f"unmatched mrkt_tp: {body}")
        raise AssertionError(f"unmatched path: {path}")

    transport = httpx.MockTransport(handler)

    # 3. TokenManager
    @asynccontextmanager
    async def _session_provider() -> AsyncIterator[AsyncSession]:
        async with commit_sessionmaker() as s:
            yield s

    def _auth_factory(base_url: str) -> KiwoomAuthClient:
        return KiwoomAuthClient(
            base_url=base_url,
            transport=transport,
            max_attempts=1,
            retry_min_wait=0.0,
            retry_max_wait=0.0,
        )

    manager = TokenManager(
        session_provider=_session_provider,
        cipher=cipher,
        auth_client_factory=_auth_factory,
    )

    # 4. SyncStockMasterUseCaseFactory — main.py lifespan 패턴 그대로
    @asynccontextmanager
    async def _sync_factory(
        alias: str,
    ) -> AsyncIterator[SyncStockMasterUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        kiwoom_client = KiwoomClient(
            base_url="https://api.kiwoom.com",
            token_provider=_token_provider,
            transport=transport,
            max_attempts=1,
            retry_min_wait=0.0,
            retry_max_wait=0.0,
            min_request_interval_seconds=0.0,
        )
        try:
            stkinfo = KiwoomStkInfoClient(kiwoom_client)
            yield SyncStockMasterUseCase(
                session_provider=_session_provider,
                stkinfo_client=stkinfo,
                mock_env=False,  # prod 모드 — 응답 nxtEnable 그대로
            )
        finally:
            await kiwoom_client.close()

    # 5. ASGI 앱 + dependency override
    app = FastAPI()
    app.include_router(stocks_router)
    app.dependency_overrides[get_sync_stock_factory] = lambda: _sync_factory

    # 6. 호출
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        resp = await client.post(
            "/api/kiwoom/stocks/sync",
            params={"alias": "test-stock-integration"},
            headers={"X-API-Key": admin_key},
        )

    # 7. 응답 검증
    assert resp.status_code == 200
    body = resp.json()
    assert body["all_succeeded"] is True
    assert body["total_upserted"] == 5  # 5 시장 x 1 row
    assert body["total_nxt_enabled"] == 2  # KOSPI + KOSDAQ 만 nxtEnable=Y

    # 8. DB 검증 — 실제로 stock 테이블 적재됨
    async with commit_sessionmaker() as s:
        repo_check = StockRepository(s)
        all_rows = await repo_check.list_by_filters(only_active=True)

    assert len(all_rows) == 5
    assert {r.market_code for r in all_rows} == {"0", "10", "50", "60", "6"}
    nxt_codes = {r.stock_code for r in all_rows if r.nxt_enable}
    assert nxt_codes == {"M0001", "M10001"}
