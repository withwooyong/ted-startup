"""StockPriceRepository.find_range — 시계열 조회 (C-1β GET 라우터 source).

설계: endpoint-06-ka10081.md § 6.2.

검증:
1. find_range 정상 시계열 (KRX) — start <= trading_date <= end
2. find_range NXT 분기 — KRX/NXT 분리 결과
3. start/end 경계 포함
4. 빈 결과 — Stock 있지만 fundamental 0
5. 정렬 — trading_date asc
6. start > end → ValueError
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.adapter.out.kiwoom.chart import NormalizedDailyOhlcv
from app.adapter.out.persistence.repositories.stock_price import StockPriceRepository
from app.application.constants import ExchangeType


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s


@pytest_asyncio.fixture(autouse=True)
async def _cleanup(engine: AsyncEngine) -> AsyncIterator[None]:
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        await s.execute(text("TRUNCATE kiwoom.stock RESTART IDENTITY CASCADE"))
        await s.commit()
    yield
    async with factory() as s:
        await s.execute(text("TRUNCATE kiwoom.stock RESTART IDENTITY CASCADE"))
        await s.commit()


async def _create_stock(session: AsyncSession, code: str = "005930") -> int:
    res = await session.execute(
        text(
            "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code) "
            "VALUES (:c, :n, '0') RETURNING id"
        ).bindparams(c=code, n=f"테스트-{code}")
    )
    await session.commit()
    return int(res.scalar_one())


def _ohlcv(stock_id: int, d: date, exchange: ExchangeType = ExchangeType.KRX) -> NormalizedDailyOhlcv:
    return NormalizedDailyOhlcv(
        stock_id=stock_id, trading_date=d, exchange=exchange, adjusted=True,
        open_price=69800, high_price=70500, low_price=69600, close_price=70000,
        trade_volume=1000000, trade_amount=70000000, prev_compare_amount=600,
        prev_compare_sign="2", turnover_rate=Decimal("0.16"),
    )


@pytest.mark.asyncio
async def test_find_range_returns_sorted_rows(session: AsyncSession) -> None:
    stock_id = await _create_stock(session)
    repo = StockPriceRepository(session)

    rows = [
        _ohlcv(stock_id, date(2025, 9, 5)),
        _ohlcv(stock_id, date(2025, 9, 8)),
        _ohlcv(stock_id, date(2025, 9, 1)),
    ]
    await repo.upsert_many(rows, exchange=ExchangeType.KRX)
    await session.commit()

    found = await repo.find_range(
        stock_id, exchange=ExchangeType.KRX, start=date(2025, 9, 1), end=date(2025, 9, 8)
    )

    assert len(found) == 3
    # 오름차순 정렬
    assert [r.trading_date for r in found] == [date(2025, 9, 1), date(2025, 9, 5), date(2025, 9, 8)]


@pytest.mark.asyncio
async def test_find_range_filters_outside_window(session: AsyncSession) -> None:
    stock_id = await _create_stock(session)
    repo = StockPriceRepository(session)

    rows = [
        _ohlcv(stock_id, date(2025, 9, 1)),
        _ohlcv(stock_id, date(2025, 9, 8)),
        _ohlcv(stock_id, date(2025, 10, 1)),
    ]
    await repo.upsert_many(rows, exchange=ExchangeType.KRX)
    await session.commit()

    found = await repo.find_range(
        stock_id, exchange=ExchangeType.KRX, start=date(2025, 9, 5), end=date(2025, 9, 30)
    )

    assert len(found) == 1
    assert found[0].trading_date == date(2025, 9, 8)


@pytest.mark.asyncio
async def test_find_range_separates_krx_and_nxt(session: AsyncSession) -> None:
    stock_id = await _create_stock(session)
    repo = StockPriceRepository(session)

    await repo.upsert_many(
        [_ohlcv(stock_id, date(2025, 9, 8), ExchangeType.KRX)],
        exchange=ExchangeType.KRX,
    )
    await repo.upsert_many(
        [_ohlcv(stock_id, date(2025, 9, 8), ExchangeType.NXT)],
        exchange=ExchangeType.NXT,
    )
    await session.commit()

    krx = await repo.find_range(stock_id, exchange=ExchangeType.KRX, start=date(2025, 9, 1), end=date(2025, 9, 30))
    nxt = await repo.find_range(stock_id, exchange=ExchangeType.NXT, start=date(2025, 9, 1), end=date(2025, 9, 30))

    assert len(krx) == 1
    assert len(nxt) == 1


@pytest.mark.asyncio
async def test_find_range_empty_when_no_rows(session: AsyncSession) -> None:
    stock_id = await _create_stock(session)
    repo = StockPriceRepository(session)

    found = await repo.find_range(
        stock_id, exchange=ExchangeType.KRX, start=date(2025, 9, 1), end=date(2025, 9, 30)
    )
    assert found == []


@pytest.mark.asyncio
async def test_find_range_rejects_inverted_window(session: AsyncSession) -> None:
    stock_id = await _create_stock(session)
    repo = StockPriceRepository(session)

    with pytest.raises(ValueError, match="start"):
        await repo.find_range(
            stock_id, exchange=ExchangeType.KRX, start=date(2025, 9, 30), end=date(2025, 9, 1)
        )


@pytest.mark.asyncio
async def test_find_range_rejects_unsupported_exchange(session: AsyncSession) -> None:
    """SOR 미지원 — _MODEL_BY_EXCHANGE 분기 일관."""
    stock_id = await _create_stock(session)
    repo = StockPriceRepository(session)

    with pytest.raises(ValueError, match="unsupported exchange"):
        await repo.find_range(
            stock_id, exchange=ExchangeType.SOR, start=date(2025, 9, 1), end=date(2025, 9, 30)
        )
