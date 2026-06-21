"""PDF annotation pattern planning (compatibility shim)."""

from docintel.capabilities.pdf.pattern_planner import (
    AnnotateFromRequirementsResult,
    AnnotatePlan,
    annotate_pdf_from_requirements,
    annotate_pdf_patterns,
    extract_pdf_text_sample,
    plan_annotation_patterns,
)

__all__ = [
    "AnnotateFromRequirementsResult",
    "AnnotatePlan",
    "annotate_pdf_from_requirements",
    "annotate_pdf_patterns",
    "extract_pdf_text_sample",
    "plan_annotation_patterns",
]
