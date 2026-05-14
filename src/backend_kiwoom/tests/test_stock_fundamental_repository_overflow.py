"""Phase F-1 — stock_fundamental NUMERIC overflow 회귀 TDD (Step 0, red).

Migration 017 적용 후 trade_compare_rate (12,4) / low_250d_pre_rate (10,4) 로 확대 —
NUMERIC(8,4) 한계(9999.9999) 초과 값 적재 + 회수 검증.

계획서 § 4 결정 #1: trade_compare_rate (8,4) → (12,4)
계획서 § 4 결정 #2: low_250d_pre_rate (8,4) → (10,4)

현재 상태 (Migration 016 head):
- trade_compare_rate: Numeric(8,4) → max 9999.9999 → 10000.0001 적재 시 DB 오류
- low_250d_pre_rate: Numeric(8,4) → max 9999.9999 → 99999.5 적재 시 DB 오류

본 테스트는 Migration 017 적용 전 실패 (DB NumericValueOutOfRangeError = red).
Step 1 에서 Migration 017 + ORM 변경 후 green 전환 대상.

참고: 5-13 18:00 cron 실측 max — trade_compare_rate=8950 (Numeric(8,4) 89.5% 사용)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.adapter.out.kiwoom.stkinfo import NormalizedFundamental
from app.adapter.out.persistence.repositories.stock_fundamental import (
    StockFundamentalRepository,
)

# ---------------------------------------------------------------------------
# Fixtures — test_stock_fundamental_repository.py 패턴 차용
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """트랜잭션 + rollback — 각 테스트 격리."""
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        await s.begin()
        try:
            yield s
        finally:
            await s.rollback()


async def _create_stock(session: AsyncSession, stock_code: str = "468760") -> int:
    """테스트 fixture — stock 한 건 만들고 id 반환."""
    result = await session.execute(
        text(
            "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code) "
            "VALUES (:code, :name, '0') RETURNING id"
        ).bindparams(code=stock_code, name=f"test-{stock_code}")
    )
    return int(result.scalar_one())


def _normalized_with_overflow_values(
    *,
    stock_code: str = "468760",
    asof: date = date(2026, 5, 14),
    trade_compare_rate: Decimal | None = None,
    low_250d_pre_rate: Decimal | None = None,
) -> NormalizedFundamental:
    """overflow 값이 포함된 NormalizedFundamental fixture."""
    return NormalizedFundamental(
        stock_code=stock_code,
        exchange="KRX",
        asof_date=asof,
        stock_name=f"test-{stock_code}",
        settlement_month="12",
        face_value=500,
        face_value_unit="원",
        capital_won=100,
        listed_shares=1000000,
        market_cap=50000,
        market_cap_weight=None,
        foreign_holding_rate=None,
        replacement_price=None,
        credit_rate=None,
        circulating_shares=None,
        circulating_rate=None,
        per_ratio=None,
        eps_won=None,
        roe_pct=None,
        pbr_ratio=None,
        ev_ratio=None,
        bps_won=None,
        revenue_amount=None,
        operating_profit=None,
        net_profit=None,
        high_250d=None,
        high_250d_date=None,
        high_250d_pre_rate=None,
        low_250d=None,
        low_250d_date=None,
        low_250d_pre_rate=low_250d_pre_rate,
        year_high=None,
        year_low=None,
        current_price=10000,
        prev_compare_sign=None,
        prev_compare_amount=None,
        change_rate=None,
        trade_volume=None,
        trade_compare_rate=trade_compare_rate,
        open_price=None,
        high_price=None,
        low_price=None,
        upper_limit_price=None,
        lower_limit_price=None,
        base_price=None,
        expected_match_price=None,
        expected_match_volume=None,
    )


# ---------------------------------------------------------------------------
# Migration 017 후 NUMERIC(12,4) 수용 — trade_compare_rate overflow 회귀
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trade_compare_rate_exceeds_8_4_limit_persisted_after_migration_017(
    session: AsyncSession,
) -> None:
    """trade_compare_rate=10000.0001 적재 + 회수 — Migration 017 (12,4) 후 정상.

    현재 상태 (016 head): Numeric(8,4) — 9999.9999 초과 → DB NumericValueOutOfRangeError.
    5-13 실측 max=8950 이지만 종목 468760 은 이미 한계 근접.
    Migration 017 upgrade 후: Numeric(12,4) → max 99,999,999.9999 — 정상 적재.

    RED: Migration 017 미적용 상태에서 DB 오류 발생 → 본 테스트 fail.
    """
    stock_id = await _create_stock(session, "468760")

    # NUMERIC(8,4) 한계 초과값 (실측 8950 ~ 10000 범위 시뮬)
    overflow_rate = Decimal("10000.0001")

    repo = StockFundamentalRepository(session)
    f = await repo.upsert_one(
        _normalized_with_overflow_values(
            stock_code="468760",
            trade_compare_rate=overflow_rate,
        ),
        stock_id=stock_id,
    )

    # 회수 검증 — Decimal 라운드트립
    assert f.trade_compare_rate is not None, "trade_compare_rate None 은 기대 밖"
    assert f.trade_compare_rate == overflow_rate, (
        f"trade_compare_rate 라운드트립 실패: 기대={overflow_rate}, 실제={f.trade_compare_rate}"
    )


@pytest.mark.asyncio
async def test_trade_compare_rate_large_value_persisted_after_migration_017(
    session: AsyncSession,
) -> None:
    """trade_compare_rate=99999.9999 — Migration 017 (12,4) 후 최대 범위 테스트.

    실측 max=8950 의 약 11배. 극단 테마주 급등 시뮬.
    """
    stock_id = await _create_stock(session, "474930")

    large_rate = Decimal("99999.9999")
    repo = StockFundamentalRepository(session)
    f = await repo.upsert_one(
        _normalized_with_overflow_values(
            stock_code="474930",
            trade_compare_rate=large_rate,
        ),
        stock_id=stock_id,
    )

    assert f.trade_compare_rate == large_rate, (
        f"trade_compare_rate={large_rate} 라운드트립 실패: {f.trade_compare_rate}"
    )


# ---------------------------------------------------------------------------
# Migration 017 후 NUMERIC(10,4) 수용 — low_250d_pre_rate overflow 회귀
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_low_250d_pre_rate_exceeds_8_4_limit_persisted_after_migration_017(
    session: AsyncSession,
) -> None:
    """low_250d_pre_rate=99999.5 적재 + 회수 — Migration 017 (10,4) 후 정상.

    현재 상태 (016 head): Numeric(8,4) — 9999.9999 초과 → DB 오류.
    5-13 실측 max=5745.71 — NUMERIC(8,4) 57.5% 사용 (안전권 끝).
    Migration 017 upgrade 후: Numeric(10,4) → max 999,999.9999 — 정상 적재.

    RED: Migration 017 미적용 상태 → DB 오류 발생 → fail.
    """
    stock_id = await _create_stock(session, "474930")

    overflow_rate = Decimal("99999.5000")

    repo = StockFundamentalRepository(session)
    f = await repo.upsert_one(
        _normalized_with_overflow_values(
            stock_code="474930",
            low_250d_pre_rate=overflow_rate,
        ),
        stock_id=stock_id,
    )

    assert f.low_250d_pre_rate is not None, "low_250d_pre_rate None 은 기대 밖"
    assert f.low_250d_pre_rate == overflow_rate, (
        f"low_250d_pre_rate 라운드트립 실패: 기대={overflow_rate}, 실제={f.low_250d_pre_rate}"
    )


@pytest.mark.asyncio
async def test_low_250d_pre_rate_near_limit_value_roundtrips(
    session: AsyncSession,
) -> None:
    """low_250d_pre_rate=5745.7100 — 5-13 cron 실측 max 회귀.

    Migration 017 이전에도 적재 가능한 값 (NUMERIC(8,4) 57.5%). 회귀 보장.
    """
    stock_id = await _create_stock(session, "000660")

    observed_max = Decimal("5745.7100")
    repo = StockFundamentalRepository(session)
    f = await repo.upsert_one(
        _normalized_with_overflow_values(
            stock_code="000660",
            low_250d_pre_rate=observed_max,
        ),
        stock_id=stock_id,
    )

    assert f.low_250d_pre_rate == observed_max, (
        f"실측 max 값 라운드트립 실패: {f.low_250d_pre_rate}"
    )


# ---------------------------------------------------------------------------
# 기존 정상 범위 값 회귀 — 확장 후 기존 데이터 영향 없음
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_normal_range_trade_compare_rate_still_works_after_migration_017(
    session: AsyncSession,
) -> None:
    """trade_compare_rate=5.4321 — 기존 정상 범위 회귀 (Migration 017 후 기존 데이터 영향 없음)."""
    stock_id = await _create_stock(session, "035720")

    normal_rate = Decimal("5.4321")
    repo = StockFundamentalRepository(session)
    f = await repo.upsert_one(
        _normalized_with_overflow_values(
            stock_code="035720",
            trade_compare_rate=normal_rate,
        ),
        stock_id=stock_id,
    )

    assert f.trade_compare_rate == normal_rate


@pytest.mark.asyncio
async def test_normal_range_low_250d_pre_rate_still_works_after_migration_017(
    session: AsyncSession,
) -> None:
    """low_250d_pre_rate=48.0000 — 기존 정상 범위 회귀."""
    stock_id = await _create_stock(session, "005930")

    normal_rate = Decimal("48.0000")
    repo = StockFundamentalRepository(session)
    f = await repo.upsert_one(
        _normalized_with_overflow_values(
            stock_code="005930",
            low_250d_pre_rate=normal_rate,
        ),
        stock_id=stock_id,
    )

    assert f.low_250d_pre_rate == normal_rate
