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
    database_url: str = Field(
        default="postgresql+asyncpg://kiwoom:kiwoom@localhost:5432/kiwoom_db",
        description="SQLAlchemy async DSN (asyncpg). Alembic 은 psycopg2 로 자동 치환.",
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
        default=True,
        description="False 면 KRX 만 수집 — 운영 전환 전 안전판",
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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
