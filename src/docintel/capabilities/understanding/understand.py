"""Document understanding: classification, summary, and PII snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from docintel.capabilities.compliance.pii import detect_pii_in_text
from docintel.capabilities.extraction.formats import extract_document_text, identify_document
from docintel.capabilities.understanding.classify import classify_text
from docintel.services.summary import summarize_text
from docintel.services.summary.textrank import DEFAULT_SENTENCE_COUNT


def _word_count(text: str) -> int:
    return len(text.split())


def _reading_minutes(word_count: int) -> float:
    return round(max(word_count, 1) / 200, 1)


@dataclass(frozen=True)
class UnderstandResult:
    word_count: int
    reading_minutes: float
    classification: dict[str, Any]
    summary: dict[str, Any] | None
    pii: dict[str, Any] | None
    filename: str | None = None
    identification: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": "ok",
            "word_count": self.word_count,
            "reading_minutes": self.reading_minutes,
            "classification": self.classification,
        }
        if self.filename:
            payload["filename"] = self.filename
        if self.identification is not None:
            payload["identification"] = self.identification
        if self.summary is not None:
            payload["summary"] = self.summary
        if self.pii is not None:
            payload["pii"] = self.pii
        return payload


def understand_text(
    text: str,
    *,
    sentences: int = DEFAULT_SENTENCE_COUNT,
    include_summary: bool = True,
    include_pii: bool = True,
    entities: list[str] | None = None,
    min_score: float = 0.35,
) -> UnderstandResult:
    """Classify, summarize, and scan plain text for a quick comprehension report."""
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Text must not be empty.")

    words = _word_count(cleaned)
    classification = classify_text(cleaned).to_dict()
    summary_payload = None
    if include_summary:
        summary_payload = summarize_text(text=cleaned, sentence_count=sentences).to_dict()

    pii_payload = None
    if include_pii:
        hits = detect_pii_in_text(cleaned, entities=entities, min_score=min_score)
        entity_types = sorted({hit.entity_type for hit in hits})
        pii_payload = {
            "finding_count": len(hits),
            "entity_types": entity_types,
            "findings": [hit.to_dict() for hit in hits[:50]],
            "truncated": len(hits) > 50,
        }

    return UnderstandResult(
        word_count=words,
        reading_minutes=_reading_minutes(words),
        classification=classification,
        summary=summary_payload,
        pii=pii_payload,
    )


def understand_document(
    path: Path,
    *,
    filename: str | None = None,
    content_type: str | None = None,
    sentences: int = DEFAULT_SENTENCE_COUNT,
    include_summary: bool = True,
    include_pii: bool = True,
    entities: list[str] | None = None,
    min_score: float = 0.35,
) -> UnderstandResult:
    """Extract text from a file and return a comprehension report."""
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"Document not found: {source}")

    resolved_name = filename or source.name
    identification = identify_document(source, filename=resolved_name, content_type=content_type)
    extraction = extract_document_text(source, identification=identification)
    text = extraction.text or ""
    if not text.strip():
        raise ValueError("No extractable text found in the document.")

    base = understand_text(
        text,
        sentences=sentences,
        include_summary=include_summary,
        include_pii=include_pii,
        entities=entities,
        min_score=min_score,
    )
    return UnderstandResult(
        word_count=base.word_count,
        reading_minutes=base.reading_minutes,
        classification=base.classification,
        summary=base.summary,
        pii=base.pii,
        filename=resolved_name,
        identification=identification.to_dict(),
    )
