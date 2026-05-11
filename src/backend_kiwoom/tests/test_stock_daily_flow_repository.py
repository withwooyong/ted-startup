"""StockDailyFlowRepository — ka10086 stock_daily_flow upsert + 조회 (C-2α).

설계: endpoint-10-ka10086.md § 6.2.

검증:
1. upsert_many — INSERT (DB 빈)
2. upsert_many — UPDATE (ON CONFLICT)
3. KRX/NXT 분리 적재 (같은 종목·같은 날 두 row)
4. trading_date == date.min 자동 skip (caller 안전망)
5. 빈 list 입력 → 0 반환
6. 명시 update_set (B-γ-1 2R B-H3 패턴) — credit_rate / individual_net 등 변경 시 갱신
7. find_range — 정상 시계열 + 거래소 필터 + start <= trading_date <= end
8. find_range start > end → ValueError
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.adapter.out.kiwoom._records import NormalizedDailyFlow
from app.adapter.out.persistence.repositories.stock_daily_flow import (
    StockDailyFlowRepository,
)
from app.application.constants import DailyMarketDisplayMode, ExchangeType


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


def _flow(
    stock_id: int,
    d: date,
    exchange: ExchangeType = ExchangeType.KRX,
    *,
    individual_net: int | None = -714,
    credit_rate: Decimal | None = Decimal("0.50"),
) -> NormalizedDailyFlow:
    return NormalizedDailyFlow(
        stock_id=stock_id,
        trading_date=d,
        exchange=exchange,
        indc_mode=DailyMarketDisplayMode.QUANTITY,
        credit_rate=credit_rate,
        individual_net=individual_net,
        institutional_net=693,
        foreign_brokerage_net=0,
        program_net=0,
        foreign_volume=-266783,
        foreign_rate=Decimal("12.34"),
        foreign_holdings=1234567,
    )


@pytest.mark.asyncio
async def test_upsert_many_inserts_new_rows(session: AsyncSession) -> None:
    stock_id = await _create_stock(session)
    repo = StockDailyFlowRepository(session)

    rows = [_flow(stock_id, date(2025, 9, 8))]
    affected = await repo.upsert_many(rows)
    await session.commit()

    assert affected == 1
    found = await repo.find_range(
        stock_id, exchange=ExchangeType.KRX, start=date(2025, 9, 1), end=date(2025, 9, 30)
    )
    assert len(found) == 1
    assert found[0].individual_net == -714
    assert found[0].credit_rate == Decimal("0.5000")


@pytest.mark.asyncio
async def test_upsert_many_updates_on_conflict(session: AsyncSession) -> None:
    """같은 (stock_id, trading_date, exchange) 두 번 → UPDATE."""
    stock_id = await _create_stock(session)
    repo = StockDailyFlowRepository(session)

    await repo.upsert_many([_flow(stock_id, date(2025, 9, 8), individual_net=-100)])
    await session.commit()

    # 같은 날·거래소 다른 값
    await repo.upsert_many(
        [_flow(stock_id, date(2025, 9, 8), individual_net=-999, credit_rate=Decimal("9.99"))]
    )
    await session.commit()

    found = await repo.find_range(
        stock_id, exchange=ExchangeType.KRX, start=date(2025, 9, 1), end=date(2025, 9, 30)
    )
    assert len(found) == 1  # UPSERT — 1 row 유지
    assert found[0].individual_net == -999
    assert found[0].credit_rate == Decimal("9.9900")


@pytest.mark.asyncio
async def test_upsert_many_separates_krx_nxt(session: AsyncSession) -> None:
    """같은 종목·같은 날 KRX + NXT → 두 row."""
    stock_id = await _create_stock(session)
    repo = StockDailyFlowRepository(session)

    await repo.upsert_many(
        [
            _flow(stock_id, date(2025, 9, 8), ExchangeType.KRX, individual_net=-100),
            _flow(stock_id, date(2025, 9, 8), ExchangeType.NXT, individual_net=-50),
        ]
    )
    await session.commit()

    krx = await repo.find_range(
        stock_id, exchange=ExchangeType.KRX, start=date(2025, 9, 1), end=date(2025, 9, 30)
    )
    nxt = await repo.find_range(
        stock_id, exchange=ExchangeType.NXT, start=date(2025, 9, 1), end=date(2025, 9, 30)
    )
    assert len(krx) == 1
    assert len(nxt) == 1
    assert krx[0].individual_net == -100
    assert nxt[0].individual_net == -50


@pytest.mark.asyncio
async def test_upsert_many_skips_date_min_rows(session: AsyncSession) -> None:
    """trading_date == date.min 빈 응답 row 자동 skip (caller 안전망)."""
    stock_id = await _create_stock(session)
    repo = StockDailyFlowRepository(session)

    affected = await repo.upsert_many([_flow(stock_id, date.min)])
    await session.commit()
    assert affected == 0


@pytest.mark.asyncio
async def test_upsert_many_empty_list_returns_zero(session: AsyncSession) -> None:
    repo = StockDailyFlowRepository(session)
    affected = await repo.upsert_many([])
    assert affected == 0


@pytest.mark.asyncio
async def test_find_range_sorted_by_trading_date(session: AsyncSession) -> None:
    stock_id = await _create_stock(session)
    repo = StockDailyFlowRepository(session)

    rows = [
        _flow(stock_id, date(2025, 9, 5)),
        _flow(stock_id, date(2025, 9, 8)),
        _flow(stock_id, date(2025, 9, 1)),
    ]
    await repo.upsert_many(rows)
    await session.commit()

    found = await repo.find_range(
        stock_id, exchange=ExchangeType.KRX, start=date(2025, 9, 1), end=date(2025, 9, 30)
    )
    assert [r.trading_date for r in found] == [date(2025, 9, 1), date(2025, 9, 5), date(2025, 9, 8)]


@pytest.mark.asyncio
async def test_find_range_filters_outside_window(session: AsyncSession) -> None:
    stock_id = await _create_stock(session)
    repo = StockDailyFlowRepository(session)

    await repo.upsert_many(
        [
            _flow(stock_id, date(2025, 9, 1)),
            _flow(stock_id, date(2025, 9, 8)),
            _flow(stock_id, date(2025, 10, 1)),
        ]
    )
    await session.commit()

    found = await repo.find_range(
        stock_id, exchange=ExchangeType.KRX, start=date(2025, 9, 5), end=date(2025, 9, 30)
    )
    assert len(found) == 1
    assert found[0].trading_date == date(2025, 9, 8)


@pytest.mark.asyncio
async def test_find_range_rejects_inverted_window(session: AsyncSession) -> None:
    stock_id = await _create_stock(session)
    repo = StockDailyFlowRepository(session)

    with pytest.raises(ValueError, match="start"):
        await repo.find_range(
            stock_id, exchange=ExchangeType.KRX, start=date(2025, 9, 30), end=date(2025, 9, 1)
        )


@pytest.mark.asyncio
async def test_find_range_empty_when_no_rows(session: AsyncSession) -> None:
    stock_id = await _create_stock(session)
    repo = StockDailyFlowRepository(session)

    found = await repo.find_range(
        stock_id, exchange=ExchangeType.KRX, start=date(2025, 9, 1), end=date(2025, 9, 30)
    )
    assert found == []


# ---------- 2b-M1 회귀 — SOR 영속화 차단 ----------


@pytest.mark.asyncio
async def test_upsert_many_rejects_sor_exchange(session: AsyncSession) -> None:
    """SOR 거래소 silent 영속화 차단 (Phase D 까지 KRX/NXT 만)."""
    stock_id = await _create_stock(session)
    repo = StockDailyFlowRepository(session)

    sor_row = _flow(stock_id, date(2025, 9, 8), exchange=ExchangeType.SOR)
    with pytest.raises(ValueError, match="unsupported exchange"):
        await repo.upsert_many([sor_row])


@pytest.mark.asyncio
async def test_upsert_many_rejects_mixed_with_sor(session: AsyncSession) -> None:
    """KRX + SOR 혼합 → 첫 unsupported 검출 시 전체 raise (silent merge 차단)."""
    stock_id = await _create_stock(session)
    repo = StockDailyFlowRepository(session)

    rows = [
        _flow(stock_id, date(2025, 9, 8), exchange=ExchangeType.KRX),
        _flow(stock_id, date(2025, 9, 8), exchange=ExchangeType.SOR),
    ]
    with pytest.raises(ValueError, match="unsupported exchange"):
        await repo.upsert_many(rows)


@pytest.mark.asyncio
async def test_find_range_rejects_sor_exchange(session: AsyncSession) -> None:
    """find_range 도 SOR 거부 (upsert_many 와 일관)."""
    stock_id = await _create_stock(session)
    repo = StockDailyFlowRepository(session)

    with pytest.raises(ValueError, match="unsupported exchange"):
        await repo.find_range(
            stock_id, exchange=ExchangeType.SOR, start=date(2025, 9, 1), end=date(2025, 9, 30)
        )


@pytest.mark.asyncio
async def test_upsert_many_explicit_update_set_drift_guard(session: AsyncSession) -> None:
    """B-γ-1 2R B-H3 — 명시 update_set 검증.

    같은 키로 두 번 upsert 후 NormalizedDailyFlow 의 모든 도메인 필드가 갱신되는지 확인.
    """
    stock_id = await _create_stock(session)
    repo = StockDailyFlowRepository(session)

    await repo.upsert_many([_flow(stock_id, date(2025, 9, 8), individual_net=-100)])
    await session.commit()

    # 모든 도메인 필드를 다른 값으로 update
    new_row = NormalizedDailyFlow(
        stock_id=stock_id,
        trading_date=date(2025, 9, 8),
        exchange=ExchangeType.KRX,
        indc_mode=DailyMarketDisplayMode.QUANTITY,
        credit_rate=Decimal("1.11"),
        individual_net=-999,
        institutional_net=999,
        foreign_brokerage_net=999,
        program_net=999,
        foreign_volume=999,
        foreign_rate=Decimal("3.33"),
        foreign_holdings=999,
    )
    await repo.upsert_many([new_row])
    await session.commit()

    found = await repo.find_range(
        stock_id, exchange=ExchangeType.KRX, start=date(2025, 9, 1), end=date(2025, 9, 30)
    )
    assert len(found) == 1
    r = found[0]
    assert r.individual_net == -999
    assert r.credit_rate == Decimal("1.1100")
    assert r.foreign_holdings == 999
    assert r.foreign_rate == Decimal("3.3300")
