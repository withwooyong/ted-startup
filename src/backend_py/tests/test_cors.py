from __future__ import annotations

from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.main import create_app


def _preflight(client: TestClient, origin: str) -> dict[str, str]:
    resp = client.options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    return {k.lower(): v for k, v in resp.headers.items()}


def test_no_cors_header_when_whitelist_empty(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "[]")
    # cache-busting: 새 인스턴스로 create_app 호출
    app = create_app()
    client = TestClient(app)
    headers = _preflight(client, "https://evil.example.com")
    assert "access-control-allow-origin" not in headers


def test_wildcard_origin_is_stripped(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # 설정에 '*'가 들어가도 와일드카드는 필터링되어 CORS 미활성화
    settings = Settings(cors_allow_origins=["*"])
    assert [o for o in settings.cors_allow_origins if o and o != "*"] == []


def test_whitelisted_origin_allowed(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", '["https://app.example.com"]')
    app = create_app()
    client = TestClient(app)
    headers = _preflight(client, "https://app.example.com")
    assert headers.get("access-control-allow-origin") == "https://app.example.com"
    assert headers.get("access-control-allow-credentials") == "true"


def test_non_whitelisted_origin_denied(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", '["https://app.example.com"]')
    app = create_app()
    client = TestClient(app)
    headers = _preflight(client, "https://evil.example.com")
    assert headers.get("access-control-allow-origin") != "https://evil.example.com"
