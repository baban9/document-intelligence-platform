"""Microsoft Presidio PII detection."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Sequence

from docintel.capabilities.compliance.presets import DEFAULT_PII_ENTITIES

logger = logging.getLogger("docintel.pii")

DEFAULT_SPACY_MODEL = "en_core_web_lg"


def spacy_model_name() -> str:
    """spaCy model Presidio should load (must be installed in the runtime image)."""
    return os.getenv("DOCINTEL_SPACY_MODEL", DEFAULT_SPACY_MODEL).strip() or DEFAULT_SPACY_MODEL


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
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    model_name = spacy_model_name()
    configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": model_name}],
    }
    provider = NlpEngineProvider(nlp_configuration=configuration)
    nlp_engine = provider.create_engine()
    logger.info("Presidio analyzer ready with spaCy model %s", model_name)
    return AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])


def warm_pii_analyzer() -> None:
    """Load Presidio and spaCy at startup so the first API or job request is fast."""
    try:
        _analyzer_engine()
    except Exception as exc:
        logger.warning("PII analyzer warm-up skipped: %s", exc)


def resolve_pii_entities(entities: Sequence[str] | None = None) -> list[str]:
    """Use explicit entities, tenant settings, or platform defaults."""
    if entities:
        return list(entities)
    try:
        from docintel.tenants.context import get_tenant_context

        tenant = get_tenant_context()
        if tenant and tenant.settings and tenant.settings.pii_entities:
            return list(tenant.settings.pii_entities)
    except Exception:
        pass
    return list(DEFAULT_PII_ENTITIES)


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
    from docintel.services.pdf import pii as pii_compat

    hits = pii_compat.detect_pii_in_text(
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
