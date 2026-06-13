"""PDF structuring (compatibility shim)."""

from docintel.capabilities.extraction.structure import structure_pdf
from docintel.capabilities.extraction.structure_llm import structure_document

__all__ = ["structure_document", "structure_pdf"]
