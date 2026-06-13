"""PDF core capabilities (search, annotate, shared models)."""

from docintel.capabilities.pdf.annotator import PDFAnnotator, annotate_pdf
from docintel.capabilities.pdf.models import (
    Action,
    PIIDetectionResult,
    ProcessResult,
    StructureMode,
    StructureResult,
)
from docintel.capabilities.pdf.search import extract_info, search_for_text

__all__ = [
    "Action",
    "PDFAnnotator",
    "PIIDetectionResult",
    "ProcessResult",
    "StructureMode",
    "StructureResult",
    "annotate_pdf",
    "extract_info",
    "search_for_text",
]
