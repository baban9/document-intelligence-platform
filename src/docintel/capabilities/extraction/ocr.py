"""EasyOCR extraction for scanned PDF pages."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

import fitz

from docintel.capabilities.compliance.presets import MIN_NATIVE_TEXT_CHARS, OCR_RENDER_SCALE

if TYPE_CHECKING:
    import numpy as np


@dataclass(frozen=True)
class OCRSpan:
    """A text region detected by OCR with PDF coordinates."""

    text: str
    rect: fitz.Rect
    confidence: float
    char_start: int = 0
    char_end: int = 0


@dataclass(frozen=True)
class IndexedSpan:
    """Character offsets mapped to a PDF rectangle."""

    char_start: int
    char_end: int
    rect: fitz.Rect


def page_has_native_text(page: fitz.Page, min_chars: int = MIN_NATIVE_TEXT_CHARS) -> bool:
    """Return True when the PDF text layer has enough content to skip OCR."""
    return len(page.get_text("text").strip()) >= min_chars


@lru_cache(maxsize=1)
def _easyocr_reader():
    import easyocr

    return easyocr.Reader(["en"], gpu=False, verbose=False)


def _pixmap_to_array(pix: fitz.Pixmap) -> np.ndarray:
    import numpy as np

    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)


def extract_page_ocr(page: fitz.Page, scale: float = OCR_RENDER_SCALE) -> list[OCRSpan]:
    """Run EasyOCR on a PDF page and return text boxes in PDF coordinates."""
    matrix = fitz.Matrix(scale, scale)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    image = _pixmap_to_array(pixmap)

    reader = _easyocr_reader()
    detections = reader.readtext(image)

    spans: list[OCRSpan] = []
    for bbox, text, confidence in detections:
        cleaned = str(text).strip()
        if not cleaned:
            continue
        xs = [point[0] for point in bbox]
        ys = [point[1] for point in bbox]
        rect = fitz.Rect(
            min(xs) / scale,
            min(ys) / scale,
            max(xs) / scale,
            max(ys) / scale,
        )
        spans.append(OCRSpan(text=cleaned, rect=rect, confidence=float(confidence)))

    return spans


def build_indexed_text(spans: list[OCRSpan]) -> tuple[str, list[IndexedSpan]]:
    """Join OCR spans into page text and track character offsets per box."""
    chunks: list[str] = []
    indexed: list[IndexedSpan] = []
    position = 0

    for index, span in enumerate(spans):
        if index > 0:
            chunks.append(" ")
            position += 1
        start = position
        chunks.append(span.text)
        position += len(span.text)
        indexed.append(IndexedSpan(char_start=start, char_end=position, rect=span.rect))

    return "".join(chunks), indexed


def rects_for_char_range(start: int, end: int, indexed: list[IndexedSpan]) -> list[fitz.Rect]:
    """Map a character span to one or more PDF rectangles."""
    rects: list[fitz.Rect] = []
    for item in indexed:
        if item.char_end <= start or item.char_start >= end:
            continue
        rects.append(item.rect)
    return rects


def merge_rects(rects: list[fitz.Rect]) -> fitz.Rect | None:
    """Merge rectangles into a single bounding box."""
    if not rects:
        return None
    return fitz.Rect(
        min(rect.x0 for rect in rects),
        min(rect.y0 for rect in rects),
        max(rect.x1 for rect in rects),
        max(rect.y1 for rect in rects),
    )


def embed_invisible_text_layer(page: fitz.Page, spans: list[OCRSpan]) -> None:
    """Add a searchable text layer from OCR spans (invisible rendering)."""
    for span in spans:
        page.insert_text(
            (span.rect.x0, span.rect.y1),
            span.text,
            fontsize=max(6, span.rect.height * 0.8),
            render_mode=3,
        )
