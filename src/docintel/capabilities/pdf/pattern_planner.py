"""LLM-backed search pattern planning for PDF annotation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz

from docintel.capabilities.extraction.llm_providers import (
    chat_json_completion,
    create_openai_client,
    resolve_llm_config,
)
from docintel.capabilities.pdf.models import Action, ProcessResult
from docintel.capabilities.pdf.search import search_for_text

PLANNER_SYSTEM_PROMPT = """You help users find text in PDF documents for highlighting or redaction.
Return valid JSON only. Use Python regex syntax compatible with re.findall (case insensitive).
Prefer simple, safe patterns. Include literal phrases when the user names exact words.
Do not invent requirements beyond what the user asked for."""

PLANNER_USER_TEMPLATE = """User requirements:
{requirements}

Document text sample (for context only):
---
{sample}
---

Return JSON with this schema:
{{
  "patterns": ["regex patterns to search for"],
  "phrases": ["exact words or phrases to match literally"],
  "rationale": "one short sentence explaining the search plan"
}}

Rules:
- patterns must be valid Python regex strings
- phrases are matched as literal text (case insensitive search is applied later)
- use patterns for formats (emails, invoice numbers, dates) and phrases for named terms
- return at least one pattern or phrase when requirements are clear"""


@dataclass(frozen=True)
class AnnotatePlan:
    requirements: str
    patterns: tuple[str, ...] = ()
    phrases: tuple[str, ...] = ()
    rationale: str = ""

    def search_patterns(self) -> list[str]:
        """Combine regex patterns and escaped literal phrases for search."""
        combined: list[str] = []
        seen: set[str] = set()
        for phrase in self.phrases:
            cleaned = phrase.strip()
            if not cleaned:
                continue
            escaped = re.escape(cleaned)
            if escaped not in seen:
                seen.add(escaped)
                combined.append(escaped)
        for pattern in self.patterns:
            cleaned = pattern.strip()
            if not cleaned or cleaned in seen:
                continue
            try:
                re.compile(cleaned, re.IGNORECASE)
            except re.error:
                continue
            seen.add(cleaned)
            combined.append(cleaned)
        return combined

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirements": self.requirements,
            "patterns": list(self.patterns),
            "phrases": list(self.phrases),
            "rationale": self.rationale,
            "search_patterns": self.search_patterns(),
        }


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


def extract_pdf_text_sample(input_file: str | Path, *, max_chars: int = 8000) -> str:
    """Read native PDF text for LLM context (first pages until max_chars)."""
    pdf_path = Path(input_file)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pdf_doc = fitz.open(pdf_path)
    chunks: list[str] = []
    total = 0
    try:
        for page_index in range(pdf_doc.page_count):
            page_text = pdf_doc[page_index].get_text("text").strip()
            if not page_text:
                continue
            header = f"[Page {page_index + 1}]\n"
            remaining = max_chars - total
            if remaining <= 0:
                break
            piece = page_text[: max(0, remaining - len(header))]
            if not piece:
                break
            chunks.append(header + piece)
            total += len(header) + len(piece)
    finally:
        pdf_doc.close()

    return "\n\n".join(chunks).strip()


def plan_annotation_patterns(requirements: str, document_sample: str) -> AnnotatePlan:
    """Use the configured LLM to derive regex patterns and phrases from requirements."""
    cleaned_requirements = requirements.strip()
    if not cleaned_requirements:
        raise ValueError("Provide annotation requirements.")

    _ensure_llm_stack()
    config = resolve_llm_config()
    client = create_openai_client(config)

    user_prompt = PLANNER_USER_TEMPLATE.format(
        requirements=cleaned_requirements,
        sample=document_sample[:8000] or "(no extractable text in sample pages)",
    )
    content = chat_json_completion(
        client,
        model=config.model,
        system_prompt=PLANNER_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )
    payload = _parse_json_response(content)

    raw_patterns = payload.get("patterns") or []
    raw_phrases = payload.get("phrases") or []
    patterns = tuple(str(item).strip() for item in raw_patterns if str(item).strip())
    phrases = tuple(str(item).strip() for item in raw_phrases if str(item).strip())
    rationale = str(payload.get("rationale") or "").strip()

    plan = AnnotatePlan(
        requirements=cleaned_requirements,
        patterns=patterns,
        phrases=phrases,
        rationale=rationale,
    )
    if not plan.search_patterns():
        raise ValueError(
            "The LLM did not return usable search patterns. "
            "Try clearer requirements or use a manual regex pattern."
        )
    return plan


def annotate_pdf_patterns(
    input_file: str | Path,
    output_file: str | Path,
    patterns: list[str],
    action: Action | str = Action.HIGHLIGHT,
    pages: list[int] | None = None,
    password: str | None = None,
) -> ProcessResult:
    """Search a PDF with multiple patterns and apply the requested annotation action."""
    from docintel.capabilities.pdf.annotator import (
        _normalize_pages,
        _open_pdf,
        _save_pdf,
        frame_matches,
        highlight_matches,
        redact_matches,
    )

    selected_action = action if isinstance(action, Action) else Action.from_value(action)
    page_list = _normalize_pages(pages)

    pdf_doc = _open_pdf(input_file, password)
    total_matches = 0
    pages_processed = 0

    for page_index in range(pdf_doc.page_count):
        if page_list is not None and page_index not in page_list:
            continue
        pages_processed += 1
        page = pdf_doc[page_index]
        page_lines = page.get_text("text").split("\n")
        matched_values: set[str] = set()
        for pattern in patterns:
            try:
                for result in search_for_text(page_lines, pattern):
                    matched_values.add(result)
            except re.error:
                continue
        if not matched_values:
            continue

        ordered = list(matched_values)
        if selected_action == Action.REDACT:
            total_matches += redact_matches(page, ordered)
        elif selected_action == Action.FRAME:
            total_matches += frame_matches(page, ordered)
        else:
            total_matches += highlight_matches(page, ordered, selected_action)

    _save_pdf(pdf_doc, Path(output_file))
    return ProcessResult(
        input_path=str(input_file),
        output_path=str(output_file),
        action=selected_action,
        matches=total_matches,
        pages_processed=pages_processed,
    )


@dataclass
class AnnotateFromRequirementsResult:
    process: ProcessResult
    plan: AnnotatePlan
    search_patterns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = self.process.to_dict()
        payload.update(self.plan.to_dict())
        payload["search_patterns"] = self.search_patterns or self.plan.search_patterns()
        return payload


def annotate_pdf_from_requirements(
    input_file: str | Path,
    output_file: str | Path,
    requirements: str,
    action: Action | str = Action.HIGHLIGHT,
    pages: list[int] | None = None,
    password: str | None = None,
) -> AnnotateFromRequirementsResult:
    """Plan patterns with the LLM, then annotate the PDF."""
    sample = extract_pdf_text_sample(input_file)
    plan = plan_annotation_patterns(requirements, sample)
    search_patterns = plan.search_patterns()
    process = annotate_pdf_patterns(
        input_file=input_file,
        output_file=output_file,
        patterns=search_patterns,
        action=action,
        pages=pages,
        password=password,
    )
    return AnnotateFromRequirementsResult(
        process=process,
        plan=plan,
        search_patterns=search_patterns,
    )
