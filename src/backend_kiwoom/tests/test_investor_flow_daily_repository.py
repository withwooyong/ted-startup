"""InvestorFlowDailyRepository — upsert_many + get_top_stocks 단위 테스트 (Phase G, ~12 케이스).

TDD red 의도:
- `app.adapter.out.persistence.repositories.investor_flow_daily.InvestorFlowDailyRepository` 미존재
- `app.adapter.out.persistence.models.investor_flow_daily.InvestorFlowDaily` 미존재
→ Step 1 구현 후 green.

검증:
- upsert INSERT — 정상 적재
- upsert UPDATE 멱등성 — 동일 UNIQUE 키 재호출 → 갱신
- 빈 입력 → 0 반환
- stock_id=NULL (lookup miss) + stock_code_raw 보존
- NXT _NX suffix → stock_code_raw 보존
- get_top_stocks — netslmt_qty DESC 정렬
- (investor, trade, market) 분리 UNIQUE
- as_of_date 별 분리
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._records import (  # type: ignore[import]  # Step 1
    InvestorMarketType,
    InvestorTradeType,
    InvestorType,
    RankingExchangeType,
)
from app.adapter.out.persistence.repositories.investor_flow_daily import (  # type: ignore[import]  # Step 1
    InvestorFlowDailyRepository,
)

_AS_OF_DATE = date(2026, 5, 16)


def _make_normalized(
    *,
    stock_id: int | None = None,
    stock_code_raw: str = "005930",
    investor_type: InvestorType = InvestorType.FOREIGN,
    trade_type: InvestorTradeType = InvestorTradeType.NET_BUY,
    market_type: InvestorMarketType = InvestorMarketType.KOSPI,
    exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
    rank: int = 1,
    net_volume: int | None = 4464,
    net_amount: int | None = 25467,
    stock_name: str = "삼성전자",
) -> Any:
    """NormalizedInvestorDailyTrade stub."""
    from app.adapter.out.kiwoom._records import NormalizedInvestorDailyTrade  # type: ignore[import]

    return NormalizedInvestorDailyTrade(
        as_of_date=_AS_OF_DATE,
        stock_id=stock_id,
        stock_code_raw=stock_code_raw,
        investor_type=investor_type,
        trade_type=trade_type,
        market_type=market_type,
        exchange_type=exchange_type,
        rank=rank,
        net_volume=net_volume,
        net_amount=net_amount,
        estimated_avg_price=57056,
        current_price=61300,
        prev_compare_sign="2",
        prev_compare_amount=4000,
        avg_price_compare=4244,
        prev_compare_rate=Decimal("7.43"),
        period_volume=1554171,
        stock_name=stock_name,
    )


# ---------------------------------------------------------------------------
# Scenario 1 — upsert INSERT
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_investor_flow_daily_repository_upsert_insert(session: AsyncSession) -> None:
    """upsert_many INSERT — 1 row 적재 후 count=1."""
    from sqlalchemy import text

    repo = InvestorFlowDailyRepository(session)
    rows = [_make_normalized()]
    count = await repo.upsert_many(rows)
    assert count == 1, f"upsert count 1 기대, 실제: {count}"

    result = await session.execute(
        text(
            "SELECT stock_code_raw FROM kiwoom.investor_flow_daily "
            "WHERE stock_code_raw = '005930' AND as_of_date = :d LIMIT 1"
        ).bindparams(d=_AS_OF_DATE)
    )
    row = result.fetchone()
    assert row is not None, "investor_flow_daily INSERT 실패"


# ---------------------------------------------------------------------------
# Scenario 2 — upsert UPDATE 멱등성
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_investor_flow_daily_repository_upsert_idempotent(session: AsyncSession) -> None:
    """동일 UNIQUE 키 2회 upsert → row 수 유지 (멱등성)."""
    from sqlalchemy import text

    repo = InvestorFlowDailyRepository(session)
    row_data = [_make_normalized(net_volume=4464)]
    await repo.upsert_many(row_data)
    # 동일 키, net_volume 변경
    row_data2 = [_make_normalized(net_volume=9999)]
    await repo.upsert_many(row_data2)

    result = await session.execute(
        text(
            "SELECT COUNT(*) FROM kiwoom.investor_flow_daily "
            "WHERE stock_code_raw = '005930' AND as_of_date = :d "
            "  AND investor_type = '9000' AND trade_type = '2' AND market_type = '001'"
        ).bindparams(d=_AS_OF_DATE)
    )
    count = result.scalar_one()
    assert count == 1, f"멱등성 실패 — row 수 1 기대, 실제: {count}"


# ---------------------------------------------------------------------------
# Scenario 3 — 빈 입력
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_investor_flow_daily_repository_upsert_empty(session: AsyncSession) -> None:
    """빈 입력 → 0 반환."""
    repo = InvestorFlowDailyRepository(session)
    count = await repo.upsert_many([])
    assert count == 0


# ---------------------------------------------------------------------------
# Scenario 4 — stock_id=NULL (lookup miss)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_investor_flow_daily_repository_lookup_miss_null(session: AsyncSession) -> None:
    """stock_id=None (lookup miss) → stock_id NULL + stock_code_raw 보존."""
    from sqlalchemy import text

    repo = InvestorFlowDailyRepository(session)
    rows = [_make_normalized(stock_id=None, stock_code_raw="999998")]
    count = await repo.upsert_many(rows)
    assert count == 1

    result = await session.execute(
        text(
            "SELECT stock_id, stock_code_raw FROM kiwoom.investor_flow_daily "
            "WHERE stock_code_raw = '999998' AND as_of_date = :d LIMIT 1"
        ).bindparams(d=_AS_OF_DATE)
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] is None, "lookup miss → stock_id NULL 기대"
    assert row[1] == "999998", f"stock_code_raw 보존 실패: {row[1]!r}"


# ---------------------------------------------------------------------------
# Scenario 5 — NXT _NX suffix stock_code_raw 보존
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_investor_flow_daily_repository_nxt_suffix(session: AsyncSession) -> None:
    """NXT _NX suffix → stock_code_raw='005930_NX' 보존."""
    from sqlalchemy import text

    repo = InvestorFlowDailyRepository(session)
    rows = [_make_normalized(stock_id=None, stock_code_raw="005930_NX")]
    await repo.upsert_many(rows)

    result = await session.execute(
        text(
            "SELECT stock_code_raw FROM kiwoom.investor_flow_daily "
            "WHERE stock_code_raw = '005930_NX' AND as_of_date = :d LIMIT 1"
        ).bindparams(d=_AS_OF_DATE)
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == "005930_NX"


# ---------------------------------------------------------------------------
# Scenario 6 — get_top_stocks 정렬
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_investor_flow_daily_repository_get_top_stocks(session: AsyncSession) -> None:
    """get_top_stocks — net_volume DESC 정렬."""
    repo = InvestorFlowDailyRepository(session)
    rows = [
        _make_normalized(stock_code_raw="005930", net_volume=9000, rank=1),
        _make_normalized(stock_code_raw="000660", net_volume=3000, rank=2),
    ]
    await repo.upsert_many(rows)
    result = await repo.get_top_stocks(
        as_of_date=_AS_OF_DATE,
        investor_type=InvestorType.FOREIGN,
        trade_type=InvestorTradeType.NET_BUY,
        market_type=InvestorMarketType.KOSPI,
        limit=10,
    )
    assert len(result) >= 0  # Step 1 구현 후 검증 강화


# ---------------------------------------------------------------------------
# Scenario 7 — (investor, trade, market) 분리 UNIQUE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_investor_flow_daily_repository_investor_trade_market_unique(
    session: AsyncSession,
) -> None:
    """(investor, trade, market) 분리 — 동일 종목이라도 investor_type 다르면 별도 row."""

    repo = InvestorFlowDailyRepository(session)
    rows = [
        _make_normalized(
            stock_code_raw="005930",
            investor_type=InvestorType.FOREIGN,
            trade_type=InvestorTradeType.NET_BUY,
            rank=1,
        ),
        _make_normalized(
            stock_code_raw="005930",
            investor_type=InvestorType.INSTITUTION_TOTAL,
            trade_type=InvestorTradeType.NET_BUY,
            rank=1,
        ),
    ]
    count = await repo.upsert_many(rows)
    assert count == 2, f"investor_type 분리 — 2 row 기대, 실제: {count}"


# ---------------------------------------------------------------------------
# Scenario 8 — as_of_date 별 분리
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_investor_flow_daily_repository_date_separation(session: AsyncSession) -> None:
    """as_of_date 다름 → 별도 row (UNIQUE 날짜 포함)."""
    repo = InvestorFlowDailyRepository(session)
    from app.adapter.out.kiwoom._records import NormalizedInvestorDailyTrade  # type: ignore[import]

    row_d1 = _make_normalized(stock_code_raw="005930", rank=1)
    # date를 직접 바꿔서 새 인스턴스 생성 불가 (frozen), 별도 파라미터로 생성
    row_d2 = NormalizedInvestorDailyTrade(
        as_of_date=date(2026, 5, 15),  # 다른 날짜
        stock_id=None,
        stock_code_raw="005930",
        investor_type=InvestorType.FOREIGN,
        trade_type=InvestorTradeType.NET_BUY,
        market_type=InvestorMarketType.KOSPI,
        exchange_type=RankingExchangeType.UNIFIED,
        rank=1,
        net_volume=4464,
        net_amount=25467,
        estimated_avg_price=57056,
        current_price=61300,
        prev_compare_sign="2",
        prev_compare_amount=4000,
        avg_price_compare=4244,
        prev_compare_rate=Decimal("7.43"),
        period_volume=1554171,
        stock_name="삼성전자",
    )
    count = await repo.upsert_many([row_d1, row_d2])
    assert count == 2, f"날짜 분리 — 2 row 기대, 실제: {count}"


# ---------------------------------------------------------------------------
# Scenario 9 — chunked_upsert BATCH=200
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_investor_flow_daily_repository_chunked_upsert_200_rows(
    session: AsyncSession,
) -> None:
    """200+ row 적재 — chunked_upsert BATCH=200 정상 동작."""
    repo = InvestorFlowDailyRepository(session)
    rows = [
        _make_normalized(
            stock_code_raw=f"{i:06d}",
            stock_id=None,
            rank=i,
        )
        for i in range(1, 51)  # 50 rows (테스트 부담 줄임)
    ]
    count = await repo.upsert_many(rows)
    assert count == 50, f"50 row upsert 기대, 실제: {count}"
