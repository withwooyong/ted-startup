"""DailyMarketDisplayMode StrEnum (C-2α).

설계: endpoint-10-ka10086.md § 2.3.

검증:
- value 가 "0"/"1"
- 멤버 이름 QUANTITY/AMOUNT
- StrEnum 동작 (str 호환)
- 키움 API spec 일치
"""

from __future__ import annotations

import pytest

from app.application.constants import DailyMarketDisplayMode


def test_quantity_value_is_zero() -> None:
    assert DailyMarketDisplayMode.QUANTITY.value == "0"


def test_amount_value_is_one() -> None:
    assert DailyMarketDisplayMode.AMOUNT.value == "1"


def test_str_enum_str_compat() -> None:
    """StrEnum 이라 str() 동등성 유지."""
    assert str(DailyMarketDisplayMode.QUANTITY) == "0"
    assert str(DailyMarketDisplayMode.AMOUNT) == "1"


def test_membership_check() -> None:
    members = {m.value for m in DailyMarketDisplayMode}
    assert members == {"0", "1"}


def test_value_construction() -> None:
    assert DailyMarketDisplayMode("0") is DailyMarketDisplayMode.QUANTITY
    assert DailyMarketDisplayMode("1") is DailyMarketDisplayMode.AMOUNT


def test_invalid_value_raises() -> None:
    with pytest.raises(ValueError):
        DailyMarketDisplayMode("2")


# ---------- 2b-M2 회귀 — ExchangeType 길이 정적 invariant ----------


def test_exchange_type_values_within_varchar4_limit() -> None:
    """모든 ExchangeType.value 가 VARCHAR(4) 한도 안 (Migration 005/006/007 일관)."""
    from app.application.constants import EXCHANGE_TYPE_MAX_LENGTH, ExchangeType

    assert EXCHANGE_TYPE_MAX_LENGTH == 4
    for member in ExchangeType:
        assert len(member.value) <= EXCHANGE_TYPE_MAX_LENGTH, (
            f"{member.name}={member.value!r} 가 VARCHAR({EXCHANGE_TYPE_MAX_LENGTH}) 한도 초과"
        )
