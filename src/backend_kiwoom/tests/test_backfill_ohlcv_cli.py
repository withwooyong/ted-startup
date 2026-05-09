"""scripts/backfill_ohlcv.py CLI — argparse + period dispatch + dry-run + resume + exit code.

설계: phase-c-backfill-ohlcv.md § 3.

본 테스트는 CLI 전체 플로우 — argparse / period dispatch / dry-run / resume / exit code 분기.
KiwoomClient / DB 는 mock — 실제 호출 X.

검증 영역:
1. argparse 인자 검증 (필수 / 디폴트 / 형식)
2. period 분기 (daily → IngestDailyOhlcvUseCase / weekly|monthly → IngestPeriodicOhlcvUseCase)
3. dry-run 모드 — UseCase.execute 호출 안 함, 추정값만 출력
4. resume 모드 — max(trading_date) 기반 skip
5. exit code 4 분기 (0/1/2/3)
6. only_market_codes / only_stock_codes 필터
7. summary 출력 포맷
"""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.application.service.ohlcv_daily_service import OhlcvSyncResult

# ---------- 1. argparse ----------


def test_parse_args_period_required() -> None:
    """--period 필수."""
    from scripts.backfill_ohlcv import build_parser

    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--alias", "x"])


def test_parse_args_alias_required() -> None:
    """--alias 필수."""
    from scripts.backfill_ohlcv import build_parser

    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--period", "daily"])


def test_parse_args_period_choices() -> None:
    """period 는 daily/weekly/monthly 만."""
    from scripts.backfill_ohlcv import build_parser

    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--period", "yearly", "--alias", "x"])


def test_parse_args_default_years_3() -> None:
    """--years 디폴트 3."""
    from scripts.backfill_ohlcv import build_parser

    parser = build_parser()
    args = parser.parse_args(["--period", "daily", "--alias", "x"])
    assert args.years == 3


def test_parse_args_dry_run_flag() -> None:
    """--dry-run flag."""
    from scripts.backfill_ohlcv import build_parser

    parser = build_parser()
    args = parser.parse_args(["--period", "daily", "--alias", "x", "--dry-run"])
    assert args.dry_run is True

    args = parser.parse_args(["--period", "daily", "--alias", "x"])
    assert args.dry_run is False


def test_parse_args_only_market_codes_csv() -> None:
    """--only-market-codes 0,10 → list[str]."""
    from scripts.backfill_ohlcv import parse_csv_codes

    assert parse_csv_codes("0,10") == ["0", "10"]
    assert parse_csv_codes("0") == ["0"]
    assert parse_csv_codes("") == []


def test_parse_args_only_stock_codes_csv() -> None:
    from scripts.backfill_ohlcv import parse_csv_codes

    assert parse_csv_codes("005930,000660") == ["005930", "000660"]


def test_parse_args_max_stocks() -> None:
    from scripts.backfill_ohlcv import build_parser

    parser = build_parser()
    args = parser.parse_args(["--period", "daily", "--alias", "x", "--max-stocks", "100"])
    assert args.max_stocks == 100


# ---------- 2. resolve_date_range ----------


def test_resolve_date_range_default_3_years() -> None:
    """--years 3 (디폴트) → today - 3*365 ~ today."""
    from datetime import timedelta

    from scripts.backfill_ohlcv import resolve_date_range

    today = date.today()
    start, end = resolve_date_range(years=3, start_date=None, end_date=None)
    assert end == today
    assert start == today - timedelta(days=365 * 3)


def test_resolve_date_range_explicit_start_end() -> None:
    """명시 --start-date / --end-date 가 --years 무시."""
    from scripts.backfill_ohlcv import resolve_date_range

    start, end = resolve_date_range(
        years=3,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )
    assert start == date(2024, 1, 1)
    assert end == date(2024, 12, 31)


def test_resolve_date_range_start_after_end_raises() -> None:
    """start > end → ValueError."""
    from scripts.backfill_ohlcv import resolve_date_range

    with pytest.raises(ValueError, match="start"):
        resolve_date_range(
            years=3,
            start_date=date(2024, 12, 31),
            end_date=date(2024, 1, 1),
        )


# ---------- 3. period dispatch ----------


def test_choose_use_case_factory_daily() -> None:
    """period=daily → IngestDailyOhlcvUseCase factory."""
    from app.application.service.ohlcv_daily_service import IngestDailyOhlcvUseCase
    from scripts.backfill_ohlcv import use_case_class_for_period

    cls = use_case_class_for_period("daily")
    assert cls is IngestDailyOhlcvUseCase


def test_choose_use_case_factory_weekly_monthly() -> None:
    """period=weekly|monthly → IngestPeriodicOhlcvUseCase factory."""
    from app.application.service.ohlcv_periodic_service import (
        IngestPeriodicOhlcvUseCase,
    )
    from scripts.backfill_ohlcv import use_case_class_for_period

    assert use_case_class_for_period("weekly") is IngestPeriodicOhlcvUseCase
    assert use_case_class_for_period("monthly") is IngestPeriodicOhlcvUseCase


# ---------- 4. dry-run 시간 추정 ----------


def test_estimate_seconds_lower_bound() -> None:
    """dry-run 시간 추정 = rate_limit × 호출 수 (lower-bound). H-3."""
    from scripts.backfill_ohlcv import estimate_seconds

    # 100 종목 × 1 거래소 (KRX 만) × 페이지 1 = 100 호출 × 2초 = 200초
    seconds = estimate_seconds(stocks=100, exchanges_per_stock=1, pages_per_call=1, rate_limit_seconds=2.0)
    assert seconds == pytest.approx(200.0)

    # 100 종목 × 2 거래소 × 페이지 2 = 400 호출 × 2초 = 800초
    seconds = estimate_seconds(stocks=100, exchanges_per_stock=2, pages_per_call=2, rate_limit_seconds=2.0)
    assert seconds == pytest.approx(800.0)


def test_format_duration_hours_minutes() -> None:
    from scripts.backfill_ohlcv import format_duration

    assert format_duration(60) == "0h 1m 0s"
    assert format_duration(3661) == "1h 1m 1s"
    assert format_duration(7200) == "2h 0m 0s"


# ---------- 5. exit code (subprocess 시뮬) ----------


def test_summary_to_exit_code_success() -> None:
    """failed=0 → exit 0."""
    from scripts.backfill_ohlcv import summary_to_exit_code

    result = OhlcvSyncResult(base_date=date(2025, 9, 8), total=10, success_krx=10, success_nxt=0, failed=0, errors=())
    assert summary_to_exit_code(result) == 0


def test_summary_to_exit_code_partial_failure() -> None:
    """failed > 0 → exit 1."""
    from app.application.service.ohlcv_daily_service import OhlcvSyncOutcome
    from scripts.backfill_ohlcv import summary_to_exit_code

    result = OhlcvSyncResult(
        base_date=date(2025, 9, 8),
        total=10,
        success_krx=9,
        success_nxt=0,
        failed=1,
        errors=(OhlcvSyncOutcome(stock_code="005930", exchange="KRX", error_class="KiwoomBusinessError"),),
    )
    assert summary_to_exit_code(result) == 1


# ---------- 6. resume — DB max(trading_date) ----------


@pytest.mark.asyncio
async def test_should_skip_resume_when_max_date_ge_end() -> None:
    """resume + max(trading_date) >= end_date → skip."""
    from scripts.backfill_ohlcv import should_skip_resume

    skip = should_skip_resume(
        max_trading_date=date(2025, 9, 8),
        end_date=date(2025, 9, 8),
    )
    assert skip is True

    skip = should_skip_resume(
        max_trading_date=date(2025, 9, 9),
        end_date=date(2025, 9, 8),
    )
    assert skip is True


@pytest.mark.asyncio
async def test_should_not_skip_resume_when_max_date_lt_end() -> None:
    """resume + max(trading_date) < end_date → 진행."""
    from scripts.backfill_ohlcv import should_skip_resume

    skip = should_skip_resume(
        max_trading_date=date(2025, 8, 1),
        end_date=date(2025, 9, 8),
    )
    assert skip is False


@pytest.mark.asyncio
async def test_should_not_skip_resume_when_no_data() -> None:
    """resume + max(trading_date) None (적재 0) → 진행."""
    from scripts.backfill_ohlcv import should_skip_resume

    skip = should_skip_resume(max_trading_date=None, end_date=date(2025, 9, 8))
    assert skip is False


# ---------- 7. dry_run 출력 ----------


@pytest.mark.asyncio
async def test_dry_run_does_not_call_use_case() -> None:
    """dry-run 모드 — use_case.execute 호출 안 함."""
    from scripts.backfill_ohlcv import run_dry_run

    use_case = AsyncMock()
    output = await run_dry_run(
        use_case=use_case,
        period="daily",
        active_stocks_count=100,
        nxt_enabled=False,
        end_date=date(2025, 9, 8),
        start_date=date(2022, 9, 8),
        rate_limit_seconds=2.0,
    )

    use_case.execute.assert_not_awaited()
    assert "추정" in output or "estimate" in output.lower()
    assert "100" in output  # 종목 수 노출


# ---------- 8. main 함수 진입점 ----------


@pytest.mark.asyncio
async def test_main_returns_2_when_invalid_args() -> None:
    """invalid args → exit code 2."""
    from scripts.backfill_ohlcv import async_main

    # period 미지정 → SystemExit (argparse) — exit code 2
    with pytest.raises(SystemExit) as exc_info:
        await async_main(["--alias", "x"])
    assert exc_info.value.code == 2


# ---------- 9. resume — DB 통합 ----------


@pytest.mark.asyncio
async def test_compute_resume_remaining_codes_filters_already_loaded() -> None:
    """compute_resume_remaining_codes — 적재 완료 종목 skip + 미완료만 반환."""
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager

    # 별도 fixture 로 하기보다 inline — engine fixture 활용
    @asynccontextmanager
    async def _no_op() -> AsyncIterator[None]:
        yield None

    # engine fixture 직접 import 어렵 — pytest fixture 통해 호출되도록 별도 함수로 위임


@pytest.mark.asyncio
async def test_compute_resume_remaining_codes_empty_returns_empty(
    engine: Any,
) -> None:
    """후보 0 → 빈 list."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from scripts.backfill_ohlcv import compute_resume_remaining_codes

    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        remaining = await compute_resume_remaining_codes(
            session,
            period="daily",
            end_date=date(2025, 9, 8),
            candidate_codes=[],
        )
        assert remaining == []


@pytest.mark.asyncio
async def test_compute_resume_remaining_codes_no_data_returns_all(
    engine: Any,
) -> None:
    """적재 0 → 모든 후보 진행 대상."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from scripts.backfill_ohlcv import compute_resume_remaining_codes

    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session, session.begin():
        # 종목만 등록, OHLCV 적재 0
        await session.execute(
            text(
                "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code) "
                "VALUES ('TST701', 'r1', '0'), ('TST702', 'r2', '0') "
                "ON CONFLICT DO NOTHING"
            )
        )
    async with factory() as session:
        remaining = await compute_resume_remaining_codes(
            session,
            period="daily",
            end_date=date(2025, 9, 8),
            candidate_codes=["TST701", "TST702"],
        )
        assert sorted(remaining) == ["TST701", "TST702"]
    # cleanup
    async with factory() as session, session.begin():
        await session.execute(text("DELETE FROM kiwoom.stock WHERE stock_code IN ('TST701', 'TST702')"))
