"""Tests for process extraction report segments in API responses."""

from pathlib import Path

import fitz

from docintel.capabilities.pipeline.process import ProcessOptions, process_document


def test_process_includes_segments_without_full_text(tmp_path: Path):
    pdf_path = tmp_path / "pages.pdf"
    doc = fitz.open()
    for index in range(2):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {index + 1} content with EMAIL test{index}@example.org")
    doc.save(pdf_path)
    doc.close()

    result = process_document(
        pdf_path,
        options=ProcessOptions(include_text=False, include_pii=False, include_summarize=False),
    )
    segments = result.extraction_report.get("segments")
    assert isinstance(segments, list)
    assert len(segments) >= 2
    assert "text" not in result.extraction_report or result.extraction_report.get("text") is None
