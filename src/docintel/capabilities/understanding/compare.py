"""Generic document text comparison."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass(frozen=True)
class ComparisonResult:
    similarity: float
    shared_terms: list[str]
    unique_terms_a: list[str]
    unique_terms_b: list[str]

    def to_dict(self) -> dict:
        return {
            "similarity": round(self.similarity, 4),
            "shared_terms": self.shared_terms,
            "unique_terms_a": self.unique_terms_a,
            "unique_terms_b": self.unique_terms_b,
        }


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def compare_texts(text_a: str, text_b: str, *, max_terms: int = 20) -> ComparisonResult:
    """Compare two documents using sequence similarity and token overlap."""
    cleaned_a = text_a.strip()
    cleaned_b = text_b.strip()
    if not cleaned_a or not cleaned_b:
        raise ValueError("Both text_a and text_b must be non-empty.")

    similarity = SequenceMatcher(None, cleaned_a.lower(), cleaned_b.lower()).ratio()
    tokens_a = set(_tokenize(cleaned_a))
    tokens_b = set(_tokenize(cleaned_b))
    shared = sorted(tokens_a & tokens_b)[:max_terms]
    unique_a = sorted(tokens_a - tokens_b)[:max_terms]
    unique_b = sorted(tokens_b - tokens_a)[:max_terms]

    return ComparisonResult(
        similarity=similarity,
        shared_terms=shared,
        unique_terms_a=unique_a,
        unique_terms_b=unique_b,
    )
