"""IngestDailyOhlcvUseCase (C-1β) — execute + refresh_one + per-stock skip + KRX/NXT 분리.

설계: endpoint-06-ka10081.md § 6.3 + ADR § 16.6.

Phase B-γ-2 SyncStockFundamentalUseCase 패턴 차용 — per-stock try/except + KiwoomError
catch + outcome.error 격리 + 다음 종목 진행. KRX/NXT 분리 ingest (settings flag 게이팅).

lazy fetch (c) batch fail-closed (사용자 결정, ADR § 13.4.1):
- active stock 만 대상, ensure_exists 호출 안 함
- 응답 stk_cd 메아리가 미지 종목으로 박혀와도 chart.py base 비교가 차단

검증:
1. 정상 sync — KRX 만 적재 (nxt_collection_enabled=False 디폴트)
2. nxt_collection_enabled=True + nxt_enable=True 종목 → KRX + NXT 둘 다
3. nxt_collection_enabled=True + nxt_enable=False 종목 → KRX 만
4. KRX 실패 → NXT 는 시도 (계획서 § 4.2 (a) 독립 호출)
5. KRX 성공 + NXT KiwoomBusinessError → KRX 적재 + NXT outcome 실패
6. only_market_codes 필터
7. base_date 디폴트 today + target_date_range 검증 (today - 365 ~ today)
8. base_date 미래 / 1년 초과 과거 → ValueError
9. refresh_one — 단건 새로고침 (Stock 마스터 active 검증)
10. 비활성 stock 미순회
11. 빈 응답 (적재 0)
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

from app.adapter.out.kiwoom._exceptions import (
    KiwoomBusinessError,
    KiwoomCredentialRejectedError,
)
from app.adapter.out.kiwoom.chart import (
    DailyChartRow,
    KiwoomChartClient,
)
from app.adapter.out.persistence.repositories.stock_price import StockPriceRepository
from app.application.constants import ExchangeType
from app.application.exceptions import StockMasterNotFoundError
from app.application.service.ohlcv_daily_service import (
    IngestDailyOhlcvUseCase,
    OhlcvSyncOutcome,
    OhlcvSyncResult,
)


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s


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
    return int(res.scalar_one())


def _row(dt: str = "20250908", close: str = "70100") -> DailyChartRow:
    return DailyChartRow(
        cur_prc=close, trde_qty="9263135", trde_prica="648525", dt=dt,
        open_pric="69800", high_pric="70500", low_pric="69600",
        pred_pre="+600", pred_pre_sig="2", trde_tern_rt="+0.16",
    )


def _stub_client(
    krx_responses: dict[str, list[DailyChartRow] | Exception] | None = None,
    nxt_responses: dict[str, list[DailyChartRow] | Exception] | None = None,
) -> KiwoomChartClient:
    """stock_code+exchange → list 또는 Exception."""
    krx_responses = krx_responses or {}
    nxt_responses = nxt_responses or {}
    client = AsyncMock(spec=KiwoomChartClient)

    async def _fetch(
        stock_code: str,
        *,
        base_date: date,
        exchange: ExchangeType = ExchangeType.KRX,
        adjusted: bool = True,
        max_pages: int | None = None,
        since_date: date | None = None,
    ) -> list[DailyChartRow]:
        store = krx_responses if exchange is ExchangeType.KRX else nxt_responses
        result = store.get(stock_code, [])
        if isinstance(result, Exception):
            raise result
        return result

    client.fetch_daily = _fetch
    return client


# ---------- 1. 정상 KRX-only ----------


@pytest.mark.asyncio
async def test_execute_krx_only_when_nxt_disabled(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    """nxt_collection_enabled=False (디폴트) → KRX 만 적재."""
    await _create_active_stock(session, "005930", "삼성전자", "0", nxt_enable=True)
    await session.commit()

    client = _stub_client(krx_responses={"005930": [_row("20250908")]})
    uc = IngestDailyOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=False,  # 디폴트
    )

    result = await uc.execute(base_date=date(2025, 9, 8))

    assert isinstance(result, OhlcvSyncResult)
    assert result.total == 1
    assert result.success_krx == 1
    assert result.success_nxt == 0
    assert result.failed == 0


# ---------- 2. nxt_collection_enabled + nxt_enable=True ----------


@pytest.mark.asyncio
async def test_execute_collects_both_krx_and_nxt(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    """nxt_collection_enabled=True + stock.nxt_enable=True → KRX + NXT 모두."""
    await _create_active_stock(session, "005930", "삼성전자", "0", nxt_enable=True)
    await session.commit()

    client = _stub_client(
        krx_responses={"005930": [_row("20250908")]},
        nxt_responses={"005930": [_row("20250908", "70200")]},
    )
    uc = IngestDailyOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=True,
    )
    result = await uc.execute(base_date=date(2025, 9, 8))

    assert result.success_krx == 1
    assert result.success_nxt == 1


# ---------- 3. nxt_collection_enabled=True + nxt_enable=False ----------


@pytest.mark.asyncio
async def test_execute_skips_nxt_when_stock_nxt_disable(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    """nxt_collection_enabled=True 여도 stock.nxt_enable=False 면 NXT skip."""
    await _create_active_stock(session, "035720", "카카오", "0", nxt_enable=False)
    await session.commit()

    client = _stub_client(krx_responses={"035720": [_row("20250908")]})
    uc = IngestDailyOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=True,
    )
    result = await uc.execute(base_date=date(2025, 9, 8))

    assert result.success_krx == 1
    assert result.success_nxt == 0


# ---------- 4. KRX 실패 → NXT 독립 호출 ----------


@pytest.mark.asyncio
async def test_execute_krx_fail_does_not_block_nxt(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    """KRX KiwoomBusinessError → NXT 시도 (계획서 § 4.2 (a) 독립 호출)."""
    await _create_active_stock(session, "005930", "삼성전자", "0", nxt_enable=True)
    await session.commit()

    client = _stub_client(
        krx_responses={"005930": KiwoomBusinessError(api_id="ka10081", return_code=1, message="조회 실패")},
        nxt_responses={"005930": [_row("20250908")]},
    )
    uc = IngestDailyOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=True,
    )
    result = await uc.execute(base_date=date(2025, 9, 8))

    assert result.success_krx == 0
    assert result.success_nxt == 1
    assert result.failed == 1
    assert result.errors[0].exchange == "KRX"
    assert result.errors[0].error_class == "KiwoomBusinessError"


# ---------- 5. KRX 성공 + NXT 실패 ----------


@pytest.mark.asyncio
async def test_execute_krx_success_nxt_fail_records_partial(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    await _create_active_stock(session, "005930", "삼성전자", "0", nxt_enable=True)
    await session.commit()

    client = _stub_client(
        krx_responses={"005930": [_row("20250908")]},
        nxt_responses={"005930": KiwoomCredentialRejectedError("401")},
    )
    uc = IngestDailyOhlcvUseCase(
        session_provider=session_provider,
        chart_client=client,
        nxt_collection_enabled=True,
    )
    result = await uc.execute(base_date=date(2025, 9, 8))

    assert result.success_krx == 1
    assert result.success_nxt == 0
    assert result.failed == 1
    assert result.errors[0].exchange == "NXT"


# ---------- 6. only_market_codes 필터 ----------


@pytest.mark.asyncio
async def test_execute_only_market_codes_filters(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    await _create_active_stock(session, "005930", "KOSPI종목", "0")
    await _create_active_stock(session, "100100", "KOSDAQ종목", "10")
    await session.commit()

    client = _stub_client(
        krx_responses={
            "005930": [_row("20250908")],
            "100100": [_row("20250908")],
        }
    )
    uc = IngestDailyOhlcvUseCase(
        session_provider=session_provider, chart_client=client, nxt_collection_enabled=False
    )
    result = await uc.execute(base_date=date(2025, 9, 8), only_market_codes=["0"])

    assert result.total == 1
    assert result.success_krx == 1


# ---------- 7-8. base_date 검증 ----------


@pytest.mark.asyncio
async def test_execute_base_date_defaults_to_today(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    """base_date 미지정 → today."""
    await _create_active_stock(session, "005930", "삼성전자")
    await session.commit()

    client = _stub_client(krx_responses={"005930": [_row("20250908")]})
    uc = IngestDailyOhlcvUseCase(
        session_provider=session_provider, chart_client=client, nxt_collection_enabled=False
    )
    result = await uc.execute()

    assert result.base_date == date.today()


@pytest.mark.asyncio
async def test_execute_rejects_future_base_date(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """target_date 미래 → ValueError."""
    client = _stub_client()
    uc = IngestDailyOhlcvUseCase(
        session_provider=session_provider, chart_client=client, nxt_collection_enabled=False
    )

    future = date.today() + timedelta(days=1)
    with pytest.raises(ValueError, match="base_date"):
        await uc.execute(base_date=future)


@pytest.mark.asyncio
async def test_execute_rejects_too_old_base_date(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """today - 365일 초과 과거 → ValueError (사용자 승인)."""
    client = _stub_client()
    uc = IngestDailyOhlcvUseCase(
        session_provider=session_provider, chart_client=client, nxt_collection_enabled=False
    )

    too_old = date.today() - timedelta(days=400)
    with pytest.raises(ValueError, match="base_date"):
        await uc.execute(base_date=too_old)


@pytest.mark.asyncio
async def test_execute_accepts_one_year_old_base_date(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    """today - 365일 경계는 허용."""
    await _create_active_stock(session, "005930", "삼성전자")
    await session.commit()

    client = _stub_client(krx_responses={"005930": [_row("20250101")]})
    uc = IngestDailyOhlcvUseCase(
        session_provider=session_provider, chart_client=client, nxt_collection_enabled=False
    )
    one_year_ago = date.today() - timedelta(days=365)
    result = await uc.execute(base_date=one_year_ago)
    assert result.base_date == one_year_ago


# ---------- 9. refresh_one ----------


@pytest.mark.asyncio
async def test_refresh_one_returns_ingest_count(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    """단건 새로고침 — KRX 시계열 적재 후 row 수 반환."""
    await _create_active_stock(session, "005930", "삼성전자")
    await session.commit()

    client = _stub_client(
        krx_responses={"005930": [_row("20250908"), _row("20250905", "69500")]}
    )
    uc = IngestDailyOhlcvUseCase(
        session_provider=session_provider, chart_client=client, nxt_collection_enabled=False
    )

    result = await uc.refresh_one("005930", base_date=date(2025, 9, 8))

    assert result.success_krx == 1
    assert result.total == 1


@pytest.mark.asyncio
async def test_refresh_one_raises_when_stock_master_missing(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """Stock 마스터 미존재 → ValueError. ensure_exists 미사용 (lazy fetch (c))."""
    client = _stub_client()
    uc = IngestDailyOhlcvUseCase(
        session_provider=session_provider, chart_client=client, nxt_collection_enabled=False
    )

    with pytest.raises(StockMasterNotFoundError):
        await uc.refresh_one("005930", base_date=date(2025, 9, 8))


# ---------- 10. 비활성 stock 미순회 ----------


@pytest.mark.asyncio
async def test_execute_skips_inactive_stocks(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    await _create_active_stock(session, "005930", "삼성전자", is_active=True)
    await _create_active_stock(session, "999999", "폐지", is_active=False)
    await session.commit()

    called: list[str] = []

    async def _fetch(
        stock_code: str,
        *,
        base_date: date,
        exchange: ExchangeType = ExchangeType.KRX,
        adjusted: bool = True,
        max_pages: int | None = None,
        since_date: date | None = None,
    ) -> list[DailyChartRow]:
        called.append(stock_code)
        return [_row("20250908")]

    client = AsyncMock(spec=KiwoomChartClient)
    client.fetch_daily = _fetch
    uc = IngestDailyOhlcvUseCase(
        session_provider=session_provider, chart_client=client, nxt_collection_enabled=False
    )
    result = await uc.execute(base_date=date(2025, 9, 8))

    assert called == ["005930"]
    assert result.total == 1


# ---------- 11. 빈 응답 ----------


@pytest.mark.asyncio
async def test_execute_empty_response_records_success_with_zero_rows(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    """키움이 빈 list 응답 → success=1, row 0 적재."""
    stock_id = await _create_active_stock(session, "005930")
    await session.commit()

    client = _stub_client(krx_responses={"005930": []})
    uc = IngestDailyOhlcvUseCase(
        session_provider=session_provider, chart_client=client, nxt_collection_enabled=False
    )
    result = await uc.execute(base_date=date(2025, 9, 8))

    assert result.success_krx == 1  # 호출 성공
    repo = StockPriceRepository(session)
    found = await repo.find_range(stock_id, exchange=ExchangeType.KRX, start=date(2025, 1, 1), end=date(2025, 12, 31))
    assert found == []  # row 0


# ---------- 12. 적재 실제 검증 ----------


@pytest.mark.asyncio
async def test_execute_persists_rows_to_correct_table(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    """KRX 응답이 stock_price_krx 에 정확히 영속화."""
    stock_id = await _create_active_stock(session, "005930", nxt_enable=True)
    await session.commit()

    client = _stub_client(
        krx_responses={"005930": [_row("20250908"), _row("20250905", "69500")]},
        nxt_responses={"005930": [_row("20250908", "70200")]},
    )
    uc = IngestDailyOhlcvUseCase(
        session_provider=session_provider, chart_client=client, nxt_collection_enabled=True
    )
    await uc.execute(base_date=date(2025, 9, 8))

    repo = StockPriceRepository(session)
    krx = await repo.find_range(
        stock_id, exchange=ExchangeType.KRX, start=date(2025, 1, 1), end=date(2025, 12, 31)
    )
    nxt = await repo.find_range(
        stock_id, exchange=ExchangeType.NXT, start=date(2025, 1, 1), end=date(2025, 12, 31)
    )

    assert len(krx) == 2
    assert len(nxt) == 1


def test_outcome_dataclass_is_frozen_slots() -> None:
    """OhlcvSyncOutcome 응답 본문 echo 차단 (B-α/B-β M-2 패턴) + frozen slots."""
    o = OhlcvSyncOutcome(stock_code="005930", exchange="KRX", error_class="KiwoomBusinessError")
    assert o.stock_code == "005930"
    assert o.exchange == "KRX"
    assert o.error_class == "KiwoomBusinessError"


# ---------- 2a-M2 회귀 — refresh_one KRX KiwoomError propagates ----------


@pytest.mark.asyncio
async def test_refresh_one_propagates_krx_kiwoom_error(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    """KRX 호출 실패 → KiwoomError 그대로 raise (라우터가 4xx/5xx 매핑)."""
    await _create_active_stock(session, "005930", "삼성전자")
    await session.commit()

    err = KiwoomBusinessError(api_id="ka10081", return_code=1, message="조회 실패")
    client = _stub_client(krx_responses={"005930": err})
    uc = IngestDailyOhlcvUseCase(
        session_provider=session_provider, chart_client=client, nxt_collection_enabled=False
    )

    with pytest.raises(KiwoomBusinessError):
        await uc.refresh_one("005930", base_date=date(2025, 9, 8))


# ---------- 2a-M1 / 2b-L3 회귀 — refresh_one NXT 격리 ----------


@pytest.mark.asyncio
async def test_refresh_one_isolates_nxt_failure_after_krx_success(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    """KRX 성공 후 NXT KiwoomError → errors 격리 (전체 raise 안 함)."""
    await _create_active_stock(session, "005930", "삼성전자", nxt_enable=True)
    await session.commit()

    client = _stub_client(
        krx_responses={"005930": [_row("20250908")]},
        nxt_responses={
            "005930": KiwoomBusinessError(api_id="ka10081", return_code=1, message="NXT 실패")
        },
    )
    uc = IngestDailyOhlcvUseCase(
        session_provider=session_provider, chart_client=client, nxt_collection_enabled=True
    )

    result = await uc.refresh_one("005930", base_date=date(2025, 9, 8))

    assert result.success_krx == 1
    assert result.success_nxt == 0
    assert result.failed == 1
    assert len(result.errors) == 1
    assert result.errors[0].exchange == "NXT"
    assert result.errors[0].error_class == "KiwoomBusinessError"


# ---------- 2b-M2 회귀 — only_market_codes 화이트리스트 ----------


@pytest.mark.asyncio
async def test_execute_rejects_unknown_market_code(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """미등록 시장 코드 → ValueError (silent no-op 차단)."""
    client = _stub_client()
    uc = IngestDailyOhlcvUseCase(
        session_provider=session_provider, chart_client=client, nxt_collection_enabled=False
    )

    with pytest.raises(ValueError, match="unknown market_code"):
        await uc.execute(base_date=date(2025, 9, 8), only_market_codes=["99"])


@pytest.mark.asyncio
async def test_execute_accepts_known_market_codes(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """등록된 시장 코드 (StockListMarketType.value) 는 통과."""
    client = _stub_client()
    uc = IngestDailyOhlcvUseCase(
        session_provider=session_provider, chart_client=client, nxt_collection_enabled=False
    )

    # KOSPI=0, KOSDAQ=10, REIT=6 — 모두 known
    result = await uc.execute(base_date=date(2025, 9, 8), only_market_codes=["0", "10", "6"])
    assert result.total == 0  # active stock 없음 — but no error raised
