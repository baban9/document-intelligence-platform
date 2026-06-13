"""Compliance capabilities (PII detection, sensitive PDF scanning)."""

from docintel.capabilities.compliance.pii import PIIHit, detect_pii_in_text, list_supported_entities, mask_pii_in_text
from docintel.capabilities.compliance.presets import DEFAULT_PII_ENTITIES, MIN_NATIVE_TEXT_CHARS, OCR_RENDER_SCALE

__all__ = [
    "DEFAULT_PII_ENTITIES",
    "MIN_NATIVE_TEXT_CHARS",
    "OCR_RENDER_SCALE",
    "PIIHit",
    "detect_pii_in_text",
    "list_supported_entities",
    "mask_pii_in_text",
]
