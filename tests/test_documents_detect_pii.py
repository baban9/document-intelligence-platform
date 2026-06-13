"""Tests for document PII detection route."""

from docintel.app import create_app
from docintel.services.pdf.pii import PIIHit


def test_detect_pii_route_returns_findings(monkeypatch):
    def fake_detect(text, *, entities=None, language="en", min_score=0.35):
        assert "john@example.com" in text
        return [
            PIIHit(
                entity_type="EMAIL_ADDRESS",
                text="john@example.com",
                start=text.index("john@example.com"),
                end=text.index("john@example.com") + len("john@example.com"),
                score=0.95,
            )
        ]

    monkeypatch.setattr("docintel.routes.documents.detect_pii_in_text", fake_detect)

    app = create_app()
    with app.test_client() as client:
        response = client.post(
            "/v1/documents/detect-pii",
            json={"text": "Contact john@example.com for billing."},
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["finding_count"] == 1
    assert payload["findings"][0]["entity_type"] == "EMAIL_ADDRESS"


def test_detect_pii_route_requires_input():
    app = create_app()
    with app.test_client() as client:
        response = client.post("/v1/documents/detect-pii", json={})
    assert response.status_code == 400
