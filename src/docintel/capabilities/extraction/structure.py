"""LLM-backed PDF structuring: unstructured scan to curated digital PDF."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol

import fitz

from docintel.services.pdf.annotator import _open_pdf
from docintel.services.pdf.models import StructureMode, StructureResult
from docintel.capabilities.extraction.ocr import build_indexed_text, extract_page_ocr, page_has_native_text
from docintel.capabilities.extraction.structure_render import render_curated_pdf, render_searchable_pdf
from docintel.capabilities.extraction.structure_schema import StructuredDocument


class ProgressCallback(Protocol):
    def __call__(
        self,
        *,
        stage: str,
        pages_done: int,
        pages_total: int,
        message: str,
    ) -> None: ...


def _ensure_ocr_stack() -> None:
    try:
        import easyocr  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "OCR dependencies are not installed. Run: pip install -e '.[ocr]'"
        ) from exc


def _extract_page_text(page: fitz.Page, force_ocr: bool) -> tuple[str, bool]:
    use_ocr = force_ocr or not page_has_native_text(page)
    if use_ocr:
        _ensure_ocr_stack()
        spans = extract_page_ocr(page)
        text, _ = build_indexed_text(spans)
        return text, True
    return page.get_text("text"), False


def structure_pdf(
    input_file: str | Path,
    output_file: str | Path,
    *,
    mode: StructureMode | str = StructureMode.CURATE,
    force_ocr: bool = False,
    redact_before_llm: bool = False,
    structure_fn: Callable[[list[tuple[int, str]]], StructuredDocument] | None = None,
    progress_callback: ProgressCallback | None = None,
    password: str | None = None,
) -> StructureResult:
    """
    Convert an unstructured or scanned PDF into a curated structured PDF.

    Uses EasyOCR when native text is missing, then an LLM to clean and structure
    content before rendering a new PDF (curate) or embedding a searchable layer
    (searchable).
    """
    selected_mode = mode if isinstance(mode, StructureMode) else StructureMode.from_value(mode)

    pdf_doc = _open_pdf(input_file, password)
    page_texts: list[tuple[int, str]] = []
    ocr_pages: list[int] = []

    total_pages = pdf_doc.page_count
    for page_index in range(total_pages):
        if progress_callback is not None:
            progress_callback(
                stage="extracting",
                pages_done=page_index,
                pages_total=total_pages,
                message=f"Extracting page {page_index + 1} of {total_pages}",
            )
        text, used_ocr = _extract_page_text(pdf_doc[page_index], force_ocr=force_ocr)
        if used_ocr:
            ocr_pages.append(page_index)
        if redact_before_llm and text.strip():
            from docintel.services.pdf.pii import mask_pii_in_text

            text, _ = mask_pii_in_text(text)
        page_texts.append((page_index, text))

    if progress_callback is not None:
        progress_callback(
            stage="extracting",
            pages_done=total_pages,
            pages_total=total_pages,
            message="Extraction complete",
        )

    if structure_fn is not None:
        document = structure_fn(page_texts)
    else:
        from docintel.services.pdf import structure as structure_compat

        document = structure_compat.structure_document(page_texts, progress_callback=progress_callback)

    output_path = Path(output_file)
    pages_processed = pdf_doc.page_count
    if selected_mode == StructureMode.SEARCHABLE:
        render_searchable_pdf(pdf_doc, document.pages, output_path)
    else:
        pdf_doc.close()
        render_curated_pdf(document, output_path)

    return StructureResult(
        input_path=str(input_file),
        output_path=str(output_path),
        mode=selected_mode,
        pages_processed=pages_processed,
        ocr_pages=ocr_pages,
        document_title=document.title,
    )
