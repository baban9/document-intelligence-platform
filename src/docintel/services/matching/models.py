"""Types for resume matching."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MatchResult:
    score: float
    matched_keywords: list[str]
    missing_keywords: list[str]

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "matched_keywords": self.matched_keywords,
            "missing_keywords": self.missing_keywords,
        }
