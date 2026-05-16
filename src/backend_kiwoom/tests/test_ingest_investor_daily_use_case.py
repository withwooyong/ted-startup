"""IngestInvestorDailyTradeUseCase / IngestInvestorDailyTradeBulkUseCase (Phase G, ~15 케이스).

TDD red 의도:
- `app.application.service.investor_flow_service.IngestInvestorDailyTradeUseCase` 미존재
- `IngestInvestorDailyTradeBulkUseCase` 미존재
→ Step 1 구현 후 green.

검증:
- 단건 정상 — fetch → lookup_codes → upsert → outcome.upserted = N
- 단건 stock lookup miss → stock_id=NULL + stock_code_raw 보존
- 단건 NXT _NX suffix → stock_code_raw 보존
- 단건 KiwoomBusinessError → outcome.error
- 단건 sentinel catch (SkipReason.SENTINEL_SKIP.value — F-3 D-7)
- Bulk 12 호출 매트릭스 (2 mkt × 3 inv × 2 trde = 12)
- Bulk 일부 실패 → 나머지 진행
- Bulk 빈 응답 → _empty_bulk_result (F-3 D-5 helper)
- Bulk errors_above_threshold tuple
- Bulk total_upserted 집계
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from app.adapter.out.kiwoom._records import (  # type: ignore[import]  # Step 1
    InvestorMarketType,
    InvestorTradeType,
    InvestorType,
    RankingExchangeType,
)
from app.application.dto._shared import SkipReason
from app.application.dto.investor_flow import (  # type: ignore[import]  # Step 1
    InvestorFlowBulkResult,
    InvestorIngestOutcome,
)
from app.application.service.investor_flow_service import (  # type: ignore[import]  # Step 1
    IngestInvestorDailyTradeBulkUseCase,
    IngestInvestorDailyTradeUseCase,
)

KST = ZoneInfo("Asia/Seoul")
_NOW = datetime(2026, 5, 16, 20, 0, 0, tzinfo=KST)
_AS_OF_DATE = date(2026, 5, 16)
_STRT_DT = "20260516"
_END_DT = "20260516"


def _make_investor_row(stk_cd: str = "005930") -> Any:
    """InvestorDailyTradeRow stub."""
    from app.adapter.out.kiwoom._records import InvestorDailyTradeRow  # type: ignore[import]

    return InvestorDailyTradeRow(
        stk_cd=stk_cd,
        stk_nm="삼성전자",
        netslmt_qty="+4464",
        netslmt_amt="+25467",
        prsm_avg_pric="57056",
        cur_prc="+61300",
        pre_sig="2",
        pred_pre="+4000",
        avg_pric_pre="+4244",
        pre_rt="+7.43",
        dt_trde_qty="1554171",
    )


# ---------------------------------------------------------------------------
# 단건 UseCase 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_investor_daily_trade_use_case_normal() -> None:
    """단건 정상 — fetch → lookup → upsert → InvestorIngestOutcome."""
    mock_client = AsyncMock()
    mock_client.fetch_investor_daily_trade_stocks = AsyncMock(
        return_value=[_make_investor_row()]
    )
    mock_repo = AsyncMock()
    mock_repo.upsert_many = AsyncMock(return_value=1)
    mock_stock_repo = AsyncMock()
    mock_stock_repo.find_by_codes = AsyncMock(return_value={"005930": 1})
    mock_session = AsyncMock()

    uc = IngestInvestorDailyTradeUseCase(
        client=mock_client,
        repository=mock_repo,
        stock_repository=mock_stock_repo,
        session=mock_session,
    )
    outcome = await uc.execute(
        strt_dt=_STRT_DT,
        end_dt=_END_DT,
        investor_type=InvestorType.FOREIGN,
        trade_type=InvestorTradeType.NET_BUY,
        market_type=InvestorMarketType.KOSPI,
        exchange_type=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
    )
    assert outcome.upserted == 1
    assert outcome.error is None


@pytest.mark.asyncio
async def test_ingest_investor_daily_trade_use_case_lookup_miss() -> None:
    """단건 stock lookup miss → stock_id=NULL 적재."""
    mock_client = AsyncMock()
    mock_client.fetch_investor_daily_trade_stocks = AsyncMock(
        return_value=[_make_investor_row("999998")]
    )
    mock_repo = AsyncMock()
    mock_repo.upsert_many = AsyncMock(return_value=1)
    mock_stock_repo = AsyncMock()
    mock_stock_repo.find_by_codes = AsyncMock(return_value={})  # lookup miss → 빈 dict
    mock_session = AsyncMock()

    uc = IngestInvestorDailyTradeUseCase(
        client=mock_client,
        repository=mock_repo,
        stock_repository=mock_stock_repo,
        session=mock_session,
    )
    outcome = await uc.execute(
        strt_dt=_STRT_DT,
        end_dt=_END_DT,
        investor_type=InvestorType.FOREIGN,
        trade_type=InvestorTradeType.NET_BUY,
        market_type=InvestorMarketType.KOSPI,
        exchange_type=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
    )
    assert outcome.upserted == 1


@pytest.mark.asyncio
async def test_ingest_investor_daily_trade_use_case_nxt_suffix() -> None:
    """단건 NXT _NX suffix → stock_code_raw 보존."""
    mock_client = AsyncMock()
    mock_client.fetch_investor_daily_trade_stocks = AsyncMock(
        return_value=[_make_investor_row("005930_NX")]
    )
    mock_repo = AsyncMock()
    mock_repo.upsert_many = AsyncMock(return_value=1)
    mock_stock_repo = AsyncMock()
    mock_stock_repo.find_by_codes = AsyncMock(return_value={"005930": 1})
    mock_session = AsyncMock()

    uc = IngestInvestorDailyTradeUseCase(
        client=mock_client,
        repository=mock_repo,
        stock_repository=mock_stock_repo,
        session=mock_session,
    )
    outcome = await uc.execute(
        strt_dt=_STRT_DT,
        end_dt=_END_DT,
        investor_type=InvestorType.FOREIGN,
        trade_type=InvestorTradeType.NET_BUY,
        market_type=InvestorMarketType.KOSPI,
        exchange_type=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
    )
    assert outcome.upserted == 1


@pytest.mark.asyncio
async def test_ingest_investor_daily_trade_use_case_business_error() -> None:
    """단건 KiwoomBusinessError → outcome.error."""
    from app.adapter.out.kiwoom._exceptions import KiwoomBusinessError  # type: ignore[import]

    mock_client = AsyncMock()
    mock_client.fetch_investor_daily_trade_stocks = AsyncMock(
        side_effect=KiwoomBusinessError(api_id="ka10058", return_code=1, message="업무 오류")
    )
    mock_repo = AsyncMock()
    mock_stock_repo = AsyncMock()
    mock_session = AsyncMock()

    uc = IngestInvestorDailyTradeUseCase(
        client=mock_client,
        repository=mock_repo,
        stock_repository=mock_stock_repo,
        session=mock_session,
    )
    outcome = await uc.execute(
        strt_dt=_STRT_DT,
        end_dt=_END_DT,
        investor_type=InvestorType.FOREIGN,
        trade_type=InvestorTradeType.NET_BUY,
        market_type=InvestorMarketType.KOSPI,
        exchange_type=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
    )
    assert outcome.error is not None
    assert outcome.upserted == 0


@pytest.mark.asyncio
async def test_ingest_investor_daily_trade_use_case_sentinel_catch() -> None:
    """단건 SentinelStockCodeError catch → outcome.error = SENTINEL_SKIP (F-3 D-7)."""
    from app.adapter.out.kiwoom.stkinfo import SentinelStockCodeError  # type: ignore[import]

    mock_client = AsyncMock()
    mock_client.fetch_investor_daily_trade_stocks = AsyncMock(
        side_effect=SentinelStockCodeError("999999")
    )
    mock_repo = AsyncMock()
    mock_stock_repo = AsyncMock()
    mock_session = AsyncMock()

    uc = IngestInvestorDailyTradeUseCase(
        client=mock_client,
        repository=mock_repo,
        stock_repository=mock_stock_repo,
        session=mock_session,
    )
    outcome = await uc.execute(
        strt_dt=_STRT_DT,
        end_dt=_END_DT,
        investor_type=InvestorType.INDIVIDUAL,
        trade_type=InvestorTradeType.NET_BUY,
        market_type=InvestorMarketType.KOSPI,
        exchange_type=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
    )
    assert outcome.error == SkipReason.SENTINEL_SKIP.value


# ---------------------------------------------------------------------------
# Bulk UseCase 테스트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_investor_daily_trade_bulk_use_case_12_calls() -> None:
    """Bulk — 2 mkt × 3 inv × 2 trde = 12 호출."""
    mock_single_uc = AsyncMock(spec=IngestInvestorDailyTradeUseCase)
    mock_single_uc.execute = AsyncMock(
        return_value=InvestorIngestOutcome(
            fetched_at=_NOW,
            investor_type="9000",
            trade_type="2",
            market_type="001",
            exchange_type="3",
            fetched=50,
            upserted=50,
            error=None,
        )
    )

    bulk_uc = IngestInvestorDailyTradeBulkUseCase(
        single_use_case=mock_single_uc,
    )
    result = await bulk_uc.execute(
        strt_dt=_STRT_DT,
        end_dt=_END_DT,
        investor_types=[
            InvestorType.INDIVIDUAL,
            InvestorType.FOREIGN,
            InvestorType.INSTITUTION_TOTAL,
        ],
        trade_types=[InvestorTradeType.NET_BUY, InvestorTradeType.NET_SELL],
        market_types=[InvestorMarketType.KOSPI, InvestorMarketType.KOSDAQ],
        exchange_type=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
    )
    assert isinstance(result, InvestorFlowBulkResult)
    assert result.total_calls == 12


@pytest.mark.asyncio
async def test_ingest_investor_daily_trade_bulk_use_case_partial_failure() -> None:
    """Bulk 일부 실패 → 나머지 진행."""
    call_count = 0

    async def _execute(**kwargs: Any) -> InvestorIngestOutcome:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return InvestorIngestOutcome(
                fetched_at=_NOW,
                investor_type="9000",
                trade_type="2",
                market_type="001",
                exchange_type="3",
                fetched=0,
                upserted=0,
                error="timeout",
            )
        return InvestorIngestOutcome(
            fetched_at=_NOW,
            investor_type="9000",
            trade_type="2",
            market_type="001",
            exchange_type="3",
            fetched=50,
            upserted=50,
            error=None,
        )

    mock_single_uc = AsyncMock(spec=IngestInvestorDailyTradeUseCase)
    mock_single_uc.execute = _execute

    bulk_uc = IngestInvestorDailyTradeBulkUseCase(single_use_case=mock_single_uc)
    result = await bulk_uc.execute(
        strt_dt=_STRT_DT,
        end_dt=_END_DT,
        investor_types=[InvestorType.FOREIGN, InvestorType.INSTITUTION_TOTAL],
        trade_types=[InvestorTradeType.NET_BUY, InvestorTradeType.NET_SELL],
        market_types=[InvestorMarketType.KOSPI],
        exchange_type=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
    )
    # 4 호출 중 1 실패 → total_failed >= 1
    assert result.total_calls == 4
    assert result.total_failed >= 1


@pytest.mark.asyncio
async def test_ingest_investor_daily_trade_bulk_use_case_empty_bulk_result() -> None:
    """Bulk 빈 응답 → _empty_bulk_result (F-3)."""
    mock_single_uc = AsyncMock(spec=IngestInvestorDailyTradeUseCase)
    mock_single_uc.execute = AsyncMock(
        return_value=InvestorIngestOutcome(
            fetched_at=_NOW,
            investor_type="9000",
            trade_type="2",
            market_type="001",
            exchange_type="3",
            fetched=0,
            upserted=0,
            error=None,
        )
    )

    bulk_uc = IngestInvestorDailyTradeBulkUseCase(single_use_case=mock_single_uc)
    result = await bulk_uc.execute(
        strt_dt=_STRT_DT,
        end_dt=_END_DT,
        investor_types=[],  # 빈 조합 → _empty_bulk_result
        trade_types=[],
        market_types=[],
        exchange_type=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
    )
    assert result.total_upserted == 0


@pytest.mark.asyncio
async def test_ingest_investor_daily_trade_bulk_use_case_errors_above_threshold() -> None:
    """Bulk errors_above_threshold tuple — D-11 임계치 미도입, 기본 빈 tuple."""
    mock_single_uc = AsyncMock(spec=IngestInvestorDailyTradeUseCase)
    mock_single_uc.execute = AsyncMock(
        return_value=InvestorIngestOutcome(
            fetched_at=_NOW,
            investor_type="9000",
            trade_type="2",
            market_type="001",
            exchange_type="3",
            fetched=50,
            upserted=50,
            error=None,
        )
    )

    bulk_uc = IngestInvestorDailyTradeBulkUseCase(single_use_case=mock_single_uc)
    result = await bulk_uc.execute(
        strt_dt=_STRT_DT,
        end_dt=_END_DT,
        investor_types=[InvestorType.FOREIGN],
        trade_types=[InvestorTradeType.NET_BUY],
        market_types=[InvestorMarketType.KOSPI],
        exchange_type=RankingExchangeType.UNIFIED,
        fetched_at=_NOW,
    )
    assert isinstance(result.errors_above_threshold, tuple)
    assert result.errors_above_threshold == ()  # D-11 임계치 미도입
