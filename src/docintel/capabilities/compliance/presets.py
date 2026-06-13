"""Default Presidio entity presets (extend via API or custom recognizers)."""

# Core Presidio entities suitable for legal, finance, and compliance workflows.
DEFAULT_PII_ENTITIES: tuple[str, ...] = (
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "US_SSN",
    "CREDIT_CARD",
    "US_BANK_NUMBER",
    "US_DRIVER_LICENSE",
    "US_ITIN",
    "US_PASSPORT",
    "PERSON",
    "LOCATION",
    "DATE_TIME",
    "IP_ADDRESS",
    "IBAN_CODE",
    "MEDICAL_LICENSE",
    "URL",
)

VERTICAL_ENTITY_PRESETS: dict[str, tuple[str, ...]] = {
    "general": DEFAULT_PII_ENTITIES,
    "healthcare": (
        "PERSON",
        "PHONE_NUMBER",
        "EMAIL_ADDRESS",
        "DATE_TIME",
        "LOCATION",
        "US_SSN",
        "MEDICAL_LICENSE",
        "US_DRIVER_LICENSE",
        "URL",
    ),
    "financial": (
        "PERSON",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "US_SSN",
        "CREDIT_CARD",
        "US_BANK_NUMBER",
        "IBAN_CODE",
        "US_ITIN",
        "DATE_TIME",
        "LOCATION",
        "URL",
    ),
    "legal": (
        "PERSON",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "LOCATION",
        "DATE_TIME",
        "US_PASSPORT",
        "US_DRIVER_LICENSE",
        "US_SSN",
        "URL",
    ),
}

# Minimum extracted characters before a page is treated as scanned (OCR fallback).
MIN_NATIVE_TEXT_CHARS = 20

# EasyOCR render scale (higher improves accuracy, increases memory).
OCR_RENDER_SCALE = 2.0


def list_vertical_presets() -> dict[str, list[str]]:
    """Return named entity packs for vertical workflows."""
    return {name: list(entities) for name, entities in VERTICAL_ENTITY_PRESETS.items()}


def entities_for_vertical(name: str) -> tuple[str, ...]:
    """Resolve a vertical preset name to a Presidio entity list."""
    key = name.strip().lower()
    try:
        return VERTICAL_ENTITY_PRESETS[key]
    except KeyError as exc:
        valid = ", ".join(sorted(VERTICAL_ENTITY_PRESETS))
        raise ValueError(f"Unknown vertical preset '{name}'. Choose from: {valid}") from exc
