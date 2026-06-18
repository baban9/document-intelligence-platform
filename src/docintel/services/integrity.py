"""Compatibility shim for document integrity analysis."""

from docintel.capabilities.compliance.integrity import (
    IntegrityEvidence,
    IntegrityFinding,
    IntegrityResult,
    V1_CHECKS,
    analyze_document_integrity,
)

__all__ = [
    "IntegrityEvidence",
    "IntegrityFinding",
    "IntegrityResult",
    "V1_CHECKS",
    "analyze_document_integrity",
]
