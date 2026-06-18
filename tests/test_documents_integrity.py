"""Tests for document integrity analysis route."""

from docintel.app import create_app
from docintel.capabilities.compliance.integrity import IntegrityFinding, IntegrityResult


def test_analyze_integrity_route_returns_findings(monkeypatch):
    def fake_analyze(text, *, checks=None):
        assert "TBD" in text
        return IntegrityResult(
            finding_count=1,
            findings=[
                IntegrityFinding(
                    severity="medium",
                    category="placeholder",
                    description="Unresolved placeholder marker.",
                    evidence=[],
                )
            ],
            summary={"by_category": {"placeholder": 1}, "by_severity": {"medium": 1}},
            checks_run=["placeholders"],
        )

    monkeypatch.setattr("docintel.routes.documents.analyze_document_integrity", fake_analyze)

    app = create_app()
    with app.test_client() as client:
        response = client.post(
            "/v1/documents/analyze-integrity",
            json={"text": "Scope is TBD for phase two."},
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["finding_count"] == 1
    assert payload["findings"][0]["category"] == "placeholder"


def test_analyze_integrity_route_requires_input():
    app = create_app()
    with app.test_client() as client:
        response = client.post("/v1/documents/analyze-integrity", json={})
    assert response.status_code == 400


def test_analyze_integrity_route_rejects_unknown_checks():
    app = create_app()
    with app.test_client() as client:
        response = client.post(
            "/v1/documents/analyze-integrity",
            json={"text": "hello", "checks": ["not_a_check"]},
        )
    payload = response.get_json()
    assert response.status_code == 400
    assert "Unknown integrity checks" in payload["error"]
