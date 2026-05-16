"""FastAPI 진입점 — α (발급) + β (폐기 + lifespan graceful shutdown).

세션 라이프사이클 (H4 α 적대적 리뷰):
- TokenManager 가 session_provider 주입 받아 매 발급마다 session 생성 + close 보장

Graceful shutdown (β):
- lifespan yield 후 활성 alias 전부 폐기 시도 (best-effort, asyncio.wait_for 타임아웃)
- 한 alias 실패해도 다른 alias 진행 — `revoke_all_aliases_best_effort`
- 종료 직전 invalidate_all — 모든 캐시 비움
- engine.dispose() 는 revoke hang 시에도 도달 보장 (분리된 try/finally — H-3 적대적 리뷰)

ValidationError 핸들러 (β C-1 적대적 리뷰):
- 민감 경로(`/revoke-raw`)에서 422 응답 본문에 token 평문이 echo 되지 않도록
  loc/type/msg 만 노출하고 input/ctx 제거.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any, Final, Literal

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapter.out.kiwoom._client import KiwoomClient
from app.adapter.out.kiwoom.auth import KiwoomAuthClient
from app.adapter.out.kiwoom.chart import KiwoomChartClient
from app.adapter.out.kiwoom.mrkcond import KiwoomMarketCondClient
from app.adapter.out.kiwoom.rkinfo import KiwoomRkInfoClient
from app.adapter.out.kiwoom.shsa import KiwoomShortSellingClient
from app.adapter.out.kiwoom.slb import KiwoomLendingClient
from app.adapter.out.kiwoom.stkinfo import KiwoomStkInfoClient
from app.adapter.out.persistence.session import get_engine, get_sessionmaker
from app.adapter.web._deps import (
    require_admin_key,
    reset_ingest_daily_flow_factory,
    reset_ingest_flu_rt_bulk_factory,
    reset_ingest_flu_rt_factory,
    reset_ingest_lending_market_factory,
    reset_ingest_lending_stock_bulk_factory,
    reset_ingest_lending_stock_single_factory,
    reset_ingest_ohlcv_factory,
    reset_ingest_periodic_ohlcv_factory,
    reset_ingest_pred_volume_bulk_factory,
    reset_ingest_pred_volume_factory,
    reset_ingest_sector_daily_factory,
    reset_ingest_sector_single_factory,
    reset_ingest_short_selling_bulk_factory,
    reset_ingest_short_selling_single_factory,
    reset_ingest_today_volume_bulk_factory,
    reset_ingest_today_volume_factory,
    reset_ingest_trade_amount_bulk_factory,
    reset_ingest_trade_amount_factory,
    reset_ingest_volume_sdnin_bulk_factory,
    reset_ingest_volume_sdnin_factory,
    reset_lookup_stock_factory,
    reset_sync_fundamental_factory,
    reset_sync_sector_factory,
    reset_sync_stock_factory,
    set_ingest_daily_flow_factory,
    set_ingest_flu_rt_bulk_factory,
    set_ingest_flu_rt_factory,
    set_ingest_lending_market_factory,
    set_ingest_lending_stock_bulk_factory,
    set_ingest_lending_stock_single_factory,
    set_ingest_ohlcv_factory,
    set_ingest_periodic_ohlcv_factory,
    set_ingest_pred_volume_bulk_factory,
    set_ingest_pred_volume_factory,
    set_ingest_sector_daily_factory,
    set_ingest_sector_single_factory,
    set_ingest_short_selling_bulk_factory,
    set_ingest_short_selling_single_factory,
    set_ingest_today_volume_bulk_factory,
    set_ingest_today_volume_factory,
    set_ingest_trade_amount_bulk_factory,
    set_ingest_trade_amount_factory,
    set_ingest_volume_sdnin_bulk_factory,
    set_ingest_volume_sdnin_factory,
    set_lookup_stock_factory,
    set_revoke_use_case,
    set_sync_fundamental_factory,
    set_sync_sector_factory,
    set_sync_stock_factory,
    set_token_manager,
)
from app.adapter.web.routers.auth import router as auth_router
from app.adapter.web.routers.daily_flow import router as daily_flow_router
from app.adapter.web.routers.fundamentals import router as fundamentals_router
from app.adapter.web.routers.lending import router as lending_router
from app.adapter.web.routers.ohlcv import router as ohlcv_router
from app.adapter.web.routers.ohlcv_periodic import router as ohlcv_periodic_router
from app.adapter.web.routers.rankings import router as rankings_router
from app.adapter.web.routers.sector_ohlcv import router as sector_ohlcv_router
from app.adapter.web.routers.sectors import router as sectors_router
from app.adapter.web.routers.short_selling import router as short_selling_router
from app.adapter.web.routers.stocks import router as stocks_router
from app.application.constants import DailyMarketDisplayMode
from app.application.service.daily_flow_service import IngestDailyFlowUseCase
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
from app.application.service.token_service import (
    RevokeKiwoomTokenUseCase,
    TokenManager,
    revoke_all_aliases_best_effort,
)
from app.config.settings import get_settings
from app.observability.logging import setup_logging
from app.scheduler import (
    DailyFlowScheduler,
    FluRtRankingScheduler,
    LendingMarketScheduler,
    LendingStockScheduler,
    MonthlyOhlcvScheduler,
    OhlcvDailyScheduler,
    PredVolumeRankingScheduler,
    SectorDailyOhlcvScheduler,
    SectorSyncScheduler,
    ShortSellingScheduler,
    StockFundamentalScheduler,
    StockMasterScheduler,
    TodayVolumeRankingScheduler,
    TrdePricaRankingScheduler,
    VolumeSdninRankingScheduler,
    WeeklyOhlcvScheduler,
    YearlyOhlcvScheduler,
)
from app.security.kiwoom_credential_cipher import KiwoomCredentialCipher

logger = logging.getLogger(__name__)

# β C-1 — 422 응답에 input 평문 echo 차단 대상 경로.
# /revoke-raw body 가 token 평문을 담음 — ValidationError input 노출 시 민감 정보 누설.
_SENSITIVE_VALIDATION_PATHS: Final[frozenset[str]] = frozenset({"/api/kiwoom/auth/tokens/revoke-raw"})

SHUTDOWN_REVOKE_TIMEOUT_SECONDS: Final[float] = 20.0
"""shutdown 일괄 폐기 글로벌 타임아웃 — k8s SIGKILL 30s grace 전 안전 마진."""


def _scrubbed_validation_error(exc: RequestValidationError) -> list[dict[str, Any]]:
    """ValidationError errors 에서 input/ctx 제거 — 토큰/비밀 echo 차단."""
    safe: list[dict[str, Any]] = []
    for err in exc.errors():
        safe.append(
            {
                "type": err.get("type", "validation_error"),
                "loc": err.get("loc", []),
                "msg": err.get("msg", ""),
            }
        )
    return safe


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(
        log_level=settings.log_level,
        json_output=settings.app_env != "local",
    )

    # B-γ-2 2R H-1 — fail-fast 검증을 set_*_factory 호출 **앞으로** 이동.
    # set 호출 후 RuntimeError 가 raise 되면 try/finally 의 cleanup (reset_*_factory,
    # revoke_all_aliases, engine.dispose) 절대 도달 안 함 → singleton/engine 누설.
    # 운영 실수로 alias 미설정 시에도 cleanup 보장 (process boundary 안전망).
    if settings.scheduler_enabled:
        # 각 alias 는 해당 job 이 `_enabled=True` 일 때만 체크 (2R-2a-H-1 fix).
        # 개별 _sync_enabled=False 로 비활성한 job 은 alias 빈 값 허용 — env override 가드.
        alias_checks: list[tuple[str, str, bool]] = [
            ("scheduler_sector_sync_alias", settings.scheduler_sector_sync_alias, True),
            ("scheduler_stock_sync_alias", settings.scheduler_stock_sync_alias, True),
            ("scheduler_fundamental_sync_alias", settings.scheduler_fundamental_sync_alias, True),
            ("scheduler_ohlcv_daily_sync_alias", settings.scheduler_ohlcv_daily_sync_alias, True),
            ("scheduler_daily_flow_sync_alias", settings.scheduler_daily_flow_sync_alias, True),
            ("scheduler_weekly_ohlcv_sync_alias", settings.scheduler_weekly_ohlcv_sync_alias, True),
            ("scheduler_monthly_ohlcv_sync_alias", settings.scheduler_monthly_ohlcv_sync_alias, True),
            ("scheduler_yearly_ohlcv_sync_alias", settings.scheduler_yearly_ohlcv_sync_alias, True),
            (
                "scheduler_sector_daily_sync_alias",
                settings.scheduler_sector_daily_sync_alias,
                True,
            ),
            # Phase E — 개별 _enabled flag 가 False 면 alias 미설정 허용.
            (
                "scheduler_short_selling_sync_alias",
                settings.scheduler_short_selling_sync_alias,
                settings.scheduler_short_selling_sync_enabled,
            ),
            (
                "scheduler_lending_market_sync_alias",
                settings.scheduler_lending_market_sync_alias,
                settings.scheduler_lending_market_sync_enabled,
            ),
            (
                "scheduler_lending_stock_sync_alias",
                settings.scheduler_lending_stock_sync_alias,
                settings.scheduler_lending_stock_sync_enabled,
            ),
            # Phase F-4 Step 2 fix C-2 — 5 ranking endpoint alias (개별 _enabled flag 게이팅)
            (
                "scheduler_flu_rt_ranking_sync_alias",
                settings.scheduler_flu_rt_ranking_sync_alias,
                settings.scheduler_flu_rt_ranking_sync_enabled,
            ),
            (
                "scheduler_today_volume_ranking_sync_alias",
                settings.scheduler_today_volume_ranking_sync_alias,
                settings.scheduler_today_volume_ranking_sync_enabled,
            ),
            (
                "scheduler_pred_volume_ranking_sync_alias",
                settings.scheduler_pred_volume_ranking_sync_alias,
                settings.scheduler_pred_volume_ranking_sync_enabled,
            ),
            (
                "scheduler_trade_amount_ranking_sync_alias",
                settings.scheduler_trade_amount_ranking_sync_alias,
                settings.scheduler_trade_amount_ranking_sync_enabled,
            ),
            (
                "scheduler_volume_sdnin_ranking_sync_alias",
                settings.scheduler_volume_sdnin_ranking_sync_alias,
                settings.scheduler_volume_sdnin_ranking_sync_enabled,
            ),
        ]
        missing_aliases = [name for name, value, job_enabled in alias_checks if job_enabled and not value]
        if missing_aliases:
            raise RuntimeError(
                f"scheduler_enabled=True 인데 미설정 alias: {missing_aliases} — 운영 실수 방어 fail-fast"
            )

    cipher = KiwoomCredentialCipher(master_key=settings.kiwoom_credential_master_key)
    sessionmaker = get_sessionmaker()

    def _session_provider() -> AbstractAsyncContextManager[AsyncSession]:
        return sessionmaker()

    def _auth_client_factory(base_url: str) -> KiwoomAuthClient:
        return KiwoomAuthClient(base_url=base_url)

    manager = TokenManager(
        session_provider=_session_provider,
        cipher=cipher,
        auth_client_factory=_auth_client_factory,
    )
    revoke_uc = RevokeKiwoomTokenUseCase(
        session_provider=_session_provider,
        cipher=cipher,
        auth_client_factory=_auth_client_factory,
        token_manager=manager,
    )
    set_token_manager(manager)
    set_revoke_use_case(revoke_uc)

    # A3-β: SyncSectorUseCaseFactory — alias 단위 KiwoomClient 빌드 + close 보장.
    # `async with factory(alias) as use_case:` 패턴으로 라우터에서 사용.
    @asynccontextmanager
    async def _sync_sector_factory(alias: str) -> AsyncIterator[SyncSectorMasterUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        # alias 의 환경 (prod/mock) 결정 — 자격증명 row 의 env 컬럼 기반
        # 현재는 settings 의 default base_url_prod 사용 (mock 사용은 운영 dry-run 후 결정)
        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            stkinfo = KiwoomStkInfoClient(kiwoom_client)
            yield SyncSectorMasterUseCase(
                session_provider=_session_provider,
                stkinfo_client=stkinfo,
            )
        finally:
            await kiwoom_client.close()

    set_sync_sector_factory(_sync_sector_factory)

    # B-α: SyncStockMasterUseCaseFactory — sector factory 와 동일 패턴.
    #
    # mock_env 결정 정책 (1R H-1 적대적 리뷰):
    # - 운영 가정: **프로세스당 단일 env** (한 프로세스에서 prod alias + mock alias 혼용 안 함)
    # - settings.kiwoom_default_env 가 진실의 원천 — 프로세스 시작 시 lifespan 1회 결정
    # - 만약 향후 멀티 env 동시 운영이 필요하면, factory 안에서 alias 의 자격증명 row
    #   (kiwoom_credential.env 컬럼) 를 조회해 alias 단위로 mock_env 를 결정하도록 변경 필요
    # - 현재는 H-1 위험을 운영 가정으로 차단 (ADR-0001 § 운영 정책에 명시)
    stock_mock_env = settings.kiwoom_default_env == "mock"

    @asynccontextmanager
    async def _sync_stock_factory(alias: str) -> AsyncIterator[SyncStockMasterUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            stkinfo = KiwoomStkInfoClient(kiwoom_client)
            yield SyncStockMasterUseCase(
                session_provider=_session_provider,
                stkinfo_client=stkinfo,
                mock_env=stock_mock_env,
            )
        finally:
            await kiwoom_client.close()

    set_sync_stock_factory(_sync_stock_factory)

    # B-β: LookupStockUseCaseFactory — sync_stock factory 와 같은 패턴, 같은 mock_env 정책.
    # 단건 보강이므로 RPS 가 낮음 (admin 명시 호출 + Phase C 의 ensure_exists lazy fetch).
    @asynccontextmanager
    async def _lookup_stock_factory(alias: str) -> AsyncIterator[LookupStockUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            stkinfo = KiwoomStkInfoClient(kiwoom_client)
            yield LookupStockUseCase(
                session_provider=_session_provider,
                stkinfo_client=stkinfo,
                mock_env=stock_mock_env,
            )
        finally:
            await kiwoom_client.close()

    set_lookup_stock_factory(_lookup_stock_factory)

    # B-γ-2: SyncStockFundamentalUseCaseFactory — sync_stock factory 와 같은 패턴.
    # KRX-only (ADR § 14) 라 mock_env 무관 (ka10001 응답에 nxtEnable 없음).
    @asynccontextmanager
    async def _sync_fundamental_factory(alias: str) -> AsyncIterator[SyncStockFundamentalUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            stkinfo = KiwoomStkInfoClient(kiwoom_client)
            yield SyncStockFundamentalUseCase(
                session_provider=_session_provider,
                stkinfo_client=stkinfo,
            )
        finally:
            await kiwoom_client.close()

    set_sync_fundamental_factory(_sync_fundamental_factory)

    # C-1β: IngestDailyOhlcvUseCaseFactory — sync_stock factory 와 같은 패턴.
    # nxt_collection_enabled 는 settings 로 lifespan 에서 묶음 (프로세스당 단일 정책, 1R H-1
    # 패턴 일관 — 멀티 env / 멀티 nxt 정책 동시 운영은 향후 확장).
    nxt_enabled = settings.nxt_collection_enabled

    @asynccontextmanager
    async def _ingest_ohlcv_factory(alias: str) -> AsyncIterator[IngestDailyOhlcvUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            chart = KiwoomChartClient(kiwoom_client)
            yield IngestDailyOhlcvUseCase(
                session_provider=_session_provider,
                chart_client=chart,
                nxt_collection_enabled=nxt_enabled,
            )
        finally:
            await kiwoom_client.close()

    set_ingest_ohlcv_factory(_ingest_ohlcv_factory)

    # C-2β: IngestDailyFlowUseCaseFactory — C-1β 패턴 일관 (KiwoomMarketCondClient 빌드).
    # indc_mode 는 프로세스당 단일 정책 — 디폴트 QUANTITY (계획서 § 2.3 권장 — 백테스팅 시그널
    # 단위 일관성). 향후 setting 으로 전환 시 settings.daily_flow_indc_mode 추가.
    daily_flow_indc_mode = DailyMarketDisplayMode.QUANTITY

    @asynccontextmanager
    async def _ingest_daily_flow_factory(alias: str) -> AsyncIterator[IngestDailyFlowUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            mrkcond = KiwoomMarketCondClient(kiwoom_client)
            yield IngestDailyFlowUseCase(
                session_provider=_session_provider,
                mrkcond_client=mrkcond,
                nxt_collection_enabled=nxt_enabled,
                indc_mode=daily_flow_indc_mode,
            )
        finally:
            await kiwoom_client.close()

    set_ingest_daily_flow_factory(_ingest_daily_flow_factory)

    # C-3β: IngestPeriodicOhlcvUseCaseFactory — 주/월봉 통합. C-1β 패턴 일관 + period dispatch.
    @asynccontextmanager
    async def _ingest_periodic_ohlcv_factory(
        alias: str,
    ) -> AsyncIterator[IngestPeriodicOhlcvUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            chart = KiwoomChartClient(kiwoom_client)
            yield IngestPeriodicOhlcvUseCase(
                session_provider=_session_provider,
                chart_client=chart,
                nxt_collection_enabled=nxt_enabled,
            )
        finally:
            await kiwoom_client.close()

    set_ingest_periodic_ohlcv_factory(_ingest_periodic_ohlcv_factory)

    # D-1: IngestSectorDaily{Bulk,Single}UseCaseFactory — 1R CRITICAL #2 fix.
    # Bulk = sync 전체 (active sector iterate) / Single = refresh 단건 (sector_id 지정).
    # 두 factory 모두 동일 KiwoomClient 패턴 — 라우터/scheduler 각각의 진입점에서 사용.
    @asynccontextmanager
    async def _ingest_sector_daily_bulk_factory(
        alias: str,
    ) -> AsyncIterator[IngestSectorDailyBulkUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            chart = KiwoomChartClient(kiwoom_client)
            yield IngestSectorDailyBulkUseCase(
                session_provider=_session_provider,
                chart_client=chart,
            )
        finally:
            await kiwoom_client.close()

    @asynccontextmanager
    async def _ingest_sector_daily_single_factory(
        alias: str,
    ) -> AsyncIterator[IngestSectorDailyUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            chart = KiwoomChartClient(kiwoom_client)
            yield IngestSectorDailyUseCase(
                session_provider=_session_provider,
                chart_client=chart,
            )
        finally:
            await kiwoom_client.close()

    set_ingest_sector_daily_factory(_ingest_sector_daily_bulk_factory)
    set_ingest_sector_single_factory(_ingest_sector_daily_single_factory)

    # Phase E — ShortSelling Single + Bulk factory (ka10014).
    # C-1β / D-1 패턴 1:1 — 매 호출마다 새 KiwoomClient + KiwoomShortSellingClient 빌드.
    # IngestShortSellingUseCase / IngestShortSellingBulkUseCase 는 `session_provider` 사용
    # (lending UseCase 와 시그니처 차이) — 직접 주입.
    short_selling_env: Literal["prod", "mock"] = settings.kiwoom_default_env

    @asynccontextmanager
    async def _ingest_short_selling_single_factory(
        alias: str,
    ) -> AsyncIterator[IngestShortSellingUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            shsa = KiwoomShortSellingClient(kiwoom_client)
            yield IngestShortSellingUseCase(
                session_provider=_session_provider,
                shsa_client=shsa,
                env=short_selling_env,
            )
        finally:
            await kiwoom_client.close()

    @asynccontextmanager
    async def _ingest_short_selling_bulk_factory(
        alias: str,
    ) -> AsyncIterator[IngestShortSellingBulkUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            shsa = KiwoomShortSellingClient(kiwoom_client)
            single = IngestShortSellingUseCase(
                session_provider=_session_provider,
                shsa_client=shsa,
                env=short_selling_env,
            )
            yield IngestShortSellingBulkUseCase(
                session_provider=_session_provider,
                single_use_case=single,
            )
        finally:
            await kiwoom_client.close()

    set_ingest_short_selling_single_factory(_ingest_short_selling_single_factory)
    set_ingest_short_selling_bulk_factory(_ingest_short_selling_bulk_factory)

    # Phase E — Lending Market (ka10068) + Stock Single/Bulk (ka20068) factory.
    # 차이점: IngestLending* UseCase 는 `session: AsyncSession` 을 직접 받음 (provider 아님).
    # 따라서 factory 가 sessionmaker() 컨텍스트 안에서 UseCase 를 yield. exit 시 session 자동 close.
    lending_env: Literal["prod", "mock"] = settings.kiwoom_default_env

    @asynccontextmanager
    async def _ingest_lending_market_factory(
        alias: str,
    ) -> AsyncIterator[IngestLendingMarketUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            slb = KiwoomLendingClient(kiwoom_client)
            async with sessionmaker() as session:
                yield IngestLendingMarketUseCase(
                    session=session,
                    slb_client=slb,
                )
                # caller (router/scheduler) 의 UseCase.execute 정상 종료 후 commit.
                # 예외 발생 시 sessionmaker 의 default rollback 이 동작.
                await session.commit()
        finally:
            await kiwoom_client.close()

    @asynccontextmanager
    async def _ingest_lending_stock_single_factory(
        alias: str,
    ) -> AsyncIterator[IngestLendingStockUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            slb = KiwoomLendingClient(kiwoom_client)
            async with sessionmaker() as session:
                yield IngestLendingStockUseCase(
                    session=session,
                    slb_client=slb,
                    env=lending_env,
                )
                await session.commit()
        finally:
            await kiwoom_client.close()

    @asynccontextmanager
    async def _ingest_lending_stock_bulk_factory(
        alias: str,
    ) -> AsyncIterator[IngestLendingStockBulkUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            slb = KiwoomLendingClient(kiwoom_client)
            async with sessionmaker() as session:
                single = IngestLendingStockUseCase(
                    session=session,
                    slb_client=slb,
                    env=lending_env,
                )
                yield IngestLendingStockBulkUseCase(
                    session=session,
                    single_use_case=single,
                )
                await session.commit()
        finally:
            await kiwoom_client.close()

    set_ingest_lending_market_factory(_ingest_lending_market_factory)
    set_ingest_lending_stock_single_factory(_ingest_lending_stock_single_factory)
    set_ingest_lending_stock_bulk_factory(_ingest_lending_stock_bulk_factory)

    # =========================================================================
    # Phase F-4 — 5 ranking endpoint factory (ka10027/30/31/32/23)
    # C-1β / D-1 / Phase E 패턴 1:1 — 매 호출마다 새 KiwoomClient + KiwoomRkInfoClient 빌드.
    # 단건 UseCase + Bulk UseCase 둘 다 빌드 (sync = 단건 / bulk-sync = 매트릭스).
    # =========================================================================

    # ---- ka10027 flu_rt — 단건 + Bulk ----
    @asynccontextmanager
    async def _ingest_flu_rt_single_factory(
        alias: str,
    ) -> AsyncIterator[IngestFluRtUpperUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            rkinfo = KiwoomRkInfoClient(kiwoom_client)
            async with sessionmaker() as session:
                yield IngestFluRtUpperUseCase(
                    session=session,
                    rkinfo_client=rkinfo,
                )
                await session.commit()
        finally:
            await kiwoom_client.close()

    @asynccontextmanager
    async def _ingest_flu_rt_bulk_factory(
        alias: str,
    ) -> AsyncIterator[IngestFluRtUpperBulkUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            rkinfo = KiwoomRkInfoClient(kiwoom_client)
            async with sessionmaker() as session:
                single = IngestFluRtUpperUseCase(
                    session=session,
                    rkinfo_client=rkinfo,
                )
                yield IngestFluRtUpperBulkUseCase(
                    session=session,
                    single_use_case=single,
                )
                await session.commit()
        finally:
            await kiwoom_client.close()

    # ---- ka10030 today_volume — 단건 + Bulk ----
    @asynccontextmanager
    async def _ingest_today_volume_single_factory(
        alias: str,
    ) -> AsyncIterator[IngestTodayVolumeUpperUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            rkinfo = KiwoomRkInfoClient(kiwoom_client)
            async with sessionmaker() as session:
                yield IngestTodayVolumeUpperUseCase(
                    session=session,
                    rkinfo_client=rkinfo,
                )
                await session.commit()
        finally:
            await kiwoom_client.close()

    @asynccontextmanager
    async def _ingest_today_volume_bulk_factory(
        alias: str,
    ) -> AsyncIterator[IngestTodayVolumeUpperBulkUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            rkinfo = KiwoomRkInfoClient(kiwoom_client)
            async with sessionmaker() as session:
                single = IngestTodayVolumeUpperUseCase(
                    session=session,
                    rkinfo_client=rkinfo,
                )
                yield IngestTodayVolumeUpperBulkUseCase(
                    session=session,
                    single_use_case=single,
                )
                await session.commit()
        finally:
            await kiwoom_client.close()

    # ---- ka10031 pred_volume — 단건 + Bulk ----
    @asynccontextmanager
    async def _ingest_pred_volume_single_factory(
        alias: str,
    ) -> AsyncIterator[IngestPredVolumeUpperUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            rkinfo = KiwoomRkInfoClient(kiwoom_client)
            async with sessionmaker() as session:
                yield IngestPredVolumeUpperUseCase(
                    session=session,
                    rkinfo_client=rkinfo,
                )
                await session.commit()
        finally:
            await kiwoom_client.close()

    @asynccontextmanager
    async def _ingest_pred_volume_bulk_factory(
        alias: str,
    ) -> AsyncIterator[IngestPredVolumeUpperBulkUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            rkinfo = KiwoomRkInfoClient(kiwoom_client)
            async with sessionmaker() as session:
                single = IngestPredVolumeUpperUseCase(
                    session=session,
                    rkinfo_client=rkinfo,
                )
                yield IngestPredVolumeUpperBulkUseCase(
                    session=session,
                    single_use_case=single,
                )
                await session.commit()
        finally:
            await kiwoom_client.close()

    # ---- ka10032 trade_amount — 단건 + Bulk ----
    @asynccontextmanager
    async def _ingest_trade_amount_single_factory(
        alias: str,
    ) -> AsyncIterator[IngestTradeAmountUpperUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            rkinfo = KiwoomRkInfoClient(kiwoom_client)
            async with sessionmaker() as session:
                yield IngestTradeAmountUpperUseCase(
                    session=session,
                    rkinfo_client=rkinfo,
                )
                await session.commit()
        finally:
            await kiwoom_client.close()

    @asynccontextmanager
    async def _ingest_trade_amount_bulk_factory(
        alias: str,
    ) -> AsyncIterator[IngestTradeAmountUpperBulkUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            rkinfo = KiwoomRkInfoClient(kiwoom_client)
            async with sessionmaker() as session:
                single = IngestTradeAmountUpperUseCase(
                    session=session,
                    rkinfo_client=rkinfo,
                )
                yield IngestTradeAmountUpperBulkUseCase(
                    session=session,
                    single_use_case=single,
                )
                await session.commit()
        finally:
            await kiwoom_client.close()

    # ---- ka10023 volume_sdnin — 단건 + Bulk ----
    @asynccontextmanager
    async def _ingest_volume_sdnin_single_factory(
        alias: str,
    ) -> AsyncIterator[IngestVolumeSdninUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            rkinfo = KiwoomRkInfoClient(kiwoom_client)
            async with sessionmaker() as session:
                yield IngestVolumeSdninUseCase(
                    session=session,
                    rkinfo_client=rkinfo,
                )
                await session.commit()
        finally:
            await kiwoom_client.close()

    @asynccontextmanager
    async def _ingest_volume_sdnin_bulk_factory(
        alias: str,
    ) -> AsyncIterator[IngestVolumeSdninBulkUseCase]:
        async def _token_provider() -> str:
            issued = await manager.get(alias=alias)
            return issued.token

        base_url = settings.kiwoom_base_url_prod
        kiwoom_client = KiwoomClient(
            base_url=base_url,
            token_provider=_token_provider,
            timeout_seconds=settings.kiwoom_request_timeout_seconds,
            min_request_interval_seconds=settings.kiwoom_min_request_interval_seconds,
            concurrent_requests=settings.kiwoom_concurrent_requests,
        )
        try:
            rkinfo = KiwoomRkInfoClient(kiwoom_client)
            async with sessionmaker() as session:
                single = IngestVolumeSdninUseCase(
                    session=session,
                    rkinfo_client=rkinfo,
                )
                yield IngestVolumeSdninBulkUseCase(
                    session=session,
                    single_use_case=single,
                )
                await session.commit()
        finally:
            await kiwoom_client.close()

    # 10 setter — 5 단건 + 5 Bulk
    set_ingest_flu_rt_factory(_ingest_flu_rt_single_factory)
    set_ingest_flu_rt_bulk_factory(_ingest_flu_rt_bulk_factory)
    set_ingest_today_volume_factory(_ingest_today_volume_single_factory)
    set_ingest_today_volume_bulk_factory(_ingest_today_volume_bulk_factory)
    set_ingest_pred_volume_factory(_ingest_pred_volume_single_factory)
    set_ingest_pred_volume_bulk_factory(_ingest_pred_volume_bulk_factory)
    set_ingest_trade_amount_factory(_ingest_trade_amount_single_factory)
    set_ingest_trade_amount_bulk_factory(_ingest_trade_amount_bulk_factory)
    set_ingest_volume_sdnin_factory(_ingest_volume_sdnin_single_factory)
    set_ingest_volume_sdnin_bulk_factory(_ingest_volume_sdnin_bulk_factory)

    # A3-γ: SectorSyncScheduler — settings.scheduler_enabled=True 일 때만 실제 cron 등록.
    # alias fail-fast 검증은 lifespan 진입 직후로 이동 (B-γ-2 2R H-1) — set_*_factory 후
    # raise 시 cleanup 우회 차단.
    scheduler = SectorSyncScheduler(
        factory=_sync_sector_factory,
        alias=settings.scheduler_sector_sync_alias,
        enabled=settings.scheduler_enabled,
    )
    scheduler.start()

    stock_scheduler = StockMasterScheduler(
        factory=_sync_stock_factory,
        alias=settings.scheduler_stock_sync_alias,
        enabled=settings.scheduler_enabled,
    )
    stock_scheduler.start()

    fundamental_scheduler = StockFundamentalScheduler(
        factory=_sync_fundamental_factory,
        alias=settings.scheduler_fundamental_sync_alias,
        enabled=settings.scheduler_enabled,
    )
    fundamental_scheduler.start()

    ohlcv_scheduler = OhlcvDailyScheduler(
        factory=_ingest_ohlcv_factory,
        alias=settings.scheduler_ohlcv_daily_sync_alias,
        enabled=settings.scheduler_enabled,
    )
    ohlcv_scheduler.start()

    daily_flow_scheduler = DailyFlowScheduler(
        factory=_ingest_daily_flow_factory,
        alias=settings.scheduler_daily_flow_sync_alias,
        enabled=settings.scheduler_enabled,
    )
    daily_flow_scheduler.start()

    weekly_ohlcv_scheduler = WeeklyOhlcvScheduler(
        factory=_ingest_periodic_ohlcv_factory,
        alias=settings.scheduler_weekly_ohlcv_sync_alias,
        enabled=settings.scheduler_enabled,
    )
    weekly_ohlcv_scheduler.start()

    monthly_ohlcv_scheduler = MonthlyOhlcvScheduler(
        factory=_ingest_periodic_ohlcv_factory,
        alias=settings.scheduler_monthly_ohlcv_sync_alias,
        enabled=settings.scheduler_enabled,
    )
    monthly_ohlcv_scheduler.start()

    yearly_ohlcv_scheduler = YearlyOhlcvScheduler(
        factory=_ingest_periodic_ohlcv_factory,
        alias=settings.scheduler_yearly_ohlcv_sync_alias,
        enabled=settings.scheduler_enabled,
    )
    yearly_ohlcv_scheduler.start()

    # D-1: SectorDailyOhlcvScheduler — mon-fri 07:00 KST. Bulk factory 사용 (active sector iterate).
    sector_daily_scheduler = SectorDailyOhlcvScheduler(
        factory=_ingest_sector_daily_bulk_factory,
        alias=settings.scheduler_sector_daily_sync_alias,
        enabled=settings.scheduler_enabled,
    )
    sector_daily_scheduler.start()

    # Phase E: ShortSelling / LendingMarket / LendingStock schedulers — mon-fri KST 07:30 / 07:45 / 08:00.
    # 각 scheduler 의 개별 enabled env 가 False 면 settings.scheduler_enabled 와 AND 결합.
    short_selling_scheduler = ShortSellingScheduler(
        factory=_ingest_short_selling_bulk_factory,
        alias=settings.scheduler_short_selling_sync_alias,
        enabled=settings.scheduler_enabled and settings.scheduler_short_selling_sync_enabled,
    )
    short_selling_scheduler.start()

    lending_market_scheduler = LendingMarketScheduler(
        factory=_ingest_lending_market_factory,
        alias=settings.scheduler_lending_market_sync_alias,
        enabled=settings.scheduler_enabled and settings.scheduler_lending_market_sync_enabled,
    )
    lending_market_scheduler.start()

    lending_stock_scheduler = LendingStockScheduler(
        factory=_ingest_lending_stock_bulk_factory,
        alias=settings.scheduler_lending_stock_sync_alias,
        enabled=settings.scheduler_enabled and settings.scheduler_lending_stock_sync_enabled,
    )
    lending_stock_scheduler.start()

    # Phase F-4: 5 ranking scheduler — mon-fri KST 19:30/35/40/45/50 (D-6 5분 chain sequential).
    # 각 scheduler 의 개별 enabled env 가 False 면 settings.scheduler_enabled 와 AND 결합.
    flu_rt_ranking_scheduler = FluRtRankingScheduler(
        factory=_ingest_flu_rt_bulk_factory,
        alias=settings.scheduler_flu_rt_ranking_sync_alias,
        enabled=settings.scheduler_enabled
        and settings.scheduler_flu_rt_ranking_sync_enabled,
    )
    flu_rt_ranking_scheduler.start()

    today_volume_ranking_scheduler = TodayVolumeRankingScheduler(
        factory=_ingest_today_volume_bulk_factory,
        alias=settings.scheduler_today_volume_ranking_sync_alias,
        enabled=settings.scheduler_enabled
        and settings.scheduler_today_volume_ranking_sync_enabled,
    )
    today_volume_ranking_scheduler.start()

    pred_volume_ranking_scheduler = PredVolumeRankingScheduler(
        factory=_ingest_pred_volume_bulk_factory,
        alias=settings.scheduler_pred_volume_ranking_sync_alias,
        enabled=settings.scheduler_enabled
        and settings.scheduler_pred_volume_ranking_sync_enabled,
    )
    pred_volume_ranking_scheduler.start()

    trde_prica_ranking_scheduler = TrdePricaRankingScheduler(
        factory=_ingest_trade_amount_bulk_factory,
        alias=settings.scheduler_trade_amount_ranking_sync_alias,
        enabled=settings.scheduler_enabled
        and settings.scheduler_trade_amount_ranking_sync_enabled,
    )
    trde_prica_ranking_scheduler.start()

    volume_sdnin_ranking_scheduler = VolumeSdninRankingScheduler(
        factory=_ingest_volume_sdnin_bulk_factory,
        alias=settings.scheduler_volume_sdnin_ranking_sync_alias,
        enabled=settings.scheduler_enabled
        and settings.scheduler_volume_sdnin_ranking_sync_enabled,
    )
    volume_sdnin_ranking_scheduler.start()

    # 인시던트 진단용 — /admin/scheduler/diag 가 17 scheduler 의 _eventloop / next_run_time /
    # _timeout 상태를 노출. (12 Phase A~E + 5 Phase F-4 ranking)
    _app.state.schedulers = {
        "sector_sync": scheduler,
        "stock_master": stock_scheduler,
        "stock_fundamental": fundamental_scheduler,
        "ohlcv_daily": ohlcv_scheduler,
        "daily_flow": daily_flow_scheduler,
        "weekly_ohlcv": weekly_ohlcv_scheduler,
        "monthly_ohlcv": monthly_ohlcv_scheduler,
        "yearly_ohlcv": yearly_ohlcv_scheduler,
        "sector_daily": sector_daily_scheduler,
        "short_selling": short_selling_scheduler,
        "lending_market": lending_market_scheduler,
        "lending_stock": lending_stock_scheduler,
        "flu_rt_ranking": flu_rt_ranking_scheduler,
        "today_volume_ranking": today_volume_ranking_scheduler,
        "pred_volume_ranking": pred_volume_ranking_scheduler,
        "trde_prica_ranking": trde_prica_ranking_scheduler,
        "volume_sdnin_ranking": volume_sdnin_ranking_scheduler,
    }

    try:
        yield
    finally:
        # A3-γ / B-α / B-γ-2 / C-1β / C-2β / C-3β / C-4 / D-1 / Phase E / F-4: scheduler 먼저 정지 — 실행 중 cron
        # job 의 KiwoomClient 호출이 graceful token revoke 와 충돌하지 않도록 보장.
        # Phase F-4 ranking schedulers 먼저 (가장 늦은 cron 19:50 부터 역순).
        volume_sdnin_ranking_scheduler.shutdown(wait=True)
        trde_prica_ranking_scheduler.shutdown(wait=True)
        pred_volume_ranking_scheduler.shutdown(wait=True)
        today_volume_ranking_scheduler.shutdown(wait=True)
        flu_rt_ranking_scheduler.shutdown(wait=True)
        lending_stock_scheduler.shutdown(wait=True)
        lending_market_scheduler.shutdown(wait=True)
        short_selling_scheduler.shutdown(wait=True)
        sector_daily_scheduler.shutdown(wait=True)
        yearly_ohlcv_scheduler.shutdown(wait=True)
        monthly_ohlcv_scheduler.shutdown(wait=True)
        weekly_ohlcv_scheduler.shutdown(wait=True)
        daily_flow_scheduler.shutdown(wait=True)
        ohlcv_scheduler.shutdown(wait=True)
        fundamental_scheduler.shutdown(wait=True)
        stock_scheduler.shutdown(wait=True)
        scheduler.shutdown(wait=True)

        # 1R 2b M4 / D-1 / Phase E / F-4: factory 싱글톤 unset — close 후 stale factory 가 라우터에
        # 노출되지 않도록 fail-closed 강화. teardown 직전 신규 요청은 503 (factory 미초기화) 반환.
        # Phase F-4 — 5 단건 + 5 Bulk = 10 factory reset
        reset_ingest_volume_sdnin_factory()
        reset_ingest_volume_sdnin_bulk_factory()
        reset_ingest_trade_amount_factory()
        reset_ingest_trade_amount_bulk_factory()
        reset_ingest_pred_volume_factory()
        reset_ingest_pred_volume_bulk_factory()
        reset_ingest_today_volume_factory()
        reset_ingest_today_volume_bulk_factory()
        reset_ingest_flu_rt_factory()
        reset_ingest_flu_rt_bulk_factory()
        reset_ingest_lending_stock_bulk_factory()
        reset_ingest_lending_stock_single_factory()
        reset_ingest_lending_market_factory()
        reset_ingest_short_selling_bulk_factory()
        reset_ingest_short_selling_single_factory()
        reset_ingest_sector_single_factory()
        reset_ingest_sector_daily_factory()
        reset_ingest_periodic_ohlcv_factory()
        reset_ingest_daily_flow_factory()
        reset_ingest_ohlcv_factory()
        reset_sync_fundamental_factory()
        reset_lookup_stock_factory()
        reset_sync_stock_factory()
        reset_sync_sector_factory()

        # H-3 적대적 리뷰: revoke 실패/hang/cancel 와 무관하게 engine.dispose() 도달 보장
        try:
            await asyncio.wait_for(
                revoke_all_aliases_best_effort(manager=manager, revoke_use_case=revoke_uc),
                timeout=SHUTDOWN_REVOKE_TIMEOUT_SECONDS,
            )
        except (TimeoutError, asyncio.TimeoutError):  # noqa: UP041 — Py3.11+ alias
            logger.warning(
                "graceful shutdown 일괄 폐기 timeout — %s초 초과, 잔여 alias 미폐기",
                SHUTDOWN_REVOKE_TIMEOUT_SECONDS,
            )
            manager.invalidate_all()
        except asyncio.CancelledError:
            logger.warning("graceful shutdown cancelled — 잔여 alias 미폐기")
            manager.invalidate_all()
            raise
        except Exception as exc:  # noqa: BLE001 — shutdown 은 모든 예외 swallow
            logger.warning("graceful shutdown 일괄 폐기 실패: %s", type(exc).__name__)
            manager.invalidate_all()
        finally:
            await get_engine().dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        lifespan=_lifespan,
    )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # 민감 경로는 input/ctx 필드 제거 — 토큰 평문 echo 차단 (C-1 적대적 리뷰)
        if request.url.path in _SENSITIVE_VALIDATION_PATHS:
            return JSONResponse(
                status_code=422,
                content={"detail": _scrubbed_validation_error(exc)},
            )
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    app.include_router(auth_router)
    app.include_router(sectors_router)
    app.include_router(stocks_router)
    app.include_router(fundamentals_router)
    app.include_router(ohlcv_router)
    app.include_router(ohlcv_periodic_router)
    app.include_router(sector_ohlcv_router)
    app.include_router(daily_flow_router)
    app.include_router(short_selling_router)
    app.include_router(lending_router)
    app.include_router(rankings_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(
        "/admin/scheduler/diag",
        dependencies=[Depends(require_admin_key)],
    )
    async def scheduler_diag(request: Request) -> dict[str, object]:
        """12 scheduler 인스턴스의 _eventloop / _timeout / next_run_time 상태 dump.

        9 scheduler dead (2026-05-13 06:00 KST 첫 cron 발화 누락) 원인 추적용. 메인
        loop id 와 각 인스턴스의 _eventloop id 비교 → 동일 루프 잡았는지 검증.
        timeout.when() 의 monotonic 값 + main_loop.time() 과의 차이 → cron 발화까지의
        남은 시간 검증.
        """
        main_loop = asyncio.get_running_loop()
        schedulers_map: dict[str, object] = getattr(request.app.state, "schedulers", {})
        items: list[dict[str, object]] = []
        for name, sched in schedulers_map.items():
            inner = sched._scheduler  # type: ignore[attr-defined]  # 진단 전용 — private 직접 접근
            loop = inner._eventloop
            timeout = getattr(inner, "_timeout", None)
            timeout_info: dict[str, object] | None
            if timeout is None:
                timeout_info = None
            else:
                try:
                    when = timeout.when()
                    timeout_info = {
                        "monotonic_when": when,
                        "delta_seconds": when - main_loop.time(),
                        "cancelled": timeout.cancelled(),
                    }
                except Exception as exc:  # noqa: BLE001 — 진단용 fallback
                    timeout_info = {"error": f"{type(exc).__name__}: {exc}"}
            items.append(
                {
                    "name": name,
                    "enabled_flag": sched._enabled,  # type: ignore[attr-defined]
                    "started_flag": sched._started,  # type: ignore[attr-defined]
                    "scheduler_running": inner.running,
                    "eventloop_id": id(loop) if loop else None,
                    "eventloop_running": loop.is_running() if loop else None,
                    "eventloop_closed": loop.is_closed() if loop else None,
                    "eventloop_is_main": (id(loop) == id(main_loop)) if loop else None,
                    "timeout": timeout_info,
                    "jobs": [
                        {
                            "id": j.id,
                            "next_run_time": j.next_run_time.isoformat() if j.next_run_time else None,
                            "pending": j.pending,
                            "trigger": str(j.trigger),
                            # 2b 2R M-2 — misfire_grace_time 노출 (ADR § 42.5 옵션 C 운영 가시화)
                            "misfire_grace_time": j.misfire_grace_time,
                        }
                        for j in inner.get_jobs()
                    ],
                }
            )
        return {
            "now_monotonic": main_loop.time(),
            "main_loop_id": id(main_loop),
            "main_loop_running": main_loop.is_running(),
            "schedulers": items,
        }

    return app


app = create_app()
