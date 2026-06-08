"""Unit tests for PDF annotation service."""

from pathlib import Path

import fitz

from docintel.services.pdf import Action, PDFAnnotator, annotate_pdf


def test_annotate_pdf_highlights_matches(sample_pdf: Path, tmp_path: Path):
    output_pdf = tmp_path / "highlighted.pdf"
    result = annotate_pdf(
        input_file=sample_pdf,
        output_file=output_pdf,
        pattern=r"ABC123",
        action=Action.HIGHLIGHT,
    )

    assert output_pdf.exists()
    assert result.matches == 1
    assert result.pages_processed == 1

    doc = fitz.open(output_pdf)
    assert doc[0].first_annot is not None
    doc.close()


def test_annotate_pdf_redacts_matches(sample_pdf: Path, tmp_path: Path):
    output_pdf = tmp_path / "redacted.pdf"
    result = annotate_pdf(
        input_file=sample_pdf,
        output_file=output_pdf,
        pattern=r"ABC123",
        action=Action.REDACT,
    )

    assert result.matches == 1
    assert output_pdf.exists()


def test_pdf_annotator_class(sample_pdf: Path, tmp_path: Path):
    output_pdf = tmp_path / "framed.pdf"
    annotator = PDFAnnotator(pattern=r"XYZ\d+", action=Action.FRAME)
    result = annotator.annotate(sample_pdf, output_pdf)

    assert result.matches == 1
    assert output_pdf.exists()


def test_invalid_action_raises():
    try:
        Action.from_value("InvalidAction")
    except ValueError as exc:
        assert "Unsupported action" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid action")
