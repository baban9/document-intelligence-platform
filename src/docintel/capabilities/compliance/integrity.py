"""Document integrity analysis: cross-page gaps, placeholders, and consistency checks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Iterable


SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"

CATEGORY_PLACEHOLDER = "placeholder"
CATEGORY_BROKEN_REFERENCE = "broken_reference"
CATEGORY_NAME_DRIFT = "name_drift"
CATEGORY_NUMBER_MISMATCH = "number_mismatch"
CATEGORY_STRUCTURAL_GAP = "structural_gap"

V1_CHECKS = (
    "placeholders",
    "broken_references",
    "name_drift",
    "number_mismatch",
    "structural_gaps",
)

_PLACEHOLDER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("unfinished_placeholder", re.compile(r"\bTBD\b|\bTBC\b|\bTODO\b|\bFIXME\b", re.IGNORECASE)),
    ("marker_placeholder", re.compile(r"\bXXX+\b")),
    ("bracket_insert", re.compile(r"\[(?:insert|todo|tbd)[^\]]*\]", re.IGNORECASE)),
    ("angle_insert", re.compile(r"<(?:insert|placeholder)[^>]*>", re.IGNORECASE)),
    ("underscore_blank", re.compile(r"_{3,}")),
)

_SECTION_HEADING = re.compile(
    r"^(?:"
    r"(?P<section>\d+(?:\.\d+)+)\s+.+"
    r"|(?:Section|SECTION)\s+(?P<section_label>\d+(?:\.\d+)*)"
    r"|(?:Appendix|APPENDIX)\s+(?P<appendix>[A-Z0-9]+)"
    r"|(?:Figure|FIGURE|Fig\.)\s+(?P<figure>\d+)"
    r"|(?:Table|TABLE)\s+(?P<table>\d+)"
    r")$",
    re.MULTILINE,
)

_REF_SECTION = re.compile(
    r"(?:see|refer to|as defined in)\s+(?:Section|section|Sec\.?)\s+(\d+(?:\.\d+)*)",
    re.IGNORECASE,
)
_REF_APPENDIX = re.compile(r"(?:Appendix|appendix)\s+([A-Z0-9]+)")
_REF_FIGURE = re.compile(r"(?:Figure|figure|Fig\.?)\s+(\d+)")
_REF_TABLE = re.compile(r"(?:Table|table)\s+(\d+)")

_NUMBERED_HEADING = re.compile(r"^(\d+(?:\.\d+)*)\s+\S.+$", re.MULTILINE)
_MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
_ALL_CAPS_HEADING = re.compile(r"^[A-Z][A-Z0-9 ,/&-]{4,}$", re.MULTILINE)

_NAME_CANDIDATE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b")
_NAME_STOPWORDS = frozenset(
    {
        "Executive Summary",
        "Table Of Contents",
        "Master Service Agreement",
        "Terms And Conditions",
        "Privacy Policy",
        "Risk Assessment",
        "General Provisions",
        "Contact Us",
        "United States",
        "New York",
    }
)

_LABELED_AMOUNT = re.compile(
    r"(?P<label>total|budget|revenue|cost|amount|price|fee|balance|subtotal)"
    r"[\s:=-]{0,3}"
    r"(?P<value>[$€£]?\s?[\d,]+(?:\.\d+)?(?:\s?(?:million|billion|M|B|K))?)",
    re.IGNORECASE,
)

_NORMALIZE_AMOUNT = re.compile(r"[^\d.]")


@dataclass(frozen=True)
class IntegrityEvidence:
    quote: str
    start: int
    end: int
    context: str = ""

    def to_dict(self) -> dict:
        payload = {
            "quote": self.quote,
            "start": self.start,
            "end": self.end,
        }
        if self.context:
            payload["context"] = self.context
        return payload


@dataclass(frozen=True)
class IntegrityFinding:
    severity: str
    category: str
    description: str
    evidence: list[IntegrityEvidence]
    suggested_fix: str | None = None

    def to_dict(self) -> dict:
        payload = {
            "severity": self.severity,
            "category": self.category,
            "description": self.description,
            "evidence": [item.to_dict() for item in self.evidence],
        }
        if self.suggested_fix:
            payload["suggested_fix"] = self.suggested_fix
        return payload


@dataclass
class IntegrityResult:
    finding_count: int = 0
    findings: list[IntegrityFinding] = field(default_factory=list)
    summary: dict[str, dict[str, int]] = field(default_factory=dict)
    checks_run: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "finding_count": self.finding_count,
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": self.summary,
            "checks_run": self.checks_run,
        }


def analyze_document_integrity(text: str, *, checks: Iterable[str] | None = None) -> IntegrityResult:
    """Run v1 document integrity checks on extracted plain text."""
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("text must be non-empty.")

    selected = list(checks) if checks is not None else list(V1_CHECKS)
    unknown = sorted(set(selected) - set(V1_CHECKS))
    if unknown:
        raise ValueError(f"Unknown integrity checks: {', '.join(unknown)}")

    findings: list[IntegrityFinding] = []
    if "placeholders" in selected:
        findings.extend(_find_placeholders(cleaned))
    if "broken_references" in selected:
        findings.extend(_find_broken_references(cleaned))
    if "name_drift" in selected:
        findings.extend(_find_name_drift(cleaned))
    if "number_mismatch" in selected:
        findings.extend(_find_number_mismatches(cleaned))
    if "structural_gaps" in selected:
        findings.extend(_find_structural_gaps(cleaned))

    findings.sort(key=lambda item: (_severity_rank(item.severity), item.category, item.description))
    return IntegrityResult(
        finding_count=len(findings),
        findings=findings,
        summary=_summarize(findings),
        checks_run=selected,
    )


def _severity_rank(severity: str) -> int:
    return {SEVERITY_HIGH: 0, SEVERITY_MEDIUM: 1, SEVERITY_LOW: 2}.get(severity, 3)


def _summarize(findings: list[IntegrityFinding]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {"by_category": {}, "by_severity": {}}
    for finding in findings:
        summary["by_category"][finding.category] = summary["by_category"].get(finding.category, 0) + 1
        summary["by_severity"][finding.severity] = summary["by_severity"].get(finding.severity, 0) + 1
    return summary


def _snippet(text: str, start: int, end: int, *, radius: int = 60) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return text[left:right].replace("\n", " ").strip()


def _find_placeholders(text: str) -> list[IntegrityFinding]:
    findings: list[IntegrityFinding] = []
    seen: set[tuple[int, int]] = set()
    for label, pattern in _PLACEHOLDER_PATTERNS:
        for match in pattern.finditer(text):
            key = (match.start(), match.end())
            if key in seen:
                continue
            seen.add(key)
            quote = match.group(0)
            findings.append(
                IntegrityFinding(
                    severity=SEVERITY_MEDIUM,
                    category=CATEGORY_PLACEHOLDER,
                    description=f"Unresolved placeholder marker ({label}).",
                    evidence=[
                        IntegrityEvidence(
                            quote=quote,
                            start=match.start(),
                            end=match.end(),
                            context=_snippet(text, match.start(), match.end()),
                        )
                    ],
                    suggested_fix="Replace the placeholder with final content or remove it before publication.",
                )
            )
    return findings


def _collect_reference_targets(text: str) -> dict[str, set[str]]:
    targets: dict[str, set[str]] = {
        "section": set(),
        "appendix": set(),
        "figure": set(),
        "table": set(),
    }
    for match in _SECTION_HEADING.finditer(text):
        if match.group("section"):
            targets["section"].add(match.group("section"))
        if match.group("section_label"):
            targets["section"].add(match.group("section_label"))
        if match.group("appendix"):
            targets["appendix"].add(match.group("appendix").upper())
        if match.group("figure"):
            targets["figure"].add(match.group("figure"))
        if match.group("table"):
            targets["table"].add(match.group("table"))

    for match in _NUMBERED_HEADING.finditer(text):
        targets["section"].add(match.group(1))
    return targets


def _find_broken_references(text: str) -> list[IntegrityFinding]:
    targets = _collect_reference_targets(text)
    findings: list[IntegrityFinding] = []
    checks = (
        (_REF_SECTION, "section", "Section"),
        (_REF_APPENDIX, "appendix", "Appendix"),
        (_REF_FIGURE, "figure", "Figure"),
        (_REF_TABLE, "table", "Table"),
    )
    seen: set[tuple[str, str, int]] = set()
    for pattern, kind, label in checks:
        for match in pattern.finditer(text):
            ref_id = match.group(1)
            normalized = ref_id.upper() if kind == "appendix" else ref_id
            if normalized in targets[kind]:
                continue
            key = (kind, normalized, match.start())
            if key in seen:
                continue
            seen.add(key)
            quote = match.group(0)
            findings.append(
                IntegrityFinding(
                    severity=SEVERITY_HIGH,
                    category=CATEGORY_BROKEN_REFERENCE,
                    description=f"Reference to missing {label} {ref_id}.",
                    evidence=[
                        IntegrityEvidence(
                            quote=quote,
                            start=match.start(),
                            end=match.end(),
                            context=_snippet(text, match.start(), match.end()),
                        )
                    ],
                    suggested_fix=f"Add {label} {ref_id} or update the cross-reference.",
                )
            )
    return findings


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _find_name_drift(text: str) -> list[IntegrityFinding]:
    counts: dict[str, dict[str, int]] = {}
    positions: dict[str, list[tuple[int, int, str]]] = {}
    for match in _NAME_CANDIDATE.finditer(text):
        name = match.group(1).strip()
        if name in _NAME_STOPWORDS or len(name) < 6:
            continue
        if name.isupper():
            continue
        normalized = _normalize_name(name)
        if len(normalized) < 5:
            continue
        counts.setdefault(normalized, {})
        counts[normalized][name] = counts[normalized].get(name, 0) + 1
        positions.setdefault(normalized, []).append((match.start(), match.end(), name))

    findings: list[IntegrityFinding] = []
    reported: set[frozenset[str]] = set()
    keys = list(counts.keys())
    for index, left_key in enumerate(keys):
        left_names = list(counts[left_key])
        if len(left_names) > 1:
            variant_set = frozenset(left_names)
            if variant_set not in reported:
                reported.add(variant_set)
                findings.append(_name_drift_finding(left_names, positions[left_key], text))

        for right_key in keys[index + 1 :]:
            left_names = list(counts[left_key])
            right_names = list(counts[right_key])
            key_ratio = SequenceMatcher(None, left_key, right_key).ratio()
            if key_ratio >= 0.86 and key_ratio < 0.995:
                variants = sorted(set(left_names + right_names))
                variant_set = frozenset(variants)
                if variant_set in reported:
                    continue
                reported.add(variant_set)
                combined_positions = positions[left_key] + positions[right_key]
                findings.append(_name_drift_finding(variants, combined_positions, text))
                continue

            for left_name in left_names:
                left_tokens = left_name.split()
                if not left_tokens:
                    continue
                for right_name in right_names:
                    right_tokens = right_name.split()
                    if not right_tokens or left_tokens[0] != right_tokens[0]:
                        continue
                    name_ratio = SequenceMatcher(None, left_name.lower(), right_name.lower()).ratio()
                    if name_ratio < 0.72 or name_ratio >= 0.995:
                        continue
                    variants = sorted({left_name, right_name})
                    variant_set = frozenset(variants)
                    if variant_set in reported:
                        continue
                    reported.add(variant_set)
                    combined_positions = positions[left_key] + positions[right_key]
                    findings.append(_name_drift_finding(variants, combined_positions, text))
    return findings


def _name_drift_finding(
    variants: list[str],
    spans: list[tuple[int, int, str]],
    text: str,
) -> IntegrityFinding:
    evidence: list[IntegrityEvidence] = []
    for start, end, name in spans[:4]:
        evidence.append(
            IntegrityEvidence(
                quote=name,
                start=start,
                end=end,
                context=_snippet(text, start, end),
            )
        )
    joined = ", ".join(f"'{name}'" for name in variants)
    return IntegrityFinding(
        severity=SEVERITY_MEDIUM,
        category=CATEGORY_NAME_DRIFT,
        description=f"Possible inconsistent naming across the document: {joined}.",
        evidence=evidence,
        suggested_fix="Standardize the entity name and use one canonical form throughout.",
    )


def _normalize_amount(value: str) -> str:
    lowered = value.lower().replace(",", "")
    multiplier = 1.0
    if lowered.endswith("k"):
        multiplier = 1_000.0
        lowered = lowered[:-1]
    elif lowered.endswith("m") or "million" in lowered:
        multiplier = 1_000_000.0
        lowered = lowered.replace("million", "").replace("m", "")
    elif lowered.endswith("b") or "billion" in lowered:
        multiplier = 1_000_000_000.0
        lowered = lowered.replace("billion", "").replace("b", "")
    digits = _NORMALIZE_AMOUNT.sub("", lowered)
    if not digits:
        return value.strip().lower()
    try:
        numeric = float(digits) * multiplier
    except ValueError:
        return value.strip().lower()
    return f"{numeric:.4f}"


def _find_number_mismatches(text: str) -> list[IntegrityFinding]:
    label_values: dict[str, dict[str, list[tuple[int, int, str]]]] = {}
    for match in _LABELED_AMOUNT.finditer(text):
        label = match.group("label").lower()
        raw_value = match.group("value").strip()
        normalized = _normalize_amount(raw_value)
        label_values.setdefault(label, {})
        label_values[label].setdefault(normalized, [])
        label_values[label][normalized].append((match.start("value"), match.end("value"), raw_value))

    findings: list[IntegrityFinding] = []
    for label, values in label_values.items():
        if len(values) < 2:
            continue
        evidence: list[IntegrityEvidence] = []
        rendered_values: list[str] = []
        for spans in values.values():
            for start, end, raw in spans[:2]:
                evidence.append(
                    IntegrityEvidence(
                        quote=raw,
                        start=start,
                        end=end,
                        context=_snippet(text, start, end),
                    )
                )
                rendered_values.append(raw)
        unique_display = sorted(set(rendered_values))
        findings.append(
            IntegrityFinding(
                severity=SEVERITY_HIGH,
                category=CATEGORY_NUMBER_MISMATCH,
                description=(
                    f"Conflicting '{label}' values found: {', '.join(unique_display)}."
                ),
                evidence=evidence[:6],
                suggested_fix="Reconcile the figures or clarify which value applies in each section.",
            )
        )
    return findings


def _heading_spans(text: str) -> list[tuple[int, int, str]]:
    headings: list[tuple[int, int, str]] = []
    for pattern in (_MARKDOWN_HEADING, _NUMBERED_HEADING, _ALL_CAPS_HEADING):
        for match in pattern.finditer(text):
            title = match.group(1) if match.lastindex else match.group(0)
            headings.append((match.start(), match.end(), title.strip()))
    headings.sort(key=lambda item: item[0])
    deduped: list[tuple[int, int, str]] = []
    seen_starts: set[int] = set()
    for item in headings:
        if item[0] in seen_starts:
            continue
        seen_starts.add(item[0])
        deduped.append(item)
    return deduped


def _find_structural_gaps(text: str) -> list[IntegrityFinding]:
    headings = _heading_spans(text)
    if len(headings) < 2:
        return []

    findings: list[IntegrityFinding] = []
    for index, (start, end, title) in enumerate(headings[:-1]):
        next_start = headings[index + 1][0]
        body = text[end:next_start].strip()
        if len(body) >= 40:
            continue
        quote = title if len(title) <= 80 else title[:77] + "..."
        findings.append(
            IntegrityFinding(
                severity=SEVERITY_LOW,
                category=CATEGORY_STRUCTURAL_GAP,
                description=f"Section '{title}' has little or no body content before the next heading.",
                evidence=[
                    IntegrityEvidence(
                        quote=quote,
                        start=start,
                        end=end,
                        context=body or "(empty)",
                    )
                ],
                suggested_fix="Add section content or merge this heading with the following section.",
            )
        )
    return findings
