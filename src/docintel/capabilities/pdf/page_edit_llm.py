"""LLM-backed page text editing for the PDF editor."""

from __future__ import annotations

import json
from typing import Any

from docintel.capabilities.extraction.llm_providers import (
    chat_json_completion,
    create_openai_client,
    resolve_llm_config,
)

EDIT_SYSTEM_PROMPT = """You edit document page text according to user instructions.
Rules:
- Apply only the changes the user requested.
- Do not invent facts, numbers, names, or clauses that are not supported by the source.
- Preserve all content that the user did not ask to change.
- Return valid JSON only."""

EDIT_USER_TEMPLATE = """Page number: {page_number}

Current page text:
---
{source_text}
---

User edit instruction:
{instruction}

Return JSON with this schema:
{{
  "edited_text": "full updated page text after applying the instruction",
  "changes_summary": "one short sentence describing what changed"
}}"""


def _ensure_llm_stack() -> None:
    try:
        import openai  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "LLM dependencies are not installed. Run: pip install -e '.[llm]'"
        ) from exc


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


def edit_page_text_with_llm(
    page_index: int,
    source_text: str,
    instruction: str,
) -> tuple[str, str]:
    """Return edited page text and a short change summary."""
    _ensure_llm_stack()
    cleaned_instruction = instruction.strip()
    if not cleaned_instruction:
        raise ValueError("Edit instruction must not be empty.")

    source = source_text.strip()
    if not source:
        raise ValueError("Page has no extractable text to edit.")

    config = resolve_llm_config()
    client = create_openai_client(config)
    user_prompt = EDIT_USER_TEMPLATE.format(
        page_number=page_index + 1,
        source_text=source[:12000],
        instruction=cleaned_instruction,
    )
    content = chat_json_completion(
        client,
        model=config.model,
        system_prompt=EDIT_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )
    payload = _parse_json_response(content)
    edited = str(payload.get("edited_text", "")).strip()
    if not edited:
        raise ValueError("LLM did not return edited page text.")
    summary = str(payload.get("changes_summary", "")).strip() or "Page updated."
    return edited, summary
