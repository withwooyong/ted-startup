"""ShortSellingKwRepository — short_selling_kw upsert + 시그널 조회 (Phase E).

chunk = E (ka10014), plan doc § 6.2 / § 9.2 / § 12 참조.

test_sector_price_repository.py / test_stock_daily_flow_repository.py 패턴 1:1 응용.

검증:
1. upsert_many INSERT (빈 DB)
2. upsert_many UPDATE 멱등성 (ON CONFLICT DO UPDATE)
3. exchange 컬럼 분리 (KRX + NXT 같은 trading_date 분리 저장)
4. idx_short_selling_kw_weight_high partial index 검증 (NULL 제외, weight DESC NULLS LAST)
5. get_high_weight_stocks 시그널 추출 (weight > 5%)
6. 빈 rows → upserted=0

NOTE: ShortSellingKwRepository 는 Step 1 에서 작성.
      본 테스트는 import 실패가 red 의도.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from app.adapter.out.persistence.repositories.short_selling import (  # type: ignore[import]  # Step 1
    ShortSellingKwRepository,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._records import (  # type: ignore[import]  # Step 1 에서 추가
    NormalizedShortSelling,
)
from app.application.constants import ExchangeType

# ---------------------------------------------------------------------------
# helper
# ---------------------------------------------------------------------------


async def _insert_test_stock(session: AsyncSession, code: str = "SS001") -> int:
    """테스트용 stock 1행 INSERT 후 id 반환."""
    await session.execute(
        text(
            "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code) "
            "VALUES (:code, 'test-stock', '0') "
            "ON CONFLICT (stock_code) DO UPDATE SET stock_name = EXCLUDED.stock_name"
        ).bindparams(code=code)
    )
    result = await session.execute(
        text("SELECT id FROM kiwoom.stock WHERE stock_code = :code").bindparams(code=code)
    )
    return int(result.scalar_one())


def _make_normalized_row(
    stock_id: int,
    trading_date: date,
    exchange: ExchangeType = ExchangeType.KRX,
    close_price: int | None = -55800,
    short_volume: int | None = 841407,
    cumulative_short_volume: int | None = 6424755,
    short_trade_weight: Decimal | None = Decimal("8.58"),
) -> NormalizedShortSelling:
    """테스트용 NormalizedShortSelling stub."""
    return NormalizedShortSelling(
        stock_id=stock_id,
        trading_date=trading_date,
        exchange=exchange,
        close_price=close_price,
        prev_compare_amount=-1000,
        prev_compare_sign="5",
        change_rate=Decimal("-1.76"),
        trade_volume=9802105,
        short_volume=short_volume,
        cumulative_short_volume=cumulative_short_volume,
        short_trade_weight=short_trade_weight,
        short_trade_amount=46985302,
        short_avg_price=55841,
    )


# ---------------------------------------------------------------------------
# 1. upsert_many INSERT (빈 DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_many_inserts_rows(session: AsyncSession) -> None:
    """stock_id FK 기반 row 2건 INSERT 성공."""
    sid = await _insert_test_stock(session, "SR001")
    repo = ShortSellingKwRepository(session)

    rows = [
        _make_normalized_row(sid, date(2025, 5, 19)),
        _make_normalized_row(sid, date(2025, 5, 16)),
    ]
    affected = await repo.upsert_many(rows)
    assert affected == 2

    result = await session.execute(
        text(
            "SELECT COUNT(*) FROM kiwoom.short_selling_kw WHERE stock_id = :sid"
        ).bindparams(sid=sid)
    )
    assert result.scalar_one() == 2


# ---------------------------------------------------------------------------
# 2. upsert_many UPDATE 멱등성 (ON CONFLICT DO UPDATE)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_many_on_conflict_updates(session: AsyncSession) -> None:
    """ON CONFLICT (stock_id, trading_date, exchange) DO UPDATE — 동일 키 갱신."""
    sid = await _insert_test_stock(session, "SR002")
    repo = ShortSellingKwRepository(session)

    row_first = _make_normalized_row(sid, date(2025, 5, 19), short_volume=500000)
    await repo.upsert_many([row_first])

    row_second = _make_normalized_row(sid, date(2025, 5, 19), short_volume=841407)
    affected = await repo.upsert_many([row_second])
    assert affected == 1

    result = await session.execute(
        text(
            "SELECT short_volume FROM kiwoom.short_selling_kw "
            "WHERE stock_id = :sid AND trading_date = :td AND exchange = 'KRX'"
        ).bindparams(sid=sid, td=date(2025, 5, 19))
    )
    assert result.scalar_one() == 841407

    # 1행 유지
    count = await session.execute(
        text(
            "SELECT COUNT(*) FROM kiwoom.short_selling_kw WHERE stock_id = :sid"
        ).bindparams(sid=sid)
    )
    assert count.scalar_one() == 1


# ---------------------------------------------------------------------------
# 3. exchange 컬럼 분리 (KRX + NXT 같은 trading_date 분리 저장)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_many_exchange_column_separation(session: AsyncSession) -> None:
    """같은 stock_id + trading_date 이지만 exchange 다르면 별도 row 저장."""
    sid = await _insert_test_stock(session, "SR003")
    repo = ShortSellingKwRepository(session)

    krx_row = _make_normalized_row(sid, date(2025, 5, 19), exchange=ExchangeType.KRX)
    nxt_row = _make_normalized_row(sid, date(2025, 5, 19), exchange=ExchangeType.NXT)
    affected = await repo.upsert_many([krx_row, nxt_row])

    assert affected == 2

    krx_count = await session.execute(
        text(
            "SELECT COUNT(*) FROM kiwoom.short_selling_kw "
            "WHERE stock_id = :sid AND trading_date = :td AND exchange = 'KRX'"
        ).bindparams(sid=sid, td=date(2025, 5, 19))
    )
    nxt_count = await session.execute(
        text(
            "SELECT COUNT(*) FROM kiwoom.short_selling_kw "
            "WHERE stock_id = :sid AND trading_date = :td AND exchange = 'NXT'"
        ).bindparams(sid=sid, td=date(2025, 5, 19))
    )
    assert krx_count.scalar_one() == 1
    assert nxt_count.scalar_one() == 1


# ---------------------------------------------------------------------------
# 4. idx_short_selling_kw_weight_high partial index — NULL 제외, weight DESC
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_partial_index_excludes_null_weight(session: AsyncSession) -> None:
    """short_trade_weight=None → idx_short_selling_kw_weight_high partial index 제외.

    NULL 가중치 row 는 인덱스에 없어야 함 (WHERE short_trade_weight IS NOT NULL).
    PostgreSQL partial index 를 직접 쿼리하여 인덱스 이름 존재 확인.
    """
    sid = await _insert_test_stock(session, "SR004")
    repo = ShortSellingKwRepository(session)

    # weight=None → partial index 제외 대상
    null_weight_row = _make_normalized_row(
        sid, date(2025, 5, 19), short_trade_weight=None
    )
    # weight 있는 row → partial index 포함
    weighted_row = _make_normalized_row(
        sid, date(2025, 5, 16), short_trade_weight=Decimal("8.58")
    )

    await repo.upsert_many([null_weight_row, weighted_row])

    # partial index 존재 확인 (idx_short_selling_kw_weight_high)
    idx_result = await session.execute(
        text(
            "SELECT indexname FROM pg_indexes "
            "WHERE schemaname = 'kiwoom' AND tablename = 'short_selling_kw' "
            "AND indexname = 'idx_short_selling_kw_weight_high'"
        )
    )
    idx_row = idx_result.fetchone()
    assert idx_row is not None, "idx_short_selling_kw_weight_high partial index 미존재"

    # NULL weight row 는 DB 에 저장됨 (index 제외이지만 data row 는 있음)
    total = await session.execute(
        text(
            "SELECT COUNT(*) FROM kiwoom.short_selling_kw WHERE stock_id = :sid"
        ).bindparams(sid=sid)
    )
    assert total.scalar_one() == 2


# ---------------------------------------------------------------------------
# 5. get_high_weight_stocks 시그널 추출 (weight > 5%)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_high_weight_stocks_returns_above_threshold(
    session: AsyncSession,
) -> None:
    """일별 공매도 매매비중 > Decimal('5') 종목만 반환."""
    # 3 종목 INSERT
    sid1 = await _insert_test_stock(session, "SR005A")
    sid2 = await _insert_test_stock(session, "SR005B")
    sid3 = await _insert_test_stock(session, "SR005C")

    repo = ShortSellingKwRepository(session)

    target_date = date(2025, 5, 19)
    rows = [
        _make_normalized_row(sid1, target_date, short_trade_weight=Decimal("8.58")),  # > 5%
        _make_normalized_row(sid2, target_date, short_trade_weight=Decimal("3.00")),  # < 5%
        _make_normalized_row(sid3, target_date, short_trade_weight=Decimal("12.00")),  # > 5%
    ]
    await repo.upsert_many(rows)

    high_weight = await repo.get_high_weight_stocks(
        target_date,
        min_weight=Decimal("5"),
    )

    assert len(high_weight) == 2
    weights = [row.short_trade_weight for row in high_weight]
    assert all(w is not None and w >= Decimal("5") for w in weights)
    # DESC 정렬 확인
    assert weights[0] >= weights[1]


# ---------------------------------------------------------------------------
# 6. 빈 rows → upserted=0
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_many_empty_rows_returns_zero(session: AsyncSession) -> None:
    """빈 list upsert → 0 반환, DB 변경 없음."""
    repo = ShortSellingKwRepository(session)
    affected = await repo.upsert_many([])
    assert affected == 0

    count = await session.execute(
        text("SELECT COUNT(*) FROM kiwoom.short_selling_kw")
    )
    assert count.scalar_one() == 0


# ---------------------------------------------------------------------------
# trading_date == date.min → skip (upsert_many 자동 필터)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_many_skips_date_min_rows(session: AsyncSession) -> None:
    """trading_date == date.min (dt='' 정규화 결과) → upsert_many 에서 skip."""
    sid = await _insert_test_stock(session, "SR006")
    repo = ShortSellingKwRepository(session)

    rows = [
        _make_normalized_row(sid, date.min),       # skip 대상
        _make_normalized_row(sid, date(2025, 5, 19)),  # 정상
    ]
    affected = await repo.upsert_many(rows)
    assert affected == 1

    count = await session.execute(
        text(
            "SELECT COUNT(*) FROM kiwoom.short_selling_kw WHERE stock_id = :sid"
        ).bindparams(sid=sid)
    )
    assert count.scalar_one() == 1
