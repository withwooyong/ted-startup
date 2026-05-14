"""Phase F-1 — FundamentalSyncResult sentinel skip 분리 TDD (Step 0, red).

bulk execute 루프가 SentinelStockCodeError 를 캐치 시:
- result.skipped 에 적재 (별도 field)
- result.failed 미증가 (실제 실패가 아님)
- result.skipped_count == len(result.skipped)

계획서 § 4 결정 #5 / #6:
- SentinelStockCodeError 별도 catch → result.skipped 적재
- result.failed_count 의미 = 실제 실패 (sentinel skip 제외)

본 테스트는 구현 전 의도적으로 실패 (red) — Step 1 구현 후 green 전환 대상.
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
from app.adapter.out.kiwoom.stkinfo import (
    KiwoomStkInfoClient,
    StockBasicInfoResponse,
)
from app.application.service.stock_fundamental_service import (
    FundamentalSyncOutcome,
    FundamentalSyncResult,
    SyncStockFundamentalUseCase,
)

# ---------------------------------------------------------------------------
# Fixtures — test_stock_fundamental_service.py 패턴 1:1 차용
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """conftest 트랜잭션+rollback session override — 본 테스트는 commit 필요."""
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_fundamental_tables(engine: AsyncEngine) -> AsyncIterator[None]:
    """매 테스트 시작·종료 시 stock + stock_fundamental TRUNCATE (FK CASCADE)."""
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        await s.execute(text("TRUNCATE kiwoom.stock RESTART IDENTITY CASCADE"))
        await s.commit()
    yield
    async with factory() as s:
        await s.execute(text("TRUNCATE kiwoom.stock RESTART IDENTITY CASCADE"))
        await s.commit()


def _make_response(
    stk_cd: str = "005930",
    stk_nm: str = "삼성전자",
) -> StockBasicInfoResponse:
    return StockBasicInfoResponse.model_validate(
        {
            "stk_cd": stk_cd,
            "stk_nm": stk_nm,
            "setl_mm": "12",
            "fav": "5000",
            "cap": "1311",
            "flo_stk": "5969782",
            "mac": "4356400",
            "per": "15.20",
            "eps": "5000",
            "roe": "12.50",
            "pbr": "1.20",
            "ev": "8.30",
            "bps": "70000",
            "cur_prc": "75800",
            "return_code": 0,
            "return_msg": "정상",
        }
    )


async def _create_active_stock(
    session: AsyncSession,
    stock_code: str,
    stock_name: str = "test",
    market_code: str = "0",
    *,
    is_active: bool = True,
) -> int:
    result = await session.execute(
        text(
            "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code, is_active) "
            "VALUES (:code, :name, :mc, :active) RETURNING id"
        ).bindparams(code=stock_code, name=stock_name, mc=market_code, active=is_active)
    )
    return int(result.scalar_one())


@pytest.fixture
def session_provider(
    engine: Any,
) -> Callable[[], AbstractAsyncContextManager[AsyncSession]]:
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    @asynccontextmanager
    async def _provider() -> AsyncIterator[AsyncSession]:
        async with factory() as s:
            yield s

    return _provider


def _stub_stkinfo_client(
    responses: dict[str, StockBasicInfoResponse | Exception],
) -> KiwoomStkInfoClient:
    """stock_code → response 또는 Exception. fetch_basic_info 만 stub."""
    client = AsyncMock(spec=KiwoomStkInfoClient)

    async def _fetch(stock_code: str) -> StockBasicInfoResponse:
        result = responses.get(stock_code)
        if result is None:
            raise KiwoomBusinessError(api_id="ka10001", return_code=99, message="응답 없음")
        if isinstance(result, Exception):
            raise result
        return result

    client.fetch_basic_info = _fetch
    return client


# ---------------------------------------------------------------------------
# FundamentalSyncResult — skipped / skipped_count 필드 존재 단언
# ---------------------------------------------------------------------------


def test_fundamental_sync_result_has_skipped_field() -> None:
    """FundamentalSyncResult 에 skipped: tuple[FundamentalSyncOutcome, ...] 필드가 있어야 함.

    현재 없음 → AttributeError = red. Step 1 에서 dataclass field 추가 후 green.
    """
    result = FundamentalSyncResult(
        asof_date=date(2026, 5, 14),
        total=0,
        success=0,
        failed=0,
        errors=(),
    )
    # skipped 필드 접근 — 없으면 AttributeError
    _ = result.skipped  # type: ignore[attr-defined]


def test_fundamental_sync_result_has_skipped_count_property() -> None:
    """FundamentalSyncResult 의 skipped_count == len(skipped) 를 보장해야 함.

    dataclass field 또는 property 로 구현 가능.
    현재 없음 → AttributeError = red.
    """
    result = FundamentalSyncResult(
        asof_date=date(2026, 5, 14),
        total=0,
        success=0,
        failed=0,
        errors=(),
    )
    _ = result.skipped_count  # type: ignore[attr-defined]


def test_fundamental_sync_result_skipped_count_equals_len_skipped() -> None:
    """skipped_count == len(skipped) 일관성 검증.

    FundamentalSyncOutcome 의 sentinel 종목 1건 skipped 에 적재 시
    skipped_count 가 1 이어야 함.
    """
    from app.application.service.stock_fundamental_service import FundamentalSyncResult

    skipped_item = FundamentalSyncOutcome(
        stock_code="0000D0",
        error_class="SentinelStockCodeError",
    )
    result = FundamentalSyncResult(  # type: ignore[call-arg]
        asof_date=date(2026, 5, 14),
        total=3,
        success=2,
        failed=0,
        errors=(),
        skipped=(skipped_item,),
    )
    assert result.skipped_count == 1, (  # type: ignore[attr-defined]
        f"skipped_count=1 기대, 실제={result.skipped_count}"  # type: ignore[attr-defined]
    )


# ---------------------------------------------------------------------------
# execute 루프 — SentinelStockCodeError → skipped 적재 / failed 미증가
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_catches_sentinel_error_and_puts_in_skipped_not_failed(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    """sentinel 종목 (0000D0) — SentinelStockCodeError 캐치 → skipped 적재 / failed 미증가.

    계획서 § 4 결정 #5: SentinelStockCodeError 별도 catch → result.skipped 적재.
    계획서 § 4 결정 #6: result.failed_count = 실제 실패 (sentinel 제외).

    현재 구현: _validate_stk_cd_for_lookup 이 ValueError raise → KiwoomError 가 아니라서
    except Exception: 에 잡혀 failed++ 됨 → 변경 필요 (red).
    """
    from app.adapter.out.kiwoom.stkinfo import SentinelStockCodeError

    # 정상 종목 2개 + sentinel 종목 1개 등록
    await _create_active_stock(session, "005930", "삼성전자", "0")
    await _create_active_stock(session, "0000D0", "NXT_SENTINEL", "0")
    await _create_active_stock(session, "000660", "SK하이닉스", "0")
    await session.commit()

    stkinfo = _stub_stkinfo_client(
        {
            "005930": _make_response("005930", "삼성전자"),
            "0000D0": SentinelStockCodeError("0000D0"),  # sentinel 예외
            "000660": _make_response("000660", "SK하이닉스"),
        }
    )
    uc = SyncStockFundamentalUseCase(session_provider=session_provider, stkinfo_client=stkinfo)

    result = await uc.execute()

    # 핵심 단언 — failed 미증가
    assert result.total == 3, f"total=3 기대, 실제={result.total}"
    assert result.success == 2, f"success=2 기대, 실제={result.success}"
    assert result.failed == 0, (
        f"failed=0 기대 (sentinel 은 실패 아님), 실제={result.failed}"
    )

    # skipped 단언
    assert result.skipped_count == 1, (  # type: ignore[attr-defined]
        f"skipped_count=1 기대, 실제={result.skipped_count}"  # type: ignore[attr-defined]
    )
    assert len(result.skipped) == 1, (  # type: ignore[attr-defined]
        f"skipped 길이 1 기대, 실제={len(result.skipped)}"  # type: ignore[attr-defined]
    )
    skipped_item = result.skipped[0]  # type: ignore[attr-defined]
    assert skipped_item.stock_code == "0000D0", (
        f"skipped 종목코드 '0000D0' 기대, 실제='{skipped_item.stock_code}'"
    )
    assert skipped_item.error_class == "SentinelStockCodeError", (
        f"error_class 'SentinelStockCodeError' 기대, 실제='{skipped_item.error_class}'"
    )

    # errors 에는 sentinel 종목 미포함
    assert len(result.errors) == 0, (
        f"errors 는 실제 실패만 — sentinel 제외 기대, 실제={result.errors}"
    )


@pytest.mark.asyncio
async def test_execute_sentinel_skip_does_not_increment_failed_count(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    """sentinel 2건 + 실패 1건 — failed=1 / skipped=2 / success=1.

    알려진 sentinel 종목 0000D0 + 0000H0 회귀 (5-13 18:00 cron 실패 종목).
    """
    from app.adapter.out.kiwoom.stkinfo import SentinelStockCodeError

    await _create_active_stock(session, "005930", "삼성전자", "0")
    await _create_active_stock(session, "0000D0", "SENTINEL_D", "0")
    await _create_active_stock(session, "0000H0", "SENTINEL_H", "0")
    await _create_active_stock(session, "999999", "실패종목", "0")
    await session.commit()

    stkinfo = _stub_stkinfo_client(
        {
            "005930": _make_response("005930", "삼성전자"),
            "0000D0": SentinelStockCodeError("0000D0"),
            "0000H0": SentinelStockCodeError("0000H0"),
            "999999": KiwoomBusinessError(api_id="ka10001", return_code=1, message="미존재"),
        }
    )
    uc = SyncStockFundamentalUseCase(session_provider=session_provider, stkinfo_client=stkinfo)

    result = await uc.execute()

    assert result.total == 4
    assert result.success == 1
    assert result.failed == 1, (
        f"실제 실패 1건만 failed, 실제={result.failed}"
    )
    assert result.skipped_count == 2, (  # type: ignore[attr-defined]
        f"sentinel 2건 skipped, 실제={result.skipped_count}"  # type: ignore[attr-defined]
    )

    skipped_codes = {s.stock_code for s in result.skipped}  # type: ignore[attr-defined]
    assert skipped_codes == {"0000D0", "0000H0"}, (
        f"skipped 코드 집합 오류: {skipped_codes}"
    )

    failed_codes = {e.stock_code for e in result.errors}
    assert failed_codes == {"999999"}, (
        f"errors 코드 집합 오류: {failed_codes}"
    )


@pytest.mark.asyncio
async def test_execute_result_skipped_default_is_empty_tuple(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    """sentinel 없는 정상 실행 — skipped 는 기본값 빈 tuple / skipped_count=0.

    기존 정상 케이스 회귀: skipped 추가가 기존 동작을 깨지 않음.
    """
    await _create_active_stock(session, "005930", "삼성전자", "0")
    await session.commit()

    stkinfo = _stub_stkinfo_client({"005930": _make_response("005930", "삼성전자")})
    uc = SyncStockFundamentalUseCase(session_provider=session_provider, stkinfo_client=stkinfo)

    result = await uc.execute()

    assert result.success == 1
    assert result.failed == 0
    assert result.skipped_count == 0, (  # type: ignore[attr-defined]
        f"sentinel 없을 때 skipped_count=0 기대, 실제={result.skipped_count}"  # type: ignore[attr-defined]
    )
    assert len(result.skipped) == 0, (  # type: ignore[attr-defined]
        f"sentinel 없을 때 skipped 빈 tuple 기대, 실제={result.skipped}"  # type: ignore[attr-defined]
    )
