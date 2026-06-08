"""API tests for PDF annotation routes."""

from pathlib import Path

import fitz

from docintel.app import create_app


def test_annotate_returns_pdf_file(sample_pdf: Path, tmp_path: Path):
    app = create_app()
    app.config["UPLOAD_DIR"] = str(tmp_path / "uploads")

    with app.test_client() as client:
        with sample_pdf.open("rb") as handle:
            response = client.post(
                "/v1/pdf/annotate",
                data={
                    "file": (handle, "sample.pdf"),
                    "pattern": "ABC123",
                    "action": "Highlight",
                },
                content_type="multipart/form-data",
            )

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.headers["X-Docintel-Matches"] == "1"
    assert response.headers["X-Docintel-Pages-Processed"] == "1"


def test_annotate_json_format(sample_pdf: Path, tmp_path: Path):
    app = create_app()
    app.config["UPLOAD_DIR"] = str(tmp_path / "uploads")

    with app.test_client() as client:
        with sample_pdf.open("rb") as handle:
            response = client.post(
                "/v1/pdf/annotate?format=json",
                data={
                    "file": (handle, "sample.pdf"),
                    "pattern": "CONFIDENTIAL",
                    "action": "Redact",
                },
                content_type="multipart/form-data",
            )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["action"] == "Redact"
    assert "download_url" in payload


def test_annotate_requires_file(tmp_path: Path):
    app = create_app()
    app.config["UPLOAD_DIR"] = str(tmp_path / "uploads")

    with app.test_client() as client:
        response = client.post(
            "/v1/pdf/annotate",
            data={"pattern": "ABC123", "action": "Highlight"},
        )

    assert response.status_code == 400
    assert "Missing PDF file" in response.get_json()["error"]


def test_annotate_rejects_invalid_action(sample_pdf: Path, tmp_path: Path):
    app = create_app()
    app.config["UPLOAD_DIR"] = str(tmp_path / "uploads")

    with app.test_client() as client:
        with sample_pdf.open("rb") as handle:
            response = client.post(
                "/v1/pdf/annotate",
                data={
                    "file": (handle, "sample.pdf"),
                    "pattern": "ABC123",
                    "action": "NotReal",
                },
                content_type="multipart/form-data",
            )

    assert response.status_code == 400


def test_download_file_after_json_response(sample_pdf: Path, tmp_path: Path):
    app = create_app()
    app.config["UPLOAD_DIR"] = str(tmp_path / "uploads")

    with app.test_client() as client:
        with sample_pdf.open("rb") as handle:
            create_response = client.post(
                "/v1/pdf/annotate?format=json",
                data={
                    "file": (handle, "sample.pdf"),
                    "pattern": "ABC123",
                    "action": "Highlight",
                },
                content_type="multipart/form-data",
            )

        download_url = create_response.get_json()["download_url"]
        download_response = client.get(download_url)

    assert download_response.status_code == 200
    assert download_response.mimetype == "application/pdf"

    doc = fitz.open(stream=download_response.data, filetype="pdf")
    assert doc[0].first_annot is not None
    doc.close()
