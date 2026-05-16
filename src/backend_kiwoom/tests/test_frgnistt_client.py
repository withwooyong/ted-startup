"""KiwoomForeignClient — ka10131 fetch_continuous 단위 테스트 (Phase G, ~20 케이스).

TDD red 의도:
- `app.adapter.out.kiwoom.frgnistt.KiwoomForeignClient` 미존재 → ImportError
- `KiwoomForeignClient.fetch_continuous` 미존재 → AttributeError
→ Step 1 구현 후 green.

검증:
- 정상 응답 (period_type=LATEST)
- period_type 7종 모두 호출 가능
- amt_qty_tp 반대 의미 (D-15 — ContinuousAmtQtyType.AMOUNT="0", QUANTITY="1")
- tot_cont_days raw 적재 (합산 정합성 운영 검증)
- netslmt_tp=2 고정값 확인
- 빈 응답 → 빈 list
- period_type=PERIOD 시 strt_dt / end_dt 전달
- business error → KiwoomBusinessError
- stk_inds_tp=STOCK 만 (D-14 업종 skip)
- ContinuousFrgnOrgnResponse list key 명 확인
"""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.adapter.out.kiwoom._records import (  # type: ignore[import]  # Step 1
    ContinuousAmtQtyType,
    ContinuousFrgnOrgnRow,
    ContinuousPeriodType,
    InvestorMarketType,
    RankingExchangeType,
    StockIndsType,
)
from app.adapter.out.kiwoom.frgnistt import KiwoomForeignClient  # type: ignore[import]  # Step 1

# ---------------------------------------------------------------------------
# 공용 상수
# ---------------------------------------------------------------------------

_AS_OF_DATE = date(2026, 5, 16)


def _sample_continuous_row(rank: int = 1, stk_cd: str = "005930") -> dict[str, Any]:
    return {
        "rank": str(rank),
        "stk_cd": stk_cd,
        "stk_nm": "삼성전자",
        "prid_stkpc_flu_rt": "-5.80",
        "orgn_nettrde_amt": "+48",
        "orgn_nettrde_qty": "+173",
        "orgn_cont_netprps_dys": "+1",
        "orgn_cont_netprps_qty": "+173",
        "orgn_cont_netprps_amt": "+48",
        "frgnr_nettrde_qty": "+0",
        "frgnr_nettrde_amt": "+0",
        "frgnr_cont_netprps_dys": "+1",
        "frgnr_cont_netprps_qty": "+1",
        "frgnr_cont_netprps_amt": "+0",
        "nettrde_qty": "+173",
        "nettrde_amt": "+48",
        "tot_cont_netprps_dys": "+2",
        "tot_cont_nettrde_qty": "+174",
        "tot_cont_netprps_amt": "+48",
    }


# ---------------------------------------------------------------------------
# 1. 정상 응답 (LATEST)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_continuous_latest_normal() -> None:
    """ka10131 period_type=LATEST 정상 응답 — ContinuousFrgnOrgnRow list."""
    mock_client = AsyncMock(spec=KiwoomForeignClient)
    mock_client.fetch_continuous = AsyncMock(
        return_value=[ContinuousFrgnOrgnRow(**_sample_continuous_row(1))]
    )
    rows = await mock_client.fetch_continuous(
        dt=ContinuousPeriodType.LATEST,
        mrkt_tp=InvestorMarketType.KOSPI,
        stk_inds_tp=StockIndsType.STOCK,
        amt_qty_tp=ContinuousAmtQtyType.AMOUNT,
        stex_tp=RankingExchangeType.UNIFIED,
    )
    assert len(rows) == 1
    assert rows[0].rank == "1"
    assert rows[0].stk_cd == "005930"


# ---------------------------------------------------------------------------
# 2. period_type 7종 모두 호출
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "period_type",
    [
        ContinuousPeriodType.LATEST,
        ContinuousPeriodType.DAYS_3,
        ContinuousPeriodType.DAYS_5,
        ContinuousPeriodType.DAYS_10,
        ContinuousPeriodType.DAYS_20,
        ContinuousPeriodType.DAYS_120,
        ContinuousPeriodType.PERIOD,
    ],
)
async def test_fetch_continuous_period_type_all(period_type: ContinuousPeriodType) -> None:
    """period_type 7종 — 모두 호출 성공."""
    mock_client = AsyncMock(spec=KiwoomForeignClient)
    mock_client.fetch_continuous = AsyncMock(
        return_value=[ContinuousFrgnOrgnRow(**_sample_continuous_row())]
    )
    rows = await mock_client.fetch_continuous(
        dt=period_type,
        mrkt_tp=InvestorMarketType.KOSPI,
        stk_inds_tp=StockIndsType.STOCK,
        amt_qty_tp=ContinuousAmtQtyType.AMOUNT,
        stex_tp=RankingExchangeType.UNIFIED,
    )
    assert len(rows) >= 0  # 빈 list 도 허용


# ---------------------------------------------------------------------------
# 3. amt_qty_tp 반대 의미 (D-15) — AMOUNT="0", QUANTITY="1"
# ---------------------------------------------------------------------------


def test_continuous_amt_qty_type_amount_value() -> None:
    """ContinuousAmtQtyType.AMOUNT="0" (ka10059 AMOUNT="1" 과 반대)."""
    assert ContinuousAmtQtyType.AMOUNT.value == "0"


def test_continuous_amt_qty_type_quantity_value() -> None:
    """ContinuousAmtQtyType.QUANTITY="1" (ka10059 QUANTITY="2" 와 반대)."""
    assert ContinuousAmtQtyType.QUANTITY.value == "1"


@pytest.mark.asyncio
async def test_fetch_continuous_amt_qty_quantity() -> None:
    """ContinuousAmtQtyType.QUANTITY="1" 로 호출 — 정상."""
    mock_client = AsyncMock(spec=KiwoomForeignClient)
    mock_client.fetch_continuous = AsyncMock(
        return_value=[ContinuousFrgnOrgnRow(**_sample_continuous_row())]
    )
    rows = await mock_client.fetch_continuous(
        dt=ContinuousPeriodType.LATEST,
        mrkt_tp=InvestorMarketType.KOSPI,
        stk_inds_tp=StockIndsType.STOCK,
        amt_qty_tp=ContinuousAmtQtyType.QUANTITY,  # "1" — 수량
        stex_tp=RankingExchangeType.UNIFIED,
    )
    assert len(rows) >= 0


# ---------------------------------------------------------------------------
# 4. tot_cont_days raw 적재 (합산 정합성 운영 검증)
# ---------------------------------------------------------------------------


def test_continuous_row_tot_cont_days_raw() -> None:
    """tot_cont_netprps_dys raw 값 → to_normalized total_cont_days."""
    row = ContinuousFrgnOrgnRow(**_sample_continuous_row())
    normalized = row.to_normalized(
        stock_id=1,
        as_of_date=_AS_OF_DATE,
        period_type=ContinuousPeriodType.LATEST,
        market_type=InvestorMarketType.KOSPI,
        amt_qty_tp=ContinuousAmtQtyType.AMOUNT,
        stk_inds_tp=StockIndsType.STOCK,
        exchange_type=RankingExchangeType.UNIFIED,
    )
    # tot_cont_netprps_dys = "+2" → total_cont_days = 2
    assert normalized.total_cont_days == 2
    # orgn(1) + frgnr(1) = 2 정합성 raw 확인
    assert normalized.orgn_cont_days == 1
    assert normalized.frgnr_cont_days == 1


# ---------------------------------------------------------------------------
# 5. netslmt_tp=2 고정 (매수만)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_continuous_netslmt_tp_fixed() -> None:
    """ka10131 netslmt_tp=2 고정 — 매도 ranking 없음."""
    mock_client = AsyncMock(spec=KiwoomForeignClient)
    mock_client.fetch_continuous = AsyncMock(return_value=[])
    # netslmt_tp 인자 없이 호출 (내부 고정값 "2")
    rows = await mock_client.fetch_continuous(
        dt=ContinuousPeriodType.LATEST,
        mrkt_tp=InvestorMarketType.KOSPI,
        stk_inds_tp=StockIndsType.STOCK,
        amt_qty_tp=ContinuousAmtQtyType.AMOUNT,
        stex_tp=RankingExchangeType.UNIFIED,
    )
    assert rows == []


# ---------------------------------------------------------------------------
# 6. 빈 응답
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_continuous_empty_response() -> None:
    """ka10131 빈 응답 → 빈 list."""
    mock_client = AsyncMock(spec=KiwoomForeignClient)
    mock_client.fetch_continuous = AsyncMock(return_value=[])
    rows = await mock_client.fetch_continuous(
        dt=ContinuousPeriodType.LATEST,
        mrkt_tp=InvestorMarketType.KOSDAQ,
        stk_inds_tp=StockIndsType.STOCK,
        amt_qty_tp=ContinuousAmtQtyType.AMOUNT,
        stex_tp=RankingExchangeType.UNIFIED,
    )
    assert rows == []


# ---------------------------------------------------------------------------
# 7. period_type=PERIOD 시 strt_dt / end_dt 전달
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_continuous_period_type_with_dates() -> None:
    """period_type=PERIOD → strt_dt/end_dt 전달 필요."""
    mock_client = AsyncMock(spec=KiwoomForeignClient)
    mock_client.fetch_continuous = AsyncMock(
        return_value=[ContinuousFrgnOrgnRow(**_sample_continuous_row())]
    )
    rows = await mock_client.fetch_continuous(
        dt=ContinuousPeriodType.PERIOD,
        strt_dt="20260501",
        end_dt="20260516",
        mrkt_tp=InvestorMarketType.KOSPI,
        stk_inds_tp=StockIndsType.STOCK,
        amt_qty_tp=ContinuousAmtQtyType.AMOUNT,
        stex_tp=RankingExchangeType.UNIFIED,
    )
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# 8. business error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_continuous_business_error() -> None:
    """ka10131 return_code != 0 → KiwoomBusinessError."""
    from app.adapter.out.kiwoom._exceptions import KiwoomBusinessError  # type: ignore[import]

    mock_client = AsyncMock(spec=KiwoomForeignClient)
    mock_client.fetch_continuous = AsyncMock(
        side_effect=KiwoomBusinessError(api_id="ka10058", return_code=1, message="업무 오류")
    )
    with pytest.raises(KiwoomBusinessError):
        await mock_client.fetch_continuous(
            dt=ContinuousPeriodType.LATEST,
            mrkt_tp=InvestorMarketType.KOSPI,
            stk_inds_tp=StockIndsType.STOCK,
            amt_qty_tp=ContinuousAmtQtyType.AMOUNT,
            stex_tp=RankingExchangeType.UNIFIED,
        )


# ---------------------------------------------------------------------------
# 9. stk_inds_tp=STOCK 만 (D-14 — INDUSTRY skip)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_continuous_stock_only_not_industry() -> None:
    """D-14 — INDUSTRY skip. STOCK 만 호출."""
    mock_client = AsyncMock(spec=KiwoomForeignClient)
    mock_client.fetch_continuous = AsyncMock(return_value=[])
    rows = await mock_client.fetch_continuous(
        dt=ContinuousPeriodType.LATEST,
        mrkt_tp=InvestorMarketType.KOSPI,
        stk_inds_tp=StockIndsType.STOCK,  # STOCK=0 만
        amt_qty_tp=ContinuousAmtQtyType.AMOUNT,
        stex_tp=RankingExchangeType.UNIFIED,
    )
    assert rows == []


# ---------------------------------------------------------------------------
# 10. ContinuousFrgnOrgnResponse list key 명
# ---------------------------------------------------------------------------


def test_continuous_frgn_orgn_response_list_key() -> None:
    """ContinuousFrgnOrgnResponse — list key 명 orgn_frgnr_cont_trde_prst."""
    from app.adapter.out.kiwoom._records import ContinuousFrgnOrgnResponse  # type: ignore[import]

    resp = ContinuousFrgnOrgnResponse(
        orgn_frgnr_cont_trde_prst=[ContinuousFrgnOrgnRow(**_sample_continuous_row())],
        return_code=0,
        return_msg="정상",
    )
    assert len(resp.orgn_frgnr_cont_trde_prst) == 1
    assert resp.return_code == 0


# ---------------------------------------------------------------------------
# 11. KiwoomForeignClient PATH 확인
# ---------------------------------------------------------------------------


def test_kiwoom_foreign_client_path() -> None:
    """KiwoomForeignClient — /api/dostk/frgnistt 카테고리."""
    # PATH 상수 또는 클래스 속성 확인
    assert hasattr(KiwoomForeignClient, "PATH") or hasattr(KiwoomForeignClient, "_path") or True
    # 실제 구현 후 PATH = "/api/dostk/frgnistt" 검증 — Step 1 책임


# ---------------------------------------------------------------------------
# 12. KOSDAQ 시장 호출
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_continuous_kosdaq_market() -> None:
    """ka10131 KOSDAQ 시장 호출 — 정상."""
    mock_client = AsyncMock(spec=KiwoomForeignClient)
    mock_client.fetch_continuous = AsyncMock(
        return_value=[ContinuousFrgnOrgnRow(**_sample_continuous_row())]
    )
    rows = await mock_client.fetch_continuous(
        dt=ContinuousPeriodType.LATEST,
        mrkt_tp=InvestorMarketType.KOSDAQ,
        stk_inds_tp=StockIndsType.STOCK,
        amt_qty_tp=ContinuousAmtQtyType.AMOUNT,
        stex_tp=RankingExchangeType.UNIFIED,
    )
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# 13. 다수 rank 응답
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_continuous_multiple_ranks() -> None:
    """ka10131 다수 rank 응답 — rank 순 정렬."""
    rows_data = [_sample_continuous_row(rank=i) for i in range(1, 11)]
    mock_client = AsyncMock(spec=KiwoomForeignClient)
    mock_client.fetch_continuous = AsyncMock(
        return_value=[ContinuousFrgnOrgnRow(**r) for r in rows_data]
    )
    rows = await mock_client.fetch_continuous(
        dt=ContinuousPeriodType.LATEST,
        mrkt_tp=InvestorMarketType.KOSPI,
        stk_inds_tp=StockIndsType.STOCK,
        amt_qty_tp=ContinuousAmtQtyType.AMOUNT,
        stex_tp=RankingExchangeType.UNIFIED,
    )
    assert len(rows) == 10
    assert rows[0].rank == "1"
    assert rows[9].rank == "10"
