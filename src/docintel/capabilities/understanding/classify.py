"""Lightweight document classification by keyword signals."""

from __future__ import annotations

import re
from dataclasses import dataclass

_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "legal": (
        "agreement",
        "contract",
        "clause",
        "party",
        "whereas",
        "jurisdiction",
        "indemn",
        "liability",
    ),
    "finance": (
        "invoice",
        "payment",
        "balance",
        "account",
        "tax",
        "revenue",
        "ledger",
        "budget",
    ),
    "operations": (
        "procedure",
        "workflow",
        "inventory",
        "shipment",
        "maintenance",
        "schedule",
        "process",
    ),
    "security": (
        "breach",
        "vulnerability",
        "encryption",
        "access control",
        "incident",
        "malware",
        "audit",
    ),
    "knowledge": (
        "overview",
        "summary",
        "guide",
        "documentation",
        "tutorial",
        "reference",
        "faq",
    ),
}


@dataclass(frozen=True)
class ClassificationResult:
    category: str
    confidence: float
    scores: dict[str, float]

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "confidence": round(self.confidence, 4),
            "scores": {key: round(value, 4) for key, value in self.scores.items()},
        }


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def classify_text(text: str) -> ClassificationResult:
    """Score document text against enterprise function categories."""
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Text must not be empty.")

    tokens = _tokenize(cleaned)
    token_set = set(tokens)
    word_count = max(len(tokens), 1)

    scores: dict[str, float] = {}
    for category, keywords in _CATEGORY_KEYWORDS.items():
        hits = sum(1 for keyword in keywords if keyword in token_set or keyword in cleaned.lower())
        scores[category] = hits / word_count

    best_category = max(scores, key=scores.get)
    best_score = scores[best_category]
    total = sum(scores.values()) or 1.0
    confidence = best_score / total if total else 0.0

    return ClassificationResult(
        category=best_category,
        confidence=confidence,
        scores=scores,
    )
