"""SyncStockMasterUseCase 단위 테스트 — 시장 단위 격리 핵심 (sector 패턴 일관).

testcontainers PG16 + KiwoomStkInfoClient mock (httpx.MockTransport via KiwoomClient).

검증:
- 5 시장 정상 sync — outcomes 5개 / total_* 합산 정확 (nxt_enabled_count 포함)
- 한 시장 KiwoomError → 그 시장 outcome.error 기록 + 다른 시장 진행
- 한 시장 KiwoomBusinessError → 동일하게 격리
- 모든 시장 실패해도 StockMasterSyncResult 반환 (예외 전파 X)
- 멱등성: 같은 응답 두 번 sync → upserted 합계 같고 deactivated=0
- 폐지 처리: 첫 sync 후 두 번째 응답에서 stock 빠지면 is_active=False
- 재등장 처리: 비활성 stock 재등장 시 is_active=True 복원 + 이름 변경
- mock_env=True → 응답 nxtEnable='Y' 무시 → DB nxt_enable=False
- 빈 응답 보호: 시장 응답 list=[] 면 deactivate skip (그 시장 종목 비활성화 안 함)
- listCount 비숫자 → 그 시장 KiwoomResponseValidationError 격리
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.adapter.out.kiwoom._client import KiwoomClient
from app.adapter.out.kiwoom.stkinfo import KiwoomStkInfoClient
from app.adapter.out.persistence.repositories.stock import StockRepository
from app.application.constants import (
    STOCK_SYNC_DEFAULT_MARKETS,
    StockListMarketType,
)
from app.application.service.stock_master_service import (
    SyncStockMasterUseCase,
)

# =============================================================================
# 픽스처 — UseCase 전용 (별도 engine + sessionmaker)
# =============================================================================


@pytest_asyncio.fixture
async def commit_engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(database_url, pool_pre_ping=True)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def commit_sessionmaker(commit_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=commit_engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def session_provider(
    commit_sessionmaker: async_sessionmaker[AsyncSession],
):
    @asynccontextmanager
    async def _provider() -> AsyncIterator[AsyncSession]:
        async with commit_sessionmaker() as s:
            yield s

    return _provider


@pytest_asyncio.fixture
async def cleanup_stocks(commit_sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncIterator[None]:
    """본 테스트 모듈은 commit 하므로 매 테스트 시작·종료 시 stock 테이블 비움."""
    from sqlalchemy import delete

    from app.adapter.out.persistence.models import Stock

    async with commit_sessionmaker() as s:
        await s.execute(delete(Stock))
        await s.commit()
    yield
    async with commit_sessionmaker() as s:
        await s.execute(delete(Stock))
        await s.commit()


# =============================================================================
# 키움 응답 헬퍼 + Mock Transport
# =============================================================================


def _ka10099_body(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "return_code": 0,
        "return_msg": "정상적으로 처리되었습니다",
        "list": rows,
    }


def _row(
    code: str,
    name: str,
    market_code: str = "0",
    *,
    nxt_enable: str = "Y",
    list_count: str = "0000000000001000",
    last_price: str = "00010000",
    reg_day: str = "20200101",
    state: str = "정상",
    market_name: str = "거래소",
    up_name: str = "전기전자",
    up_size_name: str = "대형주",
) -> dict[str, str]:
    return {
        "code": code,
        "name": name,
        "marketCode": market_code,
        "nxtEnable": nxt_enable,
        "listCount": list_count,
        "lastPrice": last_price,
        "regDay": reg_day,
        "state": state,
        "marketName": market_name,
        "upName": up_name,
        "upSizeName": up_size_name,
        "auditInfo": "",
        "companyClassName": "",
        "orderWarning": "0",
    }


def _make_handler(responses_by_market: dict[str, httpx.Response]):
    """`mrkt_tp` 별 응답 매핑."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        for mrkt_tp, resp in responses_by_market.items():
            if f'"mrkt_tp": "{mrkt_tp}"' in body or f'"mrkt_tp":"{mrkt_tp}"' in body:
                return resp
        raise AssertionError(f"unmatched mrkt_tp in body: {body}")

    return handler


def _build_use_case(
    *,
    session_provider,
    handler,
    mock_env: bool = False,
) -> SyncStockMasterUseCase:
    transport = httpx.MockTransport(handler)

    async def _token_provider() -> str:
        return "TEST-TOKEN-VALUE"

    kiwoom_client = KiwoomClient(
        base_url="https://api.kiwoom.com",
        token_provider=_token_provider,
        transport=transport,
        max_attempts=1,
        retry_min_wait=0.0,
        retry_max_wait=0.0,
        min_request_interval_seconds=0.0,
    )
    stkinfo = KiwoomStkInfoClient(kiwoom_client)
    return SyncStockMasterUseCase(
        session_provider=session_provider,
        stkinfo_client=stkinfo,
        mock_env=mock_env,
    )


# =============================================================================
# 정상 sync (5 시장)
# =============================================================================


@pytest.mark.asyncio
async def test_execute_all_markets_succeed(
    session_provider,
    cleanup_stocks,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """5 시장 모두 정상 응답 — total_* 합산 + DB 적재."""
    responses = {
        mrkt.value: httpx.Response(
            200,
            json=_ka10099_body(
                [
                    _row(f"{mrkt.value}A001", f"{mrkt.value}-A", market_code=mrkt.value, nxt_enable="Y"),
                    _row(f"{mrkt.value}A002", f"{mrkt.value}-B", market_code=mrkt.value, nxt_enable="N"),
                ]
            ),
        )
        for mrkt in STOCK_SYNC_DEFAULT_MARKETS
    }
    use_case = _build_use_case(
        session_provider=session_provider,
        handler=_make_handler(responses),
    )

    result = await use_case.execute()

    assert len(result.markets) == 5
    assert result.all_succeeded
    assert result.total_fetched == 10  # 5 시장 x 2 row
    assert result.total_upserted == 10
    assert result.total_deactivated == 0  # 첫 sync — 비활성화 대상 없음
    assert result.total_nxt_enabled == 5  # 시장당 1 row nxtEnable=Y

    async with commit_sessionmaker() as s:
        repo = StockRepository(s)
        all_rows = await repo.list_by_filters(only_active=True)
    assert len(all_rows) == 10


# =============================================================================
# 시장 단위 격리 (핵심)
# =============================================================================


@pytest.mark.asyncio
async def test_one_market_upstream_failure_isolated(
    session_provider,
    cleanup_stocks,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """KONEX(50) 시장만 502 — 나머지 4 시장 정상 적재."""
    responses = {
        "0": httpx.Response(200, json=_ka10099_body([_row("KOSPI1", "삼성", "0")])),
        "10": httpx.Response(200, json=_ka10099_body([_row("KOSDQ1", "키움", "10")])),
        "50": httpx.Response(502),  # KONEX 실패
        "60": httpx.Response(200, json=_ka10099_body([_row("ETN001", "ETN", "60")])),
        "6": httpx.Response(200, json=_ka10099_body([_row("REIT01", "리츠", "6")])),
    }
    use_case = _build_use_case(
        session_provider=session_provider,
        handler=_make_handler(responses),
    )

    result = await use_case.execute()

    assert len(result.markets) == 5
    by_market = {m.market_code: m for m in result.markets}
    assert by_market["50"].error is not None
    assert "Upstream" in by_market["50"].error or "KiwoomUpstreamError" in by_market["50"].error
    assert all(by_market[m].succeeded for m in ("0", "10", "60", "6"))
    assert result.all_succeeded is False
    assert result.total_upserted == 4

    async with commit_sessionmaker() as s:
        repo = StockRepository(s)
        all_rows = await repo.list_by_filters(only_active=True)
    assert {r.stock_code for r in all_rows} == {"KOSPI1", "KOSDQ1", "ETN001", "REIT01"}


@pytest.mark.asyncio
async def test_one_market_credential_rejected_isolated(
    session_provider,
    cleanup_stocks,
) -> None:
    """KOSPI(0) 만 401 — 나머지 시장 진행."""
    responses = {
        "0": httpx.Response(401),
        "10": httpx.Response(200, json=_ka10099_body([_row("KOSDQ1", "K", "10")])),
        "50": httpx.Response(200, json=_ka10099_body([_row("KONEX1", "K", "50")])),
        "60": httpx.Response(200, json=_ka10099_body([_row("ETN001", "E", "60")])),
        "6": httpx.Response(200, json=_ka10099_body([_row("REIT01", "R", "6")])),
    }
    use_case = _build_use_case(
        session_provider=session_provider,
        handler=_make_handler(responses),
    )

    result = await use_case.execute()
    by_market = {m.market_code: m for m in result.markets}
    assert by_market["0"].error is not None
    assert "CredentialRejected" in by_market["0"].error
    assert all(by_market[m].succeeded for m in ("10", "50", "60", "6"))


@pytest.mark.asyncio
async def test_one_market_business_error_isolated(
    session_provider,
    cleanup_stocks,
) -> None:
    """한 시장만 return_code != 0 — KiwoomBusinessError 격리."""
    responses = {
        "0": httpx.Response(
            200,
            json={"return_code": 1, "return_msg": "거부", "list": []},
        ),
        "10": httpx.Response(200, json=_ka10099_body([_row("OK001", "OK", "10")])),
        "50": httpx.Response(200, json=_ka10099_body([_row("OK002", "OK", "50")])),
        "60": httpx.Response(200, json=_ka10099_body([_row("OK003", "OK", "60")])),
        "6": httpx.Response(200, json=_ka10099_body([_row("OK004", "OK", "6")])),
    }
    use_case = _build_use_case(
        session_provider=session_provider,
        handler=_make_handler(responses),
    )

    result = await use_case.execute()
    by_market = {m.market_code: m for m in result.markets}
    assert by_market["0"].error is not None
    assert "BusinessError" in by_market["0"].error
    assert all(by_market[m].succeeded for m in ("10", "50", "60", "6"))


@pytest.mark.asyncio
async def test_all_markets_fail_returns_full_result(
    session_provider,
    cleanup_stocks,
) -> None:
    """5 시장 모두 502 — 결과 dataclass 정상 반환 (예외 전파 X)."""
    responses = {mrkt.value: httpx.Response(502) for mrkt in STOCK_SYNC_DEFAULT_MARKETS}
    use_case = _build_use_case(
        session_provider=session_provider,
        handler=_make_handler(responses),
    )

    result = await use_case.execute()

    assert len(result.markets) == 5
    assert all(m.error is not None for m in result.markets)
    assert result.all_succeeded is False
    assert result.total_upserted == 0
    assert result.total_fetched == 0


# =============================================================================
# 멱등성 / 폐지 / 재등장
# =============================================================================


@pytest.mark.asyncio
async def test_idempotent_resync_zero_deactivations(
    session_provider,
    cleanup_stocks,
) -> None:
    """같은 응답 두 번 sync — total_upserted 동일, total_deactivated == 0."""
    responses = {
        mrkt.value: httpx.Response(
            200,
            json=_ka10099_body([_row(f"{mrkt.value}A1", f"{mrkt.value}", mrkt.value)]),
        )
        for mrkt in STOCK_SYNC_DEFAULT_MARKETS
    }
    handler = _make_handler(responses)
    use_case = _build_use_case(session_provider=session_provider, handler=handler)

    first = await use_case.execute()
    second = await use_case.execute()

    assert first.total_upserted == 5
    assert second.total_upserted == 5
    assert first.total_deactivated == 0
    assert second.total_deactivated == 0


@pytest.mark.asyncio
async def test_deprecated_stock_marked_inactive(
    session_provider,
    cleanup_stocks,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """첫 sync 후 두 번째 응답에서 stock 빠지면 is_active=False."""
    first_responses = {
        "0": httpx.Response(
            200,
            json=_ka10099_body(
                [
                    _row("KEEP01", "유지", "0"),
                    _row("DROP01", "폐지대상", "0"),
                ]
            ),
        ),
        "10": httpx.Response(200, json=_ka10099_body([])),
        "50": httpx.Response(200, json=_ka10099_body([])),
        "60": httpx.Response(200, json=_ka10099_body([])),
        "6": httpx.Response(200, json=_ka10099_body([])),
    }
    second_responses = {
        "0": httpx.Response(
            200,
            json=_ka10099_body([_row("KEEP01", "유지", "0")]),  # DROP01 빠짐
        ),
        "10": httpx.Response(200, json=_ka10099_body([])),
        "50": httpx.Response(200, json=_ka10099_body([])),
        "60": httpx.Response(200, json=_ka10099_body([])),
        "6": httpx.Response(200, json=_ka10099_body([])),
    }

    await _build_use_case(
        session_provider=session_provider, handler=_make_handler(first_responses)
    ).execute()

    use_case_second = _build_use_case(
        session_provider=session_provider, handler=_make_handler(second_responses)
    )
    result = await use_case_second.execute()

    by_market = {m.market_code: m for m in result.markets}
    assert by_market["0"].deactivated == 1

    async with commit_sessionmaker() as s:
        repo = StockRepository(s)
        active = await repo.list_by_filters(market_code="0", only_active=True)
        all_rows = await repo.list_by_filters(market_code="0", only_active=False)
    assert {r.stock_code for r in active} == {"KEEP01"}
    assert {(r.stock_code, r.is_active) for r in all_rows} == {
        ("KEEP01", True),
        ("DROP01", False),
    }


@pytest.mark.asyncio
async def test_reappearing_stock_reactivated(
    session_provider,
    cleanup_stocks,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """비활성 stock 이 재등장 → is_active=True + 이름 변경."""
    phase1 = {
        "0": httpx.Response(200, json=_ka10099_body([_row("AAA001", "v1", "0")])),
        "10": httpx.Response(200, json=_ka10099_body([])),
        "50": httpx.Response(200, json=_ka10099_body([])),
        "60": httpx.Response(200, json=_ka10099_body([])),
        "6": httpx.Response(200, json=_ka10099_body([])),
    }
    await _build_use_case(session_provider=session_provider, handler=_make_handler(phase1)).execute()

    phase2 = {
        "0": httpx.Response(200, json=_ka10099_body([])),
        "10": httpx.Response(200, json=_ka10099_body([])),
        "50": httpx.Response(200, json=_ka10099_body([])),
        "60": httpx.Response(200, json=_ka10099_body([])),
        "6": httpx.Response(200, json=_ka10099_body([])),
    }
    await _build_use_case(session_provider=session_provider, handler=_make_handler(phase2)).execute()

    phase3 = {
        "0": httpx.Response(200, json=_ka10099_body([_row("AAA001", "v3-재등장", "0")])),
        "10": httpx.Response(200, json=_ka10099_body([])),
        "50": httpx.Response(200, json=_ka10099_body([])),
        "60": httpx.Response(200, json=_ka10099_body([])),
        "6": httpx.Response(200, json=_ka10099_body([])),
    }
    await _build_use_case(session_provider=session_provider, handler=_make_handler(phase3)).execute()

    async with commit_sessionmaker() as s:
        repo = StockRepository(s)
        active = await repo.list_by_filters(market_code="0", only_active=True)
    assert len(active) == 1
    assert active[0].stock_code == "AAA001"
    assert active[0].stock_name == "v3-재등장"
    assert active[0].is_active is True


# =============================================================================
# mock 환경 안전판 (§4.2)
# =============================================================================


@pytest.mark.asyncio
async def test_mock_env_forces_nxt_enable_false(
    session_provider,
    cleanup_stocks,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """mock_env=True → 응답 nxtEnable='Y' 무시 → DB nxt_enable=False."""
    responses = {
        mrkt.value: httpx.Response(
            200,
            json=_ka10099_body(
                [_row(f"{mrkt.value}M01", f"M-{mrkt.value}", mrkt.value, nxt_enable="Y")]
            ),
        )
        for mrkt in STOCK_SYNC_DEFAULT_MARKETS
    }
    use_case = _build_use_case(
        session_provider=session_provider,
        handler=_make_handler(responses),
        mock_env=True,
    )

    result = await use_case.execute()

    assert result.total_upserted == 5
    assert result.total_nxt_enabled == 0, "mock_env 면 응답 nxtEnable 무시"

    async with commit_sessionmaker() as s:
        repo = StockRepository(s)
        all_rows = await repo.list_by_filters(only_active=True)
    assert all(not r.nxt_enable for r in all_rows), "DB 의 nxt_enable 도 모두 False"


# =============================================================================
# 빈 응답 보호 (§5.3)
# =============================================================================


@pytest.mark.asyncio
async def test_empty_response_skips_deactivation(
    session_provider,
    cleanup_stocks,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """시장 응답 list=[] 면 그 시장 종목 비활성화 SKIP — 사고 방지."""
    # 첫 sync: KOSPI 에 종목 등록
    phase1 = {
        "0": httpx.Response(
            200,
            json=_ka10099_body([_row("AAA01", "x", "0"), _row("BBB02", "y", "0")]),
        ),
        "10": httpx.Response(200, json=_ka10099_body([])),
        "50": httpx.Response(200, json=_ka10099_body([])),
        "60": httpx.Response(200, json=_ka10099_body([])),
        "6": httpx.Response(200, json=_ka10099_body([])),
    }
    await _build_use_case(session_provider=session_provider, handler=_make_handler(phase1)).execute()

    # 두 번째 sync: KOSPI 응답이 빈 list — 폐지 처리 SKIP
    phase2 = {
        "0": httpx.Response(200, json=_ka10099_body([])),
        "10": httpx.Response(200, json=_ka10099_body([])),
        "50": httpx.Response(200, json=_ka10099_body([])),
        "60": httpx.Response(200, json=_ka10099_body([])),
        "6": httpx.Response(200, json=_ka10099_body([])),
    }
    use_case = _build_use_case(session_provider=session_provider, handler=_make_handler(phase2))
    result = await use_case.execute()

    by_market = {m.market_code: m for m in result.markets}
    assert by_market["0"].deactivated == 0, "빈 응답이면 비활성화 SKIP"

    # KOSPI 종목 그대로 살아있음
    async with commit_sessionmaker() as s:
        repo = StockRepository(s)
        active = await repo.list_by_filters(market_code="0", only_active=True)
    assert {r.stock_code for r in active} == {"AAA01", "BBB02"}


# =============================================================================
# 비숫자 listCount → KiwoomResponseValidationError 격리
# =============================================================================


@pytest.mark.asyncio
async def test_non_numeric_list_count_isolated_per_market(
    session_provider,
    cleanup_stocks,
) -> None:
    """KOSPI 응답에 listCount='abc' → 그 시장만 ValidationError, 나머지 진행."""
    responses = {
        "0": httpx.Response(
            200,
            json=_ka10099_body([_row("BAD001", "비숫자", "0", list_count="abc")]),
        ),
        "10": httpx.Response(200, json=_ka10099_body([_row("OK001", "OK", "10")])),
        "50": httpx.Response(200, json=_ka10099_body([_row("OK002", "OK", "50")])),
        "60": httpx.Response(200, json=_ka10099_body([_row("OK003", "OK", "60")])),
        "6": httpx.Response(200, json=_ka10099_body([_row("OK004", "OK", "6")])),
    }
    use_case = _build_use_case(
        session_provider=session_provider,
        handler=_make_handler(responses),
    )
    result = await use_case.execute()

    by_market = {m.market_code: m for m in result.markets}
    assert by_market["0"].error is not None
    assert "ValidationError" in by_market["0"].error
    assert all(by_market[m].succeeded for m in ("10", "50", "60", "6"))


# =============================================================================
# DTO property 단위
# =============================================================================


def test_dto_outcome_succeeded_property() -> None:
    from app.application.service.stock_master_service import MarketStockOutcome

    ok = MarketStockOutcome(market_code="0", fetched=1, upserted=1, deactivated=0, nxt_enabled_count=0)
    fail = MarketStockOutcome(
        market_code="0", fetched=0, upserted=0, deactivated=0, nxt_enabled_count=0, error="X"
    )
    assert ok.succeeded is True
    assert fail.succeeded is False


def test_dto_result_all_succeeded_property() -> None:
    from app.application.service.stock_master_service import (
        MarketStockOutcome,
        StockMasterSyncResult,
    )

    all_ok = StockMasterSyncResult(
        markets=[MarketStockOutcome(market_code="0", fetched=0, upserted=0, deactivated=0, nxt_enabled_count=0)],
        total_fetched=0,
        total_upserted=0,
        total_deactivated=0,
        total_nxt_enabled=0,
    )
    has_fail = StockMasterSyncResult(
        markets=[
            MarketStockOutcome(market_code="0", fetched=0, upserted=0, deactivated=0, nxt_enabled_count=0),
            MarketStockOutcome(
                market_code="10",
                fetched=0,
                upserted=0,
                deactivated=0,
                nxt_enabled_count=0,
                error="X",
            ),
        ],
        total_fetched=0,
        total_upserted=0,
        total_deactivated=0,
        total_nxt_enabled=0,
    )
    assert all_ok.all_succeeded is True
    assert has_fail.all_succeeded is False


def test_use_case_custom_markets_override() -> None:
    """markets 파라미터 명시 시 DEFAULT_MARKETS 대신 그것 사용 (운영 dry-run 시)."""

    @asynccontextmanager
    async def _session_provider() -> AsyncIterator[AsyncSession]:
        raise AssertionError("호출되면 안 됨 — 시그니처 확인만")
        yield  # pragma: no cover

    async def _token_provider() -> str:
        return "T"

    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"return_code": 0, "list": []}))
    kc = KiwoomClient(
        base_url="https://api.kiwoom.com",
        token_provider=_token_provider,
        transport=transport,
    )
    use_case = SyncStockMasterUseCase(
        session_provider=_session_provider,
        stkinfo_client=KiwoomStkInfoClient(kc),
        markets=(StockListMarketType.KOSPI,),  # 1개만
    )
    assert use_case._markets == (StockListMarketType.KOSPI,)
