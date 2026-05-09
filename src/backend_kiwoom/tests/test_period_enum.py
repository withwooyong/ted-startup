"""Period(StrEnum) — 주봉/월봉/년봉 시계열 분류 (C-3α).

설계: phase-c-3-weekly-monthly-ohlcv.md § H-3.

원칙:
- WEEKLY / MONTHLY / YEARLY 3값. DAILY 는 별도 UseCase (IngestDailyOhlcvUseCase) 라 본 enum 외
- value 는 소문자 string ("weekly"/"monthly"/"yearly") — 라우터 path / cron job id 와 일관
- import 시점 fail-fast 검증 — 멤버 추가 시 동일 패턴 강제 (ExchangeType.EXCHANGE_TYPE_MAX_LENGTH 패턴 재사용)
"""

from __future__ import annotations

import pytest


def test_period_enum_has_three_values() -> None:
    """Period 는 WEEKLY / MONTHLY / YEARLY 3값만."""
    from app.application.constants import Period

    members = {m.name for m in Period}
    assert members == {"WEEKLY", "MONTHLY", "YEARLY"}


def test_period_enum_values_are_lowercase() -> None:
    """value 는 소문자 string — 라우터 path / cron job id 와 일관."""
    from app.application.constants import Period

    assert Period.WEEKLY.value == "weekly"
    assert Period.MONTHLY.value == "monthly"
    assert Period.YEARLY.value == "yearly"


def test_period_does_not_include_daily() -> None:
    """DAILY 는 IngestDailyOhlcvUseCase 가 별도 처리 — 본 enum 에 노출 안 함 (H-3)."""
    from app.application.constants import Period

    assert "DAILY" not in {m.name for m in Period}
    assert "daily" not in {m.value for m in Period}


def test_period_is_str_enum() -> None:
    """StrEnum — 직렬화 시 value string 그대로."""
    from enum import StrEnum

    from app.application.constants import Period

    assert issubclass(Period, StrEnum)
    assert str(Period.WEEKLY) == "weekly"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("weekly", "WEEKLY"),
        ("monthly", "MONTHLY"),
        ("yearly", "YEARLY"),
    ],
)
def test_period_lookup_by_value(value: str, expected: str) -> None:
    """value 로 enum 조회 — 라우터/cron 에서 string 입력 받을 때."""
    from app.application.constants import Period

    assert Period(value).name == expected


def test_period_invalid_value_raises() -> None:
    """미정의 value 는 ValueError."""
    from app.application.constants import Period

    with pytest.raises(ValueError):
        Period("daily")
    with pytest.raises(ValueError):
        Period("hourly")
