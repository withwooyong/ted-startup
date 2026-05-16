"""backend_kiwoom 전역 설정 — Pydantic v2 BaseSettings.

값 소스 우선순위: 환경변수 → .env → .env.prod. case-insensitive.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.prod"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- App ----
    app_name: str = "ted-kiwoom-backend"
    app_env: str = Field(default="local", description="local | dev | prod")
    port: int = Field(default=8001)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")
    cors_allow_origins: list[str] = Field(default_factory=list)

    # ---- Database ----
    kiwoom_database_url: str = Field(
        default="postgresql+asyncpg://kiwoom:kiwoom@localhost:5432/kiwoom_db",
        description=(
            "SQLAlchemy async DSN (asyncpg). Alembic 은 psycopg2 로 자동 치환. "
            "env: KIWOOM_DATABASE_URL — 다른 프로젝트의 DATABASE_URL 과 격리"
        ),
    )
    database_echo: bool = Field(default=False)
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=10, ge=0, le=50)

    # ---- Kiwoom OpenAPI ----
    kiwoom_base_url_prod: str = Field(default="https://api.kiwoom.com")
    kiwoom_base_url_mock: str = Field(
        default="https://mockapi.kiwoom.com",
        description="모의투자 도메인 — KRX 만 지원, NXT 데이터는 prod 필수",
    )
    kiwoom_default_env: Literal["prod", "mock"] = Field(
        default="mock", description="운영 배포만 'prod' — 실수 운영 호출 차단"
    )
    kiwoom_request_timeout_seconds: float = Field(default=15.0, gt=0.0)
    kiwoom_min_request_interval_seconds: float = Field(
        default=0.25,
        ge=0.0,
        description="키움 공식 RPS 권장 5회/초의 안전 마진 (250ms)",
    )
    kiwoom_concurrent_requests: int = Field(default=4, gt=0, le=10, description="asyncio.Semaphore 동시 호출 수")

    # ---- 자격증명 (Fernet 마스터키) ----
    kiwoom_credential_master_key: str = Field(
        default="",
        description=(
            "키움 자격증명(appkey/secretkey) 대칭 암호화 마스터키. Fernet `generate_key()` 출력 "
            "(32B base64). 운영 환경에서 빈 값이면 KiwoomCredentialCipher 초기화 시 "
            "MasterKeyNotConfiguredError 로 fail-fast."
        ),
    )

    # ---- NXT 수집 ----
    nxt_collection_enabled: bool = Field(
        default=False,
        description=(
            "False 디폴트 (사용자 결정, C-1β) — 운영 전환 전 안전판. KRX 만 수집. "
            "True 로 전환 시에도 stock.nxt_enable 별도 게이팅"
        ),
    )

    # ---- 백필 ----
    backfill_max_days: int = Field(default=1095, ge=1, le=3650, description="과거 N일 한도 (기본 3년)")
    backfill_concurrency: int = Field(default=2, ge=1, le=10)

    # ---- Admin ----
    admin_api_key: str = Field(
        default="",
        description="X-API-Key 헤더 검증용. 빈 값이면 admin 라우터 모두 401 fail-closed",
    )

    # ---- Scheduler ----
    scheduler_enabled: bool = Field(default=False, description="APScheduler 자동 기동 (운영만 True)")
    scheduler_sector_sync_alias: str = Field(
        default="",
        description=(
            "주간 sector sync cron job 이 사용할 키움 자격증명 alias. "
            "scheduler_enabled=True 인데 빈 값이면 lifespan 에서 fail-fast (운영 실수 방어)."
        ),
    )
    scheduler_stock_sync_alias: str = Field(
        default="",
        description=(
            "일간 stock master sync cron job 이 사용할 키움 자격증명 alias (B-α 추가). "
            "scheduler_enabled=True 인데 빈 값이면 lifespan 에서 fail-fast."
        ),
    )
    scheduler_fundamental_sync_alias: str = Field(
        default="",
        description=(
            "일간 stock fundamental sync cron job 이 사용할 키움 자격증명 alias (B-γ-2 추가). "
            "scheduler_enabled=True 인데 빈 값이면 lifespan 에서 fail-fast."
        ),
    )
    scheduler_ohlcv_daily_sync_alias: str = Field(
        default="",
        description=(
            "일간 OHLCV sync cron job 이 사용할 키움 자격증명 alias (C-1β 추가). "
            "scheduler_enabled=True 인데 빈 값이면 lifespan 에서 fail-fast."
        ),
    )
    scheduler_daily_flow_sync_alias: str = Field(
        default="",
        description=(
            "일간 daily flow (ka10086) sync cron job 이 사용할 키움 자격증명 alias (C-2β 추가). "
            "scheduler_enabled=True 인데 빈 값이면 lifespan 에서 fail-fast."
        ),
    )
    scheduler_weekly_ohlcv_sync_alias: str = Field(
        default="",
        description=(
            "주봉 OHLCV (ka10082) sync cron job 이 사용할 키움 자격증명 alias (C-3β 추가). "
            "scheduler_enabled=True 인데 빈 값이면 lifespan 에서 fail-fast."
        ),
    )
    scheduler_monthly_ohlcv_sync_alias: str = Field(
        default="",
        description=(
            "월봉 OHLCV (ka10083) sync cron job 이 사용할 키움 자격증명 alias (C-3β 추가). "
            "scheduler_enabled=True 인데 빈 값이면 lifespan 에서 fail-fast."
        ),
    )
    scheduler_yearly_ohlcv_sync_alias: str = Field(
        default="",
        description=(
            "년봉 OHLCV (ka10094) sync cron job 이 사용할 키움 자격증명 alias (C-4 추가). "
            "scheduler_enabled=True 인데 빈 값이면 lifespan 에서 fail-fast."
        ),
    )
    scheduler_sector_daily_sync_alias: str = Field(
        default="",
        description=(
            "일간 sector daily OHLCV (ka20006) sync cron job 이 사용할 키움 자격증명 alias (D-1 추가). "
            "scheduler_enabled=True 인데 빈 값이면 lifespan 에서 fail-fast (운영 실수 방어)."
        ),
    )

    # ---- Scheduler — Phase E (ka10014 / ka10068 / ka20068 매도 측 시그널 wave) ----
    scheduler_short_selling_sync_enabled: bool = Field(
        default=True,
        description=(
            "공매도 추이 (ka10014) sync cron job 활성 여부 (Phase E 추가). "
            "scheduler_enabled=True 가 전체 게이트 — 본 env 가 False 면 short_selling job 미등록 "
            "(다른 scheduler 는 영향 없음). cron: mon-fri KST 07:30."
        ),
    )
    scheduler_short_selling_sync_alias: str = Field(
        default="",
        description=(
            "공매도 추이 (ka10014) sync cron job 이 사용할 키움 자격증명 alias (Phase E 추가). "
            "scheduler_enabled=True 인데 빈 값이면 lifespan 에서 fail-fast (운영 실수 방어)."
        ),
    )
    scheduler_lending_market_sync_enabled: bool = Field(
        default=True,
        description=(
            "시장 대차거래 (ka10068) sync cron job 활성 여부 (Phase E 추가). "
            "cron: mon-fri KST 07:45."
        ),
    )
    scheduler_lending_market_sync_alias: str = Field(
        default="",
        description=(
            "시장 대차거래 (ka10068) sync cron job 이 사용할 키움 자격증명 alias (Phase E 추가). "
            "scheduler_enabled=True 인데 빈 값이면 lifespan 에서 fail-fast."
        ),
    )
    scheduler_lending_stock_sync_enabled: bool = Field(
        default=True,
        description=(
            "종목 대차거래 (ka20068) sync cron job 활성 여부 (Phase E 추가). "
            "cron: mon-fri KST 08:00 (active 3000 종목 bulk). misfire_grace_time=5400s (90분)."
        ),
    )
    scheduler_lending_stock_sync_alias: str = Field(
        default="",
        description=(
            "종목 대차거래 (ka20068) sync cron job 이 사용할 키움 자격증명 alias (Phase E 추가). "
            "scheduler_enabled=True 인데 빈 값이면 lifespan 에서 fail-fast."
        ),
    )

    # ---- Scheduler — Phase F-4 (5 ranking endpoint ka10027/30/31/32/23) ----
    # 결정: F-4 Step 2 fix C-2 — Phase E 의 sync_enabled + sync_alias 패턴 1:1 미러.
    # cron: mon-fri KST 19:30/35/40/45/50 (D-6 5분 chain). misfire_grace_time=21600s.
    scheduler_flu_rt_ranking_sync_enabled: bool = Field(
        default=True,
        description=(
            "ka10027 등락률 ranking sync cron job 활성 여부 (Phase F-4 추가). "
            "scheduler_enabled=True 가 전체 게이트 — 본 env 가 False 면 미등록. cron: mon-fri KST 19:30."
        ),
    )
    scheduler_flu_rt_ranking_sync_alias: str = Field(
        default="",
        description=(
            "ka10027 등락률 ranking sync cron job 의 키움 자격증명 alias (Phase F-4 추가). "
            "scheduler_enabled=True + scheduler_flu_rt_ranking_sync_enabled=True 인데 "
            "빈 값이면 lifespan 에서 fail-fast (운영 실수 방어)."
        ),
    )
    scheduler_today_volume_ranking_sync_enabled: bool = Field(
        default=True,
        description=(
            "ka10030 당일 거래량 ranking sync cron job 활성 여부 (Phase F-4 추가). cron: mon-fri KST 19:35."
        ),
    )
    scheduler_today_volume_ranking_sync_alias: str = Field(
        default="",
        description=(
            "ka10030 당일 거래량 ranking sync cron job 의 키움 자격증명 alias (Phase F-4 추가). "
            "scheduler_enabled=True + 본 enabled=True 인데 빈 값이면 lifespan 에서 fail-fast."
        ),
    )
    scheduler_pred_volume_ranking_sync_enabled: bool = Field(
        default=True,
        description=(
            "ka10031 전일 거래량 ranking sync cron job 활성 여부 (Phase F-4 추가). cron: mon-fri KST 19:40."
        ),
    )
    scheduler_pred_volume_ranking_sync_alias: str = Field(
        default="",
        description=(
            "ka10031 전일 거래량 ranking sync cron job 의 키움 자격증명 alias (Phase F-4 추가). "
            "scheduler_enabled=True + 본 enabled=True 인데 빈 값이면 lifespan 에서 fail-fast."
        ),
    )
    scheduler_trade_amount_ranking_sync_enabled: bool = Field(
        default=True,
        description=(
            "ka10032 거래대금 ranking sync cron job 활성 여부 (Phase F-4 추가). cron: mon-fri KST 19:45."
        ),
    )
    scheduler_trade_amount_ranking_sync_alias: str = Field(
        default="",
        description=(
            "ka10032 거래대금 ranking sync cron job 의 키움 자격증명 alias (Phase F-4 추가). "
            "scheduler_enabled=True + 본 enabled=True 인데 빈 값이면 lifespan 에서 fail-fast."
        ),
    )
    scheduler_volume_sdnin_ranking_sync_enabled: bool = Field(
        default=True,
        description=(
            "ka10023 거래량 급증 ranking sync cron job 활성 여부 (Phase F-4 추가). cron: mon-fri KST 19:50."
        ),
    )
    scheduler_volume_sdnin_ranking_sync_alias: str = Field(
        default="",
        description=(
            "ka10023 거래량 급증 ranking sync cron job 의 키움 자격증명 alias (Phase F-4 추가). "
            "scheduler_enabled=True + 본 enabled=True 인데 빈 값이면 lifespan 에서 fail-fast."
        ),
    )

    # ---- Scheduler — Phase G (3 investor flow endpoint ka10058/10059/10131) ----
    # 결정: G-2 통일 — misfire_grace_time=21600 (6h). cron: mon-fri KST 20:00/20:30/21:00.
    # Phase F-4 사례 1:1 미러.
    scheduler_investor_daily_sync_enabled: bool = Field(
        default=True,
        description=(
            "ka10058 투자자별 일별 매매 종목 ranking sync cron 활성 여부 (Phase G). "
            "scheduler_enabled=True 가 전체 게이트. cron: mon-fri KST 20:00."
        ),
    )
    scheduler_investor_daily_sync_alias: str = Field(
        default="",
        description=(
            "ka10058 sync cron 의 키움 자격증명 alias (Phase G). "
            "scheduler_enabled=True + scheduler_investor_daily_sync_enabled=True 인데 "
            "빈 값이면 lifespan 에서 fail-fast."
        ),
    )
    scheduler_stock_investor_breakdown_sync_enabled: bool = Field(
        default=True,
        description=(
            "ka10059 종목별 wide breakdown sync cron 활성 여부 (Phase G). "
            "cron: mon-fri KST 20:30 (60분 sync 예상)."
        ),
    )
    scheduler_stock_investor_breakdown_sync_alias: str = Field(
        default="",
        description=(
            "ka10059 sync cron 의 키움 자격증명 alias (Phase G). 빈 값이면 fail-fast."
        ),
    )
    scheduler_frgn_orgn_continuous_sync_enabled: bool = Field(
        default=True,
        description=(
            "ka10131 기관/외국인 연속매매 sync cron 활성 여부 (Phase G). cron: mon-fri KST 21:00."
        ),
    )
    scheduler_frgn_orgn_continuous_sync_alias: str = Field(
        default="",
        description=(
            "ka10131 sync cron 의 키움 자격증명 alias (Phase G). 빈 값이면 fail-fast."
        ),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
