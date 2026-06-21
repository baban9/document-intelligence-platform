"""Shared upload helpers for document routes."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from flask import Request, request
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


def async_default_enabled() -> bool:
    from docintel.jobs.store import jobs_enabled

    if not jobs_enabled():
        return False
    return os.getenv("DOCINTEL_ASYNC_DEFAULT", "false").strip().lower() == "true"


def parse_async_flag() -> bool:
    default = "true" if async_default_enabled() else "false"
    raw = request.args.get("async", request.form.get("async", default))
    return str(raw).strip().lower() == "true"


def job_dir(job_id: str, tenant_slug: str | None = None) -> Path:
    from docintel.storage import get_storage
    from docintel.storage.tenant_path import resolve_storage_tenant_slug

    return get_storage().job_dir(job_id, tenant_slug=resolve_storage_tenant_slug(tenant_slug))
