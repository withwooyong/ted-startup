"""투자자 record — 9 enum + 3 Pydantic Row + _strip_double_sign_int + _to_decimal_div_100 (Phase G).

TDD red 의도:
- `app.adapter.out.kiwoom._records.{InvestorType, InvestorTradeType, ...}` 미존재
- `InvestorDailyTradeRow, StockInvestorBreakdownRow, ContinuousFrgnOrgnRow` 미존재
- `_to_decimal_div_100` helper 미존재
→ Step 1 구현 후 green 전환.

검증 (~25 케이스):
- 9 enum value 매핑 (InvestorType 12 / InvestorTradeType 2 / InvestorMarketType 2 /
                     AmountQuantityType 2 / StockInvestorTradeType 3 / UnitType 2 /
                     ContinuousPeriodType 7 / ContinuousAmtQtyType 2 / StockIndsType 2)
- 3 Row frozen + extra="ignore"
- _strip_double_sign_int 재사용 (이중 부호)
- _to_decimal_div_100 신규 (flu_rt "+698" → Decimal("6.98"))
- NormalizedInvestorDailyTrade / NormalizedStockInvestorBreakdown / NormalizedFrgnOrgnConsecutive to_normalized
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.adapter.out.kiwoom._records import (  # type: ignore[import]  # Step 1
    AmountQuantityType,
    ContinuousAmtQtyType,
    ContinuousFrgnOrgnRow,
    ContinuousPeriodType,
    InvestorDailyTradeRow,
    InvestorMarketType,
    InvestorTradeType,
    InvestorType,
    RankingExchangeType,
    StockIndsType,
    StockInvestorBreakdownRow,
    StockInvestorTradeType,
    UnitType,
    _to_decimal_div_100,
)

# ---------------------------------------------------------------------------
# 1. InvestorType enum — 12 카테고리
# ---------------------------------------------------------------------------


def test_investor_type_individual() -> None:
    assert InvestorType.INDIVIDUAL.value == "8000"


def test_investor_type_foreign() -> None:
    assert InvestorType.FOREIGN.value == "9000"


def test_investor_type_institution_total() -> None:
    assert InvestorType.INSTITUTION_TOTAL.value == "9999"


def test_investor_type_all_12_categories() -> None:
    """12 카테고리 모두 존재 + 값 검증."""
    expected = {
        "INDIVIDUAL": "8000",
        "FOREIGN": "9000",
        "INSTITUTION_TOTAL": "9999",
        "FINANCIAL_INV": "1000",
        "INVESTMENT_TRUST": "3000",
        "PRIVATE_FUND": "3100",
        "OTHER_FINANCIAL": "5000",
        "BANK": "4000",
        "INSURANCE": "2000",
        "PENSION_FUND": "6000",
        "NATION": "7000",
        "OTHER_CORP": "7100",
    }
    for name, value in expected.items():
        member = InvestorType[name]
        assert member.value == value, f"InvestorType.{name} = {member.value!r} (기대 {value!r})"


# ---------------------------------------------------------------------------
# 2. InvestorTradeType enum
# ---------------------------------------------------------------------------


def test_investor_trade_type_net_sell() -> None:
    assert InvestorTradeType.NET_SELL.value == "1"


def test_investor_trade_type_net_buy() -> None:
    assert InvestorTradeType.NET_BUY.value == "2"


# ---------------------------------------------------------------------------
# 3. InvestorMarketType enum (D-17 신규 — 001/101 만)
# ---------------------------------------------------------------------------


def test_investor_market_type_kospi() -> None:
    assert InvestorMarketType.KOSPI.value == "001"


def test_investor_market_type_kosdaq() -> None:
    assert InvestorMarketType.KOSDAQ.value == "101"


def test_investor_market_type_has_only_two_members() -> None:
    """D-17 — 000 전체 없음. KOSPI + KOSDAQ 2종만."""
    values = {m.value for m in InvestorMarketType}
    assert "000" not in values, "InvestorMarketType 에 '000' (전체) 미포함 기대"
    assert len(values) == 2, f"InvestorMarketType 2종 기대, 실제: {values}"


# ---------------------------------------------------------------------------
# 4. AmountQuantityType enum (ka10059 — 1=금액/2=수량)
# ---------------------------------------------------------------------------


def test_amount_quantity_type_amount() -> None:
    assert AmountQuantityType.AMOUNT.value == "1"


def test_amount_quantity_type_quantity() -> None:
    assert AmountQuantityType.QUANTITY.value == "2"


# ---------------------------------------------------------------------------
# 5. StockInvestorTradeType enum (ka10059 — 0/1/2)
# ---------------------------------------------------------------------------


def test_stock_investor_trade_type_net_buy() -> None:
    assert StockInvestorTradeType.NET_BUY.value == "0"


def test_stock_investor_trade_type_buy() -> None:
    assert StockInvestorTradeType.BUY.value == "1"


def test_stock_investor_trade_type_sell() -> None:
    assert StockInvestorTradeType.SELL.value == "2"


# ---------------------------------------------------------------------------
# 6. UnitType enum
# ---------------------------------------------------------------------------


def test_unit_type_thousand_shares() -> None:
    assert UnitType.THOUSAND_SHARES.value == "1000"


def test_unit_type_single_share() -> None:
    assert UnitType.SINGLE_SHARE.value == "1"


# ---------------------------------------------------------------------------
# 7. ContinuousPeriodType enum — 7종
# ---------------------------------------------------------------------------


def test_continuous_period_type_all_7_members() -> None:
    expected = {
        "LATEST": "1",
        "DAYS_3": "3",
        "DAYS_5": "5",
        "DAYS_10": "10",
        "DAYS_20": "20",
        "DAYS_120": "120",
        "PERIOD": "0",
    }
    for name, value in expected.items():
        member = ContinuousPeriodType[name]
        assert member.value == value, f"ContinuousPeriodType.{name} = {member.value!r} (기대 {value!r})"


# ---------------------------------------------------------------------------
# 8. ContinuousAmtQtyType enum (D-15 반대 의미 — 0=금액/1=수량)
# ---------------------------------------------------------------------------


def test_continuous_amt_qty_type_amount_is_zero() -> None:
    """D-15 — ka10059 AmountQuantityType.AMOUNT="1" 와 반대."""
    assert ContinuousAmtQtyType.AMOUNT.value == "0"


def test_continuous_amt_qty_type_quantity_is_one() -> None:
    """D-15 — ka10059 AmountQuantityType.QUANTITY="2" 와 반대."""
    assert ContinuousAmtQtyType.QUANTITY.value == "1"


# ---------------------------------------------------------------------------
# 9. StockIndsType enum
# ---------------------------------------------------------------------------


def test_stock_inds_type_stock() -> None:
    assert StockIndsType.STOCK.value == "0"


def test_stock_inds_type_industry() -> None:
    assert StockIndsType.INDUSTRY.value == "1"


# ---------------------------------------------------------------------------
# 10. _to_decimal_div_100 helper (신규) — flu_rt 정규화
# ---------------------------------------------------------------------------


def test_to_decimal_div_100_positive() -> None:
    """+698 → Decimal("6.98")."""
    result = _to_decimal_div_100("+698")
    assert result == Decimal("6.98"), f"기대 Decimal('6.98'), 실제: {result!r}"


def test_to_decimal_div_100_negative() -> None:
    """-580 → Decimal("-5.80")."""
    result = _to_decimal_div_100("-580")
    assert result is not None
    assert result == Decimal("-5.80"), f"기대 Decimal('-5.80'), 실제: {result!r}"


def test_to_decimal_div_100_empty_returns_none() -> None:
    """빈 입력 → None."""
    assert _to_decimal_div_100("") is None
    assert _to_decimal_div_100("  ") is None


def test_to_decimal_div_100_zero() -> None:
    """0 → Decimal("0.00")."""
    result = _to_decimal_div_100("0")
    assert result is not None
    assert result == Decimal("0")


# ---------------------------------------------------------------------------
# 11. InvestorDailyTradeRow (ka10058) — frozen + extra="ignore"
# ---------------------------------------------------------------------------


def test_investor_daily_trade_row_frozen() -> None:
    """frozen=True — 필드 변경 시 ValidationError / AttributeError / TypeError."""
    from pydantic import ValidationError as PydanticValidationError

    row = InvestorDailyTradeRow(stk_cd="005930", stk_nm="삼성전자")
    with pytest.raises((AttributeError, TypeError, PydanticValidationError)):
        row.stk_cd = "000000"  # type: ignore[misc]


def test_investor_daily_trade_row_extra_ignore() -> None:
    """extra="ignore" — 알 수 없는 필드 무시."""
    row = InvestorDailyTradeRow(stk_cd="005930", unknown_field="ignored")  # type: ignore[call-arg]
    assert row.stk_cd == "005930"


def test_investor_daily_trade_row_to_normalized() -> None:
    """to_normalized — NormalizedInvestorDailyTrade dataclass 반환."""
    from datetime import date

    row = InvestorDailyTradeRow(
        stk_cd="005930",
        stk_nm="삼성전자",
        netslmt_qty="+4464",
        netslmt_amt="+25467",
        prsm_avg_pric="57056",
        cur_prc="+61300",
        pre_sig="2",
        pred_pre="+4000",
        avg_pric_pre="--335",  # 이중 부호
        pre_rt="+7.43",
        dt_trde_qty="1554171",
    )
    normalized = row.to_normalized(
        stock_id=1,
        as_of_date=date(2026, 5, 16),
        investor_type=InvestorType.FOREIGN,
        trade_type=InvestorTradeType.NET_BUY,
        market_type=InvestorMarketType.KOSPI,
        exchange_type=RankingExchangeType.UNIFIED,
        rank=1,
    )
    assert normalized.net_volume == 4464
    assert normalized.net_amount == 25467
    assert normalized.avg_price_compare == -335  # 이중 부호 → 음수


# ---------------------------------------------------------------------------
# 12. StockInvestorBreakdownRow (ka10059) — flu_rt 정규화
# ---------------------------------------------------------------------------


def test_stock_investor_breakdown_row_flu_rt_normalized() -> None:
    """flu_rt = "+698" → change_rate = Decimal("6.98")."""

    row = StockInvestorBreakdownRow(
        dt="20241107",
        cur_prc="+61300",
        flu_rt="+698",
        ind_invsr="1584",
        frgnr_invsr="-61779",
        orgn="60195",
    )
    normalized = row.to_normalized(
        stock_id=1,
        amt_qty_tp=AmountQuantityType.QUANTITY,
        trade_type=StockInvestorTradeType.NET_BUY,
        unit_tp=UnitType.THOUSAND_SHARES,
        exchange_type=RankingExchangeType.UNIFIED,
    )
    assert normalized.change_rate == Decimal("6.98"), (
        f"flu_rt '+698' → 6.98 기대, 실제: {normalized.change_rate!r}"
    )
    assert normalized.net_individual == 1584
    assert normalized.net_foreign == -61779


# ---------------------------------------------------------------------------
# 13. ContinuousFrgnOrgnRow (ka10131) — to_normalized
# ---------------------------------------------------------------------------


def test_continuous_frgn_orgn_row_to_normalized() -> None:
    """to_normalized — NormalizedFrgnOrgnConsecutive dataclass 반환."""
    from datetime import date

    row = ContinuousFrgnOrgnRow(
        rank="1",
        stk_cd="005930",
        stk_nm="삼성전자",
        prid_stkpc_flu_rt="-5.80",
        orgn_nettrde_amt="+48",
        orgn_nettrde_qty="+173",
        orgn_cont_netprps_dys="+1",
        orgn_cont_netprps_qty="+173",
        orgn_cont_netprps_amt="+48",
        frgnr_nettrde_qty="+0",
        frgnr_nettrde_amt="+0",
        frgnr_cont_netprps_dys="+1",
        frgnr_cont_netprps_qty="+1",
        frgnr_cont_netprps_amt="+0",
        nettrde_qty="+173",
        nettrde_amt="+48",
        tot_cont_netprps_dys="+2",
        tot_cont_nettrde_qty="+174",
        tot_cont_netprps_amt="+48",
    )
    normalized = row.to_normalized(
        stock_id=1,
        as_of_date=date(2026, 5, 16),
        period_type=ContinuousPeriodType.LATEST,
        market_type=InvestorMarketType.KOSPI,
        amt_qty_tp=ContinuousAmtQtyType.AMOUNT,
        stk_inds_tp=StockIndsType.STOCK,
        exchange_type=RankingExchangeType.UNIFIED,
    )
    assert normalized.total_cont_days == 2  # tot_cont_netprps_dys "+2"
    assert normalized.orgn_cont_days == 1
    assert normalized.frgnr_cont_days == 1
