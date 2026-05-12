"""IngestLendingMarketUseCase + IngestLendingStockUseCase + IngestLendingStockBulkUseCase.

chunk = Phase E, plan doc endpoint-15-ka10014.md § 12 참조.
설계: endpoint-16-ka10068.md § 6.3 + endpoint-17-ka20068.md § 6.3.

test_sector_ohlcv_service.py + test_ingest_daily_flow_service.py 패턴 1:1 응용.

검증 (12 시나리오):

MARKET (ka10068) — 4건:
1. MARKET INSERT (DB 빈, 응답 5 row) → scope=MARKET 5 row, stock_id=NULL
2. MARKET UPDATE 멱등성 (같은 호출 두 번)
3. MARKET 빈 응답 → upserted=0
4. MARKET return_code != 0 → outcome.error 세트

STOCK (ka20068) — 4건:
5. STOCK INSERT (stock 1건 + 응답 5 row) → scope=STOCK 5 row
6. STOCK UPDATE 멱등성
7. KRX only — NXT 시도 안 함 (Length=6 정책, endpoint-17 § 12.2 결정 #4)
8. inactive stock skip → outcome.skipped=True

공통 — 4건:
9. MARKET + STOCK 같은 trading_date 동시 존재 → 두 row 분리 (partial unique index)
10. CHECK constraint 위반 (scope=MARKET + stock_id=1 INSERT 시도) → IntegrityError
11. Bulk 50 batch (100 종목) → 50건마다 commit (BATCH_SIZE 분기)
12. only_market_codes 필터 (KOSPI 만) → KOSDAQ skip
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import date
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from app.adapter.out.kiwoom.slb import KiwoomLendingClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.adapter.out.kiwoom._exceptions import KiwoomBusinessError
from app.adapter.out.kiwoom._records import LendingMarketRow, LendingStockRow

# ---------------------------------------------------------------------------
# 공통 픽스처
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_lending_tables(engine: AsyncEngine) -> AsyncIterator[None]:
    """각 테스트 전후 lending + stock 테이블 정리."""
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        await s.execute(
            text("TRUNCATE kiwoom.lending_balance_kw, kiwoom.stock RESTART IDENTITY CASCADE")
        )
        await s.commit()
    yield
    async with factory() as s:
        await s.execute(
            text("TRUNCATE kiwoom.lending_balance_kw, kiwoom.stock RESTART IDENTITY CASCADE")
        )
        await s.commit()


@pytest.fixture
def session_provider(engine: Any) -> Callable[[], AbstractAsyncContextManager[AsyncSession]]:
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    @asynccontextmanager
    async def _provider() -> AsyncIterator[AsyncSession]:
        async with factory() as s:
            yield s

    return _provider


async def _create_stock(
    session: AsyncSession,
    code: str,
    name: str = "테스트종목",
    market: str = "0",
    *,
    is_active: bool = True,
    nxt_enable: bool = False,
) -> int:
    """테스트용 stock INSERT 후 id 반환."""
    res = await session.execute(
        text(
            "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code, is_active, nxt_enable) "
            "VALUES (:c, :n, :m, :a, :nx) RETURNING id"
        ).bindparams(c=code, n=name, m=market, a=is_active, nx=nxt_enable)
    )
    sid = int(res.scalar_one())
    await session.commit()
    return sid


def _make_market_rows(count: int = 5) -> list[LendingMarketRow]:
    """LendingMarketRow stub list 생성."""
    return [
        LendingMarketRow(
            dt=f"2025040{i + 1}",
            dbrt_trde_cntrcnt="35330036",
            dbrt_trde_rpy="25217364",
            dbrt_trde_irds="10112672",
            rmnd="2460259444",
            remn_amt="73956254",
        )
        for i in range(count)
    ]


def _make_stock_rows(count: int = 5) -> list[LendingStockRow]:
    """LendingStockRow stub list 생성."""
    return [
        LendingStockRow(
            dt=f"2025040{i + 1}",
            dbrt_trde_cntrcnt="1210354",
            dbrt_trde_rpy="2693108",
            dbrt_trde_irds="-1482754",
            rmnd="98242435",
            remn_amt="5452455",
        )
        for i in range(count)
    ]


def _make_lending_client_stub(
    market_rows: list[LendingMarketRow] | None = None,
    stock_rows: list[LendingStockRow] | None = None,
    market_exc: Exception | None = None,
    stock_exc: Exception | None = None,
) -> KiwoomLendingClient:
    """KiwoomLendingClient stub — fetch_market_trend / fetch_stock_trend mock."""
    client = AsyncMock(spec=KiwoomLendingClient)
    if market_exc is not None:
        client.fetch_market_trend.side_effect = market_exc
    else:
        client.fetch_market_trend.return_value = market_rows or []
    if stock_exc is not None:
        client.fetch_stock_trend.side_effect = stock_exc
    else:
        client.fetch_stock_trend.return_value = stock_rows or []
    return client


# ===========================================================================
# MARKET (ka10068)
# ===========================================================================

# ---------- 1. MARKET INSERT ----------


@pytest.mark.asyncio
async def test_ingest_lending_market_insert_five_rows(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """DB 빈 상태 + 응답 5 row → scope=MARKET 5 row INSERT, stock_id=NULL.

    endpoint-16 § 9.2 MARKET INSERT 시나리오.
    """
    rows = _make_market_rows(5)
    client = _make_lending_client_stub(market_rows=rows)

    from app.application.service.lending_service import IngestLendingMarketUseCase

    uc = IngestLendingMarketUseCase(session=session, slb_client=client)
    outcome = await uc.execute()
    await session.commit()

    assert outcome.upserted == 5
    assert outcome.error is None

    result = await session.execute(
        text(
            "SELECT COUNT(*) FROM kiwoom.lending_balance_kw "
            "WHERE scope = 'MARKET' AND stock_id IS NULL"
        )
    )
    assert result.scalar_one() == 5


# ---------- 2. MARKET UPDATE 멱등성 ----------


@pytest.mark.asyncio
async def test_ingest_lending_market_upsert_idempotent(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """같은 호출 두 번 → row 수 유지 (ON CONFLICT DO UPDATE).

    endpoint-16 § 9.2 UPDATE 멱등성 시나리오.
    """
    rows = _make_market_rows(3)
    client = _make_lending_client_stub(market_rows=rows)

    from app.application.service.lending_service import IngestLendingMarketUseCase

    uc = IngestLendingMarketUseCase(session=session, slb_client=client)

    outcome1 = await uc.execute()
    await session.commit()
    outcome2 = await uc.execute()
    await session.commit()

    assert outcome1.upserted == 3
    assert outcome2.upserted == 3

    result = await session.execute(
        text("SELECT COUNT(*) FROM kiwoom.lending_balance_kw WHERE scope = 'MARKET'")
    )
    assert result.scalar_one() == 3  # insert → update, 중복 없음


# ---------- 3. MARKET 빈 응답 → upserted=0 ----------


@pytest.mark.asyncio
async def test_ingest_lending_market_empty_response_returns_zero(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """응답 list=[] → upserted=0."""
    client = _make_lending_client_stub(market_rows=[])

    from app.application.service.lending_service import IngestLendingMarketUseCase

    uc = IngestLendingMarketUseCase(session=session, slb_client=client)
    outcome = await uc.execute()

    assert outcome.upserted == 0
    assert outcome.error is None


# ---------- 4. MARKET return_code != 0 → outcome.error ----------


@pytest.mark.asyncio
async def test_ingest_lending_market_business_error_sets_outcome_error(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """fetch_market_trend → KiwoomBusinessError → outcome.error 세트, upserted=0."""
    exc = KiwoomBusinessError(
        api_id="ka10068", return_code=1, message="조회 가능 일자가 아닙니다"
    )
    client = _make_lending_client_stub(market_exc=exc)

    from app.application.service.lending_service import IngestLendingMarketUseCase

    uc = IngestLendingMarketUseCase(session=session, slb_client=client)
    outcome = await uc.execute(
        start_date=date(1900, 1, 1), end_date=date(1900, 1, 2)
    )

    assert outcome.upserted == 0
    assert outcome.error is not None
    assert "1" in outcome.error  # return_code 포함


# ===========================================================================
# STOCK (ka20068)
# ===========================================================================

# ---------- 5. STOCK INSERT ----------


@pytest.mark.asyncio
async def test_ingest_lending_stock_insert_five_rows(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """stock 1건 + 응답 5 row → scope=STOCK 5 row INSERT.

    endpoint-17 § 9.2 STOCK INSERT 시나리오.
    """
    await _create_stock(session, "005930", "삼성전자")
    rows = _make_stock_rows(5)
    client = _make_lending_client_stub(stock_rows=rows)

    from app.application.service.lending_service import IngestLendingStockUseCase

    uc = IngestLendingStockUseCase(session=session, slb_client=client)
    outcome = await uc.execute("005930")
    await session.commit()

    assert outcome.upserted == 5
    assert not outcome.skipped

    result = await session.execute(
        text("SELECT COUNT(*) FROM kiwoom.lending_balance_kw WHERE scope = 'STOCK'")
    )
    assert result.scalar_one() == 5


# ---------- 6. STOCK UPDATE 멱등성 ----------


@pytest.mark.asyncio
async def test_ingest_lending_stock_upsert_idempotent(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """같은 종목 두 번 호출 → row 수 유지 (ON CONFLICT DO UPDATE).

    endpoint-17 § 9.2 UPDATE 멱등성 시나리오.
    """
    await _create_stock(session, "000660", "SK하이닉스")
    rows = _make_stock_rows(3)
    client = _make_lending_client_stub(stock_rows=rows)

    from app.application.service.lending_service import IngestLendingStockUseCase

    uc = IngestLendingStockUseCase(session=session, slb_client=client)

    outcome1 = await uc.execute("000660")
    await session.commit()
    outcome2 = await uc.execute("000660")
    await session.commit()

    assert outcome1.upserted == 3
    assert outcome2.upserted == 3

    result = await session.execute(
        text("SELECT COUNT(*) FROM kiwoom.lending_balance_kw WHERE scope = 'STOCK'")
    )
    assert result.scalar_one() == 3


# ---------- 7. KRX only — NXT 시도 안 함 ----------


@pytest.mark.asyncio
async def test_ingest_lending_stock_krx_only_does_not_call_nxt(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """ka20068 stk_cd Length=6 정책 — NXT suffix 시도 없음.

    endpoint-17 § 12.2 결정 #4: ka20068=KRX only (운영 검증 후 재검토).
    fetch_stock_trend 는 6자리 stock_code 만 받아야 하며, `005930_NX` 같은 NXT
    suffix 를 UseCase 가 자동으로 시도하지 않는다.
    """
    await _create_stock(session, "005930", "삼성전자", nxt_enable=True)
    rows = _make_stock_rows(2)
    client = _make_lending_client_stub(stock_rows=rows)

    from app.application.service.lending_service import IngestLendingStockUseCase

    uc = IngestLendingStockUseCase(session=session, slb_client=client)
    outcome = await uc.execute("005930")

    # fetch_stock_trend 는 정확히 1회 (KRX 한 번만)
    client.fetch_stock_trend.assert_awaited_once()
    called_code: str = client.fetch_stock_trend.call_args[0][0]
    assert "_NX" not in called_code, "NXT suffix 가 자동으로 붙으면 안 됨"
    assert len(called_code) == 6
    assert not outcome.skipped


# ---------- 8. inactive stock skip ----------


@pytest.mark.asyncio
async def test_ingest_lending_stock_skips_inactive_stock(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """is_active=False stock → outcome.skipped=True, fetch 호출 없음.

    endpoint-17 § 6.3 IngestLendingStockUseCase 비활성 stock 처리.
    """
    await _create_stock(session, "999999", "비활성종목", is_active=False)
    client = _make_lending_client_stub()

    from app.application.service.lending_service import IngestLendingStockUseCase

    uc = IngestLendingStockUseCase(session=session, slb_client=client)
    outcome = await uc.execute("999999")

    assert outcome.skipped is True
    client.fetch_stock_trend.assert_not_awaited()


# ===========================================================================
# 공통
# ===========================================================================

# ---------- 9. MARKET + STOCK 같은 trading_date → 두 row 분리 ----------


@pytest.mark.asyncio
async def test_market_and_stock_rows_coexist_on_same_trading_date(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """같은 trading_date 에 scope=MARKET row + scope=STOCK row → 두 row 분리 공존.

    endpoint-16 § 9.2 / endpoint-17 § 9.2 MARKET/STOCK 충돌 안 함 시나리오.
    partial unique index 가 scope 별로 독립 — 같은 날짜여도 충돌 없음.
    """
    stock_id = await _create_stock(session, "005930", "삼성전자")

    # MARKET row (trading_date=20250430)
    market_row = LendingMarketRow(
        dt="20250430",
        dbrt_trde_cntrcnt="35330036",
        dbrt_trde_rpy="25217364",
        dbrt_trde_irds="10112672",
        rmnd="2460259444",
        remn_amt="73956254",
    )
    market_client = _make_lending_client_stub(market_rows=[market_row])

    # STOCK row (trading_date=20250430, 같은 날)
    stock_row = LendingStockRow(
        dt="20250430",
        dbrt_trde_cntrcnt="1210354",
        dbrt_trde_rpy="2693108",
        dbrt_trde_irds="-1482754",
        rmnd="98242435",
        remn_amt="5452455",
    )
    stock_client = _make_lending_client_stub(stock_rows=[stock_row])

    from app.application.service.lending_service import (
        IngestLendingMarketUseCase,
        IngestLendingStockUseCase,
    )

    market_uc = IngestLendingMarketUseCase(session=session, slb_client=market_client)
    await market_uc.execute()
    await session.commit()

    stock_uc = IngestLendingStockUseCase(session=session, slb_client=stock_client)
    await stock_uc.execute("005930")
    await session.commit()

    result = await session.execute(
        text(
            "SELECT scope, stock_id FROM kiwoom.lending_balance_kw "
            "WHERE trading_date = '2025-04-30' ORDER BY scope"
        )
    )
    rows_db = result.fetchall()
    assert len(rows_db) == 2, "MARKET 1 + STOCK 1 = 2 row (partial unique 분리)"

    scopes = {r.scope for r in rows_db}
    assert "MARKET" in scopes
    assert "STOCK" in scopes

    market_row_db = next(r for r in rows_db if r.scope == "MARKET")
    stock_row_db = next(r for r in rows_db if r.scope == "STOCK")
    assert market_row_db.stock_id is None
    assert stock_row_db.stock_id == stock_id


# ---------- 10. CHECK constraint 위반 ----------


@pytest.mark.asyncio
async def test_insert_market_scope_with_stock_id_raises_integrity_error(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """scope=MARKET + stock_id=1 INSERT 시도 → IntegrityError (CHECK constraint).

    endpoint-16 § 9.2 CHECK constraint 위반 시나리오.
    chk_lending_scope: (scope='MARKET' AND stock_id IS NULL) OR
                       (scope='STOCK' AND stock_id IS NOT NULL)
    """

    stock_id = await _create_stock(session, "005930")

    with pytest.raises(IntegrityError):
        await session.execute(
            text(
                "INSERT INTO kiwoom.lending_balance_kw "
                "(scope, stock_id, trading_date, contracted_volume) "
                "VALUES ('MARKET', :sid, '2025-04-30', 1000)"
            ).bindparams(sid=stock_id)
        )
        await session.flush()


# ---------- 11. Bulk 50 batch (100 종목) ----------


@pytest.mark.asyncio
async def test_ingest_lending_stock_bulk_commits_every_50_stocks(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """100 종목 Bulk → 50건마다 commit (BATCH_SIZE=50).

    endpoint-17 § 6.3 IngestLendingStockBulkUseCase BATCH_SIZE 분기.
    """
    # 100 종목 INSERT
    for i in range(100):
        await _create_stock(
            session,
            f"{i:06d}",
            f"테스트종목{i}",
            market="0",
        )
    await session.commit()

    rows = _make_stock_rows(2)
    client = _make_lending_client_stub(stock_rows=rows)

    from app.application.service.lending_service import (
        IngestLendingStockBulkUseCase,
        IngestLendingStockUseCase,
    )

    single_uc = IngestLendingStockUseCase(session=session, slb_client=client)
    bulk_uc = IngestLendingStockBulkUseCase(session=session, single_use_case=single_uc)

    result = await bulk_uc.execute(
        start_date=date(2025, 4, 1),
        end_date=date(2025, 4, 30),
    )

    assert result.total_stocks == 100
    assert client.fetch_stock_trend.await_count == 100


# ---------- 12. only_market_codes 필터 ----------


@pytest.mark.asyncio
async def test_ingest_lending_stock_bulk_filters_by_market_codes(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """only_market_codes=['0'] (KOSPI) → market_code='1' (KOSDAQ) skip.

    endpoint-17 § 6.3 only_market_codes 필터.
    """
    # KOSPI (market_code='0') 2건 + KOSDAQ (market_code='1') 2건
    for i in range(2):
        await _create_stock(session, f"KOSPI{i}", f"코스피{i}", market="0")
    for i in range(2):
        await _create_stock(session, f"KOSDA{i}", f"코스닥{i}", market="1")
    await session.commit()

    rows = _make_stock_rows(1)
    client = _make_lending_client_stub(stock_rows=rows)

    from app.application.service.lending_service import (
        IngestLendingStockBulkUseCase,
        IngestLendingStockUseCase,
    )

    single_uc = IngestLendingStockUseCase(session=session, slb_client=client)
    bulk_uc = IngestLendingStockBulkUseCase(session=session, single_use_case=single_uc)

    result = await bulk_uc.execute(
        start_date=date(2025, 4, 1),
        end_date=date(2025, 4, 30),
        only_market_codes=["0"],  # KOSPI 만
    )

    assert result.total_stocks == 2  # KOSDAQ 2건 skip
    assert client.fetch_stock_trend.await_count == 2
