"""Text summarization service."""

from docintel.services.summary.models import SummaryResult
from docintel.services.summary.textrank import summarize_text

__all__ = ["SummaryResult", "summarize_text"]
