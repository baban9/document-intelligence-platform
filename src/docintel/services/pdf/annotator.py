"""PDF annotator (compatibility shim)."""

from docintel.capabilities.pdf.annotator import (
    PDFAnnotator,
    _open_pdf,
    _save_pdf,
    annotate_pdf,
    highlight_matches,
    redact_matches,
)

__all__ = [
    "PDFAnnotator",
    "_open_pdf",
    "_save_pdf",
    "annotate_pdf",
    "highlight_matches",
    "redact_matches",
]
