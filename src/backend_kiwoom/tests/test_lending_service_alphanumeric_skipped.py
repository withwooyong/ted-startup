"""Phase F-2 — LendingStockBulkResult alphanumeric_skipped 분리 TDD (Step 0, red).

bulk execute 루프가 SentinelStockCodeError 를 캐치 시:
- result.total_alphanumeric_skipped 에 카운트 (신규 필드)
- 기존 result.total_skipped (empty 응답 의미) 는 그대로 유지
- result.total_failed 미증가
- filter_alphanumeric=True 시 해당 종목 호출 자체 skip

계획서 § 4 결정 #3/#5/#6:
- SentinelStockCodeError 별도 catch → total_alphanumeric_skipped 증가
- LendingStockBulkResult.total_alphanumeric_skipped: int = 0 신규 필드 (의미 분리)
- 기존 total_skipped 는 empty 응답 의미 유지
- 임계치 분모 유지 + 메시지에 (alphanumeric_skipped=N) 명시

본 테스트는 구현 전 의도적으로 실패 (red) — Step 1 구현 후 green 전환 대상.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import date
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.adapter.out.kiwoom._exceptions import KiwoomBusinessError
from app.adapter.out.kiwoom.slb import KiwoomLendingClient
from app.adapter.out.kiwoom.stkinfo import SentinelStockCodeError
from app.application.service.lending_service import (
    IngestLendingStockBulkUseCase,
    IngestLendingStockUseCase,
)

# ---------------------------------------------------------------------------
# Fixtures — test_lending_service.py 패턴 1:1 차용
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_lending_tables(engine: AsyncEngine) -> AsyncIterator[None]:
    """각 테스트 전후 lending + stock 테이블 정리."""
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        await s.execute(
            text("TRUNCATE kiwoom.lending_balance_kw, kiwoom.stock RESTART IDENTITY CASCADE")
        )
        await s.commit()
    yield
    async with factory() as s:
        await s.execute(
            text("TRUNCATE kiwoom.lending_balance_kw, kiwoom.stock RESTART IDENTITY CASCADE")
        )
        await s.commit()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s


@pytest.fixture
def session_provider(engine: Any) -> Callable[[], AbstractAsyncContextManager[AsyncSession]]:
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    @asynccontextmanager
    async def _provider() -> AsyncIterator[AsyncSession]:
        async with factory() as s:
            yield s

    return _provider


async def _create_stock(
    session: AsyncSession,
    code: str,
    name: str = "테스트종목",
    market: str = "0",
    *,
    is_active: bool = True,
    nxt_enable: bool = False,
) -> int:
    res = await session.execute(
        text(
            "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code, is_active, nxt_enable) "
            "VALUES (:c, :n, :m, :a, :nx) RETURNING id"
        ).bindparams(c=code, n=name, m=market, a=is_active, nx=nxt_enable)
    )
    sid = int(res.scalar_one())
    await session.commit()
    return sid


def _make_lending_client_stub(
    responses: dict[str, list | Exception],
) -> KiwoomLendingClient:
    """stock_code → list[LendingStockRow] 또는 Exception."""
    client = AsyncMock(spec=KiwoomLendingClient)

    async def _fetch_stock_trend(
        stock_code: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list:
        result = responses.get(stock_code)
        if isinstance(result, Exception):
            raise result
        return result if result is not None else []

    client.fetch_stock_trend = _fetch_stock_trend
    return client


# ---------------------------------------------------------------------------
# LendingStockBulkResult — total_alphanumeric_skipped 필드 존재 단언
# ---------------------------------------------------------------------------


def test_lending_stock_bulk_result_has_total_alphanumeric_skipped_field() -> None:
    """LendingStockBulkResult 에 total_alphanumeric_skipped: int = 0 신규 필드가 있어야 함.

    현재 없음 → TypeError (unexpected keyword argument) = red.
    기존 total_skipped 는 empty 응답 의미 — 의미 분리.
    """
    from app.application.dto.lending import LendingStockBulkResult

    result = LendingStockBulkResult(  # type: ignore[call-arg]
        start_date=date(2025, 5, 13),
        end_date=date(2025, 5, 19),
        total_stocks=3,
        total_alphanumeric_skipped=1,  # 현재 미존재 → TypeError
    )
    assert result.total_alphanumeric_skipped == 1  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# SentinelStockCodeError → total_alphanumeric_skipped 증가 / total_failed 미증가
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_sentinel_goes_to_alphanumeric_skipped_not_failed(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """sentinel 종목 (00088K) → total_alphanumeric_skipped=1 / total_failed=0 / total_skipped=0.

    계획서 § 4 결정 #5: LendingStockBulkResult.total_alphanumeric_skipped 신규 필드.
    기존 total_skipped 는 empty 응답 의미 — 별도 유지.

    현재 구현: except Exception 에 잡혀 total_failed++ → red.
    """
    await _create_stock(session, "005930", "삼성전자")
    await _create_stock(session, "00088K", "알파넘릭종목")
    await _create_stock(session, "005935", "삼성우")

    client = _make_lending_client_stub(
        {
            "005930": [],
            "00088K": SentinelStockCodeError("00088K"),
            "005935": [],
        }
    )
    single_uc = IngestLendingStockUseCase(
        session=session,
        slb_client=client,
    )
    bulk_uc = IngestLendingStockBulkUseCase(
        session=session,
        single_use_case=single_uc,
    )

    result = await bulk_uc.execute(
        start_date=date(2025, 5, 13),
        end_date=date(2025, 5, 19),
    )

    assert result.total_stocks == 3
    assert result.total_alphanumeric_skipped == 1, (  # type: ignore[attr-defined]
        f"total_alphanumeric_skipped=1 기대, 실제={result.total_alphanumeric_skipped}"  # type: ignore[attr-defined]
    )
    assert result.total_skipped == 0, (
        f"total_skipped=0 기대 (empty 응답 별도 의미 유지), 실제={result.total_skipped}"
    )
    assert result.total_failed == 0, (
        f"total_failed=0 기대 (sentinel 제외), 실제={result.total_failed}"
    )
    # Step 2 MED-1: F-1 패턴 — 종목 명세 보존 단언
    assert len(result.alphanumeric_skipped_outcomes) == 1, (  # type: ignore[attr-defined]
        f"alphanumeric_skipped_outcomes 길이=1 기대, 실제={len(result.alphanumeric_skipped_outcomes)}"  # type: ignore[attr-defined]
    )
    assert result.alphanumeric_skipped_outcomes[0].stock_code == "00088K"  # type: ignore[attr-defined]
    assert result.alphanumeric_skipped_outcomes[0].error == "sentinel_skip"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# filter_alphanumeric=True → 00088K 호출 자체 skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_filter_alphanumeric_skips_call(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """filter_alphanumeric=True → 00088K fetch_stock_trend 호출 0회 + total_alphanumeric_skipped=1.

    계획서 § 4 결정 #7: execute 시그니처에 filter_alphanumeric: bool = False 신규 파라미터.
    현재 execute 시그니처에 filter_alphanumeric 없음 → TypeError = red.
    """
    await _create_stock(session, "005930", "삼성전자")
    await _create_stock(session, "00088K", "알파넘릭종목")
    await _create_stock(session, "005935", "삼성우")

    call_log: list[str] = []
    client = AsyncMock(spec=KiwoomLendingClient)

    async def _fetch_stock_trend(
        stock_code: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list:
        call_log.append(stock_code)
        return []

    client.fetch_stock_trend = _fetch_stock_trend

    single_uc = IngestLendingStockUseCase(
        session=session,
        slb_client=client,
    )
    bulk_uc = IngestLendingStockBulkUseCase(
        session=session,
        single_use_case=single_uc,
    )

    result = await bulk_uc.execute(  # type: ignore[call-arg]
        start_date=date(2025, 5, 13),
        end_date=date(2025, 5, 19),
        filter_alphanumeric=True,  # 현재 미존재 → TypeError
    )

    assert "00088K" not in call_log, (
        f"filter_alphanumeric=True 시 00088K 호출 0회 기대, 실제={call_log}"
    )
    assert result.total_alphanumeric_skipped == 1, (  # type: ignore[attr-defined]
        f"total_alphanumeric_skipped=1 기대, 실제={result.total_alphanumeric_skipped}"  # type: ignore[attr-defined]
    )
    # Step 2 MED-1: pre-filter 경로 종목 명세 보존 단언
    assert len(result.alphanumeric_skipped_outcomes) == 1  # type: ignore[attr-defined]
    assert result.alphanumeric_skipped_outcomes[0].stock_code == "00088K"  # type: ignore[attr-defined]
    assert result.alphanumeric_skipped_outcomes[0].error == "alphanumeric_pre_filter"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# 기존 total_skipped (empty 응답) 의미 유지 단언
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_total_skipped_distinct_from_alphanumeric_skipped(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """active 종목 + adapter empty 응답 → total_alphanumeric_skipped=0 (sentinel 없음).

    Phase F-2 Step 2 H-1 A: SQL `is_active.is_(True)` 필터 복원 — bulk loop 의
    분모는 active 종목만 (short_selling_service.py 와 패턴 일관). 따라서 inactive 종목은
    bulk SQL 단계에서 제외되어 single UC 의 `outcome.skipped=True (inactive)` 경로가
    bulk loop 카운터 (`total_skipped`) 에 닿지 않는다. inactive 단건 경로는 router/단건
    호출 측에서만 발생.

    본 테스트의 새 목적: 두 카운터의 **의미 분리** 단언 — sentinel 종목이 없으면
    `total_alphanumeric_skipped == 0`, empty 응답이 있어도 `total_alphanumeric_skipped`
    는 0 (오탐 차단).
    """
    await _create_stock(session, "005930", "삼성전자")
    await _create_stock(session, "005935", "삼성우")

    # adapter mock 이 모든 종목에 대해 empty 응답 반환 — alphanumeric/sentinel 없음
    client = _make_lending_client_stub(
        {
            "005930": [],
            "005935": [],
        }
    )
    single_uc = IngestLendingStockUseCase(
        session=session,
        slb_client=client,
    )
    bulk_uc = IngestLendingStockBulkUseCase(
        session=session,
        single_use_case=single_uc,
    )

    result = await bulk_uc.execute(
        start_date=date(2025, 5, 13),
        end_date=date(2025, 5, 19),
    )

    # active 분모 2 (H-1 A 복원 후)
    assert result.total_stocks == 2, (
        f"active 종목 2건 → total_stocks=2 기대, 실제={result.total_stocks}"
    )
    # sentinel 없음 → alphanumeric_skipped=0
    assert result.total_alphanumeric_skipped == 0, (  # type: ignore[attr-defined]
        f"total_alphanumeric_skipped=0 기대 (sentinel 없음), 실제={result.total_alphanumeric_skipped}"  # type: ignore[attr-defined]
    )
    assert result.total_failed == 0
    # empty 응답은 outcome.skipped=False 이므로 bulk total_skipped 미증가
    assert result.total_skipped == 0, (
        f"empty 응답은 outcome.skipped=False → total_skipped=0 (H-1 A 복원), 실제={result.total_skipped}"
    )


# ---------------------------------------------------------------------------
# 임계치 경계 — total=100 / failed=4 / alphanumeric_skipped=7
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_threshold_denominator_excludes_sentinel(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """total=100 / failed=4 / alphanumeric_skipped=7 → ratio=4/100=4% — WARNING/ERROR 미발화.

    계획서 § 4 결정 #6: 임계치 분모 유지 (total_stocks).
    LENDING_STOCK_WARNING_THRESHOLD=5% 이므로 4% < 5% → warning 없음.
    메시지 있으면 alphanumeric_skipped=7 포함 — 단, 이 케이스는 메시지 없어야 함.

    현재 total_alphanumeric_skipped 미존재 → AttributeError = red.
    """
    for i in range(100):
        code = f"{i:06d}"
        await _create_stock(session, code, f"stock-{i}")

    fail_codes = {f"{i:06d}" for i in range(4)}
    sentinel_codes = {f"{i:06d}" for i in range(4, 11)}

    async def _fetch_stock_trend(
        stock_code: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list:
        if stock_code in fail_codes:
            raise KiwoomBusinessError(api_id="ka20068", return_code=1, message="조회 실패")
        if stock_code in sentinel_codes:
            raise SentinelStockCodeError(stock_code)
        return []

    client = AsyncMock(spec=KiwoomLendingClient)
    client.fetch_stock_trend = _fetch_stock_trend

    single_uc = IngestLendingStockUseCase(
        session=session,
        slb_client=client,
    )
    bulk_uc = IngestLendingStockBulkUseCase(
        session=session,
        single_use_case=single_uc,
    )

    with caplog.at_level(logging.WARNING, logger="app"):
        result = await bulk_uc.execute(
            start_date=date(2025, 5, 13),
            end_date=date(2025, 5, 19),
        )

    assert result.total_stocks == 100
    assert result.total_failed == 4, (
        f"total_failed=4 기대 (sentinel 제외), 실제={result.total_failed}"
    )
    assert result.total_alphanumeric_skipped == 7, (  # type: ignore[attr-defined]
        f"total_alphanumeric_skipped=7 기대, 실제={result.total_alphanumeric_skipped}"  # type: ignore[attr-defined]
    )

    # ratio = 4/100 = 4% < 5% WARN → warning/error 미발화
    warn_msgs = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warn_msgs) == 0, (
        f"4% 임계치 미달 — warning 없어야 함, 실제={warn_msgs}"
    )
