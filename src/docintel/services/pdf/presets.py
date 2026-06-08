"""Default Presidio entity presets (extend via API or custom recognizers)."""

# Core Presidio entities suitable for HR, legal, and compliance workflows.
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

# Minimum extracted characters before a page is treated as scanned (OCR fallback).
MIN_NATIVE_TEXT_CHARS = 20

# EasyOCR render scale (higher improves accuracy, increases memory).
OCR_RENDER_SCALE = 2.0
