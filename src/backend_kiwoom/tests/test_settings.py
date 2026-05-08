"""Pydantic v2 BaseSettings 검증 — backend_kiwoom Settings.

검증:
- 기본값 세팅
- env override
- Literal 검증 (kiwoom_default_env: prod/mock)
- 값 범위 검증 (concurrent_requests, request_interval)
- get_settings() 싱글톤 (lru_cache)
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config.settings import Settings, get_settings

_KIWOOM_ENV_VARS = (
    "APP_NAME",
    "APP_ENV",
    "PORT",
    "LOG_LEVEL",
    "KIWOOM_DEFAULT_ENV",
    "KIWOOM_REQUEST_TIMEOUT_SECONDS",
    "KIWOOM_MIN_REQUEST_INTERVAL_SECONDS",
    "KIWOOM_CONCURRENT_REQUESTS",
    "NXT_COLLECTION_ENABLED",
    "BACKFILL_MAX_DAYS",
    "BACKFILL_CONCURRENCY",
    "SCHEDULER_ENABLED",
    "ADMIN_API_KEY",
    "KIWOOM_CREDENTIAL_MASTER_KEY",
)


def _isolate_kiwoom_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """conftest 가 주입한 KIWOOM_* 환경변수를 격리해 default 검증."""
    for name in _KIWOOM_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_settings_default_values(monkeypatch: pytest.MonkeyPatch) -> None:
    _isolate_kiwoom_env(monkeypatch)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.app_name == "ted-kiwoom-backend"
    assert s.kiwoom_base_url_prod == "https://api.kiwoom.com"
    assert s.kiwoom_base_url_mock == "https://mockapi.kiwoom.com"
    assert s.kiwoom_default_env == "mock"
    assert s.kiwoom_request_timeout_seconds == 15.0
    assert s.kiwoom_min_request_interval_seconds == 0.25
    assert s.kiwoom_concurrent_requests == 4
    assert s.nxt_collection_enabled is False  # C-1β: 디폴트 OFF (사용자 결정)
    assert s.backfill_max_days == 1095
    assert s.scheduler_enabled is False
    assert s.log_level == "INFO"
    assert s.kiwoom_credential_master_key == ""


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    _isolate_kiwoom_env(monkeypatch)
    monkeypatch.setenv("KIWOOM_DEFAULT_ENV", "prod")
    monkeypatch.setenv("KIWOOM_CONCURRENT_REQUESTS", "8")
    monkeypatch.setenv("NXT_COLLECTION_ENABLED", "true")
    monkeypatch.setenv("KIWOOM_CREDENTIAL_MASTER_KEY", "x" * 44)  # Fernet 키 길이

    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.kiwoom_default_env == "prod"
    assert s.kiwoom_concurrent_requests == 8
    assert s.nxt_collection_enabled is True
    assert s.kiwoom_credential_master_key == "x" * 44


def test_settings_kiwoom_default_env_literal_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """kiwoom_default_env 는 'prod' | 'mock' 만 허용."""
    _isolate_kiwoom_env(monkeypatch)
    monkeypatch.setenv("KIWOOM_DEFAULT_ENV", "real")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_settings_log_level_literal_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """log_level Literal — 오타 방어."""
    _isolate_kiwoom_env(monkeypatch)
    monkeypatch.setenv("LOG_LEVEL", "BOGUS")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_settings_concurrent_requests_must_be_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    _isolate_kiwoom_env(monkeypatch)
    monkeypatch.setenv("KIWOOM_CONCURRENT_REQUESTS", "0")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_settings_min_interval_must_be_non_negative(monkeypatch: pytest.MonkeyPatch) -> None:
    _isolate_kiwoom_env(monkeypatch)
    monkeypatch.setenv("KIWOOM_MIN_REQUEST_INTERVAL_SECONDS", "-0.5")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_settings_database_url_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _isolate_kiwoom_env(monkeypatch)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert "asyncpg" in s.database_url
    assert "kiwoom" in s.database_url.lower()


def test_get_settings_caches_singleton() -> None:
    """get_settings() 가 lru_cache 로 같은 인스턴스 반환."""
    get_settings.cache_clear()
    a = get_settings()
    b = get_settings()
    assert a is b


def test_settings_extra_env_vars_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    """extra='ignore' — 알려지지 않은 env var 는 silent skip."""
    _isolate_kiwoom_env(monkeypatch)
    monkeypatch.setenv("UNRELATED_ENV_VAR", "value")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert not hasattr(s, "unrelated_env_var")
