"""IngestDailyOhlcvUseCase / IngestPeriodicOhlcvUseCase 의 `_skip_base_date_validation`
키워드 옵션 (C-backfill H-1).

설계: phase-c-backfill-ohlcv.md § H-1.

CLI (scripts/backfill_ohlcv.py) 가 3년 백필을 위해 today - 365일 cap 우회.
운영 라우터는 안전 기본값 (False) 그대로 유지 — R1 invariant.

검증:
1. 디폴트 False — base_date 가 1년 초과 과거면 ValueError
2. True — base_date 가 1년 초과 과거여도 통과 (CLI backfill mode)
3. True 여도 base_date 가 미래면 ValueError (오타 가드 유지)
4. refresh_one 도 동일 동작
5. IngestDailyOhlcvUseCase + IngestPeriodicOhlcvUseCase 둘 다 동일 시그니쳐
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import date, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.adapter.out.kiwoom.chart import KiwoomChartClient
from app.application.constants import Period
from app.application.service.ohlcv_daily_service import IngestDailyOhlcvUseCase
from app.application.service.ohlcv_periodic_service import IngestPeriodicOhlcvUseCase


@pytest_asyncio.fixture(autouse=True)
async def _cleanup(engine: AsyncEngine) -> AsyncIterator[None]:
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        await s.execute(text("TRUNCATE kiwoom.stock RESTART IDENTITY CASCADE"))
        await s.commit()
    yield


@pytest.fixture
def session_provider(engine: Any) -> Callable[[], AbstractAsyncContextManager[AsyncSession]]:
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    @asynccontextmanager
    async def _provider() -> AsyncIterator[AsyncSession]:
        async with factory() as s:
            yield s

    return _provider


# ---------- IngestDailyOhlcvUseCase ----------


@pytest.mark.asyncio
async def test_daily_default_rejects_old_base_date(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """디폴트 (_skip_base_date_validation=False) — 1년 초과 과거 ValueError."""
    client = AsyncMock(spec=KiwoomChartClient)
    use_case = IngestDailyOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=False,
    )
    too_old = date.today() - timedelta(days=400)
    with pytest.raises(ValueError, match="base_date"):
        await use_case.execute(base_date=too_old)


@pytest.mark.asyncio
async def test_daily_skip_validation_allows_old_base_date(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """_skip_base_date_validation=True — 3년 과거도 통과 (CLI backfill mode)."""
    client = AsyncMock(spec=KiwoomChartClient)
    client.fetch_daily.return_value = []
    use_case = IngestDailyOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=False,
    )
    three_years_ago = date.today() - timedelta(days=365 * 3)
    # active stock 0 → total=0, raise 없이 정상 종료
    result = await use_case.execute(base_date=three_years_ago, _skip_base_date_validation=True)
    assert result.total == 0


@pytest.mark.asyncio
async def test_daily_skip_validation_still_rejects_future(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """_skip_base_date_validation=True 라도 미래는 거부 (오타 가드)."""
    client = AsyncMock(spec=KiwoomChartClient)
    use_case = IngestDailyOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=False,
    )
    future = date.today() + timedelta(days=1)
    with pytest.raises(ValueError, match="미래"):
        await use_case.execute(base_date=future, _skip_base_date_validation=True)


@pytest.mark.asyncio
async def test_daily_refresh_one_skip_validation(
    engine: AsyncEngine,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """refresh_one 도 동일 옵션 지원."""
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        await s.execute(
            text("INSERT INTO kiwoom.stock (stock_code, stock_name, market_code) VALUES ('005930', 'samsung', '0')")
        )
        await s.commit()

    client = AsyncMock(spec=KiwoomChartClient)
    client.fetch_daily.return_value = []
    use_case = IngestDailyOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=False,
    )
    three_years_ago = date.today() - timedelta(days=365 * 3)
    result = await use_case.refresh_one("005930", base_date=three_years_ago, _skip_base_date_validation=True)
    assert result.success_krx == 1


# ---------- IngestPeriodicOhlcvUseCase ----------


@pytest.mark.asyncio
async def test_periodic_default_rejects_old_base_date(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    client = AsyncMock(spec=KiwoomChartClient)
    use_case = IngestPeriodicOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=False,
    )
    too_old = date.today() - timedelta(days=400)
    with pytest.raises(ValueError, match="base_date"):
        await use_case.execute(period=Period.WEEKLY, base_date=too_old)


@pytest.mark.asyncio
async def test_periodic_skip_validation_allows_old_base_date(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """주봉 백필 — 3년 과거도 통과."""
    client = AsyncMock(spec=KiwoomChartClient)
    client.fetch_weekly.return_value = []
    client.fetch_monthly.return_value = []
    use_case = IngestPeriodicOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=False,
    )
    three_years_ago = date.today() - timedelta(days=365 * 3)
    result = await use_case.execute(
        period=Period.WEEKLY,
        base_date=three_years_ago,
        _skip_base_date_validation=True,
    )
    assert result.total == 0


@pytest.mark.asyncio
async def test_periodic_skip_validation_still_rejects_future(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    client = AsyncMock(spec=KiwoomChartClient)
    use_case = IngestPeriodicOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=False,
    )
    future = date.today() + timedelta(days=1)
    with pytest.raises(ValueError, match="미래"):
        await use_case.execute(
            period=Period.MONTHLY,
            base_date=future,
            _skip_base_date_validation=True,
        )


@pytest.mark.asyncio
async def test_periodic_skip_validation_yearly_executes(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """C-4 — YEARLY 활성 후엔 _skip_base_date_validation 이 정상 동작 (NotImplementedError 부재).

    active stock 0건이라 fetch_yearly 미호출. base_date 가 3년 전이라도 skip 으로 통과.
    """
    client = AsyncMock(spec=KiwoomChartClient)
    client.fetch_yearly.return_value = []
    use_case = IngestPeriodicOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=False,
    )
    three_years_ago = date.today() - timedelta(days=365 * 3)
    result = await use_case.execute(
        period=Period.YEARLY,
        base_date=three_years_ago,
        _skip_base_date_validation=True,
    )
    # active stock 0건이라 total=0
    assert result.total == 0
    assert result.failed == 0
