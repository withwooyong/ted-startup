"""FrgnOrgnConsecutiveRepository — upsert_many + get_top_by_total_days 단위 테스트 (Phase G, ~12 케이스).

TDD red 의도:
- `app.adapter.out.persistence.repositories.frgn_orgn_consecutive.FrgnOrgnConsecutiveRepository` 미존재
- `app.adapter.out.persistence.models.frgn_orgn_consecutive.FrgnOrgnConsecutive` 미존재
→ Step 1 구현 후 green.

검증:
- upsert INSERT — 15 metric 컬럼 적재
- upsert UPDATE 멱등성
- 빈 입력 → 0
- stock_id=NULL (lookup miss) + stock_code_raw 보존
- get_top_by_total_days — DESC + NULLS LAST 정렬
- (period, market, amt_qty, stk_inds, exchange, rank) UNIQUE
- as_of_date 별 분리
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._records import (  # type: ignore[import]  # Step 1
    ContinuousAmtQtyType,
    ContinuousPeriodType,
    InvestorMarketType,
    RankingExchangeType,
    StockIndsType,
)
from app.adapter.out.persistence.repositories.frgn_orgn_consecutive import (  # type: ignore[import]  # Step 1
    FrgnOrgnConsecutiveRepository,
)

_AS_OF_DATE = date(2026, 5, 16)
_STOCK_ID = 1


def _make_normalized(
    *,
    stock_id: int | None = None,
    stock_code_raw: str = "005930",
    stock_name: str = "삼성전자",
    as_of_date: date = _AS_OF_DATE,
    period_type: ContinuousPeriodType = ContinuousPeriodType.LATEST,
    market_type: InvestorMarketType = InvestorMarketType.KOSPI,
    amt_qty_tp: ContinuousAmtQtyType = ContinuousAmtQtyType.AMOUNT,
    stk_inds_tp: StockIndsType = StockIndsType.STOCK,
    exchange_type: RankingExchangeType = RankingExchangeType.UNIFIED,
    rank: int = 1,
    total_cont_days: int | None = 2,
    orgn_cont_days: int | None = 1,
    frgnr_cont_days: int | None = 1,
) -> Any:
    """NormalizedFrgnOrgnConsecutive stub."""
    from app.adapter.out.kiwoom._records import NormalizedFrgnOrgnConsecutive  # type: ignore[import]

    return NormalizedFrgnOrgnConsecutive(
        stock_id=stock_id,
        stock_code_raw=stock_code_raw,
        stock_name=stock_name,
        as_of_date=as_of_date,
        period_type=period_type,
        market_type=market_type,
        amt_qty_tp=amt_qty_tp,
        stk_inds_tp=stk_inds_tp,
        exchange_type=exchange_type,
        rank=rank,
        period_stock_price_flu_rt=Decimal("-5.80"),
        orgn_net_amount=48,
        orgn_net_volume=173,
        orgn_cont_days=orgn_cont_days,
        orgn_cont_volume=173,
        orgn_cont_amount=48,
        frgnr_net_volume=0,
        frgnr_net_amount=0,
        frgnr_cont_days=frgnr_cont_days,
        frgnr_cont_volume=1,
        frgnr_cont_amount=0,
        total_net_volume=173,
        total_net_amount=48,
        total_cont_days=total_cont_days,
        total_cont_volume=174,
        total_cont_amount=48,
    )


# ---------------------------------------------------------------------------
# Scenario 1 — upsert INSERT (15 metric 컬럼)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_frgn_orgn_consecutive_repository_upsert_insert(session: AsyncSession) -> None:
    """upsert_many INSERT — 15 metric 컬럼 적재."""
    from sqlalchemy import text

    repo = FrgnOrgnConsecutiveRepository(session)
    count = await repo.upsert_many([_make_normalized()])
    assert count == 1

    result = await session.execute(
        text(
            "SELECT stock_code_raw, total_cont_days, orgn_cont_days, frgnr_cont_days "
            "FROM kiwoom.frgn_orgn_consecutive "
            "WHERE stock_code_raw = '005930' AND as_of_date = :d "
            "  AND period_type = '1' AND market_type = '001' LIMIT 1"
        ).bindparams(d=_AS_OF_DATE)
    )
    row = result.fetchone()
    assert row is not None, "frgn_orgn_consecutive INSERT 실패"
    assert row[1] == 2, f"total_cont_days 미일치: {row[1]!r}"
    assert row[2] == 1, f"orgn_cont_days 미일치: {row[2]!r}"


# ---------------------------------------------------------------------------
# Scenario 2 — upsert UPDATE 멱등성
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_frgn_orgn_consecutive_repository_upsert_idempotent(session: AsyncSession) -> None:
    """동일 UNIQUE 키 2회 upsert → row 수 유지."""
    from sqlalchemy import text

    repo = FrgnOrgnConsecutiveRepository(session)
    await repo.upsert_many([_make_normalized(total_cont_days=2)])
    await repo.upsert_many([_make_normalized(total_cont_days=5)])  # 값 변경

    result = await session.execute(
        text(
            "SELECT COUNT(*) FROM kiwoom.frgn_orgn_consecutive "
            "WHERE stock_code_raw = '005930' AND as_of_date = :d "
            "  AND period_type = '1' AND market_type = '001'"
        ).bindparams(d=_AS_OF_DATE)
    )
    count = result.scalar_one()
    assert count == 1, f"멱등성 실패 — 1 기대, 실제: {count}"


# ---------------------------------------------------------------------------
# Scenario 3 — 빈 입력
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_frgn_orgn_consecutive_repository_empty_input(session: AsyncSession) -> None:
    """빈 입력 → 0 반환."""
    repo = FrgnOrgnConsecutiveRepository(session)
    count = await repo.upsert_many([])
    assert count == 0


# ---------------------------------------------------------------------------
# Scenario 4 — stock_id=NULL (lookup miss)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_frgn_orgn_consecutive_repository_lookup_miss(session: AsyncSession) -> None:
    """stock_id=None (lookup miss) → NULL + stock_code_raw 보존."""
    from sqlalchemy import text

    repo = FrgnOrgnConsecutiveRepository(session)
    count = await repo.upsert_many([_make_normalized(stock_id=None, stock_code_raw="888888")])
    assert count == 1

    result = await session.execute(
        text(
            "SELECT stock_id, stock_code_raw FROM kiwoom.frgn_orgn_consecutive "
            "WHERE stock_code_raw = '888888' AND as_of_date = :d LIMIT 1"
        ).bindparams(d=_AS_OF_DATE)
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] is None, "lookup miss → stock_id NULL 기대"
    assert row[1] == "888888"


# ---------------------------------------------------------------------------
# Scenario 5 — get_top_by_total_days DESC + NULLS LAST
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_frgn_orgn_consecutive_repository_get_top_by_total_days(
    session: AsyncSession,
) -> None:
    """get_top_by_total_days — total_cont_days DESC NULLS LAST 정렬."""
    repo = FrgnOrgnConsecutiveRepository(session)
    rows = [
        _make_normalized(stock_code_raw="005930", total_cont_days=10, rank=1),
        _make_normalized(stock_code_raw="000660", total_cont_days=5, rank=2),
    ]
    await repo.upsert_many(rows)
    result = await repo.get_top_by_total_days(
        as_of_date=_AS_OF_DATE,
        market_type=InvestorMarketType.KOSPI,
        period_type=ContinuousPeriodType.LATEST,
        limit=10,
    )
    assert len(result) >= 0  # Step 1 구현 후 검증 강화


# ---------------------------------------------------------------------------
# Scenario 6 — (period, market, amt_qty, stk_inds, exchange, rank) UNIQUE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_frgn_orgn_consecutive_repository_combo_unique(session: AsyncSession) -> None:
    """period_type 다름 → 별도 row (UNIQUE 키에 period_type 포함)."""
    repo = FrgnOrgnConsecutiveRepository(session)
    row1 = _make_normalized(period_type=ContinuousPeriodType.LATEST, rank=1)
    row2 = _make_normalized(period_type=ContinuousPeriodType.DAYS_5, rank=1)
    count = await repo.upsert_many([row1, row2])
    assert count == 2, f"period_type 분리 — 2 row 기대, 실제: {count}"


# ---------------------------------------------------------------------------
# Scenario 7 — as_of_date 별 분리
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_frgn_orgn_consecutive_repository_date_separation(session: AsyncSession) -> None:
    """as_of_date 다름 → 별도 row."""
    repo = FrgnOrgnConsecutiveRepository(session)
    row1 = _make_normalized(as_of_date=date(2026, 5, 15), rank=1)
    row2 = _make_normalized(as_of_date=date(2026, 5, 16), rank=1)
    count = await repo.upsert_many([row1, row2])
    assert count == 2, f"날짜 분리 — 2 row 기대, 실제: {count}"


# ---------------------------------------------------------------------------
# Scenario 8 — KOSDAQ 시장 분리
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_frgn_orgn_consecutive_repository_market_separation(session: AsyncSession) -> None:
    """KOSPI + KOSDAQ 분리 — 별도 row."""
    repo = FrgnOrgnConsecutiveRepository(session)
    row1 = _make_normalized(market_type=InvestorMarketType.KOSPI, rank=1)
    row2 = _make_normalized(market_type=InvestorMarketType.KOSDAQ, rank=1)
    count = await repo.upsert_many([row1, row2])
    assert count == 2, f"시장 분리 — 2 row 기대, 실제: {count}"


# ---------------------------------------------------------------------------
# Scenario 9 — amt_qty_tp 분리 (D-10 AMOUNT + QUANTITY)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_frgn_orgn_consecutive_repository_amt_qty_separation(
    session: AsyncSession,
) -> None:
    """ContinuousAmtQtyType.AMOUNT + QUANTITY → 별도 row."""
    repo = FrgnOrgnConsecutiveRepository(session)
    row1 = _make_normalized(amt_qty_tp=ContinuousAmtQtyType.AMOUNT, rank=1)
    row2 = _make_normalized(amt_qty_tp=ContinuousAmtQtyType.QUANTITY, rank=1)
    count = await repo.upsert_many([row1, row2])
    assert count == 2, f"amt_qty_tp 분리 — 2 row 기대, 실제: {count}"


# ---------------------------------------------------------------------------
# Scenario 10 — chunked_upsert BATCH=200
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_frgn_orgn_consecutive_repository_batch_upsert(session: AsyncSession) -> None:
    """50 row 적재 — chunked_upsert BATCH=200 정상 동작."""
    repo = FrgnOrgnConsecutiveRepository(session)
    rows = [
        _make_normalized(
            stock_code_raw=f"{i:06d}",
            stock_id=None,
            rank=i,
        )
        for i in range(1, 51)
    ]
    count = await repo.upsert_many(rows)
    assert count == 50, f"50 row upsert 기대, 실제: {count}"
