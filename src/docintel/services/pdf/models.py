"""Shared types for PDF annotation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Action(str, Enum):
    HIGHLIGHT = "Highlight"
    SQUIGGLY = "Squiggly"
    UNDERLINE = "Underline"
    STRIKEOUT = "Strikeout"
    REDACT = "Redact"
    FRAME = "Frame"
    REMOVE = "Remove"

    @classmethod
    def choices(cls) -> tuple[str, ...]:
        return tuple(action.value for action in cls)

    @classmethod
    def from_value(cls, value: str) -> "Action":
        normalized = value.strip().lower()
        for action in cls:
            if action.value.lower() == normalized:
                return action
        valid = ", ".join(cls.choices())
        raise ValueError(f"Unsupported action '{value}'. Choose from: {valid}")


@dataclass(frozen=True)
class ProcessResult:
    input_path: str
    output_path: str
    action: Action
    matches: int
    pages_processed: int

    def to_dict(self) -> dict:
        return {
            "input_path": self.input_path,
            "output_path": self.output_path,
            "action": self.action.value,
            "matches": self.matches,
            "pages_processed": self.pages_processed,
        }

    def __str__(self) -> str:
        return (
            f"{self.matches} matches annotated in {self.pages_processed} pages "
            f"-> {self.output_path}"
        )
