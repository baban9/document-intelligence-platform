"""Multi-format document identification and text extraction."""

from docintel.capabilities.extraction.formats.extract import extract_document_text
from docintel.capabilities.extraction.formats.models import (
    DocumentKind,
    DocumentProfile,
    ExtractionResult,
    IdentificationResult,
)
from docintel.capabilities.extraction.formats.registry import (
    get_profile,
    list_supported_types,
    profiles_for_kind,
)
from docintel.capabilities.extraction.formats.sniff import identify_document

__all__ = [
    "DocumentKind",
    "DocumentProfile",
    "ExtractionResult",
    "IdentificationResult",
    "extract_document_text",
    "get_profile",
    "identify_document",
    "list_supported_types",
    "profiles_for_kind",
]
