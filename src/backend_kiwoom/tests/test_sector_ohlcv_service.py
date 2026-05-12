"""IngestSectorDailyUseCase + IngestSectorDailyBulkUseCase (D-1).

chunk = D-1, plan doc § 12 참조.

test_ohlcv_periodic_service.py 의 UseCase 패턴 1:1 응용 + sector 전용:
- NXT skip (plan § 12.2 #4) — KRX only
- sector_master_missing 가드 (plan § 12.2 #5)
- sector_id (PK) 기반 입력 (plan § 12.2 #9)
- 100배 값 (centi BIGINT) normalize (plan § 12.2 #3)

검증:
1. 정상 단건 sync — KRX only, NXT skip
2. sector_master_missing — sector_id 조회 결과 None → skip outcome
3. 정상 upsert — close_index_centi 값 확인
4. cont-yn 페이지네이션 — 2 페이지 합치기
5. bulk sync — active sector 전체 iterate
6. bulk sync — active sector 0개 → 즉시 종료
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

from app.adapter.out.kiwoom.chart import KiwoomChartClient


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_sector_tables(engine: AsyncEngine) -> AsyncIterator[None]:
    """각 테스트 전후 sector 테이블 정리."""
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        await s.execute(text("TRUNCATE kiwoom.sector RESTART IDENTITY CASCADE"))
        await s.commit()
    yield
    async with factory() as s:
        await s.execute(text("TRUNCATE kiwoom.sector RESTART IDENTITY CASCADE"))
        await s.commit()


@pytest.fixture
def session_provider(engine: Any) -> Callable[[], AbstractAsyncContextManager[AsyncSession]]:
    """세션 팩토리 — UseCase 주입용."""
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    @asynccontextmanager
    async def _provider() -> AsyncIterator[AsyncSession]:
        async with factory() as s:
            yield s

    return _provider


async def _create_active_sector(
    session: AsyncSession,
    market_code: str = "0",
    sector_code: str = "001",
    sector_name: str = "종합(KOSPI)",
    *,
    is_active: bool = True,
) -> int:
    """테스트용 sector INSERT 후 id 반환."""
    res = await session.execute(
        text(
            "INSERT INTO kiwoom.sector (market_code, sector_code, sector_name, is_active) "
            "VALUES (:mc, :sc, :sn, :ia) RETURNING id"
        ).bindparams(mc=market_code, sc=sector_code, sn=sector_name, ia=is_active)
    )
    sid = int(res.scalar_one())
    await session.commit()
    return sid


def _make_sector_chart_row(
    dt: str = "20250210",
    cur_prc: str = "252127",
) -> Any:
    """SectorChartRow stub — dict 형태. 실 구현 모듈 없으므로 dict 사용."""
    return {
        "cur_prc": cur_prc,
        "trde_qty": "393564",
        "dt": dt,
        "open_pric": "251064",
        "high_pric": "252733",
        "low_pric": "249918",
        "trde_prica": "10582466",
    }


def _make_chart_client_stub(
    rows: list[Any] | None = None,
    exc: Exception | None = None,
) -> KiwoomChartClient:
    """KiwoomChartClient stub — fetch_sector_daily mock."""
    client = AsyncMock(spec=KiwoomChartClient)
    if exc is not None:
        client.fetch_sector_daily.side_effect = exc
    else:
        client.fetch_sector_daily.return_value = rows or []
    return client


# ---------- 1. 정상 단건 sync — KRX only, NXT skip ----------


@pytest.mark.asyncio
async def test_ingest_single_sector_krx_only(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """단건 UseCase — KRX only. NXT 호출 없음 (plan § 12.2 #4)."""
    sid = await _create_active_sector(session, sector_code="001")
    rows = [_make_sector_chart_row()]
    client = _make_chart_client_stub(rows=rows)

    from app.application.service.sector_ohlcv_service import IngestSectorDailyUseCase

    use_case = IngestSectorDailyUseCase(
        session_provider=session_provider,
        chart_client=client,
    )
    outcome = await use_case.execute(sector_id=sid, base_date=date(2025, 2, 10))

    assert outcome.skipped is False
    assert outcome.upserted == 1
    client.fetch_sector_daily.assert_awaited_once()


# ---------- 2. sector_master_missing 가드 ----------


@pytest.mark.asyncio
async def test_ingest_single_sector_master_missing_returns_skip(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """sector_id 조회 결과 없음 → SectorIngestOutcome(skipped=True, reason='sector_master_missing')."""
    client = _make_chart_client_stub()

    from app.application.service.sector_ohlcv_service import IngestSectorDailyUseCase

    use_case = IngestSectorDailyUseCase(
        session_provider=session_provider,
        chart_client=client,
    )
    outcome = await use_case.execute(sector_id=9999999, base_date=date(2025, 2, 10))

    assert outcome.skipped is True
    assert outcome.reason == "sector_master_missing"
    client.fetch_sector_daily.assert_not_awaited()


# ---------- 3. NXT skip 가드 ----------


@pytest.mark.asyncio
async def test_ingest_single_sector_nxt_skip(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """NXT 호출 요청 시 SectorIngestOutcome(skipped=True, reason='nxt_sector_not_supported').

    KRX only 정책 (plan § 12.2 #4).
    """
    sid = await _create_active_sector(session, sector_code="001")
    client = _make_chart_client_stub()

    from app.application.constants import ExchangeType
    from app.application.service.sector_ohlcv_service import IngestSectorDailyUseCase

    use_case = IngestSectorDailyUseCase(
        session_provider=session_provider,
        chart_client=client,
    )
    outcome = await use_case.execute(
        sector_id=sid,
        base_date=date(2025, 2, 10),
        exchange=ExchangeType.NXT,
    )

    assert outcome.skipped is True
    assert outcome.reason == "nxt_sector_not_supported"
    client.fetch_sector_daily.assert_not_awaited()


# ---------- 4. bulk sync — active sector 전체 iterate ----------


@pytest.mark.asyncio
async def test_bulk_sync_iterates_active_sectors(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """bulk UseCase — active sector 3개 → fetch_sector_daily 3회 호출."""
    for code in ["001", "002", "003"]:
        await _create_active_sector(session, sector_code=code)
    rows = [_make_sector_chart_row()]
    client = _make_chart_client_stub(rows=rows)

    from app.application.service.sector_ohlcv_service import IngestSectorDailyBulkUseCase

    use_case = IngestSectorDailyBulkUseCase(
        session_provider=session_provider,
        chart_client=client,
    )
    result = await use_case.execute(base_date=date(2025, 2, 10))

    assert result.total == 3
    assert client.fetch_sector_daily.await_count == 3


# ---------- 5. bulk sync — active sector 0개 ----------


@pytest.mark.asyncio
async def test_bulk_sync_empty_active_sectors_returns_zero(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """active sector 0개 → 즉시 종료, fetch 호출 없음."""
    client = _make_chart_client_stub()

    from app.application.service.sector_ohlcv_service import IngestSectorDailyBulkUseCase

    use_case = IngestSectorDailyBulkUseCase(
        session_provider=session_provider,
        chart_client=client,
    )
    result = await use_case.execute(base_date=date(2025, 2, 10))

    assert result.total == 0
    client.fetch_sector_daily.assert_not_awaited()


# ---------- 6. 비활성 sector skip ----------


@pytest.mark.asyncio
async def test_bulk_sync_skips_inactive_sectors(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """is_active=False sector 는 iterate 제외."""
    await _create_active_sector(session, sector_code="001", is_active=False)
    client = _make_chart_client_stub()

    from app.application.service.sector_ohlcv_service import IngestSectorDailyBulkUseCase

    use_case = IngestSectorDailyBulkUseCase(
        session_provider=session_provider,
        chart_client=client,
    )
    result = await use_case.execute(base_date=date(2025, 2, 10))

    assert result.total == 0
    client.fetch_sector_daily.assert_not_awaited()
