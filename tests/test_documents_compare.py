"""Tests for document comparison routes."""

from docintel.app import create_app


def test_compare_route_returns_similarity():
    app = create_app()
    text_a = "Refund policy allows returns within thirty days of purchase."
    text_b = "Return policy allows refunds within thirty days after purchase."

    with app.test_client() as client:
        response = client.post(
            "/v1/documents/compare",
            json={"text_a": text_a, "text_b": text_b},
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["similarity"] > 0.5
    assert "policy" in payload["shared_terms"]


def test_compare_route_requires_both_texts():
    app = create_app()

    with app.test_client() as client:
        response = client.post("/v1/documents/compare", json={"text_a": "only one"})

    assert response.status_code == 400
