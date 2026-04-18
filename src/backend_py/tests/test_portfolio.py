"""P10 포트폴리오 도메인 — Repository · UseCase · Router 통합 테스트."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.models import (
    BrokerageAccount,
    PortfolioHolding,
    PortfolioSnapshot,
    Stock,
    StockPrice,
)
from app.adapter.out.persistence.repositories import (
    BrokerageAccountRepository,
    PortfolioHoldingRepository,
    PortfolioSnapshotRepository,
    PortfolioTransactionRepository,
    StockPriceRepository,
    StockRepository,
)
from app.adapter.web._deps import get_session as prod_get_session
from app.application.service.portfolio_service import (
    AccountAliasConflictError,
    ComputePerformanceUseCase,
    ComputeSnapshotUseCase,
    InsufficientHoldingError,
    InvalidRealEnvironmentError,
    RecordTransactionUseCase,
    RegisterAccountUseCase,
    TransactionRecord,
)
from app.config.settings import get_settings
from app.main import create_app


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest_asyncio.fixture
async def app_with_session(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[FastAPI]:
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")
    get_settings.cache_clear()
    app = create_app()

    async def _override() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[prod_get_session] = _override
    try:
        yield app
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


@pytest_asyncio.fixture
async def client(app_with_session: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app_with_session)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-API-Key": "test-admin-key"},
    ) as c:
        yield c


async def _seed_stocks(session: AsyncSession) -> dict[str, Stock]:
    repo = StockRepository(session)
    samsung = await repo.add(Stock(stock_code="005930", stock_name="삼성전자", market_type="KOSPI"))
    sk = await repo.add(Stock(stock_code="000660", stock_name="SK하이닉스", market_type="KOSPI"))
    return {"samsung": samsung, "sk": sk}


# -----------------------------------------------------------------------------
# Repository
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_account_repository_find_by_alias(session: AsyncSession) -> None:
    repo = BrokerageAccountRepository(session)
    acc = await repo.add(
        BrokerageAccount(
            account_alias="main-mock",
            broker_code="kis",
            connection_type="kis_rest_mock",
            environment="mock",
        )
    )
    assert acc.id is not None

    fetched = await repo.find_by_alias("main-mock")
    assert fetched is not None and fetched.id == acc.id


# -----------------------------------------------------------------------------
# UseCase
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_account_rejects_real_environment(session: AsyncSession) -> None:
    uc = RegisterAccountUseCase(session)
    with pytest.raises(InvalidRealEnvironmentError):
        await uc.execute(
            account_alias="real-trading",
            broker_code="kis",
            connection_type="kis_rest_mock",
            environment="real",
        )


@pytest.mark.asyncio
async def test_register_account_rejects_duplicate_alias(session: AsyncSession) -> None:
    uc = RegisterAccountUseCase(session)
    await uc.execute(
        account_alias="dup", broker_code="manual", connection_type="manual"
    )
    with pytest.raises(AccountAliasConflictError):
        await uc.execute(
            account_alias="dup", broker_code="manual", connection_type="manual"
        )


@pytest.mark.asyncio
async def test_record_transaction_buy_then_sell_updates_holding(session: AsyncSession) -> None:
    stocks = await _seed_stocks(session)
    account = await RegisterAccountUseCase(session).execute(
        account_alias="pnl-test", broker_code="manual", connection_type="manual"
    )
    uc = RecordTransactionUseCase(session)

    # 1차 매수 10주 @ 70000
    await uc.execute(TransactionRecord(
        account_id=account.id, stock_id=stocks["samsung"].id,
        transaction_type="BUY", quantity=10, price=Decimal("70000"),
        executed_at=date(2026, 3, 1), source="manual",
    ))
    # 2차 매수 10주 @ 80000 → 평단가 75000
    await uc.execute(TransactionRecord(
        account_id=account.id, stock_id=stocks["samsung"].id,
        transaction_type="BUY", quantity=10, price=Decimal("80000"),
        executed_at=date(2026, 3, 15), source="manual",
    ))
    holding = await PortfolioHoldingRepository(session).find_by_account_and_stock(
        account.id, stocks["samsung"].id
    )
    assert holding is not None
    assert holding.quantity == 20
    assert holding.avg_buy_price == Decimal("75000.00")

    # 일부 매도 5주 @ 82000 → 수량 15, 평단가 불변
    await uc.execute(TransactionRecord(
        account_id=account.id, stock_id=stocks["samsung"].id,
        transaction_type="SELL", quantity=5, price=Decimal("82000"),
        executed_at=date(2026, 4, 1), source="manual",
    ))
    holding = await PortfolioHoldingRepository(session).find_by_account_and_stock(
        account.id, stocks["samsung"].id
    )
    assert holding.quantity == 15
    assert holding.avg_buy_price == Decimal("75000.00")


@pytest.mark.asyncio
async def test_record_transaction_rejects_oversell(session: AsyncSession) -> None:
    stocks = await _seed_stocks(session)
    account = await RegisterAccountUseCase(session).execute(
        account_alias="oversell", broker_code="manual", connection_type="manual"
    )
    uc = RecordTransactionUseCase(session)
    await uc.execute(TransactionRecord(
        account_id=account.id, stock_id=stocks["sk"].id,
        transaction_type="BUY", quantity=3, price=Decimal("200000"),
        executed_at=date(2026, 3, 1), source="manual",
    ))
    with pytest.raises(InsufficientHoldingError):
        await uc.execute(TransactionRecord(
            account_id=account.id, stock_id=stocks["sk"].id,
            transaction_type="SELL", quantity=10, price=Decimal("210000"),
            executed_at=date(2026, 3, 2), source="manual",
        ))


@pytest.mark.asyncio
async def test_compute_snapshot_values_holdings_at_latest_close(session: AsyncSession) -> None:
    stocks = await _seed_stocks(session)
    account = await RegisterAccountUseCase(session).execute(
        account_alias="snap", broker_code="manual", connection_type="manual"
    )
    await RecordTransactionUseCase(session).execute(TransactionRecord(
        account_id=account.id, stock_id=stocks["samsung"].id,
        transaction_type="BUY", quantity=10, price=Decimal("70000"),
        executed_at=date(2026, 4, 1), source="manual",
    ))
    # 평단가 70000, 최신 종가 75000 → 미실현 +50000
    await StockPriceRepository(session).upsert_many([
        {"stock_id": stocks["samsung"].id, "trading_date": date(2026, 4, 1), "close_price": 72000},
        {"stock_id": stocks["samsung"].id, "trading_date": date(2026, 4, 17), "close_price": 75000},
    ])

    record = await ComputeSnapshotUseCase(session).execute(
        account_id=account.id, snapshot_date=date(2026, 4, 17)
    )
    assert record.holdings_count == 1
    assert record.total_value == Decimal("750000.00")
    assert record.total_cost == Decimal("700000.00")
    assert record.unrealized_pnl == Decimal("50000.00")


@pytest.mark.asyncio
async def test_compute_performance_returns_mdd_and_sharpe(session: AsyncSession) -> None:
    account = await RegisterAccountUseCase(session).execute(
        account_alias="perf", broker_code="manual", connection_type="manual"
    )
    repo = PortfolioSnapshotRepository(session)
    # 가상 시계열: 100 → 110 → 105 → 115 (상승 후 pullback, MDD ≈ -4.55%)
    values = [
        (date(2026, 4, 1), Decimal("100")),
        (date(2026, 4, 2), Decimal("110")),
        (date(2026, 4, 3), Decimal("105")),
        (date(2026, 4, 4), Decimal("115")),
    ]
    for d, v in values:
        await repo.upsert(PortfolioSnapshot(
            account_id=account.id, snapshot_date=d,
            total_value=v, total_cost=Decimal("100"),
            unrealized_pnl=v - Decimal("100"), realized_pnl=Decimal("0"),
            holdings_count=1,
        ))

    report = await ComputePerformanceUseCase(session).execute(
        account_id=account.id, start=date(2026, 4, 1), end=date(2026, 4, 4)
    )
    assert report.samples == 4
    assert report.total_return_pct == Decimal("15.0000")
    # MDD: 110→105 구간 = (105-110)/110 = -0.0454... ≈ -4.5455%
    assert report.max_drawdown_pct is not None
    assert Decimal("-4.6") < report.max_drawdown_pct < Decimal("-4.5")
    assert report.sharpe_ratio is not None


# -----------------------------------------------------------------------------
# Router
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_portfolio_routes_require_admin_key(app_with_session: FastAPI) -> None:
    transport = httpx.ASGITransport(app=app_with_session)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.post(
            "/api/portfolio/accounts",
            json={
                "account_alias": "x",
                "broker_code": "manual",
                "connection_type": "manual",
                "environment": "mock",
            },
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_account_then_record_transactions_end_to_end(
    session: AsyncSession, client: httpx.AsyncClient
) -> None:
    await _seed_stocks(session)

    # 1) 계좌 생성
    resp = await client.post(
        "/api/portfolio/accounts",
        json={
            "account_alias": "e2e-main",
            "broker_code": "manual",
            "connection_type": "manual",
            "environment": "mock",
        },
    )
    assert resp.status_code == 201
    account_id = resp.json()["id"]

    # 2) 매수 10주
    resp = await client.post(
        f"/api/portfolio/accounts/{account_id}/transactions",
        json={
            "stock_code": "005930",
            "transaction_type": "BUY",
            "quantity": 10,
            "price": "70000",
            "executed_at": "2026-04-01",
        },
    )
    assert resp.status_code == 201

    # 3) 보유 조회
    resp = await client.get(f"/api/portfolio/accounts/{account_id}/holdings")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["stock_code"] == "005930"
    assert body[0]["quantity"] == 10

    # 4) 중복 계좌 alias → 409
    resp = await client.post(
        "/api/portfolio/accounts",
        json={
            "account_alias": "e2e-main",
            "broker_code": "manual",
            "connection_type": "manual",
            "environment": "mock",
        },
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_account_blocks_real_environment(client: httpx.AsyncClient) -> None:
    # Pydantic 패턴 검증에서 먼저 걸려서 400. 실제로도 403 로 의도하지만, pattern 이 먼저 발동.
    resp = await client.post(
        "/api/portfolio/accounts",
        json={
            "account_alias": "real-one",
            "broker_code": "kis",
            "connection_type": "kis_rest_mock",
            "environment": "real",
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_transaction_with_unknown_stock_returns_404(
    session: AsyncSession, client: httpx.AsyncClient
) -> None:
    await _seed_stocks(session)
    resp = await client.post(
        "/api/portfolio/accounts",
        json={
            "account_alias": "bad-stock",
            "broker_code": "manual",
            "connection_type": "manual",
            "environment": "mock",
        },
    )
    account_id = resp.json()["id"]
    resp = await client.post(
        f"/api/portfolio/accounts/{account_id}/transactions",
        json={
            "stock_code": "999999",
            "transaction_type": "BUY",
            "quantity": 1,
            "price": "1000",
            "executed_at": "2026-04-01",
        },
    )
    assert resp.status_code == 404
