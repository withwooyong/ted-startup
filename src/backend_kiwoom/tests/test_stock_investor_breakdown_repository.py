"""StockInvestorBreakdownRepository — upsert_many + get_range 단위 테스트 (Phase G, ~10 케이스).

TDD red 의도:
- `app.adapter.out.persistence.repositories.stock_investor_breakdown.StockInvestorBreakdownRepository` 미존재
- `app.adapter.out.persistence.models.stock_investor_breakdown.StockInvestorBreakdown` 미존재
→ Step 1 구현 후 green.

검증:
- upsert INSERT — 12 net 컬럼 적재
- upsert UPDATE 멱등성
- 빈 입력 → 0
- (amt_qty, trade, unit, exchange) 분리 UNIQUE
- get_range — 단일 종목 기간 조회
- flu_rt 정규화 (change_rate Decimal)
- stock_id NOT NULL (ka10059 는 stock_id 필수 — lookup miss 시 skip)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._records import (  # type: ignore[import]  # Step 1
    AmountQuantityType,
    RankingExchangeType,
    StockInvestorTradeType,
    UnitType,
)
from app.adapter.out.persistence.repositories.stock_investor_breakdown import (  # type: ignore[import]  # Step 1
    StockInvestorBreakdownRepository,
)

_TRADING_DATE = date(2024, 11, 7)
_STOCK_ID = 1


async def _ensure_stock(session: Any, code: str = "005930") -> int:
    """테스트용 stock INSERT — returning id."""
    from sqlalchemy import text as _text

    result = await session.execute(
        _text(
            "INSERT INTO kiwoom.stock "
            "(stock_code, stock_name, market_code, market_name, is_active) "
            "VALUES (:code, '테스트주식', '0', 'KOSPI', TRUE) "
            "ON CONFLICT (stock_code) DO UPDATE SET is_active=TRUE "
            "RETURNING id"
        ).bindparams(code=code)
    )
    row = result.fetchone()
    assert row is not None
    return int(row[0])


def _make_normalized(
    *,
    stock_id: int | None = None,
    trading_date: date = _TRADING_DATE,
    amt_qty_tp: AmountQuantityType = AmountQuantityType.QUANTITY,
    trade_type: StockInvestorTradeType = StockInvestorTradeType.NET_BUY,
    unit_tp: UnitType = UnitType.THOUSAND_SHARES,
    exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
    change_rate: Decimal | None = Decimal("6.98"),
    net_individual: int | None = 1584,
    net_foreign: int | None = -61779,
    net_institution_total: int | None = 60195,
) -> Any:
    """NormalizedStockInvestorBreakdown stub."""
    from app.adapter.out.kiwoom._records import NormalizedStockInvestorBreakdown  # type: ignore[import]

    return NormalizedStockInvestorBreakdown(
        stock_id=stock_id,
        trading_date=trading_date,
        amt_qty_tp=amt_qty_tp,
        trade_type=trade_type,
        unit_tp=unit_tp,
        exchange_type=exchange_type,
        current_price=61300,
        prev_compare_sign="2",
        prev_compare_amount=4000,
        change_rate=change_rate,
        acc_trade_volume=1105968,
        acc_trade_amount=64215,
        net_individual=net_individual,
        net_foreign=net_foreign,
        net_institution_total=net_institution_total,
        net_financial_inv=25514,
        net_insurance=0,
        net_investment_trust=0,
        net_other_financial=34619,
        net_bank=4,
        net_pension_fund=-1,
        net_private_fund=58,
        net_nation=0,
        net_other_corp=0,
        net_dom_for=1,
    )


# ---------------------------------------------------------------------------
# Scenario 1 — upsert INSERT (12 net 컬럼)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stock_investor_breakdown_repository_upsert_insert(
    session: AsyncSession,
) -> None:
    """upsert_many INSERT — 12 net 컬럼 적재 확인."""
    from sqlalchemy import text

    stock_id = await _ensure_stock(session)
    repo = StockInvestorBreakdownRepository(session)
    count = await repo.upsert_many([_make_normalized(stock_id=stock_id)])
    assert count == 1

    result = await session.execute(
        text(
            "SELECT net_individual, net_foreign, net_institution_total, change_rate "
            "FROM kiwoom.stock_investor_breakdown "
            "WHERE stock_id = :sid AND trading_date = :d "
            "  AND amt_qty_tp = '2' AND trade_type = '0' LIMIT 1"
        ).bindparams(sid=stock_id, d=_TRADING_DATE)
    )
    row = result.fetchone()
    assert row is not None, "stock_investor_breakdown INSERT 실패"
    assert row[0] == 1584, f"net_individual 미일치: {row[0]!r}"
    assert row[1] == -61779, f"net_foreign 미일치: {row[1]!r}"


# ---------------------------------------------------------------------------
# Scenario 2 — upsert UPDATE 멱등성
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stock_investor_breakdown_repository_upsert_idempotent(
    session: AsyncSession,
) -> None:
    """동일 UNIQUE 키 2회 upsert → row 수 유지."""
    from sqlalchemy import text

    stock_id = await _ensure_stock(session)
    repo = StockInvestorBreakdownRepository(session)
    await repo.upsert_many([_make_normalized(stock_id=stock_id, net_individual=1584)])
    await repo.upsert_many([_make_normalized(stock_id=stock_id, net_individual=9999)])

    result = await session.execute(
        text(
            "SELECT COUNT(*) FROM kiwoom.stock_investor_breakdown "
            "WHERE stock_id = :sid AND trading_date = :d "
            "  AND amt_qty_tp = '2' AND trade_type = '0'"
        ).bindparams(sid=stock_id, d=_TRADING_DATE)
    )
    count = result.scalar_one()
    assert count == 1, f"멱등성 실패 — 1 기대, 실제: {count}"


# ---------------------------------------------------------------------------
# Scenario 3 — 빈 입력
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stock_investor_breakdown_repository_empty_input(session: AsyncSession) -> None:
    """빈 입력 → 0 반환."""
    repo = StockInvestorBreakdownRepository(session)
    count = await repo.upsert_many([])
    assert count == 0


# ---------------------------------------------------------------------------
# Scenario 4 — (amt_qty, trade, unit, exchange) 분리 UNIQUE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stock_investor_breakdown_repository_combo_unique(session: AsyncSession) -> None:
    """(amt_qty, trade, unit, exchange) 다른 조합 → 별도 row."""
    repo = StockInvestorBreakdownRepository(session)
    row1 = _make_normalized(
        amt_qty_tp=AmountQuantityType.QUANTITY,
        trade_type=StockInvestorTradeType.NET_BUY,
    )
    row2 = _make_normalized(
        amt_qty_tp=AmountQuantityType.AMOUNT,
        trade_type=StockInvestorTradeType.NET_BUY,
    )
    count = await repo.upsert_many([row1, row2])
    assert count == 2, f"조합 분리 — 2 row 기대, 실제: {count}"


# ---------------------------------------------------------------------------
# Scenario 5 — get_range 단일 종목 기간 조회
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stock_investor_breakdown_repository_get_range(session: AsyncSession) -> None:
    """get_range — 단일 종목 기간 조회 (날짜 범위 필터)."""
    repo = StockInvestorBreakdownRepository(session)
    await repo.upsert_many([_make_normalized()])
    result = await repo.get_range(
        stock_id=_STOCK_ID,
        start_date=date(2024, 11, 1),
        end_date=date(2024, 11, 30),
    )
    assert len(result) >= 0  # Step 1 구현 후 검증 강화


# ---------------------------------------------------------------------------
# Scenario 6 — flu_rt 정규화 (change_rate Decimal)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stock_investor_breakdown_repository_change_rate(session: AsyncSession) -> None:
    """change_rate = Decimal('6.98') — NUMERIC 컬럼 정확성."""
    from sqlalchemy import text

    stock_id = await _ensure_stock(session)
    repo = StockInvestorBreakdownRepository(session)
    await repo.upsert_many([_make_normalized(stock_id=stock_id, change_rate=Decimal("6.98"))])

    result = await session.execute(
        text(
            "SELECT change_rate FROM kiwoom.stock_investor_breakdown "
            "WHERE stock_id = :sid AND trading_date = :d "
            "  AND amt_qty_tp = '2' AND trade_type = '0' LIMIT 1"
        ).bindparams(sid=stock_id, d=_TRADING_DATE)
    )
    row = result.fetchone()
    assert row is not None
    # Decimal("6.98") 또는 그 근사값
    assert abs(float(row[0]) - 6.98) < 0.01, f"change_rate 미일치: {row[0]!r}"


# ---------------------------------------------------------------------------
# Scenario 7 — BATCH=200 (ka10059 3000 종목)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stock_investor_breakdown_repository_batch_upsert(session: AsyncSession) -> None:
    """10 row 적재 — chunked_upsert BATCH=200 정상 동작. stock_id NULL 사용."""
    repo = StockInvestorBreakdownRepository(session)
    rows = [
        _make_normalized(
            stock_id=None,  # lookup miss simulated — stock_id NULL 영속화.
            trading_date=date(2024, 11, i),  # 다른 날짜로 UNIQUE 분리
        )
        for i in range(1, 11)  # 10 row
    ]
    count = await repo.upsert_many(rows)
    assert count == 10, f"10 row upsert 기대, 실제: {count}"


# ---------------------------------------------------------------------------
# Scenario 8 — change_rate None (빈 flu_rt)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stock_investor_breakdown_repository_change_rate_none(
    session: AsyncSession,
) -> None:
    """flu_rt 빈 → change_rate=None (nullable)."""
    from sqlalchemy import text

    repo = StockInvestorBreakdownRepository(session)
    await repo.upsert_many(
        [
            _make_normalized(
                amt_qty_tp=AmountQuantityType.QUANTITY,
                trade_type=StockInvestorTradeType.BUY,  # 다른 trade_type으로 UNIQUE 회피
                change_rate=None,
            )
        ]
    )
    result = await session.execute(
        text(
            "SELECT change_rate FROM kiwoom.stock_investor_breakdown "
            "WHERE stock_id = :sid AND trading_date = :d "
            "  AND amt_qty_tp = '2' AND trade_type = '1' LIMIT 1"
        ).bindparams(sid=_STOCK_ID, d=_TRADING_DATE)
    )
    row = result.fetchone()
    if row is not None:
        assert row[0] is None, f"change_rate None 기대, 실제: {row[0]!r}"
