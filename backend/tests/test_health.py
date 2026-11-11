"""Tests for the /health endpoint. Run from backend/:  pytest -v"""


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "api_key_configured" in body
    assert body["documents"] == 0
