"""PII entity presets (compatibility shim)."""

from docintel.capabilities.compliance.presets import (
    DEFAULT_PII_ENTITIES,
    MIN_NATIVE_TEXT_CHARS,
    OCR_RENDER_SCALE,
    VERTICAL_ENTITY_PRESETS,
    entities_for_vertical,
    list_vertical_presets,
)

__all__ = [
    "DEFAULT_PII_ENTITIES",
    "MIN_NATIVE_TEXT_CHARS",
    "OCR_RENDER_SCALE",
    "VERTICAL_ENTITY_PRESETS",
    "entities_for_vertical",
    "list_vertical_presets",
]
