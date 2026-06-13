"""Text search helpers for PDF pages."""

from __future__ import annotations

import re
from typing import Iterable

import fitz


def search_for_text(lines: Iterable[str], pattern: str) -> Iterable[str]:
    """Yield regex matches from each line (case insensitive)."""
    for line in lines:
        for result in re.findall(pattern, line, re.IGNORECASE):
            yield result


def extract_info(input_file: str) -> dict:
    """Return basic metadata for a PDF file."""
    pdf_doc = fitz.open(input_file)
    info = {
        "file": input_file,
        "page_count": pdf_doc.page_count,
        "encrypted": pdf_doc.is_encrypted,
    }
    if not pdf_doc.is_encrypted:
        info.update({key: value for key, value in pdf_doc.metadata.items() if value})
    pdf_doc.close()
    return info
