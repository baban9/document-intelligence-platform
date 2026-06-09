"""Tests for LLM PDF structuring."""

from pathlib import Path

import fitz

from docintel.app import create_app
from docintel.services.pdf.models import StructureMode
from docintel.services.pdf.structure import structure_pdf
from docintel.services.pdf.structure_render import render_curated_pdf
from docintel.services.pdf.structure_schema import (
    SectionBlock,
    StructuredDocument,
    StructuredPage,
)


def _fake_structure(page_texts, progress_callback=None):
    pages = []
    for page_index, text in page_texts:
        pages.append(
            StructuredPage(
                page_index=page_index,
                title="Invoice" if page_index == 0 else "",
                sections=[
                    SectionBlock(
                        heading="Details",
                        level=1,
                        paragraphs=[text.strip() or "Empty page"],
                        list_items=[],
                        tables=[],
                    )
                ],
                plain_text=text.strip(),
            )
        )
    return StructuredDocument.from_pages(pages)


def test_render_curated_pdf_writes_text(tmp_path: Path):
    document = StructuredDocument(
        title="Test Document",
        pages=[
            StructuredPage(
                page_index=0,
                title="Test Document",
                sections=[
                    SectionBlock(
                        heading="Section One",
                        level=1,
                        paragraphs=["First paragraph."],
                        list_items=["Item A"],
                        tables=[],
                    )
                ],
                plain_text="Section One\nFirst paragraph.\n- Item A",
            )
        ],
    )
    output_path = tmp_path / "curated.pdf"
    render_curated_pdf(document, output_path)

    doc = fitz.open(output_path)
    text = doc[0].get_text("text")
    doc.close()

    assert "Test Document" in text
    assert "Section One" in text
    assert "First paragraph." in text


def test_structure_pdf_curate_mode(sample_pdf: Path, tmp_path: Path):
    output_path = tmp_path / "structured.pdf"
    result = structure_pdf(
        input_file=sample_pdf,
        output_file=output_path,
        mode=StructureMode.CURATE,
        structure_fn=_fake_structure,
    )

    assert result.mode == StructureMode.CURATE
    assert result.pages_processed == 1
    assert result.document_title == "Invoice"
    assert output_path.is_file()

    doc = fitz.open(output_path)
    text = doc[0].get_text("text")
    doc.close()
    assert "ABC123" in text


def test_structure_pdf_searchable_mode(sample_pdf: Path, tmp_path: Path):
    output_path = tmp_path / "searchable.pdf"
    result = structure_pdf(
        input_file=sample_pdf,
        output_file=output_path,
        mode=StructureMode.SEARCHABLE,
        structure_fn=_fake_structure,
    )

    assert result.mode == StructureMode.SEARCHABLE
    assert output_path.is_file()

    doc = fitz.open(output_path)
    text = doc[0].get_text("text")
    doc.close()
    assert "ABC123" in text


def test_structure_route_returns_pdf(sample_pdf: Path, tmp_path: Path):
    app = create_app()
    app.config["UPLOAD_DIR"] = str(tmp_path / "uploads")

    def fake_structure(page_texts, progress_callback=None):
        return _fake_structure(page_texts, progress_callback=progress_callback)

    from docintel.services.pdf import structure as structure_module

    original = structure_module.structure_document
    structure_module.structure_document = fake_structure
    try:
        with app.test_client() as client:
            with sample_pdf.open("rb") as handle:
                response = client.post(
                    "/v1/pdf/structure",
                    data={
                        "file": (handle, "sample.pdf"),
                        "mode": "curate",
                    },
                    content_type="multipart/form-data",
                )
    finally:
        structure_module.structure_document = original

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.headers["X-Docintel-Mode"] == "curate"


def test_structure_route_json_format(sample_pdf: Path, tmp_path: Path):
    app = create_app()
    app.config["UPLOAD_DIR"] = str(tmp_path / "uploads")

    from docintel.services.pdf import structure as structure_module

    original = structure_module.structure_document
    structure_module.structure_document = _fake_structure
    try:
        with app.test_client() as client:
            with sample_pdf.open("rb") as handle:
                response = client.post(
                    "/v1/pdf/structure?format=json",
                    data={
                        "file": (handle, "sample.pdf"),
                        "mode": "curate",
                    },
                    content_type="multipart/form-data",
                )
    finally:
        structure_module.structure_document = original

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["mode"] == "curate"
    assert "download_url" in payload


def test_structure_route_rejects_invalid_mode(sample_pdf: Path, tmp_path: Path):
    app = create_app()
    app.config["UPLOAD_DIR"] = str(tmp_path / "uploads")

    with app.test_client() as client:
        with sample_pdf.open("rb") as handle:
            response = client.post(
                "/v1/pdf/structure",
                data={
                    "file": (handle, "sample.pdf"),
                    "mode": "invalid",
                },
                content_type="multipart/form-data",
            )

    assert response.status_code == 400
