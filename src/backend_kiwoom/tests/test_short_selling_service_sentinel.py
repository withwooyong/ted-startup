"""Phase F-2 — ShortSellingBulkResult sentinel skip 분리 TDD (Step 0, red).

bulk execute 루프가 SentinelStockCodeError 를 캐치 시:
- result.total_skipped 에 카운트 (신규 필드)
- result.total_failed 미증가 (실제 실패가 아님)
- filter_alphanumeric=True 시 해당 종목 호출 자체 skip

계획서 § 4 결정 #3~#7:
- SentinelStockCodeError 별도 catch → total_skipped 증가
- ShortSellingBulkResult 에 total_skipped: int = 0 신규 필드 (현재 부재)
- filter_alphanumeric=True → ^[0-9]{6}$ 외 종목 호출 자체 skip
- 임계치 분모 유지 (failure_ratio = total_failed / total_stocks)
- 임계치 메시지에 (alphanumeric_skipped=N) 명시

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
from app.adapter.out.kiwoom._records import ShortSellingTimeType
from app.adapter.out.kiwoom.shsa import KiwoomShortSellingClient
from app.adapter.out.kiwoom.stkinfo import SentinelStockCodeError
from app.application.constants import ExchangeType
from app.application.service.short_selling_service import (
    IngestShortSellingBulkUseCase,
    IngestShortSellingUseCase,
)

# ---------------------------------------------------------------------------
# Fixtures — test_short_selling_service.py 패턴 1:1 차용
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
    res = await session.execute(
        text(
            "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code, is_active, nxt_enable) "
            "VALUES (:c, :n, :m, :a, :nx) RETURNING id"
        ).bindparams(c=code, n=name, m=market, a=is_active, nx=nxt_enable)
    )
    sid = int(res.scalar_one())
    await session.commit()
    return sid


def _make_shsa_client_stub(
    responses: dict[str, list | Exception],
) -> KiwoomShortSellingClient:
    """stock_code → list[ShortSellingRow] 또는 Exception."""
    client = AsyncMock(spec=KiwoomShortSellingClient)

    async def _fetch_trend(
        stock_code: str,
        *,
        start_date: date,
        end_date: date,
        tm_tp: ShortSellingTimeType = ShortSellingTimeType.PERIOD,
        exchange: ExchangeType = ExchangeType.KRX,
        max_pages: int = 5,
    ) -> list:
        result = responses.get(stock_code)
        if isinstance(result, Exception):
            raise result
        return result if result is not None else []

    client.fetch_trend = _fetch_trend
    return client


# ---------------------------------------------------------------------------
# ShortSellingBulkResult — total_skipped 필드 존재 단언
# ---------------------------------------------------------------------------


def test_short_selling_bulk_result_has_total_skipped_field() -> None:
    """ShortSellingBulkResult 에 total_skipped: int = 0 신규 필드가 있어야 함.

    현재 없음 → TypeError (unexpected keyword argument) = red.
    Step 1 에서 dataclass field 추가 후 green.
    """
    from app.application.dto.short_selling import ShortSellingBulkResult

    result = ShortSellingBulkResult(  # type: ignore[call-arg]
        total_stocks=3,
        total_skipped=1,  # 현재 미존재 → TypeError
    )
    assert result.total_skipped == 1  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# SentinelStockCodeError → total_skipped 증가 / total_failed 미증가
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_sentinel_goes_to_total_skipped_not_failed(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """sentinel 종목 (00088K) — SentinelStockCodeError → total_skipped=1 / total_failed=0.

    계획서 § 4 결정 #3: bulk loop 에 SentinelStockCodeError 별도 catch → skipped 분리.
    계획서 § 4 결정 #4: ShortSellingBulkResult 에 total_skipped 신규 필드.

    현재 구현: except Exception 에 잡혀 krx_outcomes 에 error 적재 → red.
    """
    await _create_active_stock(session, "005930", "삼성전자")
    await _create_active_stock(session, "00088K", "알파넘릭종목")
    await _create_active_stock(session, "005935", "삼성우")

    client = _make_shsa_client_stub(
        {
            "005930": [],
            "00088K": SentinelStockCodeError("00088K"),
            "005935": [],
        }
    )
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
    )

    assert result.total_stocks == 3

    # 핵심 단언 — sentinel 은 failed 아님
    assert result.total_skipped == 1, (  # type: ignore[attr-defined]
        f"total_skipped=1 기대 (alphanumeric 1건), 실제={result.total_skipped}"  # type: ignore[attr-defined]
    )
    assert result.total_failed == 0, (
        f"total_failed=0 기대 (sentinel 제외), 실제={result.total_failed}"
    )

    # 00088K 는 krx_outcomes 의 error 컬럼에 미포함
    error_codes = {o.stock_code for o in result.krx_outcomes if o.error is not None}
    assert "00088K" not in error_codes, (
        f"00088K 가 failed outcomes 에 포함되면 안 됨: {error_codes}"
    )

    # Step 2 MED-1: F-1 패턴 — 종목 명세 보존 단언
    assert len(result.skipped_outcomes) == 1, (  # type: ignore[attr-defined]
        f"skipped_outcomes 길이=1 기대, 실제={len(result.skipped_outcomes)}"  # type: ignore[attr-defined]
    )
    assert result.skipped_outcomes[0].stock_code == "00088K"  # type: ignore[attr-defined]
    assert result.skipped_outcomes[0].error == "sentinel_skip"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# filter_alphanumeric=True → 00088K 호출 자체 skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_filter_alphanumeric_skips_call(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """filter_alphanumeric=True → 00088K fetch_trend 호출 0회 + total_skipped=1.

    계획서 § 4 결정 #7: UseCase filter_alphanumeric: bool = False 신규 파라미터.
    True 시 ^[0-9]{6}$ 외 종목 호출 자체 skip → mock call count = 0 검증.

    현재 execute 시그니처에 filter_alphanumeric 없음 → TypeError = red.
    """
    await _create_active_stock(session, "005930", "삼성전자")
    await _create_active_stock(session, "00088K", "알파넘릭종목")
    await _create_active_stock(session, "005935", "삼성우")

    call_log: list[str] = []

    client = AsyncMock(spec=KiwoomShortSellingClient)

    async def _fetch_trend(
        stock_code: str,
        *,
        start_date: date,
        end_date: date,
        tm_tp: ShortSellingTimeType = ShortSellingTimeType.PERIOD,
        exchange: ExchangeType = ExchangeType.KRX,
        max_pages: int = 5,
    ) -> list:
        call_log.append(stock_code)
        return []

    client.fetch_trend = _fetch_trend

    single_uc = IngestShortSellingUseCase(
        session_provider=session_provider,
        shsa_client=client,
    )
    bulk_uc = IngestShortSellingBulkUseCase(
        session_provider=session_provider,
        single_use_case=single_uc,
    )

    result = await bulk_uc.execute(  # type: ignore[call-arg]
        start_date=date(2025, 5, 13),
        end_date=date(2025, 5, 19),
        filter_alphanumeric=True,  # 현재 미존재 → TypeError
    )

    assert "00088K" not in call_log, (
        f"filter_alphanumeric=True 시 00088K 호출 0회 기대, 실제 call_log={call_log}"
    )
    assert result.total_skipped == 1, (  # type: ignore[attr-defined]
        f"total_skipped=1 기대, 실제={result.total_skipped}"  # type: ignore[attr-defined]
    )
    # Step 2 MED-1: pre-filter 경로 종목 명세 보존 단언
    assert len(result.skipped_outcomes) == 1  # type: ignore[attr-defined]
    assert result.skipped_outcomes[0].stock_code == "00088K"  # type: ignore[attr-defined]
    assert result.skipped_outcomes[0].error == "alphanumeric_pre_filter"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# 임계치 경계 — total=200 / failed=10 / sentinel_skipped=15
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_threshold_denominator_excludes_sentinel(
    session: AsyncSession,
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """total=200 / failed=10 / sentinel_skipped=15 → ratio=10/200=5% (분모 유지).

    계획서 § 4 결정 #6: 임계치 분모 유지 (total_stocks, sentinel 제외 안 함).
    ratio=5% → PARTIAL_WARN_THRESHOLD (5%) 도달 → warning 발화.
    메시지에 (alphanumeric_skipped=15) 포함.

    sentinel 15건이 total_failed 에 포함되면 ratio=25/200=12.5% → 동일 warning.
    하지만 sentinel 이 total_failed 에 포함되면 안 됨 — 본 테스트로 분리 의도 보장.

    현재 total_skipped 미존재 → AttributeError = red.
    """
    # 200 종목 INSERT
    for i in range(200):
        code = f"{i:06d}"
        await _create_active_stock(session, code, f"stock-{i}")

    # 처음 10개 KiwoomBusinessError, 그 다음 15개 SentinelStockCodeError
    fail_codes = {f"{i:06d}" for i in range(10)}
    sentinel_codes = {f"{i:06d}" for i in range(10, 25)}

    async def _fetch_trend(
        stock_code: str,
        *,
        start_date: date,
        end_date: date,
        tm_tp: ShortSellingTimeType = ShortSellingTimeType.PERIOD,
        exchange: ExchangeType = ExchangeType.KRX,
        max_pages: int = 5,
    ) -> list:
        if stock_code in fail_codes:
            raise KiwoomBusinessError(api_id="ka10014", return_code=1, message="조회 실패")
        if stock_code in sentinel_codes:
            raise SentinelStockCodeError(stock_code)
        return []

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
    assert result.total_failed == 10, (
        f"total_failed=10 기대 (sentinel 제외), 실제={result.total_failed}"
    )
    assert result.total_skipped == 15, (  # type: ignore[attr-defined]
        f"total_skipped=15 기대, 실제={result.total_skipped}"  # type: ignore[attr-defined]
    )

    # ratio = 10/200 = 5% → warning 발화
    warn_msgs = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warn_msgs) >= 1, "5% 임계치 warning 없음"

    # 메시지에 alphanumeric_skipped=15 포함 (계획서 § 4 결정 #6)
    full_log = " ".join(warn_msgs)
    assert "alphanumeric_skipped=15" in full_log, (
        f"임계치 메시지에 'alphanumeric_skipped=15' 포함 기대, 실제={warn_msgs}"
    )
