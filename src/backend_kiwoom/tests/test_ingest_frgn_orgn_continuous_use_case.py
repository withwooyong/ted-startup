"""IngestFrgnOrgnConsecutiveUseCase / IngestFrgnOrgnConsecutiveBulkUseCase (Phase G, ~12 케이스).

TDD red 의도:
- `app.application.service.investor_flow_service.IngestFrgnOrgnConsecutiveUseCase` 미존재
- `IngestFrgnOrgnConsecutiveBulkUseCase` 미존재
→ Step 1 구현 후 green.

검증:
- 단건 정상 — fetch → lookup → upsert → FrgnOrgnConsecutiveOutcome
- Bulk 4 호출 (2 mkt × 2 amt_qty — D-10)
- period_type=PERIOD strt/end 전달
- amt_qty_tp 반대 의미 (D-15 ContinuousAmtQtyType)
- Bulk errors_above_threshold tuple
- Bulk 빈 응답 → _empty_bulk_result
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from app.adapter.out.kiwoom._records import (  # type: ignore[import]  # Step 1
    ContinuousAmtQtyType,
    ContinuousFrgnOrgnRow,
    ContinuousPeriodType,
    InvestorMarketType,
    RankingExchangeType,
    StockIndsType,
)
from app.application.dto.investor_flow import (  # type: ignore[import]  # Step 1
    FrgnOrgnConsecutiveBulkResult,
    FrgnOrgnConsecutiveOutcome,
)
from app.application.service.investor_flow_service import (  # type: ignore[import]  # Step 1
    IngestFrgnOrgnConsecutiveBulkUseCase,
    IngestFrgnOrgnConsecutiveUseCase,
)

KST = ZoneInfo("Asia/Seoul")
_NOW = datetime(2026, 5, 16, 21, 0, 0, tzinfo=KST)
_AS_OF_DATE = date(2026, 5, 16)


def _sample_consecutive_row(rank: int = 1) -> ContinuousFrgnOrgnRow:
    return ContinuousFrgnOrgnRow(
        rank=str(rank),
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


def _make_outcome(error: str | None = None) -> FrgnOrgnConsecutiveOutcome:
    return FrgnOrgnConsecutiveOutcome(
        fetched_at=_NOW,
        period_type="1",
        market_type="001",
        amt_qty_tp="0",
        exchange_type="3",
        fetched=0 if error else 100,
        upserted=0 if error else 100,
        error=error,
    )


# ---------------------------------------------------------------------------
# 단건 UseCase 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_frgn_orgn_consecutive_use_case_normal() -> None:
    """단건 정상 — fetch → lookup → upsert → FrgnOrgnConsecutiveOutcome."""
    mock_client = AsyncMock()
    mock_client.fetch_continuous = AsyncMock(
        return_value=[_sample_consecutive_row(1), _sample_consecutive_row(2)]
    )
    mock_repo = AsyncMock()
    mock_repo.upsert_many = AsyncMock(return_value=2)
    mock_stock_repo = AsyncMock()
    mock_stock_repo.find_by_codes = AsyncMock(return_value={"005930": 1})
    mock_session = AsyncMock()

    uc = IngestFrgnOrgnConsecutiveUseCase(
        client=mock_client,
        repository=mock_repo,
        stock_repository=mock_stock_repo,
        session=mock_session,
    )
    outcome = await uc.execute(
        dt=ContinuousPeriodType.LATEST,
        mrkt_tp=InvestorMarketType.KOSPI,
        stk_inds_tp=StockIndsType.STOCK,
        amt_qty_tp=ContinuousAmtQtyType.AMOUNT,
        stex_tp=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
        as_of_date=_AS_OF_DATE,
    )
    assert outcome.upserted == 2
    assert outcome.error is None


@pytest.mark.asyncio
async def test_ingest_frgn_orgn_consecutive_use_case_period_type_period() -> None:
    """period_type=PERIOD → strt_dt/end_dt 전달."""
    mock_client = AsyncMock()
    mock_client.fetch_continuous = AsyncMock(return_value=[_sample_consecutive_row()])
    mock_repo = AsyncMock()
    mock_repo.upsert_many = AsyncMock(return_value=1)
    mock_stock_repo = AsyncMock()
    mock_stock_repo.find_by_codes = AsyncMock(return_value={"005930": 1})
    mock_session = AsyncMock()

    uc = IngestFrgnOrgnConsecutiveUseCase(
        client=mock_client,
        repository=mock_repo,
        stock_repository=mock_stock_repo,
        session=mock_session,
    )
    outcome = await uc.execute(
        dt=ContinuousPeriodType.PERIOD,
        strt_dt="20260501",
        end_dt="20260516",
        mrkt_tp=InvestorMarketType.KOSPI,
        stk_inds_tp=StockIndsType.STOCK,
        amt_qty_tp=ContinuousAmtQtyType.AMOUNT,
        stex_tp=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
        as_of_date=_AS_OF_DATE,
    )
    assert outcome.upserted == 1


@pytest.mark.asyncio
async def test_ingest_frgn_orgn_consecutive_use_case_amt_qty_quantity() -> None:
    """ContinuousAmtQtyType.QUANTITY='1' (D-15 반대 의미) 호출."""
    mock_client = AsyncMock()
    mock_client.fetch_continuous = AsyncMock(return_value=[_sample_consecutive_row()])
    mock_repo = AsyncMock()
    mock_repo.upsert_many = AsyncMock(return_value=1)
    mock_stock_repo = AsyncMock()
    mock_stock_repo.find_by_codes = AsyncMock(return_value={"005930": 1})
    mock_session = AsyncMock()

    uc = IngestFrgnOrgnConsecutiveUseCase(
        client=mock_client,
        repository=mock_repo,
        stock_repository=mock_stock_repo,
        session=mock_session,
    )
    outcome = await uc.execute(
        dt=ContinuousPeriodType.LATEST,
        mrkt_tp=InvestorMarketType.KOSPI,
        stk_inds_tp=StockIndsType.STOCK,
        amt_qty_tp=ContinuousAmtQtyType.QUANTITY,  # "1" = 수량
        stex_tp=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
        as_of_date=_AS_OF_DATE,
    )
    assert outcome.upserted == 1


@pytest.mark.asyncio
async def test_ingest_frgn_orgn_consecutive_use_case_empty_response() -> None:
    """단건 빈 응답 → outcome.upserted = 0."""
    mock_client = AsyncMock()
    mock_client.fetch_continuous = AsyncMock(return_value=[])
    mock_repo = AsyncMock()
    mock_repo.upsert_many = AsyncMock(return_value=0)
    mock_stock_repo = AsyncMock()
    mock_session = AsyncMock()

    uc = IngestFrgnOrgnConsecutiveUseCase(
        client=mock_client,
        repository=mock_repo,
        stock_repository=mock_stock_repo,
        session=mock_session,
    )
    outcome = await uc.execute(
        dt=ContinuousPeriodType.LATEST,
        mrkt_tp=InvestorMarketType.KOSPI,
        stk_inds_tp=StockIndsType.STOCK,
        amt_qty_tp=ContinuousAmtQtyType.AMOUNT,
        stex_tp=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
        as_of_date=_AS_OF_DATE,
    )
    assert outcome.upserted == 0


@pytest.mark.asyncio
async def test_ingest_frgn_orgn_consecutive_use_case_business_error() -> None:
    """단건 KiwoomBusinessError → outcome.error."""
    from app.adapter.out.kiwoom._exceptions import KiwoomBusinessError  # type: ignore[import]

    mock_client = AsyncMock()
    mock_client.fetch_continuous = AsyncMock(
        side_effect=KiwoomBusinessError(api_id="ka10058", return_code=1, message="업무 오류")
    )
    mock_repo = AsyncMock()
    mock_stock_repo = AsyncMock()
    mock_session = AsyncMock()

    uc = IngestFrgnOrgnConsecutiveUseCase(
        client=mock_client,
        repository=mock_repo,
        stock_repository=mock_stock_repo,
        session=mock_session,
    )
    outcome = await uc.execute(
        dt=ContinuousPeriodType.LATEST,
        mrkt_tp=InvestorMarketType.KOSPI,
        stk_inds_tp=StockIndsType.STOCK,
        amt_qty_tp=ContinuousAmtQtyType.AMOUNT,
        stex_tp=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
        as_of_date=_AS_OF_DATE,
    )
    assert outcome.error is not None
    assert outcome.upserted == 0


# ---------------------------------------------------------------------------
# Bulk UseCase 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_frgn_orgn_consecutive_bulk_use_case_4_calls() -> None:
    """Bulk 4 호출 (2 mkt × 2 amt_qty — D-10)."""
    mock_single_uc = AsyncMock(spec=IngestFrgnOrgnConsecutiveUseCase)
    mock_single_uc.execute = AsyncMock(side_effect=lambda **kw: _make_outcome())

    bulk_uc = IngestFrgnOrgnConsecutiveBulkUseCase(single_use_case=mock_single_uc)
    result = await bulk_uc.execute(
        dt=ContinuousPeriodType.LATEST,
        market_types=[InvestorMarketType.KOSPI, InvestorMarketType.KOSDAQ],
        amt_qty_types=[ContinuousAmtQtyType.AMOUNT, ContinuousAmtQtyType.QUANTITY],
        stk_inds_tp=StockIndsType.STOCK,
        stex_tp=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
        as_of_date=_AS_OF_DATE,
    )
    assert isinstance(result, FrgnOrgnConsecutiveBulkResult)
    assert result.total_calls == 4  # 2 × 2


@pytest.mark.asyncio
async def test_ingest_frgn_orgn_consecutive_bulk_use_case_errors_above_threshold() -> None:
    """Bulk errors_above_threshold tuple — D-11 임계치 미도입, 기본 빈 tuple."""
    mock_single_uc = AsyncMock(spec=IngestFrgnOrgnConsecutiveUseCase)
    mock_single_uc.execute = AsyncMock(side_effect=lambda **kw: _make_outcome())

    bulk_uc = IngestFrgnOrgnConsecutiveBulkUseCase(single_use_case=mock_single_uc)
    result = await bulk_uc.execute(
        dt=ContinuousPeriodType.LATEST,
        market_types=[InvestorMarketType.KOSPI],
        amt_qty_types=[ContinuousAmtQtyType.AMOUNT],
        stk_inds_tp=StockIndsType.STOCK,
        stex_tp=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
        as_of_date=_AS_OF_DATE,
    )
    assert isinstance(result.errors_above_threshold, tuple)
    assert result.errors_above_threshold == ()


@pytest.mark.asyncio
async def test_ingest_frgn_orgn_consecutive_bulk_use_case_empty_matrix() -> None:
    """빈 매트릭스 → _empty_bulk_result."""
    mock_single_uc = AsyncMock(spec=IngestFrgnOrgnConsecutiveUseCase)

    bulk_uc = IngestFrgnOrgnConsecutiveBulkUseCase(single_use_case=mock_single_uc)
    result = await bulk_uc.execute(
        dt=ContinuousPeriodType.LATEST,
        market_types=[],
        amt_qty_types=[],
        stk_inds_tp=StockIndsType.STOCK,
        stex_tp=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
        as_of_date=_AS_OF_DATE,
    )
    assert result.total_calls == 0
    assert result.total_upserted == 0


@pytest.mark.asyncio
async def test_ingest_frgn_orgn_consecutive_bulk_use_case_partial_failure() -> None:
    """Bulk 일부 실패 → 나머지 진행."""
    call_count = 0

    def _execute(**kwargs: Any) -> FrgnOrgnConsecutiveOutcome:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _make_outcome(error="timeout")
        return _make_outcome()

    mock_single_uc = AsyncMock(spec=IngestFrgnOrgnConsecutiveUseCase)
    mock_single_uc.execute = _execute

    bulk_uc = IngestFrgnOrgnConsecutiveBulkUseCase(single_use_case=mock_single_uc)
    result = await bulk_uc.execute(
        dt=ContinuousPeriodType.LATEST,
        market_types=[InvestorMarketType.KOSPI, InvestorMarketType.KOSDAQ],
        amt_qty_types=[ContinuousAmtQtyType.AMOUNT],
        stk_inds_tp=StockIndsType.STOCK,
        stex_tp=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
        as_of_date=_AS_OF_DATE,
    )
    assert result.total_calls == 2
    assert result.total_failed >= 1
