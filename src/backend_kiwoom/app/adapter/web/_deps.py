"""FastAPI 의존성 — admin guard + TokenManager / RevokeUseCase / SyncSectorUseCase factory.

설계: endpoint-01-au10001.md § 7.1 / endpoint-14-ka10101.md § 7.1 / master.md § 6.5.

보안:
- `require_admin_key` — `hmac.compare_digest` 로 timing-safe 비교
- `admin_api_key` 미설정 (`""`) 시 fail-closed (401) — 운영 실수 방어
- `X-API-Key` 헤더 부재 시 401

Singleton 패턴 (모두 `lifespan` 에서 set):
- TokenManager (α)
- RevokeKiwoomTokenUseCase (β)
- SyncSectorUseCaseFactory (A3-β) — alias → AsyncContextManager[UseCase], sync 마다
  새 KiwoomClient 빌드 + close 보장
"""

from __future__ import annotations

import hmac
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from fastapi import Depends, Header, HTTPException, status

from app.application.service.daily_flow_service import IngestDailyFlowUseCase
from app.application.service.ohlcv_daily_service import IngestDailyOhlcvUseCase
from app.application.service.ohlcv_periodic_service import IngestPeriodicOhlcvUseCase
from app.application.service.sector_service import SyncSectorMasterUseCase
from app.application.service.stock_fundamental_service import SyncStockFundamentalUseCase
from app.application.service.stock_master_service import (
    LookupStockUseCase,
    SyncStockMasterUseCase,
)
from app.application.service.token_service import RevokeKiwoomTokenUseCase, TokenManager
from app.config.settings import Settings, get_settings

SyncSectorUseCaseFactory = Callable[[str], AbstractAsyncContextManager[SyncSectorMasterUseCase]]
"""alias → AsyncContextManager[SyncSectorMasterUseCase] factory.

`async with factory(alias) as use_case:` 패턴 — exit 시 KiwoomClient.close 보장.
"""

SyncStockMasterUseCaseFactory = Callable[[str], AbstractAsyncContextManager[SyncStockMasterUseCase]]
"""alias → AsyncContextManager[SyncStockMasterUseCase] factory (B-α 추가).

sector factory 와 동일 패턴 — 매 호출마다 새 KiwoomClient 빌드 + close 보장.
mock_env 는 lifespan 에서 settings.kiwoom_default_env 기반으로 결정 후 묶음.
"""

LookupStockUseCaseFactory = Callable[[str], AbstractAsyncContextManager[LookupStockUseCase]]
"""alias → AsyncContextManager[LookupStockUseCase] factory (B-β 추가).

sync_stock factory 와 동일 패턴 — 매 호출마다 새 KiwoomClient 빌드 + close 보장.
mock_env 는 lifespan 에서 settings.kiwoom_default_env 기반으로 결정.
"""

SyncStockFundamentalUseCaseFactory = Callable[[str], AbstractAsyncContextManager[SyncStockFundamentalUseCase]]
"""alias → AsyncContextManager[SyncStockFundamentalUseCase] factory (B-γ-2 추가).

sync_stock factory 와 동일 패턴 — 매 호출마다 새 KiwoomClient 빌드 + close 보장.
KRX-only 라 mock_env 무관 (ka10001 응답에 nxtEnable 없음).
"""

IngestDailyOhlcvUseCaseFactory = Callable[[str], AbstractAsyncContextManager[IngestDailyOhlcvUseCase]]
"""alias → AsyncContextManager[IngestDailyOhlcvUseCase] factory (C-1β 추가).

sync_stock factory 와 동일 패턴 — 매 호출마다 새 KiwoomClient + KiwoomChartClient 빌드.
nxt_collection_enabled 는 settings 기반으로 lifespan 에서 묶음 (프로세스당 단일 정책).
"""

IngestDailyFlowUseCaseFactory = Callable[[str], AbstractAsyncContextManager[IngestDailyFlowUseCase]]
"""alias → AsyncContextManager[IngestDailyFlowUseCase] factory (C-2β 추가).

C-1β IngestDailyOhlcvUseCaseFactory 와 동일 패턴 — 매 호출마다 새 KiwoomClient +
KiwoomMarketCondClient 빌드. nxt_collection_enabled / indc_mode 는 settings 기반으로
lifespan 에서 묶음 (프로세스당 단일 정책).
"""

IngestPeriodicOhlcvUseCaseFactory = Callable[[str], AbstractAsyncContextManager[IngestPeriodicOhlcvUseCase]]
"""alias → AsyncContextManager[IngestPeriodicOhlcvUseCase] factory (C-3β 추가).

C-1β factory 와 동일 패턴 — 매 호출마다 새 KiwoomClient + KiwoomChartClient 빌드.
period 분기 (WEEKLY/MONTHLY) 는 caller 가 execute(period=...) 인자로 결정.
"""


def get_settings_dep() -> Settings:
    return get_settings()


async def require_admin_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    """admin 라우터 가드.

    timing-safe 비교 + fail-closed (key 미설정 시 401).
    """
    expected = settings.admin_api_key
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="admin api key 미설정 — admin 라우터 비활성",
        )
    if x_api_key is None or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="admin 인증 실패",
        )


# =============================================================================
# Singletons — lifespan 에서 set
# =============================================================================

_token_manager_singleton: TokenManager | None = None
_revoke_use_case_singleton: RevokeKiwoomTokenUseCase | None = None
_sync_sector_factory: SyncSectorUseCaseFactory | None = None
_sync_stock_factory: SyncStockMasterUseCaseFactory | None = None
_lookup_stock_factory: LookupStockUseCaseFactory | None = None
_sync_fundamental_factory: SyncStockFundamentalUseCaseFactory | None = None
_ingest_ohlcv_factory: IngestDailyOhlcvUseCaseFactory | None = None
_ingest_daily_flow_factory: IngestDailyFlowUseCaseFactory | None = None
_ingest_periodic_ohlcv_factory: IngestPeriodicOhlcvUseCaseFactory | None = None


def get_token_manager() -> TokenManager:
    """TokenManager 싱글톤. lifespan 에서 set 하거나 dependency_overrides 로 테스트 주입."""
    if _token_manager_singleton is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TokenManager 미초기화",
        )
    return _token_manager_singleton


def set_token_manager(manager: TokenManager) -> None:
    """lifespan 시작 시 호출 — TokenManager 주입."""
    global _token_manager_singleton
    _token_manager_singleton = manager


def get_revoke_use_case() -> RevokeKiwoomTokenUseCase:
    """RevokeKiwoomTokenUseCase 싱글톤. lifespan 에서 set 또는 dependency_overrides 로 테스트 주입."""
    if _revoke_use_case_singleton is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RevokeUseCase 미초기화",
        )
    return _revoke_use_case_singleton


def set_revoke_use_case(use_case: RevokeKiwoomTokenUseCase) -> None:
    """lifespan 시작 시 호출."""
    global _revoke_use_case_singleton
    _revoke_use_case_singleton = use_case


def get_sync_sector_factory() -> SyncSectorUseCaseFactory:
    """alias → AsyncContextManager[UseCase] factory. lifespan 에서 set."""
    if _sync_sector_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="sector UseCase factory 미초기화",
        )
    return _sync_sector_factory


def set_sync_sector_factory(factory: SyncSectorUseCaseFactory) -> None:
    """lifespan 시작 시 호출 — KiwoomClient 빌드 + UseCase 결합 factory."""
    global _sync_sector_factory
    _sync_sector_factory = factory


def get_sync_stock_factory() -> SyncStockMasterUseCaseFactory:
    """alias → AsyncContextManager[UseCase] factory. lifespan 에서 set."""
    if _sync_stock_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="stock UseCase factory 미초기화",
        )
    return _sync_stock_factory


def set_sync_stock_factory(factory: SyncStockMasterUseCaseFactory) -> None:
    """lifespan 시작 시 호출 — KiwoomClient 빌드 + UseCase 결합 factory."""
    global _sync_stock_factory
    _sync_stock_factory = factory


def get_lookup_stock_factory() -> LookupStockUseCaseFactory:
    """alias → AsyncContextManager[LookupStockUseCase] factory. lifespan 에서 set."""
    if _lookup_stock_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="lookup stock UseCase factory 미초기화",
        )
    return _lookup_stock_factory


def set_lookup_stock_factory(factory: LookupStockUseCaseFactory) -> None:
    """lifespan 시작 시 호출 — KiwoomClient 빌드 + UseCase 결합 factory."""
    global _lookup_stock_factory
    _lookup_stock_factory = factory


def get_sync_fundamental_factory() -> SyncStockFundamentalUseCaseFactory:
    """alias → AsyncContextManager[SyncStockFundamentalUseCase] factory. lifespan 에서 set."""
    if _sync_fundamental_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="fundamental UseCase factory 미초기화",
        )
    return _sync_fundamental_factory


def set_sync_fundamental_factory(factory: SyncStockFundamentalUseCaseFactory) -> None:
    """lifespan 시작 시 호출 — KiwoomClient 빌드 + UseCase 결합 factory (B-γ-2)."""
    global _sync_fundamental_factory
    _sync_fundamental_factory = factory


def get_ingest_ohlcv_factory() -> IngestDailyOhlcvUseCaseFactory:
    """alias → AsyncContextManager[IngestDailyOhlcvUseCase] factory (C-1β). lifespan 에서 set."""
    if _ingest_ohlcv_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ohlcv UseCase factory 미초기화",
        )
    return _ingest_ohlcv_factory


def set_ingest_ohlcv_factory(factory: IngestDailyOhlcvUseCaseFactory) -> None:
    """lifespan 시작 시 호출 — KiwoomClient + KiwoomChartClient 빌드 + UseCase 결합 (C-1β)."""
    global _ingest_ohlcv_factory
    _ingest_ohlcv_factory = factory


def get_ingest_daily_flow_factory() -> IngestDailyFlowUseCaseFactory:
    """alias → AsyncContextManager[IngestDailyFlowUseCase] factory (C-2β). lifespan 에서 set."""
    if _ingest_daily_flow_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="daily_flow UseCase factory 미초기화",
        )
    return _ingest_daily_flow_factory


def set_ingest_daily_flow_factory(factory: IngestDailyFlowUseCaseFactory) -> None:
    """lifespan 시작 시 호출 — KiwoomClient + KiwoomMarketCondClient 빌드 + UseCase 결합 (C-2β)."""
    global _ingest_daily_flow_factory
    _ingest_daily_flow_factory = factory


def get_ingest_periodic_ohlcv_factory() -> IngestPeriodicOhlcvUseCaseFactory:
    """alias → AsyncContextManager[IngestPeriodicOhlcvUseCase] factory (C-3β). lifespan 에서 set."""
    if _ingest_periodic_ohlcv_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="periodic ohlcv UseCase factory 미초기화",
        )
    return _ingest_periodic_ohlcv_factory


def set_ingest_periodic_ohlcv_factory(factory: IngestPeriodicOhlcvUseCaseFactory) -> None:
    """lifespan 시작 시 호출 — KiwoomClient + KiwoomChartClient 빌드 + UseCase 결합 (C-3β)."""
    global _ingest_periodic_ohlcv_factory
    _ingest_periodic_ohlcv_factory = factory


def reset_token_manager() -> None:
    """테스트 전용 — 모든 싱글톤 리셋."""
    global \
        _token_manager_singleton, \
        _revoke_use_case_singleton, \
        _sync_sector_factory, \
        _sync_stock_factory, \
        _lookup_stock_factory, \
        _sync_fundamental_factory, \
        _ingest_ohlcv_factory, \
        _ingest_daily_flow_factory, \
        _ingest_periodic_ohlcv_factory
    _token_manager_singleton = None
    _revoke_use_case_singleton = None
    _sync_sector_factory = None
    _sync_stock_factory = None
    _lookup_stock_factory = None
    _sync_fundamental_factory = None
    _ingest_ohlcv_factory = None
    _ingest_daily_flow_factory = None
    _ingest_periodic_ohlcv_factory = None


def reset_sync_sector_factory() -> None:
    """lifespan teardown + 테스트 — sector factory 만 리셋 (1R 2b M4 fail-closed)."""
    global _sync_sector_factory
    _sync_sector_factory = None


def reset_sync_stock_factory() -> None:
    """lifespan teardown + 테스트 — stock factory 만 리셋 (1R 2b M4 fail-closed)."""
    global _sync_stock_factory
    _sync_stock_factory = None


def reset_lookup_stock_factory() -> None:
    """lifespan teardown + 테스트 — lookup factory 만 리셋 (1R 2b M4 fail-closed)."""
    global _lookup_stock_factory
    _lookup_stock_factory = None


def reset_sync_fundamental_factory() -> None:
    """lifespan teardown + 테스트 — fundamental factory 만 리셋 (B-γ-2, 1R 2b M4 fail-closed)."""
    global _sync_fundamental_factory
    _sync_fundamental_factory = None


def reset_ingest_ohlcv_factory() -> None:
    """lifespan teardown + 테스트 — ohlcv factory 만 리셋 (C-1β, 1R 2b M4 fail-closed)."""
    global _ingest_ohlcv_factory
    _ingest_ohlcv_factory = None


def reset_ingest_daily_flow_factory() -> None:
    """lifespan teardown + 테스트 — daily_flow factory 만 리셋 (C-2β, 1R 2b M4 fail-closed)."""
    global _ingest_daily_flow_factory
    _ingest_daily_flow_factory = None


def reset_ingest_periodic_ohlcv_factory() -> None:
    """lifespan teardown + 테스트 — periodic ohlcv factory 만 리셋 (C-3β, 1R 2b M4 fail-closed)."""
    global _ingest_periodic_ohlcv_factory
    _ingest_periodic_ohlcv_factory = None


__all__ = [
    "IngestDailyFlowUseCaseFactory",
    "IngestDailyOhlcvUseCaseFactory",
    "IngestPeriodicOhlcvUseCaseFactory",
    "LookupStockUseCaseFactory",
    "SyncSectorUseCaseFactory",
    "SyncStockFundamentalUseCaseFactory",
    "SyncStockMasterUseCaseFactory",
    "get_ingest_daily_flow_factory",
    "get_ingest_ohlcv_factory",
    "get_ingest_periodic_ohlcv_factory",
    "get_lookup_stock_factory",
    "get_revoke_use_case",
    "get_settings_dep",
    "get_sync_fundamental_factory",
    "get_sync_sector_factory",
    "get_sync_stock_factory",
    "get_token_manager",
    "require_admin_key",
    "reset_ingest_daily_flow_factory",
    "reset_ingest_ohlcv_factory",
    "reset_ingest_periodic_ohlcv_factory",
    "reset_lookup_stock_factory",
    "reset_sync_fundamental_factory",
    "reset_sync_sector_factory",
    "reset_sync_stock_factory",
    "reset_token_manager",
    "set_ingest_daily_flow_factory",
    "set_ingest_ohlcv_factory",
    "set_ingest_periodic_ohlcv_factory",
    "set_lookup_stock_factory",
    "set_revoke_use_case",
    "set_sync_fundamental_factory",
    "set_sync_sector_factory",
    "set_sync_stock_factory",
    "set_token_manager",
]
