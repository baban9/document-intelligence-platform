"""Structured document schema for LLM PDF curation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TableBlock:
    headers: list[str]
    rows: list[list[str]]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TableBlock":
        return cls(
            headers=[str(item) for item in payload.get("headers", [])],
            rows=[[str(cell) for cell in row] for row in payload.get("rows", [])],
        )


@dataclass
class SectionBlock:
    heading: str
    level: int
    paragraphs: list[str] = field(default_factory=list)
    list_items: list[str] = field(default_factory=list)
    tables: list[TableBlock] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SectionBlock":
        tables = [TableBlock.from_dict(item) for item in payload.get("tables", [])]
        return cls(
            heading=str(payload.get("heading", "")).strip(),
            level=max(1, min(6, int(payload.get("level", 1)))),
            paragraphs=[str(item).strip() for item in payload.get("paragraphs", []) if str(item).strip()],
            list_items=[str(item).strip() for item in payload.get("list_items", []) if str(item).strip()],
            tables=tables,
        )


@dataclass
class StructuredPage:
    page_index: int
    title: str
    sections: list[SectionBlock] = field(default_factory=list)
    plain_text: str = ""

    @classmethod
    def from_llm_payload(cls, page_index: int, payload: dict[str, Any]) -> "StructuredPage":
        sections = [SectionBlock.from_dict(item) for item in payload.get("sections", [])]
        plain_text = str(payload.get("plain_text", "")).strip()
        if not plain_text:
            plain_text = _sections_to_plain_text(sections)
        return cls(
            page_index=page_index,
            title=str(payload.get("page_title", "")).strip(),
            sections=sections,
            plain_text=plain_text,
        )


@dataclass
class StructuredDocument:
    title: str
    pages: list[StructuredPage] = field(default_factory=list)

    @property
    def sections(self) -> list[SectionBlock]:
        merged: list[SectionBlock] = []
        for page in self.pages:
            merged.extend(page.sections)
        return merged

    @classmethod
    def from_pages(cls, pages: list[StructuredPage]) -> "StructuredDocument":
        title = ""
        for page in pages:
            if page.title:
                title = page.title
                break
        if not title:
            title = "Structured Document"
        return cls(title=title, pages=pages)


def _sections_to_plain_text(sections: list[SectionBlock]) -> str:
    lines: list[str] = []
    for section in sections:
        if section.heading:
            lines.append(section.heading)
        lines.extend(section.paragraphs)
        lines.extend(f"- {item}" for item in section.list_items)
        for table in section.tables:
            if table.headers:
                lines.append(" | ".join(table.headers))
            for row in table.rows:
                lines.append(" | ".join(row))
    return "\n".join(lines)
