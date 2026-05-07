"""FastAPI 의존성 — admin guard + TokenManager singleton.

설계: endpoint-01-au10001.md § 7.1 / master.md § 6.5.

보안:
- `require_admin_key` — `hmac.compare_digest` 로 timing-safe 비교
- `admin_api_key` 미설정 (`""`) 시 fail-closed (401) — 운영 실수 방어
- `X-API-Key` 헤더 부재 시 401
"""

from __future__ import annotations

import hmac

from fastapi import Depends, Header, HTTPException, status

from app.application.service.token_service import TokenManager
from app.config.settings import Settings, get_settings


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


_token_manager_singleton: TokenManager | None = None


def get_token_manager() -> TokenManager:
    """TokenManager 싱글톤. lifespan 에서 set 하거나 dependency_overrides 로 테스트 주입.

    α chunk 에서는 placeholder — main.py lifespan 이 set_token_manager 로 등록.
    """
    if _token_manager_singleton is None:
        # 운영 코드에서는 main.py 가 lifespan 에서 set_token_manager 호출. 미설정은 즉시 fail.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TokenManager 미초기화",
        )
    return _token_manager_singleton


def set_token_manager(manager: TokenManager) -> None:
    """lifespan 시작 시 호출 — TokenManager 주입."""
    global _token_manager_singleton
    _token_manager_singleton = manager


def reset_token_manager() -> None:
    """테스트 전용 — 싱글톤 리셋."""
    global _token_manager_singleton
    _token_manager_singleton = None


__all__ = [
    "get_settings_dep",
    "get_token_manager",
    "require_admin_key",
    "reset_token_manager",
    "set_token_manager",
]
