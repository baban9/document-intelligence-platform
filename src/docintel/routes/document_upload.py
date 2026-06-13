"""Shared upload helpers for document routes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from flask import Request
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from docintel.capabilities.extraction.formats import DocumentKind, IdentificationResult, identify_document


@dataclass(frozen=True)
class SavedUpload:
    path: Path
    filename: str
    content_type: str | None
    identification: IdentificationResult


def read_upload(request: Request, field_name: str = "file") -> FileStorage | None:
    upload = request.files.get(field_name)
    if upload is None or not upload.filename:
        return None
    return upload


def save_upload(upload: FileStorage, destination_dir: Path) -> SavedUpload:
    destination_dir.mkdir(parents=True, exist_ok=True)
    filename = secure_filename(upload.filename)
    path = destination_dir / filename
    upload.save(path)
    identification = identify_document(
        path,
        filename=filename,
        content_type=upload.content_type,
    )
    return SavedUpload(
        path=path,
        filename=filename,
        content_type=upload.content_type,
        identification=identification,
    )


def pdf_required_message(identification: IdentificationResult) -> dict:
    return {
        "error": (
            f"This endpoint requires a PDF file. Detected kind: {identification.kind.value} "
            f"({identification.mime_type})."
        ),
        "detected": identification.to_dict(),
        "hint": "Use GET /v1/documents/types and POST /v1/documents/extract-text for office documents.",
    }


def is_pdf_upload(identification: IdentificationResult) -> bool:
    return identification.kind is DocumentKind.PDF
