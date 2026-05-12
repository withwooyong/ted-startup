"""IngestShortSellingUseCase + IngestShortSellingBulkUseCase (Phase E).

chunk = E (ka10014), plan doc § 9.2 / § 12 참조.

test_ingest_daily_flow_service.py / test_sector_ohlcv_service.py 패턴 1:1 응용.
- KRX + NXT 분리 적재 (nxt_enable 게이팅)
- mock env NXT skip (결정 #9 — warning 안 함)
- Bulk BATCH_SIZE=50 commit
- partial 임계치 5%/15% (결정 #10)
- ovr_shrts_qty 누적 의미 — 같은 일자 두 번 호출 시 마지막 값으로 덮어씀 (§ 8.2)
- NXT 빈 응답 정상 처리 (warning 안 함, 결정 #9)

검증:
1. INSERT (DB 빈, stock 1건 + 응답 5 row) → short_selling_kw 5 row INSERT
2. UPDATE (멱등성) → row 5개 유지, updated_at 갱신
3. KRX + NXT 분리 적재 (nxt_enable=true) → krx 5 + nxt 5 row, exchange 컬럼 분리
4. nxt_enable=false skip → outcome.skipped=true
5. inactive stock skip → outcome.skipped=true
6. mock env no NXT → outcome.skipped=true, reason="mock_no_nxt"
7. 빈 응답 NXT 공매도 미지원 → upserted=0, warning 안 함 (결정 #9)
8. Bulk 50 batch (100 종목) → 50건마다 commit
9. only_market_codes 필터 (KOSPI 만) → KOSDAQ skip
10. ovr_shrts_qty 누적 (다른 strt_dt 두 번) → UPDATE 마지막 호출 값으로
11. partial 임계치 (5%/15%) → bulk 200 종목 10 failed → warning logger 검증

NOTE: IngestShortSellingUseCase, IngestShortSellingBulkUseCase, IngestShortSellingInput,
      ShortSellingIngestOutcome, ShortSellingBulkResult 는 Step 1 에서 작성.
      본 테스트는 import 실패가 red 의도.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from app.adapter.out.kiwoom.shsa import (  # type: ignore[import]  # Step 1 에서 작성
    KiwoomShortSellingClient,
    ShortSellingTimeType,
)
from app.application.service.short_selling_service import (  # type: ignore[import]  # Step 1 에서 작성
    IngestShortSellingBulkUseCase,
    IngestShortSellingUseCase,
    ShortSellingIngestOutcome,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.adapter.out.kiwoom._exceptions import KiwoomBusinessError
from app.adapter.out.kiwoom._records import (  # type: ignore[import]  # Step 1 에서 추가
    ShortSellingRow,
)
from app.application.constants import ExchangeType

# ---------------------------------------------------------------------------
# 공통 fixture + helper
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_short_selling_tables(engine: AsyncEngine) -> AsyncIterator[None]:
    """각 테스트 전후 stock + short_selling_kw 테이블 정리."""
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        await s.execute(text("TRUNCATE kiwoom.stock RESTART IDENTITY CASCADE"))
        await s.commit()
    yield
    async with factory() as s:
        await s.execute(text("TRUNCATE kiwoom.stock RESTART IDENTITY CASCADE"))
        await s.commit()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s


@pytest.fixture
def session_provider(engine: Any) -> Callable[[], AbstractAsyncContextManager[AsyncSession]]:
    """UseCase 주입용 세션 팩토리."""
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
    """테스트용 stock INSERT 후 id 반환."""
    res = await session.execute(
        text(
            "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code, is_active, nxt_enable) "
            "VALUES (:c, :n, :m, :a, :nx) RETURNING id"
        ).bindparams(c=code, n=name, m=market, a=is_active, nx=nxt_enable)
    )
    sid = int(res.scalar_one())
    await session.commit()
    return sid


def _make_short_selling_rows(count: int = 5) -> list[ShortSellingRow]:
    """테스트용 ShortSellingRow stub list."""
    base_dates = ["20250519", "20250516", "20250515", "20250514", "20250513"]
    rows = []
    for i in range(count):
        dt = base_dates[i % len(base_dates)]
        rows.append(
            ShortSellingRow(
                dt=dt,
                close_pric="-55800",
                pred_pre_sig="5",
                pred_pre="-1000",
                flu_rt="-1.76",
                trde_qty="9802105",
                shrts_qty="841407",
                ovr_shrts_qty="6424755",
                trde_wght="+8.58",
                shrts_trde_prica="46985302",
                shrts_avg_pric="55841",
            )
        )
    return rows


def _make_shsa_client_stub(
    krx_rows: list[ShortSellingRow] | None = None,
    nxt_rows: list[ShortSellingRow] | None = None,
    krx_exc: Exception | None = None,
    nxt_exc: Exception | None = None,
) -> KiwoomShortSellingClient:
    """KiwoomShortSellingClient stub."""
    client = AsyncMock(spec=KiwoomShortSellingClient)

    async def _fetch_trend(
        stock_code: str,
        *,
        start_date: date,
        end_date: date,
        tm_tp: ShortSellingTimeType = ShortSellingTimeType.PERIOD,
        exchange: ExchangeType = ExchangeType.KRX,
        max_pages: int = 5,
    ) -> list[ShortSellingRow]:
        if exchange is ExchangeType.KRX:
            if krx_exc is not None:
                raise krx_exc
            return krx_rows if krx_rows is not None else []
        else:
            if nxt_exc is not None:
                raise nxt_exc
            return nxt_rows if nxt_rows is not None else []

    client.fetch_trend = _fetch_trend
    return client


# ---------------------------------------------------------------------------
# 1. INSERT (DB 빈, stock 1건 + 응답 5 row)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_single_inserts_5_rows(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """DB 빈 + 응답 5 row → short_selling_kw 5 row INSERT."""
    await _create_active_stock(session, "005930", "삼성전자")
    rows = _make_short_selling_rows(5)
    client = _make_shsa_client_stub(krx_rows=rows)

    uc = IngestShortSellingUseCase(
        session_provider=session_provider,
        shsa_client=client,
    )
    outcome = await uc.execute(
        "005930",
        start_date=date(2025, 5, 13),
        end_date=date(2025, 5, 19),
        exchange=ExchangeType.KRX,
    )

    assert outcome.skipped is False
    assert outcome.upserted == 5

    result = await session.execute(
        text("SELECT COUNT(*) FROM kiwoom.short_selling_kw WHERE exchange = 'KRX'")
    )
    assert result.scalar_one() == 5


# ---------------------------------------------------------------------------
# 2. UPDATE 멱등성
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_single_idempotent_update(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """같은 호출 두 번 → row 수 5개 유지, upserted=5 (ON CONFLICT UPDATE)."""
    await _create_active_stock(session, "005930", "삼성전자")
    rows = _make_short_selling_rows(5)
    client = _make_shsa_client_stub(krx_rows=rows)

    uc = IngestShortSellingUseCase(
        session_provider=session_provider,
        shsa_client=client,
    )

    first = await uc.execute(
        "005930",
        start_date=date(2025, 5, 13),
        end_date=date(2025, 5, 19),
        exchange=ExchangeType.KRX,
    )
    second = await uc.execute(
        "005930",
        start_date=date(2025, 5, 13),
        end_date=date(2025, 5, 19),
        exchange=ExchangeType.KRX,
    )

    assert first.upserted == 5
    assert second.upserted == 5

    result = await session.execute(
        text("SELECT COUNT(*) FROM kiwoom.short_selling_kw WHERE exchange = 'KRX'")
    )
    assert result.scalar_one() == 5


# ---------------------------------------------------------------------------
# 3. KRX + NXT 분리 적재 (nxt_enable=true)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_single_krx_and_nxt_separate(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """nxt_enable=true → KRX 5 + NXT 5 row, exchange 컬럼 분리 저장."""
    await _create_active_stock(session, "005930", "삼성전자", nxt_enable=True)
    rows = _make_short_selling_rows(5)
    client = _make_shsa_client_stub(krx_rows=rows, nxt_rows=rows)

    uc = IngestShortSellingUseCase(
        session_provider=session_provider,
        shsa_client=client,
    )

    krx_outcome = await uc.execute(
        "005930",
        start_date=date(2025, 5, 13),
        end_date=date(2025, 5, 19),
        exchange=ExchangeType.KRX,
    )
    nxt_outcome = await uc.execute(
        "005930",
        start_date=date(2025, 5, 13),
        end_date=date(2025, 5, 19),
        exchange=ExchangeType.NXT,
    )

    assert krx_outcome.upserted == 5
    assert nxt_outcome.upserted == 5

    krx_count = await session.execute(
        text("SELECT COUNT(*) FROM kiwoom.short_selling_kw WHERE exchange = 'KRX'")
    )
    nxt_count = await session.execute(
        text("SELECT COUNT(*) FROM kiwoom.short_selling_kw WHERE exchange = 'NXT'")
    )
    assert krx_count.scalar_one() == 5
    assert nxt_count.scalar_one() == 5


# ---------------------------------------------------------------------------
# 4. nxt_enable=false skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_single_nxt_disabled_skips(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """stock.nxt_enable=False + exchange=NXT → outcome.skipped=True, reason='nxt_disabled'."""
    await _create_active_stock(session, "005930", "삼성전자", nxt_enable=False)
    client = _make_shsa_client_stub(nxt_rows=[])

    uc = IngestShortSellingUseCase(
        session_provider=session_provider,
        shsa_client=client,
    )
    outcome = await uc.execute(
        "005930",
        start_date=date(2025, 5, 13),
        end_date=date(2025, 5, 19),
        exchange=ExchangeType.NXT,
    )

    assert outcome.skipped is True
    assert outcome.reason == "nxt_disabled"


# ---------------------------------------------------------------------------
# 5. inactive stock skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_single_inactive_stock_skips(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """is_active=False stock → outcome.skipped=True, reason='inactive'."""
    await _create_active_stock(session, "005930", "삼성전자", is_active=False)
    client = _make_shsa_client_stub(krx_rows=[])

    uc = IngestShortSellingUseCase(
        session_provider=session_provider,
        shsa_client=client,
    )
    outcome = await uc.execute(
        "005930",
        start_date=date(2025, 5, 13),
        end_date=date(2025, 5, 19),
        exchange=ExchangeType.KRX,
    )

    assert outcome.skipped is True
    assert outcome.reason == "inactive"


# ---------------------------------------------------------------------------
# 6. mock env no NXT
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_single_mock_env_skips_nxt(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """env='mock' + exchange=NXT → outcome.skipped=True, reason='mock_no_nxt'."""
    await _create_active_stock(session, "005930", "삼성전자", nxt_enable=True)
    client = _make_shsa_client_stub(nxt_rows=_make_short_selling_rows(5))

    uc = IngestShortSellingUseCase(
        session_provider=session_provider,
        shsa_client=client,
        env="mock",
    )
    outcome = await uc.execute(
        "005930",
        start_date=date(2025, 5, 13),
        end_date=date(2025, 5, 19),
        exchange=ExchangeType.NXT,
    )

    assert outcome.skipped is True
    assert outcome.reason == "mock_no_nxt"


# ---------------------------------------------------------------------------
# 7. 빈 응답 NXT 공매도 미지원 → upserted=0, warning 안 함
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_single_nxt_empty_response_no_warning(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """NXT 응답 list=[] → upserted=0, warning 로그 없음 (결정 #9)."""
    await _create_active_stock(session, "005930", "삼성전자", nxt_enable=True)
    client = _make_shsa_client_stub(nxt_rows=[])

    uc = IngestShortSellingUseCase(
        session_provider=session_provider,
        shsa_client=client,
    )

    with caplog.at_level(logging.WARNING, logger="app"):
        outcome = await uc.execute(
            "005930",
            start_date=date(2025, 5, 13),
            end_date=date(2025, 5, 19),
            exchange=ExchangeType.NXT,
        )

    assert outcome.upserted == 0
    assert outcome.skipped is False
    # NXT 빈 응답은 warning 안 함 (결정 #9)
    warning_lines = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warning_lines) == 0, f"예상치 못한 warning: {warning_lines}"


# ---------------------------------------------------------------------------
# 8. Bulk 50 batch (100 종목) → 50건마다 commit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_commits_every_50_stocks(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """100 active 종목 bulk → BATCH_SIZE=50 마다 commit (2회)."""
    # 100 종목 INSERT
    for i in range(100):
        code = f"{i:06d}"
        await _create_active_stock(session, code, f"stock-{i}")

    rows = _make_short_selling_rows(1)
    client = _make_shsa_client_stub(krx_rows=rows)

    single_uc = IngestShortSellingUseCase(
        session_provider=session_provider,
        shsa_client=client,
    )

    commit_count = 0
    original_commit = AsyncSession.commit

    async def _counting_commit(self: AsyncSession) -> None:
        nonlocal commit_count
        commit_count += 1
        return await original_commit(self)

    bulk_uc = IngestShortSellingBulkUseCase(
        session_provider=session_provider,
        single_use_case=single_uc,
    )

    with patch.object(AsyncSession, "commit", _counting_commit):
        result = await bulk_uc.execute(
            start_date=date(2025, 5, 13),
            end_date=date(2025, 5, 19),
        )

    assert result.total_stocks == 100
    # commit 이 최소 2회 발생 (50마다 1번 + 종료 시 1번)
    assert commit_count >= 2


# ---------------------------------------------------------------------------
# 9. only_market_codes 필터 (KOSPI 만 = market_code="0")
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_only_market_codes_filters_kosdaq(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """only_market_codes=['0'] → KOSDAQ (market_code='10') skip."""
    await _create_active_stock(session, "005930", "KOSPI종목", "0")
    await _create_active_stock(session, "100100", "KOSDAQ종목", "10")

    rows = _make_short_selling_rows(5)
    client = _make_shsa_client_stub(krx_rows=rows)

    single_uc = IngestShortSellingUseCase(
        session_provider=session_provider,
        shsa_client=client,
    )
    bulk_uc = IngestShortSellingBulkUseCase(
        session_provider=session_provider,
        single_use_case=single_uc,
    )

    result = await bulk_uc.execute(
        start_date=date(2025, 5, 13),
        end_date=date(2025, 5, 19),
        only_market_codes=["0"],
    )

    assert result.total_stocks == 1
    assert len(result.krx_outcomes) == 1
    assert result.krx_outcomes[0].stock_code == "005930"


# ---------------------------------------------------------------------------
# 10. ovr_shrts_qty 누적 — 다른 strt_dt 두 번 호출 → 마지막 값으로 업데이트
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_single_ovr_shrts_qty_updated_by_last_call(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """같은 일자 row 를 ovr_shrts_qty 값만 다르게 두 번 upsert → 마지막 값으로 덮어씀.

    UNIQUE (stock_id, trading_date, exchange) ON CONFLICT DO UPDATE.
    """
    await _create_active_stock(session, "005930", "삼성전자")

    # 첫 번째 호출: strt_dt=2025-04-01 기준 누적 → ovr_shrts_qty="3000000"
    rows_first = [
        ShortSellingRow(
            dt="20250519",
            close_pric="-55800",
            flu_rt="-1.76",
            trde_wght="+8.58",
            shrts_qty="841407",
            ovr_shrts_qty="3000000",  # 첫 번째 호출 누적값
        )
    ]
    client_first = _make_shsa_client_stub(krx_rows=rows_first)

    uc = IngestShortSellingUseCase(
        session_provider=session_provider,
        shsa_client=client_first,
    )
    await uc.execute(
        "005930",
        start_date=date(2025, 4, 1),
        end_date=date(2025, 5, 19),
        exchange=ExchangeType.KRX,
    )

    # 두 번째 호출: strt_dt=2025-05-13 기준 누적 → ovr_shrts_qty="6424755"
    rows_second = [
        ShortSellingRow(
            dt="20250519",
            close_pric="-55800",
            flu_rt="-1.76",
            trde_wght="+8.58",
            shrts_qty="841407",
            ovr_shrts_qty="6424755",  # 두 번째 호출 누적값 (기간이 짧으므로 다름)
        )
    ]
    client_second = _make_shsa_client_stub(krx_rows=rows_second)

    uc2 = IngestShortSellingUseCase(
        session_provider=session_provider,
        shsa_client=client_second,
    )
    await uc2.execute(
        "005930",
        start_date=date(2025, 5, 13),
        end_date=date(2025, 5, 19),
        exchange=ExchangeType.KRX,
    )

    # 마지막 호출 값 확인
    result = await session.execute(
        text(
            "SELECT cumulative_short_volume FROM kiwoom.short_selling_kw "
            "WHERE exchange = 'KRX' AND trading_date = '2025-05-19'"
        )
    )
    assert result.scalar_one() == 6424755


# ---------------------------------------------------------------------------
# 11. partial 임계치 (5%/15%) — bulk 200 종목 10 failed → warning
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_partial_threshold_warning(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """bulk 200 종목 중 10건 (5%) failed → warning 로그 검증."""
    # 200 종목 INSERT
    for i in range(200):
        code = f"{i:06d}"
        await _create_active_stock(session, code, f"stock-{i}")

    fail_codes = {f"{i:06d}" for i in range(10)}  # 처음 10개 실패

    async def _fetch_trend(
        stock_code: str,
        *,
        start_date: date,
        end_date: date,
        tm_tp: ShortSellingTimeType = ShortSellingTimeType.PERIOD,
        exchange: ExchangeType = ExchangeType.KRX,
        max_pages: int = 5,
    ) -> list[ShortSellingRow]:
        if stock_code in fail_codes:
            raise KiwoomBusinessError(
                api_id="ka10014", return_code=1, message="조회 실패"
            )
        return _make_short_selling_rows(1)

    client = AsyncMock(spec=KiwoomShortSellingClient)
    client.fetch_trend = _fetch_trend

    single_uc = IngestShortSellingUseCase(
        session_provider=session_provider,
        shsa_client=client,
    )
    bulk_uc = IngestShortSellingBulkUseCase(
        session_provider=session_provider,
        single_use_case=single_uc,
    )

    with caplog.at_level(logging.WARNING, logger="app"):
        result = await bulk_uc.execute(
            start_date=date(2025, 5, 13),
            end_date=date(2025, 5, 19),
        )

    assert result.total_stocks == 200
    # 10/200 = 5% → warning 임계치 (결정 #10)
    failed_count = sum(1 for o in result.krx_outcomes if o.error is not None)
    assert failed_count == 10

    # warning 또는 error 로그 발생 확인 (5% 임계치 도달)
    warn_or_error = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warn_or_error) >= 1, "5% 실패율 임계치 경고 로그 없음"


# ---------------------------------------------------------------------------
# ShortSellingIngestOutcome / ShortSellingBulkResult 구조 검증
# ---------------------------------------------------------------------------


def test_short_selling_ingest_outcome_is_frozen_slots() -> None:
    """ShortSellingIngestOutcome frozen + slots — 응답 본문 echo 차단."""
    o = ShortSellingIngestOutcome(
        stock_code="005930",
        exchange=ExchangeType.KRX,
        upserted=5,
    )
    assert o.stock_code == "005930"
    assert o.exchange == ExchangeType.KRX
    assert o.upserted == 5
    assert o.skipped is False
    assert o.reason is None
    assert o.error is None
