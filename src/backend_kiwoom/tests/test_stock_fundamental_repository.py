"""StockFundamentalRepository (B-γ-1) — upsert_one + find_latest.

검증:
1. upsert_one INSERT — 새 row + RETURNING StockFundamental
2. upsert_one UPDATE — 같은 (stock_id, asof_date, exchange) 이면 UPDATE (멱등)
3. upsert_one 다른 일자 — 새 row 추가
4. fundamental_hash 산출 — PER/EPS/ROE/PBR/EV/BPS 6 필드 기준
5. find_latest — 가장 최근 asof_date row
6. find_latest 없음 → None
7. 부분 NULL 영속화 (외부 벤더 빈값 시뮬)
8. UPDATE 시 fetched_at 갱신
"""

from __future__ import annotations

import dataclasses
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom.stkinfo import NormalizedFundamental
from app.adapter.out.persistence.repositories.stock_fundamental import (
    StockFundamentalRepository,
    compute_fundamental_hash,
)


def _normalized(
    *,
    stock_code: str = "005930",
    asof: date = date(2026, 5, 8),
    per_ratio: Decimal | None = Decimal("15.20"),
    eps_won: int | None = 5000,
    roe_pct: Decimal | None = Decimal("12.50"),
    pbr_ratio: Decimal | None = Decimal("1.20"),
    ev_ratio: Decimal | None = Decimal("8.30"),
    bps_won: int | None = 70000,
) -> NormalizedFundamental:
    return NormalizedFundamental(
        stock_code=stock_code,
        exchange="KRX",
        asof_date=asof,
        stock_name="삼성전자",
        settlement_month="12",
        face_value=5000,
        face_value_unit="원",
        capital_won=1311,
        listed_shares=5969782,
        market_cap=4356400,
        market_cap_weight=Decimal("12.3456"),
        foreign_holding_rate=Decimal("53.2100"),
        replacement_price=66780,
        credit_rate=Decimal("0.0800"),
        circulating_shares=5969782,
        circulating_rate=Decimal("100.0000"),
        per_ratio=per_ratio,
        eps_won=eps_won,
        roe_pct=roe_pct,
        pbr_ratio=pbr_ratio,
        ev_ratio=ev_ratio,
        bps_won=bps_won,
        revenue_amount=300000000,
        operating_profit=50000000,
        net_profit=30000000,
        high_250d=181400,
        high_250d_date=date(2025, 12, 15),
        high_250d_pre_rate=Decimal("-25.5000"),
        low_250d=91200,
        low_250d_date=date(2025, 6, 12),
        low_250d_pre_rate=Decimal("48.0000"),
        year_high=181400,
        year_low=91200,
        current_price=75800,
        prev_compare_sign="2",
        prev_compare_amount=200,
        change_rate=Decimal("0.2640"),
        trade_volume=1234567,
        trade_compare_rate=Decimal("5.4321"),
        open_price=75600,
        high_price=76000,
        low_price=75400,
        upper_limit_price=98800,
        lower_limit_price=53000,
        base_price=75600,
        expected_match_price=75800,
        expected_match_volume=12345,
    )


async def _create_stock(session: AsyncSession, stock_code: str = "005930") -> int:
    """테스트 fixture — stock 한 건 만들고 id 반환."""
    result = await session.execute(
        text(
            "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code) "
            "VALUES (:code, :name, '0') RETURNING id"
        ).bindparams(code=stock_code, name=f"test-{stock_code}")
    )
    return int(result.scalar_one())


# -----------------------------------------------------------------------------
# 1. INSERT — RETURNING
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_one_inserts_returns_fundamental_with_id(session: AsyncSession) -> None:
    stock_id = await _create_stock(session)
    repo = StockFundamentalRepository(session)
    f = await repo.upsert_one(_normalized(), stock_id=stock_id)

    assert f.id is not None
    assert f.stock_id == stock_id
    assert f.exchange == "KRX"
    assert f.asof_date == date(2026, 5, 8)
    assert f.per_ratio == Decimal("15.20")
    assert f.eps_won == 5000
    assert f.fundamental_hash is not None
    assert len(f.fundamental_hash) == 32


# -----------------------------------------------------------------------------
# 2. UPDATE — 같은 (stock_id, asof_date, exchange) → 멱등
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_one_updates_existing_returns_same_id(session: AsyncSession) -> None:
    stock_id = await _create_stock(session)
    repo = StockFundamentalRepository(session)
    initial = await repo.upsert_one(_normalized(per_ratio=Decimal("15.20")), stock_id=stock_id)
    initial_id = initial.id
    initial_fetched = initial.fetched_at

    updated = await repo.upsert_one(_normalized(per_ratio=Decimal("16.50")), stock_id=stock_id)

    assert updated.id == initial_id, "같은 (stock_id, asof_date, exchange) — UPDATE"
    assert updated.per_ratio == Decimal("16.50")
    assert updated.fetched_at >= initial_fetched


# -----------------------------------------------------------------------------
# 3. 다른 일자 → 새 row
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_one_different_date_creates_new_row(session: AsyncSession) -> None:
    stock_id = await _create_stock(session)
    repo = StockFundamentalRepository(session)
    a = await repo.upsert_one(_normalized(asof=date(2026, 5, 7)), stock_id=stock_id)
    b = await repo.upsert_one(_normalized(asof=date(2026, 5, 8)), stock_id=stock_id)

    assert a.id != b.id
    assert a.asof_date != b.asof_date


# -----------------------------------------------------------------------------
# 4. fundamental_hash 산출 — PER/EPS/ROE/PBR/EV/BPS 6 필드 기준
# -----------------------------------------------------------------------------


def test_compute_fundamental_hash_stable_for_same_inputs() -> None:
    """같은 6 필드 → 같은 hash. 일중 시세는 hash 영향 없음."""
    n1 = _normalized(per_ratio=Decimal("15.20"), eps_won=5000)
    n2 = _normalized(per_ratio=Decimal("15.20"), eps_won=5000)
    # 일중 시세만 다른 두 정규화 — hash 동일해야 함 (slots=True 라 dataclasses.replace 필요)
    n3 = dataclasses.replace(n1, current_price=99999)

    h1 = compute_fundamental_hash(n1)
    h2 = compute_fundamental_hash(n2)
    h3 = compute_fundamental_hash(n3)

    assert h1 == h2
    assert h1 == h3, "일중 시세 변경은 hash 에 영향 없음 (펀더멘털 6 필드만)"
    assert len(h1) == 32


def test_compute_fundamental_hash_differs_when_per_changes() -> None:
    """PER 변경 → 다른 hash."""
    n1 = _normalized(per_ratio=Decimal("15.20"))
    n2 = _normalized(per_ratio=Decimal("16.50"))

    assert compute_fundamental_hash(n1) != compute_fundamental_hash(n2)


def test_compute_fundamental_hash_handles_all_none() -> None:
    """6 필드 모두 None — 외부 벤더 미공급 종목. hash 는 stable."""
    n1 = _normalized(per_ratio=None, eps_won=None, roe_pct=None, pbr_ratio=None, ev_ratio=None, bps_won=None)
    n2 = _normalized(per_ratio=None, eps_won=None, roe_pct=None, pbr_ratio=None, ev_ratio=None, bps_won=None)

    assert compute_fundamental_hash(n1) == compute_fundamental_hash(n2)
    assert len(compute_fundamental_hash(n1)) == 32


# -----------------------------------------------------------------------------
# 5-6. find_latest
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_latest_returns_most_recent_asof_date(session: AsyncSession) -> None:
    stock_id = await _create_stock(session)
    repo = StockFundamentalRepository(session)
    await repo.upsert_one(_normalized(asof=date(2026, 5, 5)), stock_id=stock_id)
    await repo.upsert_one(_normalized(asof=date(2026, 5, 7)), stock_id=stock_id)
    await repo.upsert_one(_normalized(asof=date(2026, 5, 6)), stock_id=stock_id)

    latest = await repo.find_latest(stock_id)

    assert latest is not None
    assert latest.asof_date == date(2026, 5, 7)


@pytest.mark.asyncio
async def test_find_latest_returns_none_when_no_rows(session: AsyncSession) -> None:
    stock_id = await _create_stock(session)
    repo = StockFundamentalRepository(session)

    assert await repo.find_latest(stock_id) is None


@pytest.mark.asyncio
async def test_find_latest_filters_by_exchange(session: AsyncSession) -> None:
    """exchange 파라미터 — 다른 거래소 row 는 무시 (Phase C 후 NXT 추가 시 안전)."""
    stock_id = await _create_stock(session)
    repo = StockFundamentalRepository(session)
    await repo.upsert_one(_normalized(asof=date(2026, 5, 7)), stock_id=stock_id)

    found = await repo.find_latest(stock_id, exchange="KRX")
    assert found is not None
    assert found.exchange == "KRX"

    not_found = await repo.find_latest(stock_id, exchange="NXT")
    assert not_found is None


# -----------------------------------------------------------------------------
# 7. 부분 NULL 영속화
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_one_persists_nulls_for_missing_fundamentals(session: AsyncSession) -> None:
    """외부 벤더 미공급 (PER/EPS/ROE/PBR/EV/BPS 빈값) 종목 — NULL 그대로 영속화."""
    stock_id = await _create_stock(session)
    repo = StockFundamentalRepository(session)
    n = _normalized(
        per_ratio=None, eps_won=None, roe_pct=None, pbr_ratio=None, ev_ratio=None, bps_won=None,
    )
    f = await repo.upsert_one(n, stock_id=stock_id)

    assert f.per_ratio is None
    assert f.eps_won is None
    assert f.roe_pct is None
    assert f.pbr_ratio is None
    assert f.ev_ratio is None
    assert f.bps_won is None
    assert f.fundamental_hash is not None  # 6 필드 모두 None 도 hash 산출 가능


# -----------------------------------------------------------------------------
# 8. 모든 카테고리 영속화 — 라운드트립
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_one_persists_all_categories(session: AsyncSession) -> None:
    """45 필드 → DB 라운드트립 검증 (B/C/D/E)."""
    stock_id = await _create_stock(session)
    repo = StockFundamentalRepository(session)
    n = _normalized()
    f = await repo.upsert_one(n, stock_id=stock_id)

    # B
    assert f.face_value == 5000
    assert f.face_value_unit == "원"
    assert f.market_cap == 4356400
    assert f.foreign_holding_rate == Decimal("53.2100")

    # C
    assert f.per_ratio == Decimal("15.20")
    assert f.eps_won == 5000
    assert f.revenue_amount == 300000000

    # D
    assert f.high_250d == 181400
    assert f.high_250d_date == date(2025, 12, 15)
    assert f.year_high == 181400

    # E
    assert f.current_price == 75800
    assert f.prev_compare_sign == "2"
    assert f.change_rate == Decimal("0.2640")
    assert f.trade_volume == 1234567
    assert f.expected_match_volume == 12345


# =============================================================================
# 2R 회귀 — B-H2 stock_id ↔ stock_code invariant 검증
# =============================================================================


@pytest.mark.asyncio
async def test_upsert_one_rejects_stock_code_mismatch(session: AsyncSession) -> None:
    """B-H2 — caller 가 expected_stock_code 명시 시 row 와 불일치하면 ValueError.

    fail-closed 안전망: caller 가 strip 빠뜨리고 wrong stock_id 넘기는 사고 차단.
    """
    stock_id = await _create_stock(session, "005930")
    repo = StockFundamentalRepository(session)
    n = _normalized(stock_code="005930")

    # 잘못된 expected — orphaned row 시뮬
    with pytest.raises(ValueError, match="stock_code mismatch"):
        await repo.upsert_one(n, stock_id=stock_id, expected_stock_code="000660")


@pytest.mark.asyncio
async def test_upsert_one_accepts_matching_stock_code(session: AsyncSession) -> None:
    """B-H2 — expected_stock_code 가 row 와 일치하면 정상 진행."""
    stock_id = await _create_stock(session, "005930")
    repo = StockFundamentalRepository(session)
    n = _normalized(stock_code="005930")

    f = await repo.upsert_one(n, stock_id=stock_id, expected_stock_code="005930")
    assert f.stock_id == stock_id


@pytest.mark.asyncio
async def test_upsert_one_without_expected_stock_code_legacy_path(session: AsyncSession) -> None:
    """B-H2 — expected_stock_code 미지정 (None) 은 legacy path — caller 책임으로 통과."""
    stock_id = await _create_stock(session, "005930")
    repo = StockFundamentalRepository(session)
    n = _normalized(stock_code="005930")

    f = await repo.upsert_one(n, stock_id=stock_id)  # expected_stock_code 안 넘김
    assert f.stock_id == stock_id
