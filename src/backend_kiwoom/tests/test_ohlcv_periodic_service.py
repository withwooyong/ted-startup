"""IngestPeriodicOhlcvUseCase + RefreshOnePeriodicOhlcvUseCase (C-3β) — 주/월봉 적재 + period dispatch.

설계: phase-c-3-weekly-monthly-ohlcv.md § 3.2 / § 5.2.

ka10081 의 IngestDailyOhlcvUseCase (C-1β) 패턴 ~95% 복제 + period dispatch:
- WEEKLY → KiwoomChartClient.fetch_weekly + StockPricePeriodicRepository.upsert_many(period=WEEKLY)
- MONTHLY → fetch_monthly + upsert_many(period=MONTHLY)
- YEARLY → NotImplementedError (P2 chunk 진입 시 활성화, H-3)
- DAILY → ValueError (별도 UseCase 사용 안내, H-3)

R1 정착 패턴 5종 전면 적용:
1. errors: tuple[Outcome, ...] (mutable list 노출 금지)
2. StockMasterNotFoundError(ValueError) + raise (subclass first 순서)
3. fetched_at: datetime non-Optional (ORM)
4. only_market_codes max_length=2
5. NXT path except Exception 격리 (partial-failure)

검증 (ka10081 14 시나리오 ~95% 복제 + period 차이점):
1. 정상 sync — KRX 만 적재 (nxt_collection_enabled=False)
2. nxt_enabled=True + nxt_enable=True → KRX + NXT 둘 다
3. KRX 실패 → NXT 시도 (독립 호출)
4. KRX 성공 + NXT KiwoomBusinessError → KRX 적재 + NXT outcome 실패
5. KRX 성공 + NXT 비-Kiwoom Exception → 격리 (R1 L-5)
6. only_market_codes 필터 (max_length=2 검증)
7. base_date 디폴트 today + target_date_range
8. base_date 미래 → ValueError
9. refresh_one — 단건 새로고침 (Stock active 검증)
10. refresh_one — Stock 미존재 → StockMasterNotFoundError
11. period=WEEKLY → fetch_weekly 호출 (fetch_monthly 호출 안 함)
12. period=MONTHLY → fetch_monthly 호출
13. period=YEARLY → NotImplementedError (Migration 미작성)
14. period=DAILY → ValueError (별도 UseCase 사용)
15. errors 가 tuple 인지 (R1 invariant 회귀)
"""

from __future__ import annotations

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
from app.adapter.out.kiwoom.chart import (
    KiwoomChartClient,
    MonthlyChartRow,
    WeeklyChartRow,
)
from app.application.constants import Period
from app.application.exceptions import StockMasterNotFoundError
from app.application.service.ohlcv_periodic_service import (
    IngestPeriodicOhlcvUseCase,
    OhlcvSyncOutcome,
    OhlcvSyncResult,
)


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_ohlcv_tables(engine: AsyncEngine) -> AsyncIterator[None]:
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        await s.execute(text("TRUNCATE kiwoom.stock RESTART IDENTITY CASCADE"))
        await s.commit()
    yield
    async with factory() as s:
        await s.execute(text("TRUNCATE kiwoom.stock RESTART IDENTITY CASCADE"))
        await s.commit()


@pytest.fixture
def session_provider(engine: Any) -> Callable[[], AbstractAsyncContextManager[AsyncSession]]:
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    @asynccontextmanager
    async def _provider() -> AsyncIterator[AsyncSession]:
        async with factory() as s:
            yield s

    return _provider


async def _create_active_stock(
    session: AsyncSession,
    code: str,
    name: str = "test",
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


def _make_weekly_row(dt: str = "20250901", cur_prc: str = "69500") -> WeeklyChartRow:
    return WeeklyChartRow(
        cur_prc=cur_prc,
        trde_qty="56700518",
        trde_prica="3922030535087",
        dt=dt,
        open_pric="68400",
        high_pric="70400",
        low_pric="67500",
        pred_pre="-200",
        pred_pre_sig="5",
        trde_tern_rt="+0.95",
    )


def _make_monthly_row(dt: str = "20250901", cur_prc: str = "78900") -> MonthlyChartRow:
    return MonthlyChartRow(
        cur_prc=cur_prc,
        trde_qty="215040968",
        trde_prica="15774571011618",
        dt=dt,
        open_pric="68400",
        high_pric="79500",
        low_pric="67500",
        pred_pre="+9200",
        pred_pre_sig="2",
        trde_tern_rt="+13.45",
    )


def _make_yearly_row(dt: str = "20250102", cur_prc: str = "78900") -> "YearlyChartRow":
    """ka10094 응답 7 필드만 (pred_pre/pred_pre_sig/trde_tern_rt 없음, C-4)."""
    from app.adapter.out.kiwoom.chart import YearlyChartRow

    return YearlyChartRow(
        cur_prc=cur_prc,
        trde_qty="215040968",
        trde_prica="15774571011618",
        dt=dt,
        open_pric="68400",
        high_pric="79500",
        low_pric="67500",
    )


def _make_chart_client(
    *,
    weekly_rows: list[WeeklyChartRow] | None = None,
    monthly_rows: list[MonthlyChartRow] | None = None,
    yearly_rows: list["YearlyChartRow"] | None = None,
    weekly_exc: Exception | None = None,
    monthly_exc: Exception | None = None,
    yearly_exc: Exception | None = None,
) -> KiwoomChartClient:
    """KiwoomChartClient stub — fetch_weekly / fetch_monthly / fetch_yearly mock (C-4)."""
    client = AsyncMock(spec=KiwoomChartClient)
    if weekly_exc is not None:
        client.fetch_weekly.side_effect = weekly_exc
    else:
        client.fetch_weekly.return_value = weekly_rows or []
    if monthly_exc is not None:
        client.fetch_monthly.side_effect = monthly_exc
    else:
        client.fetch_monthly.return_value = monthly_rows or []
    if yearly_exc is not None:
        client.fetch_yearly.side_effect = yearly_exc
    else:
        client.fetch_yearly.return_value = yearly_rows or []
    # fetch_daily 은 본 UseCase 가 호출하면 안 됨
    client.fetch_daily.side_effect = AssertionError(
        "IngestPeriodicOhlcvUseCase 가 fetch_daily 를 호출하면 안 됨 (period 분기 위반)"
    )
    return client


# ---------- 1. 정상 sync — KRX 만 적재 ----------


@pytest.mark.asyncio
async def test_execute_weekly_krx_only_when_nxt_disabled(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    await _create_active_stock(session, "005930", market="0")
    client = _make_chart_client(weekly_rows=[_make_weekly_row()])

    use_case = IngestPeriodicOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=False,
    )
    result = await use_case.execute(period=Period.WEEKLY, base_date=date(2025, 9, 8))

    assert isinstance(result, OhlcvSyncResult)
    assert result.total == 1
    assert result.success_krx == 1
    assert result.success_nxt == 0
    assert result.failed == 0
    assert result.errors == ()
    client.fetch_weekly.assert_awaited_once()
    client.fetch_monthly.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_monthly_krx_only(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    await _create_active_stock(session, "005930")
    client = _make_chart_client(monthly_rows=[_make_monthly_row()])

    use_case = IngestPeriodicOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=False,
    )
    result = await use_case.execute(period=Period.MONTHLY, base_date=date(2025, 9, 8))

    assert result.success_krx == 1
    client.fetch_monthly.assert_awaited_once()
    client.fetch_weekly.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_weekly_skips_alpha_stock_codes(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """ka10082/83 호환 가드 — daily 와 동일 정책 (ETF/ETN/우선주 사전 skip)."""
    await _create_active_stock(session, "005930", market="0")  # 호환
    await _create_active_stock(session, "0000D0", market="0")  # ETF — skip
    await _create_active_stock(session, "00088K", market="0")  # 우선주 — skip
    client = _make_chart_client(weekly_rows=[_make_weekly_row()])

    use_case = IngestPeriodicOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=False,
    )
    result = await use_case.execute(period=Period.WEEKLY, base_date=date(2025, 9, 8))

    # 호환 1 종목만 호출. ETF/우선주 2 종목은 사전 가드로 skip.
    assert result.total == 1
    assert result.success_krx == 1
    assert result.failed == 0
    client.fetch_weekly.assert_awaited_once()


# ---------- 2. NXT 분기 ----------


@pytest.mark.asyncio
async def test_execute_weekly_with_nxt_when_both_enabled(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    await _create_active_stock(session, "005930", nxt_enable=True)
    client = _make_chart_client(weekly_rows=[_make_weekly_row()])

    use_case = IngestPeriodicOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=True,
    )
    result = await use_case.execute(period=Period.WEEKLY, base_date=date(2025, 9, 8))

    assert result.success_krx == 1
    assert result.success_nxt == 1
    assert client.fetch_weekly.await_count == 2  # KRX + NXT


@pytest.mark.asyncio
async def test_execute_skips_nxt_when_stock_nxt_enable_false(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    await _create_active_stock(session, "005930", nxt_enable=False)
    client = _make_chart_client(weekly_rows=[_make_weekly_row()])

    use_case = IngestPeriodicOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=True,  # settings True 지만 stock.nxt_enable=False
    )
    result = await use_case.execute(period=Period.WEEKLY, base_date=date(2025, 9, 8))

    assert result.success_krx == 1
    assert result.success_nxt == 0
    assert client.fetch_weekly.await_count == 1  # KRX 만


# ---------- 3. KRX 실패 → NXT 시도 (독립) ----------


@pytest.mark.asyncio
async def test_execute_krx_fails_nxt_still_attempted(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    await _create_active_stock(session, "005930", nxt_enable=True)
    client = AsyncMock(spec=KiwoomChartClient)
    client.fetch_weekly.side_effect = [
        KiwoomBusinessError(api_id="ka10082", return_code=999, message="krx 실패"),
        [_make_weekly_row()],  # NXT 는 성공
    ]
    client.fetch_monthly.return_value = []
    client.fetch_daily.side_effect = AssertionError("호출 금지")

    use_case = IngestPeriodicOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=True,
    )
    result = await use_case.execute(period=Period.WEEKLY, base_date=date(2025, 9, 8))

    assert result.success_krx == 0
    assert result.success_nxt == 1
    assert result.failed == 1
    assert len(result.errors) == 1
    assert result.errors[0].exchange == "KRX"
    assert client.fetch_weekly.await_count == 2


# ---------- 4. KRX 성공 + NXT 비-Kiwoom Exception 격리 (R1 L-5) ----------


@pytest.mark.asyncio
async def test_execute_isolates_nxt_non_kiwoom_exception(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """R1 L-5 — NXT path 의 비-Kiwoom Exception 도 격리 (partial-failure 모델)."""
    await _create_active_stock(session, "005930", nxt_enable=True)
    client = AsyncMock(spec=KiwoomChartClient)
    client.fetch_weekly.side_effect = [
        [_make_weekly_row()],  # KRX 성공
        RuntimeError("NXT 비-Kiwoom 예외"),  # NXT unexpected
    ]
    client.fetch_monthly.return_value = []
    client.fetch_daily.side_effect = AssertionError("호출 금지")

    use_case = IngestPeriodicOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=True,
    )
    result = await use_case.execute(period=Period.WEEKLY, base_date=date(2025, 9, 8))

    assert result.success_krx == 1
    assert result.success_nxt == 0
    assert result.failed == 1
    assert result.errors[0].exchange == "NXT"
    assert result.errors[0].error_class == "RuntimeError"


# ---------- 5. only_market_codes 필터 ----------


@pytest.mark.asyncio
async def test_execute_filters_by_market_codes(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    await _create_active_stock(session, "005930", market="0")  # KOSPI
    await _create_active_stock(session, "020000", market="10")  # KOSDAQ
    client = _make_chart_client(weekly_rows=[_make_weekly_row()])

    use_case = IngestPeriodicOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=False,
    )
    result = await use_case.execute(
        period=Period.WEEKLY,
        base_date=date(2025, 9, 8),
        only_market_codes=["0"],
    )

    assert result.total == 1
    assert client.fetch_weekly.await_count == 1


@pytest.mark.asyncio
async def test_execute_unknown_market_codes_raises(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    client = _make_chart_client()
    use_case = IngestPeriodicOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=False,
    )
    with pytest.raises(ValueError, match="unknown market"):
        await use_case.execute(period=Period.WEEKLY, only_market_codes=["99"])


# ---------- 6. base_date 검증 ----------


@pytest.mark.asyncio
async def test_execute_future_base_date_raises(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    client = _make_chart_client()
    use_case = IngestPeriodicOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=False,
    )
    from datetime import timedelta

    future = date.today() + timedelta(days=1)
    with pytest.raises(ValueError, match="base_date"):
        await use_case.execute(period=Period.WEEKLY, base_date=future)


# ---------- 7. period dispatch — H-3 검증 ----------


@pytest.mark.asyncio
async def test_execute_yearly_krx_only(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """YEARLY 활성 (C-4) — KRX 만 적재, NXT 는 skip (plan § 12.2 #3 yearly_nxt_disabled).

    nxt_collection_enabled=True 이고 stock.nxt_enable=True 라도 YEARLY 는 NXT 호출 안 함.
    """
    await _create_active_stock(session, "005930", nxt_enable=True)
    client = _make_chart_client(yearly_rows=[_make_yearly_row()])

    use_case = IngestPeriodicOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=True,
    )
    result = await use_case.execute(period=Period.YEARLY, base_date=date(2025, 9, 8))

    assert result.success_krx == 1
    assert result.success_nxt == 0  # YEARLY NXT skip
    assert result.failed == 0
    # fetch_yearly KRX 1회만, NXT 미호출
    client.fetch_yearly.assert_awaited_once()


# ---------- 8. refresh_one ----------


@pytest.mark.asyncio
async def test_refresh_one_weekly_success(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    await _create_active_stock(session, "005930")
    client = _make_chart_client(weekly_rows=[_make_weekly_row()])

    use_case = IngestPeriodicOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=False,
    )
    result = await use_case.refresh_one("005930", period=Period.WEEKLY, base_date=date(2025, 9, 8))

    assert result.success_krx == 1
    assert result.failed == 0
    assert result.errors == ()


@pytest.mark.asyncio
async def test_refresh_one_stock_master_not_found(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """R1 M-2 — StockMasterNotFoundError 전용 예외 raise."""
    client = _make_chart_client()
    use_case = IngestPeriodicOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=False,
    )
    with pytest.raises(StockMasterNotFoundError) as exc_info:
        await use_case.refresh_one("999999", period=Period.WEEKLY, base_date=date(2025, 9, 8))
    assert exc_info.value.stock_code == "999999"
    # ValueError subclass 검증
    assert isinstance(exc_info.value, ValueError)


@pytest.mark.asyncio
async def test_refresh_one_isolates_nxt_kiwoom_error(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """R1 L-5 — refresh_one 의 NXT path 도 격리 (KRX 적재 후 NXT 실패는 200 + failed=1)."""
    await _create_active_stock(session, "005930", nxt_enable=True)
    client = AsyncMock(spec=KiwoomChartClient)
    client.fetch_weekly.side_effect = [
        [_make_weekly_row()],
        KiwoomBusinessError(api_id="ka10082", return_code=999, message="nxt err"),
    ]
    client.fetch_monthly.return_value = []
    client.fetch_daily.side_effect = AssertionError("호출 금지")

    use_case = IngestPeriodicOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=True,
    )
    result = await use_case.refresh_one("005930", period=Period.WEEKLY, base_date=date(2025, 9, 8))

    assert result.success_krx == 1
    assert result.success_nxt == 0
    assert result.failed == 1
    assert result.errors[0].exchange == "NXT"


@pytest.mark.asyncio
async def test_refresh_one_yearly_krx_only(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """YEARLY refresh — KRX 만 호출 (plan § 12.2 #3 yearly_nxt_disabled).

    NXT enabled 라도 YEARLY 는 NXT skip 가드 적용.
    """
    await _create_active_stock(session, "005930", nxt_enable=True)
    client = _make_chart_client(yearly_rows=[_make_yearly_row()])
    use_case = IngestPeriodicOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=True,
    )
    result = await use_case.refresh_one("005930", period=Period.YEARLY, base_date=date(2025, 9, 8))

    assert result.success_krx == 1
    assert result.success_nxt == 0  # YEARLY NXT skip
    assert result.failed == 0
    client.fetch_yearly.assert_awaited_once()


# ---------- 9. 비활성 stock 미순회 ----------


@pytest.mark.asyncio
async def test_execute_skips_inactive_stocks(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    await _create_active_stock(session, "005930", is_active=False)
    client = _make_chart_client(weekly_rows=[_make_weekly_row()])

    use_case = IngestPeriodicOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=False,
    )
    result = await use_case.execute(period=Period.WEEKLY, base_date=date(2025, 9, 8))

    assert result.total == 0
    client.fetch_weekly.assert_not_awaited()


# ---------- 10. R1 invariant — errors 가 tuple ----------


@pytest.mark.asyncio
async def test_result_errors_is_tuple_not_list(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """R1 invariant — errors 필드가 tuple (mutable list 노출 금지)."""
    await _create_active_stock(session, "005930", nxt_enable=True)
    client = AsyncMock(spec=KiwoomChartClient)
    client.fetch_weekly.side_effect = [
        [_make_weekly_row()],
        KiwoomBusinessError(api_id="ka10082", return_code=999, message="err"),
    ]
    client.fetch_monthly.return_value = []
    client.fetch_daily.side_effect = AssertionError("호출 금지")

    use_case = IngestPeriodicOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=True,
    )
    result = await use_case.execute(period=Period.WEEKLY, base_date=date(2025, 9, 8))

    assert type(result.errors) is tuple
    assert isinstance(result.errors[0], OhlcvSyncOutcome)


# ---------- 11. 빈 응답 ----------


@pytest.mark.asyncio
async def test_execute_empty_response_still_success(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    await _create_active_stock(session, "005930")
    client = _make_chart_client(weekly_rows=[])

    use_case = IngestPeriodicOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=False,
    )
    result = await use_case.execute(period=Period.WEEKLY, base_date=date(2025, 9, 8))

    assert result.success_krx == 1  # 빈 응답도 호출 성공
    assert result.failed == 0
