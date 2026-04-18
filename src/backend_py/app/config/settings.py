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

    # ---- KRX (pykrx 로그인) ----
    # 값이 비어 있으면 인증 필요 엔드포인트(공매도/대차잔고)는 실패함.
    # 시가총액/OHLCV 류는 익명 접근 가능.
    krx_id: str = Field(default="", description="data.krx.co.kr 회원 ID")
    krx_pw: str = Field(default="", description="data.krx.co.kr 회원 비밀번호")
    krx_request_interval_seconds: float = Field(default=2.0, description="KRX 요청 간 최소 간격(초)")

    # ---- Telegram Bot ----
    # 둘 중 하나라도 비어 있으면 TelegramClient 는 no-op 으로 동작.
    telegram_bot_token: str = Field(default="", description="BotFather 발급 토큰")
    telegram_chat_id: str = Field(default="", description="수신 채팅/채널 ID")

    # ---- Admin ----
    # 관리자 API Key — /api/*/detect, /run, /collect, PUT /preferences 에 요구.
    # 값이 비어 있으면 모든 요청은 401 로 거부(fail-closed).
    admin_api_key: str = Field(default="", description="X-API-Key 헤더 검증용 고정 키(32+ 바이트)")

    # ---- Batch Scheduler ----
    # False 면 APScheduler 를 기동하지 않음(테스트·개발 환경 기본값).
    # 운영 배포 시에만 True 로 설정해 매일 KST 06:00 월~금 실행.
    scheduler_enabled: bool = Field(default=False, description="프로세스 부팅 시 배치 스케줄러 자동 기동 여부")
    scheduler_hour_kst: int = Field(default=6, ge=0, le=23, description="일일 실행 시각(KST 24h)")
    scheduler_minute_kst: int = Field(default=0, ge=0, le=59)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
