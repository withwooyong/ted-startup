"""IngestLendingStockUseCase 단건 sentinel catch 회귀 (Phase F-3 D-7).

라우터 정규식 (^[0-9]{6}$) 우회 호출 시에도 단건 UseCase 가 SentinelStockCodeError 를
catch 하여 outcome.error = SkipReason.SENTINEL_SKIP.value 로 변환 (defense-in-depth).

D-7 설계 근거 (lending 측):
- ka20068 단건 UseCase 는 라우터가 없는 경로에서 직접 호출될 수 있음 (CLI / bulk / 테스트)
- alphanumeric stock_code (예: 000A1B, 00088K) 가 단건 UseCase 에 도달 시
  SentinelStockCodeError raise → outcome.error = SkipReason.SENTINEL_SKIP.value
- bulk loop 의 sentinel 분리 (F-2 결정 #5) 와 일관성 유지

본 테스트는 구현 전 의도적으로 실패 (red) — Step 1 구현 후 green 전환 대상.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.adapter.out.kiwoom._exceptions import KiwoomBusinessError
from app.adapter.out.kiwoom.slb import KiwoomLendingClient
from app.adapter.out.kiwoom.stkinfo import SentinelStockCodeError
from app.application.dto._shared import SkipReason  # type: ignore[import]  # Step 1 에서 생성
from app.application.service.lending_service import IngestLendingStockUseCase

# ---------------------------------------------------------------------------
# Fixtures — test_lending_service_alphanumeric_skipped.py 패턴 1:1 차용
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


async def _create_stock(
    session: AsyncSession,
    code: str,
    name: str = "테스트종목",
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


def _make_sentinel_raising_client() -> KiwoomLendingClient:
    """fetch_stock_trend 호출 시 SentinelStockCodeError 를 raise 하는 stub client."""
    from unittest.mock import AsyncMock

    client = AsyncMock(spec=KiwoomLendingClient)

    async def _fetch_stock_trend(
        stock_code: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list:
        raise SentinelStockCodeError(stock_code)

    client.fetch_stock_trend = _fetch_stock_trend
    return client


def _make_kiwoom_error_client() -> KiwoomLendingClient:
    """fetch_stock_trend 호출 시 KiwoomBusinessError 를 raise 하는 stub client."""
    from unittest.mock import AsyncMock

    client = AsyncMock(spec=KiwoomLendingClient)

    async def _fetch_stock_trend(
        stock_code: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list:
        raise KiwoomBusinessError(api_id="ka20068", return_code=1, message="조회 실패")

    client.fetch_stock_trend = _fetch_stock_trend
    return client


def _make_normal_client() -> KiwoomLendingClient:
    """fetch_stock_trend 호출 시 빈 list 를 반환하는 정상 stub client."""
    from unittest.mock import AsyncMock

    client = AsyncMock(spec=KiwoomLendingClient)
    client.fetch_stock_trend.return_value = []
    return client


# ---------------------------------------------------------------------------
# D-7 방어적 catch — SentinelStockCodeError → outcome.error = SkipReason.SENTINEL_SKIP.value
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_sentinel_catch_returns_outcome_with_skip_reason(
    session: AsyncSession,
) -> None:
    """alphanumeric stock_code (000A1B) → SentinelStockCodeError catch → outcome.error == SkipReason.SENTINEL_SKIP.value.

    D-7 defense-in-depth: 라우터 정규식 우회 경로에서 단건 UseCase 가 직접 호출될 경우에도
    SentinelStockCodeError 를 graceful 하게 처리. outcome.error = SkipReason.SENTINEL_SKIP.value.

    현재 구현: execute 내부에 SentinelStockCodeError catch 없음 → 예외 전파 = red.
    Step 1 구현 후 green.
    """
    # DB 에 alphanumeric stock_code 로 stock 등록 (stock master 조회 통과용)
    await _create_stock(session, "000A1B", "알파넘릭테스트")

    client = _make_sentinel_raising_client()
    uc = IngestLendingStockUseCase(session=session, slb_client=client)

    outcome = await uc.execute("000A1B")

    # 핵심 단언 — SentinelStockCodeError 가 catch 되어 outcome 으로 변환
    assert outcome.error == SkipReason.SENTINEL_SKIP.value, (
        f"outcome.error=SkipReason.SENTINEL_SKIP.value 기대, 실제={outcome.error!r}"
    )
    assert outcome.upserted == 0, f"upserted=0 기대, 실제={outcome.upserted}"
    assert outcome.fetched == 0, f"fetched=0 기대, 실제={outcome.fetched}"
    assert outcome.skipped is False, "skipped=False 기대 (sentinel 은 error 경로)"


@pytest.mark.asyncio
async def test_execute_normal_path_unchanged(
    session: AsyncSession,
) -> None:
    """정상 path 회귀 — sentinel catch 추가가 기존 동작 깨지 않음.

    D-7 catch 추가 후 정상 종목 (6자리 숫자) 의 execute 가 기존과 동일하게 동작해야 함.
    fetch_stock_trend → 빈 list → upserted=0, error=None, skipped=False.
    """
    await _create_stock(session, "005930", "삼성전자")
    client = _make_normal_client()
    uc = IngestLendingStockUseCase(session=session, slb_client=client)

    outcome = await uc.execute("005930")

    # 정상 path — sentinel catch 에 걸리지 않음
    assert outcome.error is None, f"정상 종목에서 error 없어야 함, 실제={outcome.error!r}"
    assert outcome.skipped is False
    assert outcome.upserted == 0  # 빈 응답이므로 0


@pytest.mark.asyncio
async def test_execute_kiwoom_error_still_propagates_via_outcome(
    session: AsyncSession,
) -> None:
    """KiwoomBusinessError (네트워크/비즈니스) 는 기존 동작 유지 — outcome.error 에 return_code 포함.

    D-7 catch 가 SentinelStockCodeError 만 catch 해야 하며,
    KiwoomBusinessError 는 기존 except 분기에서 처리되어 outcome.error 에 설정.
    SentinelStockCodeError catch 추가가 KiwoomBusinessError 처리 경로를 방해하지 않음.
    """
    await _create_stock(session, "005930", "삼성전자")
    client = _make_kiwoom_error_client()
    uc = IngestLendingStockUseCase(session=session, slb_client=client)

    outcome = await uc.execute("005930")

    # KiwoomBusinessError 는 outcome.error 에 return_code 포함
    assert outcome.error is not None, "KiwoomBusinessError → outcome.error 있어야 함"
    assert "1" in outcome.error, f"return_code=1 이 outcome.error 에 포함 기대, 실제={outcome.error!r}"
    # sentinel 경로로 오분류되면 안 됨
    assert outcome.error != SkipReason.SENTINEL_SKIP.value, (
        f"KiwoomBusinessError 가 sentinel 로 분류되면 안 됨, 실제={outcome.error!r}"
    )
