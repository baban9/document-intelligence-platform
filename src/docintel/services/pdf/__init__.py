"""PDF search and annotation service."""

from docintel.services.pdf.annotator import PDFAnnotator, annotate_pdf
from docintel.services.pdf.models import Action, PIIDetectionResult, ProcessResult, StructureMode, StructureResult
from docintel.services.pdf.pii import detect_pii_in_text, list_supported_entities
from docintel.services.pdf.presets import DEFAULT_PII_ENTITIES
from docintel.services.pdf.search import extract_info, search_for_text
from docintel.services.pdf.sensitive import detect_sensitive_pdf
from docintel.services.pdf.structure import structure_pdf

__all__ = [
    "Action",
    "DEFAULT_PII_ENTITIES",
    "PDFAnnotator",
    "PIIDetectionResult",
    "ProcessResult",
    "StructureMode",
    "StructureResult",
    "annotate_pdf",
    "detect_pii_in_text",
    "detect_sensitive_pdf",
    "extract_info",
    "list_supported_entities",
    "search_for_text",
    "structure_pdf",
]
