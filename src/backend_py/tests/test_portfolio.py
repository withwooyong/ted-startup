"""P10 포트폴리오 도메인 — Repository · UseCase · Router 통합 테스트."""
from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.external import KisClient
from app.adapter.out.persistence.models import (
    BrokerageAccount,
    PortfolioSnapshot,
    Signal,
    SignalType,
    Stock,
)
from app.adapter.out.persistence.repositories import (
    BrokerageAccountRepository,
    PortfolioHoldingRepository,
    PortfolioSnapshotRepository,
    SignalRepository,
    StockPriceRepository,
    StockRepository,
)
from app.adapter.web._deps import get_kis_client as prod_get_kis_client
from app.adapter.web._deps import get_session as prod_get_session
from app.application.service.portfolio_service import (
    AccountAliasConflictError,
    ComputePerformanceUseCase,
    ComputeSnapshotUseCase,
    CredentialNotFoundError,
    InsufficientHoldingError,
    InvalidRealEnvironmentError,
    RecordTransactionUseCase,
    RegisterAccountUseCase,
    SignalAlignmentUseCase,
    SyncPortfolioFromKisUseCase,
    TransactionRecord,
    UnsupportedConnectionError,
)
from app.config.settings import Settings, get_settings
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
async def test_create_account_blocks_mismatched_real_environment(
    client: httpx.AsyncClient,
) -> None:
    """PR 4: environment='real' 은 connection_type='kis_rest_real' 에서만 허용 → 403.

    이전 PR 까지 Pydantic 패턴이 environment='real' 자체를 400 으로 차단했지만,
    PR 4 에서 실계정 등록 경로를 열면서 패턴을 완화. 조합 검증은 UseCase 로 이관.
    """
    resp = await client.post(
        "/api/portfolio/accounts",
        json={
            "account_alias": "real-one",
            "broker_code": "kis",
            "connection_type": "kis_rest_mock",
            "environment": "real",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_account_blocks_real_connection_with_mock_env(
    client: httpx.AsyncClient,
) -> None:
    """역조합: connection_type='kis_rest_real' + environment='mock' → 403."""
    resp = await client.post(
        "/api/portfolio/accounts",
        json={
            "account_alias": "real-wrong-env",
            "broker_code": "kis",
            "connection_type": "kis_rest_real",
            "environment": "mock",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_kis_rest_real_account_succeeds(client: httpx.AsyncClient) -> None:
    """PR 4: 올바른 조합(kis_rest_real + environment='real')은 201 로 생성."""
    resp = await client.post(
        "/api/portfolio/accounts",
        json={
            "account_alias": "real-ok",
            "broker_code": "kis",
            "connection_type": "kis_rest_real",
            "environment": "real",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["connection_type"] == "kis_rest_real"
    assert body["environment"] == "real"


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


# -----------------------------------------------------------------------------
# P11 — KIS 모의 동기화
# -----------------------------------------------------------------------------


def _kis_settings() -> Settings:
    return Settings(
        kis_app_key_mock="MOCK-KEY",
        kis_app_secret_mock="MOCK-SECRET",
        kis_account_no_mock="12345678-01",
    )


def _build_mock_kis_client(rows: list[dict[str, object]]) -> KisClient:
    """고정 응답을 내보내는 KIS 클라이언트 — httpx MockTransport 주입."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(
                200, json={"access_token": "FAKE", "expires_in": 86400}
            )
        if request.url.path.endswith("/inquire-balance"):
            return httpx.Response(
                200,
                json={
                    "rt_cd": "0",
                    "msg1": "OK",
                    "output1": rows,
                    "output2": [],
                },
            )
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    return KisClient(_kis_settings(), transport=transport)


@pytest.mark.asyncio
async def test_sync_from_kis_creates_holdings_and_upserts_stock(
    session: AsyncSession,
) -> None:
    account = await RegisterAccountUseCase(session).execute(
        account_alias="kis-main",
        broker_code="kis",
        connection_type="kis_rest_mock",
    )
    kis = _build_mock_kis_client([
        {
            "pdno": "005930",
            "prdt_name": "삼성전자",
            "hldg_qty": "10",
            "pchs_avg_pric": "70000",
        },
        {
            "pdno": "000660",
            "prdt_name": "SK하이닉스",
            "hldg_qty": "3",
            "pchs_avg_pric": "215000",
        },
    ])

    async with kis as client:
        result = await SyncPortfolioFromKisUseCase(session, kis_client=client).execute(
            account_id=account.id
        )

    assert result.fetched_count == 2
    assert result.created_count == 2
    assert result.updated_count == 0
    assert result.stock_created_count == 2

    holdings = await PortfolioHoldingRepository(session).list_by_account(account.id)
    assert {h.quantity for h in holdings} == {10, 3}


@pytest.mark.asyncio
async def test_sync_from_kis_updates_existing_holding(session: AsyncSession) -> None:
    stocks = await _seed_stocks(session)
    account = await RegisterAccountUseCase(session).execute(
        account_alias="kis-upd",
        broker_code="kis",
        connection_type="kis_rest_mock",
    )
    # 수동으로 먼저 등록된 보유 (수량 5, 평단 65000)
    await RecordTransactionUseCase(session).execute(TransactionRecord(
        account_id=account.id, stock_id=stocks["samsung"].id,
        transaction_type="BUY", quantity=5, price=Decimal("65000"),
        executed_at=date(2026, 3, 1), source="manual",
    ))

    # KIS 에서는 수량 10, 평단가 70000 으로 반환
    kis = _build_mock_kis_client([
        {
            "pdno": "005930",
            "prdt_name": "삼성전자",
            "hldg_qty": "10",
            "pchs_avg_pric": "70000",
        },
    ])
    async with kis as client:
        result = await SyncPortfolioFromKisUseCase(session, kis_client=client).execute(
            account_id=account.id
        )
    assert result.updated_count == 1
    assert result.created_count == 0

    holding = await PortfolioHoldingRepository(session).find_by_account_and_stock(
        account.id, stocks["samsung"].id
    )
    assert holding.quantity == 10
    assert holding.avg_buy_price == Decimal("70000.00")


@pytest.mark.asyncio
async def test_sync_rejects_manual_connection_type(session: AsyncSession) -> None:
    account = await RegisterAccountUseCase(session).execute(
        account_alias="manual-only",
        broker_code="manual",
        connection_type="manual",
    )
    kis = _build_mock_kis_client([])
    async with kis as client:
        with pytest.raises(UnsupportedConnectionError):
            await SyncPortfolioFromKisUseCase(session, kis_client=client).execute(
                account_id=account.id
            )


@pytest.mark.asyncio
async def test_sync_kis_rest_real_without_credentials_raises_not_found(
    session: AsyncSession,
) -> None:
    """PR 5: `kis_rest_real` + credential 미등록 → `CredentialNotFoundError`.

    PR 2~4 단계에서는 `KisCredentialsNotWiredError` (개발 장벽) 를 raise 했으나,
    PR 5 에서 credential 저장소를 wire 하면 "자격증명 미등록" 의미로 전환.
    라우터는 이를 404 로 매핑.
    """
    from cryptography.fernet import Fernet

    from app.adapter.out.persistence.repositories import (
        BrokerageAccountCredentialRepository,
    )
    from app.security.credential_cipher import CredentialCipher

    account = await BrokerageAccountRepository(session).add(
        BrokerageAccount(
            account_alias="kis-real-no-cred",
            broker_code="kis",
            connection_type="kis_rest_real",
            environment="real",
        )
    )
    cipher = CredentialCipher(Fernet.generate_key().decode())
    credential_repo = BrokerageAccountCredentialRepository(session, cipher)

    def _factory(_creds):
        # 미등록이면 factory 까지 도달해선 안 됨 — 도달 시 테스트 실패로 전환.
        raise AssertionError("credential 미등록 상태에서 factory 가 호출됐음")

    with pytest.raises(CredentialNotFoundError, match="credential 미등록"):
        await SyncPortfolioFromKisUseCase(
            session,
            credential_repo=credential_repo,
            real_client_factory=_factory,
        ).execute(account_id=account.id)


@pytest.mark.asyncio
async def test_sync_kis_rest_real_requires_real_environment(
    session: AsyncSession,
) -> None:
    """`kis_rest_real` + environment='mock' 조합 → `InvalidRealEnvironmentError`."""
    account = await BrokerageAccountRepository(session).add(
        BrokerageAccount(
            account_alias="kis-real-wrong-env",
            broker_code="kis",
            connection_type="kis_rest_real",
            environment="mock",  # 의도적 불일치
        )
    )
    kis = _build_mock_kis_client([])
    async with kis as client:
        with pytest.raises(InvalidRealEnvironmentError, match="environment='real'"):
            await SyncPortfolioFromKisUseCase(session, kis_client=client).execute(
                account_id=account.id
            )


@pytest.mark.asyncio
async def test_sync_endpoint_returns_summary(
    app_with_session: FastAPI, session: AsyncSession
) -> None:
    account = await RegisterAccountUseCase(session).execute(
        account_alias="kis-http",
        broker_code="kis",
        connection_type="kis_rest_mock",
    )

    async def _kis_override():
        kis = _build_mock_kis_client([
            {
                "pdno": "005930",
                "prdt_name": "삼성전자",
                "hldg_qty": "7",
                "pchs_avg_pric": "68000",
            },
        ])
        try:
            yield kis
        finally:
            await kis.close()

    app_with_session.dependency_overrides[prod_get_kis_client] = _kis_override

    transport = httpx.ASGITransport(app=app_with_session)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"X-API-Key": "test-admin-key"},
    ) as c:
        resp = await c.post(f"/api/portfolio/accounts/{account.id}/sync")

    assert resp.status_code == 200
    body = resp.json()
    assert body["account_id"] == account.id
    assert body["connection_type"] == "kis_rest_mock"
    assert body["fetched_count"] == 1
    assert body["created_count"] == 1


# -----------------------------------------------------------------------------
# P12 — 시그널 정합도
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_signal_alignment_empty_holdings_returns_empty_items(
    session: AsyncSession,
) -> None:
    account = await RegisterAccountUseCase(session).execute(
        account_alias="align-empty", broker_code="manual", connection_type="manual"
    )
    report = await SignalAlignmentUseCase(session).execute(
        account_id=account.id,
        since=date(2026, 3, 1),
        until=date(2026, 4, 17),
        min_score=60,
    )
    assert report.total_holdings == 0
    assert report.aligned_holdings == 0
    assert report.items == []


@pytest.mark.asyncio
async def test_signal_alignment_matches_held_stocks_and_filters_by_score(
    session: AsyncSession,
) -> None:
    stocks = await _seed_stocks(session)
    account = await RegisterAccountUseCase(session).execute(
        account_alias="align-match", broker_code="manual", connection_type="manual"
    )
    # 삼성/SK 모두 보유
    for stock_key, qty, price in (("samsung", 10, 70000), ("sk", 3, 210000)):
        await RecordTransactionUseCase(session).execute(TransactionRecord(
            account_id=account.id, stock_id=stocks[stock_key].id,
            transaction_type="BUY", quantity=qty, price=Decimal(str(price)),
            executed_at=date(2026, 3, 1), source="manual",
        ))

    sr = SignalRepository(session)
    # 삼성: score 85 / 55(컷오프 미달)
    await sr.add(Signal(
        stock_id=stocks["samsung"].id, signal_date=date(2026, 4, 10),
        signal_type=SignalType.RAPID_DECLINE.value, score=85, grade="A", detail={},
    ))
    await sr.add(Signal(
        stock_id=stocks["samsung"].id, signal_date=date(2026, 4, 12),
        signal_type=SignalType.SHORT_SQUEEZE.value, score=55, grade="C", detail={},
    ))
    # SK: score 70 1건
    await sr.add(Signal(
        stock_id=stocks["sk"].id, signal_date=date(2026, 4, 11),
        signal_type=SignalType.TREND_REVERSAL.value, score=70, grade="B", detail={},
    ))

    report = await SignalAlignmentUseCase(session).execute(
        account_id=account.id,
        since=date(2026, 4, 1),
        until=date(2026, 4, 17),
        min_score=60,
    )
    assert report.total_holdings == 2
    assert report.aligned_holdings == 2
    assert [item.stock_code for item in report.items] == ["005930", "000660"]  # max_score 정렬
    samsung = report.items[0]
    assert samsung.max_score == 85
    # 55점은 컷오프로 배제
    assert samsung.hit_count == 1
    assert samsung.signals[0].signal_type == "RAPID_DECLINE"


@pytest.mark.asyncio
async def test_signal_alignment_excludes_signals_outside_window(
    session: AsyncSession,
) -> None:
    stocks = await _seed_stocks(session)
    account = await RegisterAccountUseCase(session).execute(
        account_alias="align-window", broker_code="manual", connection_type="manual"
    )
    await RecordTransactionUseCase(session).execute(TransactionRecord(
        account_id=account.id, stock_id=stocks["samsung"].id,
        transaction_type="BUY", quantity=5, price=Decimal("70000"),
        executed_at=date(2026, 2, 1), source="manual",
    ))
    # 기간 밖 시그널만 있음
    await SignalRepository(session).add(Signal(
        stock_id=stocks["samsung"].id, signal_date=date(2026, 2, 15),
        signal_type=SignalType.RAPID_DECLINE.value, score=90, grade="A", detail={},
    ))
    report = await SignalAlignmentUseCase(session).execute(
        account_id=account.id,
        since=date(2026, 4, 1),
        until=date(2026, 4, 17),
        min_score=60,
    )
    assert report.total_holdings == 1
    assert report.aligned_holdings == 0


@pytest.mark.asyncio
async def test_signal_alignment_endpoint_e2e(
    session: AsyncSession, client: httpx.AsyncClient
) -> None:
    stocks = await _seed_stocks(session)
    account = await RegisterAccountUseCase(session).execute(
        account_alias="align-e2e", broker_code="manual", connection_type="manual"
    )
    await RecordTransactionUseCase(session).execute(TransactionRecord(
        account_id=account.id, stock_id=stocks["samsung"].id,
        transaction_type="BUY", quantity=2, price=Decimal("70000"),
        executed_at=date(2026, 4, 1), source="manual",
    ))
    await SignalRepository(session).add(Signal(
        stock_id=stocks["samsung"].id, signal_date=date(2026, 4, 10),
        signal_type=SignalType.RAPID_DECLINE.value, score=75, grade="B", detail={},
    ))

    resp = await client.get(
        f"/api/portfolio/accounts/{account.id}/signal-alignment",
        params={"since": "2026-04-01", "until": "2026-04-17", "min_score": 60},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["aligned_holdings"] == 1
    assert body["items"][0]["stock_code"] == "005930"
    assert body["items"][0]["signals"][0]["score"] == 75


@pytest.mark.asyncio
async def test_signal_alignment_endpoint_404_for_unknown_account(
    client: httpx.AsyncClient,
) -> None:
    resp = await client.get("/api/portfolio/accounts/999999/signal-alignment")
    assert resp.status_code == 404
