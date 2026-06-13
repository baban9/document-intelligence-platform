"""Shared types for multi-format document handling."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DocumentKind(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    CSV = "csv"
    PLAIN_TEXT = "plain_text"
    JSON = "json"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DocumentProfile:
    kind: DocumentKind
    mime_type: str
    extensions: tuple[str, ...]
    label: str
    supports_pdf_pipeline: bool
    supports_text_extraction: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "mime_type": self.mime_type,
            "extensions": list(self.extensions),
            "label": self.label,
            "capabilities": {
                "pdf_pipeline": self.supports_pdf_pipeline,
                "text_extraction": self.supports_text_extraction,
            },
        }


@dataclass(frozen=True)
class IdentificationResult:
    kind: DocumentKind
    mime_type: str
    extension: str | None
    detected_by: str
    profile: DocumentProfile | None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "kind": self.kind.value,
            "mime_type": self.mime_type,
            "extension": self.extension,
            "detected_by": self.detected_by,
        }
        if self.profile is not None:
            payload["profile"] = self.profile.to_dict()
        return payload


@dataclass(frozen=True)
class ExtractionResult:
    kind: DocumentKind
    mime_type: str
    text: str
    segments: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "mime_type": self.mime_type,
            "text": self.text,
            "segments": self.segments,
            "metadata": self.metadata,
        }
