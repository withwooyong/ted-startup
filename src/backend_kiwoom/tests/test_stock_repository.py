"""StockRepository 단위 테스트 — testcontainers PG16.

검증 (sector 패턴 차용 + stock 특이사항):
- list_by_filters — market_code / nxt_enable / only_active 필터 + 정렬
- list_nxt_enabled — nxt_enable=true partial index 사용
- find_by_code — 단건 조회
- upsert_many — insert / update / 빈 list / 14필드 갱신 / is_active 복원
- deactivate_missing — 응답 빠진 row 비활성화 / 시장 단위 격리 / 이미 비활성 재처리 X /
  빈 present_codes 가 그 시장 전체 비활성화 (안전장치)
- 중복 stock_code (한 종목이 여러 시장 sync 응답에 등장) → 두 번째 sync 가 market_code 덮어씀
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.repositories.stock import StockRepository


def _row(
    stock_code: str,
    stock_name: str,
    market_code: str = "0",
    *,
    nxt_enable: bool = False,
    list_count: int | None = None,
    listed_date: date | None = None,
    last_price: int | None = None,
    state: str | None = None,
    up_name: str | None = None,
    market_name: str | None = None,
    up_size_name: str | None = None,
    company_class_name: str | None = None,
    audit_info: str | None = None,
    order_warning: str = "0",
) -> dict[str, Any]:
    return {
        "stock_code": stock_code,
        "stock_name": stock_name,
        "market_code": market_code,
        "list_count": list_count,
        "audit_info": audit_info,
        "listed_date": listed_date,
        "last_price": last_price,
        "state": state,
        "market_name": market_name,
        "up_name": up_name,
        "up_size_name": up_size_name,
        "company_class_name": company_class_name,
        "order_warning": order_warning,
        "nxt_enable": nxt_enable,
    }


# =============================================================================
# upsert_many
# =============================================================================


@pytest.mark.asyncio
async def test_upsert_many_inserts_new_rows(session: AsyncSession) -> None:
    repo = StockRepository(session)
    rows = [
        _row("005930", "삼성전자", "0", nxt_enable=True, list_count=5969782550),
        _row("000660", "SK하이닉스", "0", nxt_enable=True),
    ]

    count = await repo.upsert_many(rows)

    assert count == 2
    persisted = await repo.list_by_filters(market_code="0", only_active=True)
    assert len(persisted) == 2
    assert {p.stock_code for p in persisted} == {"005930", "000660"}
    by_code = {p.stock_code: p for p in persisted}
    assert by_code["005930"].list_count == 5969782550
    assert by_code["005930"].nxt_enable is True


@pytest.mark.asyncio
async def test_upsert_many_empty_returns_zero(session: AsyncSession) -> None:
    repo = StockRepository(session)
    assert await repo.upsert_many([]) == 0


@pytest.mark.asyncio
async def test_upsert_many_updates_existing_rows(session: AsyncSession) -> None:
    """기존 row 의 모든 도메인 필드 갱신 + fetched_at 변경."""
    repo = StockRepository(session)
    await repo.upsert_many([_row("005930", "삼성전자", "0", last_price=70000)])

    initial = (await repo.list_by_filters(market_code="0"))[0]
    initial_fetched = initial.fetched_at

    # 동일 stock_code 재 upsert — 가격 변경
    await repo.upsert_many([_row("005930", "삼성전자", "0", last_price=75800)])
    await session.refresh(initial)

    updated = (await repo.list_by_filters(market_code="0"))[0]
    assert updated.last_price == 75800
    assert updated.fetched_at >= initial_fetched


@pytest.mark.asyncio
async def test_upsert_many_reactivates_inactive_row(session: AsyncSession) -> None:
    """비활성화된 row 가 응답에 다시 등장하면 is_active=TRUE 복원."""
    repo = StockRepository(session)
    await repo.upsert_many([_row("005930", "삼성전자", "0")])

    # 비활성화 (다른 종목만 응답에 있다고 가정)
    await repo.deactivate_missing("0", {"000660"})
    inactive_rows = await repo.list_by_filters(market_code="0", only_active=False)
    assert inactive_rows[0].is_active is False

    # 재등장 + 이름 변경
    await repo.upsert_many([_row("005930", "삼성전자(재등장)", "0", nxt_enable=True)])
    active_rows = await repo.list_by_filters(market_code="0", only_active=True)
    assert len(active_rows) == 1
    assert active_rows[0].is_active is True
    assert active_rows[0].stock_name == "삼성전자(재등장)"
    assert active_rows[0].nxt_enable is True


@pytest.mark.asyncio
async def test_upsert_many_chunks_large_batch_under_asyncpg_limit(session: AsyncSession) -> None:
    """asyncpg bind parameter 한도 (32767) 초과 시 자동 chunk 분할.

    실측 2026-05-09: KOSPI 2440 종목 × 14 컬럼 = 34160 > 32767 한도. 분할 안 하면
    InterfaceError. 1000 per batch chunk 분할로 한 batch 14000 < 32767.
    """
    repo = StockRepository(session)
    rows = [
        _row(f"{i:06d}", f"종목{i}", "0")
        for i in range(2500)  # KOSPI 실측 2440 보다 많이
    ]

    count = await repo.upsert_many(rows)
    assert count == 2500


@pytest.mark.asyncio
async def test_upsert_many_overwrites_market_code_on_cross_market_conflict(
    session: AsyncSession,
) -> None:
    """§11.2 — 한 종목이 두 시장에 등장 시 두 번째 upsert 가 market_code 덮어씀.

    UNIQUE(stock_code) 단일키이므로 ON CONFLICT (stock_code) UPDATE 가 market_code
    를 excluded.market_code 로 덮어쓴다. 운영 dry-run 후 정책 재검토 (§11.1 #2).
    """
    repo = StockRepository(session)
    await repo.upsert_many([_row("AAA111", "공통종목", market_code="0")])
    await repo.upsert_many([_row("AAA111", "공통종목", market_code="6")])  # REIT

    rows = await repo.list_by_filters(only_active=False)
    assert len(rows) == 1
    assert rows[0].market_code == "6"


@pytest.mark.asyncio
async def test_upsert_many_persists_listed_date(session: AsyncSession) -> None:
    repo = StockRepository(session)
    await repo.upsert_many([_row("005930", "삼성전자", "0", listed_date=date(1975, 6, 11))])
    rows = await repo.list_by_filters(market_code="0")
    assert rows[0].listed_date == date(1975, 6, 11)


# =============================================================================
# list_by_filters
# =============================================================================


@pytest.mark.asyncio
async def test_list_by_filters_only_active(session: AsyncSession) -> None:
    repo = StockRepository(session)
    await repo.upsert_many(
        [
            _row("005930", "active1", "0"),
            _row("000660", "active2", "0"),
        ]
    )
    await repo.deactivate_missing("0", {"005930"})

    active_only = await repo.list_by_filters(market_code="0", only_active=True)
    all_rows = await repo.list_by_filters(market_code="0", only_active=False)

    assert {r.stock_code for r in active_only} == {"005930"}
    assert {r.stock_code for r in all_rows} == {"005930", "000660"}


@pytest.mark.asyncio
async def test_list_by_filters_isolated_per_market(session: AsyncSession) -> None:
    repo = StockRepository(session)
    await repo.upsert_many(
        [
            _row("005930", "KOSPI", "0"),
            _row("123456", "KOSDAQ", "10"),
            _row("777777", "KONEX", "50"),
        ]
    )

    kospi = await repo.list_by_filters(market_code="0")
    kosdaq = await repo.list_by_filters(market_code="10")
    konex = await repo.list_by_filters(market_code="50")

    assert len(kospi) == 1
    assert kospi[0].stock_name == "KOSPI"
    assert len(kosdaq) == 1
    assert kosdaq[0].stock_name == "KOSDAQ"
    assert len(konex) == 1


@pytest.mark.asyncio
async def test_list_by_filters_ordered_by_market_then_code(session: AsyncSession) -> None:
    repo = StockRepository(session)
    await repo.upsert_many(
        [
            _row("999999", "Z-1", "10"),
            _row("000001", "A-1", "0"),
            _row("000002", "A-2", "0"),
            _row("888888", "Y-1", "10"),
        ]
    )

    rows = await repo.list_by_filters()
    keys = [(r.market_code, r.stock_code) for r in rows]
    assert keys == [
        ("0", "000001"),
        ("0", "000002"),
        ("10", "888888"),
        ("10", "999999"),
    ]


@pytest.mark.asyncio
async def test_list_by_filters_nxt_enable_filter(session: AsyncSession) -> None:
    repo = StockRepository(session)
    await repo.upsert_many(
        [
            _row("005930", "삼성", "0", nxt_enable=True),
            _row("000660", "SK", "0", nxt_enable=False),
            _row("035420", "네이버", "0", nxt_enable=True),
        ]
    )

    nxt_only = await repo.list_by_filters(market_code="0", nxt_enable=True)
    non_nxt = await repo.list_by_filters(market_code="0", nxt_enable=False)
    all_rows = await repo.list_by_filters(market_code="0", nxt_enable=None)

    assert {r.stock_code for r in nxt_only} == {"005930", "035420"}
    assert {r.stock_code for r in non_nxt} == {"000660"}
    assert len(all_rows) == 3


# =============================================================================
# list_nxt_enabled
# =============================================================================


@pytest.mark.asyncio
async def test_list_nxt_enabled_returns_only_active_nxt_true(session: AsyncSession) -> None:
    """Phase C 의 NXT 호출 큐 — nxt_enable=true AND is_active=true."""
    repo = StockRepository(session)
    await repo.upsert_many(
        [
            _row("005930", "삼성", "0", nxt_enable=True),
            _row("000660", "SK", "0", nxt_enable=False),
            _row("035420", "네이버", "0", nxt_enable=True),
        ]
    )
    await repo.deactivate_missing("0", {"005930", "000660"})  # 035420 비활성화

    queue = await repo.list_nxt_enabled(only_active=True)
    assert {r.stock_code for r in queue} == {"005930"}

    # only_active=False 면 비활성도 포함
    full_queue = await repo.list_nxt_enabled(only_active=False)
    assert {r.stock_code for r in full_queue} == {"005930", "035420"}


# =============================================================================
# find_by_code
# =============================================================================


@pytest.mark.asyncio
async def test_find_by_code_returns_row(session: AsyncSession) -> None:
    repo = StockRepository(session)
    await repo.upsert_many([_row("005930", "삼성전자", "0", nxt_enable=True)])

    found = await repo.find_by_code("005930")

    assert found is not None
    assert found.stock_code == "005930"
    assert found.nxt_enable is True


@pytest.mark.asyncio
async def test_find_by_code_returns_none_when_missing(session: AsyncSession) -> None:
    repo = StockRepository(session)
    found = await repo.find_by_code("999999")
    assert found is None


# =============================================================================
# deactivate_missing
# =============================================================================


@pytest.mark.asyncio
async def test_deactivate_missing_marks_absent_codes_inactive(session: AsyncSession) -> None:
    repo = StockRepository(session)
    await repo.upsert_many(
        [
            _row("005930", "keep", "0"),
            _row("000660", "remove1", "0"),
            _row("035420", "remove2", "0"),
        ]
    )

    deactivated = await repo.deactivate_missing("0", present_codes={"005930"})

    assert deactivated == 2
    rows = await repo.list_by_filters(market_code="0", only_active=False)
    by_code = {r.stock_code: r for r in rows}
    assert by_code["005930"].is_active is True
    assert by_code["000660"].is_active is False
    assert by_code["035420"].is_active is False


@pytest.mark.asyncio
async def test_deactivate_missing_isolated_per_market(session: AsyncSession) -> None:
    """KOSPI sync 가 KOSDAQ 종목 비활성화 안 함 — 사고 방지."""
    repo = StockRepository(session)
    await repo.upsert_many(
        [
            _row("005930", "KOSPI-A", "0"),
            _row("123456", "KOSDAQ-A", "10"),
        ]
    )

    # KOSPI 시장만 비활성 처리 (응답 빈 set — 안전장치 동작)
    await repo.deactivate_missing("0", present_codes=set())

    kospi = await repo.list_by_filters(market_code="0", only_active=False)
    kosdaq = await repo.list_by_filters(market_code="10", only_active=False)
    assert kospi[0].is_active is False
    assert kosdaq[0].is_active is True, "KOSDAQ row 가 영향받음 — 시장 격리 깨짐"


@pytest.mark.asyncio
async def test_deactivate_missing_skips_already_inactive(session: AsyncSession) -> None:
    """이미 비활성 row 는 다시 update 안 함 — rowcount 정확."""
    repo = StockRepository(session)
    await repo.upsert_many([_row("005930", "x", "0")])
    first = await repo.deactivate_missing("0", set())  # 1
    second = await repo.deactivate_missing("0", set())  # 0 (이미 비활성)

    assert first == 1
    assert second == 0


@pytest.mark.asyncio
async def test_deactivate_missing_with_empty_present_deactivates_all_active(
    session: AsyncSession,
) -> None:
    """present_codes 빈 set 이면 그 시장 모든 활성 row 비활성화 — 안전장치 동작."""
    repo = StockRepository(session)
    await repo.upsert_many(
        [
            _row("005930", "a", "0"),
            _row("000660", "b", "0"),
        ]
    )

    count = await repo.deactivate_missing("0", set())

    assert count == 2
    rows = await repo.list_by_filters(market_code="0", only_active=True)
    assert rows == []
