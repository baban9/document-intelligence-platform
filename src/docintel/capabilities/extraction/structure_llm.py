"""LLM structuring for OCR and native PDF text."""

from __future__ import annotations

import json
from typing import Any

from docintel.capabilities.extraction.llm_providers import (
    chat_json_completion,
    create_openai_client,
    resolve_llm_config,
)
from docintel.capabilities.extraction.structure_schema import StructuredDocument, StructuredPage

STRUCTURE_SYSTEM_PROMPT = """You convert noisy OCR or unstructured PDF text into clean structured JSON.
Rules:
- Fix OCR typos only when the intended word is obvious from context.
- Do not invent facts, numbers, names, or clauses that are not in the source.
- Preserve reading order.
- Use headings only when the source clearly has a section title.
- Return valid JSON only, matching the schema exactly."""

STRUCTURE_USER_TEMPLATE = """Page number: {page_number}
Source text:
---
{source_text}
---

Return JSON with this schema:
{{
  "page_title": "document or section title if visible on this page, else empty string",
  "plain_text": "full cleaned page text in reading order with paragraph breaks",
  "sections": [
    {{
      "heading": "section heading or empty string",
      "level": 1,
      "paragraphs": ["paragraph text"],
      "list_items": ["bullet items"],
      "tables": [{{"headers": ["col"], "rows": [["value"]]}}]
    }}
  ]
}}"""


def _ensure_llm_stack() -> None:
    try:
        import openai  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "LLM dependencies are not installed. Run: pip install -e '.[llm]'"
        ) from exc


def _llm_settings():
    """Return resolved LLM config (provider, api_key, model, base_url)."""
    return resolve_llm_config()


def _parse_json_response(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        raise ValueError("LLM response must be a JSON object.")
    return payload


def structure_page_text(page_index: int, source_text: str) -> StructuredPage:
    """Send one page of source text to the LLM and return structured output."""
    _ensure_llm_stack()
    config = _llm_settings()
    client = create_openai_client(config)

    user_prompt = STRUCTURE_USER_TEMPLATE.format(
        page_number=page_index + 1,
        source_text=source_text[:12000],
    )
    content = chat_json_completion(
        client,
        model=config.model,
        system_prompt=STRUCTURE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )
    payload = _parse_json_response(content)
    return StructuredPage.from_llm_payload(page_index, payload)


def structure_document(
    page_texts: list[tuple[int, str]],
    *,
    progress_callback=None,
) -> StructuredDocument:
    """Structure each page with the LLM and merge into one document model."""
    structured_pages: list[StructuredPage] = []
    total = len(page_texts)
    for offset, (page_index, text) in enumerate(page_texts):
        cleaned = text.strip()
        if progress_callback is not None:
            progress_callback(
                stage="structuring",
                pages_done=offset,
                pages_total=total,
                message=f"Structuring page {page_index + 1} of {total}",
            )
        if not cleaned:
            structured_pages.append(
                StructuredPage(page_index=page_index, title="", sections=[], plain_text="")
            )
            continue
        structured_pages.append(structure_page_text(page_index, cleaned))
    if progress_callback is not None:
        progress_callback(
            stage="structuring",
            pages_done=total,
            pages_total=total,
            message="Structuring complete",
        )
    return StructuredDocument.from_pages(structured_pages)
