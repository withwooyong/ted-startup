"""MarketDataCollectionService._compute_lending_deltas 단위 테스트.

대차잔고 전일 대비 변동률·연속 감소일수 계산 규칙 회귀 방지.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from app.application.service.market_data_service import MarketDataCollectionService


@dataclass
class _Prev:
    balance_quantity: int
    consecutive_decrease_days: int | None = 0


class TestComputeLendingDeltas:
    fn = staticmethod(MarketDataCollectionService._compute_lending_deltas)

    def test_prev_none_returns_zero_and_none(self) -> None:
        assert self.fn(today_qty=100, prev=None) == (None, None, 0)

    def test_prev_zero_balance_returns_none_rate(self) -> None:
        # 분모 0 회피 — change_q 는 계산되지만 rate 는 None
        q, r, c = self.fn(today_qty=100, prev=_Prev(balance_quantity=0))
        assert q == 100
        assert r is None
        assert c == 0  # change_q 양수 → consec 리셋

    def test_decrease_triggers_consec_increment(self) -> None:
        q, r, c = self.fn(
            today_qty=80, prev=_Prev(balance_quantity=100, consecutive_decrease_days=2)
        )
        assert q == -20
        assert r == Decimal("-20.0000")
        assert c == 3

    def test_increase_resets_consec(self) -> None:
        q, r, c = self.fn(
            today_qty=120, prev=_Prev(balance_quantity=100, consecutive_decrease_days=5)
        )
        assert q == 20
        assert r == Decimal("20.0000")
        assert c == 0

    def test_zero_change_resets_consec(self) -> None:
        # 동일 값은 감소 아님 → 리셋
        q, r, c = self.fn(
            today_qty=100, prev=_Prev(balance_quantity=100, consecutive_decrease_days=7)
        )
        assert q == 0
        assert r == Decimal("0.0000")
        assert c == 0

    def test_prev_none_consec_coerced_to_zero(self) -> None:
        q, _, c = self.fn(
            today_qty=50, prev=_Prev(balance_quantity=100, consecutive_decrease_days=None)
        )
        assert q == -50
        assert c == 1

    def test_rapid_decline_threshold_case(self) -> None:
        # 실제 RAPID_DECLINE 시그널 조건(change_rate <= -10%) 시나리오
        _, r, _ = self.fn(today_qty=899, prev=_Prev(balance_quantity=1000))
        assert r == Decimal("-10.1000")

    @pytest.mark.parametrize(
        "today_qty, prev_qty, expected_rate",
        [
            (5000, 4000, Decimal("25.0000")),
            (3000, 4000, Decimal("-25.0000")),
            (1, 3, Decimal("-66.6667")),  # 반올림 확인 (4자리)
        ],
    )
    def test_rate_quantization_four_decimals(
        self, today_qty: int, prev_qty: int, expected_rate: Decimal
    ) -> None:
        _, r, _ = self.fn(today_qty=today_qty, prev=_Prev(balance_quantity=prev_qty))
        assert r == expected_rate
