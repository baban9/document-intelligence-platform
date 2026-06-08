"""API tests for text summarization routes."""

from docintel.app import create_app

TEXT = """
Machine learning helps teams automate document review.
Extractive summarization selects the most important sentences from a source text.
TextRank builds a graph of sentence similarities and ranks them with PageRank.
This approach works well for reports, resumes, and meeting notes.
"""


def test_summarize_route_returns_summary():
    app = create_app()

    with app.test_client() as client:
        response = client.post(
            "/v1/text/summarize",
            json={"text": TEXT, "sentences": 2},
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["sentence_count"] == 2
    assert len(payload["sentences"]) == 2
    assert payload["summary"]


def test_summarize_route_requires_text():
    app = create_app()

    with app.test_client() as client:
        response = client.post("/v1/text/summarize", json={"sentences": 2})

    assert response.status_code == 400


def test_summarize_route_validates_sentence_count():
    app = create_app()

    with app.test_client() as client:
        response = client.post(
            "/v1/text/summarize",
            json={"text": TEXT, "sentences": 0},
        )

    assert response.status_code == 400
