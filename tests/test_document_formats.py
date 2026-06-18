"""Tests for multi-format document identification and extraction."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from docintel.app import create_app
from docintel.capabilities.extraction.formats import (
    DocumentKind,
    extract_document_text,
    identify_document,
    list_supported_types,
)


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    path = tmp_path / "report.csv"
    path.write_text("name,amount\nAcme,1200\nBeta,800\n", encoding="utf-8")
    return path


@pytest.fixture
def sample_txt(tmp_path: Path) -> Path:
    path = tmp_path / "notes.txt"
    path.write_text("Quarterly operations review for the logistics team.", encoding="utf-8")
    return path


@pytest.fixture
def sample_docx(tmp_path: Path) -> Path:
    docx = pytest.importorskip("docx")
    path = tmp_path / "contract.docx"
    document = docx.Document()
    document.add_paragraph("Master service agreement between the parties.")
    document.save(path)
    return path


@pytest.fixture
def sample_xlsx(tmp_path: Path) -> Path:
    openpyxl = pytest.importorskip("openpyxl")
    path = tmp_path / "budget.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Q1"
    sheet.append(["account", "balance"])
    sheet.append(["cash", "50000"])
    workbook.save(path)
    workbook.close()
    return path


@pytest.fixture
def sample_pptx(tmp_path: Path) -> Path:
    pptx = pytest.importorskip("pptx")
    path = tmp_path / "review.pptx"
    presentation = pptx.Presentation()
    slide_layout = presentation.slide_layouts[1]
    slide = presentation.slides.add_slide(slide_layout)
    slide.shapes.title.text = "Quarterly finance review"
    slide.placeholders[1].text = "Revenue, payment totals, and ledger balances."
    presentation.save(path)
    return path


@pytest.fixture
def fake_docx_extension(tmp_path: Path) -> Path:
    """A zip file with a .docx extension but non-word contents."""
    path = tmp_path / "fake.docx"
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("readme.txt", "not a word file")
    path.write_bytes(buffer.getvalue())
    return path


def test_list_supported_types_includes_office_formats():
    kinds = {item["kind"] for item in list_supported_types()}
    assert {"pdf", "docx", "xlsx", "pptx", "csv", "plain_text", "json"}.issubset(kinds)


def test_identify_csv_by_content(sample_csv: Path):
    result = identify_document(sample_csv, filename="upload.dat")
    assert result.kind is DocumentKind.CSV


def test_identify_docx_by_zip_signature(sample_docx: Path):
    result = identify_document(sample_docx)
    assert result.kind is DocumentKind.DOCX
    assert result.detected_by == "content"


def test_identify_rejects_mismatched_docx_extension(fake_docx_extension: Path):
    result = identify_document(fake_docx_extension)
    assert result.kind is not DocumentKind.DOCX


def test_extract_text_from_csv(sample_csv: Path):
    result = extract_document_text(sample_csv)
    assert "Acme" in result.text
    assert result.kind is DocumentKind.CSV


def test_extract_text_from_docx(sample_docx: Path):
    result = extract_document_text(sample_docx)
    assert "Master service agreement" in result.text
    assert result.metadata["paragraph_count"] >= 1


def test_extract_text_from_xlsx(sample_xlsx: Path):
    result = extract_document_text(sample_xlsx)
    assert "cash" in result.text.lower()
    assert result.metadata["sheet_count"] == 1


def test_identify_pptx_by_zip_signature(sample_pptx: Path):
    result = identify_document(sample_pptx)
    assert result.kind is DocumentKind.PPTX
    assert result.detected_by == "content"


def test_extract_text_from_pptx(sample_pptx: Path):
    result = extract_document_text(sample_pptx)
    assert "Quarterly finance review" in result.text
    assert "ledger balances" in result.text
    assert result.metadata["slide_count"] == 1


def test_types_route_lists_formats():
    app = create_app()
    with app.test_client() as client:
        response = client.get("/v1/documents/types")
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert any(item["kind"] == "xlsx" for item in payload["types"])
    assert any(item["kind"] == "pptx" for item in payload["types"])


def test_identify_route(sample_txt: Path):
    app = create_app()
    with app.test_client() as client:
        with sample_txt.open("rb") as handle:
            response = client.post(
                "/v1/documents/identify",
                data={"file": (handle, "notes.txt")},
                content_type="multipart/form-data",
            )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["kind"] == "plain_text"


def test_extract_text_route(sample_csv: Path):
    app = create_app()
    with app.test_client() as client:
        with sample_csv.open("rb") as handle:
            response = client.post(
                "/v1/documents/extract-text",
                data={"file": (handle, "report.csv")},
                content_type="multipart/form-data",
            )
    payload = response.get_json()
    assert response.status_code == 200
    assert "Acme" in payload["text"]


def test_classify_route_accepts_file_upload(sample_docx: Path):
    app = create_app()
    with app.test_client() as client:
        with sample_docx.open("rb") as handle:
            response = client.post(
                "/v1/documents/classify",
                data={"file": (handle, "contract.docx")},
                content_type="multipart/form-data",
            )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["category"] == "legal"


def test_pdf_route_rejects_docx_with_detected_kind(sample_docx: Path, tmp_path: Path):
    app = create_app()
    app.config["UPLOAD_DIR"] = str(tmp_path / "uploads")

    with app.test_client() as client:
        with sample_docx.open("rb") as handle:
            response = client.post(
                "/v1/pdf/annotate",
                data={
                    "file": (handle, "contract.docx"),
                    "pattern": "party",
                    "action": "Highlight",
                },
                content_type="multipart/form-data",
            )

    payload = response.get_json()
    assert response.status_code == 415
    assert payload["detected"]["kind"] == "docx"
    assert "extract-text" in payload["hint"]
