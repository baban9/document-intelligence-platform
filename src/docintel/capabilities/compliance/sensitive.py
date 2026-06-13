"""Scanned and native PDF sensitive-data detection with OCR + Presidio."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol, Sequence

import fitz

from docintel.services.pdf.annotator import _open_pdf, _save_pdf, highlight_matches, redact_matches
from docintel.services.pdf.models import Action, PIIDetectionResult
from docintel.services.pdf.ocr import (
    build_indexed_text,
    embed_invisible_text_layer,
    extract_page_ocr,
    merge_rects,
    page_has_native_text,
    rects_for_char_range,
)
from docintel.capabilities.compliance.pii import PIIHit
from docintel.services.pdf.search import search_for_text


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
        import presidio_analyzer  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "OCR and Presidio dependencies are not installed. "
            "Run: pip install -e '.[ocr]' && python -m spacy download en_core_web_sm"
        ) from exc


def _apply_rect_action(page: fitz.Page, rect: fitz.Rect, action: Action) -> bool:
    if action == Action.REDACT:
        page.add_redact_annot(rect, text=" ", fill=(0, 0, 0))
        return True
    if action == Action.FRAME:
        annot = page.add_rect_annot(rect)
        annot.set_colors(stroke=fitz.utils.getColor("red"))
        annot.update()
        return True
    if action == Action.UNDERLINE:
        annot = page.add_underline_annot([rect])
        annot.update()
        return True
    if action == Action.SQUIGGLY:
        annot = page.add_squiggly_annot([rect])
        annot.update()
        return True
    if action == Action.STRIKEOUT:
        annot = page.add_strikeout_annot([rect])
        annot.update()
        return True

    annot = page.add_highlight_annot([rect])
    annot.update()
    return True


def _annotate_rects(page: fitz.Page, rects: list[fitz.Rect], action: Action) -> int:
    applied = 0
    for rect in rects:
        if _apply_rect_action(page, rect, action):
            applied += 1
    if action == Action.REDACT and applied:
        page.apply_redactions()
    return applied


def _native_rects_for_hit(page: fitz.Page, hit: PIIHit) -> list[fitz.Rect]:
    return page.search_for(hit.text)


def _ocr_rects_for_hit(hit: PIIHit, indexed) -> list[fitz.Rect]:
    rects = rects_for_char_range(hit.start, hit.end, indexed)
    merged = merge_rects(rects)
    return [merged] if merged else []


def _regex_hits(page_text: str, pattern: str) -> list[PIIHit]:
    hits: list[PIIHit] = []
    for match in re.finditer(pattern, page_text, flags=re.IGNORECASE):
        hits.append(
            PIIHit(
                entity_type="REGEX",
                text=match.group(0),
                start=match.start(),
                end=match.end(),
                score=1.0,
            )
        )
    return hits


def detect_sensitive_pdf(
    input_file: str | Path,
    output_file: str | Path,
    *,
    entities: Sequence[str] | None = None,
    action: Action | str = Action.HIGHLIGHT,
    force_ocr: bool = False,
    add_text_layer: bool = True,
    pattern: str | None = None,
    min_score: float = 0.35,
    password: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> PIIDetectionResult:
    """
    Detect sensitive information with Presidio (and optional regex), annotate PDF.

    Uses native PDF text when available. Falls back to EasyOCR for scanned pages.
    """
    from docintel.services.pdf import sensitive as sensitive_compat

    sensitive_compat._ensure_ocr_stack()
    selected_action = action if isinstance(action, Action) else Action.from_value(action)
    if selected_action == Action.REMOVE:
        raise ValueError("Action 'Remove' is not supported for sensitive detection.")

    pdf_doc = _open_pdf(input_file, password)
    total_annotations = 0
    pages_processed = 0
    ocr_pages: list[int] = []
    findings: list[dict] = []

    total_pages = pdf_doc.page_count
    for page_index in range(total_pages):
        if progress_callback is not None:
            progress_callback(
                stage="detecting",
                pages_done=page_index,
                pages_total=total_pages,
                message=f"Processing page {page_index + 1} of {total_pages}",
            )
        page = pdf_doc[page_index]
        pages_processed += 1
        use_ocr = force_ocr or not page_has_native_text(page)

        if use_ocr:
            ocr_pages.append(page_index)
            ocr_spans = extract_page_ocr(page)
            if add_text_layer and ocr_spans:
                embed_invisible_text_layer(page, ocr_spans)
            page_text, indexed = build_indexed_text(ocr_spans)
        else:
            ocr_spans = []
            indexed = []
            page_text = page.get_text("text")

        hits = sensitive_compat.detect_pii_in_text(page_text, entities=entities, min_score=min_score)
        if pattern:
            hits.extend(_regex_hits(page_text, pattern))

        for hit in hits:
            if use_ocr:
                rects = _ocr_rects_for_hit(hit, indexed)
            else:
                rects = _native_rects_for_hit(page, hit)

            if not rects:
                continue

            total_annotations += _annotate_rects(page, rects, selected_action)
            findings.append(
                {
                    "page": page_index,
                    "entity_type": hit.entity_type,
                    "text": hit.text,
                    "score": round(hit.score, 4),
                    "ocr_used": use_ocr,
                }
            )

        # Legacy regex path for native PDFs when pattern matches line fragments
        if pattern and not use_ocr:
            matched_values = list(search_for_text(page_text.split("\n"), pattern))
            if matched_values:
                if selected_action == Action.REDACT:
                    total_annotations += redact_matches(page, matched_values)
                else:
                    total_annotations += highlight_matches(page, matched_values, selected_action)

    if progress_callback is not None:
        progress_callback(
            stage="detecting",
            pages_done=total_pages,
            pages_total=total_pages,
            message="Detection complete",
        )

    _save_pdf(pdf_doc, Path(output_file))
    return PIIDetectionResult(
        input_path=str(input_file),
        output_path=str(output_file),
        action=selected_action,
        matches=total_annotations,
        pages_processed=pages_processed,
        ocr_pages=ocr_pages,
        findings=findings,
    )
