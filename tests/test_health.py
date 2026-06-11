"""Smoke tests for the API shell."""

from docintel.app import create_app


def test_health_returns_ok():
    client = create_app().test_client()
    response = client.get("/health")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["service"] == "document-intelligence-platform"
    assert payload["version"] == "1.0.0"
