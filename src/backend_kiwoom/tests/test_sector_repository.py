"""SectorRepository 단위 테스트 — testcontainers PG16.

검증:
- list_by_market — 활성 필터 / 정렬 / 다른 시장 격리
- list_all — 전체 시장 통합 조회 + 정렬
- upsert_many — insert / update / 빈 list / sector_name·group_no 갱신 / is_active 복원
- deactivate_missing — 응답에 빠진 row 비활성화 / 시장 단위 격리 / 이미 비활성 row 재처리 X /
  빈 present_codes 가 그 시장 전체 비활성화 (안전장치 동작 확인)
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.repositories.sector import SectorRepository


def _row(market_code: str, sector_code: str, sector_name: str, group_no: str | None = None) -> dict[str, str | None]:
    return {
        "market_code": market_code,
        "sector_code": sector_code,
        "sector_name": sector_name,
        "group_no": group_no,
    }


# =============================================================================
# upsert_many
# =============================================================================


@pytest.mark.asyncio
async def test_upsert_many_inserts_new_rows(session: AsyncSession) -> None:
    repo = SectorRepository(session)
    rows = [
        _row("0", "001", "종합(KOSPI)"),
        _row("0", "002", "대형주", group_no="1"),
    ]

    count = await repo.upsert_many(rows)

    assert count == 2
    persisted = await repo.list_by_market("0", only_active=True)
    assert len(persisted) == 2
    assert {p.sector_code for p in persisted} == {"001", "002"}


@pytest.mark.asyncio
async def test_upsert_many_empty_returns_zero(session: AsyncSession) -> None:
    repo = SectorRepository(session)
    assert await repo.upsert_many([]) == 0


@pytest.mark.asyncio
async def test_upsert_many_updates_existing_rows(session: AsyncSession) -> None:
    """기존 row 의 sector_name / group_no 갱신 + fetched_at 변경."""
    repo = SectorRepository(session)
    await repo.upsert_many([_row("0", "001", "기존명", group_no="A")])

    initial = (await repo.list_by_market("0"))[0]
    initial_fetched = initial.fetched_at

    # 동일 (market_code, sector_code) 재 upsert — name + group 변경
    await repo.upsert_many([_row("0", "001", "변경된명", group_no="B")])
    await session.refresh(initial)

    updated = (await repo.list_by_market("0"))[0]
    assert updated.sector_name == "변경된명"
    assert updated.group_no == "B"
    assert updated.fetched_at >= initial_fetched


@pytest.mark.asyncio
async def test_upsert_many_reactivates_inactive_row(session: AsyncSession) -> None:
    """비활성화된 row 가 응답에 다시 등장하면 is_active=TRUE 복원."""
    repo = SectorRepository(session)
    await repo.upsert_many([_row("0", "001", "초기")])

    # 비활성화
    await repo.deactivate_missing("0", set())  # present 비어있으면 전체 비활성화
    persisted_inactive = await repo.list_by_market("0", only_active=False)
    assert persisted_inactive[0].is_active is False

    # 재등장
    await repo.upsert_many([_row("0", "001", "재등장")])
    persisted_active = await repo.list_by_market("0", only_active=True)
    assert len(persisted_active) == 1
    assert persisted_active[0].is_active is True
    assert persisted_active[0].sector_name == "재등장"


# =============================================================================
# list_by_market
# =============================================================================


@pytest.mark.asyncio
async def test_list_by_market_only_active_filter(session: AsyncSession) -> None:
    repo = SectorRepository(session)
    await repo.upsert_many(
        [
            _row("0", "001", "active1"),
            _row("0", "002", "active2"),
        ]
    )
    # 002 만 비활성화
    await repo.deactivate_missing("0", {"001"})

    active_only = await repo.list_by_market("0", only_active=True)
    all_rows = await repo.list_by_market("0", only_active=False)

    assert {r.sector_code for r in active_only} == {"001"}
    assert {r.sector_code for r in all_rows} == {"001", "002"}


@pytest.mark.asyncio
async def test_list_by_market_isolated_per_market(session: AsyncSession) -> None:
    """한 시장 호출이 다른 시장 row 를 반환하지 않음."""
    repo = SectorRepository(session)
    await repo.upsert_many(
        [
            _row("0", "001", "KOSPI"),
            _row("1", "001", "KOSDAQ"),
            _row("2", "001", "KOSPI200"),
        ]
    )

    kospi = await repo.list_by_market("0")
    kosdaq = await repo.list_by_market("1")

    assert len(kospi) == 1
    assert kospi[0].sector_name == "KOSPI"
    assert len(kosdaq) == 1
    assert kosdaq[0].sector_name == "KOSDAQ"


@pytest.mark.asyncio
async def test_list_by_market_ordered_by_sector_code(session: AsyncSession) -> None:
    repo = SectorRepository(session)
    await repo.upsert_many(
        [
            _row("0", "099", "마지막"),
            _row("0", "001", "첫번째"),
            _row("0", "050", "중간"),
        ]
    )

    rows = await repo.list_by_market("0")
    assert [r.sector_code for r in rows] == ["001", "050", "099"]


# =============================================================================
# list_all
# =============================================================================


@pytest.mark.asyncio
async def test_list_all_orders_by_market_then_sector(session: AsyncSession) -> None:
    repo = SectorRepository(session)
    await repo.upsert_many(
        [
            _row("1", "001", "K-1"),
            _row("0", "002", "K-2"),
            _row("0", "001", "K-1"),
            _row("1", "002", "K-2"),
        ]
    )

    rows = await repo.list_all()
    keys = [(r.market_code, r.sector_code) for r in rows]
    assert keys == [("0", "001"), ("0", "002"), ("1", "001"), ("1", "002")]


@pytest.mark.asyncio
async def test_list_all_only_active(session: AsyncSession) -> None:
    repo = SectorRepository(session)
    await repo.upsert_many(
        [
            _row("0", "001", "active"),
            _row("0", "002", "to-deactivate"),
        ]
    )
    await repo.deactivate_missing("0", {"001"})

    active = await repo.list_all(only_active=True)
    full = await repo.list_all(only_active=False)

    assert {r.sector_code for r in active} == {"001"}
    assert {r.sector_code for r in full} == {"001", "002"}


# =============================================================================
# deactivate_missing
# =============================================================================


@pytest.mark.asyncio
async def test_deactivate_missing_marks_absent_codes_inactive(session: AsyncSession) -> None:
    repo = SectorRepository(session)
    await repo.upsert_many(
        [
            _row("0", "001", "keep"),
            _row("0", "002", "remove1"),
            _row("0", "003", "remove2"),
        ]
    )

    deactivated = await repo.deactivate_missing("0", present_codes={"001"})

    assert deactivated == 2
    rows = await repo.list_by_market("0", only_active=False)
    by_code = {r.sector_code: r for r in rows}
    assert by_code["001"].is_active is True
    assert by_code["002"].is_active is False
    assert by_code["003"].is_active is False


@pytest.mark.asyncio
async def test_deactivate_missing_isolated_per_market(session: AsyncSession) -> None:
    """`deactivate_missing("0", ...)` 호출이 다른 시장 row 를 건드리지 않음."""
    repo = SectorRepository(session)
    await repo.upsert_many(
        [
            _row("0", "001", "KOSPI-A"),
            _row("1", "001", "KOSDAQ-A"),
        ]
    )

    # KOSPI 시장만 비활성 처리
    await repo.deactivate_missing("0", present_codes=set())

    kospi = await repo.list_by_market("0", only_active=False)
    kosdaq = await repo.list_by_market("1", only_active=False)
    assert kospi[0].is_active is False
    assert kosdaq[0].is_active is True, "KOSDAQ row 가 영향받음 — 시장 격리 깨짐"


@pytest.mark.asyncio
async def test_deactivate_missing_skips_already_inactive(session: AsyncSession) -> None:
    """이미 비활성인 row 는 다시 update 안 함 — rowcount 정확."""
    repo = SectorRepository(session)
    await repo.upsert_many([_row("0", "001", "x")])
    first = await repo.deactivate_missing("0", set())  # 1
    second = await repo.deactivate_missing("0", set())  # 0 (이미 비활성)

    assert first == 1
    assert second == 0


@pytest.mark.asyncio
async def test_deactivate_missing_with_empty_present_deactivates_all_active(
    session: AsyncSession,
) -> None:
    """present_codes 가 빈 set 이면 그 시장의 모든 활성 row 비활성화 — 안전장치."""
    repo = SectorRepository(session)
    await repo.upsert_many(
        [
            _row("0", "001", "a"),
            _row("0", "002", "b"),
        ]
    )

    count = await repo.deactivate_missing("0", set())

    assert count == 2
    rows = await repo.list_by_market("0", only_active=True)
    assert rows == []
