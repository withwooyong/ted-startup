"""KST 영업일 helper (ADR § 35).

`previous_kst_business_day` 요일 경계 단언 — cron 06:00 발화 시 base_date 결정 로직.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.batch.business_day import previous_kst_business_day


@pytest.mark.parametrize(
    "today, expected",
    [
        # 2026-05-11 (Mon, weekday=0) → 2026-05-08 (Fri, last business day)
        (date(2026, 5, 11), date(2026, 5, 8)),
        # 2026-05-12 (Tue) → 2026-05-11 (Mon)
        (date(2026, 5, 12), date(2026, 5, 11)),
        # 2026-05-13 (Wed) → 2026-05-12 (Tue)
        (date(2026, 5, 13), date(2026, 5, 12)),
        # 2026-05-14 (Thu) → 2026-05-13 (Wed)
        (date(2026, 5, 14), date(2026, 5, 13)),
        # 2026-05-15 (Fri) → 2026-05-14 (Thu)
        (date(2026, 5, 15), date(2026, 5, 14)),
        # 2026-05-16 (Sat, weekday=5) → 2026-05-15 (Fri) — Weekly cron sat 발화
        (date(2026, 5, 16), date(2026, 5, 15)),
        # 2026-05-17 (Sun, weekday=6) → 2026-05-15 (Fri) — 안전망
        (date(2026, 5, 17), date(2026, 5, 15)),
    ],
)
def test_previous_kst_business_day_by_weekday(today: date, expected: date) -> None:
    assert previous_kst_business_day(today) == expected


def test_previous_kst_business_day_monday_skips_weekend() -> None:
    """Monday → Friday (3일 전). 토/일 거래 없음 자연 skip."""
    mon = date(2026, 5, 11)
    fri = previous_kst_business_day(mon)
    assert fri == date(2026, 5, 8)
    assert fri.weekday() == 4  # Friday


def test_previous_kst_business_day_saturday_returns_friday() -> None:
    """Saturday (Weekly cron 발화) → Friday. 주봉 마지막 거래일 일치."""
    sat = date(2026, 5, 16)
    fri = previous_kst_business_day(sat)
    assert fri == date(2026, 5, 15)
    assert fri.weekday() == 4  # Friday


def test_previous_kst_business_day_pure_function_no_side_effects() -> None:
    """side-effect 없음 — 캘린더 외부 의존성 0 (공휴일 무시 정책 유지)."""
    today = date(2026, 5, 13)
    expected = date(2026, 5, 12)
    # 같은 입력으로 여러 번 호출해도 동일
    assert previous_kst_business_day(today) == expected
    assert previous_kst_business_day(today) == expected
