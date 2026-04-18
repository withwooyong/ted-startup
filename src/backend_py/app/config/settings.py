from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 전역 설정. 값 소스는 환경변수 우선, 없으면 .env 순."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.prod"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "ted-signal-backend"
    app_env: str = Field(default="local", description="local | dev | prod")
    port: int = 8000
    # 화이트리스트 방식 — 빈 값이면 CORS 미들웨어는 아무 출처도 허용하지 않음.
    # 로컬 개발 시 .env에 CORS_ALLOW_ORIGINS=http://localhost:3000 형태로 명시.
    cors_allow_origins: list[str] = Field(default_factory=list)

    # ---- Database ----
    # 기본값은 로컬 docker-compose 의 PostgreSQL(5432) 접속. 운영 시 env 로 오버라이드.
    database_url: str = Field(
        default="postgresql+asyncpg://signal:signal@localhost:5432/signal_db",
        description="SQLAlchemy async DSN — asyncpg 드라이버 전제",
    )
    database_echo: bool = Field(default=False, description="SQL 에코(디버그 용)")
    database_pool_size: int = Field(default=5)
    database_max_overflow: int = Field(default=10)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
