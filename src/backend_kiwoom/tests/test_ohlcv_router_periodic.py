"""POST /api/kiwoom/ohlcv/{weekly|monthly}/sync + refresh path (C-3β).

설계: phase-c-3-weekly-monthly-ohlcv.md § 3.2.

기존 ohlcv_router (daily) 패턴 ~95% 복제 + period dispatch + R1 contract:
- POST /api/kiwoom/ohlcv/weekly/sync (admin)
- POST /api/kiwoom/ohlcv/monthly/sync (admin)
- POST /api/kiwoom/stocks/{code}/ohlcv/weekly/refresh (admin)
- POST /api/kiwoom/stocks/{code}/ohlcv/monthly/refresh (admin)

R1 contract 검증:
- response DTO errors: tuple[OutcomeOut, ...]
- only_market_codes max_length=2 + pattern
- fetched_at: datetime non-Optional (조회 endpoint 가 추가될 때만 — 본 chunk 는 sync/refresh)
- StockMasterNotFoundError → 404 (subclass first 순서)

검증:
1. POST weekly/sync — 200 응답 + admin gate
2. POST monthly/sync — 200 응답
3. POST weekly/sync — body without admin key → 401
4. POST refresh — Stock 미존재 → 404 (StockMasterNotFoundError)
5. POST refresh — base_date 미래 → 400 (ValueError)
6. POST refresh — KiwoomBusinessError → 400 (echo 차단)
7. only_market_codes max_length=2 위반 → 422
8. errors tuple 직렬화 (Pydantic v2 → JSON array)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.adapter.out.kiwoom._exceptions import KiwoomBusinessError
from app.adapter.web._deps import (
    IngestPeriodicOhlcvUseCaseFactory,
    reset_ingest_periodic_ohlcv_factory,
    set_ingest_periodic_ohlcv_factory,
)
from app.application.constants import Period
from app.application.exceptions import StockMasterNotFoundError
from app.application.service.ohlcv_periodic_service import (
    IngestPeriodicOhlcvUseCase,
    OhlcvSyncOutcome,
    OhlcvSyncResult,
)


@pytest.fixture
def admin_key(monkeypatch: pytest.MonkeyPatch) -> str:
    key = "test-admin-key-c3beta"
    monkeypatch.setenv("ADMIN_API_KEY", key)
    from app.config.settings import get_settings

    get_settings.cache_clear()
    return key


@pytest.fixture
def app_client(admin_key: str) -> TestClient:
    from app.main import create_app

    return TestClient(create_app())


def _ok_result(*, success_krx: int = 1) -> OhlcvSyncResult:
    return OhlcvSyncResult(
        base_date=date(2025, 9, 8),
        total=success_krx,
        success_krx=success_krx,
        success_nxt=0,
        failed=0,
        errors=(),
    )


def _result_with_nxt_failure() -> OhlcvSyncResult:
    return OhlcvSyncResult(
        base_date=date(2025, 9, 8),
        total=1,
        success_krx=1,
        success_nxt=0,
        failed=1,
        errors=(OhlcvSyncOutcome(stock_code="005930", exchange="NXT", error_class="KiwoomBusinessError"),),
    )


def _make_factory(use_case: AsyncMock) -> IngestPeriodicOhlcvUseCaseFactory:
    @asynccontextmanager
    async def _factory(_alias: str) -> AsyncIterator[IngestPeriodicOhlcvUseCase]:
        yield use_case  # type: ignore[misc]

    return _factory  # type: ignore[return-value]


# ---------- 1. POST weekly/sync ----------


def test_post_weekly_sync_returns_200_with_admin_key(app_client: TestClient, admin_key: str) -> None:
    use_case = AsyncMock(spec=IngestPeriodicOhlcvUseCase)
    use_case.execute.return_value = _ok_result(success_krx=3)

    set_ingest_periodic_ohlcv_factory(_make_factory(use_case))
    try:
        response = app_client.post(
            "/api/kiwoom/ohlcv/weekly/sync",
            headers={"X-API-Key": admin_key},
            params={"alias": "test-alias"},
            json={},
        )
    finally:
        reset_ingest_periodic_ohlcv_factory()

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success_krx"] == 3
    assert body["errors"] == []
    use_case.execute.assert_awaited_once()
    # period=WEEKLY 인자 전달 검증
    call_kwargs = use_case.execute.await_args.kwargs
    assert call_kwargs.get("period") == Period.WEEKLY


def test_post_monthly_sync_returns_200(app_client: TestClient, admin_key: str) -> None:
    use_case = AsyncMock(spec=IngestPeriodicOhlcvUseCase)
    use_case.execute.return_value = _ok_result()

    set_ingest_periodic_ohlcv_factory(_make_factory(use_case))
    try:
        response = app_client.post(
            "/api/kiwoom/ohlcv/monthly/sync",
            headers={"X-API-Key": admin_key},
            params={"alias": "test-alias"},
            json={},
        )
    finally:
        reset_ingest_periodic_ohlcv_factory()

    assert response.status_code == 200
    call_kwargs = use_case.execute.await_args.kwargs
    assert call_kwargs.get("period") == Period.MONTHLY


def test_post_weekly_sync_without_admin_key_returns_401(app_client: TestClient) -> None:
    response = app_client.post(
        "/api/kiwoom/ohlcv/weekly/sync",
        params={"alias": "test-alias"},
        json={},
    )
    assert response.status_code == 401


# ---------- 2. POST refresh ----------


def test_post_weekly_refresh_returns_200(app_client: TestClient, admin_key: str) -> None:
    use_case = AsyncMock(spec=IngestPeriodicOhlcvUseCase)
    use_case.refresh_one.return_value = _ok_result()

    set_ingest_periodic_ohlcv_factory(_make_factory(use_case))
    try:
        response = app_client.post(
            "/api/kiwoom/stocks/005930/ohlcv/weekly/refresh",
            headers={"X-API-Key": admin_key},
            params={"alias": "test-alias", "base_date": "2025-09-08"},
        )
    finally:
        reset_ingest_periodic_ohlcv_factory()

    assert response.status_code == 200, response.text
    use_case.refresh_one.assert_awaited_once()


def test_post_refresh_stock_master_not_found_returns_404(app_client: TestClient, admin_key: str) -> None:
    """R1 M-2 — StockMasterNotFoundError → 404 (subclass first 순서)."""
    use_case = AsyncMock(spec=IngestPeriodicOhlcvUseCase)
    use_case.refresh_one.side_effect = StockMasterNotFoundError("999999")

    set_ingest_periodic_ohlcv_factory(_make_factory(use_case))
    try:
        response = app_client.post(
            "/api/kiwoom/stocks/999999/ohlcv/weekly/refresh",
            headers={"X-API-Key": admin_key},
            params={"alias": "test-alias"},
        )
    finally:
        reset_ingest_periodic_ohlcv_factory()

    assert response.status_code == 404


def test_post_refresh_value_error_returns_400(app_client: TestClient, admin_key: str) -> None:
    """base_date 범위 외 — ValueError → 400."""
    use_case = AsyncMock(spec=IngestPeriodicOhlcvUseCase)
    use_case.refresh_one.side_effect = ValueError("base_date 가 미래")

    set_ingest_periodic_ohlcv_factory(_make_factory(use_case))
    try:
        response = app_client.post(
            "/api/kiwoom/stocks/005930/ohlcv/weekly/refresh",
            headers={"X-API-Key": admin_key},
            params={"alias": "test-alias"},
        )
    finally:
        reset_ingest_periodic_ohlcv_factory()

    assert response.status_code == 400


def test_post_refresh_kiwoom_business_error_returns_400(app_client: TestClient, admin_key: str) -> None:
    """KiwoomBusinessError → 400, message echo 차단."""
    use_case = AsyncMock(spec=IngestPeriodicOhlcvUseCase)
    use_case.refresh_one.side_effect = KiwoomBusinessError(api_id="ka10082", return_code=999, message="민감 정보")

    set_ingest_periodic_ohlcv_factory(_make_factory(use_case))
    try:
        response = app_client.post(
            "/api/kiwoom/stocks/005930/ohlcv/weekly/refresh",
            headers={"X-API-Key": admin_key},
            params={"alias": "test-alias"},
        )
    finally:
        reset_ingest_periodic_ohlcv_factory()

    assert response.status_code == 400
    body = response.json()
    # message echo 차단 — return_msg 가 응답에 없어야
    assert "민감 정보" not in str(body)


# ---------- 3. R1 contract 검증 ----------


def test_post_weekly_sync_only_market_codes_max_length_2(app_client: TestClient, admin_key: str) -> None:
    """R1 L-1 — max_length=2 (pattern={1,2} 일치). 3자 입력 시 422."""
    use_case = AsyncMock(spec=IngestPeriodicOhlcvUseCase)
    use_case.execute.return_value = _ok_result()

    set_ingest_periodic_ohlcv_factory(_make_factory(use_case))
    try:
        response = app_client.post(
            "/api/kiwoom/ohlcv/weekly/sync",
            headers={"X-API-Key": admin_key},
            params={"alias": "test-alias"},
            json={"only_market_codes": ["100"]},  # 3자 — 422
        )
    finally:
        reset_ingest_periodic_ohlcv_factory()

    assert response.status_code == 422


def test_response_errors_serialized_as_json_array(app_client: TestClient, admin_key: str) -> None:
    """R1 invariant — errors tuple 이 JSON array 로 직렬화 (Pydantic v2)."""
    use_case = AsyncMock(spec=IngestPeriodicOhlcvUseCase)
    use_case.execute.return_value = _result_with_nxt_failure()

    set_ingest_periodic_ohlcv_factory(_make_factory(use_case))
    try:
        response = app_client.post(
            "/api/kiwoom/ohlcv/weekly/sync",
            headers={"X-API-Key": admin_key},
            params={"alias": "test-alias"},
            json={},
        )
    finally:
        reset_ingest_periodic_ohlcv_factory()

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["errors"], list)  # JSON array
    assert len(body["errors"]) == 1
    assert body["errors"][0]["exchange"] == "NXT"
    assert body["errors"][0]["error_class"] == "KiwoomBusinessError"


def test_factory_uninitialized_returns_503(app_client: TestClient, admin_key: str) -> None:
    """factory 미초기화 — 503."""
    reset_ingest_periodic_ohlcv_factory()
    response = app_client.post(
        "/api/kiwoom/ohlcv/weekly/sync",
        headers={"X-API-Key": admin_key},
        params={"alias": "test-alias"},
        json={},
    )
    assert response.status_code == 503
