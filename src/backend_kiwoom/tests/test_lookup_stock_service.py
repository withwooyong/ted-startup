"""LookupStockUseCase (B-β) 통합 테스트 — testcontainers PG16 + ka10100 MockTransport.

stock_master_service 의 SyncStockMasterUseCase 패턴 일관:
- session_provider 가 매 호출마다 새 AsyncSession (mini txn)
- Stock ORM/Repository 는 ka10099 가 정의한 것 재사용 (UNIQUE stock_code)
- mock_env 안전판 (§4.2)
- KiwoomError 는 caller 결정 — UseCase 가 swallow 안 함

검증 (§9.2):
1. INSERT (DB miss) — stock 비어있고 정상 응답 → row 1 INSERT, returned Stock.id 채워짐
2. UPDATE (DB hit) — 기존 row 갱신, fetched_at 변경, is_active=True
3. 비활성 stock 재활성화 — is_active=false 였던 row 가 응답 등장 시 True 복원
4. ensure_exists DB hit — 이미 존재 → ka10100 호출 안 함
5. ensure_exists DB miss — 비어있음 → ka10100 호출 + INSERT
6. ensure_exists 의 ka10100 실패 → KiwoomError raise (DB 변경 없음)
7. 같은 code 동시 ensure_exists 2회 → 두 호출 모두 성공, ON CONFLICT 로 row 1개
8. mock 환경 강제 false → DB nxt_enable=False
9. return_code=1 → KiwoomBusinessError, INSERT 안 됨
"""

from __future__ import annotations

import asyncio
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
from app.adapter.out.kiwoom._exceptions import (
    KiwoomBusinessError,
    KiwoomCredentialRejectedError,
    KiwoomError,
)
from app.adapter.out.kiwoom.stkinfo import KiwoomStkInfoClient
from app.adapter.out.persistence.repositories.stock import StockRepository
from app.application.service.stock_master_service import LookupStockUseCase

# =============================================================================
# 픽스처 — UseCase 전용 (commit engine + cleanup)
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


def _ka10100_body(
    stock_code: str = "005930",
    *,
    name: str = "삼성전자",
    market_code: str = "0",
    nxt_enable: str = "Y",
    list_count: str = "0000000026034239",
    last_price: str = "00136000",
    reg_day: str = "20090803",
    state: str = "정상",
    return_code: int = 0,
    return_msg: str = "정상",
) -> dict[str, Any]:
    return {
        "code": stock_code,
        "name": name,
        "listCount": list_count,
        "auditInfo": "정상",
        "regDay": reg_day,
        "lastPrice": last_price,
        "state": state,
        "marketCode": market_code,
        "marketName": "거래소",
        "upName": "전기전자",
        "upSizeName": "대형주",
        "companyClassName": "",
        "orderWarning": "0",
        "nxtEnable": nxt_enable,
        "return_code": return_code,
        "return_msg": return_msg,
    }


class _SpyHandler:
    """호출 횟수 + 마지막 stk_cd 추적."""

    def __init__(self, response_factory) -> None:
        self.call_count = 0
        self.last_stk_cd: str | None = None
        self._factory = response_factory

    def __call__(self, request: httpx.Request) -> httpx.Response:
        import json

        self.call_count += 1
        try:
            self.last_stk_cd = json.loads(request.content).get("stk_cd")
        except Exception:  # noqa: BLE001
            self.last_stk_cd = None
        return self._factory(request)


def _build_use_case(
    *,
    session_provider,
    handler,
    mock_env: bool = False,
) -> LookupStockUseCase:
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
    return LookupStockUseCase(
        session_provider=session_provider,
        stkinfo_client=stkinfo,
        mock_env=mock_env,
    )


# =============================================================================
# 1. INSERT (DB miss)
# =============================================================================


@pytest.mark.asyncio
async def test_execute_inserts_when_db_miss(
    session_provider,
    cleanup_stocks,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    spy = _SpyHandler(lambda _r: httpx.Response(200, json=_ka10100_body("005930")))
    use_case = _build_use_case(session_provider=session_provider, handler=spy)

    stock = await use_case.execute("005930")

    assert stock.id is not None
    assert stock.stock_code == "005930"
    assert stock.stock_name == "삼성전자"
    assert stock.is_active is True
    assert stock.market_code == "0"
    assert stock.list_count == 26034239
    assert stock.last_price == 136000
    assert stock.nxt_enable is True
    assert spy.call_count == 1
    assert spy.last_stk_cd == "005930"

    async with commit_sessionmaker() as s:
        repo = StockRepository(s)
        persisted = await repo.find_by_code("005930")
    assert persisted is not None
    assert persisted.id == stock.id


# =============================================================================
# 2. UPDATE (DB hit) — 모든 필드 갱신 + fetched_at 변경
# =============================================================================


@pytest.mark.asyncio
async def test_execute_updates_existing_row(
    session_provider,
    cleanup_stocks,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """1차 sync 후 ka10100 으로 갱신 — 가격/상태 변경 반영."""
    # 1차 — 초기 데이터 INSERT
    spy1 = _SpyHandler(lambda _r: httpx.Response(200, json=_ka10100_body("005930", last_price="00100000")))
    uc1 = _build_use_case(session_provider=session_provider, handler=spy1)
    initial = await uc1.execute("005930")
    initial_fetched_at = initial.fetched_at

    # 2차 — 가격 변경 응답
    spy2 = _SpyHandler(
        lambda _r: httpx.Response(
            200,
            json=_ka10100_body("005930", last_price="00136000", state="증거금40%"),
        )
    )
    uc2 = _build_use_case(session_provider=session_provider, handler=spy2)
    updated = await uc2.execute("005930")

    assert updated.id == initial.id, "같은 row — UPDATE"
    assert updated.last_price == 136000
    assert updated.state == "증거금40%"
    assert updated.fetched_at >= initial_fetched_at

    async with commit_sessionmaker() as s:
        repo = StockRepository(s)
        all_rows = await repo.list_by_filters(only_active=False)
    assert len(all_rows) == 1, "row 1개만 있어야 — INSERT 가 아님"


# =============================================================================
# 3. 비활성 stock 재활성화
# =============================================================================


@pytest.mark.asyncio
async def test_execute_reactivates_deactivated_stock(
    session_provider,
    cleanup_stocks,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """이전에 is_active=False 됐던 row 가 ka10100 응답에 등장 → True 복원."""
    # 1차 INSERT
    spy1 = _SpyHandler(lambda _r: httpx.Response(200, json=_ka10100_body("005930")))
    await _build_use_case(session_provider=session_provider, handler=spy1).execute("005930")

    # 직접 비활성화 (운영 폐지 시뮬)
    from sqlalchemy import update

    from app.adapter.out.persistence.models import Stock

    async with commit_sessionmaker() as s:
        await s.execute(update(Stock).where(Stock.stock_code == "005930").values(is_active=False))
        await s.commit()

    # 재활성화 — ka10100 응답 등장 = 살아있음
    spy2 = _SpyHandler(lambda _r: httpx.Response(200, json=_ka10100_body("005930")))
    stock = await _build_use_case(session_provider=session_provider, handler=spy2).execute("005930")

    assert stock.is_active is True


# =============================================================================
# 4-5. ensure_exists — DB hit / DB miss
# =============================================================================


@pytest.mark.asyncio
async def test_ensure_exists_db_hit_skips_kiwoom_call(
    session_provider,
    cleanup_stocks,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """이미 DB 에 있으면 ka10100 호출 안 함 (RPS 보존)."""
    # 사전 INSERT
    spy_seed = _SpyHandler(lambda _r: httpx.Response(200, json=_ka10100_body("005930")))
    await _build_use_case(session_provider=session_provider, handler=spy_seed).execute("005930")

    # ensure_exists — handler 가 호출되면 안 됨
    spy = _SpyHandler(lambda _r: httpx.Response(500))  # 호출 시 실패
    uc = _build_use_case(session_provider=session_provider, handler=spy)
    stock = await uc.ensure_exists("005930")

    assert stock.stock_code == "005930"
    assert spy.call_count == 0, "DB hit 시 ka10100 호출 안 함"


@pytest.mark.asyncio
async def test_ensure_exists_db_miss_triggers_lookup(
    session_provider,
    cleanup_stocks,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """DB 비어있으면 ka10100 호출 + INSERT."""
    spy = _SpyHandler(lambda _r: httpx.Response(200, json=_ka10100_body("005930")))
    uc = _build_use_case(session_provider=session_provider, handler=spy)

    stock = await uc.ensure_exists("005930")

    assert stock.stock_code == "005930"
    assert stock.is_active is True
    assert spy.call_count == 1


# =============================================================================
# 6. ensure_exists 의 ka10100 실패 — DB 변경 없음
# =============================================================================


@pytest.mark.asyncio
async def test_ensure_exists_kiwoom_failure_raises_no_db_change(
    session_provider,
    cleanup_stocks,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """ka10100 502 → KiwoomError raise. stock 테이블 변경 없음."""
    spy = _SpyHandler(lambda _r: httpx.Response(502))
    uc = _build_use_case(session_provider=session_provider, handler=spy)

    with pytest.raises(KiwoomError):
        await uc.ensure_exists("005930")

    async with commit_sessionmaker() as s:
        repo = StockRepository(s)
        all_rows = await repo.list_by_filters(only_active=False)
    assert all_rows == [], "DB 변경 없음 — 트랜잭션 격리"


# =============================================================================
# 7. 동시 ensure_exists — race 흡수 (ON CONFLICT)
# =============================================================================


@pytest.mark.asyncio
async def test_concurrent_ensure_exists_results_in_single_row(
    session_provider,
    cleanup_stocks,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """같은 stock_code 두 코루틴이 동시 호출 → 두 호출 모두 성공, row 1개 (ON CONFLICT 흡수)."""
    spy = _SpyHandler(lambda _r: httpx.Response(200, json=_ka10100_body("005930")))
    uc = _build_use_case(session_provider=session_provider, handler=spy)

    results = await asyncio.gather(
        uc.ensure_exists("005930"),
        uc.ensure_exists("005930"),
    )

    assert all(r.stock_code == "005930" for r in results)

    async with commit_sessionmaker() as s:
        repo = StockRepository(s)
        all_rows = await repo.list_by_filters(only_active=False)
    assert len(all_rows) == 1, "ON CONFLICT (stock_code) 가 race 흡수"


# =============================================================================
# 8. mock 환경 안전판
# =============================================================================


@pytest.mark.asyncio
async def test_mock_env_forces_nxt_enable_false(
    session_provider,
    cleanup_stocks,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """mock_env=True + 응답 nxtEnable="Y" → DB nxt_enable=False (mock 도메인 NXT 미지원)."""
    spy = _SpyHandler(lambda _r: httpx.Response(200, json=_ka10100_body("005930", nxt_enable="Y")))
    uc = _build_use_case(session_provider=session_provider, handler=spy, mock_env=True)
    stock = await uc.execute("005930")

    assert stock.nxt_enable is False, "mock_env 면 응답 nxtEnable 무시"


# =============================================================================
# 9. return_code != 0 → KiwoomBusinessError, INSERT 안 됨
# =============================================================================


@pytest.mark.asyncio
async def test_business_error_no_insert(
    session_provider,
    cleanup_stocks,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """존재하지 않는 종목 (return_code=1) → KiwoomBusinessError, DB 변경 없음."""
    spy = _SpyHandler(
        lambda _r: httpx.Response(
            200,
            json={"return_code": 1, "return_msg": "존재하지 않는 종목"},
        )
    )
    uc = _build_use_case(session_provider=session_provider, handler=spy)

    with pytest.raises(KiwoomBusinessError):
        await uc.execute("999999")

    async with commit_sessionmaker() as s:
        repo = StockRepository(s)
        all_rows = await repo.list_by_filters(only_active=False)
    assert all_rows == [], "Business error 시 INSERT 안 됨"


# =============================================================================
# 자격증명 거부 — 401 → KiwoomCredentialRejectedError
# =============================================================================


@pytest.mark.asyncio
async def test_credential_rejected_no_insert(
    session_provider,
    cleanup_stocks,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    spy = _SpyHandler(lambda _r: httpx.Response(401))
    uc = _build_use_case(session_provider=session_provider, handler=spy)

    with pytest.raises(KiwoomCredentialRejectedError):
        await uc.execute("005930")

    async with commit_sessionmaker() as s:
        repo = StockRepository(s)
        all_rows = await repo.list_by_filters(only_active=False)
    assert all_rows == []


# =============================================================================
# 1R 회귀 가드 — 2b H2 / 2a M2 / 2b M2 fix 검증
# =============================================================================


@pytest.mark.asyncio
async def test_execute_maps_non_numeric_value_to_validation_error(
    session_provider,
    cleanup_stocks,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """1R 2b H2 — listCount 비숫자 시 raw ValueError → KiwoomResponseValidationError 매핑.

    매핑 누락 시 라우터 except 망에서 잡지 못해 500 누설 위험. B-α 의 _sync_one_market
    패턴 일관 + __cause__/__context__ None 확인.
    """
    from app.adapter.out.kiwoom._exceptions import KiwoomResponseValidationError

    spy = _SpyHandler(lambda _r: httpx.Response(200, json=_ka10100_body("005930", list_count="abc")))
    uc = _build_use_case(session_provider=session_provider, handler=spy)

    with pytest.raises(KiwoomResponseValidationError) as exc_info:
        await uc.execute("005930")

    err = exc_info.value
    assert err.__cause__ is None, "1R 2b H2 — cause leak 회귀"
    assert err.__context__ is None, "1R 2b H2 — context leak 회귀"

    async with commit_sessionmaker() as s:
        repo = StockRepository(s)
        all_rows = await repo.list_by_filters(only_active=False)
    assert all_rows == [], "정규화 실패 시 INSERT 안 됨"


@pytest.mark.asyncio
async def test_ensure_exists_refetches_inactive_stock(
    session_provider,
    cleanup_stocks,
    commit_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """1R 2a M2 — DB hit 이지만 is_active=False 면 키움 재조회 + 활성화 복원.

    Phase C 의 OHLCV 적재가 비활성 stock 을 그대로 사용하지 않도록 안전망.
    """
    # 1차 INSERT
    spy_seed = _SpyHandler(lambda _r: httpx.Response(200, json=_ka10100_body("005930")))
    await _build_use_case(session_provider=session_provider, handler=spy_seed).execute("005930")

    # 직접 비활성화 (운영 폐지 시뮬)
    from sqlalchemy import update

    from app.adapter.out.persistence.models import Stock

    async with commit_sessionmaker() as s:
        await s.execute(update(Stock).where(Stock.stock_code == "005930").values(is_active=False))
        await s.commit()

    # ensure_exists — 비활성이므로 키움 재호출 + 활성 복원
    spy = _SpyHandler(lambda _r: httpx.Response(200, json=_ka10100_body("005930")))
    uc = _build_use_case(session_provider=session_provider, handler=spy)
    stock = await uc.ensure_exists("005930")

    assert stock.is_active is True, "비활성 stock 재조회 후 활성화 복원"
    assert spy.call_count == 1, "1R 2a M2 — 비활성이면 키움 호출 발동"


@pytest.mark.asyncio
async def test_ensure_exists_validates_stk_cd(
    session_provider,
    cleanup_stocks,
) -> None:
    """1R 2b M2 — DB hit 분기에서도 stk_cd 검증 우회 차단.

    잘못된 stock_code (5자리 / 영문) 면 ValueError raise — DB lookup 자체 안 함.
    """
    spy = _SpyHandler(lambda _r: httpx.Response(500))
    uc = _build_use_case(session_provider=session_provider, handler=spy)

    for invalid in ("00593", "ABC123", "005930_NX", ""):
        with pytest.raises(ValueError):
            await uc.ensure_exists(invalid)

    assert spy.call_count == 0, "잘못된 stk_cd → 키움 호출 안 함"
