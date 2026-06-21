"""Page-by-page PDF extraction and analysis for large documents."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import fitz

from docintel.capabilities.extraction.formats.models import ExtractionResult, IdentificationResult

PAGE_SEPARATOR = "\n\n"
DEFAULT_LARGE_PDF_PAGE_THRESHOLD = 50
DEFAULT_MAX_FULL_TEXT_CHARS = 250_000
DEFAULT_ANALYSIS_SAMPLE_CHARS = 120_000


def large_pdf_page_threshold() -> int:
    raw = os.getenv("DOCINTEL_LARGE_PDF_PAGE_THRESHOLD", str(DEFAULT_LARGE_PDF_PAGE_THRESHOLD)).strip()
    try:
        return max(int(raw), 1)
    except ValueError:
        return DEFAULT_LARGE_PDF_PAGE_THRESHOLD


def max_full_text_chars() -> int:
    raw = os.getenv("DOCINTEL_MAX_FULL_TEXT_CHARS", str(DEFAULT_MAX_FULL_TEXT_CHARS)).strip()
    try:
        return max(int(raw), 10_000)
    except ValueError:
        return DEFAULT_MAX_FULL_TEXT_CHARS


def analysis_sample_chars() -> int:
    raw = os.getenv("DOCINTEL_PDF_ANALYSIS_SAMPLE_CHARS", str(DEFAULT_ANALYSIS_SAMPLE_CHARS)).strip()
    try:
        return max(int(raw), 5_000)
    except ValueError:
        return DEFAULT_ANALYSIS_SAMPLE_CHARS


@dataclass(frozen=True)
class PageText:
    page: int
    text: str
    char_start: int
    char_end: int


def is_large_pdf(*, page_count: int, char_count: int) -> bool:
    """True when the document should use paginated processing."""
    return page_count >= large_pdf_page_threshold() or char_count >= max_full_text_chars()


def iter_pdf_pages(path: Path) -> Iterator[PageText]:
    """Yield one page at a time with global character offsets (non-empty pages joined with \\n\\n)."""
    pdf_doc = fitz.open(path)
    try:
        offset = 0
        first = True
        for page_index in range(pdf_doc.page_count):
            text = pdf_doc[page_index].get_text("text").strip()
            if text:
                if not first:
                    offset += len(PAGE_SEPARATOR)
                char_start = offset
                offset += len(text)
                first = False
            else:
                char_start = offset
            yield PageText(page=page_index, text=text, char_start=char_start, char_end=offset)
    finally:
        pdf_doc.close()


def read_pdf_pages(path: Path) -> list[PageText]:
    return list(iter_pdf_pages(path))


def build_monolithic_text(pages: list[PageText]) -> str:
    return PAGE_SEPARATOR.join(page.text for page in pages if page.text)


def total_char_count(pages: list[PageText]) -> int:
    if not pages:
        return 0
    non_empty = [page for page in pages if page.text]
    if not non_empty:
        return 0
    return sum(len(page.text) for page in non_empty) + len(PAGE_SEPARATOR) * (len(non_empty) - 1)


def pages_to_segments(pages: list[PageText]) -> list[dict[str, Any]]:
    return [{"page": page.page, "text": page.text} for page in pages]


def sample_pages_for_analysis(pages: list[PageText], max_chars: int | None = None) -> str:
    """Build a bounded text sample from first, middle, and last pages for classify/summary."""
    limit = max_chars if max_chars is not None else analysis_sample_chars()
    non_empty = [page for page in pages if page.text.strip()]
    if not non_empty:
        return ""

    if len(non_empty) <= 8:
        sample = build_monolithic_text(non_empty)
        return sample[:limit]

    picks: list[PageText] = []
    picks.extend(non_empty[:3])
    picks.append(non_empty[len(non_empty) // 3])
    picks.append(non_empty[(2 * len(non_empty)) // 3])
    picks.extend(non_empty[-2:])

    seen: set[int] = set()
    ordered: list[PageText] = []
    for page in picks:
        if page.page not in seen:
            seen.add(page.page)
            ordered.append(page)

    parts: list[str] = []
    size = 0
    for page in ordered:
        chunk = page.text.strip()
        if not chunk:
            continue
        if size and size + len(chunk) + 2 > limit:
            remaining = limit - size - 2
            if remaining > 200:
                parts.append(chunk[:remaining])
            break
        parts.append(chunk)
        size += len(chunk) + (2 if parts else 0)
    return PAGE_SEPARATOR.join(parts)


def extract_pdf_document(path: Path, identification: IdentificationResult) -> ExtractionResult:
    """Extract PDF text page-by-page; avoid monolithic strings for large books."""
    pages = read_pdf_pages(path)
    page_count = len(pages)
    char_count = total_char_count(pages)
    segments = pages_to_segments(pages)
    large = is_large_pdf(page_count=page_count, char_count=char_count)

    if large:
        text = sample_pages_for_analysis(pages)
        metadata: dict[str, Any] = {
            "page_count": page_count,
            "char_count": char_count,
            "large_document": True,
            "processing_mode": "paginated",
            "analysis_sample_chars": len(text),
        }
    else:
        text = build_monolithic_text(pages)
        metadata = {
            "page_count": page_count,
            "char_count": len(text),
            "large_document": False,
            "processing_mode": "monolithic",
        }

    if not text.strip() and not any(page.text.strip() for page in pages):
        text = ""

    return ExtractionResult(
        kind=identification.kind,
        mime_type=identification.mime_type,
        text=text,
        segments=segments,
        metadata=metadata,
    )


def detect_pii_in_pdf_segments(
    segments: list[dict[str, Any]],
    *,
    entities: list[str] | None = None,
    language: str = "en",
    min_score: float = 0.35,
) -> list[dict[str, Any]]:
    """Run Presidio on each page separately and attach global offsets and page numbers."""
    from docintel.services.pdf.pii import detect_pii_in_text

    findings: list[dict[str, Any]] = []
    offset = 0
    first = True
    for segment in segments:
        text = str(segment.get("text") or "")
        page = int(segment.get("page", 0))
        if not text.strip():
            continue
        if not first:
            offset += len(PAGE_SEPARATOR)
        page_start = offset
        hits = detect_pii_in_text(
            text,
            entities=entities,
            language=language,
            min_score=min_score,
        )
        for hit in hits:
            item = hit.to_dict()
            item["page"] = page
            item["start"] = page_start + int(hit.start)
            item["end"] = page_start + int(hit.end)
            findings.append(item)
        offset += len(text)
        first = False
    return findings
