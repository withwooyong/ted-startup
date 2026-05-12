"""LendingBalanceKwRepository — upsert_market + upsert_stock + get_market_range + get_stock_range.

chunk = Phase E, plan doc endpoint-15-ka10014.md § 12 참조.
설계: endpoint-16-ka10068.md § 6.2 + endpoint-17-ka20068.md § 6.2.

test_sector_price_repository.py 의 upsert idempotent / ON CONFLICT / FK /
partial unique 패턴 1:1 응용 + lending scope 분기 추가.

검증 (8 시나리오):
1. upsert_market INSERT (stock_id NULL)
2. upsert_market UPDATE 멱등성 (ON CONFLICT)
3. upsert_stock INSERT (FK stock_id)
4. upsert_stock UPDATE 멱등성
5. partial unique 충돌 분리 검증 (MARKET row + STOCK row 같은 trading_date)
6. CHECK constraint 검증 (scope=MARKET + stock_id NOT NULL → IntegrityError)
7. get_market_range (date range 조회)
8. get_stock_range (date range + stock_id 조회)
"""

from __future__ import annotations

from datetime import date

import pytest
from app.adapter.out.persistence.repositories.lending_balance import (
    LendingBalanceKwRepository,
)
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._records import LendingScope, NormalizedLendingMarket

# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


async def _insert_test_stock(session: AsyncSession, code: str = "TST001") -> int:
    """테스트용 stock 1행 INSERT 후 id 반환."""
    await session.execute(
        text(
            "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code, is_active) "
            "VALUES (:code, 'test-stock', '0', TRUE) "
            "ON CONFLICT (stock_code) DO UPDATE SET stock_name = EXCLUDED.stock_name"
        ).bindparams(code=code)
    )
    result = await session.execute(
        text("SELECT id FROM kiwoom.stock WHERE stock_code = :code").bindparams(code=code)
    )
    return int(result.scalar_one())


def _market_normalized(
    trading_date: date,
    contracted_volume: int = 35330036,
    delta_volume: int = 10112672,
) -> NormalizedLendingMarket:
    """scope=MARKET NormalizedLendingMarket stub (stock_id=None)."""
    return NormalizedLendingMarket(
        scope=LendingScope.MARKET,
        stock_id=None,
        trading_date=trading_date,
        contracted_volume=contracted_volume,
        repaid_volume=25217364,
        delta_volume=delta_volume,
        balance_volume=2460259444,
        balance_amount=73956254,
    )


def _stock_normalized(
    stock_id: int,
    trading_date: date,
    contracted_volume: int = 1210354,
    delta_volume: int = -1482754,
) -> NormalizedLendingMarket:
    """scope=STOCK NormalizedLendingMarket stub (stock_id 필수)."""
    return NormalizedLendingMarket(
        scope=LendingScope.STOCK,
        stock_id=stock_id,
        trading_date=trading_date,
        contracted_volume=contracted_volume,
        repaid_volume=2693108,
        delta_volume=delta_volume,
        balance_volume=98242435,
        balance_amount=5452455,
    )


# ---------------------------------------------------------------------------
# 1. upsert_market INSERT (stock_id NULL)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_market_inserts_rows_with_null_stock_id(
    session: AsyncSession,
) -> None:
    """scope=MARKET row 2건 INSERT — stock_id=NULL 확인.

    endpoint-16 § 6.2 upsert_market 정상 INSERT.
    """
    repo = LendingBalanceKwRepository(session)

    rows = [
        _market_normalized(date(2025, 4, 30)),
        _market_normalized(date(2025, 4, 28)),
    ]
    affected = await repo.upsert_market(rows)
    assert affected == 2

    result = await session.execute(
        text(
            "SELECT COUNT(*) FROM kiwoom.lending_balance_kw "
            "WHERE scope = 'MARKET' AND stock_id IS NULL"
        )
    )
    assert result.scalar_one() == 2


# ---------------------------------------------------------------------------
# 2. upsert_market UPDATE 멱등성 (ON CONFLICT)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_market_on_conflict_updates_existing_row(
    session: AsyncSession,
) -> None:
    """ON CONFLICT (scope, trading_date) WHERE scope='MARKET' DO UPDATE — 멱등성.

    같은 trading_date 에 두 번 호출 시 row 갱신 (INSERT 아닌 UPDATE).
    """
    repo = LendingBalanceKwRepository(session)

    row1 = _market_normalized(date(2025, 4, 30), contracted_volume=35330036)
    await repo.upsert_market([row1])

    row2 = _market_normalized(date(2025, 4, 30), contracted_volume=99999999)
    affected = await repo.upsert_market([row2])
    assert affected == 1

    result = await session.execute(
        text(
            "SELECT contracted_volume FROM kiwoom.lending_balance_kw "
            "WHERE scope = 'MARKET' AND trading_date = '2025-04-30'"
        )
    )
    assert result.scalar_one() == 99999999

    count = await session.execute(
        text("SELECT COUNT(*) FROM kiwoom.lending_balance_kw WHERE scope = 'MARKET'")
    )
    assert count.scalar_one() == 1  # 갱신 (중복 row 없음)


# ---------------------------------------------------------------------------
# 3. upsert_stock INSERT (FK stock_id)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_stock_inserts_rows_with_stock_id_fk(
    session: AsyncSession,
) -> None:
    """scope=STOCK row 2건 INSERT — stock_id FK 확인.

    endpoint-17 § 6.2 upsert_stock 정상 INSERT.
    """
    sid = await _insert_test_stock(session, "005930")
    repo = LendingBalanceKwRepository(session)

    rows = [
        _stock_normalized(sid, date(2025, 4, 30)),
        _stock_normalized(sid, date(2025, 4, 28)),
    ]
    affected = await repo.upsert_stock(rows)
    assert affected == 2

    result = await session.execute(
        text(
            "SELECT COUNT(*) FROM kiwoom.lending_balance_kw "
            "WHERE scope = 'STOCK' AND stock_id = :sid"
        ).bindparams(sid=sid)
    )
    assert result.scalar_one() == 2


# ---------------------------------------------------------------------------
# 4. upsert_stock UPDATE 멱등성
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_stock_on_conflict_updates_existing_row(
    session: AsyncSession,
) -> None:
    """ON CONFLICT (scope, stock_id, trading_date) WHERE scope='STOCK' DO UPDATE.

    같은 종목 + trading_date 에 두 번 호출 시 row 갱신.
    """
    sid = await _insert_test_stock(session, "000660")
    repo = LendingBalanceKwRepository(session)

    row1 = _stock_normalized(sid, date(2025, 4, 30), contracted_volume=1210354)
    await repo.upsert_stock([row1])

    row2 = _stock_normalized(sid, date(2025, 4, 30), contracted_volume=9999999)
    affected = await repo.upsert_stock([row2])
    assert affected == 1

    result = await session.execute(
        text(
            "SELECT contracted_volume FROM kiwoom.lending_balance_kw "
            "WHERE scope = 'STOCK' AND stock_id = :sid AND trading_date = '2025-04-30'"
        ).bindparams(sid=sid)
    )
    assert result.scalar_one() == 9999999

    count = await session.execute(
        text(
            "SELECT COUNT(*) FROM kiwoom.lending_balance_kw "
            "WHERE scope = 'STOCK' AND stock_id = :sid"
        ).bindparams(sid=sid)
    )
    assert count.scalar_one() == 1


# ---------------------------------------------------------------------------
# 5. partial unique 충돌 분리 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_market_and_stock_rows_coexist_same_trading_date(
    session: AsyncSession,
) -> None:
    """MARKET row + STOCK row 같은 trading_date → 두 row 분리 (partial unique 인덱스).

    endpoint-16 § 5.1 / § 9.2 MARKET / STOCK 충돌 안 함 시나리오.
    uq_lending_market_date: (scope, trading_date) WHERE scope='MARKET'
    uq_lending_stock_date: (scope, stock_id, trading_date) WHERE scope='STOCK'
    → 두 인덱스가 독립이라 같은 trading_date 여도 scope 다르면 충돌 없음.
    """
    sid = await _insert_test_stock(session, "005930")
    repo = LendingBalanceKwRepository(session)

    market_row = _market_normalized(date(2025, 4, 30))
    stock_row = _stock_normalized(sid, date(2025, 4, 30))

    await repo.upsert_market([market_row])
    await repo.upsert_stock([stock_row])

    result = await session.execute(
        text(
            "SELECT scope, stock_id FROM kiwoom.lending_balance_kw "
            "WHERE trading_date = '2025-04-30' ORDER BY scope"
        )
    )
    rows_db = result.fetchall()
    assert len(rows_db) == 2, "MARKET 1 + STOCK 1 = 2 row"

    scopes = {r.scope for r in rows_db}
    assert scopes == {"MARKET", "STOCK"}

    market_db = next(r for r in rows_db if r.scope == "MARKET")
    stock_db = next(r for r in rows_db if r.scope == "STOCK")
    assert market_db.stock_id is None
    assert stock_db.stock_id == sid


# ---------------------------------------------------------------------------
# 6. CHECK constraint 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_market_with_stock_id_raises_integrity_error(
    session: AsyncSession,
) -> None:
    """scope=MARKET + stock_id NOT NULL → IntegrityError (chk_lending_scope).

    endpoint-16 § 5.1 CHECK constraint:
    (scope='MARKET' AND stock_id IS NULL) OR (scope='STOCK' AND stock_id IS NOT NULL)
    """
    sid = await _insert_test_stock(session, "005930")

    with pytest.raises(IntegrityError):
        await session.execute(
            text(
                "INSERT INTO kiwoom.lending_balance_kw "
                "(scope, stock_id, trading_date, contracted_volume) "
                "VALUES ('MARKET', :sid, '2025-04-30', 1000)"
            ).bindparams(sid=sid)
        )
        await session.flush()


# ---------------------------------------------------------------------------
# 7. get_market_range
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_market_range_returns_rows_in_date_range(
    session: AsyncSession,
) -> None:
    """date range 조회 — start_date ~ end_date 사이의 MARKET row 반환.

    endpoint-16 § 6.2 get_market_range.
    """
    repo = LendingBalanceKwRepository(session)

    dates = [date(2025, 4, 28), date(2025, 4, 29), date(2025, 4, 30), date(2025, 5, 1)]
    rows = [_market_normalized(d) for d in dates]
    await repo.upsert_market(rows)

    result = await repo.get_market_range(
        start_date=date(2025, 4, 29),
        end_date=date(2025, 4, 30),
    )

    assert len(result) == 2
    retrieved_dates = [r.trading_date for r in result]
    assert date(2025, 4, 29) in retrieved_dates
    assert date(2025, 4, 30) in retrieved_dates
    assert date(2025, 4, 28) not in retrieved_dates
    assert date(2025, 5, 1) not in retrieved_dates


# ---------------------------------------------------------------------------
# 8. get_stock_range
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_stock_range_returns_rows_in_date_range_for_stock(
    session: AsyncSession,
) -> None:
    """date range + stock_id 조회 — 해당 종목의 STOCK row 반환.

    endpoint-17 § 6.2 get_stock_range.
    다른 종목의 row 는 포함되지 않아야 함.
    """
    sid1 = await _insert_test_stock(session, "005930")
    sid2 = await _insert_test_stock(session, "000660")
    repo = LendingBalanceKwRepository(session)

    # sid1 3건 + sid2 1건
    sid1_rows = [
        _stock_normalized(sid1, date(2025, 4, 28)),
        _stock_normalized(sid1, date(2025, 4, 29)),
        _stock_normalized(sid1, date(2025, 4, 30)),
    ]
    sid2_rows = [_stock_normalized(sid2, date(2025, 4, 29))]
    await repo.upsert_stock(sid1_rows)
    await repo.upsert_stock(sid2_rows)

    result = await repo.get_stock_range(
        sid1,
        start_date=date(2025, 4, 28),
        end_date=date(2025, 4, 30),
    )

    assert len(result) == 3
    for row in result:
        assert row.stock_id == sid1
        assert row.scope == "STOCK"

    # sid2 row 포함 안 됨
    result2 = await repo.get_stock_range(
        sid2,
        start_date=date(2025, 4, 28),
        end_date=date(2025, 4, 30),
    )
    assert len(result2) == 1
    assert result2[0].stock_id == sid2
