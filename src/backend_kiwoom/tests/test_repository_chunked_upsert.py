"""_chunked_upsert helper — unit test (mock session, testcontainers 불필요).

chunk = D-1 follow-up, plan doc § 13.

목적:
- `_chunked_upsert` 를 `_helpers.py` 에 추가하는 Step 1 구현 전 red 고정.
- 현재 `_helpers.py` 에 `_chunked_upsert` 가 없어 ImportError → 전체 모듈 red.

helper 책임:
- rows 를 chunk_size 단위로 분할
- 각 chunk 마다 statement_factory(chunk) 로 statement 생성 후 session.execute()
- rowcount 합산 반환
- PostgreSQL wire protocol int16 한도 (32767) 회피 목적
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.persistence.repositories._helpers import _chunked_upsert


@pytest.mark.asyncio
async def test_chunked_upsert_empty_rows_returns_zero() -> None:
    """빈 rows → factory 호출 없이 0 반환."""
    session = AsyncMock(spec=AsyncSession)
    factory: Any = MagicMock()
    result = await _chunked_upsert(session, factory, [], chunk_size=1000)
    assert result == 0
    factory.assert_not_called()
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_chunked_upsert_single_row_single_chunk() -> None:
    """1 row → factory 1회 호출, rowcount=1 반환."""
    session = AsyncMock(spec=AsyncSession)
    cursor = MagicMock(rowcount=1)
    session.execute = AsyncMock(return_value=cursor)
    factory: Any = MagicMock(return_value="stmt")

    result = await _chunked_upsert(session, factory, [{"id": 1}], chunk_size=1000)
    assert result == 1
    assert factory.call_count == 1
    factory.assert_called_with([{"id": 1}])


@pytest.mark.asyncio
async def test_chunked_upsert_999_rows_single_chunk() -> None:
    """경계 — chunk_size=1000 일 때 999 row 는 단일 chunk."""
    session = AsyncMock(spec=AsyncSession)
    cursor = MagicMock(rowcount=999)
    session.execute = AsyncMock(return_value=cursor)
    factory: Any = MagicMock(return_value="stmt")

    rows = [{"id": i} for i in range(999)]
    result = await _chunked_upsert(session, factory, rows, chunk_size=1000)
    assert result == 999
    assert factory.call_count == 1


@pytest.mark.asyncio
async def test_chunked_upsert_1001_rows_two_chunks() -> None:
    """경계 — 1001 row 는 2 chunk (1000 + 1)."""
    session = AsyncMock(spec=AsyncSession)
    cursor_a = MagicMock(rowcount=1000)
    cursor_b = MagicMock(rowcount=1)
    session.execute = AsyncMock(side_effect=[cursor_a, cursor_b])
    factory: Any = MagicMock(return_value="stmt")

    rows = [{"id": i} for i in range(1001)]
    result = await _chunked_upsert(session, factory, rows, chunk_size=1000)
    assert result == 1001
    assert factory.call_count == 2
    # 첫 chunk = 1000, 두 번째 = 1
    assert len(factory.call_args_list[0][0][0]) == 1000
    assert len(factory.call_args_list[1][0][0]) == 1


@pytest.mark.asyncio
async def test_chunked_upsert_5500_rows_six_chunks() -> None:
    """sector_daily 장기 백필 시뮬레이션 — 5500 row × 8 col = 44000 > 32767 → chunk 6개."""
    session = AsyncMock(spec=AsyncSession)
    cursors = [MagicMock(rowcount=1000)] * 5 + [MagicMock(rowcount=500)]
    session.execute = AsyncMock(side_effect=cursors)
    factory: Any = MagicMock(return_value="stmt")

    rows = [{"id": i} for i in range(5500)]
    result = await _chunked_upsert(session, factory, rows, chunk_size=1000)
    assert result == 5500
    assert factory.call_count == 6


@pytest.mark.asyncio
async def test_chunked_upsert_custom_chunk_size() -> None:
    """chunk_size=500 명시 — 2000 row → 4 chunk."""
    session = AsyncMock(spec=AsyncSession)
    cursors = [MagicMock(rowcount=500)] * 4
    session.execute = AsyncMock(side_effect=cursors)
    factory: Any = MagicMock(return_value="stmt")

    rows = [{"id": i} for i in range(2000)]
    result = await _chunked_upsert(session, factory, rows, chunk_size=500)
    assert result == 2000
    assert factory.call_count == 4


@pytest.mark.asyncio
async def test_chunked_upsert_column_count_exceeds_int16_raises() -> None:
    """2b 2R M-1 — n_cols × chunk_size > 32767 시 fail-fast.

    미래 schema growth (33+ col) 로 silent breakage 발생 차단. 본 케이스는
    35 col × 1000 row = 35000 > 32767 → ValueError + 권장 chunk_size 안내.
    """
    session = AsyncMock(spec=AsyncSession)
    factory: Any = MagicMock(return_value="stmt")

    # 35 col 짜리 row 한 줄 (factory 까지 도달 못 함 — 가드가 사전 차단)
    wide_row = {f"c{i}": i for i in range(35)}
    rows = [wide_row]

    with pytest.raises(ValueError, match=r"n_cols=35 .+ 32767"):
        await _chunked_upsert(session, factory, rows, chunk_size=1000)

    factory.assert_not_called()
    session.execute.assert_not_called()
