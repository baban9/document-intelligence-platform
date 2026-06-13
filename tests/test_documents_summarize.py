"""Tests for document summarize route."""

from pathlib import Path

import pytest

from docintel.app import create_app


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    path = tmp_path / "report.csv"
    path.write_text(
        "summary,Quarterly operations review for logistics.\n"
        "detail,Inventory levels remained stable across regions.\n"
        "detail,Maintenance schedules were completed on time.\n",
        encoding="utf-8",
    )
    return path


def test_summarize_route_accepts_file_upload(sample_csv: Path):
    app = create_app()
    with app.test_client() as client:
        with sample_csv.open("rb") as handle:
            response = client.post(
                "/v1/documents/summarize",
                data={"file": (handle, "report.csv"), "sentences": "2"},
                content_type="multipart/form-data",
            )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["sentence_count"] == 2
    assert payload["summary"]


def test_summarize_route_requires_input():
    app = create_app()
    with app.test_client() as client:
        response = client.post("/v1/documents/summarize", json={"sentences": 2})
    assert response.status_code == 400
