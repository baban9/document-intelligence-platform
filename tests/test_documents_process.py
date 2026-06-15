"""Tests for unified document process pipeline."""

from pathlib import Path

import pytest

from docintel.app import create_app
from docintel.capabilities.pipeline import ProcessOptions, process_document
from docintel.services.pdf.pii import PIIHit


@pytest.fixture
def sample_txt(tmp_path: Path) -> Path:
    path = tmp_path / "contract.txt"
    path.write_text(
        "Master service agreement between the parties. "
        "This contract defines jurisdiction and liability clauses. "
        "Contact john@example.com for legal notices only.",
        encoding="utf-8",
    )
    return path


def test_process_document_runs_all_steps(sample_txt: Path, monkeypatch):
    def fake_detect(text, *, entities=None, language="en", min_score=0.35):
        return [
            PIIHit(
                entity_type="EMAIL_ADDRESS",
                text="john@example.com",
                start=text.index("john@example.com"),
                end=text.index("john@example.com") + len("john@example.com"),
                score=0.95,
            )
        ]

    monkeypatch.setattr("docintel.capabilities.pipeline.process.detect_pii_in_text", fake_detect)

    result = process_document(
        sample_txt,
        options=ProcessOptions(include_text=True, sentences=2),
    )
    payload = result.to_dict()

    assert payload["identification"]["kind"] == "plain_text"
    assert payload["classification"]["category"] == "legal"
    assert payload["summary"]["sentence_count"] == 2
    assert payload["pii"]["finding_count"] == 1
    assert "john@example.com" in payload["extraction"]["text"]


def test_process_route(sample_txt: Path, monkeypatch):
    def fake_detect(text, *, entities=None, language="en", min_score=0.35):
        return []

    monkeypatch.setattr(
        "docintel.capabilities.pipeline.process.detect_pii_in_text",
        fake_detect,
    )

    app = create_app()
    with app.test_client() as client:
        with sample_txt.open("rb") as handle:
            response = client.post(
                "/v1/documents/process",
                data={
                    "file": (handle, "contract.txt"),
                    "sentences": "2",
                    "include_pii": "false",
                },
                content_type="multipart/form-data",
            )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["classification"]["category"] == "legal"
    assert "summary" in payload
    assert "pii" not in payload
