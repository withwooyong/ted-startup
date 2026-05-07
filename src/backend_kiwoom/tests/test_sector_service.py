"""SyncSectorMasterUseCase 단위 테스트 — 시장 단위 격리 핵심.

testcontainers PG16 + KiwoomStkInfoClient mock (httpx.MockTransport via KiwoomClient).

검증:
- 5 시장 정상 sync — outcomes 5개 / total_* 합산 정확
- 한 시장 KiwoomError → 그 시장 outcome.error 기록 + 다른 시장 진행
- 한 시장 KiwoomBusinessError → 동일하게 격리
- 모든 시장 실패해도 SectorSyncResult 반환 (예외 전파 X)
- DB 변경: 성공 시장만 sector 테이블에 적재 / 실패 시장은 빈 상태 유지
- 멱등성: 같은 응답 두 번 sync → upserted 합계 같고 deactivated=0
- 폐지 처리: 첫 sync 후 두 번째 응답에서 sector 빠지면 is_active=False
- 재등장 처리: 비활성 sector 재등장 시 is_active=True 복원
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
from app.adapter.out.persistence.repositories.sector import SectorRepository
from app.application.service.sector_service import (
    SUPPORTED_MARKETS,
    SyncSectorMasterUseCase,
)

# =============================================================================
# 픽스처 — Use Case 전용 (별도 engine + sessionmaker, 본 모듈만의 트랜잭션 격리)
# =============================================================================


@pytest_asyncio.fixture
async def commit_engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    """UseCase 가 자체 commit 하므로 conftest 의 rollback session 과 별도 engine."""
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
    """UseCase 에 주입할 session_provider — 매 호출마다 새 세션."""

    @asynccontextmanager
    async def _provider() -> AsyncIterator[AsyncSession]:
        async with commit_sessionmaker() as s:
            yield s

    return _provider


@pytest_asyncio.fixture
async def cleanup_sectors(commit_sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncIterator[None]:
    """본 테스트 모듈은 commit 하므로 매 테스트 시작·종료 시 sector 테이블 비움."""
    from sqlalchemy import delete

    from app.adapter.out.persistence.models import Sector

    async with commit_sessionmaker() as s:
        await s.execute(delete(Sector))
        await s.commit()
    yield
    async with commit_sessionmaker() as s:
        await s.execute(delete(Sector))
        await s.commit()


# =============================================================================
# 키움 응답 헬퍼 + Mock Transport
# =============================================================================


def _ka10101_body(rows: list[dict[str, str]]) -> dict[str, Any]:
    """ka10101 정상 응답 (return_code=0)."""
    return {
        "return_code": 0,
        "return_msg": "정상적으로 처리되었습니다",
        "list": rows,
    }


def _row(market_code: str, code: str, name: str, group: str = "") -> dict[str, str]:
    return {"marketCode": market_code, "code": code, "name": name, "group": group}


def _make_handler(
    responses_by_market: dict[str, httpx.Response],
):
    """`mrkt_tp` 별 응답 매핑 — 같은 mrkt_tp 호출 시 같은 응답."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        # 단순한 substring 매칭 — JSON 본문 안의 mrkt_tp 값 추출
        for mrkt_tp, resp in responses_by_market.items():
            if f'"mrkt_tp":"{mrkt_tp}"' in body or f'"mrkt_tp": "{mrkt_tp}"' in body:
                return resp
        raise AssertionError(f"unmatched mrkt_tp in body: {body}")

    return handler


def _build_use_case(
    *,
    session_provider,
    handler,
) -> SyncSectorMasterUseCase:
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
    return SyncSectorMasterUseCase(
        session_provider=session_provider,
        stkinfo_client=stkinfo,
    )


# =============================================================================
# 정상 sync (5 시장)
# =============================================================================


@pytest.mark.asyncio
async def test_execute_all_markets_succeed(
    session_provider,
    cleanup_sectors,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """5 시장 모두 정상 응답 — 모든 시장 outcome.succeeded == True."""
    responses = {
        mrkt_tp: httpx.Response(
            200,
            json=_ka10101_body(
                [
                    _row(mrkt_tp, "001", f"{mrkt_tp}-종합"),
                    _row(mrkt_tp, "002", f"{mrkt_tp}-대형주"),
                ]
            ),
        )
        for mrkt_tp in SUPPORTED_MARKETS
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

    # DB 검증: 5 시장 x 2 = 10 row
    async with commit_sessionmaker() as s:
        repo = SectorRepository(s)
        all_rows = await repo.list_all(only_active=True)
    assert len(all_rows) == 10


# =============================================================================
# 시장 단위 격리 (핵심)
# =============================================================================


@pytest.mark.asyncio
async def test_one_market_upstream_failure_isolated(
    session_provider,
    cleanup_sectors,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """시장 2 만 502 — 나머지 4 시장은 정상 적재."""
    responses = {
        "0": httpx.Response(200, json=_ka10101_body([_row("0", "001", "KOSPI")])),
        "1": httpx.Response(200, json=_ka10101_body([_row("1", "001", "KOSDAQ")])),
        "2": httpx.Response(502),  # 실패
        "4": httpx.Response(200, json=_ka10101_body([_row("4", "001", "KOSPI100")])),
        "7": httpx.Response(200, json=_ka10101_body([_row("7", "001", "KRX100")])),
    }
    use_case = _build_use_case(
        session_provider=session_provider,
        handler=_make_handler(responses),
    )

    result = await use_case.execute()

    assert len(result.markets) == 5
    by_market = {m.market_code: m for m in result.markets}
    assert by_market["0"].succeeded
    assert by_market["1"].succeeded
    assert by_market["2"].error is not None
    assert "Upstream" in by_market["2"].error or "KiwoomUpstreamError" in by_market["2"].error
    assert by_market["4"].succeeded
    assert by_market["7"].succeeded
    assert result.all_succeeded is False
    assert result.total_upserted == 4  # 4 시장 x 1 row

    async with commit_sessionmaker() as s:
        repo = SectorRepository(s)
        all_rows = await repo.list_all(only_active=True)
    assert {(r.market_code, r.sector_code) for r in all_rows} == {
        ("0", "001"),
        ("1", "001"),
        ("4", "001"),
        ("7", "001"),
    }


@pytest.mark.asyncio
async def test_one_market_credential_rejected_isolated(
    session_provider,
    cleanup_sectors,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """한 시장만 401 — 나머지 시장 진행."""
    responses = {
        "0": httpx.Response(401),
        "1": httpx.Response(200, json=_ka10101_body([_row("1", "001", "KOSDAQ")])),
        "2": httpx.Response(200, json=_ka10101_body([_row("2", "001", "200")])),
        "4": httpx.Response(200, json=_ka10101_body([_row("4", "001", "100")])),
        "7": httpx.Response(200, json=_ka10101_body([_row("7", "001", "K100")])),
    }
    use_case = _build_use_case(
        session_provider=session_provider,
        handler=_make_handler(responses),
    )

    result = await use_case.execute()
    by_market = {m.market_code: m for m in result.markets}
    assert by_market["0"].error is not None
    assert "CredentialRejected" in by_market["0"].error
    assert all(by_market[m].succeeded for m in ("1", "2", "4", "7"))


@pytest.mark.asyncio
async def test_one_market_business_error_isolated(
    session_provider,
    cleanup_sectors,
) -> None:
    """한 시장만 return_code != 0 — KiwoomBusinessError 격리."""
    responses = {
        "0": httpx.Response(
            200,
            json={"return_code": 1, "return_msg": "비즈니스 거부", "list": []},
        ),
        "1": httpx.Response(200, json=_ka10101_body([_row("1", "001", "OK")])),
        "2": httpx.Response(200, json=_ka10101_body([_row("2", "001", "OK")])),
        "4": httpx.Response(200, json=_ka10101_body([_row("4", "001", "OK")])),
        "7": httpx.Response(200, json=_ka10101_body([_row("7", "001", "OK")])),
    }
    use_case = _build_use_case(
        session_provider=session_provider,
        handler=_make_handler(responses),
    )

    result = await use_case.execute()
    by_market = {m.market_code: m for m in result.markets}
    assert by_market["0"].error is not None
    assert "BusinessError" in by_market["0"].error
    assert all(by_market[m].succeeded for m in ("1", "2", "4", "7"))
    assert result.total_upserted == 4


@pytest.mark.asyncio
async def test_all_markets_fail_returns_full_result(
    session_provider,
    cleanup_sectors,
) -> None:
    """5 시장 모두 502 — 결과 dataclass 정상 반환 (예외 전파 X)."""
    responses = {mrkt_tp: httpx.Response(502) for mrkt_tp in SUPPORTED_MARKETS}
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
    cleanup_sectors,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """같은 응답 두 번 sync — total_upserted 동일, total_deactivated == 0."""
    responses = {
        mrkt_tp: httpx.Response(
            200,
            json=_ka10101_body([_row(mrkt_tp, "001", f"{mrkt_tp}-A")]),
        )
        for mrkt_tp in SUPPORTED_MARKETS
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
async def test_deprecated_sector_marked_inactive(
    session_provider,
    cleanup_sectors,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """첫 sync 후 두 번째 응답에서 sector 빠지면 is_active=False."""
    first_responses = {
        "0": httpx.Response(
            200,
            json=_ka10101_body(
                [
                    _row("0", "001", "유지"),
                    _row("0", "002", "폐지대상"),
                ]
            ),
        ),
        "1": httpx.Response(200, json=_ka10101_body([])),
        "2": httpx.Response(200, json=_ka10101_body([])),
        "4": httpx.Response(200, json=_ka10101_body([])),
        "7": httpx.Response(200, json=_ka10101_body([])),
    }

    second_responses = {
        "0": httpx.Response(
            200,
            json=_ka10101_body([_row("0", "001", "유지")]),  # 002 빠짐
        ),
        "1": httpx.Response(200, json=_ka10101_body([])),
        "2": httpx.Response(200, json=_ka10101_body([])),
        "4": httpx.Response(200, json=_ka10101_body([])),
        "7": httpx.Response(200, json=_ka10101_body([])),
    }

    use_case_first = _build_use_case(
        session_provider=session_provider,
        handler=_make_handler(first_responses),
    )
    await use_case_first.execute()

    use_case_second = _build_use_case(
        session_provider=session_provider,
        handler=_make_handler(second_responses),
    )
    result = await use_case_second.execute()

    by_market = {m.market_code: m for m in result.markets}
    assert by_market["0"].deactivated == 1

    async with commit_sessionmaker() as s:
        repo = SectorRepository(s)
        active = await repo.list_by_market("0", only_active=True)
        all_rows = await repo.list_by_market("0", only_active=False)
    assert {r.sector_code for r in active} == {"001"}
    assert {(r.sector_code, r.is_active) for r in all_rows} == {("001", True), ("002", False)}


@pytest.mark.asyncio
async def test_reappearing_sector_reactivated(
    session_provider,
    cleanup_sectors,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """비활성화된 sector 가 다시 응답에 등장하면 is_active=True 로 복원."""
    # phase 1: 첫 sync
    phase1 = {
        "0": httpx.Response(200, json=_ka10101_body([_row("0", "001", "v1")])),
        "1": httpx.Response(200, json=_ka10101_body([])),
        "2": httpx.Response(200, json=_ka10101_body([])),
        "4": httpx.Response(200, json=_ka10101_body([])),
        "7": httpx.Response(200, json=_ka10101_body([])),
    }
    await _build_use_case(session_provider=session_provider, handler=_make_handler(phase1)).execute()

    # phase 2: sector 빠짐 → 비활성화
    phase2 = {
        "0": httpx.Response(200, json=_ka10101_body([])),
        "1": httpx.Response(200, json=_ka10101_body([])),
        "2": httpx.Response(200, json=_ka10101_body([])),
        "4": httpx.Response(200, json=_ka10101_body([])),
        "7": httpx.Response(200, json=_ka10101_body([])),
    }
    await _build_use_case(session_provider=session_provider, handler=_make_handler(phase2)).execute()

    # phase 3: 같은 sector 재등장 + name 변경
    phase3 = {
        "0": httpx.Response(200, json=_ka10101_body([_row("0", "001", "v3-재등장")])),
        "1": httpx.Response(200, json=_ka10101_body([])),
        "2": httpx.Response(200, json=_ka10101_body([])),
        "4": httpx.Response(200, json=_ka10101_body([])),
        "7": httpx.Response(200, json=_ka10101_body([])),
    }
    await _build_use_case(session_provider=session_provider, handler=_make_handler(phase3)).execute()

    async with commit_sessionmaker() as s:
        repo = SectorRepository(s)
        active = await repo.list_by_market("0", only_active=True)
    assert len(active) == 1
    assert active[0].sector_code == "001"
    assert active[0].sector_name == "v3-재등장"
    assert active[0].is_active is True


@pytest.mark.asyncio
async def test_market_name_changed_updates_sector_name(
    session_provider,
    cleanup_sectors,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """code 동일 + name 다름 → sector_name UPDATE."""
    phase1 = {
        "0": httpx.Response(200, json=_ka10101_body([_row("0", "001", "기존명")])),
        "1": httpx.Response(200, json=_ka10101_body([])),
        "2": httpx.Response(200, json=_ka10101_body([])),
        "4": httpx.Response(200, json=_ka10101_body([])),
        "7": httpx.Response(200, json=_ka10101_body([])),
    }
    await _build_use_case(session_provider=session_provider, handler=_make_handler(phase1)).execute()

    phase2 = {
        "0": httpx.Response(200, json=_ka10101_body([_row("0", "001", "변경명")])),
        "1": httpx.Response(200, json=_ka10101_body([])),
        "2": httpx.Response(200, json=_ka10101_body([])),
        "4": httpx.Response(200, json=_ka10101_body([])),
        "7": httpx.Response(200, json=_ka10101_body([])),
    }
    await _build_use_case(session_provider=session_provider, handler=_make_handler(phase2)).execute()

    async with commit_sessionmaker() as s:
        repo = SectorRepository(s)
        rows = await repo.list_by_market("0")
    assert rows[0].sector_name == "변경명"


# =============================================================================
# 도메인 예외 노출 안전성
# =============================================================================


def test_dto_outcome_succeeded_property() -> None:
    from app.application.service.sector_service import MarketSyncOutcome

    ok = MarketSyncOutcome(market_code="0", fetched=1, upserted=1, deactivated=0)
    fail = MarketSyncOutcome(market_code="0", fetched=0, upserted=0, deactivated=0, error="X")
    assert ok.succeeded is True
    assert fail.succeeded is False


def test_dto_result_all_succeeded_property() -> None:
    from app.application.service.sector_service import (
        MarketSyncOutcome,
        SectorSyncResult,
    )

    all_ok = SectorSyncResult(
        markets=[MarketSyncOutcome(market_code="0", fetched=0, upserted=0, deactivated=0)],
        total_fetched=0,
        total_upserted=0,
        total_deactivated=0,
    )
    has_fail = SectorSyncResult(
        markets=[
            MarketSyncOutcome(market_code="0", fetched=0, upserted=0, deactivated=0),
            MarketSyncOutcome(market_code="1", fetched=0, upserted=0, deactivated=0, error="X"),
        ],
        total_fetched=0,
        total_upserted=0,
        total_deactivated=0,
    )
    assert all_ok.all_succeeded is True
    assert has_fail.all_succeeded is False
