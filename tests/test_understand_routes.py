"""API tests for document understanding routes."""

from docintel.app import create_app

TEXT = """
This service agreement governs payment terms between the vendor and customer.
The invoice total is due within thirty days of receipt.
Contact Jane Doe at jane.doe@example.com for billing questions.
"""


def test_text_understand_route_returns_report():
    app = create_app()

    with app.test_client() as client:
        response = client.post(
            "/v1/text/understand",
            json={"text": TEXT, "sentences": 2, "include_summary": True, "include_pii": True},
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["word_count"] > 0
    assert payload["classification"]["category"]
    assert payload["summary"]["summary"]
    assert payload["pii"]["finding_count"] >= 1


def test_text_understand_route_requires_text():
    app = create_app()

    with app.test_client() as client:
        response = client.post("/v1/text/understand", json={"sentences": 2})

    assert response.status_code == 400


def test_documents_understand_route_accepts_upload(sample_pdf):
    app = create_app()

    with app.test_client() as client:
        with sample_pdf.open("rb") as handle:
            response = client.post(
                "/v1/documents/understand",
                data={"file": (handle, "sample.pdf"), "sentences": "2"},
                content_type="multipart/form-data",
            )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["filename"] == "sample.pdf"
    assert payload["classification"]["category"]
