"""LLM structuring for OCR and native PDF text."""

from __future__ import annotations

import json
import os
from typing import Any

from docintel.services.pdf.structure_schema import StructuredDocument, StructuredPage

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


def _llm_settings() -> tuple[str, str, str | None]:
    api_key = os.getenv("DOCINTEL_LLM_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "DOCINTEL_LLM_API_KEY is not set. Configure an OpenAI-compatible API key."
        )
    model = os.getenv("DOCINTEL_LLM_MODEL", "gpt-4o-mini").strip()
    base_url = os.getenv("DOCINTEL_LLM_BASE_URL", "").strip() or None
    return api_key, model, base_url


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
    api_key, model, base_url = _llm_settings()

    from openai import OpenAI

    client_kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = OpenAI(**client_kwargs)

    user_prompt = STRUCTURE_USER_TEMPLATE.format(
        page_number=page_index + 1,
        source_text=source_text[:12000],
    )
    response = client.chat.completions.create(
        model=model,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": STRUCTURE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = response.choices[0].message.content or "{}"
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
