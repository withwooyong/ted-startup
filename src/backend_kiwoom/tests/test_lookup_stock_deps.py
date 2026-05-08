"""LookupStockUseCase factory DI 단위 — get/set/reset (B-β).

설계: app/adapter/web/_deps.py — sector / sync_stock factory 와 같은 패턴.

검증:
1. 미설정 상태에서 get → 503
2. set 후 get → 같은 factory 반환
3. reset 후 get → 503 (다시 미설정)
4. reset_token_manager 가 lookup factory 도 리셋 (전역 reset 체인)
5. SyncStockMasterUseCaseFactory / LookupStockUseCaseFactory / SyncSectorUseCaseFactory
   세 factory 가 독립적으로 set/get/reset 가능
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from fastapi import HTTPException


@pytest.fixture(autouse=True)
def _reset_singletons():
    """매 테스트 시작·종료 시 모든 싱글톤 리셋 — global state 격리."""
    from app.adapter.web import _deps

    _deps.reset_token_manager()
    yield
    _deps.reset_token_manager()


def _dummy_factory():
    @asynccontextmanager
    async def _factory(alias: str) -> AsyncIterator[object]:
        yield object()

    return _factory


def test_get_lookup_stock_factory_not_set_raises_503() -> None:
    from app.adapter.web._deps import get_lookup_stock_factory

    with pytest.raises(HTTPException) as exc_info:
        get_lookup_stock_factory()
    assert exc_info.value.status_code == 503


def test_set_get_lookup_stock_factory_roundtrip() -> None:
    from app.adapter.web._deps import (
        get_lookup_stock_factory,
        set_lookup_stock_factory,
    )

    factory = _dummy_factory()
    set_lookup_stock_factory(factory)

    retrieved = get_lookup_stock_factory()
    assert retrieved is factory


def test_reset_lookup_stock_factory_clears() -> None:
    from app.adapter.web._deps import (
        get_lookup_stock_factory,
        reset_lookup_stock_factory,
        set_lookup_stock_factory,
    )

    set_lookup_stock_factory(_dummy_factory())
    reset_lookup_stock_factory()

    with pytest.raises(HTTPException) as exc_info:
        get_lookup_stock_factory()
    assert exc_info.value.status_code == 503


def test_reset_token_manager_resets_lookup_factory_too() -> None:
    """전역 reset_token_manager 가 lookup factory 도 함께 리셋한다 (sector / sync_stock 일관)."""
    from app.adapter.web._deps import (
        get_lookup_stock_factory,
        reset_token_manager,
        set_lookup_stock_factory,
    )

    set_lookup_stock_factory(_dummy_factory())
    reset_token_manager()

    with pytest.raises(HTTPException):
        get_lookup_stock_factory()


def test_three_factories_independent() -> None:
    """sector / sync_stock / lookup_stock 세 factory 가 독립적으로 동작."""
    from app.adapter.web._deps import (
        get_lookup_stock_factory,
        get_sync_sector_factory,
        get_sync_stock_factory,
        set_lookup_stock_factory,
        set_sync_sector_factory,
        set_sync_stock_factory,
    )

    sector_factory = _dummy_factory()
    stock_factory = _dummy_factory()
    lookup_factory = _dummy_factory()

    set_sync_sector_factory(sector_factory)
    set_sync_stock_factory(stock_factory)
    set_lookup_stock_factory(lookup_factory)

    assert get_sync_sector_factory() is sector_factory
    assert get_sync_stock_factory() is stock_factory
    assert get_lookup_stock_factory() is lookup_factory
