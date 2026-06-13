"""Core PDF annotation engine."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import fitz

from docintel.capabilities.pdf.models import Action, ProcessResult
from docintel.capabilities.pdf.search import search_for_text


def _normalize_pages(pages: Sequence[int | str] | None) -> list[int] | None:
    if pages is None:
        return None
    return [int(page) for page in pages]


def _open_pdf(path: str | Path, password: str | None = None) -> fitz.Document:
    pdf_path = Path(path)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pdf_doc = fitz.open(pdf_path)
    if pdf_doc.is_encrypted:
        if not password or not pdf_doc.authenticate(password):
            pdf_doc.close()
            raise PermissionError(f"PDF is encrypted: {pdf_path}")
    return pdf_doc


def _save_pdf(pdf_doc: fitz.Document, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_doc.save(output_path)
    pdf_doc.close()


def redact_matches(page: fitz.Page, matched_values: Iterable[str]) -> int:
    count = 0
    for value in matched_values:
        areas = page.search_for(value)
        if not areas:
            continue
        count += 1
        for area in areas:
            page.add_redact_annot(area, text=" ", fill=(0, 0, 0))
    if count:
        page.apply_redactions()
    return count


def frame_matches(page: fitz.Page, matched_values: Iterable[str]) -> int:
    count = 0
    for value in matched_values:
        areas = page.search_for(value)
        if not areas:
            continue
        count += 1
        for area in areas:
            annot = page.add_rect_annot(area)
            annot.set_colors(stroke=fitz.utils.getColor("red"))
            annot.update()
    return count


def highlight_matches(page: fitz.Page, matched_values: Iterable[str], action: Action) -> int:
    count = 0
    for value in matched_values:
        areas = page.search_for(value)
        if not areas:
            continue
        count += 1
        if action == Action.SQUIGGLY:
            annot = page.add_squiggly_annot(areas)
        elif action == Action.UNDERLINE:
            annot = page.add_underline_annot(areas)
        elif action == Action.STRIKEOUT:
            annot = page.add_strikeout_annot(areas)
        else:
            annot = page.add_highlight_annot(areas)
        annot.update()
    return count


def remove_annotations(
    input_file: str | Path,
    output_file: str | Path,
    pages: Sequence[int] | None = None,
    password: str | None = None,
) -> ProcessResult:
    pdf_doc = _open_pdf(input_file, password)
    removed = 0
    pages_processed = 0
    page_list = _normalize_pages(pages)

    for page_index in range(pdf_doc.page_count):
        if page_list is not None and page_index not in page_list:
            continue
        pages_processed += 1
        page = pdf_doc[page_index]
        annot = page.first_annot
        while annot:
            removed += 1
            next_annot = annot.next
            page.delete_annot(annot)
            annot = next_annot

    _save_pdf(pdf_doc, Path(output_file))
    return ProcessResult(
        input_path=str(input_file),
        output_path=str(output_file),
        action=Action.REMOVE,
        matches=removed,
        pages_processed=pages_processed,
    )


class PDFAnnotator:
    """High-level API for annotating PDF files."""

    def __init__(
        self,
        pattern: str,
        action: Action | str = Action.HIGHLIGHT,
        pages: Sequence[int | str] | None = None,
        password: str | None = None,
    ):
        self.pattern = pattern
        self.action = action if isinstance(action, Action) else Action.from_value(action)
        self.pages = _normalize_pages(pages)
        self.password = password

    def annotate(self, input_file: str | Path, output_file: str | Path) -> ProcessResult:
        return annotate_pdf(
            input_file=input_file,
            output_file=output_file,
            pattern=self.pattern,
            action=self.action,
            pages=self.pages,
            password=self.password,
        )


def annotate_pdf(
    input_file: str | Path,
    output_file: str | Path,
    pattern: str,
    action: Action | str = Action.HIGHLIGHT,
    pages: Sequence[int | str] | None = None,
    password: str | None = None,
) -> ProcessResult:
    """Search a PDF and apply the requested annotation action."""
    selected_action = action if isinstance(action, Action) else Action.from_value(action)
    page_list = _normalize_pages(pages)

    if selected_action == Action.REMOVE:
        return remove_annotations(input_file, output_file, page_list, password)

    pdf_doc = _open_pdf(input_file, password)
    total_matches = 0
    pages_processed = 0

    for page_index in range(pdf_doc.page_count):
        if page_list is not None and page_index not in page_list:
            continue
        pages_processed += 1
        page = pdf_doc[page_index]
        page_lines = page.get_text("text").split("\n")
        matched_values = list(search_for_text(page_lines, pattern))
        if not matched_values:
            continue

        if selected_action == Action.REDACT:
            total_matches += redact_matches(page, matched_values)
        elif selected_action == Action.FRAME:
            total_matches += frame_matches(page, matched_values)
        else:
            total_matches += highlight_matches(page, matched_values, selected_action)

    _save_pdf(pdf_doc, Path(output_file))
    return ProcessResult(
        input_path=str(input_file),
        output_path=str(output_file),
        action=selected_action,
        matches=total_matches,
        pages_processed=pages_processed,
    )
