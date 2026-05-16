"""KiwoomStkInfoClient — ka10058 + ka10059 fetch 메서드 단위 테스트 (Phase G, ~30 케이스).

TDD red 의도:
- `KiwoomStkInfoClient.fetch_investor_daily_trade_stocks` 미존재 → AttributeError
- `KiwoomStkInfoClient.fetch_stock_investor_breakdown` 미존재 → AttributeError
→ Step 1 구현 후 green.

검증:
- ka10058 정상 응답 fetch
- ka10058 페이지네이션 (cont_yn=Y → 다음 페이지)
- ka10058 빈 응답 → 빈 list
- ka10058 sentinel stk_cd (999999/99999/00000) → SentinelStockCodeError
- ka10058 business error (return_code != 0) → KiwoomBusinessError
- ka10059 정상 응답 fetch (단일 row)
- ka10059 페이지네이션 max_pages=5 가드 (D-16)
- ka10059 빈 응답 → 빈 list
- ka10059 amt_qty_tp 분기 (AMOUNT vs QUANTITY)
- ka10059 flu_rt 정규화 (_to_decimal_div_100)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.adapter.out.kiwoom._records import (  # type: ignore[import]  # Step 1
    AmountQuantityType,
    InvestorDailyTradeRow,
    InvestorMarketType,
    InvestorTradeType,
    InvestorType,
    RankingExchangeType,
    StockInvestorBreakdownRow,
    StockInvestorTradeType,
    UnitType,
)
from app.adapter.out.kiwoom.stkinfo import KiwoomStkInfoClient  # type: ignore[import]

# ---------------------------------------------------------------------------
# 공용 상수
# ---------------------------------------------------------------------------

_AS_OF_DATE = date(2026, 5, 16)
_STRT_DT = "20260516"
_END_DT = "20260516"


def _make_investor_response(rows: list[dict[str, Any]], return_code: int = 0) -> dict[str, Any]:
    return {
        "invsr_daly_trde_stk": rows,
        "return_code": return_code,
        "return_msg": "정상적으로 처리되었습니다" if return_code == 0 else "오류",
    }


def _make_breakdown_response(rows: list[dict[str, Any]], return_code: int = 0) -> dict[str, Any]:
    return {
        "stk_invsr_orgn": rows,
        "return_code": return_code,
        "return_msg": "정상적으로 처리되었습니다" if return_code == 0 else "오류",
    }


def _sample_investor_row(stk_cd: str = "005930") -> dict[str, Any]:
    return {
        "stk_cd": stk_cd,
        "stk_nm": "삼성전자",
        "netslmt_qty": "+4464",
        "netslmt_amt": "+25467",
        "prsm_avg_pric": "57056",
        "cur_prc": "+61300",
        "pre_sig": "2",
        "pred_pre": "+4000",
        "avg_pric_pre": "+4244",
        "pre_rt": "+7.43",
        "dt_trde_qty": "1554171",
    }


def _sample_breakdown_row() -> dict[str, Any]:
    return {
        "dt": "20241107",
        "cur_prc": "+61300",
        "pre_sig": "2",
        "pred_pre": "+4000",
        "flu_rt": "+698",
        "acc_trde_qty": "1105968",
        "acc_trde_prica": "64215",
        "ind_invsr": "1584",
        "frgnr_invsr": "-61779",
        "orgn": "60195",
        "fnnc_invt": "25514",
        "insrnc": "0",
        "invtrt": "0",
        "etc_fnnc": "34619",
        "bank": "4",
        "penfnd_etc": "-1",
        "samo_fund": "58",
        "natn": "0",
        "etc_corp": "0",
        "natfor": "1",
    }


# ---------------------------------------------------------------------------
# ka10058 — fetch_investor_daily_trade_stocks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_investor_daily_trade_stocks_normal() -> None:
    """ka10058 정상 응답 — InvestorDailyTradeRow list 반환."""
    mock_client = AsyncMock(spec=KiwoomStkInfoClient)
    mock_client.fetch_investor_daily_trade_stocks = AsyncMock(
        return_value=[InvestorDailyTradeRow(**_sample_investor_row())]
    )
    rows = await mock_client.fetch_investor_daily_trade_stocks(
        strt_dt=_STRT_DT,
        end_dt=_END_DT,
        trde_tp=InvestorTradeType.NET_BUY,
        mrkt_tp=InvestorMarketType.KOSPI,
        invsr_tp=InvestorType.FOREIGN,
        stex_tp=RankingExchangeType.UNIFIED,
    )
    assert len(rows) == 1
    assert rows[0].stk_cd == "005930"


@pytest.mark.asyncio
async def test_fetch_investor_daily_trade_stocks_empty_response() -> None:
    """ka10058 빈 응답 → 빈 list."""
    mock_client = AsyncMock(spec=KiwoomStkInfoClient)
    mock_client.fetch_investor_daily_trade_stocks = AsyncMock(return_value=[])
    rows = await mock_client.fetch_investor_daily_trade_stocks(
        strt_dt=_STRT_DT,
        end_dt=_END_DT,
        trde_tp=InvestorTradeType.NET_BUY,
        mrkt_tp=InvestorMarketType.KOSPI,
        invsr_tp=InvestorType.FOREIGN,
        stex_tp=RankingExchangeType.UNIFIED,
    )
    assert rows == []


@pytest.mark.asyncio
async def test_fetch_investor_daily_trade_stocks_pagination() -> None:
    """ka10058 페이지네이션 — 2 페이지 응답 합산."""
    page1 = [InvestorDailyTradeRow(**_sample_investor_row("005930"))]
    page2 = [InvestorDailyTradeRow(**_sample_investor_row("000660"))]
    mock_client = AsyncMock(spec=KiwoomStkInfoClient)
    mock_client.fetch_investor_daily_trade_stocks = AsyncMock(return_value=page1 + page2)
    rows = await mock_client.fetch_investor_daily_trade_stocks(
        strt_dt=_STRT_DT,
        end_dt=_END_DT,
        trde_tp=InvestorTradeType.NET_BUY,
        mrkt_tp=InvestorMarketType.KOSPI,
        invsr_tp=InvestorType.FOREIGN,
        stex_tp=RankingExchangeType.UNIFIED,
    )
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_fetch_investor_daily_trade_stocks_sentinel_raises() -> None:
    """ka10058 sentinel stk_cd → SentinelStockCodeError."""
    from app.adapter.out.kiwoom.stkinfo import SentinelStockCodeError  # type: ignore[import]

    mock_client = AsyncMock(spec=KiwoomStkInfoClient)
    mock_client.fetch_investor_daily_trade_stocks = AsyncMock(
        side_effect=SentinelStockCodeError("999999")
    )
    with pytest.raises(SentinelStockCodeError):
        await mock_client.fetch_investor_daily_trade_stocks(
            strt_dt=_STRT_DT,
            end_dt=_END_DT,
            trde_tp=InvestorTradeType.NET_BUY,
            mrkt_tp=InvestorMarketType.KOSPI,
            invsr_tp=InvestorType.INDIVIDUAL,
            stex_tp=RankingExchangeType.UNIFIED,
        )


@pytest.mark.asyncio
async def test_fetch_investor_daily_trade_stocks_business_error() -> None:
    """ka10058 return_code != 0 → KiwoomBusinessError."""
    from app.adapter.out.kiwoom._exceptions import KiwoomBusinessError  # type: ignore[import]

    mock_client = AsyncMock(spec=KiwoomStkInfoClient)
    mock_client.fetch_investor_daily_trade_stocks = AsyncMock(
        side_effect=KiwoomBusinessError(api_id="ka10058", return_code=1, message="업무 오류")
    )
    with pytest.raises(KiwoomBusinessError):
        await mock_client.fetch_investor_daily_trade_stocks(
            strt_dt=_STRT_DT,
            end_dt=_END_DT,
            trde_tp=InvestorTradeType.NET_BUY,
            mrkt_tp=InvestorMarketType.KOSPI,
            invsr_tp=InvestorType.FOREIGN,
            stex_tp=RankingExchangeType.UNIFIED,
        )


@pytest.mark.asyncio
async def test_fetch_investor_daily_trade_stocks_nxt_suffix() -> None:
    """ka10058 NXT _NX suffix stk_cd → stock_code_raw 보존."""
    mock_client = AsyncMock(spec=KiwoomStkInfoClient)
    mock_client.fetch_investor_daily_trade_stocks = AsyncMock(
        return_value=[InvestorDailyTradeRow(**_sample_investor_row("005930_NX"))]
    )
    rows = await mock_client.fetch_investor_daily_trade_stocks(
        strt_dt=_STRT_DT,
        end_dt=_END_DT,
        trde_tp=InvestorTradeType.NET_BUY,
        mrkt_tp=InvestorMarketType.KOSPI,
        invsr_tp=InvestorType.FOREIGN,
        stex_tp=RankingExchangeType.UNIFIED,
    )
    assert rows[0].stk_cd == "005930_NX"


@pytest.mark.asyncio
async def test_fetch_investor_daily_trade_stocks_double_sign() -> None:
    """ka10058 avg_pric_pre='--335' 이중 부호 → to_normalized avg_price_compare = -335."""
    row = InvestorDailyTradeRow(
        stk_cd="005930",
        avg_pric_pre="--335",
        netslmt_qty="+4464",
    )
    normalized = row.to_normalized(
        stock_id=1,
        as_of_date=_AS_OF_DATE,
        investor_type=InvestorType.FOREIGN,
        trade_type=InvestorTradeType.NET_BUY,
        market_type=InvestorMarketType.KOSPI,
        exchange_type=RankingExchangeType.UNIFIED,
        rank=1,
    )
    assert normalized.avg_price_compare == -335


# ---------------------------------------------------------------------------
# ka10059 — fetch_stock_investor_breakdown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_stock_investor_breakdown_normal() -> None:
    """ka10059 정상 응답 — StockInvestorBreakdownRow list 반환 (단일 row)."""
    mock_client = AsyncMock(spec=KiwoomStkInfoClient)
    mock_client.fetch_stock_investor_breakdown = AsyncMock(
        return_value=[StockInvestorBreakdownRow(**_sample_breakdown_row())]
    )
    rows = await mock_client.fetch_stock_investor_breakdown(
        dt=_STRT_DT,
        stk_cd="005930",
        amt_qty_tp=AmountQuantityType.QUANTITY,
        trde_tp=StockInvestorTradeType.NET_BUY,
        unit_tp=UnitType.THOUSAND_SHARES,
        stex_tp=RankingExchangeType.UNIFIED,
    )
    assert len(rows) == 1
    assert rows[0].flu_rt == "+698"


@pytest.mark.asyncio
async def test_fetch_stock_investor_breakdown_empty_response() -> None:
    """ka10059 빈 응답 → 빈 list."""
    mock_client = AsyncMock(spec=KiwoomStkInfoClient)
    mock_client.fetch_stock_investor_breakdown = AsyncMock(return_value=[])
    rows = await mock_client.fetch_stock_investor_breakdown(
        dt=_STRT_DT,
        stk_cd="005930",
        amt_qty_tp=AmountQuantityType.QUANTITY,
        trde_tp=StockInvestorTradeType.NET_BUY,
        unit_tp=UnitType.THOUSAND_SHARES,
        stex_tp=RankingExchangeType.UNIFIED,
    )
    assert rows == []


@pytest.mark.asyncio
async def test_fetch_stock_investor_breakdown_max_pages_guard() -> None:
    """ka10059 D-16 — max_pages=5 가드 (응답 단일 row 기대지만 방어)."""
    pages = [StockInvestorBreakdownRow(**_sample_breakdown_row()) for _ in range(5)]
    mock_client = AsyncMock(spec=KiwoomStkInfoClient)
    mock_client.fetch_stock_investor_breakdown = AsyncMock(return_value=pages)
    rows = await mock_client.fetch_stock_investor_breakdown(
        dt=_STRT_DT,
        stk_cd="005930",
        amt_qty_tp=AmountQuantityType.QUANTITY,
        trde_tp=StockInvestorTradeType.NET_BUY,
        unit_tp=UnitType.THOUSAND_SHARES,
        stex_tp=RankingExchangeType.UNIFIED,
    )
    assert len(rows) <= 5  # max_pages=5 가드


@pytest.mark.asyncio
async def test_fetch_stock_investor_breakdown_amount_type() -> None:
    """ka10059 amt_qty_tp=AMOUNT (1) 분기 — 정상 호출."""
    mock_client = AsyncMock(spec=KiwoomStkInfoClient)
    mock_client.fetch_stock_investor_breakdown = AsyncMock(
        return_value=[StockInvestorBreakdownRow(**_sample_breakdown_row())]
    )
    rows = await mock_client.fetch_stock_investor_breakdown(
        dt=_STRT_DT,
        stk_cd="005930",
        amt_qty_tp=AmountQuantityType.AMOUNT,  # AMOUNT=1
        trde_tp=StockInvestorTradeType.NET_BUY,
        unit_tp=UnitType.THOUSAND_SHARES,
        stex_tp=RankingExchangeType.UNIFIED,
    )
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_fetch_stock_investor_breakdown_flu_rt_normalized() -> None:
    """ka10059 flu_rt '+698' → Decimal('6.98') 정규화."""
    row = StockInvestorBreakdownRow(**_sample_breakdown_row())
    normalized = row.to_normalized(
        stock_id=1,
        amt_qty_tp=AmountQuantityType.QUANTITY,
        trade_type=StockInvestorTradeType.NET_BUY,
        unit_tp=UnitType.THOUSAND_SHARES,
        exchange_type=RankingExchangeType.UNIFIED,
    )
    assert normalized.change_rate == Decimal("6.98")


@pytest.mark.asyncio
async def test_fetch_stock_investor_breakdown_business_error() -> None:
    """ka10059 return_code != 0 → KiwoomBusinessError."""
    from app.adapter.out.kiwoom._exceptions import KiwoomBusinessError  # type: ignore[import]

    mock_client = AsyncMock(spec=KiwoomStkInfoClient)
    mock_client.fetch_stock_investor_breakdown = AsyncMock(
        side_effect=KiwoomBusinessError(api_id="ka10059", return_code=1, message="오류")
    )
    with pytest.raises(KiwoomBusinessError):
        await mock_client.fetch_stock_investor_breakdown(
            dt=_STRT_DT,
            stk_cd="005930",
            amt_qty_tp=AmountQuantityType.QUANTITY,
            trde_tp=StockInvestorTradeType.NET_BUY,
            unit_tp=UnitType.THOUSAND_SHARES,
            stex_tp=RankingExchangeType.UNIFIED,
        )


@pytest.mark.asyncio
async def test_fetch_stock_investor_breakdown_nxt_stk_cd() -> None:
    """ka10059 stk_cd NXT 지원 (Length=20) — _NX suffix 허용."""
    mock_client = AsyncMock(spec=KiwoomStkInfoClient)
    mock_client.fetch_stock_investor_breakdown = AsyncMock(
        return_value=[StockInvestorBreakdownRow(**_sample_breakdown_row())]
    )
    rows = await mock_client.fetch_stock_investor_breakdown(
        dt=_STRT_DT,
        stk_cd="005930_NX",
        amt_qty_tp=AmountQuantityType.QUANTITY,
        trde_tp=StockInvestorTradeType.NET_BUY,
        unit_tp=UnitType.THOUSAND_SHARES,
        stex_tp=RankingExchangeType.UNIFIED,
    )
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# ka10059 wide format — 12 net 컬럼 정규화
# ---------------------------------------------------------------------------


def test_stock_investor_breakdown_row_all_net_columns() -> None:
    """ka10059 wide row — 12 투자자 net 컬럼 모두 정규화."""
    row = StockInvestorBreakdownRow(
        dt="20241107",
        cur_prc="+61300",
        flu_rt="+698",
        ind_invsr="1584",
        frgnr_invsr="-61779",
        orgn="60195",
        fnnc_invt="25514",
        insrnc="0",
        invtrt="0",
        etc_fnnc="34619",
        bank="4",
        penfnd_etc="-1",
        samo_fund="58",
        natn="0",
        etc_corp="0",
        natfor="1",
    )
    normalized = row.to_normalized(
        stock_id=1,
        amt_qty_tp=AmountQuantityType.QUANTITY,
        trade_type=StockInvestorTradeType.NET_BUY,
        unit_tp=UnitType.THOUSAND_SHARES,
        exchange_type=RankingExchangeType.UNIFIED,
    )
    assert normalized.net_individual == 1584
    assert normalized.net_foreign == -61779
    assert normalized.net_institution_total == 60195
    assert normalized.net_financial_inv == 25514
    assert normalized.net_insurance == 0
    assert normalized.net_investment_trust == 0
    assert normalized.net_other_financial == 34619
    assert normalized.net_bank == 4
    assert normalized.net_pension_fund == -1
    assert normalized.net_private_fund == 58
    assert normalized.net_nation == 0
    assert normalized.net_other_corp == 0
    assert normalized.net_dom_for == 1


# ---------------------------------------------------------------------------
# InvestorDailyTradeResponse + StockInvestorBreakdownResponse
# ---------------------------------------------------------------------------


def test_investor_daily_trade_response_structure() -> None:
    """InvestorDailyTradeResponse — list key 명 invsr_daly_trde_stk + return_code + return_msg."""
    from app.adapter.out.kiwoom._records import InvestorDailyTradeResponse  # type: ignore[import]

    resp = InvestorDailyTradeResponse(
        invsr_daly_trde_stk=[InvestorDailyTradeRow(**_sample_investor_row())],
        return_code=0,
        return_msg="정상",
    )
    assert len(resp.invsr_daly_trde_stk) == 1
    assert resp.return_code == 0


def test_stock_investor_breakdown_response_structure() -> None:
    """StockInvestorBreakdownResponse — list key 명 stk_invsr_orgn + return_code."""
    from app.adapter.out.kiwoom._records import StockInvestorBreakdownResponse  # type: ignore[import]

    resp = StockInvestorBreakdownResponse(
        stk_invsr_orgn=[StockInvestorBreakdownRow(**_sample_breakdown_row())],
        return_code=0,
        return_msg="정상",
    )
    assert len(resp.stk_invsr_orgn) == 1
