"""StockPriceRepository (C-1α) — KRX/NXT 분기 + upsert_many 멱등.

설계: endpoint-06-ka10081.md § 6.2.

검증:
1. KRX 일봉 bulk insert
2. NXT 일봉 bulk insert (별도 테이블)
3. ON CONFLICT (stock_id, trading_date, adjusted) DO UPDATE — 멱등
4. exchange 인자 분기 — 같은 stock_id/trading_date 도 KRX/NXT 분리 row
5. trading_date=date.min 빈 row 자동 스킵
6. raw vs adjusted 분리 적재 — adjusted=False 도 별도 row
7. 빈 list → 0
8. 다중 stock 다중 일자 한 번에 upsert
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
async def _cleanup_price_tables(engine: AsyncEngine) -> AsyncIterator[None]:
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


def _ohlcv(
    *,
    stock_id: int,
    trading_date: date,
    exchange: ExchangeType = ExchangeType.KRX,
    adjusted: bool = True,
    close: int | None = 70000,
) -> NormalizedDailyOhlcv:
    return NormalizedDailyOhlcv(
        stock_id=stock_id,
        trading_date=trading_date,
        exchange=exchange,
        adjusted=adjusted,
        open_price=69800,
        high_price=70500,
        low_price=69600,
        close_price=close,
        trade_volume=9263135,
        trade_amount=648525,
        prev_compare_amount=600,
        prev_compare_sign="2",
        turnover_rate=Decimal("0.16"),
    )


# ---------- 1. KRX bulk insert ----------


@pytest.mark.asyncio
async def test_upsert_many_inserts_krx_rows(session: AsyncSession) -> None:
    stock_id = await _create_stock(session)
    repo = StockPriceRepository(session)

    rows = [
        _ohlcv(stock_id=stock_id, trading_date=date(2025, 9, 8)),
        _ohlcv(stock_id=stock_id, trading_date=date(2025, 9, 5)),
    ]
    affected = await repo.upsert_many(rows, exchange=ExchangeType.KRX)
    await session.commit()

    assert affected == 2

    res = await session.execute(
        text("SELECT COUNT(*) FROM kiwoom.stock_price_krx WHERE stock_id = :sid").bindparams(sid=stock_id)
    )
    assert res.scalar_one() == 2


# ---------- 2. NXT bulk insert (별도 테이블) ----------


@pytest.mark.asyncio
async def test_upsert_many_inserts_nxt_rows_in_separate_table(session: AsyncSession) -> None:
    stock_id = await _create_stock(session)
    repo = StockPriceRepository(session)

    krx_rows = [_ohlcv(stock_id=stock_id, trading_date=date(2025, 9, 8))]
    nxt_rows = [_ohlcv(stock_id=stock_id, trading_date=date(2025, 9, 8), exchange=ExchangeType.NXT)]

    await repo.upsert_many(krx_rows, exchange=ExchangeType.KRX)
    await repo.upsert_many(nxt_rows, exchange=ExchangeType.NXT)
    await session.commit()

    krx_count = (await session.execute(
        text("SELECT COUNT(*) FROM kiwoom.stock_price_krx WHERE stock_id = :sid").bindparams(sid=stock_id)
    )).scalar_one()
    nxt_count = (await session.execute(
        text("SELECT COUNT(*) FROM kiwoom.stock_price_nxt WHERE stock_id = :sid").bindparams(sid=stock_id)
    )).scalar_one()

    assert krx_count == 1
    assert nxt_count == 1


# ---------- 3. ON CONFLICT 멱등 ----------


@pytest.mark.asyncio
async def test_upsert_many_idempotent_on_repeat(session: AsyncSession) -> None:
    """같은 (stock_id, trading_date, adjusted) → UPDATE (row 1개 유지)."""
    stock_id = await _create_stock(session)
    repo = StockPriceRepository(session)

    rows = [_ohlcv(stock_id=stock_id, trading_date=date(2025, 9, 8), close=70000)]
    await repo.upsert_many(rows, exchange=ExchangeType.KRX)
    await session.commit()

    rows_updated = [_ohlcv(stock_id=stock_id, trading_date=date(2025, 9, 8), close=72000)]
    await repo.upsert_many(rows_updated, exchange=ExchangeType.KRX)
    await session.commit()

    res = await session.execute(
        text(
            "SELECT close_price, COUNT(*) FROM kiwoom.stock_price_krx "
            "WHERE stock_id = :sid GROUP BY close_price"
        ).bindparams(sid=stock_id)
    )
    rows_db = res.fetchall()
    assert len(rows_db) == 1
    assert rows_db[0][0] == 72000  # 갱신 반영
    assert rows_db[0][1] == 1


# ---------- 4. raw vs adjusted 분리 row ----------


@pytest.mark.asyncio
async def test_upsert_many_separates_raw_and_adjusted(session: AsyncSession) -> None:
    """UNIQUE (stock_id, trading_date, adjusted) — 같은 일자 raw + adjusted 둘 다 row."""
    stock_id = await _create_stock(session)
    repo = StockPriceRepository(session)

    rows = [
        _ohlcv(stock_id=stock_id, trading_date=date(2025, 9, 8), adjusted=True, close=70000),
        _ohlcv(stock_id=stock_id, trading_date=date(2025, 9, 8), adjusted=False, close=72000),
    ]
    await repo.upsert_many(rows, exchange=ExchangeType.KRX)
    await session.commit()

    res = await session.execute(
        text("SELECT COUNT(*) FROM kiwoom.stock_price_krx WHERE stock_id = :sid").bindparams(sid=stock_id)
    )
    assert res.scalar_one() == 2


# ---------- 5. trading_date=date.min 빈 row 스킵 ----------


@pytest.mark.asyncio
async def test_upsert_many_skips_empty_trading_date(session: AsyncSession) -> None:
    """ka10081 응답의 빈 dt → date.min 으로 정규화. caller skip 방어."""
    stock_id = await _create_stock(session)
    repo = StockPriceRepository(session)

    rows = [
        _ohlcv(stock_id=stock_id, trading_date=date(2025, 9, 8)),
        _ohlcv(stock_id=stock_id, trading_date=date.min),  # 빈 응답 row
    ]
    await repo.upsert_many(rows, exchange=ExchangeType.KRX)
    await session.commit()

    res = await session.execute(
        text("SELECT COUNT(*) FROM kiwoom.stock_price_krx WHERE stock_id = :sid").bindparams(sid=stock_id)
    )
    assert res.scalar_one() == 1, "date.min 은 영속화 안 됨"


# ---------- 6. 빈 list ----------


@pytest.mark.asyncio
async def test_upsert_many_empty_list_returns_zero(session: AsyncSession) -> None:
    repo = StockPriceRepository(session)
    affected = await repo.upsert_many([], exchange=ExchangeType.KRX)
    assert affected == 0


# ---------- 7. 다중 stock 다중 일자 ----------


@pytest.mark.asyncio
async def test_upsert_many_multi_stock_multi_date(session: AsyncSession) -> None:
    sid_a = await _create_stock(session, "005930")
    sid_b = await _create_stock(session, "000660")
    repo = StockPriceRepository(session)

    rows = [
        _ohlcv(stock_id=sid_a, trading_date=date(2025, 9, 8)),
        _ohlcv(stock_id=sid_a, trading_date=date(2025, 9, 5)),
        _ohlcv(stock_id=sid_b, trading_date=date(2025, 9, 8)),
    ]
    await repo.upsert_many(rows, exchange=ExchangeType.KRX)
    await session.commit()

    res = await session.execute(text("SELECT COUNT(*) FROM kiwoom.stock_price_krx"))
    assert res.scalar_one() == 3


# ---------- 8. 잘못된 exchange ----------


@pytest.mark.asyncio
async def test_upsert_many_rejects_unsupported_exchange(session: AsyncSession) -> None:
    """SOR 은 본 chunk 미지원 (ka10081 응답이 KRX/NXT 만 영속화)."""
    repo = StockPriceRepository(session)

    with pytest.raises(ValueError, match="unsupported exchange"):
        await repo.upsert_many([], exchange=ExchangeType.SOR)
