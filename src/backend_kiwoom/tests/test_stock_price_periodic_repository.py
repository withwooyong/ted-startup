"""StockPricePeriodicRepository — 주봉/월봉 KRX/NXT upsert + 조회 (C-3α).

설계: phase-c-3-weekly-monthly-ohlcv.md § 3.1 + endpoint-07-ka10082.md § 6.2.

ka10081 의 StockPriceRepository 와 분리된 이유:
- 일봉은 호출 빈도 + row 수가 압도적 → 별도 hot path
- 주/월봉은 통합 인터페이스 (period dispatch)

검증:
- _MODEL_BY_PERIOD_AND_EXCHANGE 4 키 매핑 (WEEKLY/MONTHLY × KRX/NXT)
- _model dispatch — period+exchange 분기
- YEARLY (미구현) 호출 시 ValueError
- SOR exchange 호출 시 ValueError (Phase D 결정)
- upsert_many insert / ON CONFLICT DO UPDATE
- trading_date == date.min 자동 skip
- 빈 rows → 0 반환
- find_range start > end ValueError
- find_range period+exchange 분기
- NormalizedDailyOhlcv 재사용 (period 정보는 Repository 가 분기)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom.chart import NormalizedDailyOhlcv
from app.adapter.out.persistence.models.stock_price_periodic import (
    StockPriceMonthlyKrx,
    StockPriceMonthlyNxt,
    StockPriceWeeklyKrx,
    StockPriceWeeklyNxt,
)
from app.adapter.out.persistence.repositories.stock_price_periodic import (
    StockPricePeriodicRepository,
)
from app.application.constants import ExchangeType, Period


async def _insert_test_stock(session: AsyncSession, code: str = "TST300") -> int:
    """테스트용 stock 1행 INSERT 후 id 반환."""
    await session.execute(
        text(
            "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code) VALUES (:code, 'periodic-test', '0')"
        ).bindparams(code=code)
    )
    result = await session.execute(text("SELECT id FROM kiwoom.stock WHERE stock_code = :code").bindparams(code=code))
    return int(result.scalar_one())


def _make_normalized(stock_id: int, trading_date: date, exchange: ExchangeType) -> NormalizedDailyOhlcv:
    return NormalizedDailyOhlcv(
        stock_id=stock_id,
        trading_date=trading_date,
        exchange=exchange,
        adjusted=True,
        open_price=68400,
        high_price=70400,
        low_price=67500,
        close_price=69500,
        trade_volume=56700518,
        trade_amount=3922030535087,
        prev_compare_amount=-200,
        prev_compare_sign="5",
        turnover_rate=Decimal("0.95"),
    )


# ---------- _MODEL_BY_PERIOD_AND_EXCHANGE 매핑 ----------


def test_repository_has_four_model_mappings() -> None:
    """4 매핑 (WEEKLY × KRX/NXT + MONTHLY × KRX/NXT). YEARLY 미구현."""
    mappings = StockPricePeriodicRepository._MODEL_BY_PERIOD_AND_EXCHANGE
    assert mappings[(Period.WEEKLY, ExchangeType.KRX)] is StockPriceWeeklyKrx
    assert mappings[(Period.WEEKLY, ExchangeType.NXT)] is StockPriceWeeklyNxt
    assert mappings[(Period.MONTHLY, ExchangeType.KRX)] is StockPriceMonthlyKrx
    assert mappings[(Period.MONTHLY, ExchangeType.NXT)] is StockPriceMonthlyNxt


def test_repository_yearly_not_in_mappings() -> None:
    """YEARLY 매핑 부재 — Migration 미구현 (P2 chunk 후 추가)."""
    mappings = StockPricePeriodicRepository._MODEL_BY_PERIOD_AND_EXCHANGE
    assert (Period.YEARLY, ExchangeType.KRX) not in mappings
    assert (Period.YEARLY, ExchangeType.NXT) not in mappings


# ---------- 통합 테스트 (DB) ----------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("period", "exchange"),
    [
        (Period.WEEKLY, ExchangeType.KRX),
        (Period.WEEKLY, ExchangeType.NXT),
        (Period.MONTHLY, ExchangeType.KRX),
        (Period.MONTHLY, ExchangeType.NXT),
    ],
)
async def test_upsert_many_inserts_rows(session: AsyncSession, period: Period, exchange: ExchangeType) -> None:
    sid = await _insert_test_stock(session, f"TST3{period.value[:2].upper()}{exchange.value[:1]}")
    repo = StockPricePeriodicRepository(session)

    rows = [
        _make_normalized(sid, date(2025, 9, 1), exchange),
        _make_normalized(sid, date(2025, 8, 25), exchange),
    ]

    affected = await repo.upsert_many(rows, period=period, exchange=exchange)
    assert affected == 2

    # 매핑 모델로 직접 조회
    model = StockPricePeriodicRepository._MODEL_BY_PERIOD_AND_EXCHANGE[(period, exchange)]
    table = model.__tablename__
    result = await session.execute(
        text(f"SELECT COUNT(*) FROM kiwoom.{table} WHERE stock_id = :sid").bindparams(sid=sid)
    )
    assert result.scalar_one() == 2


@pytest.mark.asyncio
async def test_upsert_many_on_conflict_updates(session: AsyncSession) -> None:
    """ON CONFLICT (stock_id, trading_date, adjusted) DO UPDATE — 같은 키 두 번째 호출."""
    sid = await _insert_test_stock(session, "TST301")
    repo = StockPricePeriodicRepository(session)

    row1 = _make_normalized(sid, date(2025, 9, 1), ExchangeType.KRX)
    await repo.upsert_many([row1], period=Period.WEEKLY, exchange=ExchangeType.KRX)

    row2 = NormalizedDailyOhlcv(
        stock_id=sid,
        trading_date=date(2025, 9, 1),
        exchange=ExchangeType.KRX,
        adjusted=True,
        open_price=99999,  # 변경 값
        high_price=99999,
        low_price=99999,
        close_price=99999,
        trade_volume=1,
        trade_amount=1,
        prev_compare_amount=1,
        prev_compare_sign="2",
        turnover_rate=Decimal("0.01"),
    )
    affected = await repo.upsert_many([row2], period=Period.WEEKLY, exchange=ExchangeType.KRX)
    assert affected == 1

    # 갱신 확인
    result = await session.execute(
        text(
            "SELECT close_price FROM kiwoom.stock_price_weekly_krx WHERE stock_id = :sid AND trading_date = :td"
        ).bindparams(sid=sid, td=date(2025, 9, 1))
    )
    assert result.scalar_one() == 99999

    # 1행 유지 (insert 가 아닌 update)
    result = await session.execute(
        text("SELECT COUNT(*) FROM kiwoom.stock_price_weekly_krx WHERE stock_id = :sid").bindparams(sid=sid)
    )
    assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_upsert_many_skips_date_min_rows(session: AsyncSession) -> None:
    """trading_date == date.min 빈 응답 row 자동 skip."""
    sid = await _insert_test_stock(session, "TST302")
    repo = StockPricePeriodicRepository(session)

    rows = [
        _make_normalized(sid, date.min, ExchangeType.KRX),  # skip 대상
        _make_normalized(sid, date(2025, 9, 1), ExchangeType.KRX),
    ]

    affected = await repo.upsert_many(rows, period=Period.WEEKLY, exchange=ExchangeType.KRX)
    assert affected == 1


@pytest.mark.asyncio
async def test_upsert_many_empty_rows_returns_zero(session: AsyncSession) -> None:
    repo = StockPricePeriodicRepository(session)
    affected = await repo.upsert_many([], period=Period.WEEKLY, exchange=ExchangeType.KRX)
    assert affected == 0


@pytest.mark.asyncio
async def test_upsert_many_all_date_min_rows_returns_zero(session: AsyncSession) -> None:
    sid = await _insert_test_stock(session, "TST303")
    repo = StockPricePeriodicRepository(session)
    rows = [_make_normalized(sid, date.min, ExchangeType.KRX)]
    affected = await repo.upsert_many(rows, period=Period.WEEKLY, exchange=ExchangeType.KRX)
    assert affected == 0


@pytest.mark.asyncio
async def test_upsert_many_yearly_raises(session: AsyncSession) -> None:
    """YEARLY 미구현 → ValueError (H-3 — Migration 미작성)."""
    repo = StockPricePeriodicRepository(session)
    with pytest.raises(ValueError, match="unsupported"):
        await repo.upsert_many([], period=Period.YEARLY, exchange=ExchangeType.KRX)


@pytest.mark.asyncio
async def test_upsert_many_sor_raises(session: AsyncSession) -> None:
    """SOR 영속화 미지원 (Phase D 결정) → ValueError."""
    repo = StockPricePeriodicRepository(session)
    with pytest.raises(ValueError, match="unsupported"):
        await repo.upsert_many([], period=Period.WEEKLY, exchange=ExchangeType.SOR)


# ---------- find_range ----------


@pytest.mark.asyncio
async def test_find_range_returns_empty_when_no_data(session: AsyncSession) -> None:
    sid = await _insert_test_stock(session, "TST304")
    repo = StockPricePeriodicRepository(session)
    rows = await repo.find_range(
        sid,
        period=Period.WEEKLY,
        exchange=ExchangeType.KRX,
        start=date(2025, 1, 1),
        end=date(2025, 12, 31),
    )
    assert rows == []


@pytest.mark.asyncio
async def test_find_range_returns_rows_in_period(session: AsyncSession) -> None:
    sid = await _insert_test_stock(session, "TST305")
    repo = StockPricePeriodicRepository(session)

    rows = [
        _make_normalized(sid, date(2025, 9, 1), ExchangeType.KRX),
        _make_normalized(sid, date(2025, 9, 8), ExchangeType.KRX),
        _make_normalized(sid, date(2025, 9, 15), ExchangeType.KRX),
    ]
    await repo.upsert_many(rows, period=Period.WEEKLY, exchange=ExchangeType.KRX)

    found = await repo.find_range(
        sid,
        period=Period.WEEKLY,
        exchange=ExchangeType.KRX,
        start=date(2025, 9, 1),
        end=date(2025, 9, 8),
    )
    assert len(found) == 2
    # asc 정렬
    assert found[0].trading_date == date(2025, 9, 1)
    assert found[1].trading_date == date(2025, 9, 8)


@pytest.mark.asyncio
async def test_find_range_start_after_end_raises(session: AsyncSession) -> None:
    sid = await _insert_test_stock(session, "TST306")
    repo = StockPricePeriodicRepository(session)
    with pytest.raises(ValueError):
        await repo.find_range(
            sid,
            period=Period.WEEKLY,
            exchange=ExchangeType.KRX,
            start=date(2025, 9, 8),
            end=date(2025, 9, 1),
        )


@pytest.mark.asyncio
async def test_find_range_yearly_raises(session: AsyncSession) -> None:
    sid = await _insert_test_stock(session, "TST307")
    repo = StockPricePeriodicRepository(session)
    with pytest.raises(ValueError, match="unsupported"):
        await repo.find_range(
            sid,
            period=Period.YEARLY,
            exchange=ExchangeType.KRX,
            start=date(2025, 1, 1),
            end=date(2025, 12, 31),
        )


@pytest.mark.asyncio
async def test_find_range_separates_periods(session: AsyncSession) -> None:
    """WEEKLY 와 MONTHLY 는 분리된 테이블 — 같은 key 라도 cross-pollination 없음."""
    sid = await _insert_test_stock(session, "TST308")
    repo = StockPricePeriodicRepository(session)

    weekly_row = _make_normalized(sid, date(2025, 9, 1), ExchangeType.KRX)
    monthly_row = _make_normalized(sid, date(2025, 9, 1), ExchangeType.KRX)

    await repo.upsert_many([weekly_row], period=Period.WEEKLY, exchange=ExchangeType.KRX)
    await repo.upsert_many([monthly_row], period=Period.MONTHLY, exchange=ExchangeType.KRX)

    weekly_found = await repo.find_range(
        sid,
        period=Period.WEEKLY,
        exchange=ExchangeType.KRX,
        start=date(2025, 9, 1),
        end=date(2025, 9, 1),
    )
    monthly_found = await repo.find_range(
        sid,
        period=Period.MONTHLY,
        exchange=ExchangeType.KRX,
        start=date(2025, 9, 1),
        end=date(2025, 9, 1),
    )
    assert len(weekly_found) == 1
    assert len(monthly_found) == 1
    # 다른 테이블 ORM 인스턴스
    assert type(weekly_found[0]).__name__ == "StockPriceWeeklyKrx"
    assert type(monthly_found[0]).__name__ == "StockPriceMonthlyKrx"


@pytest.mark.asyncio
async def test_find_range_separates_exchanges(session: AsyncSession) -> None:
    """KRX 와 NXT 는 분리된 테이블."""
    sid = await _insert_test_stock(session, "TST309")
    repo = StockPricePeriodicRepository(session)

    krx_row = _make_normalized(sid, date(2025, 9, 1), ExchangeType.KRX)
    nxt_row = _make_normalized(sid, date(2025, 9, 1), ExchangeType.NXT)

    await repo.upsert_many([krx_row], period=Period.WEEKLY, exchange=ExchangeType.KRX)
    await repo.upsert_many([nxt_row], period=Period.WEEKLY, exchange=ExchangeType.NXT)

    krx_found = await repo.find_range(
        sid, period=Period.WEEKLY, exchange=ExchangeType.KRX, start=date(2025, 9, 1), end=date(2025, 9, 1)
    )
    nxt_found = await repo.find_range(
        sid, period=Period.WEEKLY, exchange=ExchangeType.NXT, start=date(2025, 9, 1), end=date(2025, 9, 1)
    )
    assert len(krx_found) == 1
    assert len(nxt_found) == 1
    assert type(krx_found[0]).__name__ == "StockPriceWeeklyKrx"
    assert type(nxt_found[0]).__name__ == "StockPriceWeeklyNxt"
