"""UI 데모 시드 — 결정론성 및 시계열 생성 단위 테스트."""

from __future__ import annotations

from datetime import date

import pytest

from scripts.seed_ui_demo import (
    DEMO_STOCKS,
    DemoStock,
    business_days_back,
    generate_price_series,
)

# ---------------------------------------------------------------------------
# business_days_back
# ---------------------------------------------------------------------------


def test_business_days_back_excludes_weekends() -> None:
    # 2026-04-19 는 일요일. 직전 영업일 5개를 거꾸로.
    sunday = date(2026, 4, 19)
    days = business_days_back(sunday, 5)
    assert len(days) == 5
    # 모두 월~금
    assert all(d.weekday() < 5 for d in days)
    # 오름차순
    assert days == sorted(days)


def test_business_days_back_ordering_and_count() -> None:
    days = business_days_back(date(2026, 4, 17), 60)  # 금요일 기준
    assert len(days) == 60
    assert days[-1] == date(2026, 4, 17)  # 오늘이 마지막
    # 모든 요일이 월~금
    assert all(d.weekday() < 5 for d in days)


# ---------------------------------------------------------------------------
# generate_price_series
# ---------------------------------------------------------------------------


_DEMO = DemoStock("005930", "삼성전자", "KOSPI", "반도체", 72_000)


def test_generate_price_series_is_deterministic_per_seed() -> None:
    days = business_days_back(date(2026, 4, 17), 10)
    r1 = generate_price_series(_DEMO, days, seed=42)
    r2 = generate_price_series(_DEMO, days, seed=42)
    # 동일 seed → 동일 결과
    assert [row["close_price"] for row in r1] == [row["close_price"] for row in r2]


def test_generate_price_series_differs_between_seeds() -> None:
    days = business_days_back(date(2026, 4, 17), 10)
    r1 = generate_price_series(_DEMO, days, seed=1)
    r2 = generate_price_series(_DEMO, days, seed=2)
    assert [row["close_price"] for row in r1] != [row["close_price"] for row in r2]


def test_generate_price_series_shape_and_invariants() -> None:
    days = business_days_back(date(2026, 4, 17), 30)
    rows = generate_price_series(_DEMO, days, seed=123)
    assert len(rows) == 30
    for row in rows:
        close = row["close_price"]
        open_ = row["open_price"]
        high = row["high_price"]
        low = row["low_price"]
        assert isinstance(close, int) and close > 0
        assert isinstance(open_, int)
        assert isinstance(high, int)
        assert isinstance(low, int)
        # OHLC 불변식
        assert low <= open_ <= high or low <= close <= high
        assert low <= high
        assert row["volume"] > 0


def test_demo_stocks_set_is_valid() -> None:
    """5개 대표 종목이 모두 6자리 유효 코드 + 기본가 > 0."""
    assert len(DEMO_STOCKS) >= 3
    codes = {s.stock_code for s in DEMO_STOCKS}
    assert len(codes) == len(DEMO_STOCKS)  # 중복 없음
    for s in DEMO_STOCKS:
        assert len(s.stock_code) == 6 and s.stock_code.isdigit()
        assert s.base_price > 0
        assert s.market_type in ("KOSPI", "KOSDAQ")


# ---------------------------------------------------------------------------
# 통합: 가격 시계열이 변동률을 내포하는지 (MDD/수익률 계산 가능성)
# ---------------------------------------------------------------------------


def test_generate_price_series_has_nonzero_variation() -> None:
    """시계열에 충분한 변동이 있어 MDD/수익률 계산이 유의미해야 함."""
    days = business_days_back(date(2026, 4, 17), 60)
    rows = generate_price_series(_DEMO, days, seed=20260419)
    closes = [int(row["close_price"]) for row in rows]
    # 최대/최소 차이가 최소 ±5% 이상이어야 UI 지표가 의미있게 나타남
    peak = max(closes)
    trough = min(closes)
    assert (peak - trough) / trough > 0.05


@pytest.mark.parametrize("days_count", [30, 60, 90])
def test_generate_price_series_respects_day_count(days_count: int) -> None:
    days = business_days_back(date(2026, 4, 17), days_count)
    rows = generate_price_series(_DEMO, days, seed=7)
    assert len(rows) == days_count
