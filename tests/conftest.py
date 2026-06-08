"""Shared pytest fixtures."""

from pathlib import Path

import fitz
import pytest


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Invoice Number: ABC123")
    page.insert_text((72, 100), "Customer ID: XYZ789")
    doc.save(pdf_path)
    doc.close()
    return pdf_path
