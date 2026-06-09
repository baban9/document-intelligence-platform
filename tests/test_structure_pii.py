"""Tests for PII redaction before LLM structuring."""

from pathlib import Path

from docintel.services.pdf.models import StructureMode
from docintel.services.pdf.structure import structure_pdf
from docintel.services.pdf.structure_schema import (
    SectionBlock,
    StructuredDocument,
    StructuredPage,
)


def _fake_structure(page_texts, progress_callback=None):
    captured = page_texts[0][1]
    pages = [
        StructuredPage(
            page_index=0,
            title="Doc",
            sections=[
                SectionBlock(
                    heading="Body",
                    level=1,
                    paragraphs=[captured],
                    list_items=[],
                    tables=[],
                )
            ],
            plain_text=captured,
        )
    ]
    return StructuredDocument.from_pages(pages)


def test_structure_pdf_redacts_before_llm(sample_pdf: Path, tmp_path: Path, monkeypatch):
    def fake_mask(text, **kwargs):
        return text.replace("ABC123", "[REDACTED_US_SSN]"), 1

    monkeypatch.setattr("docintel.services.pdf.pii.mask_pii_in_text", fake_mask)

    output_path = tmp_path / "structured.pdf"
    structure_pdf(
        input_file=sample_pdf,
        output_file=output_path,
        mode=StructureMode.CURATE,
        redact_before_llm=True,
        structure_fn=_fake_structure,
    )

    doc_text = __import__("fitz").open(output_path)[0].get_text("text")
    assert "[REDACTED_US_SSN]" in doc_text
