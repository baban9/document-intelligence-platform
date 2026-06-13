"""Tests for document compare file uploads."""

from pathlib import Path

import pytest

from docintel.app import create_app


@pytest.fixture
def policy_a(tmp_path: Path) -> Path:
    path = tmp_path / "policy_a.txt"
    path.write_text("Refund policy allows returns within thirty days of purchase.", encoding="utf-8")
    return path


@pytest.fixture
def policy_b(tmp_path: Path) -> Path:
    path = tmp_path / "policy_b.txt"
    path.write_text("Return policy allows refunds within thirty days after purchase.", encoding="utf-8")
    return path


def test_compare_route_accepts_file_uploads(policy_a: Path, policy_b: Path):
    app = create_app()
    with app.test_client() as client:
        with policy_a.open("rb") as handle_a, policy_b.open("rb") as handle_b:
            response = client.post(
                "/v1/documents/compare",
                data={
                    "file_a": (handle_a, "policy_a.txt"),
                    "file_b": (handle_b, "policy_b.txt"),
                },
                content_type="multipart/form-data",
            )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["similarity"] > 0.5
    assert "policy" in payload["shared_terms"]
