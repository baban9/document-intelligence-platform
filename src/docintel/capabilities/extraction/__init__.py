"""Document extraction capabilities (OCR, LLM structuring)."""

from docintel.capabilities.extraction.ocr import (
    OCRSpan,
    build_indexed_text,
    embed_invisible_text_layer,
    extract_page_ocr,
    merge_rects,
    page_has_native_text,
    rects_for_char_range,
)
from docintel.capabilities.extraction.structure_schema import (
    SectionBlock,
    StructuredDocument,
    StructuredPage,
)

__all__ = [
    "OCRSpan",
    "SectionBlock",
    "StructuredDocument",
    "StructuredPage",
    "build_indexed_text",
    "embed_invisible_text_layer",
    "extract_page_ocr",
    "merge_rects",
    "page_has_native_text",
    "rects_for_char_range",
]
