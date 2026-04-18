from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_up_without_env_metadata() -> None:
    """외부 공개 엔드포인트 — 상태 코드만. app/env 노출 금지."""
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"status": "UP"}
    assert "app" not in body
    assert "env" not in body


def test_internal_info_exposes_app_env() -> None:
    """/internal/* 는 Caddy 에서 외부 차단. 내부 요청에는 상세 응답."""
    client = TestClient(app)
    resp = client.get("/internal/info")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "UP"
    assert "app" in body
    assert "env" in body


def test_metrics_endpoint_exposed() -> None:
    client = TestClient(app)
    # 애플리케이션에 한 번 요청을 보내 메트릭 생성
    client.get("/health")
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text or "# HELP" in resp.text
