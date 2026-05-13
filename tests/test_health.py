from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "YourNews"}


def test_dashboard_root_serves_index() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "YourNews MVP Dashboard" in response.text


def test_dashboard_static_javascript_served() -> None:
    client = TestClient(app)
    response = client.get("/static/dashboard.js")
    assert response.status_code == 200
    assert "loadDigest" in response.text
