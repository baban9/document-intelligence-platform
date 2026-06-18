"""Run extract, classify, summarize, and PII detection in one pass."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from docintel.capabilities.extraction.formats import (
    DocumentKind,
    IdentificationResult,
    extract_document_text,
    identify_document,
)
from docintel.capabilities.understanding.classify import classify_text
from docintel.services.pdf.pii import detect_pii_in_text
from docintel.services.summary import summarize_text
from docintel.services.summary.textrank import DEFAULT_SENTENCE_COUNT


@dataclass(frozen=True)
class ProcessOptions:
    sentences: int = DEFAULT_SENTENCE_COUNT
    include_summarize: bool = True
    include_pii: bool = True
    include_text: bool = False
    text_preview_chars: int = 500
    entities: list[str] | None = None
    min_score: float = 0.35

    def to_dict(self) -> dict[str, Any]:
        return {
            "sentences": self.sentences,
            "include_summarize": self.include_summarize,
            "include_pii": self.include_pii,
            "include_text": self.include_text,
            "text_preview_chars": self.text_preview_chars,
            "entities": self.entities,
            "min_score": self.min_score,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProcessOptions":
        entities = payload.get("entities")
        return cls(
            sentences=int(payload.get("sentences", DEFAULT_SENTENCE_COUNT)),
            include_summarize=bool(payload.get("include_summarize", True)),
            include_pii=bool(payload.get("include_pii", True)),
            include_text=bool(payload.get("include_text", False)),
            text_preview_chars=int(payload.get("text_preview_chars", 500)),
            entities=list(entities) if entities else None,
            min_score=float(payload.get("min_score", 0.35)),
        )


@dataclass(frozen=True)
class ProcessResult:
    filename: str
    identification: IdentificationResult
    extraction_report: dict[str, Any]
    classification: dict[str, Any]
    summary: dict[str, Any] | None
    pii: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "filename": self.filename,
            "identification": self.identification.to_dict(),
            "extraction": self.extraction_report,
            "classification": self.classification,
        }
        if self.summary is not None:
            payload["summary"] = self.summary
        if self.pii is not None:
            payload["pii"] = self.pii
        return payload


def process_document(
    path: str | Path,
    *,
    filename: str | None = None,
    content_type: str | None = None,
    options: ProcessOptions | None = None,
) -> ProcessResult:
    """Extract text and run understanding and compliance steps on a document."""
    file_path = Path(path)
    selected = options or ProcessOptions()

    identification = identify_document(
        file_path,
        filename=filename or file_path.name,
        content_type=content_type,
    )
    extraction = extract_document_text(
        file_path,
        filename=filename or file_path.name,
        content_type=content_type,
        identification=identification,
    )

    text = extraction.text
    if not text.strip():
        raise ValueError("Document contains no extractable text.")

    classification = classify_text(text).to_dict()

    summary_payload: dict[str, Any] | None = None
    if selected.include_summarize:
        summary_payload = summarize_text(text, sentence_count=selected.sentences).to_dict()

    pii_payload: dict[str, Any] | None = None
    if selected.include_pii:
        try:
            hits = detect_pii_in_text(
                text,
                entities=selected.entities,
                min_score=selected.min_score,
            )
        except RuntimeError as exc:
            raise RuntimeError(
                "PII detection requires Presidio. Install: pip install -e '.[pii]'"
            ) from exc
        findings = [hit.to_dict() for hit in hits]
        pii_payload = {"finding_count": len(findings), "findings": findings}

    if selected.include_text:
        extraction_report = extraction.to_dict()
    else:
        preview = text[: selected.text_preview_chars]
        if len(text) > selected.text_preview_chars:
            preview += "\n...(truncated)"
        extraction_report = {
            "kind": extraction.kind.value,
            "mime_type": extraction.mime_type,
            "text_preview": preview,
            "char_count": len(text),
            "metadata": extraction.metadata,
            "segment_count": len(extraction.segments),
        }

    return ProcessResult(
        filename=filename or file_path.name,
        identification=identification,
        extraction_report=extraction_report,
        classification=classification,
        summary=summary_payload,
        pii=pii_payload,
    )


def process_text(text: str, *, options: ProcessOptions | None = None) -> ProcessResult:
    """Run classify, summarize, and PII on plain text without a file upload."""
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Text must not be empty.")

    selected = options or ProcessOptions()
    classification = classify_text(cleaned).to_dict()

    summary_payload: dict[str, Any] | None = None
    if selected.include_summarize:
        summary_payload = summarize_text(cleaned, sentence_count=selected.sentences).to_dict()

    pii_payload: dict[str, Any] | None = None
    if selected.include_pii:
        try:
            hits = detect_pii_in_text(
                cleaned,
                entities=selected.entities,
                min_score=selected.min_score,
            )
        except RuntimeError as exc:
            raise RuntimeError(
                "PII detection requires Presidio. Install: pip install -e '.[pii]'"
            ) from exc
        findings = [hit.to_dict() for hit in hits]
        pii_payload = {"finding_count": len(findings), "findings": findings}

    preview = cleaned[: selected.text_preview_chars]
    if len(cleaned) > selected.text_preview_chars:
        preview += "\n...(truncated)"
    extraction_report = {
        "kind": "plain_text",
        "mime_type": "text/plain",
        "text": cleaned if selected.include_text else None,
        "text_preview": preview if not selected.include_text else cleaned,
        "char_count": len(cleaned),
        "metadata": {},
        "segment_count": 1,
    }
    if not selected.include_text:
        extraction_report.pop("text", None)

    identification = IdentificationResult(
        kind=DocumentKind.PLAIN_TEXT,
        mime_type="text/plain",
        extension=".txt",
        detected_by="text_input",
        profile=None,
    )

    return ProcessResult(
        filename="inline.txt",
        identification=identification,
        extraction_report=extraction_report,
        classification=classification,
        summary=summary_payload,
        pii=pii_payload,
    )
