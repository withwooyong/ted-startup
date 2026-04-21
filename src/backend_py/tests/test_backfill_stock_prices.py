"""과거 N 영업일 백필 스크립트 — 단위 테스트.

실제 API 호출 없이 business_days_back 로직만 검증. run() 은 통합
성격이 강해 단위 테스트 범위 밖.
"""

from __future__ import annotations

from datetime import date

from scripts.backfill_stock_prices import business_days_back


def test_business_days_back_excludes_weekends() -> None:
    sunday = date(2026, 4, 19)
    days = business_days_back(sunday, 5)
    assert len(days) == 5
    assert all(d.weekday() < 5 for d in days)
    assert days == sorted(days)


def test_business_days_back_last_day_is_end_when_weekday() -> None:
    friday = date(2026, 4, 17)
    days = business_days_back(friday, 10)
    assert len(days) == 10
    assert days[-1] == friday


def test_business_days_back_large_range_is_deterministic() -> None:
    end = date(2026, 4, 17)
    days = business_days_back(end, 252)
    # 1년치(252 영업일) — 시작일은 대략 전년 같은 주 금요일 부근
    assert len(days) == 252
    assert days[-1] == end
    # 모두 평일
    assert all(d.weekday() < 5 for d in days)
    # 오름차순 중복 없음
    assert len(set(days)) == 252
