"""PII detection (compatibility shim)."""

from docintel.capabilities.compliance.pii import PIIHit, detect_pii_in_text, list_supported_entities, mask_pii_in_text

__all__ = ["PIIHit", "detect_pii_in_text", "list_supported_entities", "mask_pii_in_text"]
