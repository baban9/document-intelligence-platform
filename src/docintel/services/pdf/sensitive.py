"""Sensitive PDF detection (compatibility shim)."""

from docintel.capabilities.compliance.sensitive import _ensure_ocr_stack, detect_sensitive_pdf
from docintel.services.pdf.pii import PIIHit, detect_pii_in_text

__all__ = ["PIIHit", "_ensure_ocr_stack", "detect_pii_in_text", "detect_sensitive_pdf"]
