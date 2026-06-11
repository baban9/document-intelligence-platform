"""Tests for OpenAPI spec and Swagger UI."""

from docintel.app import create_app


def test_openapi_json_lists_v1_paths():
    app = create_app()
    with app.test_client() as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.get_json()
    assert "/v1/pdf/structure" in spec["paths"]
    assert "/v1/pdf/detect-sensitive" in spec["paths"]
    assert "/v1/jobs/{job_id}" in spec["paths"]


def test_docs_returns_swagger_ui():
    app = create_app()
    with app.test_client() as client:
        response = client.get("/docs")
    assert response.status_code == 200
    assert b"swagger-ui" in response.data
