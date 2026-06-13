"""Text summarization capability (compatibility shim)."""

from docintel.capabilities.understanding.textrank import (
    DEFAULT_SENTENCE_COUNT,
    MAX_SENTENCE_COUNT,
    summarize_text,
)

__all__ = ["DEFAULT_SENTENCE_COUNT", "MAX_SENTENCE_COUNT", "summarize_text"]
