"""slowapi Limiter 싱글톤 — 관리자 키 단위 쿼터.

FastAPI + slowapi 통합 패턴:
  1) 여기서 Limiter 인스턴스를 생성해 라우터가 `@limiter.limit(...)` 로 참조.
  2) `app/main.py` 가 `app.state.limiter = limiter` 등록 + 예외 핸들러 설정.
  3) Route 핸들러는 반드시 `request: Request` 파라미터를 받아야 slowapi 가
     요청 메타(헤더·IP)에 접근할 수 있다.

key_func 는 `X-API-Key` 헤더 우선, 없으면 원격 IP 로 fallback.
관리자 키가 노출될 경우 공격자가 IP 우회해도 같은 키로 묶이도록 의도.
"""
from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _admin_key_or_ip(request: Request) -> str:
    # X-API-Key 는 require_admin_key 에서 필수. 여기까지 온 요청은 유효한 키 보유.
    key = request.headers.get("X-API-Key")
    if key:
        return f"apikey:{key}"
    # 이론상 도달 불가지만 defense-in-depth 로 IP fallback.
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_admin_key_or_ip)
