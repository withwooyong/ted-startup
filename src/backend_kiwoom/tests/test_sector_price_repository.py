"""SectorPriceDailyRepository — sector_price_daily upsert + 조회 (D-1).

D-1 follow-up 추가 (§ 13):
- test_upsert_many_chunks_5500_rows_under_32767_param_limit
  : 5500 row × 8 col = 44000 query args → chunk 분할로 InterfaceError 회피 확인.

chunk = D-1, plan doc § 12 참조.

test_stock_price_periodic_repository.py 의 upsert idempotent / 동일 키 갱신 / FK /
UNIQUE 충돌 패턴 1:1 응용. sector_id FK 기반 upsert.

검증:
- upsert_many insert 정상 적재
- ON CONFLICT (sector_id, trading_date) DO UPDATE — 동일 키 갱신
- FK constraint — 존재하지 않는 sector_id 참조 시 IntegrityError
- trading_date == date.min 자동 skip
- 빈 rows → 0 반환
- 100배 값 (centi BIGINT) 정상 저장
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.models.sector_price_daily import SectorPriceDaily
from app.adapter.out.persistence.repositories.sector_price import SectorPriceDailyRepository


async def _insert_test_sector(session: AsyncSession, code: str = "TST001") -> int:
    """테스트용 sector 1행 INSERT 후 id 반환."""
    await session.execute(
        text(
            "INSERT INTO kiwoom.sector (market_code, sector_code, sector_name) "
            "VALUES ('0', :code, 'sector-test') "
            "ON CONFLICT (market_code, sector_code) DO UPDATE SET sector_name = EXCLUDED.sector_name"
        ).bindparams(code=code)
    )
    result = await session.execute(
        text("SELECT id FROM kiwoom.sector WHERE market_code = '0' AND sector_code = :code").bindparams(code=code)
    )
    return int(result.scalar_one())


def _make_row(
    sector_id: int,
    trading_date: date,
    close_index_centi: int = 252127,
) -> dict[str, Any]:
    """NormalizedSectorDailyOhlcv 역할의 dict stub."""
    return {
        "sector_id": sector_id,
        "trading_date": trading_date,
        "open_index_centi": 251064,
        "high_index_centi": 252733,
        "low_index_centi": 249918,
        "close_index_centi": close_index_centi,
        "trade_volume": 393564,
        "trade_amount": 10582466,
    }


# ---------- 1. 정상 upsert ----------


@pytest.mark.asyncio
async def test_upsert_many_inserts_rows(session: AsyncSession) -> None:
    """sector_id FK 기반 row 2건 INSERT 성공."""
    sid = await _insert_test_sector(session, "SP001")
    repo = SectorPriceDailyRepository(session)

    rows = [
        _make_row(sid, date(2025, 9, 8)),
        _make_row(sid, date(2025, 9, 5)),
    ]
    affected = await repo.upsert_many(rows)
    assert affected == 2

    result = await session.execute(
        text("SELECT COUNT(*) FROM kiwoom.sector_price_daily WHERE sector_id = :sid").bindparams(sid=sid)
    )
    assert result.scalar_one() == 2


# ---------- 2. ON CONFLICT DO UPDATE ----------


@pytest.mark.asyncio
async def test_upsert_many_on_conflict_updates(session: AsyncSession) -> None:
    """ON CONFLICT (sector_id, trading_date) DO UPDATE — 동일 키 두 번째 호출 시 갱신."""
    sid = await _insert_test_sector(session, "SP002")
    repo = SectorPriceDailyRepository(session)

    row1 = _make_row(sid, date(2025, 9, 8), close_index_centi=252127)
    await repo.upsert_many([row1])

    row2 = _make_row(sid, date(2025, 9, 8), close_index_centi=999999)
    affected = await repo.upsert_many([row2])
    assert affected == 1

    result = await session.execute(
        text(
            "SELECT close_index_centi FROM kiwoom.sector_price_daily "
            "WHERE sector_id = :sid AND trading_date = :td"
        ).bindparams(sid=sid, td=date(2025, 9, 8))
    )
    assert result.scalar_one() == 999999

    # 1행 유지 (insert 가 아닌 update)
    count = await session.execute(
        text("SELECT COUNT(*) FROM kiwoom.sector_price_daily WHERE sector_id = :sid").bindparams(sid=sid)
    )
    assert count.scalar_one() == 1


# ---------- 3. trading_date == date.min skip ----------


@pytest.mark.asyncio
async def test_upsert_many_skips_date_min_rows(session: AsyncSession) -> None:
    """trading_date == date.min 빈 응답 row 자동 skip."""
    sid = await _insert_test_sector(session, "SP003")
    repo = SectorPriceDailyRepository(session)

    rows = [
        _make_row(sid, date.min),  # skip 대상
        _make_row(sid, date(2025, 9, 8)),
    ]
    affected = await repo.upsert_many(rows)
    assert affected == 1


# ---------- 4. 빈 rows → 0 ----------


@pytest.mark.asyncio
async def test_upsert_many_empty_rows_returns_zero(session: AsyncSession) -> None:
    """빈 list upsert → 0 반환."""
    repo = SectorPriceDailyRepository(session)
    affected = await repo.upsert_many([])
    assert affected == 0


# ---------- 5. FK constraint ----------


@pytest.mark.asyncio
async def test_upsert_many_fk_constraint_raises_for_invalid_sector(session: AsyncSession) -> None:
    """존재하지 않는 sector_id 참조 시 IntegrityError."""
    from sqlalchemy.exc import IntegrityError

    repo = SectorPriceDailyRepository(session)
    rows = [_make_row(sector_id=9999999, trading_date=date(2025, 9, 8))]
    with pytest.raises(IntegrityError):
        await repo.upsert_many(rows)


# ---------- 6. centi BIGINT 값 정확성 ----------


@pytest.mark.asyncio
async def test_upsert_many_stores_centi_bigint_correctly(session: AsyncSession) -> None:
    """100배 값 (centi BIGINT) 이 그대로 저장됨.

    KOSPI 2521.27 → 252127 (centi). DB 에 252127 저장 확인.
    """
    sid = await _insert_test_sector(session, "SP004")
    repo = SectorPriceDailyRepository(session)

    row = _make_row(sid, date(2025, 2, 10), close_index_centi=252127)
    row["open_index_centi"] = 251064
    row["high_index_centi"] = 252733
    row["low_index_centi"] = 249918
    await repo.upsert_many([row])

    result = await session.execute(
        text(
            "SELECT open_index_centi, high_index_centi, low_index_centi, close_index_centi "
            "FROM kiwoom.sector_price_daily WHERE sector_id = :sid AND trading_date = :td"
        ).bindparams(sid=sid, td=date(2025, 2, 10))
    )
    row_db = result.one()
    assert row_db.open_index_centi == 251064
    assert row_db.high_index_centi == 252733
    assert row_db.low_index_centi == 249918
    assert row_db.close_index_centi == 252127


# ---------- D-1 follow-up — chunk 분할로 32767 한도 회피 ----------


@pytest.mark.asyncio
async def test_upsert_many_chunks_5500_rows_under_32767_param_limit(
    session: AsyncSession,
) -> None:
    """5500 row × 8 col = 44000 query args — chunk_size=1000 분할로 InterfaceError 회피.

    이 테스트가 fix 의 핵심:
    - chunk 미적용 시: asyncpg 가 단일 INSERT 에 44000 args 전달 →
      `asyncpg.exceptions._base.InterfaceError: cannot exceed 32767` 발생 (red)
    - chunk 적용 후: 8000 args/chunk (1000 × 8) × 6 chunks → InterfaceError 없이 적재 (green)

    testcontainers PG16 실 DB 에서 실행 — mock 아님.
    """
    sid = await _insert_test_sector(session, "SPCK5500")
    repo = SectorPriceDailyRepository(session)

    base = date(2010, 1, 1)
    rows = [
        {
            "sector_id": sid,
            "trading_date": base + timedelta(days=i),
            "open_index_centi": 100000 + i,
            "high_index_centi": 100100 + i,
            "low_index_centi": 99900 + i,
            "close_index_centi": 100050 + i,
            "trade_volume": 1_000_000 + i,
            "trade_amount": 2_000_000_000 + i,
        }
        for i in range(5500)
    ]

    count = await repo.upsert_many(rows)
    assert count == 5500

    stmt = select(func.count()).select_from(SectorPriceDaily).where(
        SectorPriceDaily.sector_id == sid
    )
    db_count = (await session.execute(stmt)).scalar_one()
    assert db_count == 5500
