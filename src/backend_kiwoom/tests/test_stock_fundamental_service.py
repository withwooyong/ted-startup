"""SyncStockFundamentalUseCase (B-γ-2) — execute + refresh_one + per-stock skip 정책.

설계: endpoint-05-ka10001.md § 6.3 + ADR § 14.6.

Phase B-α 의 SyncStockMasterUseCase 패턴 차용 — per-stock try/except + KiwoomError
catch + outcome.error 격리 + 다음 종목 진행 (partial-failure 정책 (a) per-stock skip
+ counter, ADR § 14.5 / 2R C-M3 결정).

검증:
1. execute — active stock 3건 정상 sync → success=3 / failed=0
2. execute — only_market_codes 필터
3. execute — target_date 옵션 (백필)
4. execute — 1건 KiwoomBusinessError 발생 → success=2 / failed=1, errors[0]
5. execute — 1건 KiwoomCredentialRejectedError → 다음 종목 진행
6. execute — 1건 KiwoomResponseValidationError (Pydantic 위반) → 다음 종목 진행
7. execute — stk_nm mismatch → logger.warning + 적재는 진행
8. execute — 비활성 stock 은 순회 안 함
9. execute — stock_id resolution 시 strip_kiwoom_suffix 적용
10. execute — fundamental_hash 산출 + DB 저장
11. execute — 같은 날 두 번 호출 멱등 (UNIQUE 제약 통과)
12. refresh_one — 단건 새로고침 → upsert + Stock + StockFundamental 반환
13. refresh_one — KiwoomBusinessError raw 전파 (caller=router)
14. refresh_one — Stock 미존재 시 ValueError (어댑터 사전 검증 + repository expected_stock_code)
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

from app.adapter.out.kiwoom._exceptions import (
    KiwoomBusinessError,
    KiwoomCredentialRejectedError,
    KiwoomResponseValidationError,
)
from app.adapter.out.kiwoom.stkinfo import (
    KiwoomStkInfoClient,
    StockBasicInfoResponse,
)
from app.adapter.out.persistence.repositories.stock_fundamental import (
    StockFundamentalRepository,
)
from app.application.service.stock_fundamental_service import (
    FundamentalSyncOutcome,
    FundamentalSyncResult,
    SyncStockFundamentalUseCase,
)

# ---------- Fixtures ----------
#
# 본 테스트는 UseCase 가 자체 session_provider 로 commit 하므로 conftest 의
# session 픽스처 (트랜잭션+rollback) 와 상호 비호환. session 픽스처를 override 해서
# commit 가능한 세션 + autouse cleanup 으로 매 테스트 격리 (B-α test_stock_master_service
# 의 commit_sessionmaker + cleanup_stocks 패턴 차용).


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """conftest 의 트랜잭션+rollback session 을 override — 본 테스트는 commit 필요."""
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
    *,
    per: str = "15.20",
    eps: str = "5000",
    return_code: int = 0,
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
            "per": per,
            "eps": eps,
            "roe": "12.50",
            "pbr": "1.20",
            "ev": "8.30",
            "bps": "70000",
            "cur_prc": "75800",
            "return_code": return_code,
            "return_msg": "정상" if return_code == 0 else "오류",
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


def _stub_stkinfo_client(responses: dict[str, StockBasicInfoResponse | Exception]) -> KiwoomStkInfoClient:
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


# ---------- 1. execute — 정상 ----------


@pytest.mark.asyncio
async def test_execute_returns_success_count_for_active_stocks(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    await _create_active_stock(session, "005930", "삼성전자", "0")
    await _create_active_stock(session, "000660", "SK하이닉스", "0")
    await _create_active_stock(session, "035720", "카카오", "0")
    await session.commit()

    stkinfo = _stub_stkinfo_client(
        {
            "005930": _make_response("005930", "삼성전자"),
            "000660": _make_response("000660", "SK하이닉스"),
            "035720": _make_response("035720", "카카오"),
        }
    )
    uc = SyncStockFundamentalUseCase(session_provider=session_provider, stkinfo_client=stkinfo)

    result = await uc.execute()

    assert isinstance(result, FundamentalSyncResult)
    assert result.total == 3
    assert result.success == 3
    assert result.failed == 0
    assert result.asof_date == date.today()


# ---------- 2. only_market_codes 필터 ----------


@pytest.mark.asyncio
async def test_execute_only_market_codes_filters_stocks(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    await _create_active_stock(session, "005930", "KOSPI종목", "0")
    await _create_active_stock(session, "100100", "KOSDAQ종목", "10")
    await session.commit()

    stkinfo = _stub_stkinfo_client(
        {
            "005930": _make_response("005930", "KOSPI종목"),
            "100100": _make_response("100100", "KOSDAQ종목"),
        }
    )
    uc = SyncStockFundamentalUseCase(session_provider=session_provider, stkinfo_client=stkinfo)

    result = await uc.execute(only_market_codes=["0"])

    assert result.total == 1
    assert result.success == 1


# ---------- 3. target_date 옵션 ----------


@pytest.mark.asyncio
async def test_execute_target_date_persists_with_specified_date(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    await _create_active_stock(session, "005930", "삼성전자", "0")
    await session.commit()

    stkinfo = _stub_stkinfo_client({"005930": _make_response("005930", "삼성전자")})
    uc = SyncStockFundamentalUseCase(session_provider=session_provider, stkinfo_client=stkinfo)

    backfill_date = date(2026, 4, 1)
    result = await uc.execute(target_date=backfill_date)

    assert result.asof_date == backfill_date


# ---------- 4-6. partial-failure — per-stock skip ----------


@pytest.mark.asyncio
async def test_execute_skips_failed_stock_and_continues(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    """ADR § 14.6 — partial-failure 정책 (a): per-stock try/except → 다음 종목 진행."""
    await _create_active_stock(session, "005930", "삼성전자", "0")
    await _create_active_stock(session, "999999", "존재안함", "0")
    await _create_active_stock(session, "000660", "SK하이닉스", "0")
    await session.commit()

    stkinfo = _stub_stkinfo_client(
        {
            "005930": _make_response("005930", "삼성전자"),
            "999999": KiwoomBusinessError(api_id="ka10001", return_code=1, message="존재하지 않는 종목"),
            "000660": _make_response("000660", "SK하이닉스"),
        }
    )
    uc = SyncStockFundamentalUseCase(session_provider=session_provider, stkinfo_client=stkinfo)

    result = await uc.execute()

    assert result.total == 3
    assert result.success == 2
    assert result.failed == 1
    assert len(result.errors) == 1
    failed_outcome = result.errors[0]
    assert isinstance(failed_outcome, FundamentalSyncOutcome)
    assert failed_outcome.stock_code == "999999"
    assert failed_outcome.error_class == "KiwoomBusinessError"


@pytest.mark.asyncio
async def test_execute_handles_credential_rejected_per_stock(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    """KiwoomCredentialRejectedError 한 종목 발생 → 다음 종목 진행 (자격증명 문제는 outcome 으로 노출)."""
    await _create_active_stock(session, "005930", "삼성전자", "0")
    await _create_active_stock(session, "000660", "SK하이닉스", "0")
    await session.commit()

    stkinfo = _stub_stkinfo_client(
        {
            "005930": KiwoomCredentialRejectedError("401 거부"),
            "000660": _make_response("000660", "SK하이닉스"),
        }
    )
    uc = SyncStockFundamentalUseCase(session_provider=session_provider, stkinfo_client=stkinfo)

    result = await uc.execute()

    assert result.total == 2
    assert result.success == 1
    assert result.failed == 1
    assert result.errors[0].error_class == "KiwoomCredentialRejectedError"


@pytest.mark.asyncio
async def test_execute_handles_validation_error_per_stock(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    await _create_active_stock(session, "005930", "삼성전자", "0")
    await session.commit()

    stkinfo = _stub_stkinfo_client(
        {"005930": KiwoomResponseValidationError("ka10001 응답 검증 실패")}
    )
    uc = SyncStockFundamentalUseCase(session_provider=session_provider, stkinfo_client=stkinfo)

    result = await uc.execute()

    assert result.success == 0
    assert result.failed == 1
    assert result.errors[0].error_class == "KiwoomResponseValidationError"


# ---------- 7. mismatch alert ----------


@pytest.mark.asyncio
async def test_execute_logs_warning_on_stk_name_mismatch(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """응답 stk_nm ≠ Stock.stock_name → logger.warning, 적재는 진행 (계획서 § 6.3).

    structlog 와 stdlib logging routing 으로 caplog 에 안 잡히는 경우 — logger
    객체를 직접 spy 처리.
    """
    await _create_active_stock(session, "005930", "삼성전자", "0")
    await session.commit()

    import app.application.service.stock_fundamental_service as svc

    captured: list[str] = []

    def _spy(msg: str, *args: object) -> None:
        captured.append(msg % args if args else msg)

    monkeypatch.setattr(svc.logger, "warning", _spy)

    stkinfo = _stub_stkinfo_client({"005930": _make_response("005930", "삼성전자(이상한이름)")})
    uc = SyncStockFundamentalUseCase(session_provider=session_provider, stkinfo_client=stkinfo)
    result = await uc.execute()

    assert result.success == 1
    mismatch_logs = [m for m in captured if "mismatch" in m.lower()]
    assert len(mismatch_logs) == 1, f"captured warnings: {captured}"


# ---------- 8. 비활성 stock 미순회 ----------


@pytest.mark.asyncio
async def test_execute_skips_inactive_stocks(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    await _create_active_stock(session, "005930", "삼성전자", "0", is_active=True)
    await _create_active_stock(session, "999999", "폐지", "0", is_active=False)
    await session.commit()

    called: list[str] = []

    async def _fetch(stock_code: str) -> StockBasicInfoResponse:
        called.append(stock_code)
        return _make_response(stock_code, "test")

    stkinfo = AsyncMock(spec=KiwoomStkInfoClient)
    stkinfo.fetch_basic_info = _fetch
    uc = SyncStockFundamentalUseCase(session_provider=session_provider, stkinfo_client=stkinfo)

    result = await uc.execute()

    assert called == ["005930"], "비활성 stock 은 호출 안 함"
    assert result.total == 1


# ---------- 9. stock_id resolution + DB 영속 ----------


@pytest.mark.asyncio
async def test_execute_persists_fundamental_with_correct_stock_id(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    """active stock → fundamental row 생성 (stock_id FK 정확)."""
    stock_id = await _create_active_stock(session, "005930", "삼성전자", "0")
    await session.commit()

    stkinfo = _stub_stkinfo_client({"005930": _make_response("005930", "삼성전자")})
    uc = SyncStockFundamentalUseCase(session_provider=session_provider, stkinfo_client=stkinfo)
    await uc.execute()

    repo = StockFundamentalRepository(session)
    found = await repo.find_latest(stock_id)
    assert found is not None
    assert found.stock_id == stock_id
    assert found.exchange == "KRX"
    assert found.fundamental_hash is not None


@pytest.mark.asyncio
async def test_execute_strips_suffix_from_response_stk_cd(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    """응답 stk_cd 가 `005930_NX` 메아리쳐도 base code 로 stock_id resolution."""
    stock_id = await _create_active_stock(session, "005930", "삼성전자", "0")
    await session.commit()

    stkinfo = _stub_stkinfo_client({"005930": _make_response("005930_NX", "삼성전자")})
    uc = SyncStockFundamentalUseCase(session_provider=session_provider, stkinfo_client=stkinfo)
    result = await uc.execute()

    assert result.success == 1
    repo = StockFundamentalRepository(session)
    assert (await repo.find_latest(stock_id)) is not None


# ---------- 10. 멱등성 ----------


@pytest.mark.asyncio
async def test_execute_idempotent_on_repeat(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    stock_id = await _create_active_stock(session, "005930", "삼성전자", "0")
    await session.commit()

    stkinfo = _stub_stkinfo_client({"005930": _make_response("005930", "삼성전자")})
    uc = SyncStockFundamentalUseCase(session_provider=session_provider, stkinfo_client=stkinfo)

    await uc.execute(target_date=date(2026, 5, 8))
    result2 = await uc.execute(target_date=date(2026, 5, 8))

    assert result2.success == 1

    res = await session.execute(
        text(
            "SELECT COUNT(*) FROM kiwoom.stock_fundamental WHERE stock_id = :sid AND asof_date = :d"
        ).bindparams(sid=stock_id, d=date(2026, 5, 8))
    )
    assert res.scalar_one() == 1, "UNIQUE 통과 — row 1개 유지"


# ---------- 11. refresh_one 단건 ----------


@pytest.mark.asyncio
async def test_refresh_one_returns_fundamental_for_existing_stock(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    stock_id = await _create_active_stock(session, "005930", "삼성전자", "0")
    await session.commit()

    stkinfo = _stub_stkinfo_client({"005930": _make_response("005930", "삼성전자")})
    uc = SyncStockFundamentalUseCase(session_provider=session_provider, stkinfo_client=stkinfo)

    fundamental = await uc.refresh_one("005930")

    assert fundamental.stock_id == stock_id
    assert fundamental.fundamental_hash is not None


@pytest.mark.asyncio
async def test_refresh_one_propagates_business_error(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
) -> None:
    """refresh_one 은 router 가 받도록 KiwoomBusinessError 그대로 전파 (B-β execute 패턴)."""
    await _create_active_stock(session, "005930", "삼성전자", "0")
    await session.commit()

    stkinfo = _stub_stkinfo_client(
        {"005930": KiwoomBusinessError(api_id="ka10001", return_code=1, message="비즈니스 거부")}
    )
    uc = SyncStockFundamentalUseCase(session_provider=session_provider, stkinfo_client=stkinfo)

    with pytest.raises(KiwoomBusinessError):
        await uc.refresh_one("005930")


@pytest.mark.asyncio
async def test_refresh_one_raises_when_stock_master_missing(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
) -> None:
    """Stock 마스터에 없는 종목 → ValueError. ensure_exists 미사용 (B-γ-2 결정)."""
    stkinfo = _stub_stkinfo_client({"005930": _make_response("005930", "삼성전자")})
    uc = SyncStockFundamentalUseCase(session_provider=session_provider, stkinfo_client=stkinfo)

    with pytest.raises(ValueError, match="stock master not found"):
        await uc.refresh_one("005930")


# =============================================================================
# 2R 회귀 — M-1 log injection escape
# =============================================================================


@pytest.mark.asyncio
async def test_mismatch_log_strips_control_characters_from_response_stock_name(
    session_provider: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B-γ-2 2R M-1 — 응답 stk_nm 의 newline/ANSI/NULL 등 control char 가 logger 에 박히지 않음.

    sink (Sentry/CloudWatch) 의 line 분리 / 색상 spoof / null injection 차단.
    """
    await _create_active_stock(session, "005930", "삼성전자", "0")
    await session.commit()

    import app.application.service.stock_fundamental_service as svc

    captured: list[str] = []

    def _spy(msg: str, *args: object) -> None:
        captured.append(msg % args if args else msg)

    monkeypatch.setattr(svc.logger, "warning", _spy)

    # 응답 stk_nm 에 newline + ANSI + NULL 박힘 — escape 후 logger 출력
    evil_name = "evil\nFAKE\x1b[31mRED\x00NULL"
    stkinfo = _stub_stkinfo_client({"005930": _make_response("005930", evil_name)})
    uc = SyncStockFundamentalUseCase(session_provider=session_provider, stkinfo_client=stkinfo)
    await uc.execute()

    mismatch_lines = [m for m in captured if "mismatch" in m.lower()]
    assert len(mismatch_lines) == 1
    rendered = mismatch_lines[0]
    # control char 모두 strip 됐는지 검증
    assert "\n" not in rendered, f"newline 박힘: {rendered!r}"
    assert "\x1b" not in rendered, f"ANSI escape 박힘: {rendered!r}"
    assert "\x00" not in rendered, f"NULL byte 박힘: {rendered!r}"
    assert "evilFAKERedNULL".replace("Red", "[31mRED").replace("[31m", "") in rendered or "evilFAKE" in rendered


def test_safe_for_log_strips_all_unsafe_chars() -> None:
    """B-γ-2 2R M-1 — _safe_for_log 단위 검증."""
    from app.application.service.stock_fundamental_service import _safe_for_log

    assert _safe_for_log("normal") == "normal"
    assert _safe_for_log("a\nb") == "ab"
    assert _safe_for_log("a\rb") == "ab"
    assert _safe_for_log("a\tb") == "ab"
    assert _safe_for_log("a\x00b") == "ab"
    assert _safe_for_log("a\x1b[31mb") == "a[31mb"  # ESC 만 strip, 나머지 chars 유지
    assert _safe_for_log("") == ""
    assert _safe_for_log(None) == ""


def test_safe_for_log_caps_length() -> None:
    """긴 값은 max_length cap."""
    from app.application.service.stock_fundamental_service import _safe_for_log

    assert _safe_for_log("X" * 100, max_length=10) == "X" * 10
    assert _safe_for_log("X" * 100) == "X" * 40  # default 40
