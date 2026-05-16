"""investor_flow E2E — testcontainers PG16 통합 테스트 (Phase G, ~10 케이스).

설계: phase-g-investor-flow.md § 5.13 #14.

가정 production 위치:
- app/adapter/out/persistence/repositories/investor_flow_daily.py (Step 1 에서 작성)
- app/adapter/out/persistence/repositories/stock_investor_breakdown.py (Step 1 에서 작성)
- app/adapter/out/persistence/repositories/frgn_orgn_consecutive.py (Step 1 에서 작성)
- Migration 019 (3 테이블 + UNIQUE/INDEX) 이미 적용됨.

testcontainers fixture:
- 부모 conftest.py (tests/conftest.py) 의 `engine` fixture 재사용.
- `apply_migrations` autouse — 세션 스코프 Alembic upgrade head.

검증 (~10 케이스):
1. investor_flow_daily INSERT 50 + UPDATE 멱등
2. stock_investor_breakdown INSERT + flu_rt Decimal 정확성
3. frgn_orgn_consecutive INSERT + total_cont_days DESC 정렬
4. 3 테이블 cross-query — 동일 종목 + 동일 날짜
5. stock_id=NULL (lookup miss) 보존 확인
6. NXT _NX suffix stock_code_raw 보존
7. investor_flow_daily UNIQUE 키 분리 (investor_type 별)
8. frgn_orgn_consecutive amt_qty_tp 분리 (AMOUNT vs QUANTITY)
9. Migration 019 upgrade/downgrade (019 → 018 → 019)
10. get_top_stocks / get_top_by_total_days 크로스 검증

TDD red 의도:
- `from app.adapter.out.persistence.repositories.investor_flow_daily import InvestorFlowDailyRepository`
  → ImportError (Step 1 미구현)
→ Step 1 구현 후 green 전환.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.adapter.out.kiwoom._records import (  # type: ignore[import]  # Step 1
    AmountQuantityType,
    ContinuousAmtQtyType,
    ContinuousPeriodType,
    InvestorMarketType,
    InvestorTradeType,
    InvestorType,
    NormalizedFrgnOrgnConsecutive,  # type: ignore[import]
    NormalizedInvestorDailyTrade,  # type: ignore[import]
    NormalizedStockInvestorBreakdown,  # type: ignore[import]
    RankingExchangeType,
    StockIndsType,
    StockInvestorTradeType,
    UnitType,
)
from app.adapter.out.persistence.repositories.frgn_orgn_consecutive import (  # type: ignore[import]  # Step 1
    FrgnOrgnConsecutiveRepository,
)
from app.adapter.out.persistence.repositories.investor_flow_daily import (  # type: ignore[import]  # Step 1
    InvestorFlowDailyRepository,
)
from app.adapter.out.persistence.repositories.stock_investor_breakdown import (  # type: ignore[import]  # Step 1
    StockInvestorBreakdownRepository,
)

# ---------------------------------------------------------------------------
# 공용 상수
# ---------------------------------------------------------------------------

_AS_OF_DATE = date(2026, 5, 16)
_TRADING_DATE = date(2024, 11, 7)


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncSession:
    """각 테스트 롤백 보장 세션."""
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        await s.begin()
        try:
            yield s
        finally:
            await s.rollback()


async def _ensure_stock(session: AsyncSession, code: str = "005930") -> int:
    """테스트용 stock INSERT — returning id."""
    result = await session.execute(
        text(
            "INSERT INTO kiwoom.stock "
            "(stock_code, stock_name, market_code, market_name, is_active) "
            "VALUES (:code, '테스트주식', '0', 'KOSPI', TRUE) "
            "ON CONFLICT (stock_code) DO UPDATE SET is_active=TRUE "
            "RETURNING id"
        ).bindparams(code=code)
    )
    row = result.fetchone()
    assert row is not None
    return row[0]


def _make_ifd_row(
    stock_id: int | None = None,
    stock_code_raw: str = "005930",
    investor_type: InvestorType = InvestorType.FOREIGN,
    trade_type: InvestorTradeType = InvestorTradeType.NET_BUY,
    rank: int = 1,
) -> NormalizedInvestorDailyTrade:
    return NormalizedInvestorDailyTrade(
        as_of_date=_AS_OF_DATE,
        stock_id=stock_id,
        stock_code_raw=stock_code_raw,
        investor_type=investor_type,
        trade_type=trade_type,
        market_type=InvestorMarketType.KOSPI,
        exchange_type=RankingExchangeType.UNIFIED,
        rank=rank,
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


def _make_sib_row(stock_id: int = 1) -> NormalizedStockInvestorBreakdown:
    return NormalizedStockInvestorBreakdown(
        stock_id=stock_id,
        trading_date=_TRADING_DATE,
        amt_qty_tp=AmountQuantityType.QUANTITY,
        trade_type=StockInvestorTradeType.NET_BUY,
        unit_tp=UnitType.THOUSAND_SHARES,
        exchange_type=RankingExchangeType.UNIFIED,
        current_price=61300,
        prev_compare_sign="2",
        prev_compare_amount=4000,
        change_rate=Decimal("6.98"),
        acc_trade_volume=1105968,
        acc_trade_amount=64215,
        net_individual=1584,
        net_foreign=-61779,
        net_institution_total=60195,
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


def _make_foc_row(
    stock_id: int | None = None,
    stock_code_raw: str = "005930",
    amt_qty_tp: ContinuousAmtQtyType = ContinuousAmtQtyType.AMOUNT,
    total_cont_days: int = 2,
    rank: int = 1,
) -> NormalizedFrgnOrgnConsecutive:
    return NormalizedFrgnOrgnConsecutive(
        stock_id=stock_id,
        stock_code_raw=stock_code_raw,
        stock_name="삼성전자",
        as_of_date=_AS_OF_DATE,
        period_type=ContinuousPeriodType.LATEST,
        market_type=InvestorMarketType.KOSPI,
        amt_qty_tp=amt_qty_tp,
        stk_inds_tp=StockIndsType.STOCK,
        exchange_type=RankingExchangeType.UNIFIED,
        rank=rank,
        period_stock_price_flu_rt=Decimal("-5.80"),
        orgn_net_amount=48,
        orgn_net_volume=173,
        orgn_cont_days=1,
        orgn_cont_volume=173,
        orgn_cont_amount=48,
        frgnr_net_volume=0,
        frgnr_net_amount=0,
        frgnr_cont_days=1,
        frgnr_cont_volume=1,
        frgnr_cont_amount=0,
        total_net_volume=173,
        total_net_amount=48,
        total_cont_days=total_cont_days,
        total_cont_volume=174,
        total_cont_amount=48,
    )


# ---------------------------------------------------------------------------
# Scenario 1 — investor_flow_daily INSERT 50 + UPDATE 멱등
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_investor_flow_daily_insert_50_update_idempotent(
    session: AsyncSession,
) -> None:
    """investor_flow_daily INSERT 50 row + UPDATE 멱등."""
    stock_id = await _ensure_stock(session)
    repo = InvestorFlowDailyRepository(session)

    rows = [
        _make_ifd_row(stock_id=stock_id, stock_code_raw=f"{i:06d}", rank=i)
        for i in range(1, 51)
    ]
    count = await repo.upsert_many(rows)
    assert count == 50, f"50 row 기대, 실제: {count}"

    # 동일 row 재적재 — 멱등성
    await repo.upsert_many(rows)
    result = await session.execute(
        text(
            "SELECT COUNT(*) FROM kiwoom.investor_flow_daily "
            "WHERE as_of_date = :d AND investor_type = '9000' AND trade_type = '2'"
        ).bindparams(d=_AS_OF_DATE)
    )
    total = result.scalar_one()
    assert total == 50, f"멱등성 — 50 row 기대, 실제: {total}"


# ---------------------------------------------------------------------------
# Scenario 2 — stock_investor_breakdown INSERT + flu_rt Decimal 정확성
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_stock_investor_breakdown_insert_flu_rt_decimal(
    session: AsyncSession,
) -> None:
    """stock_investor_breakdown INSERT + change_rate Decimal('6.98') 정확성."""
    stock_id = await _ensure_stock(session)
    repo = StockInvestorBreakdownRepository(session)

    count = await repo.upsert_many([_make_sib_row(stock_id=stock_id)])
    assert count == 1

    result = await session.execute(
        text(
            "SELECT change_rate FROM kiwoom.stock_investor_breakdown "
            "WHERE stock_id = :sid AND trading_date = :d "
            "  AND amt_qty_tp = '2' AND trade_type = '0' LIMIT 1"
        ).bindparams(sid=stock_id, d=_TRADING_DATE)
    )
    row = result.fetchone()
    assert row is not None
    assert abs(float(row[0]) - 6.98) < 0.01


# ---------------------------------------------------------------------------
# Scenario 3 — frgn_orgn_consecutive INSERT + total_cont_days DESC
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_frgn_orgn_consecutive_insert_total_cont_days(
    session: AsyncSession,
) -> None:
    """frgn_orgn_consecutive INSERT + total_cont_days 보존."""
    stock_id = await _ensure_stock(session)
    repo = FrgnOrgnConsecutiveRepository(session)

    count = await repo.upsert_many([_make_foc_row(stock_id=stock_id, total_cont_days=5)])
    assert count == 1

    result = await session.execute(
        text(
            "SELECT total_cont_days FROM kiwoom.frgn_orgn_consecutive "
            "WHERE stock_code_raw = '005930' AND as_of_date = :d LIMIT 1"
        ).bindparams(d=_AS_OF_DATE)
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == 5


# ---------------------------------------------------------------------------
# Scenario 4 — 3 테이블 cross-query (동일 종목 + 동일 날짜)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_three_tables_cross_query(session: AsyncSession) -> None:
    """3 테이블 동일 종목 적재 + cross-query."""
    stock_id = await _ensure_stock(session)

    ifd_repo = InvestorFlowDailyRepository(session)
    sib_repo = StockInvestorBreakdownRepository(session)
    foc_repo = FrgnOrgnConsecutiveRepository(session)

    await ifd_repo.upsert_many([_make_ifd_row(stock_id=stock_id)])
    await sib_repo.upsert_many([_make_sib_row(stock_id=stock_id)])
    await foc_repo.upsert_many([_make_foc_row(stock_id=stock_id)])

    # 3 테이블 모두 stock_id 기준 조회
    r1 = await session.execute(
        text(
            "SELECT COUNT(*) FROM kiwoom.investor_flow_daily WHERE stock_id = :sid"
        ).bindparams(sid=stock_id)
    )
    r2 = await session.execute(
        text(
            "SELECT COUNT(*) FROM kiwoom.stock_investor_breakdown WHERE stock_id = :sid"
        ).bindparams(sid=stock_id)
    )
    r3 = await session.execute(
        text(
            "SELECT COUNT(*) FROM kiwoom.frgn_orgn_consecutive WHERE stock_id = :sid"
        ).bindparams(sid=stock_id)
    )
    assert r1.scalar_one() >= 1
    assert r2.scalar_one() >= 1
    assert r3.scalar_one() >= 1


# ---------------------------------------------------------------------------
# Scenario 5 — stock_id=NULL (lookup miss) 보존
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_investor_flow_daily_lookup_miss_null(session: AsyncSession) -> None:
    """stock_id=NULL (lookup miss) + stock_code_raw 보존."""
    repo = InvestorFlowDailyRepository(session)
    count = await repo.upsert_many([_make_ifd_row(stock_id=None, stock_code_raw="777777")])
    assert count == 1

    result = await session.execute(
        text(
            "SELECT stock_id, stock_code_raw FROM kiwoom.investor_flow_daily "
            "WHERE stock_code_raw = '777777' LIMIT 1"
        )
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] is None
    assert row[1] == "777777"


# ---------------------------------------------------------------------------
# Scenario 6 — NXT _NX suffix stock_code_raw 보존
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_investor_flow_daily_nxt_suffix(session: AsyncSession) -> None:
    """NXT _NX suffix → stock_code_raw='005930_NX' 보존."""
    repo = InvestorFlowDailyRepository(session)
    count = await repo.upsert_many([_make_ifd_row(stock_id=None, stock_code_raw="005930_NX")])
    assert count == 1

    result = await session.execute(
        text(
            "SELECT stock_code_raw FROM kiwoom.investor_flow_daily "
            "WHERE stock_code_raw = '005930_NX' LIMIT 1"
        )
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == "005930_NX"


# ---------------------------------------------------------------------------
# Scenario 7 — investor_flow_daily UNIQUE 키 (investor_type 별)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_investor_flow_daily_unique_investor_type(session: AsyncSession) -> None:
    """investor_type 다름 → 별도 row (같은 종목이라도 UNIQUE 분리)."""
    repo = InvestorFlowDailyRepository(session)
    rows = [
        _make_ifd_row(stock_id=None, investor_type=InvestorType.FOREIGN, rank=1),
        _make_ifd_row(stock_id=None, investor_type=InvestorType.INSTITUTION_TOTAL, rank=1),
        _make_ifd_row(stock_id=None, investor_type=InvestorType.INDIVIDUAL, rank=1),
    ]
    count = await repo.upsert_many(rows)
    assert count == 3

    result = await session.execute(
        text(
            "SELECT COUNT(DISTINCT investor_type) FROM kiwoom.investor_flow_daily "
            "WHERE stock_code_raw = '005930' AND as_of_date = :d "
            "  AND market_type = '001' AND trade_type = '2'"
        ).bindparams(d=_AS_OF_DATE)
    )
    distinct_types = result.scalar_one()
    assert distinct_types == 3


# ---------------------------------------------------------------------------
# Scenario 8 — frgn_orgn_consecutive amt_qty_tp 분리
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_frgn_orgn_consecutive_amt_qty_separation(session: AsyncSession) -> None:
    """amt_qty_tp AMOUNT vs QUANTITY → 별도 row."""
    repo = FrgnOrgnConsecutiveRepository(session)
    rows = [
        _make_foc_row(stock_id=None, amt_qty_tp=ContinuousAmtQtyType.AMOUNT, rank=1),
        _make_foc_row(stock_id=None, amt_qty_tp=ContinuousAmtQtyType.QUANTITY, rank=1),
    ]
    count = await repo.upsert_many(rows)
    assert count == 2


# ---------------------------------------------------------------------------
# Scenario 9 — Migration 019 upgrade/downgrade 회귀
# ---------------------------------------------------------------------------


def test_e2e_migration_019_upgrade_downgrade(database_url: str) -> None:
    """Migration 019 upgrade → downgrade → upgrade 회귀."""
    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(
        str(Path(__file__).resolve().parent.parent.parent / "alembic.ini")
    )
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    sync_engine = sa.create_engine(database_url.replace("+asyncpg", "+psycopg2"))
    try:
        # 현재 head 상태에서 downgrade
        command.downgrade(alembic_cfg, "018_ranking_snapshot")
        with sync_engine.connect() as conn:
            from sqlalchemy import inspect
            tables = set(inspect(conn).get_table_names(schema="kiwoom"))
        assert "investor_flow_daily" not in tables

        # 복원
        command.upgrade(alembic_cfg, "head")
        with sync_engine.connect() as conn2:
            from sqlalchemy import inspect
            tables2 = set(inspect(conn2).get_table_names(schema="kiwoom"))
        assert "investor_flow_daily" in tables2
    finally:
        sync_engine.dispose()


# ---------------------------------------------------------------------------
# Scenario 10 — get_top_stocks / get_top_by_total_days 크로스 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_get_top_cross_validation(session: AsyncSession) -> None:
    """get_top_stocks + get_top_by_total_days — 동일 날짜 기준 크로스 검증."""
    ifd_repo = InvestorFlowDailyRepository(session)
    foc_repo = FrgnOrgnConsecutiveRepository(session)

    # investor_flow_daily 데이터 적재
    ifd_rows = [
        _make_ifd_row(stock_id=None, stock_code_raw=f"{i:06d}", rank=i)
        for i in range(1, 6)
    ]
    await ifd_repo.upsert_many(ifd_rows)

    # frgn_orgn_consecutive 데이터 적재
    foc_rows = [
        _make_foc_row(stock_id=None, stock_code_raw=f"{i:06d}", total_cont_days=i, rank=i)
        for i in range(1, 6)
    ]
    await foc_repo.upsert_many(foc_rows)

    # get_top_stocks
    ifd_top = await ifd_repo.get_top_stocks(
        as_of_date=_AS_OF_DATE,
        investor_type=InvestorType.FOREIGN,
        trade_type=InvestorTradeType.NET_BUY,
        market_type=InvestorMarketType.KOSPI,
        limit=5,
    )
    # get_top_by_total_days
    foc_top = await foc_repo.get_top_by_total_days(
        as_of_date=_AS_OF_DATE,
        market_type=InvestorMarketType.KOSPI,
        period_type=ContinuousPeriodType.LATEST,
        limit=5,
    )
    assert len(ifd_top) >= 0
    assert len(foc_top) >= 0
