"""ranking_jobs.py — Phase F-4 5 cron 함수 단위 테스트 (~10 케이스).

설계: phase-f-4-rankings.md § 5.8 + § 5.12 #9.

가정 production 위치: app/batch/ranking_jobs.py (Step 1 에서 작성).

5 cron 함수:
- fire_flu_rt_sync
- fire_today_volume_sync
- fire_pred_volume_sync
- fire_trde_prica_sync
- fire_volume_sdnin_sync

검증 시나리오 (~10 케이스):

각 cron 함수 × 2 케이스 = 10 케이스:

[케이스 A] is_trading_day=False → BulkUseCase 미호출 (휴장일 skip):
  1. fire_flu_rt_sync — is_trading_day False → execute 미호출
  2. fire_today_volume_sync — is_trading_day False → execute 미호출

[케이스 B] is_trading_day=True → BulkUseCase execute 호출:
  3. fire_flu_rt_sync — is_trading_day True → execute 1회 호출
  4. fire_today_volume_sync — is_trading_day True → execute 1회 호출
  5. fire_pred_volume_sync — is_trading_day True → execute 1회 호출
  6. fire_trde_prica_sync — is_trading_day True → execute 1회 호출
  7. fire_volume_sdnin_sync — is_trading_day True → execute 1회 호출

[케이스 C] errors_above_threshold tuple → logger.error 알람 (F-3 D-3 패턴):
  8. fire_flu_rt_sync — errors_above_threshold 비어있지 않음 → logger.error 호출
  9. fire_today_volume_sync — errors_above_threshold 비어있지 않음 → logger.error 호출
  10. 예외 swallow — execute raise → cron 연속성 (예외 전파 안 됨)

TDD red 의도:
- `from app.batch.ranking_jobs import fire_flu_rt_sync` → ImportError (Step 1 미구현)
- Step 1 구현 후 green 전환.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.adapter.out.kiwoom._records import RankingType  # type: ignore[import]  # Step 0b
from app.application.dto.ranking import RankingBulkResult  # type: ignore[import]  # Step 0c
from app.batch.ranking_jobs import (  # type: ignore[import]  # Step 1
    fire_flu_rt_sync,
    fire_pred_volume_sync,
    fire_today_volume_sync,
    fire_trde_prica_sync,
    fire_volume_sdnin_sync,
)

KST = ZoneInfo("Asia/Seoul")
SNAPSHOT_AT = datetime(2026, 5, 15, 19, 30, 0, tzinfo=KST)


# ---------------------------------------------------------------------------
# 헬퍼 — RankingBulkResult stub 생성
# ---------------------------------------------------------------------------


def _make_bulk_result(
    ranking_type: Any = None,
    total_calls: int = 4,
    total_upserted: int = 100,
    total_failed: int = 0,
    errors_above_threshold: tuple[str, ...] = (),
) -> RankingBulkResult:
    """테스트용 RankingBulkResult stub."""
    return RankingBulkResult(
        ranking_type=ranking_type or RankingType.FLU_RT,
        total_calls=total_calls,
        total_upserted=total_upserted,
        total_failed=total_failed,
        outcomes=(),
        errors_above_threshold=errors_above_threshold,
    )


def _make_bulk_uc_factory(result: RankingBulkResult) -> Any:
    """BulkUseCase factory context manager stub."""
    uc = AsyncMock()
    uc.execute = AsyncMock(return_value=result)

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _factory(_alias: str):  # type: ignore[no-untyped-def]
        yield uc

    return _factory, uc


# ===========================================================================
# 케이스 A — is_trading_day=False → BulkUseCase 미호출
# ===========================================================================


@pytest.mark.asyncio
async def test_flu_rt_sync_skips_on_non_trading_day() -> None:
    """fire_flu_rt_sync — is_trading_day=False → execute 미호출 (휴장일 skip).

    plan § 5.8 — cron 발화 시 is_trading_day guard 통과 후 BulkUseCase 호출.
    """
    factory, uc = _make_bulk_uc_factory(_make_bulk_result(RankingType.FLU_RT))

    with patch("app.batch.ranking_jobs.is_trading_day", return_value=False):
        await fire_flu_rt_sync(factory=factory, alias="test")

    uc.execute.assert_not_called()


@pytest.mark.asyncio
async def test_today_volume_sync_skips_on_non_trading_day() -> None:
    """fire_today_volume_sync — is_trading_day=False → execute 미호출."""
    factory, uc = _make_bulk_uc_factory(_make_bulk_result(RankingType.TODAY_VOLUME))

    with patch("app.batch.ranking_jobs.is_trading_day", return_value=False):
        await fire_today_volume_sync(factory=factory, alias="test")

    uc.execute.assert_not_called()


# ===========================================================================
# 케이스 B — is_trading_day=True → BulkUseCase execute 1회 호출
# ===========================================================================


@pytest.mark.asyncio
async def test_flu_rt_sync_calls_bulk_use_case_on_trading_day() -> None:
    """fire_flu_rt_sync — is_trading_day=True → execute 1회 호출."""
    factory, uc = _make_bulk_uc_factory(_make_bulk_result(RankingType.FLU_RT))

    with patch("app.batch.ranking_jobs.is_trading_day", return_value=True):
        await fire_flu_rt_sync(factory=factory, alias="test")

    assert uc.execute.await_count == 1, f"execute 1회 기대, 실제={uc.execute.await_count}"


@pytest.mark.asyncio
async def test_today_volume_sync_calls_bulk_use_case_on_trading_day() -> None:
    """fire_today_volume_sync — is_trading_day=True → execute 1회 호출."""
    factory, uc = _make_bulk_uc_factory(_make_bulk_result(RankingType.TODAY_VOLUME))

    with patch("app.batch.ranking_jobs.is_trading_day", return_value=True):
        await fire_today_volume_sync(factory=factory, alias="test")

    assert uc.execute.await_count == 1


@pytest.mark.asyncio
async def test_pred_volume_sync_calls_bulk_use_case_on_trading_day() -> None:
    """fire_pred_volume_sync — is_trading_day=True → execute 1회 호출."""
    factory, uc = _make_bulk_uc_factory(_make_bulk_result(RankingType.PRED_VOLUME))

    with patch("app.batch.ranking_jobs.is_trading_day", return_value=True):
        await fire_pred_volume_sync(factory=factory, alias="test")

    assert uc.execute.await_count == 1


@pytest.mark.asyncio
async def test_trde_prica_sync_calls_bulk_use_case_on_trading_day() -> None:
    """fire_trde_prica_sync — is_trading_day=True → execute 1회 호출."""
    factory, uc = _make_bulk_uc_factory(_make_bulk_result(RankingType.TRDE_PRICA))

    with patch("app.batch.ranking_jobs.is_trading_day", return_value=True):
        await fire_trde_prica_sync(factory=factory, alias="test")

    assert uc.execute.await_count == 1


@pytest.mark.asyncio
async def test_volume_sdnin_sync_calls_bulk_use_case_on_trading_day() -> None:
    """fire_volume_sdnin_sync — is_trading_day=True → execute 1회 호출."""
    factory, uc = _make_bulk_uc_factory(_make_bulk_result(RankingType.VOLUME_SDNIN))

    with patch("app.batch.ranking_jobs.is_trading_day", return_value=True):
        await fire_volume_sdnin_sync(factory=factory, alias="test")

    assert uc.execute.await_count == 1


# ===========================================================================
# 케이스 C — errors_above_threshold tuple → logger.error 알람 (F-3 D-3 패턴)
# ===========================================================================


@pytest.mark.asyncio
async def test_flu_rt_sync_logs_error_on_errors_above_threshold(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """fire_flu_rt_sync — errors_above_threshold 비어있지 않음 → logger.error 호출.

    F-3 D-3 패턴: errors_above_threshold: tuple[str, ...] — 비어있으면 falsy,
    비어있지 않으면 logger.error 알람. short_selling_job.py:59 패턴 미러.
    """
    error_messages = ("call_1 failed: business error", "call_3 failed: upstream error")
    result = _make_bulk_result(
        RankingType.FLU_RT,
        total_calls=4,
        total_upserted=50,
        total_failed=2,
        errors_above_threshold=error_messages,
    )
    factory, uc = _make_bulk_uc_factory(result)

    with (
        patch("app.batch.ranking_jobs.is_trading_day", return_value=True),
        caplog.at_level(logging.ERROR, logger="app.batch.ranking_jobs"),
    ):
        await fire_flu_rt_sync(factory=factory, alias="test")

    # errors_above_threshold 비어있지 않음 → ERROR 레벨 로그 존재
    error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(error_records) >= 1, (
        f"errors_above_threshold 있을 때 logger.error 기대, 실제 log count={len(error_records)}"
    )


@pytest.mark.asyncio
async def test_today_volume_sync_logs_error_on_errors_above_threshold(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """fire_today_volume_sync — errors_above_threshold 비어있지 않음 → logger.error 호출."""
    error_messages = ("call_2 failed: timeout",)
    result = _make_bulk_result(
        RankingType.TODAY_VOLUME,
        total_calls=2,
        total_upserted=30,
        total_failed=1,
        errors_above_threshold=error_messages,
    )
    factory, uc = _make_bulk_uc_factory(result)

    with (
        patch("app.batch.ranking_jobs.is_trading_day", return_value=True),
        caplog.at_level(logging.ERROR, logger="app.batch.ranking_jobs"),
    ):
        await fire_today_volume_sync(factory=factory, alias="test")

    error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(error_records) >= 1


@pytest.mark.asyncio
async def test_flu_rt_sync_swallows_exception_for_cron_continuity() -> None:
    """execute 에서 예외 raise → cron 연속성 보장 (예외 전파 안 됨).

    best-effort cron — sector_daily_ohlcv_job.py 패턴 1:1 미러.
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _factory(_alias: str):  # type: ignore[no-untyped-def]
        raise RuntimeError("simulate crash during factory context")
        yield  # unreachable

    with patch("app.batch.ranking_jobs.is_trading_day", return_value=True):
        # 예외가 전파되면 테스트 실패 — 예외 swallow 되어야 함
        try:
            await fire_flu_rt_sync(factory=_factory, alias="test")
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"cron 콜백에서 예외 전파됨 — swallow 기대: {exc!r}")


__all__: list[Any] = []
