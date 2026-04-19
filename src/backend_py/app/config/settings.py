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

    # ---- Rate Limiting (slowapi) ----
    # AI 리포트 엔드포인트 등 관리자 전용/고비용 경로에 적용. 관리자 키 단위 쿼터.
    # 기본값은 운영 보수적 — 정상 사용에 여유, 루프/오남용 방어.
    ai_report_rate_limit: str = Field(
        default="30/minute",
        description="AI 리포트 생성 엔드포인트 (POST /api/reports/{stock_code}) 제한",
    )

    # ---- Batch Scheduler ----
    # False 면 APScheduler 를 기동하지 않음(테스트·개발 환경 기본값).
    # 운영 배포 시에만 True 로 설정해 매일 KST 06:00 월~금 실행.
    scheduler_enabled: bool = Field(default=False, description="프로세스 부팅 시 배치 스케줄러 자동 기동 여부")
    scheduler_hour_kst: int = Field(default=6, ge=0, le=23, description="일일 실행 시각(KST 24h)")
    scheduler_minute_kst: int = Field(default=0, ge=0, le=59)

    # ---- OpenAI (AI 분석 리포트 — Plan B) ----
    # 플랜 §12 #9: mini(수집) + flagship(분석) + nano(리패키징) 3단 라우팅.
    # MVP 는 flagship 단독 호출만 필수. mini 는 web_search 활성 시만 호출, nano 는 기본 passthrough.
    openai_base_url: str = Field(default="https://api.openai.com/v1")
    openai_api_key: str = Field(default="", description="OpenAI API Key")
    openai_model_flagship: str = Field(
        default="gpt-4o",
        description="분석 레이어 — 1M 컨텍스트 가정. 실 배포 시 gpt-5.4 등으로 교체",
    )
    openai_model_collector: str = Field(
        default="gpt-4o-mini",
        description="Tier2 수집 — web_search 지원 모델",
    )
    openai_model_nano: str = Field(
        default="gpt-4o-mini",
        description="프론트 리패키징 — strict JSON 전환. MVP 에서 passthrough 로 사용",
    )
    openai_request_timeout_seconds: float = Field(default=60.0)

    # ---- AI Report (공통) ----
    ai_report_provider: str = Field(
        default="openai",
        description="현재 지원: openai. 추후 perplexity_claude 로 Plan A 전환",
    )
    ai_report_cache_hours: int = Field(
        default=24, ge=1, le=168, description="동일 (stock_code, report_date) 캐시 TTL"
    )
    ai_report_web_search_enabled: bool = Field(
        default=False,
        description="True 시 Tier2 web_search(mini) 호출. MVP 기본 False",
    )

    # ---- DART OpenAPI (금융감독원 공시 — Tier1 공식 재무 출처) ----
    dart_base_url: str = Field(
        default="https://opendart.fss.or.kr/api",
        description="DART OpenAPI Base URL",
    )
    dart_api_key: str = Field(default="", description="DART OpenAPI 인증키 (무료 발급)")
    dart_request_timeout_seconds: float = Field(default=15.0)

    # ---- KIS (한국투자증권) 모의투자 REST ----
    # MVP 는 모의 전용. 실거래 URL/키는 코드 레벨에서 진입 차단.
    kis_base_url_mock: str = Field(
        default="https://openapivts.koreainvestment.com:29443",
        description="KIS 모의투자 OpenAPI Base URL (실거래로 바꾸지 말 것)",
    )
    kis_app_key_mock: str = Field(default="", description="KIS 모의 APP Key")
    kis_app_secret_mock: str = Field(default="", description="KIS 모의 APP Secret")
    kis_account_no_mock: str = Field(
        default="",
        description="KIS 모의 계좌번호 — 10자리(CANO 8 + ACNT_PRDT_CD 2). 하이픈 허용",
    )
    kis_request_timeout_seconds: float = Field(default=15.0)
    kis_use_in_memory_mock: bool = Field(
        default=False,
        description=(
            "True 면 KisClient 가 내장 httpx.MockTransport 로 구동 — 외부 KIS 호출 없음. "
            "E2E/CI 에서 KIS sandbox rate limit(1분 1회) 회피용. 운영은 반드시 False."
        ),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
