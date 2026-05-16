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
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import Depends, Header, HTTPException, status

from app.application.service.daily_flow_service import IngestDailyFlowUseCase
from app.application.service.investor_flow_service import (
    IngestFrgnOrgnConsecutiveBulkUseCase,
    IngestFrgnOrgnConsecutiveUseCase,
    IngestInvestorDailyTradeBulkUseCase,
    IngestInvestorDailyTradeUseCase,
    IngestStockInvestorBreakdownBulkUseCase,
    IngestStockInvestorBreakdownUseCase,
)
from app.application.service.lending_service import (
    IngestLendingMarketUseCase,
    IngestLendingStockBulkUseCase,
    IngestLendingStockUseCase,
)
from app.application.service.ohlcv_daily_service import IngestDailyOhlcvUseCase
from app.application.service.ohlcv_periodic_service import IngestPeriodicOhlcvUseCase
from app.application.service.ranking_service import (
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
from app.application.service.sector_ohlcv_service import (
    IngestSectorDailyBulkUseCase,
    IngestSectorDailyUseCase,
)
from app.application.service.sector_service import SyncSectorMasterUseCase
from app.application.service.short_selling_service import (
    IngestShortSellingBulkUseCase,
    IngestShortSellingUseCase,
)
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

IngestSectorDailyBulkUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestSectorDailyBulkUseCase]
]
"""alias → AsyncContextManager[IngestSectorDailyBulkUseCase] factory (D-1 추가).

C-1β factory 와 동일 패턴 — 매 호출마다 새 KiwoomClient + KiwoomChartClient 빌드.
plan § 12.2 #4 — KRX only (sector 도메인에 NXT 없음).
"""

IngestSectorDailySingleUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestSectorDailyUseCase]
]
"""alias → AsyncContextManager[IngestSectorDailyUseCase] factory (D-1 추가).

bulk factory 와 동일 패턴 — 단건 refresh 라우터 전용. plan § 12.2 #9 UseCase 입력 = sector_id.
"""

IngestShortSellingUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestShortSellingUseCase]
]
"""alias → AsyncContextManager[IngestShortSellingUseCase] factory (Phase E, ka10014).

D-1 sector factory 와 동일 패턴 — 매 호출마다 새 KiwoomClient + KiwoomShortSellingClient 빌드.
plan § 12.2 결정 #4 — KRX + NXT (nxt_enable 게이팅).
"""

IngestShortSellingBulkUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestShortSellingBulkUseCase]
]
"""alias → AsyncContextManager[IngestShortSellingBulkUseCase] factory (Phase E, ka10014).

single factory 와 동일 패턴 — bulk sync 라우터 전용.
"""

IngestLendingMarketUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestLendingMarketUseCase]
]
"""alias → AsyncContextManager[IngestLendingMarketUseCase] factory (Phase E, ka10068).

C-1β factory 패턴 1:1 — 매 호출마다 새 KiwoomClient + KiwoomLendingClient 빌드.
단일 호출 (시장 단위 — mrkt_tp 분리 없음). 라우터 + scheduler 공용.
"""

IngestLendingStockUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestLendingStockUseCase]
]
"""alias → AsyncContextManager[IngestLendingStockUseCase] factory (Phase E, ka20068).

종목 단건 — 라우터 POST /lending/stock/{code} 진입점 전용.
"""

IngestLendingStockBulkUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestLendingStockBulkUseCase]
]
"""alias → AsyncContextManager[IngestLendingStockBulkUseCase] factory (Phase E, ka20068).

active 종목 bulk — scheduler `LendingStockScheduler` + router POST /lending/stock/sync 공용.
~3000 종목 × 2s = ~100분 추정 (plan § 12.2 H-10).
"""

# =============================================================================
# Phase F-4 — 5 ranking endpoint Bulk factory (ka10027/30/31/32/23)
# =============================================================================

IngestFluRtBulkUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestFluRtUpperBulkUseCase]
]
"""ka10027 등락률 ranking Bulk factory (Phase F-4)."""

IngestTodayVolumeBulkUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestTodayVolumeUpperBulkUseCase]
]
"""ka10030 당일 거래량 ranking Bulk factory (Phase F-4)."""

IngestPredVolumeBulkUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestPredVolumeUpperBulkUseCase]
]
"""ka10031 전일 거래량 ranking Bulk factory (Phase F-4)."""

IngestTradeAmountBulkUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestTradeAmountUpperBulkUseCase]
]
"""ka10032 거래대금 ranking Bulk factory (Phase F-4)."""

IngestVolumeSdninBulkUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestVolumeSdninBulkUseCase]
]
"""ka10023 거래량 급증 ranking Bulk factory (Phase F-4)."""

# Phase F-4 Step 2 fix G-3 — 단건 모드 분리 (5 단건 factory).
# router /sync endpoint 가 body 의 mrkt_tp/sort_tp/stex_tp 로 1×1 단건 호출.

IngestFluRtUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestFluRtUpperUseCase]
]
"""ka10027 등락률 ranking 단건 factory (Phase F-4 Step 2 fix G-3)."""

IngestTodayVolumeUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestTodayVolumeUpperUseCase]
]
"""ka10030 당일 거래량 ranking 단건 factory (Phase F-4 Step 2 fix G-3)."""

IngestPredVolumeUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestPredVolumeUpperUseCase]
]
"""ka10031 전일 거래량 ranking 단건 factory (Phase F-4 Step 2 fix G-3)."""

IngestTradeAmountUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestTradeAmountUpperUseCase]
]
"""ka10032 거래대금 ranking 단건 factory (Phase F-4 Step 2 fix G-3)."""

IngestVolumeSdninUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestVolumeSdninUseCase]
]
"""ka10023 거래량 급증 ranking 단건 factory (Phase F-4 Step 2 fix G-3)."""

# =============================================================================
# Phase G — 3 investor flow endpoint factory (ka10058/10059/10131)
# =============================================================================

IngestInvestorDailyBulkUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestInvestorDailyTradeBulkUseCase]
]
"""ka10058 투자자별 일별 매매 종목 Bulk factory (Phase G)."""

IngestInvestorDailyUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestInvestorDailyTradeUseCase]
]
"""ka10058 단건 factory (Phase G G-3 단건 모드)."""

IngestStockInvestorBreakdownBulkUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestStockInvestorBreakdownBulkUseCase]
]
"""ka10059 종목별 wide breakdown Bulk factory (Phase G)."""

IngestStockInvestorBreakdownUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestStockInvestorBreakdownUseCase]
]
"""ka10059 단건 factory (Phase G G-3 단건 모드)."""

IngestFrgnOrgnBulkUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestFrgnOrgnConsecutiveBulkUseCase]
]
"""ka10131 외국인/기관 연속매매 Bulk factory (Phase G)."""

IngestFrgnOrgnUseCaseFactory = Callable[
    [str], AbstractAsyncContextManager[IngestFrgnOrgnConsecutiveUseCase]
]
"""ka10131 단건 factory (Phase G G-3 단건 모드)."""


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
_ingest_sector_daily_factory: IngestSectorDailyBulkUseCaseFactory | None = None
_ingest_sector_single_factory: IngestSectorDailySingleUseCaseFactory | None = None
_ingest_short_selling_single_factory: IngestShortSellingUseCaseFactory | None = None
_ingest_short_selling_bulk_factory: IngestShortSellingBulkUseCaseFactory | None = None
_ingest_lending_market_factory: IngestLendingMarketUseCaseFactory | None = None
_ingest_lending_stock_single_factory: IngestLendingStockUseCaseFactory | None = None
_ingest_lending_stock_bulk_factory: IngestLendingStockBulkUseCaseFactory | None = None
# Phase F-4 — 5 ranking endpoint Bulk factory singletons
_ingest_flu_rt_bulk_factory: IngestFluRtBulkUseCaseFactory | None = None
_ingest_today_volume_bulk_factory: IngestTodayVolumeBulkUseCaseFactory | None = None
_ingest_pred_volume_bulk_factory: IngestPredVolumeBulkUseCaseFactory | None = None
_ingest_trade_amount_bulk_factory: IngestTradeAmountBulkUseCaseFactory | None = None
_ingest_volume_sdnin_bulk_factory: IngestVolumeSdninBulkUseCaseFactory | None = None
# Phase F-4 Step 2 fix G-3 — 5 단건 factory singletons (sync endpoint 1×1 호출)
_ingest_flu_rt_factory: IngestFluRtUseCaseFactory | None = None
_ingest_today_volume_factory: IngestTodayVolumeUseCaseFactory | None = None
_ingest_pred_volume_factory: IngestPredVolumeUseCaseFactory | None = None
_ingest_trade_amount_factory: IngestTradeAmountUseCaseFactory | None = None
_ingest_volume_sdnin_factory: IngestVolumeSdninUseCaseFactory | None = None
# Phase G — 3 investor flow endpoint (단건 3 + Bulk 3 = 6 factory singletons)
_ingest_investor_daily_factory: IngestInvestorDailyUseCaseFactory | None = None
_ingest_investor_daily_bulk_factory: IngestInvestorDailyBulkUseCaseFactory | None = None
_ingest_stock_investor_breakdown_factory: IngestStockInvestorBreakdownUseCaseFactory | None = None
_ingest_stock_investor_breakdown_bulk_factory: IngestStockInvestorBreakdownBulkUseCaseFactory | None = None
_ingest_frgn_orgn_factory: IngestFrgnOrgnUseCaseFactory | None = None
_ingest_frgn_orgn_bulk_factory: IngestFrgnOrgnBulkUseCaseFactory | None = None


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


def get_ingest_sector_daily_factory() -> IngestSectorDailyBulkUseCaseFactory:
    """alias → AsyncContextManager[IngestSectorDailyBulkUseCase] factory (D-1). lifespan 에서 set."""
    if _ingest_sector_daily_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="sector daily UseCase factory 미초기화",
        )
    return _ingest_sector_daily_factory


def set_ingest_sector_daily_factory(factory: IngestSectorDailyBulkUseCaseFactory) -> None:
    """lifespan 시작 시 호출 — KiwoomClient + KiwoomChartClient 빌드 + Bulk UseCase 결합 (D-1)."""
    global _ingest_sector_daily_factory
    _ingest_sector_daily_factory = factory


def get_ingest_sector_single_factory() -> IngestSectorDailySingleUseCaseFactory:
    """alias → AsyncContextManager[IngestSectorDailyUseCase] factory (D-1, refresh 단건). lifespan 에서 set."""
    if _ingest_sector_single_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="sector daily single UseCase factory 미초기화",
        )
    return _ingest_sector_single_factory


def set_ingest_sector_single_factory(factory: IngestSectorDailySingleUseCaseFactory) -> None:
    """lifespan 시작 시 호출 — 단건 refresh 라우터 전용 (D-1)."""
    global _ingest_sector_single_factory
    _ingest_sector_single_factory = factory


def get_ingest_short_selling_single_factory() -> IngestShortSellingUseCaseFactory:
    """alias → AsyncContextManager[IngestShortSellingUseCase] factory (Phase E, ka10014). lifespan 에서 set."""
    if _ingest_short_selling_single_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="short_selling single UseCase factory 미초기화",
        )
    return _ingest_short_selling_single_factory


def set_ingest_short_selling_single_factory(
    factory: IngestShortSellingUseCaseFactory,
) -> None:
    """lifespan 시작 시 호출 — 단건 refresh 라우터 전용 (Phase E, ka10014)."""
    global _ingest_short_selling_single_factory
    _ingest_short_selling_single_factory = factory


def get_ingest_short_selling_bulk_factory() -> IngestShortSellingBulkUseCaseFactory:
    """alias → AsyncContextManager[IngestShortSellingBulkUseCase] factory (Phase E, ka10014). lifespan 에서 set."""
    if _ingest_short_selling_bulk_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="short_selling bulk UseCase factory 미초기화",
        )
    return _ingest_short_selling_bulk_factory


def set_ingest_short_selling_bulk_factory(
    factory: IngestShortSellingBulkUseCaseFactory,
) -> None:
    """lifespan 시작 시 호출 — bulk sync 라우터 전용 (Phase E, ka10014)."""
    global _ingest_short_selling_bulk_factory
    _ingest_short_selling_bulk_factory = factory


def get_ingest_lending_market_factory() -> IngestLendingMarketUseCaseFactory:
    """alias → AsyncContextManager[IngestLendingMarketUseCase] factory (Phase E, ka10068). lifespan 에서 set."""
    if _ingest_lending_market_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="lending_market UseCase factory 미초기화",
        )
    return _ingest_lending_market_factory


def set_ingest_lending_market_factory(
    factory: IngestLendingMarketUseCaseFactory,
) -> None:
    """lifespan 시작 시 호출 — 시장 단위 단일 호출 라우터 전용 (Phase E, ka10068)."""
    global _ingest_lending_market_factory
    _ingest_lending_market_factory = factory


def get_ingest_lending_stock_single_factory() -> IngestLendingStockUseCaseFactory:
    """alias → AsyncContextManager[IngestLendingStockUseCase] factory (Phase E, ka20068). lifespan 에서 set."""
    if _ingest_lending_stock_single_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="lending_stock single UseCase factory 미초기화",
        )
    return _ingest_lending_stock_single_factory


def set_ingest_lending_stock_single_factory(
    factory: IngestLendingStockUseCaseFactory,
) -> None:
    """lifespan 시작 시 호출 — 종목 단건 라우터 전용 (Phase E, ka20068)."""
    global _ingest_lending_stock_single_factory
    _ingest_lending_stock_single_factory = factory


def get_ingest_lending_stock_bulk_factory() -> IngestLendingStockBulkUseCaseFactory:
    """alias → AsyncContextManager[IngestLendingStockBulkUseCase] factory (Phase E, ka20068). lifespan 에서 set."""
    if _ingest_lending_stock_bulk_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="lending_stock bulk UseCase factory 미초기화",
        )
    return _ingest_lending_stock_bulk_factory


def set_ingest_lending_stock_bulk_factory(
    factory: IngestLendingStockBulkUseCaseFactory,
) -> None:
    """lifespan 시작 시 호출 — active 종목 bulk sync 라우터/scheduler 공용 (Phase E, ka20068)."""
    global _ingest_lending_stock_bulk_factory
    _ingest_lending_stock_bulk_factory = factory


# ----------------------------------------------------------------------------
# Phase F-4 — 5 ranking endpoint Bulk factory getters / setters / resets
# ----------------------------------------------------------------------------


def get_ingest_flu_rt_bulk_factory() -> IngestFluRtBulkUseCaseFactory:
    """ka10027 등락률 ranking Bulk factory (Phase F-4). lifespan 에서 set.

    factory 미초기화 시 lazy factory 반환 — body validation 이 dependency 보다
    먼저 처리되도록 호출 시점에 503 raise.
    """
    factory = _ingest_flu_rt_bulk_factory
    if factory is None:
        @asynccontextmanager
        async def _missing_factory(_alias: str):  # type: ignore[no-untyped-def]
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="flu_rt ranking bulk UseCase factory 미초기화",
            )
            yield  # unreachable
        return _missing_factory
    return factory


def set_ingest_flu_rt_bulk_factory(factory: IngestFluRtBulkUseCaseFactory) -> None:
    """lifespan 시작 시 호출 — ka10027 ranking bulk 라우터/scheduler 공용."""
    global _ingest_flu_rt_bulk_factory
    _ingest_flu_rt_bulk_factory = factory


def reset_ingest_flu_rt_bulk_factory() -> None:
    """lifespan teardown + 테스트 — flu_rt factory 만 리셋."""
    global _ingest_flu_rt_bulk_factory
    _ingest_flu_rt_bulk_factory = None


def get_ingest_today_volume_bulk_factory() -> IngestTodayVolumeBulkUseCaseFactory:
    """ka10030 당일 거래량 ranking Bulk factory (Phase F-4).

    factory 미초기화 시 lazy factory 반환 — body validation 이 dependency 보다
    먼저 처리되도록 호출 시점에 503 raise (F-4 Step 2 fix H-2 통일).
    """
    factory = _ingest_today_volume_bulk_factory
    if factory is None:
        @asynccontextmanager
        async def _missing_factory(_alias: str):  # type: ignore[no-untyped-def]
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="today_volume ranking bulk UseCase factory 미초기화",
            )
            yield  # unreachable
        return _missing_factory
    return factory


def set_ingest_today_volume_bulk_factory(
    factory: IngestTodayVolumeBulkUseCaseFactory,
) -> None:
    global _ingest_today_volume_bulk_factory
    _ingest_today_volume_bulk_factory = factory


def reset_ingest_today_volume_bulk_factory() -> None:
    global _ingest_today_volume_bulk_factory
    _ingest_today_volume_bulk_factory = None


def get_ingest_pred_volume_bulk_factory() -> IngestPredVolumeBulkUseCaseFactory:
    """ka10031 전일 거래량 ranking Bulk factory (Phase F-4).

    factory 미초기화 시 lazy factory 반환 (F-4 Step 2 fix H-2 통일).
    """
    factory = _ingest_pred_volume_bulk_factory
    if factory is None:
        @asynccontextmanager
        async def _missing_factory(_alias: str):  # type: ignore[no-untyped-def]
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="pred_volume ranking bulk UseCase factory 미초기화",
            )
            yield  # unreachable
        return _missing_factory
    return factory


def set_ingest_pred_volume_bulk_factory(
    factory: IngestPredVolumeBulkUseCaseFactory,
) -> None:
    global _ingest_pred_volume_bulk_factory
    _ingest_pred_volume_bulk_factory = factory


def reset_ingest_pred_volume_bulk_factory() -> None:
    global _ingest_pred_volume_bulk_factory
    _ingest_pred_volume_bulk_factory = None


def get_ingest_trade_amount_bulk_factory() -> IngestTradeAmountBulkUseCaseFactory:
    """ka10032 거래대금 ranking Bulk factory (Phase F-4).

    factory 미초기화 시 lazy factory 반환 (F-4 Step 2 fix H-2 통일).
    """
    factory = _ingest_trade_amount_bulk_factory
    if factory is None:
        @asynccontextmanager
        async def _missing_factory(_alias: str):  # type: ignore[no-untyped-def]
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="trade_amount ranking bulk UseCase factory 미초기화",
            )
            yield  # unreachable
        return _missing_factory
    return factory


def set_ingest_trade_amount_bulk_factory(
    factory: IngestTradeAmountBulkUseCaseFactory,
) -> None:
    global _ingest_trade_amount_bulk_factory
    _ingest_trade_amount_bulk_factory = factory


def reset_ingest_trade_amount_bulk_factory() -> None:
    global _ingest_trade_amount_bulk_factory
    _ingest_trade_amount_bulk_factory = None


def get_ingest_volume_sdnin_bulk_factory() -> IngestVolumeSdninBulkUseCaseFactory:
    """ka10023 거래량 급증 ranking Bulk factory (Phase F-4).

    factory 미초기화 시 lazy factory 반환 (F-4 Step 2 fix H-2 통일).
    """
    factory = _ingest_volume_sdnin_bulk_factory
    if factory is None:
        @asynccontextmanager
        async def _missing_factory(_alias: str):  # type: ignore[no-untyped-def]
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="volume_sdnin ranking bulk UseCase factory 미초기화",
            )
            yield  # unreachable
        return _missing_factory
    return factory


def set_ingest_volume_sdnin_bulk_factory(
    factory: IngestVolumeSdninBulkUseCaseFactory,
) -> None:
    global _ingest_volume_sdnin_bulk_factory
    _ingest_volume_sdnin_bulk_factory = factory


def reset_ingest_volume_sdnin_bulk_factory() -> None:
    global _ingest_volume_sdnin_bulk_factory
    _ingest_volume_sdnin_bulk_factory = None


# ----------------------------------------------------------------------------
# Phase F-4 Step 2 fix G-3 — 5 단건 factory getters / setters / resets
# router /sync endpoint 가 body 의 mrkt_tp/sort_tp/stex_tp 로 1×1 호출.
# lazy missing factory 패턴 통일 (H-2).
# ----------------------------------------------------------------------------


def get_ingest_flu_rt_factory() -> IngestFluRtUseCaseFactory:
    """ka10027 등락률 ranking 단건 factory (Phase F-4 Step 2 fix G-3).

    factory 미초기화 시 lazy factory 반환 (H-2 통일).
    """
    factory = _ingest_flu_rt_factory
    if factory is None:
        @asynccontextmanager
        async def _missing_factory(_alias: str):  # type: ignore[no-untyped-def]
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="flu_rt ranking single UseCase factory 미초기화",
            )
            yield  # unreachable
        return _missing_factory
    return factory


def set_ingest_flu_rt_factory(factory: IngestFluRtUseCaseFactory) -> None:
    """lifespan 시작 시 호출 — ka10027 단건 라우터/scheduler 공용."""
    global _ingest_flu_rt_factory
    _ingest_flu_rt_factory = factory


def reset_ingest_flu_rt_factory() -> None:
    """lifespan teardown + 테스트 — flu_rt single factory 만 리셋."""
    global _ingest_flu_rt_factory
    _ingest_flu_rt_factory = None


def get_ingest_today_volume_factory() -> IngestTodayVolumeUseCaseFactory:
    """ka10030 당일 거래량 ranking 단건 factory (Phase F-4 Step 2 fix G-3)."""
    factory = _ingest_today_volume_factory
    if factory is None:
        @asynccontextmanager
        async def _missing_factory(_alias: str):  # type: ignore[no-untyped-def]
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="today_volume ranking single UseCase factory 미초기화",
            )
            yield  # unreachable
        return _missing_factory
    return factory


def set_ingest_today_volume_factory(factory: IngestTodayVolumeUseCaseFactory) -> None:
    global _ingest_today_volume_factory
    _ingest_today_volume_factory = factory


def reset_ingest_today_volume_factory() -> None:
    global _ingest_today_volume_factory
    _ingest_today_volume_factory = None


def get_ingest_pred_volume_factory() -> IngestPredVolumeUseCaseFactory:
    """ka10031 전일 거래량 ranking 단건 factory (Phase F-4 Step 2 fix G-3)."""
    factory = _ingest_pred_volume_factory
    if factory is None:
        @asynccontextmanager
        async def _missing_factory(_alias: str):  # type: ignore[no-untyped-def]
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="pred_volume ranking single UseCase factory 미초기화",
            )
            yield  # unreachable
        return _missing_factory
    return factory


def set_ingest_pred_volume_factory(factory: IngestPredVolumeUseCaseFactory) -> None:
    global _ingest_pred_volume_factory
    _ingest_pred_volume_factory = factory


def reset_ingest_pred_volume_factory() -> None:
    global _ingest_pred_volume_factory
    _ingest_pred_volume_factory = None


def get_ingest_trade_amount_factory() -> IngestTradeAmountUseCaseFactory:
    """ka10032 거래대금 ranking 단건 factory (Phase F-4 Step 2 fix G-3)."""
    factory = _ingest_trade_amount_factory
    if factory is None:
        @asynccontextmanager
        async def _missing_factory(_alias: str):  # type: ignore[no-untyped-def]
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="trade_amount ranking single UseCase factory 미초기화",
            )
            yield  # unreachable
        return _missing_factory
    return factory


def set_ingest_trade_amount_factory(factory: IngestTradeAmountUseCaseFactory) -> None:
    global _ingest_trade_amount_factory
    _ingest_trade_amount_factory = factory


def reset_ingest_trade_amount_factory() -> None:
    global _ingest_trade_amount_factory
    _ingest_trade_amount_factory = None


def get_ingest_volume_sdnin_factory() -> IngestVolumeSdninUseCaseFactory:
    """ka10023 거래량 급증 ranking 단건 factory (Phase F-4 Step 2 fix G-3)."""
    factory = _ingest_volume_sdnin_factory
    if factory is None:
        @asynccontextmanager
        async def _missing_factory(_alias: str):  # type: ignore[no-untyped-def]
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="volume_sdnin ranking single UseCase factory 미초기화",
            )
            yield  # unreachable
        return _missing_factory
    return factory


def set_ingest_volume_sdnin_factory(factory: IngestVolumeSdninUseCaseFactory) -> None:
    global _ingest_volume_sdnin_factory
    _ingest_volume_sdnin_factory = factory


def reset_ingest_volume_sdnin_factory() -> None:
    global _ingest_volume_sdnin_factory
    _ingest_volume_sdnin_factory = None


# ----------------------------------------------------------------------------
# Phase G — 6 investor flow factory getters / setters / resets
# router /sync endpoint 단건 + Bulk 분리 (G-3 패턴 미러).
# lazy missing factory 패턴 통일 (F-4 H-2) — body validation 이 dependency 보다 먼저.
# ----------------------------------------------------------------------------


def get_ingest_investor_daily_factory() -> IngestInvestorDailyUseCaseFactory:
    """ka10058 단건 factory (Phase G G-3)."""
    factory = _ingest_investor_daily_factory
    if factory is None:
        @asynccontextmanager
        async def _missing_factory(_alias: str):  # type: ignore[no-untyped-def]
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="investor_daily single UseCase factory 미초기화",
            )
            yield  # unreachable

        return _missing_factory
    return factory


def set_ingest_investor_daily_factory(factory: IngestInvestorDailyUseCaseFactory) -> None:
    global _ingest_investor_daily_factory
    _ingest_investor_daily_factory = factory


def reset_ingest_investor_daily_factory() -> None:
    global _ingest_investor_daily_factory
    _ingest_investor_daily_factory = None


def get_ingest_investor_daily_bulk_factory() -> IngestInvestorDailyBulkUseCaseFactory:
    """ka10058 Bulk factory (Phase G)."""
    factory = _ingest_investor_daily_bulk_factory
    if factory is None:
        @asynccontextmanager
        async def _missing_factory(_alias: str):  # type: ignore[no-untyped-def]
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="investor_daily bulk UseCase factory 미초기화",
            )
            yield  # unreachable

        return _missing_factory
    return factory


def set_ingest_investor_daily_bulk_factory(
    factory: IngestInvestorDailyBulkUseCaseFactory,
) -> None:
    global _ingest_investor_daily_bulk_factory
    _ingest_investor_daily_bulk_factory = factory


def reset_ingest_investor_daily_bulk_factory() -> None:
    global _ingest_investor_daily_bulk_factory
    _ingest_investor_daily_bulk_factory = None


def get_ingest_stock_investor_breakdown_factory() -> IngestStockInvestorBreakdownUseCaseFactory:
    """ka10059 단건 factory (Phase G G-3)."""
    factory = _ingest_stock_investor_breakdown_factory
    if factory is None:
        @asynccontextmanager
        async def _missing_factory(_alias: str):  # type: ignore[no-untyped-def]
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="stock_investor_breakdown single UseCase factory 미초기화",
            )
            yield  # unreachable

        return _missing_factory
    return factory


def set_ingest_stock_investor_breakdown_factory(
    factory: IngestStockInvestorBreakdownUseCaseFactory,
) -> None:
    global _ingest_stock_investor_breakdown_factory
    _ingest_stock_investor_breakdown_factory = factory


def reset_ingest_stock_investor_breakdown_factory() -> None:
    global _ingest_stock_investor_breakdown_factory
    _ingest_stock_investor_breakdown_factory = None


def get_ingest_stock_investor_breakdown_bulk_factory() -> IngestStockInvestorBreakdownBulkUseCaseFactory:
    """ka10059 Bulk factory (Phase G)."""
    factory = _ingest_stock_investor_breakdown_bulk_factory
    if factory is None:
        @asynccontextmanager
        async def _missing_factory(_alias: str):  # type: ignore[no-untyped-def]
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="stock_investor_breakdown bulk UseCase factory 미초기화",
            )
            yield  # unreachable

        return _missing_factory
    return factory


def set_ingest_stock_investor_breakdown_bulk_factory(
    factory: IngestStockInvestorBreakdownBulkUseCaseFactory,
) -> None:
    global _ingest_stock_investor_breakdown_bulk_factory
    _ingest_stock_investor_breakdown_bulk_factory = factory


def reset_ingest_stock_investor_breakdown_bulk_factory() -> None:
    global _ingest_stock_investor_breakdown_bulk_factory
    _ingest_stock_investor_breakdown_bulk_factory = None


def get_ingest_frgn_orgn_factory() -> IngestFrgnOrgnUseCaseFactory:
    """ka10131 단건 factory (Phase G G-3)."""
    factory = _ingest_frgn_orgn_factory
    if factory is None:
        @asynccontextmanager
        async def _missing_factory(_alias: str):  # type: ignore[no-untyped-def]
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="frgn_orgn single UseCase factory 미초기화",
            )
            yield  # unreachable

        return _missing_factory
    return factory


def set_ingest_frgn_orgn_factory(factory: IngestFrgnOrgnUseCaseFactory) -> None:
    global _ingest_frgn_orgn_factory
    _ingest_frgn_orgn_factory = factory


def reset_ingest_frgn_orgn_factory() -> None:
    global _ingest_frgn_orgn_factory
    _ingest_frgn_orgn_factory = None


def get_ingest_frgn_orgn_bulk_factory() -> IngestFrgnOrgnBulkUseCaseFactory:
    """ka10131 Bulk factory (Phase G)."""
    factory = _ingest_frgn_orgn_bulk_factory
    if factory is None:
        @asynccontextmanager
        async def _missing_factory(_alias: str):  # type: ignore[no-untyped-def]
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="frgn_orgn bulk UseCase factory 미초기화",
            )
            yield  # unreachable

        return _missing_factory
    return factory


def set_ingest_frgn_orgn_bulk_factory(factory: IngestFrgnOrgnBulkUseCaseFactory) -> None:
    global _ingest_frgn_orgn_bulk_factory
    _ingest_frgn_orgn_bulk_factory = factory


def reset_ingest_frgn_orgn_bulk_factory() -> None:
    global _ingest_frgn_orgn_bulk_factory
    _ingest_frgn_orgn_bulk_factory = None


def reset_token_manager() -> None:
    """테스트 전용 — 모든 싱글톤 리셋 (F-4 Step 2 fix H-1: 5 ranking 단건 + 5 Bulk 포함)."""
    global \
        _token_manager_singleton, \
        _revoke_use_case_singleton, \
        _sync_sector_factory, \
        _sync_stock_factory, \
        _lookup_stock_factory, \
        _sync_fundamental_factory, \
        _ingest_ohlcv_factory, \
        _ingest_daily_flow_factory, \
        _ingest_periodic_ohlcv_factory, \
        _ingest_sector_daily_factory, \
        _ingest_sector_single_factory, \
        _ingest_short_selling_single_factory, \
        _ingest_short_selling_bulk_factory, \
        _ingest_lending_market_factory, \
        _ingest_lending_stock_single_factory, \
        _ingest_lending_stock_bulk_factory, \
        _ingest_flu_rt_bulk_factory, \
        _ingest_today_volume_bulk_factory, \
        _ingest_pred_volume_bulk_factory, \
        _ingest_trade_amount_bulk_factory, \
        _ingest_volume_sdnin_bulk_factory, \
        _ingest_flu_rt_factory, \
        _ingest_today_volume_factory, \
        _ingest_pred_volume_factory, \
        _ingest_trade_amount_factory, \
        _ingest_volume_sdnin_factory, \
        _ingest_investor_daily_factory, \
        _ingest_investor_daily_bulk_factory, \
        _ingest_stock_investor_breakdown_factory, \
        _ingest_stock_investor_breakdown_bulk_factory, \
        _ingest_frgn_orgn_factory, \
        _ingest_frgn_orgn_bulk_factory
    _token_manager_singleton = None
    _revoke_use_case_singleton = None
    _sync_sector_factory = None
    _sync_stock_factory = None
    _lookup_stock_factory = None
    _sync_fundamental_factory = None
    _ingest_ohlcv_factory = None
    _ingest_daily_flow_factory = None
    _ingest_periodic_ohlcv_factory = None
    _ingest_sector_daily_factory = None
    _ingest_sector_single_factory = None
    _ingest_short_selling_single_factory = None
    _ingest_short_selling_bulk_factory = None
    _ingest_lending_market_factory = None
    _ingest_lending_stock_single_factory = None
    _ingest_lending_stock_bulk_factory = None
    # Phase F-4 — 5 ranking Bulk + 5 단건 (H-1)
    _ingest_flu_rt_bulk_factory = None
    _ingest_today_volume_bulk_factory = None
    _ingest_pred_volume_bulk_factory = None
    _ingest_trade_amount_bulk_factory = None
    _ingest_volume_sdnin_bulk_factory = None
    _ingest_flu_rt_factory = None
    _ingest_today_volume_factory = None
    _ingest_pred_volume_factory = None
    _ingest_trade_amount_factory = None
    _ingest_volume_sdnin_factory = None
    # Phase G — 3 단건 + 3 Bulk = 6 factory reset
    _ingest_investor_daily_factory = None
    _ingest_investor_daily_bulk_factory = None
    _ingest_stock_investor_breakdown_factory = None
    _ingest_stock_investor_breakdown_bulk_factory = None
    _ingest_frgn_orgn_factory = None
    _ingest_frgn_orgn_bulk_factory = None


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


def reset_ingest_sector_daily_factory() -> None:
    """lifespan teardown + 테스트 — sector daily bulk factory 만 리셋 (D-1, 1R 2b M4 fail-closed)."""
    global _ingest_sector_daily_factory
    _ingest_sector_daily_factory = None


def reset_ingest_sector_single_factory() -> None:
    """lifespan teardown + 테스트 — sector daily single factory 만 리셋 (D-1, 1R 2b M4 fail-closed)."""
    global _ingest_sector_single_factory
    _ingest_sector_single_factory = None


def reset_ingest_short_selling_single_factory() -> None:
    """lifespan teardown + 테스트 — short_selling single factory 만 리셋 (Phase E, 1R 2b M4 fail-closed)."""
    global _ingest_short_selling_single_factory
    _ingest_short_selling_single_factory = None


def reset_ingest_short_selling_bulk_factory() -> None:
    """lifespan teardown + 테스트 — short_selling bulk factory 만 리셋 (Phase E, 1R 2b M4 fail-closed)."""
    global _ingest_short_selling_bulk_factory
    _ingest_short_selling_bulk_factory = None


def reset_ingest_lending_market_factory() -> None:
    """lifespan teardown + 테스트 — lending_market factory 만 리셋 (Phase E, 1R 2b M4 fail-closed)."""
    global _ingest_lending_market_factory
    _ingest_lending_market_factory = None


def reset_ingest_lending_stock_single_factory() -> None:
    """lifespan teardown + 테스트 — lending_stock single factory 만 리셋 (Phase E, 1R 2b M4 fail-closed)."""
    global _ingest_lending_stock_single_factory
    _ingest_lending_stock_single_factory = None


def reset_ingest_lending_stock_bulk_factory() -> None:
    """lifespan teardown + 테스트 — lending_stock bulk factory 만 리셋 (Phase E, 1R 2b M4 fail-closed)."""
    global _ingest_lending_stock_bulk_factory
    _ingest_lending_stock_bulk_factory = None


__all__ = [
    "IngestDailyFlowUseCaseFactory",
    "IngestDailyOhlcvUseCaseFactory",
    "IngestFluRtBulkUseCaseFactory",
    "IngestFluRtUseCaseFactory",
    "IngestFrgnOrgnBulkUseCaseFactory",
    "IngestFrgnOrgnUseCaseFactory",
    "IngestInvestorDailyBulkUseCaseFactory",
    "IngestInvestorDailyUseCaseFactory",
    "IngestLendingMarketUseCaseFactory",
    "IngestLendingStockBulkUseCaseFactory",
    "IngestLendingStockUseCaseFactory",
    "IngestPeriodicOhlcvUseCaseFactory",
    "IngestPredVolumeBulkUseCaseFactory",
    "IngestPredVolumeUseCaseFactory",
    "IngestSectorDailyBulkUseCaseFactory",
    "IngestSectorDailySingleUseCaseFactory",
    "IngestShortSellingBulkUseCaseFactory",
    "IngestShortSellingUseCaseFactory",
    "IngestStockInvestorBreakdownBulkUseCaseFactory",
    "IngestStockInvestorBreakdownUseCaseFactory",
    "IngestTodayVolumeBulkUseCaseFactory",
    "IngestTodayVolumeUseCaseFactory",
    "IngestTradeAmountBulkUseCaseFactory",
    "IngestTradeAmountUseCaseFactory",
    "IngestVolumeSdninBulkUseCaseFactory",
    "IngestVolumeSdninUseCaseFactory",
    "LookupStockUseCaseFactory",
    "SyncSectorUseCaseFactory",
    "SyncStockFundamentalUseCaseFactory",
    "SyncStockMasterUseCaseFactory",
    "get_ingest_daily_flow_factory",
    "get_ingest_flu_rt_bulk_factory",
    "get_ingest_flu_rt_factory",
    "get_ingest_frgn_orgn_bulk_factory",
    "get_ingest_frgn_orgn_factory",
    "get_ingest_investor_daily_bulk_factory",
    "get_ingest_investor_daily_factory",
    "get_ingest_lending_market_factory",
    "get_ingest_lending_stock_bulk_factory",
    "get_ingest_lending_stock_single_factory",
    "get_ingest_ohlcv_factory",
    "get_ingest_periodic_ohlcv_factory",
    "get_ingest_pred_volume_bulk_factory",
    "get_ingest_pred_volume_factory",
    "get_ingest_sector_daily_factory",
    "get_ingest_sector_single_factory",
    "get_ingest_short_selling_bulk_factory",
    "get_ingest_short_selling_single_factory",
    "get_ingest_stock_investor_breakdown_bulk_factory",
    "get_ingest_stock_investor_breakdown_factory",
    "get_ingest_today_volume_bulk_factory",
    "get_ingest_today_volume_factory",
    "get_ingest_trade_amount_bulk_factory",
    "get_ingest_trade_amount_factory",
    "get_ingest_volume_sdnin_bulk_factory",
    "get_ingest_volume_sdnin_factory",
    "get_lookup_stock_factory",
    "get_revoke_use_case",
    "get_settings_dep",
    "get_sync_fundamental_factory",
    "get_sync_sector_factory",
    "get_sync_stock_factory",
    "get_token_manager",
    "require_admin_key",
    "reset_ingest_daily_flow_factory",
    "reset_ingest_flu_rt_bulk_factory",
    "reset_ingest_flu_rt_factory",
    "reset_ingest_frgn_orgn_bulk_factory",
    "reset_ingest_frgn_orgn_factory",
    "reset_ingest_investor_daily_bulk_factory",
    "reset_ingest_investor_daily_factory",
    "reset_ingest_lending_market_factory",
    "reset_ingest_lending_stock_bulk_factory",
    "reset_ingest_lending_stock_single_factory",
    "reset_ingest_ohlcv_factory",
    "reset_ingest_periodic_ohlcv_factory",
    "reset_ingest_pred_volume_bulk_factory",
    "reset_ingest_pred_volume_factory",
    "reset_ingest_sector_daily_factory",
    "reset_ingest_sector_single_factory",
    "reset_ingest_short_selling_bulk_factory",
    "reset_ingest_short_selling_single_factory",
    "reset_ingest_stock_investor_breakdown_bulk_factory",
    "reset_ingest_stock_investor_breakdown_factory",
    "reset_ingest_today_volume_bulk_factory",
    "reset_ingest_today_volume_factory",
    "reset_ingest_trade_amount_bulk_factory",
    "reset_ingest_trade_amount_factory",
    "reset_ingest_volume_sdnin_bulk_factory",
    "reset_ingest_volume_sdnin_factory",
    "reset_lookup_stock_factory",
    "reset_sync_fundamental_factory",
    "reset_sync_sector_factory",
    "reset_sync_stock_factory",
    "reset_token_manager",
    "set_ingest_daily_flow_factory",
    "set_ingest_flu_rt_bulk_factory",
    "set_ingest_flu_rt_factory",
    "set_ingest_frgn_orgn_bulk_factory",
    "set_ingest_frgn_orgn_factory",
    "set_ingest_investor_daily_bulk_factory",
    "set_ingest_investor_daily_factory",
    "set_ingest_lending_market_factory",
    "set_ingest_lending_stock_bulk_factory",
    "set_ingest_lending_stock_single_factory",
    "set_ingest_ohlcv_factory",
    "set_ingest_periodic_ohlcv_factory",
    "set_ingest_pred_volume_bulk_factory",
    "set_ingest_pred_volume_factory",
    "set_ingest_sector_daily_factory",
    "set_ingest_sector_single_factory",
    "set_ingest_short_selling_bulk_factory",
    "set_ingest_short_selling_single_factory",
    "set_ingest_stock_investor_breakdown_bulk_factory",
    "set_ingest_stock_investor_breakdown_factory",
    "set_ingest_today_volume_bulk_factory",
    "set_ingest_today_volume_factory",
    "set_ingest_trade_amount_bulk_factory",
    "set_ingest_trade_amount_factory",
    "set_ingest_volume_sdnin_bulk_factory",
    "set_ingest_volume_sdnin_factory",
    "set_lookup_stock_factory",
    "set_revoke_use_case",
    "set_sync_fundamental_factory",
    "set_sync_sector_factory",
    "set_sync_stock_factory",
    "set_token_manager",
]
