"""Tests for paginated PDF extraction and large-document processing."""

from __future__ import annotations

from pathlib import Path

import fitz

from docintel.capabilities.extraction.formats import extract_document_text, identify_document
from docintel.capabilities.extraction.formats.paginated_pdf import (
    build_monolithic_text,
    detect_pii_in_pdf_segments,
    extract_pdf_document,
    is_large_pdf,
    read_pdf_pages,
    sample_pages_for_analysis,
    total_char_count,
)
from docintel.capabilities.pipeline import ProcessOptions, process_document
from docintel.services.pdf.pii import PIIHit


def _make_multi_page_pdf(path: Path, page_count: int, *, pii_page: int | None = None) -> None:
    doc = fitz.open()
    for index in range(page_count):
        page = doc.new_page()
        body = f"Chapter {index + 1}. Operations review for quarter {index + 1}."
        if pii_page is not None and index == pii_page:
            body += " Contact legal@example.com for notices."
        page.insert_text((72, 72), body)
    doc.save(path)
    doc.close()


def test_is_large_pdf_by_page_count():
    assert is_large_pdf(page_count=50, char_count=1000) is True
    assert is_large_pdf(page_count=49, char_count=1000) is False


def test_is_large_pdf_by_char_count(monkeypatch):
    monkeypatch.setattr(
        "docintel.capabilities.extraction.formats.paginated_pdf.max_full_text_chars",
        lambda: 1000,
    )
    assert is_large_pdf(page_count=10, char_count=1000) is True
    assert is_large_pdf(page_count=10, char_count=999) is False


def test_read_pdf_pages_tracks_global_offsets(tmp_path: Path):
    pdf_path = tmp_path / "book.pdf"
    _make_multi_page_pdf(pdf_path, 3)

    pages = read_pdf_pages(pdf_path)
    assert len(pages) == 3
    assert pages[0].char_start == 0
    assert pages[1].char_start == len(pages[0].text) + 2
    assert build_monolithic_text(pages) == "\n\n".join(page.text for page in pages)


def test_large_pdf_uses_paginated_mode(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DOCINTEL_LARGE_PDF_PAGE_THRESHOLD", "5")
    pdf_path = tmp_path / "book.pdf"
    _make_multi_page_pdf(pdf_path, 30)

    result = extract_document_text(pdf_path)
    full_count = total_char_count(read_pdf_pages(pdf_path))
    assert result.metadata["large_document"] is True
    assert result.metadata["processing_mode"] == "paginated"
    assert result.metadata["page_count"] == 30
    assert len(result.segments) == 30
    assert len(result.text) < full_count


def test_sample_pages_for_analysis_is_bounded(tmp_path: Path):
    pdf_path = tmp_path / "book.pdf"
    _make_multi_page_pdf(pdf_path, 120)
    pages = read_pdf_pages(pdf_path)

    sample = sample_pages_for_analysis(pages, max_chars=500)
    assert len(sample) <= 500
    assert "Chapter 1" in sample
    assert "Chapter 120" in sample


def test_extract_pdf_document_small_pdf_stays_monolithic(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DOCINTEL_LARGE_PDF_PAGE_THRESHOLD", "50")
    pdf_path = tmp_path / "short.pdf"
    _make_multi_page_pdf(pdf_path, 3)
    identification = identify_document(pdf_path)

    result = extract_pdf_document(pdf_path, identification)
    assert result.metadata["large_document"] is False
    assert result.metadata["processing_mode"] == "monolithic"
    assert result.text == build_monolithic_text(read_pdf_pages(pdf_path))


def test_detect_pii_in_pdf_segments_preserves_page_and_offsets(tmp_path: Path, monkeypatch):
    def fake_detect(text, *, entities=None, language="en", min_score=0.35):
        marker = "legal@example.com"
        if marker not in text:
            return []
        start = text.index(marker)
        return [
            PIIHit(
                entity_type="EMAIL_ADDRESS",
                text=marker,
                start=start,
                end=start + len(marker),
                score=0.99,
            )
        ]

    monkeypatch.setattr(
        "docintel.services.pdf.pii.detect_pii_in_text",
        fake_detect,
    )

    pdf_path = tmp_path / "book.pdf"
    _make_multi_page_pdf(pdf_path, 6, pii_page=4)
    segments = extract_document_text(pdf_path).segments

    findings = detect_pii_in_pdf_segments(segments)
    assert len(findings) == 1
    assert findings[0]["page"] == 4
    assert findings[0]["entity_type"] == "EMAIL_ADDRESS"


def test_process_large_pdf_completes_without_monolithic_text(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DOCINTEL_LARGE_PDF_PAGE_THRESHOLD", "5")

    def fake_detect(text, *, entities=None, language="en", min_score=0.35):
        if "legal@example.com" in text:
            start = text.index("legal@example.com")
            return [
                PIIHit(
                    entity_type="EMAIL_ADDRESS",
                    text="legal@example.com",
                    start=start,
                    end=start + len("legal@example.com"),
                    score=0.99,
                )
            ]
        return []

    monkeypatch.setattr(
        "docintel.services.pdf.pii.detect_pii_in_text",
        fake_detect,
    )

    pdf_path = tmp_path / "book.pdf"
    _make_multi_page_pdf(pdf_path, 12, pii_page=10)

    result = process_document(
        pdf_path,
        options=ProcessOptions(include_text=True, include_pii=True, sentences=2),
    )
    payload = result.to_dict()

    assert payload["extraction"]["large_document"] is True
    assert payload["extraction"]["segment_count"] == 12
    assert "text" not in payload["extraction"]
    assert payload["classification"]["category"]
    assert payload["summary"]["sentence_count"] == 2
    assert payload["pii"]["finding_count"] == 1
    assert payload["pii"]["findings"][0]["page"] == 10
