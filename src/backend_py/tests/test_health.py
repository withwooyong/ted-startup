from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_up() -> None:
    client = TestClient(app)
    resp = client.get("/health")
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
