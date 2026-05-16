"""IngestRankingUseCase 5종 + Bulk 5종 — Phase F-4 통합 테스트.

설계: endpoint-18-ka10027.md § 6.3/6.4 + endpoint-19~22 + phase-f-4-rankings.md § 5.6.

본 테스트는 import 실패가 red 의도 (Step 0 TDD red):
- `app.application.service.ranking_service.IngestFluRtUpperUseCase` 외 9개 미존재
→ Step 1 신규 구현 후 green.

plan doc § 5.12 의 6 파일 분할 (test_ingest_flu_rt_use_case.py 등) 권고를 본 테스트는
**통합 1 파일**로 작성 — 5 endpoint 가 같은 service module + 같은 client + 같은 repository
공유라 maintainability 가 더 높음. ADR § 48 D-1 변형 결정 기록 예정.

검증 시나리오 (~22):

ka10027 (FLU_RT) 풀 — 단건 + Bulk:
1. 단건 정상 — fetch → lookup_codes → upsert → outcome.upserted = N
2. 단건 stock lookup miss → stock_id=NULL + stock_code_raw 보존
3. 단건 NXT `_NX` suffix → stock_code_raw 보존 (strip 후 stock_id 매핑)
4. 단건 KiwoomBusinessError → outcome.error = "business: 1"
5. 단건 F-3 D-7 SentinelStockCodeError catch (defense-in-depth) →
   outcome.error = SkipReason.SENTINEL_SKIP.value
6. 단건 used_filters → request_filters JSONB 적재 (재현)
7. 단건 primary_metric = flu_rt (`+29.86` → Decimal("29.86"))
8. Bulk 4 호출 매트릭스 (2 market × 2 sort) → outcomes 4건
9. Bulk 일부 호출 실패 → 나머지는 진행, outcome.error 분리
10. Bulk empty raw_rows → _empty_bulk_result (조기 반환, F-3 D-5 helper)
11. Bulk RankingBulkResult.errors_above_threshold tuple (D-11 빈 tuple default)
12. Bulk total_upserted property 집계

ka10030 (TODAY_VOLUME) 차이점:
13. nested payload D-9 — payload 에 {opmr, af_mkrt, bf_mkrt} 분리 보존
14. primary_metric = trde_qty BIGINT

ka10031 (PRED_VOLUME):
15. body 5 필드 + list key `pred_trde_qty_upper`

ka10032 (TRDE_PRICA):
16. primary_metric = trde_prica BIGINT (큰 거래대금)
17. body 3 필드 minimum

ka10023 (VOLUME_SDNIN):
18. primary_metric — sort_tp 분기 (sdnin_qty / sdnin_rt)
19. tm_tp body 필드

공통:
20. snapshot_at 인자 — caller (router/cron) 가 결정
21. session.commit Bulk 1회 (BATCH 분할 없음 — Bulk 가 4 호출만)
22. RankingType 5 endpoint outcome 분리
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.adapter.out.kiwoom._exceptions import KiwoomBusinessError
from app.adapter.out.kiwoom._records import (  # type: ignore[import]
    FluRtSortType,
    FluRtUpperRow,
    PredVolumeUpperRow,
    RankingExchangeType,
    RankingMarketType,
    RankingType,
    TodayVolumeUpperRow,
    TradeAmountUpperRow,
    VolumeSdninRow,
    VolumeSdninSortType,
)
from app.adapter.out.kiwoom.rkinfo import KiwoomRkInfoClient  # type: ignore[import]
from app.adapter.out.kiwoom.stkinfo import SentinelStockCodeError
from app.application.dto._shared import SkipReason
from app.application.service.ranking_service import (  # type: ignore[import]  # Step 1
    IngestFluRtUpperBulkUseCase,
    IngestFluRtUpperUseCase,
    IngestPredVolumeUpperBulkUseCase,
    IngestPredVolumeUpperUseCase,
    IngestTodayVolumeUpperBulkUseCase,
    IngestTodayVolumeUpperUseCase,
    IngestTradeAmountUpperBulkUseCase,
    IngestTradeAmountUpperUseCase,
    IngestVolumeSdninBulkUseCase,
    IngestVolumeSdninUseCase,
)

KST = ZoneInfo("Asia/Seoul")


# ---------------------------------------------------------------------------
# 공통 fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_ranking_tables(engine: AsyncEngine) -> AsyncIterator[None]:
    """각 테스트 전후 stock + ranking_snapshot 정리."""
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        await s.execute(text("TRUNCATE kiwoom.stock RESTART IDENTITY CASCADE"))
        await s.execute(text("TRUNCATE kiwoom.ranking_snapshot RESTART IDENTITY"))
        await s.commit()
    yield
    async with factory() as s:
        await s.execute(text("TRUNCATE kiwoom.stock RESTART IDENTITY CASCADE"))
        await s.execute(text("TRUNCATE kiwoom.ranking_snapshot RESTART IDENTITY"))
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


async def _create_stock(
    session: AsyncSession, code: str, name: str = "테스트종목"
) -> int:
    res = await session.execute(
        text(
            "INSERT INTO kiwoom.stock (stock_code, stock_name, market_code, is_active) "
            "VALUES (:c, :n, '0', TRUE) RETURNING id"
        ).bindparams(c=code, n=name)
    )
    sid = int(res.scalar_one())
    await session.commit()
    return sid


def _flu_rt_row(stk_cd: str = "005930", flu_rt: str = "+29.86") -> FluRtUpperRow:
    return FluRtUpperRow(
        stk_cls="0",
        stk_cd=stk_cd,
        stk_nm="삼성전자",
        cur_prc="+74800",
        pred_pre_sig="1",
        pred_pre="+17200",
        flu_rt=flu_rt,
        sel_req="207",
        buy_req="3820638",
        now_trde_qty="446203",
        cntr_str="346.54",
        cnt="4",
    )


def _today_volume_row(stk_cd: str = "005930") -> TodayVolumeUpperRow:
    return TodayVolumeUpperRow(
        stk_cd=stk_cd,
        stk_nm="삼성전자",
        cur_prc="+74800",
        pred_pre_sig="1",
        pred_pre="+17200",
        flu_rt="+29.86",
        trde_qty="446203",
        pred_rt="+15.23",
        trde_tern_rt="1.25",
        opmr_trde_qty="100000",
        opmr_pred_rt="+10.00",
        opmr_trde_rt="0.5",
        opmr_trde_amt="5000000",
        af_mkrt_trde_qty="0",
        af_mkrt_pred_rt="0.00",
        af_mkrt_trde_rt="0",
        af_mkrt_trde_amt="0",
        bf_mkrt_trde_qty="346203",
        bf_mkrt_pred_rt="+8.5",
        bf_mkrt_trde_rt="0.75",
        bf_mkrt_trde_amt="25900000",
    )


def _make_client_mock(method: str, return_value: tuple[list, dict]) -> AsyncMock:
    """KiwoomRkInfoClient AsyncMock — 특정 메서드 응답 세팅."""
    client = AsyncMock(spec=KiwoomRkInfoClient)
    getattr(client, method).return_value = return_value
    return client


SNAPSHOT_AT = datetime(2026, 5, 14, 19, 30, 0, tzinfo=KST)


# ===========================================================================
# ka10027 — 단건 (FluRt) 7건
# ===========================================================================


@pytest.mark.asyncio
async def test_flu_rt_single_normal(session: AsyncSession) -> None:
    """정상 — fetch → lookup → upsert → outcome.upserted = 1."""
    stock_id = await _create_stock(session, "005930")

    client = _make_client_mock(
        "fetch_flu_rt_upper",
        (
            [_flu_rt_row("005930", "+29.86")],
            {"mrkt_tp": "001", "sort_tp": "1", "stex_tp": "3"},
        ),
    )

    use_case = IngestFluRtUpperUseCase(
        session=session,
        rkinfo_client=client,
    )
    outcome = await use_case.execute(
        snapshot_at=SNAPSHOT_AT,
        market_type=RankingMarketType.KOSPI,
        sort_tp=FluRtSortType.UP_RATE,
        exchange_type=RankingExchangeType.UNIFIED,
    )
    await session.commit()

    assert outcome.ranking_type == RankingType.FLU_RT
    assert outcome.fetched == 1
    assert outcome.upserted == 1
    assert outcome.error is None
    assert outcome.sort_tp == "1"
    assert outcome.market_type == "001"

    # DB 검증 — primary_metric = flu_rt Decimal
    result = await session.execute(
        text(
            "SELECT primary_metric, stock_id, stock_code_raw, payload->>'cur_prc' "
            "FROM kiwoom.ranking_snapshot "
            "WHERE ranking_type = 'FLU_RT' AND snapshot_date = '2026-05-14'"
        )
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == Decimal("29.8600"), f"primary_metric (flu_rt) 정확성: {row[0]}"
    assert row[1] == stock_id
    assert row[2] == "005930"
    assert row[3] == "74800"


@pytest.mark.asyncio
async def test_flu_rt_single_lookup_miss_stock_id_null(session: AsyncSession) -> None:
    """stock 마스터 부재 → stock_id=NULL + stock_code_raw 보존 (D-8)."""
    client = _make_client_mock(
        "fetch_flu_rt_upper",
        ([_flu_rt_row("999999")], {"mrkt_tp": "001"}),
    )

    use_case = IngestFluRtUpperUseCase(session=session, rkinfo_client=client)
    outcome = await use_case.execute(snapshot_at=SNAPSHOT_AT)
    await session.commit()

    assert outcome.upserted == 1

    result = await session.execute(
        text(
            "SELECT stock_id, stock_code_raw FROM kiwoom.ranking_snapshot "
            "WHERE stock_code_raw = '999999'"
        )
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] is None, "lookup miss → stock_id NULL"
    assert row[1] == "999999"


@pytest.mark.asyncio
async def test_flu_rt_single_nxt_suffix_preserved(session: AsyncSession) -> None:
    """NXT `_NX` suffix — stock_code_raw 보존 + stock_id 매핑은 strip 후."""
    stock_id = await _create_stock(session, "005930")

    client = _make_client_mock(
        "fetch_flu_rt_upper",
        ([_flu_rt_row("005930_NX")], {"mrkt_tp": "001"}),
    )

    use_case = IngestFluRtUpperUseCase(session=session, rkinfo_client=client)
    await use_case.execute(snapshot_at=SNAPSHOT_AT)
    await session.commit()

    result = await session.execute(
        text(
            "SELECT stock_id, stock_code_raw FROM kiwoom.ranking_snapshot "
            "WHERE stock_code_raw = '005930_NX'"
        )
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == stock_id, "stk_cd strip 후 stock_id 매핑"
    assert row[1] == "005930_NX", "NXT suffix raw 보존"


@pytest.mark.asyncio
async def test_flu_rt_single_business_error_returns_outcome_error(
    session: AsyncSession,
) -> None:
    """KiwoomBusinessError → outcome.error = 'business: <return_code>'."""
    client = AsyncMock(spec=KiwoomRkInfoClient)
    client.fetch_flu_rt_upper.side_effect = KiwoomBusinessError(
        api_id="ka10027", return_code=1, message="잘못된 요청"
    )

    use_case = IngestFluRtUpperUseCase(session=session, rkinfo_client=client)
    outcome = await use_case.execute(snapshot_at=SNAPSHOT_AT)

    assert outcome.upserted == 0
    assert outcome.error is not None
    assert "business" in outcome.error.lower() or "1" in outcome.error


@pytest.mark.asyncio
async def test_flu_rt_single_sentinel_catch_d7_defense_in_depth(
    session: AsyncSession,
) -> None:
    """F-3 D-7 — SentinelStockCodeError catch (defense-in-depth).

    라우터 정규식 우회 또는 응답 row 의 stk_cd 가 sentinel 인 경우에 대비.
    """
    client = AsyncMock(spec=KiwoomRkInfoClient)
    client.fetch_flu_rt_upper.side_effect = SentinelStockCodeError("응답 stk_cd 알파벳 포함")

    use_case = IngestFluRtUpperUseCase(session=session, rkinfo_client=client)
    outcome = await use_case.execute(snapshot_at=SNAPSHOT_AT)

    assert outcome.upserted == 0
    assert outcome.error == SkipReason.SENTINEL_SKIP.value


@pytest.mark.asyncio
async def test_flu_rt_single_request_filters_persisted(session: AsyncSession) -> None:
    """used_filters → request_filters JSONB 컬럼 보존 (재현용)."""
    await _create_stock(session, "005930")

    used_filters = {
        "mrkt_tp": "101",
        "sort_tp": "3",
        "stex_tp": "1",
        "trde_qty_cnd": "0010",
    }
    client = _make_client_mock(
        "fetch_flu_rt_upper",
        ([_flu_rt_row("005930")], used_filters),
    )

    use_case = IngestFluRtUpperUseCase(session=session, rkinfo_client=client)
    await use_case.execute(snapshot_at=SNAPSHOT_AT)
    await session.commit()

    result = await session.execute(
        text(
            "SELECT request_filters->>'mrkt_tp', "
            "       request_filters->>'sort_tp', "
            "       request_filters->>'trde_qty_cnd' "
            "FROM kiwoom.ranking_snapshot WHERE stock_code_raw = '005930'"
        )
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == "101"
    assert row[1] == "3"
    assert row[2] == "0010"


@pytest.mark.asyncio
async def test_flu_rt_single_primary_metric_decimal_4digit(
    session: AsyncSession,
) -> None:
    """primary_metric = _to_decimal(flu_rt) — NUMERIC(20,4)."""
    await _create_stock(session, "005930")

    client = _make_client_mock(
        "fetch_flu_rt_upper",
        ([_flu_rt_row("005930", "+0.0001")], {"mrkt_tp": "001"}),
    )

    use_case = IngestFluRtUpperUseCase(session=session, rkinfo_client=client)
    await use_case.execute(snapshot_at=SNAPSHOT_AT)
    await session.commit()

    result = await session.execute(
        text(
            "SELECT primary_metric FROM kiwoom.ranking_snapshot "
            "WHERE stock_code_raw = '005930'"
        )
    )
    metric = result.scalar_one()
    assert metric == Decimal("0.0001"), f"NUMERIC(20,4) 정밀도 손실: {metric}"


# ===========================================================================
# ka10027 — Bulk 5건
# ===========================================================================


@pytest.mark.asyncio
async def test_flu_rt_bulk_4_call_matrix(session: AsyncSession) -> None:
    """Bulk — 2 market × 2 sort = 4 호출 → outcomes 4건."""
    await _create_stock(session, "005930")

    client = _make_client_mock(
        "fetch_flu_rt_upper",
        ([_flu_rt_row("005930")], {"mrkt_tp": "001", "sort_tp": "1"}),
    )

    single = IngestFluRtUpperUseCase(session=session, rkinfo_client=client)
    bulk = IngestFluRtUpperBulkUseCase(session=session, single_use_case=single)

    result = await bulk.execute(snapshot_at=SNAPSHOT_AT)

    assert result.total_calls == 4
    assert result.ranking_type == RankingType.FLU_RT
    # fetch_flu_rt_upper 가 4번 호출됨
    assert client.fetch_flu_rt_upper.await_count == 4


@pytest.mark.asyncio
async def test_flu_rt_bulk_partial_failure_continues(session: AsyncSession) -> None:
    """일부 호출 실패 — 나머지는 진행, outcome.error 분리."""
    await _create_stock(session, "005930")

    call_count = 0

    async def _flaky_fetch(**kwargs: Any) -> tuple:
        nonlocal call_count
        call_count += 1
        if call_count == 2:  # 두 번째 호출만 실패
            raise KiwoomBusinessError(
                api_id="ka10027", return_code=1, message="일시 오류"
            )
        return ([_flu_rt_row("005930")], dict(kwargs))

    client = AsyncMock(spec=KiwoomRkInfoClient)
    client.fetch_flu_rt_upper.side_effect = _flaky_fetch

    single = IngestFluRtUpperUseCase(session=session, rkinfo_client=client)
    bulk = IngestFluRtUpperBulkUseCase(session=session, single_use_case=single)

    result = await bulk.execute(snapshot_at=SNAPSHOT_AT)

    assert result.total_calls == 4
    assert result.total_failed == 1
    assert result.total_upserted >= 1  # 나머지 호출 진행


@pytest.mark.asyncio
async def test_flu_rt_bulk_empty_raw_rows_uses_empty_helper(
    session: AsyncSession,
) -> None:
    """F-3 D-5 — empty raw_rows → _empty_bulk_result 조기 반환 패턴.

    모든 호출이 빈 list 반환 → bulk 정상 종료 + total_upserted=0.
    """
    client = _make_client_mock("fetch_flu_rt_upper", ([], {"mrkt_tp": "001"}))

    single = IngestFluRtUpperUseCase(session=session, rkinfo_client=client)
    bulk = IngestFluRtUpperBulkUseCase(session=session, single_use_case=single)

    result = await bulk.execute(snapshot_at=SNAPSHOT_AT)

    assert result.total_upserted == 0
    assert all(o.upserted == 0 for o in result.outcomes)


@pytest.mark.asyncio
async def test_flu_rt_bulk_errors_above_threshold_tuple_default_empty(
    session: AsyncSession,
) -> None:
    """D-11 — 임계치 도입 안 함. errors_above_threshold default 빈 tuple.

    F-3 D-3 패턴 통일 — tuple[str, ...].
    """
    await _create_stock(session, "005930")
    client = _make_client_mock(
        "fetch_flu_rt_upper",
        ([_flu_rt_row("005930")], {"mrkt_tp": "001"}),
    )

    single = IngestFluRtUpperUseCase(session=session, rkinfo_client=client)
    bulk = IngestFluRtUpperBulkUseCase(session=session, single_use_case=single)

    result = await bulk.execute(snapshot_at=SNAPSHOT_AT)

    assert isinstance(result.errors_above_threshold, tuple)
    assert result.errors_above_threshold == ()


@pytest.mark.asyncio
async def test_flu_rt_bulk_total_upserted_property(session: AsyncSession) -> None:
    """RankingBulkResult.total_upserted = sum(outcome.upserted)."""
    await _create_stock(session, "005930")

    rows = [_flu_rt_row("005930"), _flu_rt_row("999999")]
    client = _make_client_mock(
        "fetch_flu_rt_upper",
        (rows, {"mrkt_tp": "001"}),
    )

    single = IngestFluRtUpperUseCase(session=session, rkinfo_client=client)
    bulk = IngestFluRtUpperBulkUseCase(session=session, single_use_case=single)

    result = await bulk.execute(snapshot_at=SNAPSHOT_AT)

    # 4 호출 × 2 rows 각 = 8 upserted (멱등 UNIQUE 키 동일 시 UPDATE)
    # 단 (market, sort) 4쌍이라 각각 다른 UNIQUE 키 → 8 row INSERT
    assert result.total_upserted == 8


# ===========================================================================
# ka10030 (TODAY_VOLUME) 차이점 — 2건
# ===========================================================================


@pytest.mark.asyncio
async def test_today_volume_single_nested_payload_d9(session: AsyncSession) -> None:
    """D-9 — payload 에 {opmr, af_mkrt, bf_mkrt} 분리 보존 (ka10030 nested)."""
    await _create_stock(session, "005930")

    client = AsyncMock(spec=KiwoomRkInfoClient)
    client.fetch_today_volume_upper.return_value = (
        [_today_volume_row("005930")],
        {"mrkt_tp": "001", "sort_tp": "1"},
    )

    use_case = IngestTodayVolumeUpperUseCase(session=session, rkinfo_client=client)
    await use_case.execute(snapshot_at=SNAPSHOT_AT)
    await session.commit()

    result = await session.execute(
        text(
            "SELECT payload->'opmr'->>'trde_qty', "
            "       payload->'af_mkrt'->>'trde_qty', "
            "       payload->'bf_mkrt'->>'trde_qty' "
            "FROM kiwoom.ranking_snapshot WHERE ranking_type = 'TODAY_VOLUME'"
        )
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == "100000", f"opmr.trde_qty: {row[0]}"
    assert row[1] == "0"
    assert row[2] == "346203"


@pytest.mark.asyncio
async def test_today_volume_single_primary_metric_trade_volume(
    session: AsyncSession,
) -> None:
    """primary_metric = trde_qty (BIGINT → NUMERIC(20,4) 캐스팅)."""
    await _create_stock(session, "005930")

    client = AsyncMock(spec=KiwoomRkInfoClient)
    client.fetch_today_volume_upper.return_value = (
        [_today_volume_row("005930")],
        {"mrkt_tp": "001"},
    )

    use_case = IngestTodayVolumeUpperUseCase(session=session, rkinfo_client=client)
    await use_case.execute(snapshot_at=SNAPSHOT_AT)
    await session.commit()

    result = await session.execute(
        text(
            "SELECT primary_metric FROM kiwoom.ranking_snapshot "
            "WHERE ranking_type = 'TODAY_VOLUME'"
        )
    )
    metric = result.scalar_one()
    assert metric == Decimal("446203.0000"), f"primary_metric (trde_qty): {metric}"


# ===========================================================================
# ka10031 (PRED_VOLUME) 차이점 — 1건
# ===========================================================================


@pytest.mark.asyncio
async def test_pred_volume_single_normal(session: AsyncSession) -> None:
    """ka10031 단건 — list key `pred_trde_qty_upper` + 6 필드 단순."""
    await _create_stock(session, "005930")

    pred_row = PredVolumeUpperRow(
        stk_cd="005930",
        stk_nm="삼성전자",
        cur_prc="+74800",
        pred_pre_sig="1",
        pred_pre="+17200",
        trde_qty="446203",
    )
    client = AsyncMock(spec=KiwoomRkInfoClient)
    client.fetch_pred_volume_upper.return_value = (
        [pred_row],
        {"mrkt_tp": "001", "qry_tp": "1"},
    )

    use_case = IngestPredVolumeUpperUseCase(session=session, rkinfo_client=client)
    outcome = await use_case.execute(snapshot_at=SNAPSHOT_AT)
    await session.commit()

    assert outcome.ranking_type == RankingType.PRED_VOLUME
    assert outcome.upserted == 1


# ===========================================================================
# ka10032 (TRDE_PRICA) 차이점 — 1건
# ===========================================================================


@pytest.mark.asyncio
async def test_trade_amount_single_now_rank_pred_rank(session: AsyncSession) -> None:
    """ka10032 단건 — now_rank/pred_rank payload 보존 + primary_metric = trde_prica."""
    await _create_stock(session, "005930")

    trade_row = TradeAmountUpperRow(
        stk_cd="005930",
        stk_nm="삼성전자",
        cur_prc="+74800",
        pred_pre_sig="1",
        pred_pre="+17200",
        flu_rt="+29.86",
        now_trde_qty="446203",
        trde_prica="33380000",
        now_rank="1",
        pred_rank="5",
    )
    client = AsyncMock(spec=KiwoomRkInfoClient)
    client.fetch_trde_prica_upper.return_value = (
        [trade_row],
        {"mrkt_tp": "001"},
    )

    use_case = IngestTradeAmountUpperUseCase(session=session, rkinfo_client=client)
    await use_case.execute(snapshot_at=SNAPSHOT_AT)
    await session.commit()

    result = await session.execute(
        text(
            "SELECT primary_metric, "
            "       payload->>'now_rank', payload->>'pred_rank' "
            "FROM kiwoom.ranking_snapshot WHERE ranking_type = 'TRDE_PRICA'"
        )
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == Decimal("33380000.0000")
    assert row[1] == "1"
    assert row[2] == "5"


# ===========================================================================
# ka10023 (VOLUME_SDNIN) 차이점 — 2건
# ===========================================================================


@pytest.mark.asyncio
async def test_volume_sdnin_single_sort_qty(session: AsyncSession) -> None:
    """ka10023 sort_tp=1 (SUDDEN_VOLUME) → primary_metric = sdnin_qty."""
    await _create_stock(session, "005930")

    sdnin_row = VolumeSdninRow(
        stk_cd="005930",
        stk_nm="삼성전자",
        cur_prc="+74800",
        pred_pre_sig="1",
        pred_pre="+17200",
        flu_rt="+29.86",
        now_trde_qty="446203",
        sdnin_qty="1500000",
        sdnin_rt="+38.04",
    )
    client = AsyncMock(spec=KiwoomRkInfoClient)
    client.fetch_volume_sdnin.return_value = (
        [sdnin_row],
        {"mrkt_tp": "001", "sort_tp": "1", "tm_tp": "2"},
    )

    use_case = IngestVolumeSdninUseCase(session=session, rkinfo_client=client)
    await use_case.execute(
        snapshot_at=SNAPSHOT_AT,
        sort_tp=VolumeSdninSortType.SUDDEN_VOLUME,
    )
    await session.commit()

    result = await session.execute(
        text(
            "SELECT primary_metric FROM kiwoom.ranking_snapshot "
            "WHERE ranking_type = 'VOLUME_SDNIN'"
        )
    )
    metric = result.scalar_one()
    assert metric == Decimal("1500000.0000")


@pytest.mark.asyncio
async def test_volume_sdnin_single_sort_rate(session: AsyncSession) -> None:
    """ka10023 sort_tp=2 (SUDDEN_RATE) → primary_metric = sdnin_rt (Decimal)."""
    await _create_stock(session, "005930")

    sdnin_row = VolumeSdninRow(
        stk_cd="005930",
        stk_nm="삼성전자",
        cur_prc="+74800",
        pred_pre_sig="1",
        pred_pre="+17200",
        flu_rt="+29.86",
        now_trde_qty="446203",
        sdnin_qty="1500000",
        sdnin_rt="+38.04",
    )
    client = AsyncMock(spec=KiwoomRkInfoClient)
    client.fetch_volume_sdnin.return_value = (
        [sdnin_row],
        {"mrkt_tp": "001", "sort_tp": "2"},
    )

    use_case = IngestVolumeSdninUseCase(session=session, rkinfo_client=client)
    await use_case.execute(
        snapshot_at=SNAPSHOT_AT,
        sort_tp=VolumeSdninSortType.SUDDEN_RATE,
    )
    await session.commit()

    result = await session.execute(
        text(
            "SELECT primary_metric FROM kiwoom.ranking_snapshot "
            "WHERE ranking_type = 'VOLUME_SDNIN'"
        )
    )
    metric = result.scalar_one()
    # sort_tp=2 → sdnin_rt 가 primary_metric (Decimal "+38.04" → 38.0400)
    assert metric == Decimal("38.0400")


# ===========================================================================
# 공통 — 5건
# ===========================================================================


@pytest.mark.asyncio
async def test_snapshot_at_arg_propagates_to_db(session: AsyncSession) -> None:
    """snapshot_at 인자가 DB snapshot_date / snapshot_time 으로 정확히 매핑."""
    await _create_stock(session, "005930")
    snapshot_at = datetime(2026, 6, 15, 13, 45, 22, tzinfo=KST)

    client = _make_client_mock(
        "fetch_flu_rt_upper",
        ([_flu_rt_row("005930")], {"mrkt_tp": "001"}),
    )
    use_case = IngestFluRtUpperUseCase(session=session, rkinfo_client=client)
    await use_case.execute(snapshot_at=snapshot_at)
    await session.commit()

    result = await session.execute(
        text(
            "SELECT snapshot_date, snapshot_time FROM kiwoom.ranking_snapshot "
            "WHERE stock_code_raw = '005930'"
        )
    )
    row = result.fetchone()
    assert row is not None
    assert str(row[0]) == "2026-06-15"
    # snapshot_time microsecond 0 보존
    assert str(row[1]).startswith("13:45:22")


@pytest.mark.asyncio
async def test_today_volume_bulk_basic_signature(session: AsyncSession) -> None:
    """ka10030 Bulk — RankingType.TODAY_VOLUME outcome 분리."""
    await _create_stock(session, "005930")

    client = AsyncMock(spec=KiwoomRkInfoClient)
    client.fetch_today_volume_upper.return_value = (
        [_today_volume_row("005930")],
        {"mrkt_tp": "001"},
    )

    single = IngestTodayVolumeUpperUseCase(session=session, rkinfo_client=client)
    bulk = IngestTodayVolumeUpperBulkUseCase(session=session, single_use_case=single)
    result = await bulk.execute(snapshot_at=SNAPSHOT_AT)

    assert result.ranking_type == RankingType.TODAY_VOLUME
    assert result.total_calls >= 1
    assert isinstance(result.errors_above_threshold, tuple)


@pytest.mark.asyncio
async def test_pred_volume_bulk_signature(session: AsyncSession) -> None:
    """ka10031 Bulk — RankingType.PRED_VOLUME."""
    await _create_stock(session, "005930")

    pred_row = PredVolumeUpperRow(
        stk_cd="005930",
        stk_nm="삼성전자",
        cur_prc="+74800",
        pred_pre_sig="1",
        pred_pre="+17200",
        trde_qty="446203",
    )
    client = AsyncMock(spec=KiwoomRkInfoClient)
    client.fetch_pred_volume_upper.return_value = ([pred_row], {"mrkt_tp": "001"})

    single = IngestPredVolumeUpperUseCase(session=session, rkinfo_client=client)
    bulk = IngestPredVolumeUpperBulkUseCase(session=session, single_use_case=single)
    result = await bulk.execute(snapshot_at=SNAPSHOT_AT)

    assert result.ranking_type == RankingType.PRED_VOLUME


@pytest.mark.asyncio
async def test_trade_amount_bulk_signature(session: AsyncSession) -> None:
    """ka10032 Bulk — RankingType.TRDE_PRICA."""
    await _create_stock(session, "005930")

    trade_row = TradeAmountUpperRow(
        stk_cd="005930",
        stk_nm="삼성전자",
        cur_prc="+74800",
        pred_pre_sig="1",
        pred_pre="+17200",
        flu_rt="+29.86",
        now_trde_qty="446203",
        trde_prica="33380000",
        now_rank="1",
        pred_rank="2",
    )
    client = AsyncMock(spec=KiwoomRkInfoClient)
    client.fetch_trde_prica_upper.return_value = ([trade_row], {"mrkt_tp": "001"})

    single = IngestTradeAmountUpperUseCase(session=session, rkinfo_client=client)
    bulk = IngestTradeAmountUpperBulkUseCase(session=session, single_use_case=single)
    result = await bulk.execute(snapshot_at=SNAPSHOT_AT)

    assert result.ranking_type == RankingType.TRDE_PRICA


@pytest.mark.asyncio
async def test_volume_sdnin_bulk_signature(session: AsyncSession) -> None:
    """ka10023 Bulk — RankingType.VOLUME_SDNIN."""
    await _create_stock(session, "005930")

    sdnin_row = VolumeSdninRow(
        stk_cd="005930",
        stk_nm="삼성전자",
        cur_prc="+74800",
        pred_pre_sig="1",
        pred_pre="+17200",
        flu_rt="+29.86",
        now_trde_qty="446203",
        sdnin_qty="1500000",
        sdnin_rt="+38.04",
    )
    client = AsyncMock(spec=KiwoomRkInfoClient)
    client.fetch_volume_sdnin.return_value = ([sdnin_row], {"mrkt_tp": "001"})

    single = IngestVolumeSdninUseCase(session=session, rkinfo_client=client)
    bulk = IngestVolumeSdninBulkUseCase(session=session, single_use_case=single)
    result = await bulk.execute(snapshot_at=SNAPSHOT_AT)

    assert result.ranking_type == RankingType.VOLUME_SDNIN
