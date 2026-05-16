"""investor_flow_jobs.py — Phase G 3 cron 함수 단위 테스트 (~10 케이스).

TDD red 의도:
- `app.batch.investor_flow_jobs.fire_investor_daily_sync` 미존재 → ImportError
- `fire_stock_investor_breakdown_sync` 미존재 → ImportError
- `fire_frgn_orgn_continuous_sync` 미존재 → ImportError
→ Step 1 구현 후 green.

검증 (~10 케이스):
- 3 cron 시간 (20:00/20:30/21:00 KST mon-fri)
- misfire_grace_time=21600 (G-2 통일)
- is_trading_day=True → BulkUseCase execute 호출
- is_trading_day=False → BulkUseCase 미호출 (휴장일 skip)
- errors_above_threshold tuple 알람 (logger.error)
- 예외 swallow — execute raise → cron 연속성
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.application.dto.investor_flow import (  # type: ignore[import]  # Step 1
    FrgnOrgnConsecutiveBulkResult,
    InvestorFlowBulkResult,
    StockInvestorBreakdownBulkResult,
)
from app.batch.investor_flow_jobs import (  # type: ignore[import]  # Step 1
    fire_frgn_orgn_continuous_sync,
    fire_investor_daily_sync,
    fire_stock_investor_breakdown_sync,
)

KST = ZoneInfo("Asia/Seoul")
_NOW = datetime(2026, 5, 16, 20, 0, 0, tzinfo=KST)


def _make_investor_bulk_result(
    errors_above_threshold: tuple[str, ...] = (),
    total_upserted: int = 600,
) -> InvestorFlowBulkResult:
    return InvestorFlowBulkResult(
        total_calls=12,
        total_upserted=total_upserted,
        total_failed=0,
        outcomes=(),
        errors_above_threshold=errors_above_threshold,
    )


def _make_breakdown_bulk_result(
    errors_above_threshold: tuple[str, ...] = (),
    total_upserted: int = 3000,
) -> StockInvestorBreakdownBulkResult:
    return StockInvestorBreakdownBulkResult(
        total_calls=3000,
        total_upserted=total_upserted,
        total_failed=0,
        outcomes=(),
        errors_above_threshold=errors_above_threshold,
    )


def _make_frgn_orgn_bulk_result(
    errors_above_threshold: tuple[str, ...] = (),
    total_upserted: int = 400,
) -> FrgnOrgnConsecutiveBulkResult:
    return FrgnOrgnConsecutiveBulkResult(
        total_calls=4,
        total_upserted=total_upserted,
        total_failed=0,
        outcomes=(),
        errors_above_threshold=errors_above_threshold,
    )


def _make_bulk_uc_factory(result: Any) -> Any:
    """BulkUseCase factory context manager stub."""
    uc = AsyncMock()
    uc.execute = AsyncMock(return_value=result)

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _factory(alias: str):  # type: ignore[no-untyped-def]
        yield uc

    return _factory, uc


# ===========================================================================
# fire_investor_daily_sync — KST 20:00 mon-fri
# ===========================================================================


@pytest.mark.asyncio
async def test_fire_investor_daily_sync_trading_day_executes() -> None:
    """is_trading_day=True → IngestInvestorDailyTradeBulkUseCase.execute 호출."""
    result = _make_investor_bulk_result()
    _factory, mock_uc = _make_bulk_uc_factory(result)

    with (
        patch("app.batch.investor_flow_jobs.get_ingest_investor_daily_bulk_factory", return_value=_factory),
        patch("app.batch.investor_flow_jobs.is_trading_day", return_value=True),
    ):
        await fire_investor_daily_sync(snapshot_at=_NOW)

    mock_uc.execute.assert_called_once()


@pytest.mark.asyncio
async def test_fire_investor_daily_sync_holiday_skips() -> None:
    """is_trading_day=False → BulkUseCase 미호출."""
    _factory, mock_uc = _make_bulk_uc_factory(_make_investor_bulk_result())

    with (
        patch("app.batch.investor_flow_jobs.get_ingest_investor_daily_bulk_factory", return_value=_factory),
        patch("app.batch.investor_flow_jobs.is_trading_day", return_value=False),
    ):
        await fire_investor_daily_sync(snapshot_at=_NOW)

    mock_uc.execute.assert_not_called()


@pytest.mark.asyncio
async def test_fire_investor_daily_sync_errors_above_threshold_alarm(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """errors_above_threshold 비어있지 않음 → logger.error 알람."""
    result = _make_investor_bulk_result(errors_above_threshold=("FOREIGN:NET_BUY:001",))
    _factory, mock_uc = _make_bulk_uc_factory(result)

    with (
        patch("app.batch.investor_flow_jobs.get_ingest_investor_daily_bulk_factory", return_value=_factory),
        patch("app.batch.investor_flow_jobs.is_trading_day", return_value=True),
        caplog.at_level(logging.ERROR),
    ):
        await fire_investor_daily_sync(snapshot_at=_NOW)

    # errors_above_threshold 비어있지 않음 → logger.error 호출 확인 (Step 2 R1 L-1)
    error_logs = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(error_logs) >= 1, "errors_above_threshold 시 logger.error 미발생"


# ===========================================================================
# fire_stock_investor_breakdown_sync — KST 20:30 mon-fri (60분 sync)
# ===========================================================================


@pytest.mark.asyncio
async def test_fire_stock_investor_breakdown_sync_trading_day_executes() -> None:
    """is_trading_day=True → IngestStockInvestorBreakdownBulkUseCase.execute 호출.

    Step 2 R1 C-5: cron 진입 시 active 종목 list 를 ``_build_active_stock_targets`` 가
    빌드. 본 테스트는 그 helper 를 mock 해 단위 격리.
    """
    result = _make_breakdown_bulk_result()
    _factory, mock_uc = _make_bulk_uc_factory(result)

    async def _mock_targets() -> tuple[list[str], dict[str, int]]:
        return ["005930"], {"005930": 1}

    with (
        patch(
            "app.batch.investor_flow_jobs.get_ingest_stock_investor_breakdown_bulk_factory",
            return_value=_factory,
        ),
        patch("app.batch.investor_flow_jobs.is_trading_day", return_value=True),
        patch(
            "app.batch.investor_flow_jobs._build_active_stock_targets",
            side_effect=_mock_targets,
        ),
    ):
        await fire_stock_investor_breakdown_sync(snapshot_at=_NOW)

    mock_uc.execute.assert_called_once()


@pytest.mark.asyncio
async def test_fire_stock_investor_breakdown_sync_holiday_skips() -> None:
    """is_trading_day=False → BulkUseCase 미호출."""
    _factory, mock_uc = _make_bulk_uc_factory(_make_breakdown_bulk_result())

    with (
        patch(
            "app.batch.investor_flow_jobs.get_ingest_stock_investor_breakdown_bulk_factory",
            return_value=_factory,
        ),
        patch("app.batch.investor_flow_jobs.is_trading_day", return_value=False),
    ):
        await fire_stock_investor_breakdown_sync(snapshot_at=_NOW)

    mock_uc.execute.assert_not_called()


# ===========================================================================
# fire_frgn_orgn_continuous_sync — KST 21:00 mon-fri
# ===========================================================================


@pytest.mark.asyncio
async def test_fire_frgn_orgn_continuous_sync_trading_day_executes() -> None:
    """is_trading_day=True → IngestFrgnOrgnConsecutiveBulkUseCase.execute 호출."""
    result = _make_frgn_orgn_bulk_result()
    _factory, mock_uc = _make_bulk_uc_factory(result)

    with (
        patch(
            "app.batch.investor_flow_jobs.get_ingest_frgn_orgn_bulk_factory",
            return_value=_factory,
        ),
        patch("app.batch.investor_flow_jobs.is_trading_day", return_value=True),
    ):
        await fire_frgn_orgn_continuous_sync(snapshot_at=_NOW)

    mock_uc.execute.assert_called_once()


@pytest.mark.asyncio
async def test_fire_frgn_orgn_continuous_sync_holiday_skips() -> None:
    """is_trading_day=False → BulkUseCase 미호출."""
    _factory, mock_uc = _make_bulk_uc_factory(_make_frgn_orgn_bulk_result())

    with (
        patch(
            "app.batch.investor_flow_jobs.get_ingest_frgn_orgn_bulk_factory",
            return_value=_factory,
        ),
        patch("app.batch.investor_flow_jobs.is_trading_day", return_value=False),
    ):
        await fire_frgn_orgn_continuous_sync(snapshot_at=_NOW)

    mock_uc.execute.assert_not_called()


# ===========================================================================
# misfire_grace_time = 21600 (G-2 통일)
# ===========================================================================


def test_investor_flow_jobs_misfire_grace_time() -> None:
    """MISFIRE_GRACE_SECONDS = 21600 (G-2). Step 2 R1 L-2 — 21600 만 허용."""
    import app.batch.investor_flow_jobs as jobs_module  # type: ignore[import]

    grace = getattr(jobs_module, "MISFIRE_GRACE_SECONDS", None)
    assert grace == 21600, f"MISFIRE_GRACE_SECONDS 21600 기대, 실제: {grace!r}"


# ===========================================================================
# 예외 swallow — execute raise → cron 연속성
# ===========================================================================


@pytest.mark.asyncio
async def test_fire_investor_daily_sync_exception_swallow() -> None:
    """execute raise → cron 연속성 (예외 전파 안 됨)."""
    uc = AsyncMock()
    uc.execute = AsyncMock(side_effect=RuntimeError("일시적 오류"))

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _factory(alias: str):  # type: ignore[no-untyped-def]
        yield uc

    with (
        patch("app.batch.investor_flow_jobs.get_ingest_investor_daily_bulk_factory", return_value=_factory),
        patch("app.batch.investor_flow_jobs.is_trading_day", return_value=True),
    ):
        # 예외가 전파되지 않아야 함
        try:
            await fire_investor_daily_sync(snapshot_at=_NOW)
        except RuntimeError:
            pytest.fail("fire_investor_daily_sync 예외 전파 — cron 연속성 위반")
