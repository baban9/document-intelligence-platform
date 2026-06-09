"""Microsoft Presidio PII detection."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Sequence

from docintel.services.pdf.presets import DEFAULT_PII_ENTITIES


@dataclass(frozen=True)
class PIIHit:
    """A sensitive entity detected in text."""

    entity_type: str
    text: str
    start: int
    end: int
    score: float

    def to_dict(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "score": round(self.score, 4),
        }


@lru_cache(maxsize=1)
def _analyzer_engine():
    from presidio_analyzer import AnalyzerEngine

    return AnalyzerEngine()


def detect_pii_in_text(
    text: str,
    *,
    entities: Sequence[str] | None = None,
    language: str = "en",
    min_score: float = 0.35,
) -> list[PIIHit]:
    """Run Presidio analyzer on plain text."""
    if not text.strip():
        return []

    selected_entities = list(entities) if entities else list(DEFAULT_PII_ENTITIES)
    analyzer = _analyzer_engine()
    results = analyzer.analyze(
        text=text,
        language=language,
        entities=selected_entities,
    )

    hits: list[PIIHit] = []
    for result in results:
        if result.score < min_score:
            continue
        hits.append(
            PIIHit(
                entity_type=result.entity_type,
                text=text[result.start : result.end],
                start=result.start,
                end=result.end,
                score=float(result.score),
            )
        )
    return hits


def list_supported_entities(language: str = "en") -> list[str]:
    """Return Presidio-supported entity types for a language."""
    return sorted(_analyzer_engine().get_supported_entities(language=language))


def mask_pii_in_text(
    text: str,
    *,
    entities: Sequence[str] | None = None,
    language: str = "en",
    min_score: float = 0.35,
    mask_template: str = "[REDACTED_{entity}]",
) -> tuple[str, int]:
    """
    Replace detected PII spans with redaction tokens before external LLM calls.

    Returns masked text and the number of entities redacted.
    """
    hits = detect_pii_in_text(
        text,
        entities=entities,
        language=language,
        min_score=min_score,
    )
    if not hits:
        return text, 0

    masked = text
    for hit in sorted(hits, key=lambda item: item.start, reverse=True):
        token = mask_template.format(entity=hit.entity_type)
        masked = masked[: hit.start] + token + masked[hit.end :]
    return masked, len(hits)
