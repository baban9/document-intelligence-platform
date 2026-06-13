"""Tests for document classification routes."""

from docintel.app import create_app


def test_classify_route_returns_category():
    app = create_app()
    text = (
        "This service agreement defines party obligations, liability limits, "
        "and jurisdiction for the contract term."
    )

    with app.test_client() as client:
        response = client.post("/v1/documents/classify", json={"text": text})

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["category"] == "legal"
    assert payload["confidence"] > 0
    assert "finance" in payload["scores"]


def test_classify_route_requires_text():
    app = create_app()

    with app.test_client() as client:
        response = client.post("/v1/documents/classify", json={"text": "   "})

    assert response.status_code == 400
