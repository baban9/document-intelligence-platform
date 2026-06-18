"""Registry of supported document formats and capabilities."""

from __future__ import annotations

import mimetypes

from docintel.capabilities.extraction.formats.models import DocumentKind, DocumentProfile

_PROFILES: tuple[DocumentProfile, ...] = (
    DocumentProfile(
        kind=DocumentKind.PDF,
        mime_type="application/pdf",
        extensions=(".pdf",),
        label="PDF",
        supports_pdf_pipeline=True,
        supports_text_extraction=True,
    ),
    DocumentProfile(
        kind=DocumentKind.DOCX,
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        extensions=(".docx",),
        label="Word document",
        supports_pdf_pipeline=False,
        supports_text_extraction=True,
    ),
    DocumentProfile(
        kind=DocumentKind.XLSX,
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        extensions=(".xlsx", ".xlsm"),
        label="Excel workbook",
        supports_pdf_pipeline=False,
        supports_text_extraction=True,
    ),
    DocumentProfile(
        kind=DocumentKind.PPTX,
        mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        extensions=(".pptx",),
        label="PowerPoint presentation",
        supports_pdf_pipeline=False,
        supports_text_extraction=True,
    ),
    DocumentProfile(
        kind=DocumentKind.CSV,
        mime_type="text/csv",
        extensions=(".csv",),
        label="CSV spreadsheet",
        supports_pdf_pipeline=False,
        supports_text_extraction=True,
    ),
    DocumentProfile(
        kind=DocumentKind.PLAIN_TEXT,
        mime_type="text/plain",
        extensions=(".txt", ".md", ".log"),
        label="Plain text",
        supports_pdf_pipeline=False,
        supports_text_extraction=True,
    ),
    DocumentProfile(
        kind=DocumentKind.JSON,
        mime_type="application/json",
        extensions=(".json",),
        label="JSON document",
        supports_pdf_pipeline=False,
        supports_text_extraction=True,
    ),
)

_EXTENSION_INDEX: dict[str, DocumentProfile] = {}
_MIME_INDEX: dict[str, DocumentProfile] = {}
for _profile in _PROFILES:
    for _extension in _profile.extensions:
        _EXTENSION_INDEX[_extension.lower()] = _profile
    _MIME_INDEX[_profile.mime_type.lower()] = _profile

# Common browser and client aliases.
_MIME_INDEX["text/comma-separated-values"] = _MIME_INDEX["text/csv"]

for _extension, _guess in ((".txt", "text/plain"), (".csv", "text/csv"), (".json", "application/json")):
    mimetypes.add_type(_guess, _extension)


def list_supported_types() -> list[dict]:
    return [profile.to_dict() for profile in _PROFILES]


def get_profile(kind: DocumentKind) -> DocumentProfile | None:
    for profile in _PROFILES:
        if profile.kind == kind:
            return profile
    return None


def profiles_for_kind(kind: DocumentKind) -> DocumentProfile | None:
    return get_profile(kind)


def profile_for_extension(extension: str) -> DocumentProfile | None:
    normalized = extension.lower()
    if not normalized.startswith("."):
        normalized = f".{normalized}"
    return _EXTENSION_INDEX.get(normalized)


def profile_for_mime(mime_type: str | None) -> DocumentProfile | None:
    if not mime_type:
        return None
    cleaned = mime_type.split(";", 1)[0].strip().lower()
    return _MIME_INDEX.get(cleaned)
