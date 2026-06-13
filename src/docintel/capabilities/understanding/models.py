"""Types for text summarization."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SummaryResult:
    summary: str
    sentences: list[str]
    sentence_count: int
    source_sentence_count: int

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "sentences": self.sentences,
            "sentence_count": self.sentence_count,
            "source_sentence_count": self.source_sentence_count,
        }
