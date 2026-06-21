"""Interactive PDF editor session: preview pages and apply LLM edits."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz

from docintel.capabilities.extraction.ocr import build_indexed_text, extract_page_ocr, page_has_native_text
from docintel.capabilities.pdf.page_edit_llm import edit_page_text_with_llm

WORKING_FILENAME = "working.pdf"
PREVIEW_PREFIX = "preview_page_"
SESSION_FILENAME = "editor_session.json"


@dataclass
class EditorSession:
    session_id: str
    work_dir: Path
    source_filename: str
    page_count: int
    pages_edited: list[int] = field(default_factory=list)

    @property
    def working_path(self) -> Path:
        return self.work_dir / WORKING_FILENAME

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "filename": self.source_filename,
            "page_count": self.page_count,
            "pages_edited": sorted(set(self.pages_edited)),
            "download_url": f"/v1/pdf/files/{self.session_id}/{WORKING_FILENAME}",
        }

    def save(self) -> None:
        payload = {
            "session_id": self.session_id,
            "filename": self.source_filename,
            "page_count": self.page_count,
            "pages_edited": sorted(set(self.pages_edited)),
        }
        (self.work_dir / SESSION_FILENAME).write_text(json.dumps(payload), encoding="utf-8")


def _load_session(work_dir: Path, session_id: str) -> EditorSession:
    meta_path = work_dir / SESSION_FILENAME
    if not meta_path.is_file():
        raise FileNotFoundError(f"Editor session not found: {session_id}")
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    return EditorSession(
        session_id=str(payload["session_id"]),
        work_dir=work_dir,
        source_filename=str(payload["filename"]),
        page_count=int(payload["page_count"]),
        pages_edited=[int(page) for page in payload.get("pages_edited", [])],
    )


def create_editor_session(input_path: Path, work_dir: Path, session_id: str, filename: str) -> EditorSession:
    """Copy the upload into a mutable working PDF and initialize session metadata."""
    work_dir.mkdir(parents=True, exist_ok=True)
    working_path = work_dir / WORKING_FILENAME
    shutil.copy2(input_path, working_path)

    pdf = fitz.open(working_path)
    page_count = pdf.page_count
    pdf.close()

    session = EditorSession(
        session_id=session_id,
        work_dir=work_dir,
        source_filename=filename,
        page_count=page_count,
    )
    session.save()
    return session


def open_editor_session(work_dir: Path, session_id: str) -> EditorSession:
    """Load an existing editor session from disk."""
    return _load_session(work_dir, session_id)


def _preview_path(work_dir: Path, page_index: int) -> Path:
    return work_dir / f"{PREVIEW_PREFIX}{page_index}.png"


def render_page_preview(pdf_path: Path, page_index: int, output_path: Path) -> None:
    """Render one PDF page to a PNG preview."""
    pdf = fitz.open(pdf_path)
    try:
        if page_index < 0 or page_index >= pdf.page_count:
            raise ValueError(f"Page index out of range: {page_index}")
        page = pdf[page_index]
        matrix = fitz.Matrix(1.75, 1.75)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pixmap.save(output_path)
    finally:
        pdf.close()


def _ensure_ocr_stack() -> None:
    try:
        import easyocr  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "OCR dependencies are not installed. Run: pip install -e '.[ocr]'"
        ) from exc


def extract_page_text(pdf_path: Path, page_index: int, *, force_ocr: bool = False) -> tuple[str, str]:
    """Return page text and source label (native or ocr)."""
    pdf = fitz.open(pdf_path)
    try:
        if page_index < 0 or page_index >= pdf.page_count:
            raise ValueError(f"Page index out of range: {page_index}")
        page = pdf[page_index]
        use_ocr = force_ocr or not page_has_native_text(page)
        if use_ocr:
            _ensure_ocr_stack()
            spans = extract_page_ocr(page)
            text, _ = build_indexed_text(spans)
            return text, "ocr"
        return page.get_text("text"), "native"
    finally:
        pdf.close()


def rewrite_page_text(pdf_path: Path, page_index: int, new_text: str) -> None:
    """Replace visible page content with rewritten text (text-heavy pages)."""
    pdf = fitz.open(pdf_path)
    try:
        if page_index < 0 or page_index >= pdf.page_count:
            raise ValueError(f"Page index out of range: {page_index}")
        page = pdf[page_index]
        rect = page.rect
        margin = 54.0
        shape = page.new_shape()
        shape.draw_rect(rect)
        shape.finish(color=(1, 1, 1), fill=(1, 1, 1))
        shape.commit()
        inner = fitz.Rect(margin, margin, rect.width - margin, rect.height - margin)
        page.insert_textbox(
            inner,
            new_text,
            fontsize=11,
            fontname="helv",
            align=fitz.TEXT_ALIGN_LEFT,
        )
        pdf.saveIncr()
    finally:
        pdf.close()


def page_state(session: EditorSession, page_index: int) -> dict[str, Any]:
    """Return page text and ensure a PNG preview exists."""
    if page_index < 0 or page_index >= session.page_count:
        raise ValueError(f"Page index out of range: {page_index}")

    preview = _preview_path(session.work_dir, page_index)
    if not preview.is_file():
        render_page_preview(session.working_path, page_index, preview)

    text, text_source = extract_page_text(session.working_path, page_index)
    return {
        "session_id": session.session_id,
        "page": page_index,
        "page_count": session.page_count,
        "text": text,
        "text_source": text_source,
        "preview_url": f"/v1/pdf/editor/session/{session.session_id}/pages/{page_index}/preview",
        "pages_edited": sorted(set(session.pages_edited)),
        "download_url": session.to_dict()["download_url"],
    }


def apply_page_edit(session: EditorSession, page_index: int, instruction: str) -> dict[str, Any]:
    """Use the LLM to edit one page and refresh the working PDF."""
    current_text, _ = extract_page_text(session.working_path, page_index)
    edited_text, changes_summary = edit_page_text_with_llm(page_index, current_text, instruction)
    rewrite_page_text(session.working_path, page_index, edited_text)
    if page_index not in session.pages_edited:
        session.pages_edited.append(page_index)
    session.save()

    preview = _preview_path(session.work_dir, page_index)
    render_page_preview(session.working_path, page_index, preview)

    return {
        **page_state(session, page_index),
        "instruction": instruction.strip(),
        "changes_summary": changes_summary,
        "edited_text": edited_text,
    }
