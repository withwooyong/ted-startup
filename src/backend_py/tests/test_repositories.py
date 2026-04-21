"""Repository CRUD 통합 테스트 — 7개 테이블 최소 1 시나리오씩."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.models import (
    BacktestResult,
    NotificationPreference,
    Signal,
    SignalGrade,
    SignalType,
    Stock,
)
from app.adapter.out.persistence.repositories import (
    BacktestResultRepository,
    LendingBalanceRepository,
    NotificationPreferenceRepository,
    ShortSellingRepository,
    SignalRepository,
    StockPriceRepository,
    StockRepository,
)


@pytest.mark.asyncio
async def test_stock_add_and_find_by_code(session: AsyncSession) -> None:
    repo = StockRepository(session)
    created = await repo.add(Stock(stock_code="005930", stock_name="삼성전자", market_type="KOSPI"))
    assert created.id is not None

    fetched = await repo.find_by_code("005930")
    assert fetched is not None
    assert fetched.stock_name == "삼성전자"


@pytest.mark.asyncio
async def test_stock_upsert_preserves_name_when_new_is_empty(session: AsyncSession) -> None:
    """α 배치 경로: pykrx 가 종목명을 반환하지 않아 빈 문자열이 들어와도
    기존 row 의 이름은 보존되어야 한다. β 시드 회귀 방지."""
    repo = StockRepository(session)
    # β 가 시드한 상태
    await repo.add(Stock(stock_code="005930", stock_name="삼성전자", market_type="KOSPI"))

    # α 재실행 — 빈 stock_name 으로 KOSDAQ 재분류 시도(이 경우 삼성은 KOSPI 유지가 정상)
    await repo.upsert_by_code("005930", "", "KOSPI")

    fetched = await repo.find_by_code("005930")
    assert fetched is not None
    assert fetched.stock_name == "삼성전자"  # 보존됨


@pytest.mark.asyncio
async def test_stock_upsert_updates_name_when_provided(session: AsyncSession) -> None:
    """비어있지 않은 이름은 정상적으로 업데이트."""
    repo = StockRepository(session)
    await repo.add(Stock(stock_code="005930", stock_name="(구)삼성전자", market_type="KOSPI"))

    await repo.upsert_by_code("005930", "삼성전자", "KOSPI")

    fetched = await repo.find_by_code("005930")
    assert fetched is not None
    assert fetched.stock_name == "삼성전자"


@pytest.mark.asyncio
async def test_stock_price_upsert_conflict_updates(session: AsyncSession) -> None:
    stock_repo = StockRepository(session)
    stock = await stock_repo.add(Stock(stock_code="000660", stock_name="SK하이닉스", market_type="KOSPI"))

    repo = StockPriceRepository(session)
    n1 = await repo.upsert_many([{"stock_id": stock.id, "trading_date": date(2026, 4, 17), "close_price": 245000}])
    assert n1 == 1

    # 동일 (stock_id, trading_date) → 업데이트
    n2 = await repo.upsert_many([{"stock_id": stock.id, "trading_date": date(2026, 4, 17), "close_price": 250000}])
    assert n2 == 1

    fetched = await repo.find_by_stock_and_date(stock.id, date(2026, 4, 17))
    assert fetched is not None
    assert fetched.close_price == 250000


@pytest.mark.asyncio
async def test_short_selling_upsert(session: AsyncSession) -> None:
    stock_repo = StockRepository(session)
    stock = await stock_repo.add(Stock(stock_code="035720", stock_name="카카오", market_type="KOSPI"))

    repo = ShortSellingRepository(session)
    n = await repo.upsert_many(
        [
            {
                "stock_id": stock.id,
                "trading_date": date(2026, 4, 17),
                "short_volume": 10000,
                "short_amount": 500000000,
                "short_ratio": "5.5",
            }
        ]
    )
    assert n == 1


@pytest.mark.asyncio
async def test_lending_balance_upsert(session: AsyncSession) -> None:
    stock_repo = StockRepository(session)
    stock = await stock_repo.add(Stock(stock_code="373220", stock_name="LG에너지솔루션", market_type="KOSPI"))

    repo = LendingBalanceRepository(session)
    n = await repo.upsert_many(
        [
            {
                "stock_id": stock.id,
                "trading_date": date(2026, 4, 17),
                "balance_quantity": 1_000_000,
                "balance_amount": 100_000_000_000,
                "change_rate": "1.25",
                "change_quantity": 50_000,
                "consecutive_decrease_days": 0,
            }
        ]
    )
    assert n == 1


@pytest.mark.asyncio
async def test_signal_add_and_list_by_date(session: AsyncSession) -> None:
    stock_repo = StockRepository(session)
    stock = await stock_repo.add(Stock(stock_code="207940", stock_name="삼성바이오로직스", market_type="KOSPI"))

    repo = SignalRepository(session)
    created = await repo.add(
        Signal(
            stock_id=stock.id,
            signal_date=date(2026, 4, 17),
            signal_type=SignalType.SHORT_SQUEEZE.value,
            score=85,
            grade=SignalGrade.from_score(85).value,
            detail={"reason": "short_ratio_spike", "prev_avg": 3.2, "now": 12.5},
        )
    )
    assert created.id is not None

    listed = await repo.list_by_date(date(2026, 4, 17))
    assert len(listed) == 1
    assert listed[0].detail is not None
    assert listed[0].detail["reason"] == "short_ratio_spike"


@pytest.mark.asyncio
async def test_backtest_result_add_and_list(session: AsyncSession) -> None:
    repo = BacktestResultRepository(session)
    await repo.add(
        BacktestResult(
            signal_type=SignalType.RAPID_DECLINE.value,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 3, 31),
            total_signals=120,
            hit_count_5d=60,
            hit_rate_5d="0.5",
            avg_return_5d="1.23",
        )
    )
    found = await repo.list_by_signal_type(SignalType.RAPID_DECLINE.value)
    assert len(found) == 1
    assert found[0].total_signals == 120


@pytest.mark.asyncio
async def test_notification_preference_get_or_create_is_idempotent(session: AsyncSession) -> None:
    repo = NotificationPreferenceRepository(session)
    p1 = await repo.get_or_create()
    p2 = await repo.get_or_create()
    assert p1.id == NotificationPreference.SINGLETON_ID == p2.id
    # V2 migration 의 기본 insert 또는 get_or_create 신규 생성 모두 기본값으로 수렴
    assert p1.min_score == NotificationPreference.DEFAULT_MIN_SCORE
    assert set(p1.signal_types) == set(NotificationPreference.DEFAULT_SIGNAL_TYPES)
