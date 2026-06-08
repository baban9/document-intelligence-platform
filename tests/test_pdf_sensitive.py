"""Tests for OCR + Presidio sensitive PDF detection."""

from pathlib import Path

import fitz
import pytest

from docintel.services.pdf.models import Action
from docintel.services.pdf.ocr import (
    IndexedSpan,
    OCRSpan,
    build_indexed_text,
    merge_rects,
    page_has_native_text,
    rects_for_char_range,
)
from docintel.services.pdf.pii import PIIHit
from docintel.services.pdf.sensitive import detect_sensitive_pdf


def test_page_has_native_text_detects_scanned_page():
    doc = fitz.open()
    page = doc.new_page()
    assert page_has_native_text(page) is False
    page.insert_text((72, 72), "This page has enough native text for extraction.")
    assert page_has_native_text(page) is True
    doc.close()


def test_build_indexed_text_tracks_offsets():
    spans = [
        OCRSpan(text="John", rect=fitz.Rect(10, 10, 40, 20), confidence=0.9),
        OCRSpan(text="Doe", rect=fitz.Rect(50, 10, 80, 20), confidence=0.9),
    ]
    text, indexed = build_indexed_text(spans)
    assert text == "John Doe"
    assert indexed[0].char_start == 0
    assert indexed[1].char_start == 5


def test_rects_for_char_range_maps_pii_span():
    indexed = [
        IndexedSpan(char_start=0, char_end=4, rect=fitz.Rect(0, 0, 10, 10)),
        IndexedSpan(char_start=5, char_end=8, rect=fitz.Rect(12, 0, 22, 10)),
    ]
    rects = rects_for_char_range(0, 8, indexed)
    merged = merge_rects(rects)
    assert merged is not None
    assert merged.x0 == 0
    assert merged.x1 == 22


def test_detect_sensitive_native_pdf_with_mocked_presidio(
    sample_pdf: Path, tmp_path: Path, monkeypatch
):
    def fake_detect(text, entities=None, language="en", min_score=0.35):
        if "ABC123" in text:
            start = text.index("ABC123")
            return [
                PIIHit(
                    entity_type="US_SSN",
                    text="ABC123",
                    start=start,
                    end=start + 6,
                    score=0.95,
                )
            ]
        return []

    monkeypatch.setattr(
        "docintel.services.pdf.sensitive.detect_pii_in_text",
        fake_detect,
    )
    monkeypatch.setattr("docintel.services.pdf.sensitive._ensure_ocr_stack", lambda: None)

    output_pdf = tmp_path / "sensitive.pdf"
    result = detect_sensitive_pdf(
        input_file=sample_pdf,
        output_file=output_pdf,
        action=Action.HIGHLIGHT,
    )

    assert output_pdf.exists()
    assert result.matches >= 1
    assert result.ocr_pages == []
    assert len(result.findings) >= 1

    doc = fitz.open(output_pdf)
    assert doc[0].first_annot is not None
    doc.close()


def test_detect_sensitive_route_json_mode(sample_pdf: Path, tmp_path: Path, monkeypatch):
    def fake_detect(text, entities=None, language="en", min_score=0.35):
        return []

    monkeypatch.setattr(
        "docintel.services.pdf.sensitive.detect_pii_in_text",
        fake_detect,
    )
    monkeypatch.setattr("docintel.services.pdf.sensitive._ensure_ocr_stack", lambda: None)

    from docintel.app import create_app

    app = create_app()
    app.config["UPLOAD_DIR"] = str(tmp_path / "uploads")

    with app.test_client() as client:
        with sample_pdf.open("rb") as handle:
            response = client.post(
                "/v1/pdf/detect-sensitive?format=json",
                data={"file": (handle, "sample.pdf"), "action": "Highlight"},
                content_type="multipart/form-data",
            )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert "findings" in payload
    assert "download_url" in payload


def test_list_supported_entities_not_empty():
    pytest.importorskip("presidio_analyzer")
    from docintel.services.pdf.pii import list_supported_entities

    entities = list_supported_entities()
    assert "EMAIL_ADDRESS" in entities
