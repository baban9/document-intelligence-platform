"""Render structured documents into curated or searchable PDFs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz

from docintel.services.pdf.annotator import _save_pdf
from docintel.services.pdf.structure_schema import SectionBlock, StructuredDocument, StructuredPage


@dataclass
class _RenderContext:
    pdf: fitz.Document
    page: fitz.Page
    margin: float
    y: float


def _new_page(ctx: _RenderContext) -> None:
    ctx.page = ctx.pdf.new_page()
    ctx.y = ctx.margin


def _ensure_space(ctx: _RenderContext, height: float) -> None:
    if ctx.y + height > ctx.page.rect.height - ctx.margin:
        _new_page(ctx)


def _write_line(ctx: _RenderContext, text: str, fontsize: float, indent: float = 0) -> None:
    if not text.strip():
        return
    line_height = fontsize * 1.45
    _ensure_space(ctx, line_height)
    ctx.page.insert_text(
        (ctx.margin + indent, ctx.y),
        text,
        fontsize=fontsize,
        fontname="helv",
    )
    ctx.y += line_height


def _write_wrapped_paragraph(ctx: _RenderContext, text: str, fontsize: float = 11, indent: float = 0) -> None:
    if not text.strip():
        return
    usable_width = ctx.page.rect.width - (2 * ctx.margin) - indent
    approx_chars = max(40, int(usable_width / (fontsize * 0.55)))
    words = text.split()
    line: list[str] = []
    line_len = 0
    for word in words:
        extra = len(word) + (1 if line else 0)
        if line and line_len + extra > approx_chars:
            _write_line(ctx, " ".join(line), fontsize, indent=indent)
            line = [word]
            line_len = len(word)
        else:
            line.append(word)
            line_len += extra
    if line:
        _write_line(ctx, " ".join(line), fontsize, indent=indent)
    ctx.y += 4


def _write_section(ctx: _RenderContext, section: SectionBlock) -> None:
    if section.heading:
        heading_size = max(12, 18 - section.level)
        _write_line(ctx, section.heading, heading_size)
        ctx.y += 4
    for paragraph in section.paragraphs:
        _write_wrapped_paragraph(ctx, paragraph)
    for item in section.list_items:
        _write_wrapped_paragraph(ctx, f"- {item}", indent=12)
    for table in section.tables:
        if table.headers:
            _write_line(ctx, " | ".join(table.headers), 10)
        for row in table.rows:
            _write_line(ctx, " | ".join(row), 10)
        ctx.y += 6


def render_curated_pdf(document: StructuredDocument, output_path: Path) -> None:
    """Build a new typeset PDF from structured content."""
    pdf = fitz.open()
    page = pdf.new_page()
    ctx = _RenderContext(pdf=pdf, page=page, margin=72, y=72)

    _write_line(ctx, document.title, 18)
    ctx.y += 10

    for structured_page in document.pages:
        for section in structured_page.sections:
            _write_section(ctx, section)
        if structured_page.sections:
            continue
        if structured_page.plain_text:
            for line in structured_page.plain_text.splitlines():
                _write_wrapped_paragraph(ctx, line)

    _save_pdf(pdf, output_path)


def render_searchable_pdf(
    source_doc: fitz.Document,
    pages: list[StructuredPage],
    output_path: Path,
) -> None:
    """Keep original page layout and embed an invisible curated text layer."""
    for structured_page in pages:
        if structured_page.page_index >= source_doc.page_count:
            continue
        page = source_doc[structured_page.page_index]
        text = structured_page.plain_text.strip()
        if not text:
            continue
        y = 72
        line_height = 13
        for line in text.splitlines():
            cleaned = line.strip()
            if not cleaned:
                continue
            if y > page.rect.height - 72:
                break
            page.insert_text(
                (72, y),
                cleaned,
                fontsize=10,
                fontname="helv",
                render_mode=3,
            )
            y += line_height

    _save_pdf(source_doc, output_path)
