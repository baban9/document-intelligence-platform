"""PDF search and annotation service."""

from docintel.services.pdf.annotator import PDFAnnotator, annotate_pdf
from docintel.services.pdf.models import Action, ProcessResult
from docintel.services.pdf.search import extract_info, search_for_text

__all__ = [
    "Action",
    "PDFAnnotator",
    "ProcessResult",
    "annotate_pdf",
    "extract_info",
    "search_for_text",
]
