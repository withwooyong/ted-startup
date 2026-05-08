"""B-γ-2 _deps factory — get/set/reset_sync_fundamental_factory.

설계: endpoint-05-ka10001.md § 7.1 + B-α/B-β factory 패턴 일관.

검증:
- 미초기화 시 get → 503 HTTPException
- set 후 get → 같은 factory 반환
- reset_token_manager 가 fundamental factory 도 unset
- reset_sync_fundamental_factory 단독 reset
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from fastapi import HTTPException

from app.adapter.web._deps import (
    SyncStockFundamentalUseCaseFactory,
    get_sync_fundamental_factory,
    reset_sync_fundamental_factory,
    reset_token_manager,
    set_sync_fundamental_factory,
)


@asynccontextmanager
async def _dummy(_alias: str) -> AsyncIterator[None]:
    yield None


_dummy_factory: SyncStockFundamentalUseCaseFactory = _dummy  # type: ignore[assignment]


def test_get_raises_503_when_uninitialized() -> None:
    reset_sync_fundamental_factory()
    with pytest.raises(HTTPException) as exc_info:
        get_sync_fundamental_factory()
    assert exc_info.value.status_code == 503


def test_set_then_get_returns_same_factory() -> None:
    reset_sync_fundamental_factory()
    set_sync_fundamental_factory(_dummy_factory)
    try:
        assert get_sync_fundamental_factory() is _dummy_factory
    finally:
        reset_sync_fundamental_factory()


def test_reset_token_manager_also_unsets_fundamental_factory() -> None:
    """reset_token_manager 는 모든 싱글톤 일괄 unset (lifespan teardown 안전망)."""
    set_sync_fundamental_factory(_dummy_factory)
    reset_token_manager()
    with pytest.raises(HTTPException) as exc_info:
        get_sync_fundamental_factory()
    assert exc_info.value.status_code == 503


def test_reset_sync_fundamental_factory_only() -> None:
    set_sync_fundamental_factory(_dummy_factory)
    reset_sync_fundamental_factory()
    with pytest.raises(HTTPException):
        get_sync_fundamental_factory()
