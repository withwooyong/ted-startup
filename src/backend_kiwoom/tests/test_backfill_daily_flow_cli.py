"""scripts/backfill_daily_flow.py CLI — argparse + indc-mode + dry-run + resume + exit code.

설계: phase-c-backfill-daily-flow.md § 3.

본 테스트는 CLI 전체 플로우 — argparse / dry-run / resume / exit code 분기.
KiwoomClient / DB 는 mock — 실제 호출 X.

검증 영역:
1. argparse 인자 검증 (필수 / 디폴트 / indc-mode 형식)
2. resolve_date_range 재사용 (OHLCV 백필과 동일 헬퍼)
3. dry-run 모드 — UseCase.execute 호출 안 함, 추정값만 출력
4. resume 모드 — max(trading_date) 기반 skip
5. exit code (0/1/2)
6. _list_active_stock_codes / _count_active_stocks 의 max_stocks limit (운영 차단 fix)
"""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.application.constants import DailyMarketDisplayMode
from app.application.service.daily_flow_service import (
    DailyFlowSyncOutcome,
    DailyFlowSyncResult,
)

# ---------- 1. argparse ----------


def test_parse_args_alias_required() -> None:
    """--alias 필수."""
    from scripts.backfill_daily_flow import build_parser

    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parse_args_default_years_3() -> None:
    """--years 디폴트 3."""
    from scripts.backfill_daily_flow import build_parser

    parser = build_parser()
    args = parser.parse_args(["--alias", "x"])
    assert args.years == 3


def test_parse_args_dry_run_flag() -> None:
    """--dry-run flag."""
    from scripts.backfill_daily_flow import build_parser

    parser = build_parser()
    args = parser.parse_args(["--alias", "x", "--dry-run"])
    assert args.dry_run is True

    args = parser.parse_args(["--alias", "x"])
    assert args.dry_run is False


def test_parse_args_indc_mode_default_quantity() -> None:
    """--indc-mode 디폴트 quantity (계획서 § 2.3 권장)."""
    from scripts.backfill_daily_flow import build_parser

    parser = build_parser()
    args = parser.parse_args(["--alias", "x"])
    assert args.indc_mode == "quantity"


def test_parse_args_indc_mode_amount() -> None:
    """--indc-mode amount."""
    from scripts.backfill_daily_flow import build_parser

    parser = build_parser()
    args = parser.parse_args(["--alias", "x", "--indc-mode", "amount"])
    assert args.indc_mode == "amount"


def test_parse_args_indc_mode_invalid_choice() -> None:
    """--indc-mode 는 quantity/amount 만."""
    from scripts.backfill_daily_flow import build_parser

    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--alias", "x", "--indc-mode", "yen"])


def test_parse_args_max_stocks() -> None:
    from scripts.backfill_daily_flow import build_parser

    parser = build_parser()
    args = parser.parse_args(["--alias", "x", "--max-stocks", "100"])
    assert args.max_stocks == 100


def test_parse_csv_codes_helper() -> None:
    """CSV 파서 — OHLCV 백필 헬퍼와 동일 동작."""
    from scripts.backfill_daily_flow import parse_csv_codes

    assert parse_csv_codes("0,10") == ["0", "10"]
    assert parse_csv_codes("005930,000660") == ["005930", "000660"]
    assert parse_csv_codes("") == []


def test_resolve_indc_mode_str_to_enum() -> None:
    """문자열 인자 → DailyMarketDisplayMode."""
    from scripts.backfill_daily_flow import resolve_indc_mode

    assert resolve_indc_mode("quantity") is DailyMarketDisplayMode.QUANTITY
    assert resolve_indc_mode("amount") is DailyMarketDisplayMode.AMOUNT


# ---------- 2. resolve_date_range ----------


def test_resolve_date_range_default_3_years() -> None:
    """--years 3 (디폴트) → today - 3*365 ~ today."""
    from datetime import timedelta

    from scripts.backfill_daily_flow import resolve_date_range

    today = date.today()
    start, end = resolve_date_range(years=3, start_date=None, end_date=None)
    assert end == today
    assert start == today - timedelta(days=365 * 3)


def test_resolve_date_range_explicit_start_end() -> None:
    """명시 --start-date / --end-date 가 --years 무시."""
    from scripts.backfill_daily_flow import resolve_date_range

    start, end = resolve_date_range(
        years=3,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )
    assert start == date(2024, 1, 1)
    assert end == date(2024, 12, 31)


def test_resolve_date_range_start_after_end_raises() -> None:
    """start > end → ValueError."""
    from scripts.backfill_daily_flow import resolve_date_range

    with pytest.raises(ValueError, match="start"):
        resolve_date_range(
            years=3,
            start_date=date(2024, 12, 31),
            end_date=date(2024, 1, 1),
        )


# ---------- 3. dry-run 시간 추정 ----------


def test_estimate_seconds_lower_bound() -> None:
    """dry-run 시간 추정 = rate_limit × 호출 수 (lower-bound)."""
    from scripts.backfill_daily_flow import estimate_seconds

    seconds = estimate_seconds(
        stocks=100, exchanges_per_stock=1, pages_per_call=1, rate_limit_seconds=2.0
    )
    assert seconds == pytest.approx(200.0)

    # 100 종목 × 2 거래소 × 페이지 3 = 600 호출 × 2초 = 1200초
    seconds = estimate_seconds(
        stocks=100, exchanges_per_stock=2, pages_per_call=3, rate_limit_seconds=2.0
    )
    assert seconds == pytest.approx(1200.0)


def test_format_duration_hours_minutes() -> None:
    from scripts.backfill_daily_flow import format_duration

    assert format_duration(60) == "0h 1m 0s"
    assert format_duration(3661) == "1h 1m 1s"


# ---------- 4. exit code ----------


def test_summary_to_exit_code_success() -> None:
    """failed=0 → exit 0."""
    from scripts.backfill_daily_flow import summary_to_exit_code

    result = DailyFlowSyncResult(
        base_date=date(2025, 9, 8),
        total=10,
        success_krx=10,
        success_nxt=0,
        failed=0,
        errors=(),
    )
    assert summary_to_exit_code(result) == 0


def test_summary_to_exit_code_partial_failure() -> None:
    """failed > 0 → exit 1."""
    from scripts.backfill_daily_flow import summary_to_exit_code

    result = DailyFlowSyncResult(
        base_date=date(2025, 9, 8),
        total=10,
        success_krx=9,
        success_nxt=0,
        failed=1,
        errors=(
            DailyFlowSyncOutcome(
                stock_code="005930", exchange="KRX", error_class="KiwoomBusinessError"
            ),
        ),
    )
    assert summary_to_exit_code(result) == 1


# ---------- 6. dry_run 출력 ----------


@pytest.mark.asyncio
async def test_dry_run_does_not_call_use_case() -> None:
    """dry-run 모드 — use_case.execute 호출 안 함."""
    from scripts.backfill_daily_flow import run_dry_run

    use_case = AsyncMock()
    output = await run_dry_run(
        use_case=use_case,
        active_stocks_count=100,
        nxt_enabled=False,
        end_date=date(2025, 9, 8),
        start_date=date(2022, 9, 8),
        rate_limit_seconds=2.0,
    )

    use_case.execute.assert_not_awaited()
    assert "100" in output  # 종목 수 노출
    assert "추정" in output or "estimate" in output.lower()


# ---------- 7. main 진입점 ----------


@pytest.mark.asyncio
async def test_main_returns_2_when_invalid_args() -> None:
    """invalid args → exit code 2 (argparse SystemExit)."""
    from scripts.backfill_daily_flow import async_main

    with pytest.raises(SystemExit) as exc_info:
        await async_main([])  # alias 미지정
    assert exc_info.value.code == 2


# ---------- 8. resume — gap detection (R2 신규) ----------
#
# 시나리오: 영업일 calendar = SELECT DISTINCT trading_date FROM kiwoom.stock_daily_flow
# (전체 종목 union, exchange='KRX'). candidate 의 trading_date set 와 영업일 set 의
# 차집합이 ≥ 1 이면 진행 (gap 있음). = 0 이면 skip (완전 적재).
#
# R1 의 should_skip_resume(max_trading_date, end_date) 는 폐기 — 부분 적재 (gap) 종목을
# 잘못 skip 함. 본 R2 는 일자별 검사로 정확도 향상.


@pytest.mark.asyncio
async def test_compute_resume_remaining_codes_empty_returns_empty(
    engine: Any,
) -> None:
    """후보 0 → 빈 list."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from scripts.backfill_daily_flow import compute_resume_remaining_codes

    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        remaining = await compute_resume_remaining_codes(
            session,
            start_date=date(2025, 9, 1),
            end_date=date(2025, 9, 8),
            candidate_codes=[],
        )
        assert remaining == []


@pytest.mark.asyncio
async def test_compute_resume_remaining_codes_no_business_days_includes_all(
    engine: Any,
) -> None:
    """영업일 set = ∅ (DB 0 rows in 범위) → 모든 candidate 진행 (가드 H-8)."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from scripts.backfill_daily_flow import compute_resume_remaining_codes

    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code) "
                "VALUES ('TF701', 'f1', '0'), ('TF702', 'f2', '0') "
                "ON CONFLICT DO NOTHING"
            )
        )
    try:
        async with factory() as session:
            remaining = await compute_resume_remaining_codes(
                session,
                start_date=date(2025, 9, 1),
                end_date=date(2025, 9, 8),
                candidate_codes=["TF701", "TF702"],
            )
            assert sorted(remaining) == ["TF701", "TF702"]
    finally:
        async with factory() as session, session.begin():
            await session.execute(
                text("DELETE FROM kiwoom.stock WHERE stock_code IN ('TF701', 'TF702')")
            )


@pytest.mark.asyncio
async def test_compute_resume_remaining_codes_skips_fully_loaded(
    engine: Any,
) -> None:
    """영업일 set = 종목 trading_dates set → skip (완전 적재). KRX 만 본다."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from scripts.backfill_daily_flow import compute_resume_remaining_codes

    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    business_days = [date(2025, 9, 1), date(2025, 9, 2), date(2025, 9, 3)]
    async with factory() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO kiwoom.stock (id, stock_code, stock_name, market_code) "
                "VALUES (8801, 'TFA01', 'a', '0'), (8802, 'TFA02', 'b', '0') "
                "ON CONFLICT DO NOTHING"
            )
        )
        for code_id in (8801, 8802):
            for d in business_days:
                await session.execute(
                    text(
                        "INSERT INTO kiwoom.stock_daily_flow "
                        "(stock_id, exchange, trading_date, indc_mode, fetched_at) "
                        "VALUES (:sid, 'KRX', :td, '1', now()) ON CONFLICT DO NOTHING"
                    ).bindparams(sid=code_id, td=d)
                )
    try:
        async with factory() as session:
            remaining = await compute_resume_remaining_codes(
                session,
                start_date=date(2025, 9, 1),
                end_date=date(2025, 9, 3),
                candidate_codes=["TFA01", "TFA02"],
            )
            assert remaining == []
    finally:
        async with factory() as session, session.begin():
            await session.execute(
                text("DELETE FROM kiwoom.stock_daily_flow WHERE stock_id IN (8801, 8802)")
            )
            await session.execute(
                text("DELETE FROM kiwoom.stock WHERE stock_code IN ('TFA01', 'TFA02')")
            )


@pytest.mark.asyncio
async def test_compute_resume_remaining_codes_includes_partial_loaded_with_gap(
    engine: Any,
) -> None:
    """부분 적재 (gap ≥ 1) 종목 진행 — R2 gap detection 핵심.

    종목 A = 9/1, 9/2, 9/3 (완전) → skip
    종목 B = 9/1, 9/3 (9/2 gap) → 진행
    종목 C = ∅ → 진행
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from scripts.backfill_daily_flow import compute_resume_remaining_codes

    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session, session.begin():
        await session.execute(
            text(
                "INSERT INTO kiwoom.stock (id, stock_code, stock_name, market_code) "
                "VALUES (8901, 'TFB01', 'a', '0'), "
                "(8902, 'TFC01', 'b', '0'), "
                "(8903, 'TFD01', 'c', '0') "
                "ON CONFLICT DO NOTHING"
            )
        )
        for d in (date(2025, 9, 1), date(2025, 9, 2), date(2025, 9, 3)):
            await session.execute(
                text(
                    "INSERT INTO kiwoom.stock_daily_flow "
                    "(stock_id, exchange, trading_date, indc_mode, fetched_at) "
                    "VALUES (8901, 'KRX', :td, '1', now()) ON CONFLICT DO NOTHING"
                ).bindparams(td=d)
            )
        for d in (date(2025, 9, 1), date(2025, 9, 3)):
            await session.execute(
                text(
                    "INSERT INTO kiwoom.stock_daily_flow "
                    "(stock_id, exchange, trading_date, indc_mode, fetched_at) "
                    "VALUES (8902, 'KRX', :td, '1', now()) ON CONFLICT DO NOTHING"
                ).bindparams(td=d)
            )
    try:
        async with factory() as session:
            remaining = await compute_resume_remaining_codes(
                session,
                start_date=date(2025, 9, 1),
                end_date=date(2025, 9, 3),
                candidate_codes=["TFB01", "TFC01", "TFD01"],
            )
            assert sorted(remaining) == ["TFC01", "TFD01"]
    finally:
        async with factory() as session, session.begin():
            await session.execute(
                text("DELETE FROM kiwoom.stock_daily_flow WHERE stock_id IN (8901, 8902, 8903)")
            )
            await session.execute(
                text("DELETE FROM kiwoom.stock WHERE stock_code IN ('TFB01', 'TFC01', 'TFD01')")
            )


# ---------- 9. --max-stocks limit (운영 차단 fix 일관) ----------


@pytest.mark.asyncio
async def test_list_active_stock_codes_applies_max_stocks_limit(engine: Any) -> None:
    """`_list_active_stock_codes` 가 max_stocks 로 결과 list limit 적용 (OHLCV fix 일관)."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from scripts.backfill_daily_flow import (
        _count_active_stocks,
        _list_active_stock_codes,
    )

    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    test_codes = [f"TF80{i}" for i in range(5)]
    async with factory() as session, session.begin():
        for code in test_codes:
            await session.execute(
                text(
                    "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code, is_active) "
                    f"VALUES ('{code}', 'tf', '0', true) ON CONFLICT DO NOTHING"
                )
            )

    try:
        async with factory() as session:
            count = await _count_active_stocks(
                session,
                only_market_codes=[],
                only_stock_codes=test_codes,
                max_stocks=2,
            )
            codes = await _list_active_stock_codes(
                session,
                only_market_codes=[],
                only_stock_codes=test_codes,
                max_stocks=2,
            )
        assert count == 2
        assert len(codes) == 2
        assert all(c in test_codes for c in codes)
    finally:
        async with factory() as session, session.begin():
            await session.execute(
                text(
                    "DELETE FROM kiwoom.stock WHERE stock_code IN "
                    f"({','.join(repr(c) for c in test_codes)})"
                )
            )
