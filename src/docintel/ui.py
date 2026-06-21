"""Gradio upload UI for the document intelligence platform."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import requests

from docintel.services.integrity import V1_CHECKS

API_BASE = os.getenv("DOCINTEL_API_URL", "http://127.0.0.1:5000").rstrip("/")
API_KEY = os.getenv("DOCINTEL_API_KEY", "")


def _api_headers() -> dict[str, str]:
    if API_KEY.strip():
        return {"Authorization": f"Bearer {API_KEY.strip()}"}
    return {}


def list_pii_entity_choices() -> list[str]:
    """Presidio entity types for UI pickers (API first, local default fallback)."""
    try:
        response = requests.get(f"{API_BASE}/v1/pdf/entities", headers=_api_headers(), timeout=10)
        if response.ok:
            payload = response.json()
            supported = payload.get("supported_entities")
            if isinstance(supported, list) and supported:
                return sorted(str(item) for item in supported)
    except requests.RequestException:
        pass
    from docintel.capabilities.compliance.presets import DEFAULT_PII_ENTITIES

    return sorted(DEFAULT_PII_ENTITIES)


def default_pii_entity_selection(choices: list[str] | None = None) -> list[str]:
    """Default checked entities for new sessions."""
    from docintel.capabilities.compliance.presets import DEFAULT_PII_ENTITIES

    available = set(choices or list_pii_entity_choices())
    return [entity for entity in DEFAULT_PII_ENTITIES if entity in available]


def resolve_pii_entity_list(
    *,
    vertical: str = "",
    selected_entities: list[str] | None = None,
    entities_text: str = "",
) -> str | None:
    """Build comma-separated Presidio entities for API form fields."""
    if vertical.strip():
        return None
    chosen: list[str] = []
    seen: set[str] = set()
    for entity in list(selected_entities or []):
        key = entity.strip()
        if key and key not in seen:
            seen.add(key)
            chosen.append(key)
    if entities_text.strip():
        for entity in entities_text.split(","):
            key = entity.strip()
            if key and key not in seen:
                seen.add(key)
                chosen.append(key)
    if not chosen:
        return None
    return ",".join(chosen)


def pii_entities_for_vertical(vertical: str) -> list[str]:
    """Entity checklist values when a vertical preset is selected."""
    if not vertical.strip():
        return default_pii_entity_selection()
    from docintel.capabilities.compliance.presets import entities_for_vertical

    try:
        return list(entities_for_vertical(vertical))
    except ValueError:
        return default_pii_entity_selection()


GRADIO_HOST = os.getenv("GRADIO_SERVER_NAME", "127.0.0.1")
GRADIO_PORT = int(os.getenv("GRADIO_SERVER_PORT", "7860"))


def resolve_upload_path(upload: Any) -> Path | None:
    """Normalize Gradio file upload values to a local path."""
    if upload is None:
        return None
    if isinstance(upload, (str, Path)):
        return Path(upload)
    if isinstance(upload, dict) and upload.get("path"):
        return Path(upload["path"])
    if isinstance(upload, list) and upload:
        return resolve_upload_path(upload[0])
    return None


def _api_error(response: requests.Response) -> str:
    try:
        payload = response.json()
        return payload.get("error", response.text)
    except Exception:
        return response.text or f"HTTP {response.status_code}"


def _poll_job_until_complete(
    poll_url: str,
    *,
    timeout_seconds: int = 600,
    interval_seconds: float = 2.0,
) -> tuple[dict | None, str | None]:
    """Poll GET /v1/jobs/{id} until completed or failed."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        poll = requests.get(f"{API_BASE}{poll_url}", headers=_api_headers(), timeout=30)
        if not poll.ok:
            return None, _api_error(poll)
        payload = poll.json()
        job_status = payload.get("job_status")
        if job_status == "completed":
            return payload, None
        if job_status == "failed":
            return None, payload.get("error", "Job failed.")
        time.sleep(interval_seconds)
    return None, "Job timed out while polling."


def _download_pdf_from_job(payload: dict, suffix: str) -> tuple[Any, str | None]:
    download_url = payload.get("download_url")
    if not download_url:
        return None, "Processed PDF is not ready yet."
    download = requests.get(f"{API_BASE}{download_url}", headers=_api_headers(), timeout=120)
    if not download.ok:
        return None, "Processed PDF could not be downloaded."
    output = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    output.write(download.content)
    output.close()
    return output.name, None


def check_api_health() -> str:
    try:
        response = requests.get(f"{API_BASE}/health", timeout=10)
        if response.ok:
            payload = response.json()
            return f"API online ({payload.get('version', 'unknown')}) at {API_BASE}"
        return f"API unhealthy: {_api_error(response)}"
    except requests.RequestException as exc:
        return f"Cannot reach API at {API_BASE}: {exc}"


def annotate_pdf_ui(pdf_file: Any, pattern: str, action: str) -> tuple[Any, str]:
    path = resolve_upload_path(pdf_file)
    if path is None:
        return None, "Upload a PDF file."
    if not pattern.strip():
        return None, "Enter a search pattern."
    with path.open("rb") as handle:
        response = requests.post(
            f"{API_BASE}/v1/pdf/annotate?async=true",
            files={"file": (path.name, handle, "application/pdf")},
            data={"pattern": pattern, "action": action},
            headers=_api_headers(),
            timeout=120,
        )

    if response.status_code == 202:
        payload = response.json()
        poll_url = payload.get("poll_url")
        if not poll_url:
            return None, "Async job started but poll_url is missing."
        payload, error = _poll_job_until_complete(poll_url)
        if error:
            return None, error
    elif response.ok:
        matches = response.headers.get("X-Docintel-Matches", "?")
        output = tempfile.NamedTemporaryFile(delete=False, suffix="_annotated.pdf")
        output.write(response.content)
        output.close()
        return output.name, f"Annotated PDF ready. Matches: {matches}"
    else:
        return None, _api_error(response)

    output_path, error = _download_pdf_from_job(payload, "_annotated.pdf")
    if error:
        return None, error
    result = payload.get("result") or payload
    matches = result.get("matches", "?")
    return output_path, f"Annotated PDF ready. Matches: {matches}"


def detect_sensitive_ui(
    pdf_file: Any,
    action: str,
    selected_entities: list[str],
    entities: str,
    force_ocr: bool,
    add_text_layer: bool,
) -> tuple[Any, str]:
    path = resolve_upload_path(pdf_file)
    if path is None:
        return None, "Upload a PDF file."
    data = {
        "action": action,
        "force_ocr": str(force_ocr).lower(),
        "add_text_layer": str(add_text_layer).lower(),
    }
    entity_csv = resolve_pii_entity_list(selected_entities=selected_entities, entities_text=entities)
    if entity_csv:
        data["entities"] = entity_csv

    with path.open("rb") as handle:
        response = requests.post(
            f"{API_BASE}/v1/pdf/detect-sensitive?async=true&format=json",
            files={"file": (path.name, handle, "application/pdf")},
            data=data,
            headers=_api_headers(),
            timeout=120,
        )

    if response.status_code == 202:
        enqueue_payload = response.json()
        poll_url = enqueue_payload.get("poll_url")
        if not poll_url:
            return None, "Async job started but poll_url is missing."
        payload, error = _poll_job_until_complete(poll_url, timeout_seconds=900)
        if error:
            return None, error
    elif response.ok:
        payload = response.json()
    else:
        return None, _api_error(response)

    output_path, error = _download_pdf_from_job(payload, "_sensitive.pdf")
    if error:
        return None, error

    result = payload.get("result") or payload
    summary = {
        "matches": result.get("matches"),
        "finding_count": result.get("finding_count"),
        "ocr_pages": result.get("ocr_pages"),
        "findings": result.get("findings", [])[:20],
    }
    return output_path, json.dumps(summary, indent=2)


def structure_pdf_ui(pdf_file: Any, mode: str, force_ocr: bool) -> tuple[Any, str]:
    path = resolve_upload_path(pdf_file)
    if path is None:
        return None, "Upload a PDF file."

    with path.open("rb") as handle:
        response = requests.post(
            f"{API_BASE}/v1/pdf/structure?async=true",
            files={"file": (path.name, handle, "application/pdf")},
            data={"mode": mode, "force_ocr": str(force_ocr).lower()},
            headers=_api_headers(),
            timeout=120,
        )

    if response.status_code == 202:
        payload = response.json()
        poll_url = payload.get("poll_url")
        if not poll_url:
            return None, "Async job started but poll_url is missing."
        payload, error = _poll_job_until_complete(poll_url, timeout_seconds=900)
        if error:
            return None, error
    elif response.ok:
        payload = response.json()
    else:
        return None, _api_error(response)

    output_path, error = _download_pdf_from_job(payload, "_structured.pdf")
    if error:
        return None, error

    result = payload.get("result") or payload
    summary = {
        "job_status": payload.get("job_status"),
        "mode": result.get("mode"),
        "document_title": result.get("document_title"),
        "pages_processed": result.get("pages_processed"),
        "ocr_pages": result.get("ocr_pages"),
    }
    return output_path, json.dumps(summary, indent=2)


def summarize_text_ui(text: str, sentences: int) -> str:
    if not text.strip():
        return "Provide text to summarize."

    response = requests.post(
        f"{API_BASE}/v1/text/summarize",
        json={"text": text, "sentences": int(sentences)},
        headers=_api_headers(),
        timeout=60,
    )
    if not response.ok:
        return _api_error(response)
    return json.dumps(response.json(), indent=2)


def _format_json_response(response: requests.Response) -> str:
    if response.status_code == 202:
        payload = response.json()
        poll_url = payload.get("poll_url")
        if not poll_url:
            return "Async job started but poll_url is missing."
        completed, error = _poll_job_until_complete(poll_url)
        if error:
            return error
        result = completed.get("result") or {}
        return json.dumps({"status": "ok", **result}, indent=2)
    if response.ok:
        return json.dumps(response.json(), indent=2)
    return _api_error(response)


def _post_document_file(
    endpoint: str,
    path: Path,
    *,
    data: dict | None = None,
    async_job: bool = True,
) -> str:
    url = f"{API_BASE}{endpoint}"
    if async_job:
        url = f"{url}?async=true"
    with path.open("rb") as handle:
        response = requests.post(
            url,
            files={"file": (path.name, handle, "application/octet-stream")},
            data=data or {},
            headers=_api_headers(),
            timeout=120,
        )
    return _format_json_response(response)


def identify_document_ui(upload_file: Any) -> str:
    path = resolve_upload_path(upload_file)
    if path is None:
        return "Upload a document."
    with path.open("rb") as handle:
        response = requests.post(
            f"{API_BASE}/v1/documents/identify",
            files={"file": (path.name, handle, "application/octet-stream")},
            headers=_api_headers(),
            timeout=120,
        )
    if not response.ok:
        return _api_error(response)
    return json.dumps(response.json(), indent=2)


def extract_document_text_ui(upload_file: Any) -> str:
    path = resolve_upload_path(upload_file)
    if path is None:
        return "Upload a document."
    payload_text = _post_document_file("/v1/documents/extract-text", path)
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError:
        return payload_text
    preview = payload.get("text", "")
    if len(preview) > 2000:
        preview = preview[:2000] + "\n...(truncated)"
    payload["text_preview"] = preview
    payload.pop("text", None)
    return json.dumps(payload, indent=2)


def classify_document_ui(upload_file: Any) -> str:
    path = resolve_upload_path(upload_file)
    if path is None:
        return "Upload a document."
    return _post_document_file("/v1/documents/classify", path)


def summarize_document_ui(upload_file: Any, sentences: int) -> str:
    path = resolve_upload_path(upload_file)
    if path is None:
        return "Upload a document."
    return _post_document_file(
        "/v1/documents/summarize",
        path,
        data={"sentences": str(int(sentences))},
    )


def detect_pii_document_ui(
    upload_file: Any,
    selected_entities: list[str],
    entities: str,
) -> str:
    path = resolve_upload_path(upload_file)
    if path is None:
        return "Upload a document."
    data: dict[str, str] = {}
    entity_csv = resolve_pii_entity_list(selected_entities=selected_entities, entities_text=entities)
    if entity_csv:
        data["entities"] = entity_csv
    return _post_document_file("/v1/documents/detect-pii", path, data=data or None)


def format_integrity_summary(result: dict[str, Any]) -> str:
    summary = result.get("summary") or {}
    by_severity = summary.get("by_severity") or {}
    by_category = summary.get("by_category") or {}
    severity_parts = [f"{_severity_label(k)}: {v}" for k, v in sorted(by_severity.items())]
    category_parts = [f"{k}: {v}" for k, v in sorted(by_category.items())]
    lines = [
        f"Finding count: {result.get('finding_count', 0)}",
        f"Checks run: {', '.join(result.get('checks_run') or [])}",
        f"By severity: {', '.join(severity_parts) if severity_parts else 'none'}",
        f"By category: {', '.join(category_parts) if category_parts else 'none'}",
    ]
    return "\n".join(lines)


def _severity_label(severity: str) -> str:
    """Text prefix so severity is readable without relying on color alone."""
    key = severity.strip().lower()
    if key in {"high", "critical"}:
        return f"[!] {severity.upper()}"
    if key == "medium":
        return f"[~] {severity.upper()}"
    if key == "low":
        return f"[.] {severity.upper()}"
    return severity.upper() or "UNKNOWN"


def format_integrity_findings_table(result: dict[str, Any]) -> list[list[str]]:
    rows: list[list[str]] = []
    for finding in result.get("findings") or []:
        evidence = finding.get("evidence") or []
        quote = ""
        if evidence and isinstance(evidence[0], dict):
            quote = str(evidence[0].get("quote", ""))
        rows.append(
            [
                _severity_label(str(finding.get("severity", ""))),
                str(finding.get("category", "")),
                str(finding.get("description", "")),
                quote,
                str(finding.get("suggested_fix", "") or ""),
            ]
        )
    return rows


def _parse_integrity_result(formatted: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(formatted)
    except json.JSONDecodeError:
        return None, formatted
    if not isinstance(payload, dict):
        return None, "Unexpected integrity response."
    if payload.get("error"):
        return None, str(payload["error"])
    if payload.get("findings") is None and payload.get("finding_count") is None:
        return None, formatted
    return payload, None


def analyze_document_integrity_ui(
    upload_file: Any,
    source_text: str,
    selected_checks: list[str],
) -> tuple[str, list[list[str]]]:
    """Run document integrity analysis on an upload or pasted text."""
    path = resolve_upload_path(upload_file)
    text = source_text.strip()
    if path is None and not text:
        return "Upload a document or paste text to analyze.", []

    data: dict[str, str] = {}
    if selected_checks:
        data["checks"] = ",".join(selected_checks)

    if path is not None:
        formatted = _post_document_file("/v1/documents/analyze-integrity", path, data=data or None)
    else:
        url = f"{API_BASE}/v1/documents/analyze-integrity?async=true"
        response = requests.post(
            url,
            json={"text": text, **({"checks": selected_checks} if selected_checks else {})},
            headers=_api_headers(),
            timeout=120,
        )
        formatted = _format_json_response(response)

    result, error = _parse_integrity_result(formatted)
    if error:
        return error, []
    assert result is not None
    return format_integrity_summary(result), format_integrity_findings_table(result)


def format_process_result_for_display(result: dict[str, Any]) -> dict[str, Any]:
    """Trim large text fields for Gradio output."""
    display = dict(result)
    extraction = display.get("extraction")
    if isinstance(extraction, dict) and isinstance(extraction.get("text"), str):
        text = extraction["text"]
        if len(text) > 2000:
            trimmed = dict(extraction)
            trimmed["text_preview"] = text[:2000] + "\n...(truncated)"
            trimmed.pop("text", None)
            display["extraction"] = trimmed
    return display


def process_document_ui(
    upload_file: Any,
    sentences: int,
    include_summarize: bool,
    include_pii: bool,
    include_text: bool,
    vertical: str,
    selected_entities: list[str],
    entities: str,
) -> str:
    """Run unified extract, classify, summarize, and PII pipeline via async jobs."""
    path = resolve_upload_path(upload_file)
    if path is None:
        return "Upload a document."

    data = {
        "sentences": str(int(sentences)),
        "include_summarize": str(include_summarize).lower(),
        "include_pii": str(include_pii).lower(),
        "include_text": str(include_text).lower(),
    }
    if vertical.strip():
        data["vertical"] = vertical.strip()
    else:
        entity_csv = resolve_pii_entity_list(
            selected_entities=selected_entities,
            entities_text=entities,
        )
        if entity_csv:
            data["entities"] = entity_csv

    with path.open("rb") as handle:
        response = requests.post(
            f"{API_BASE}/v1/documents/process?async=true",
            files={"file": (path.name, handle, "application/octet-stream")},
            data=data,
            headers=_api_headers(),
            timeout=120,
        )

    formatted = _format_json_response(response)
    try:
        payload = json.loads(formatted)
    except json.JSONDecodeError:
        return formatted

    if isinstance(payload, dict) and payload.get("classification") is not None:
        return json.dumps(format_process_result_for_display(payload), indent=2)
    return formatted


def compare_documents_ui(file_a: Any, file_b: Any) -> str:
    path_a = resolve_upload_path(file_a)
    path_b = resolve_upload_path(file_b)
    if path_a is None or path_b is None:
        return "Upload two documents to compare."

    with path_a.open("rb") as handle_a, path_b.open("rb") as handle_b:
        response = requests.post(
            f"{API_BASE}/v1/documents/compare?async=true",
            files={
                "file_a": (path_a.name, handle_a, "application/octet-stream"),
                "file_b": (path_b.name, handle_b, "application/octet-stream"),
            },
            headers=_api_headers(),
            timeout=120,
        )
    return _format_json_response(response)


def _show_feature_panel(selected: str) -> list[Any]:
    """Return visibility updates for each main content panel."""
    import gradio as gr

    panels = _PANEL_KEYS
    return [gr.update(visible=(name == selected)) for name in panels]


_PANEL_KEYS = ("process", "integrity", "tools", "annotate", "sensitive", "structure", "summarize")

_NAV_SECTIONS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "DOCUMENTS",
        (
            ("process", "Process pipeline"),
            ("integrity", "Integrity analysis"),
            ("tools", "Document tools"),
        ),
    ),
    (
        "PDF",
        (
            ("annotate", "PDF annotate"),
            ("sensitive", "Sensitive PDF"),
            ("structure", "PDF structure"),
        ),
    ),
    (
        "TEXT",
        (("summarize", "Text summarize"),),
    ),
)


def _nav_button_updates(selected: str) -> list[Any]:
    """Return variant updates for sidebar navigation buttons."""
    import gradio as gr

    updates: list[Any] = []
    for _section, items in _NAV_SECTIONS:
        for key, _label in items:
            updates.append(gr.update(variant="primary" if key == selected else "secondary"))
    return updates


def _select_feature_panel(selected: str) -> list[Any]:
    """Switch main panel and highlight the active navigation button."""
    return _show_feature_panel(selected) + _nav_button_updates(selected)


_DEMO_THEME = None

# High-contrast palette (WCAG-friendly). Orange is reserved for primary actions only.
_TEXT = "#0f172a"
_TEXT_MUTED = "#475569"
_BORDER = "#cbd5e1"
_BG = "#ffffff"
_BG_SOFT = "#f8fafc"
_ACCENT = "#c2410c"
_ACCENT_HOVER = "#9a3412"
_NAV_ACTIVE_BAR = "#c2410c"


def _demo_theme():
    """Light theme with dark text on white. Neutral chrome, orange call-to-action buttons."""
    global _DEMO_THEME
    if _DEMO_THEME is not None:
        return _DEMO_THEME

    import gradio as gr

    _DEMO_THEME = (
        gr.themes.Soft(
            primary_hue=gr.themes.colors.orange,
            secondary_hue=gr.themes.colors.slate,
            neutral_hue=gr.themes.colors.slate,
            font=gr.themes.GoogleFont("Inter"),
        )
        .set(
            body_background_fill=_BG,
            body_background_fill_dark=_BG,
            block_background_fill=_BG,
            block_background_fill_dark=_BG,
            block_border_color=_BORDER,
            block_border_width="1px",
            block_label_background_fill=_BG,
            block_label_background_fill_dark=_BG,
            block_label_text_color=_TEXT,
            block_label_text_color_dark=_TEXT,
            block_title_background_fill=_BG,
            block_title_background_fill_dark=_BG,
            block_title_text_color=_TEXT,
            block_title_text_color_dark=_TEXT,
            body_text_color=_TEXT,
            body_text_color_dark=_TEXT,
            body_text_color_subdued=_TEXT_MUTED,
            body_text_color_subdued_dark=_TEXT_MUTED,
            button_primary_background_fill=_ACCENT,
            button_primary_background_fill_hover=_ACCENT_HOVER,
            button_primary_text_color=_BG,
            button_secondary_background_fill=_BG,
            button_secondary_background_fill_dark=_BG,
            button_secondary_background_fill_hover=_BG_SOFT,
            button_secondary_background_fill_hover_dark=_BG_SOFT,
            button_secondary_text_color=_TEXT,
            button_secondary_text_color_dark=_TEXT,
            button_secondary_border_color=_BORDER,
            button_secondary_border_color_dark=_BORDER,
            input_background_fill=_BG,
            input_background_fill_dark=_BG,
            input_background_fill_hover=_BG_SOFT,
            input_background_fill_hover_dark=_BG_SOFT,
            input_background_fill_focus=_BG,
            input_background_fill_focus_dark=_BG,
            input_border_color=_BORDER,
            input_border_color_dark=_BORDER,
            input_border_color_hover="#94a3b8",
            input_border_color_hover_dark="#94a3b8",
            input_border_color_focus=_ACCENT,
            input_border_color_focus_dark=_ACCENT,
            input_placeholder_color=_TEXT_MUTED,
            input_placeholder_color_dark=_TEXT_MUTED,
            checkbox_label_background_fill=_BG,
            checkbox_label_background_fill_dark=_BG,
            checkbox_label_text_color=_TEXT,
            checkbox_label_text_color_dark=_TEXT,
            checkbox_label_border_color=_BORDER,
            checkbox_label_border_color_dark=_BORDER,
            slider_color=_ACCENT,
            link_text_color=_ACCENT,
            link_text_color_hover=_ACCENT_HOVER,
            border_color_primary=_BORDER,
            background_fill_primary=_BG,
            background_fill_primary_dark=_BG,
            background_fill_secondary=_BG,
            background_fill_secondary_dark=_BG,
            color_accent=_ACCENT,
            color_accent_soft=_BG_SOFT,
            table_even_background_fill=_BG_SOFT,
            table_odd_background_fill=_BG,
            table_border_color=_BORDER,
            table_text_color=_TEXT,
            table_text_color_dark=_TEXT,
        )
    )
    return _DEMO_THEME


_APP_CSS = f"""
.gradio-container {{
    background: {_BG} !important;
    color: {_TEXT} !important;
    max-width: 1200px !important;
    font-size: 15px !important;
    line-height: 1.55 !important;
    color-scheme: light !important;
}}
.gradio-container .prose,
.gradio-container label,
.gradio-container p,
.gradio-container span,
.gradio-container h1,
.gradio-container h2,
.gradio-container h3,
.gradio-container h4,
.gradio-container legend {{
    color: {_TEXT} !important;
}}
.gradio-container code,
.gradio-container pre {{
    background: {_BG_SOFT} !important;
    color: {_TEXT} !important;
    border: 1px solid {_BORDER} !important;
}}
.app-shell {{
    gap: 0 !important;
    align-items: stretch !important;
    min-height: 88vh;
}}
.sidebar {{
    background: {_BG_SOFT} !important;
    border-right: 1px solid {_BORDER} !important;
    padding: 1.25rem 0.9rem 1.5rem;
}}
.sidebar-brand {{
    margin: 0 0 0.35rem 0 !important;
    font-size: 1.1rem !important;
    font-weight: 700 !important;
    color: {_TEXT} !important;
}}
.sidebar-status {{
    font-size: 0.85rem !important;
    color: {_TEXT_MUTED} !important;
    margin-bottom: 0.75rem !important;
    line-height: 1.45 !important;
}}
.sidebar-section {{
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: {_TEXT_MUTED} !important;
    margin: 1rem 0 0.35rem 0.15rem;
}}
.main-panel {{
    padding: 1.5rem 1.75rem 2rem;
    background: {_BG} !important;
}}
.panel-title {{
    margin-top: 0 !important;
    margin-bottom: 0.35rem !important;
    color: {_TEXT} !important;
    font-weight: 700 !important;
    font-size: 1.35rem !important;
}}
.panel-desc {{
    color: {_TEXT_MUTED} !important;
    font-size: 0.95rem;
    margin-bottom: 1.25rem !important;
    line-height: 1.55 !important;
    max-width: 52rem;
}}
.sidebar .nav-btn {{
    width: 100% !important;
    margin-bottom: 0.35rem !important;
}}
.sidebar .nav-btn button,
.sidebar .nav-btn .gr-button {{
    width: 100% !important;
    justify-content: flex-start !important;
    text-align: left !important;
    font-weight: 500 !important;
    font-size: 0.92rem !important;
    border-radius: 6px !important;
    min-height: 2.35rem !important;
    box-shadow: none !important;
    color: {_TEXT} !important;
    background: {_BG} !important;
    border: 1px solid {_BORDER} !important;
}}
.sidebar .nav-btn button.secondary:hover,
.sidebar .nav-btn button:not(.primary):hover {{
    background: {_BG} !important;
    border-color: #94a3b8 !important;
}}
.sidebar .nav-btn button.primary,
.sidebar .nav-btn .primary {{
    background: {_BG} !important;
    color: {_TEXT} !important;
    border: 1px solid {_BORDER} !important;
    border-left: 4px solid {_NAV_ACTIVE_BAR} !important;
    font-weight: 700 !important;
    padding-left: 0.65rem !important;
}}
.main-panel .block,
.main-panel .form,
.main-panel .panel {{
    border-color: {_BORDER} !important;
    background: {_BG} !important;
}}
.main-panel label,
.main-panel .label-wrap,
.main-panel .label-wrap span,
.main-panel .block-label,
.main-panel .block label {{
    color: {_TEXT} !important;
    font-weight: 600 !important;
    background: transparent !important;
}}
.main-panel textarea,
.main-panel input,
.main-panel select {{
    color: {_TEXT} !important;
    background: {_BG} !important;
    border-color: {_BORDER} !important;
    font-size: 0.95rem !important;
}}
.main-panel input::placeholder,
.main-panel textarea::placeholder {{
    color: {_TEXT_MUTED} !important;
    opacity: 1 !important;
}}
.main-panel .file-upload,
.main-panel .upload-container {{
    border: 1px dashed #94a3b8 !important;
    background: {_BG_SOFT} !important;
}}
.main-panel .file-upload span,
.main-panel .upload-container span,
.main-panel .file-upload p,
.main-panel .upload-container p {{
    color: {_TEXT} !important;
}}
.main-panel .primary > button,
.main-panel button.primary {{
    background: {_ACCENT} !important;
    border-color: {_ACCENT} !important;
    color: {_BG} !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
}}
.main-panel .primary > button:hover,
.main-panel button.primary:hover {{
    background: {_ACCENT_HOVER} !important;
    border-color: {_ACCENT_HOVER} !important;
}}
.main-panel .secondary > button,
.main-panel button.secondary {{
    background: {_BG} !important;
    color: {_TEXT} !important;
    border: 1px solid {_BORDER} !important;
}}
.findings-table table,
.findings-table thead,
.findings-table tbody,
.findings-table tr,
.findings-table th,
.findings-table td {{
    background: {_BG} !important;
    color: {_TEXT} !important;
    border: 1px solid {_BORDER} !important;
    font-size: 0.9rem !important;
    line-height: 1.45 !important;
}}
.findings-table thead th {{
    background: {_BG_SOFT} !important;
    font-weight: 700 !important;
}}
.findings-table tbody tr:nth-child(even) td {{
    background: {_BG_SOFT} !important;
}}
.findings-table .table-wrap,
.findings-table .wrap {{
    background: {_BG} !important;
}}

/* Dropdowns: force readable light menus (Gradio 5). */
.gradio-container .block-label,
.gradio-container .label-wrap,
.gradio-container .label-wrap span,
.gradio-container label {{
    background: transparent !important;
    background-color: transparent !important;
    color: {_TEXT} !important;
    border: none !important;
    box-shadow: none !important;
}}
.gradio-container .dropdown,
.gradio-container .dropdown .wrap,
.gradio-container .dropdown .wrap input,
.gradio-container .dropdown input,
.gradio-container .single-select,
.gradio-container .single-select .wrap,
.gradio-container .multiselect,
.gradio-container div.block.dropdown,
.gradio-container div.block.dropdown .wrap {{
    background: {_BG} !important;
    background-color: {_BG} !important;
    color: {_TEXT} !important;
}}
.gradio-container ul.options,
.gradio-container .options,
.gradio-container [role="listbox"],
.gradio-container .dropdown ul.options,
.gradio-container .dropdown ul,
.gradio-container .overflow-menu,
.gradio-container .filterable-dropdown ul {{
    background: {_BG} !important;
    background-color: {_BG} !important;
    color: {_TEXT} !important;
    border: 1px solid {_BORDER} !important;
    box-shadow: 0 4px 12px rgba(15, 23, 42, 0.12) !important;
}}
.gradio-container ul.options li,
.gradio-container .options li,
.gradio-container ul.options li.item,
.gradio-container [role="listbox"] [role="option"],
.gradio-container .dropdown li {{
    background: {_BG} !important;
    background-color: {_BG} !important;
    color: {_TEXT} !important;
}}
.gradio-container ul.options li:hover,
.gradio-container ul.options li.selected,
.gradio-container .options li:hover,
.gradio-container .options li.selected,
.gradio-container [role="option"]:hover,
.gradio-container [role="option"][aria-selected="true"],
.gradio-container .dropdown li:hover,
.gradio-container .dropdown li.selected {{
    background: {_BG_SOFT} !important;
    background-color: {_BG_SOFT} !important;
    color: {_TEXT} !important;
}}
.gradio-container .dropdown svg,
.gradio-container .single-select svg {{
    color: {_TEXT_MUTED} !important;
    fill: {_TEXT_MUTED} !important;
}}
"""


def build_ui():
    import gradio as gr

    action_choices = [
        "Highlight",
        "Redact",
        "Frame",
        "Underline",
        "Squiggly",
        "Strikeout",
    ]
    office_types = [".pdf", ".docx", ".xlsx", ".pptx", ".csv", ".txt", ".md", ".json"]
    pii_entity_choices = list_pii_entity_choices()
    default_pii_entities = default_pii_entity_selection(pii_entity_choices)

    with gr.Blocks(
        title="Document Intelligence Platform",
        theme=_demo_theme(),
        css=_APP_CSS,
    ) as demo:
        with gr.Row(elem_classes=["app-shell"]):
            with gr.Column(scale=1, min_width=230, elem_classes=["sidebar"]):
                gr.Markdown("### Document Intelligence", elem_classes=["sidebar-brand"])
                gr.Markdown(check_api_health(), elem_classes=["sidebar-status"])

                nav_buttons: list[Any] = []
                for section_title, items in _NAV_SECTIONS:
                    gr.Markdown(section_title, elem_classes=["sidebar-section"])
                    for key, label in items:
                        nav_buttons.append(
                            gr.Button(
                                label,
                                variant="primary" if key == "process" else "secondary",
                                elem_classes=["nav-btn"],
                            )
                        )

                gr.Markdown(
                    f"API: `{API_BASE}`",
                    elem_classes=["sidebar-status"],
                )

            with gr.Column(scale=4, elem_classes=["main-panel"]):
                with gr.Group(visible=True) as process_panel:
                    gr.Markdown("## Process pipeline", elem_classes=["panel-title"])
                    gr.Markdown(
                        "Extract, classify, summarize, and scan for PII in one async job. "
                        "Requires Redis and a worker. Office formats need the documents extra on the API.",
                        elem_classes=["panel-desc"],
                    )
                    from docintel.capabilities.compliance.presets import list_vertical_presets

                    vertical_choices = [""] + sorted(list_vertical_presets().keys())
                    process_file = gr.File(label="Document upload", file_types=office_types)
                    with gr.Row():
                        process_sentences = gr.Slider(1, 10, value=3, step=1, label="Summary sentences")
                        process_vertical = gr.Dropdown(
                            vertical_choices,
                            value="",
                            label="PII vertical preset (optional)",
                        )
                    with gr.Row():
                        process_include_summary = gr.Checkbox(label="Include summary", value=True)
                        process_include_pii = gr.Checkbox(label="Include PII scan", value=True)
                        process_include_text = gr.Checkbox(label="Include extracted text", value=False)
                    process_entity_picker = gr.CheckboxGroup(
                        choices=pii_entity_choices,
                        value=default_pii_entities,
                        label="PII types to detect",
                        info="Uncheck types you do not need. A vertical preset below replaces this list.",
                    )
                    process_entities = gr.Textbox(
                        label="Additional PII entities (optional)",
                        placeholder="CUSTOM_ENTITY_NAME",
                    )
                    process_btn = gr.Button("Process document", variant="primary")
                    process_output = gr.Textbox(label="Results", lines=18)

                with gr.Group(visible=False) as integrity_panel:
                    gr.Markdown("## Integrity analysis", elem_classes=["panel-title"])
                    gr.Markdown(
                        "Find placeholders, broken references, naming drift, number mismatches, "
                        "and thin sections. Uses async jobs when Redis is available. "
                        "Severity labels: `[!]` high, `[~]` medium, `[.]` low.",
                        elem_classes=["panel-desc"],
                    )
                    integrity_file = gr.File(label="Document upload", file_types=office_types)
                    integrity_checks = gr.CheckboxGroup(
                        list(V1_CHECKS),
                        value=list(V1_CHECKS),
                        label="Checks to run",
                    )
                    integrity_text = gr.Textbox(
                        label="Or paste text",
                        lines=8,
                        placeholder="Paste policy or contract text if you are not uploading a file.",
                    )
                    integrity_btn = gr.Button("Analyze integrity", variant="primary")
                    integrity_summary = gr.Textbox(label="Summary", lines=5)
                    integrity_table = gr.Dataframe(
                        headers=["Severity", "Category", "Description", "Evidence", "Suggested fix"],
                        label="Findings",
                        interactive=False,
                        elem_classes=["findings-table"],
                        wrap=True,
                    )

                with gr.Group(visible=False) as tools_panel:
                    gr.Markdown("## Document tools", elem_classes=["panel-title"])
                    gr.Markdown(
                        "Identify, extract, classify, summarize, scan for PII, and compare documents.",
                        elem_classes=["panel-desc"],
                    )
                    doc_file = gr.File(label="Document upload", file_types=office_types)
                    with gr.Row():
                        compare_file_a = gr.File(label="Compare document A", file_types=office_types)
                        compare_file_b = gr.File(label="Compare document B", file_types=office_types)
                    doc_sentences = gr.Slider(1, 10, value=3, step=1, label="Summary sentences")
                    tools_entity_picker = gr.CheckboxGroup(
                        choices=pii_entity_choices,
                        value=default_pii_entities,
                        label="PII types to detect",
                    )
                    tools_entities = gr.Textbox(
                        label="Additional PII entities (optional)",
                        placeholder="CUSTOM_ENTITY_NAME",
                    )
                    with gr.Row():
                        identify_btn = gr.Button("Identify")
                        extract_btn = gr.Button("Extract text")
                        classify_btn = gr.Button("Classify")
                    with gr.Row():
                        summarize_doc_btn = gr.Button("Summarize file")
                        detect_pii_btn = gr.Button("Detect PII")
                        compare_btn = gr.Button("Compare files")
                    doc_output = gr.Textbox(label="Results", lines=14)

                with gr.Group(visible=False) as annotate_panel:
                    gr.Markdown("## PDF annotate", elem_classes=["panel-title"])
                    gr.Markdown(
                        "Search a PDF with a regex pattern and apply highlight, redact, or markup.",
                        elem_classes=["panel-desc"],
                    )
                    annotate_file = gr.File(label="PDF upload", file_types=[".pdf"])
                    with gr.Row():
                        annotate_pattern = gr.Textbox(label="Regex pattern", placeholder="CONFIDENTIAL")
                        annotate_action = gr.Dropdown(action_choices, value="Highlight", label="Action")
                    annotate_btn = gr.Button("Annotate PDF", variant="primary")
                    annotate_output = gr.File(label="Annotated PDF")
                    annotate_status = gr.Textbox(label="Status")

                with gr.Group(visible=False) as sensitive_panel:
                    gr.Markdown("## Sensitive PDF", elem_classes=["panel-title"])
                    gr.Markdown(
                        "OCR plus Presidio for scanned PDFs. Choose which PII types to scan for.",
                        elem_classes=["panel-desc"],
                    )
                    sensitive_file = gr.File(label="PDF upload", file_types=[".pdf"])
                    sensitive_entity_picker = gr.CheckboxGroup(
                        choices=pii_entity_choices,
                        value=default_pii_entities,
                        label="PII types to detect",
                    )
                    with gr.Row():
                        sensitive_action = gr.Dropdown(action_choices, value="Highlight", label="Action")
                        sensitive_entities = gr.Textbox(
                            label="Additional PII entities (optional)",
                            placeholder="CUSTOM_ENTITY_NAME",
                        )
                    with gr.Row():
                        sensitive_force_ocr = gr.Checkbox(label="Force OCR on all pages", value=False)
                        sensitive_text_layer = gr.Checkbox(label="Add searchable text layer", value=True)
                    sensitive_btn = gr.Button("Detect and annotate", variant="primary")
                    sensitive_output = gr.File(label="Processed PDF")
                    sensitive_report = gr.Textbox(label="Findings report", lines=12)

                with gr.Group(visible=False) as structure_panel:
                    gr.Markdown("## PDF structure", elem_classes=["panel-title"])
                    gr.Markdown(
                        "Convert scanned PDFs into a curated digital PDF. Set "
                        "`DOCINTEL_LLM_PROVIDER` on the API server (default: ollama).",
                        elem_classes=["panel-desc"],
                    )
                    structure_file = gr.File(label="PDF upload", file_types=[".pdf"])
                    with gr.Row():
                        structure_mode = gr.Dropdown(
                            ["curate", "searchable"],
                            value="curate",
                            label="Output mode",
                        )
                        structure_force_ocr = gr.Checkbox(label="Force OCR on all pages", value=False)
                    structure_btn = gr.Button("Structure PDF", variant="primary")
                    structure_output = gr.File(label="Structured PDF")
                    structure_report = gr.Textbox(label="Structure report", lines=8)

                with gr.Group(visible=False) as summarize_panel:
                    gr.Markdown("## Text summarize", elem_classes=["panel-title"])
                    gr.Markdown(
                        "Extractive summary from pasted plain text.",
                        elem_classes=["panel-desc"],
                    )
                    source_text = gr.Textbox(label="Source text", lines=10)
                    sentence_count = gr.Slider(1, 10, value=3, step=1, label="Sentences")
                    summary_btn = gr.Button("Summarize", variant="primary")
                    summary_output = gr.Textbox(label="Summary result", lines=10)

        panel_outputs = [
            process_panel,
            integrity_panel,
            tools_panel,
            annotate_panel,
            sensitive_panel,
            structure_panel,
            summarize_panel,
        ]

        nav_keys = [key for _section, items in _NAV_SECTIONS for key, _label in items]
        for nav_button, nav_key in zip(nav_buttons, nav_keys):
            nav_button.click(
                fn=lambda key=nav_key: _select_feature_panel(key),
                outputs=[*panel_outputs, *nav_buttons],
            )

        process_vertical.change(
            fn=pii_entities_for_vertical,
            inputs=process_vertical,
            outputs=process_entity_picker,
        )

        process_btn.click(
            process_document_ui,
            inputs=[
                process_file,
                process_sentences,
                process_include_summary,
                process_include_pii,
                process_include_text,
                process_vertical,
                process_entity_picker,
                process_entities,
            ],
            outputs=process_output,
        )
        integrity_btn.click(
            analyze_document_integrity_ui,
            inputs=[integrity_file, integrity_text, integrity_checks],
            outputs=[integrity_summary, integrity_table],
        )
        identify_btn.click(identify_document_ui, inputs=[doc_file], outputs=doc_output)
        extract_btn.click(extract_document_text_ui, inputs=[doc_file], outputs=doc_output)
        classify_btn.click(classify_document_ui, inputs=[doc_file], outputs=doc_output)
        summarize_doc_btn.click(
            summarize_document_ui,
            inputs=[doc_file, doc_sentences],
            outputs=doc_output,
        )
        detect_pii_btn.click(
            detect_pii_document_ui,
            inputs=[doc_file, tools_entity_picker, tools_entities],
            outputs=doc_output,
        )
        compare_btn.click(
            compare_documents_ui,
            inputs=[compare_file_a, compare_file_b],
            outputs=doc_output,
        )
        annotate_btn.click(
            annotate_pdf_ui,
            inputs=[annotate_file, annotate_pattern, annotate_action],
            outputs=[annotate_output, annotate_status],
        )
        sensitive_btn.click(
            detect_sensitive_ui,
            inputs=[
                sensitive_file,
                sensitive_action,
                sensitive_entity_picker,
                sensitive_entities,
                sensitive_force_ocr,
                sensitive_text_layer,
            ],
            outputs=[sensitive_output, sensitive_report],
        )
        structure_btn.click(
            structure_pdf_ui,
            inputs=[structure_file, structure_mode, structure_force_ocr],
            outputs=[structure_output, structure_report],
        )
        summary_btn.click(
            summarize_text_ui,
            inputs=[source_text, sentence_count],
            outputs=summary_output,
        )

    return demo


def launch_ui() -> None:
    demo = build_ui()
    demo.launch(server_name=GRADIO_HOST, server_port=GRADIO_PORT, share=False)


if __name__ == "__main__":
    launch_ui()
