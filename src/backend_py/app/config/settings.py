from __future__ import annotations

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


def get_settings() -> Settings:
    return Settings()
