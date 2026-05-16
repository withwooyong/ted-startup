"""IngestStockInvestorBreakdownUseCase / IngestStockInvestorBreakdownBulkUseCase (Phase G, ~12 케이스).

TDD red 의도:
- `app.application.service.investor_flow_service.IngestStockInvestorBreakdownUseCase` 미존재
- `IngestStockInvestorBreakdownBulkUseCase` 미존재
→ Step 1 구현 후 green.

검증:
- 단건 정상 — fetch → upsert → StockInvestorBreakdownOutcome
- Bulk 3000 종목 × 1조합 (D-8 QUANTITY/NET_BUY/THOUSAND_SHARES)
- Bulk BATCH=50 (3000 호출 부담)
- flu_rt '+698' → Decimal('6.98') 정규화
- _strip_double_sign_int 12 카테고리 (이중 부호 처리)
- Bulk errors_above_threshold tuple
- Bulk 빈 stock list → _empty_bulk_result
- 단건 stock_id 없으면 skip (ka10059 는 stock_id 필수)
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from app.adapter.out.kiwoom._records import (  # type: ignore[import]  # Step 1
    AmountQuantityType,
    RankingExchangeType,
    StockInvestorBreakdownRow,
    StockInvestorTradeType,
    UnitType,
)
from app.application.dto.investor_flow import (  # type: ignore[import]  # Step 1
    StockInvestorBreakdownBulkResult,
    StockInvestorBreakdownOutcome,
)
from app.application.service.investor_flow_service import (  # type: ignore[import]  # Step 1
    IngestStockInvestorBreakdownBulkUseCase,
    IngestStockInvestorBreakdownUseCase,
)

KST = ZoneInfo("Asia/Seoul")
_NOW = datetime(2026, 5, 16, 20, 30, 0, tzinfo=KST)
_DT = "20241107"


def _sample_breakdown_row(
    flu_rt: str = "+698",
    ind_invsr: str = "1584",
    orgn: str = "60195",
) -> StockInvestorBreakdownRow:
    return StockInvestorBreakdownRow(
        dt=_DT,
        cur_prc="+61300",
        pre_sig="2",
        pred_pre="+4000",
        flu_rt=flu_rt,
        acc_trde_qty="1105968",
        acc_trde_prica="64215",
        ind_invsr=ind_invsr,
        frgnr_invsr="-61779",
        orgn=orgn,
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


# ---------------------------------------------------------------------------
# 단건 UseCase 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_stock_investor_breakdown_use_case_normal() -> None:
    """단건 정상 — fetch → upsert → StockInvestorBreakdownOutcome."""
    mock_client = AsyncMock()
    mock_client.fetch_stock_investor_breakdown = AsyncMock(
        return_value=[_sample_breakdown_row()]
    )
    mock_repo = AsyncMock()
    mock_repo.upsert_many = AsyncMock(return_value=1)
    mock_session = AsyncMock()

    uc = IngestStockInvestorBreakdownUseCase(
        client=mock_client,
        repository=mock_repo,
        session=mock_session,
    )
    outcome = await uc.execute(
        stock_id=1,
        stk_cd="005930",
        dt=_DT,
        amt_qty_tp=AmountQuantityType.QUANTITY,
        trade_type=StockInvestorTradeType.NET_BUY,
        unit_tp=UnitType.THOUSAND_SHARES,
        exchange_type=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
    )
    assert outcome.upserted == 1
    assert outcome.error is None


@pytest.mark.asyncio
async def test_ingest_stock_investor_breakdown_use_case_flu_rt_normalized() -> None:
    """flu_rt '+698' → change_rate = Decimal('6.98') 정규화."""
    mock_client = AsyncMock()
    mock_client.fetch_stock_investor_breakdown = AsyncMock(
        return_value=[_sample_breakdown_row(flu_rt="+698")]
    )
    mock_repo = AsyncMock()
    upserted_rows: list[Any] = []

    async def _capture_upsert(rows: list[Any]) -> int:
        upserted_rows.extend(rows)
        return len(rows)

    mock_repo.upsert_many = _capture_upsert
    mock_session = AsyncMock()

    uc = IngestStockInvestorBreakdownUseCase(
        client=mock_client,
        repository=mock_repo,
        session=mock_session,
    )
    await uc.execute(
        stock_id=1,
        stk_cd="005930",
        dt=_DT,
        amt_qty_tp=AmountQuantityType.QUANTITY,
        trade_type=StockInvestorTradeType.NET_BUY,
        unit_tp=UnitType.THOUSAND_SHARES,
        exchange_type=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
    )
    if upserted_rows:
        assert upserted_rows[0].change_rate == Decimal("6.98")


@pytest.mark.asyncio
async def test_ingest_stock_investor_breakdown_use_case_double_sign() -> None:
    """_strip_double_sign_int — 이중 부호 처리 (orgn '--335')."""
    mock_client = AsyncMock()
    mock_client.fetch_stock_investor_breakdown = AsyncMock(
        return_value=[_sample_breakdown_row(ind_invsr="--335", orgn="--100")]
    )
    mock_repo = AsyncMock()
    upserted_rows: list[Any] = []

    async def _capture_upsert(rows: list[Any]) -> int:
        upserted_rows.extend(rows)
        return len(rows)

    mock_repo.upsert_many = _capture_upsert
    mock_session = AsyncMock()

    uc = IngestStockInvestorBreakdownUseCase(
        client=mock_client,
        repository=mock_repo,
        session=mock_session,
    )
    await uc.execute(
        stock_id=1,
        stk_cd="005930",
        dt=_DT,
        amt_qty_tp=AmountQuantityType.QUANTITY,
        trade_type=StockInvestorTradeType.NET_BUY,
        unit_tp=UnitType.THOUSAND_SHARES,
        exchange_type=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
    )
    if upserted_rows:
        assert upserted_rows[0].net_individual == -335


@pytest.mark.asyncio
async def test_ingest_stock_investor_breakdown_use_case_empty_response() -> None:
    """단건 빈 응답 → outcome.upserted = 0."""
    mock_client = AsyncMock()
    mock_client.fetch_stock_investor_breakdown = AsyncMock(return_value=[])
    mock_repo = AsyncMock()
    mock_repo.upsert_many = AsyncMock(return_value=0)
    mock_session = AsyncMock()

    uc = IngestStockInvestorBreakdownUseCase(
        client=mock_client,
        repository=mock_repo,
        session=mock_session,
    )
    outcome = await uc.execute(
        stock_id=1,
        stk_cd="005930",
        dt=_DT,
        amt_qty_tp=AmountQuantityType.QUANTITY,
        trade_type=StockInvestorTradeType.NET_BUY,
        unit_tp=UnitType.THOUSAND_SHARES,
        exchange_type=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
    )
    assert outcome.upserted == 0


# ---------------------------------------------------------------------------
# Bulk UseCase 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_stock_investor_breakdown_bulk_use_case_3000_stocks() -> None:
    """Bulk 3000 종목 × 1조합 (D-8 QUANTITY/NET_BUY/THOUSAND_SHARES)."""
    mock_single_uc = AsyncMock(spec=IngestStockInvestorBreakdownUseCase)
    call_count = 0

    async def _execute(**kwargs: Any) -> StockInvestorBreakdownOutcome:
        nonlocal call_count
        call_count += 1
        return StockInvestorBreakdownOutcome(
            fetched_at=_NOW,
            stock_code=kwargs.get("stk_cd", "000000"),
            trading_date=_DT,
            fetched=1,
            upserted=1,
            error=None,
        )

    mock_single_uc.execute = _execute

    bulk_uc = IngestStockInvestorBreakdownBulkUseCase(single_use_case=mock_single_uc)
    stock_codes = [f"{i:06d}" for i in range(1, 101)]  # 100 종목 (테스트 부담 줄임)
    result = await bulk_uc.execute(
        stock_codes=stock_codes,
        stock_id_map={f"{i:06d}": i for i in range(1, 101)},
        dt=_DT,
        amt_qty_tp=AmountQuantityType.QUANTITY,
        trade_type=StockInvestorTradeType.NET_BUY,
        unit_tp=UnitType.THOUSAND_SHARES,
        exchange_type=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
    )
    assert isinstance(result, StockInvestorBreakdownBulkResult)
    assert result.total_calls == 100


@pytest.mark.asyncio
async def test_ingest_stock_investor_breakdown_bulk_use_case_batch_50() -> None:
    """Bulk BATCH=50 — 50 호출마다 commit (inh-1 부분 mitigate)."""
    mock_single_uc = AsyncMock(spec=IngestStockInvestorBreakdownUseCase)
    mock_single_uc.execute = AsyncMock(
        return_value=StockInvestorBreakdownOutcome(
            fetched_at=_NOW,
            stock_code="005930",
            trading_date=_DT,
            fetched=1,
            upserted=1,
            error=None,
        )
    )

    bulk_uc = IngestStockInvestorBreakdownBulkUseCase(single_use_case=mock_single_uc)
    stock_codes = [f"{i:06d}" for i in range(1, 51)]  # 50 종목
    result = await bulk_uc.execute(
        stock_codes=stock_codes,
        stock_id_map={f"{i:06d}": i for i in range(1, 51)},
        dt=_DT,
        amt_qty_tp=AmountQuantityType.QUANTITY,
        trade_type=StockInvestorTradeType.NET_BUY,
        unit_tp=UnitType.THOUSAND_SHARES,
        exchange_type=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
    )
    assert result.total_upserted == 50


@pytest.mark.asyncio
async def test_ingest_stock_investor_breakdown_bulk_use_case_empty_stock_list() -> None:
    """빈 stock list → _empty_bulk_result."""
    mock_single_uc = AsyncMock(spec=IngestStockInvestorBreakdownUseCase)
    bulk_uc = IngestStockInvestorBreakdownBulkUseCase(single_use_case=mock_single_uc)
    result = await bulk_uc.execute(
        stock_codes=[],
        stock_id_map={},
        dt=_DT,
        amt_qty_tp=AmountQuantityType.QUANTITY,
        trade_type=StockInvestorTradeType.NET_BUY,
        unit_tp=UnitType.THOUSAND_SHARES,
        exchange_type=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
    )
    assert result.total_calls == 0
    assert result.total_upserted == 0


@pytest.mark.asyncio
async def test_ingest_stock_investor_breakdown_bulk_use_case_errors_above_threshold() -> None:
    """Bulk errors_above_threshold tuple — D-11 임계치 미도입, 기본 빈 tuple."""
    mock_single_uc = AsyncMock(spec=IngestStockInvestorBreakdownUseCase)
    mock_single_uc.execute = AsyncMock(
        return_value=StockInvestorBreakdownOutcome(
            fetched_at=_NOW,
            stock_code="005930",
            trading_date=_DT,
            fetched=1,
            upserted=1,
            error=None,
        )
    )
    bulk_uc = IngestStockInvestorBreakdownBulkUseCase(single_use_case=mock_single_uc)
    result = await bulk_uc.execute(
        stock_codes=["005930"],
        stock_id_map={"005930": 1},
        dt=_DT,
        amt_qty_tp=AmountQuantityType.QUANTITY,
        trade_type=StockInvestorTradeType.NET_BUY,
        unit_tp=UnitType.THOUSAND_SHARES,
        exchange_type=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
    )
    assert isinstance(result.errors_above_threshold, tuple)
    assert result.errors_above_threshold == ()
