"""Identify document type from filename, MIME header, and file content."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from docintel.capabilities.extraction.formats.models import DocumentKind, IdentificationResult
from docintel.capabilities.extraction.formats.registry import (
    profile_for_extension,
    profile_for_mime,
    profiles_for_kind,
)


def _extension_from_name(filename: str | None) -> str | None:
    if not filename or "." not in filename:
        return None
    return Path(filename).suffix.lower()


def _sniff_zip_kind(path: Path) -> DocumentKind | None:
    if not zipfile.is_zipfile(path):
        return None
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile:
        return None

    if any(name.startswith("word/") for name in names):
        return DocumentKind.DOCX
    if any(name.startswith("ppt/") for name in names):
        return DocumentKind.PPTX
    if any(name.startswith("xl/") for name in names):
        return DocumentKind.XLSX
    return None


def _sniff_content_kind(path: Path) -> DocumentKind | None:
    with path.open("rb") as handle:
        header = handle.read(4096)

    if header.startswith(b"%PDF"):
        return DocumentKind.PDF

    zip_kind = _sniff_zip_kind(path)
    if zip_kind is not None:
        return zip_kind

    stripped = header.lstrip()
    if stripped.startswith(b"{") or stripped.startswith(b"["):
        try:
            json.loads(stripped.decode("utf-8"))
            return DocumentKind.JSON
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass

    try:
        sample = header.decode("utf-8")
    except UnicodeDecodeError:
        return None

    if _looks_like_csv(sample):
        return DocumentKind.CSV
    if sample.strip():
        return DocumentKind.PLAIN_TEXT
    return None


def _looks_like_csv(sample: str) -> bool:
    lines = [line for line in sample.splitlines() if line.strip()]
    if len(lines) < 1:
        return False
    if len(lines) == 1:
        return "," in lines[0] or ";" in lines[0] or "\t" in lines[0]
    delimiter_hits = sum(
        1 for line in lines[:5] if ("," in line) or (";" in line) or ("\t" in line)
    )
    return delimiter_hits >= 2


def _requires_content_confirmation(kind: DocumentKind) -> bool:
    return kind in {DocumentKind.PDF, DocumentKind.DOCX, DocumentKind.XLSX, DocumentKind.PPTX}


def _build_result(
    kind: DocumentKind,
    *,
    extension: str | None,
    detected_by: str,
    mime_type: str | None = None,
) -> IdentificationResult:
    profile = profiles_for_kind(kind)
    resolved_mime = mime_type or (profile.mime_type if profile else "application/octet-stream")
    return IdentificationResult(
        kind=kind,
        mime_type=resolved_mime,
        extension=extension,
        detected_by=detected_by,
        profile=profile,
    )


def identify_document(
    path: str | Path,
    *,
    filename: str | None = None,
    content_type: str | None = None,
) -> IdentificationResult:
    """Resolve the best document kind for an on-disk upload."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Document not found: {file_path}")

    extension = _extension_from_name(filename or file_path.name)
    content_kind = _sniff_content_kind(file_path)

    mime_profile = profile_for_mime(content_type)
    extension_profile = profile_for_extension(extension) if extension else None

    if content_kind is not None and content_kind is not DocumentKind.UNKNOWN:
        detected_by = "content"
        if extension_profile is not None and extension_profile.kind != content_kind:
            detected_by = "content_override"
        return _build_result(
            content_kind,
            extension=extension,
            detected_by=detected_by,
        )

    if mime_profile is not None and not _requires_content_confirmation(mime_profile.kind):
        return _build_result(
            mime_profile.kind,
            extension=extension,
            detected_by="mime_type",
            mime_type=mime_profile.mime_type,
        )

    if extension_profile is not None and not _requires_content_confirmation(extension_profile.kind):
        return _build_result(
            extension_profile.kind,
            extension=extension,
            detected_by="extension",
            mime_type=extension_profile.mime_type,
        )

    if extension_profile is not None and _requires_content_confirmation(extension_profile.kind):
        return IdentificationResult(
            kind=DocumentKind.UNKNOWN,
            mime_type=content_type or "application/octet-stream",
            extension=extension,
            detected_by="unverified_extension",
            profile=None,
        )

    if mime_profile is not None and _requires_content_confirmation(mime_profile.kind):
        return IdentificationResult(
            kind=DocumentKind.UNKNOWN,
            mime_type=mime_profile.mime_type,
            extension=extension,
            detected_by="unverified_mime_type",
            profile=None,
        )

    return IdentificationResult(
        kind=DocumentKind.UNKNOWN,
        mime_type=content_type or "application/octet-stream",
        extension=extension,
        detected_by="unknown",
        profile=None,
    )
