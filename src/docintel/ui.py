"""Gradio upload UI for the document intelligence platform."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import requests

API_BASE = os.getenv("DOCINTEL_API_URL", "http://127.0.0.1:5000").rstrip("/")
API_KEY = os.getenv("DOCINTEL_API_KEY", "")


def _api_headers() -> dict[str, str]:
    if API_KEY.strip():
        return {"Authorization": f"Bearer {API_KEY.strip()}"}
    return {}
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
    if entities.strip():
        data["entities"] = entities.strip()

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

    with gr.Blocks(title="Document Intelligence Platform") as demo:
        gr.Markdown(
            "# Document Intelligence Platform\n"
            "Upload documents, detect sensitive data, structure PDFs, and summarize text. "
            f"Backend API: `{API_BASE}`"
        )
        gr.Markdown(check_api_health())

        with gr.Tab("PDF regex annotate"):
            with gr.Row():
                annotate_file = gr.File(label="PDF upload", file_types=[".pdf"])
                annotate_pattern = gr.Textbox(label="Regex pattern", placeholder="CONFIDENTIAL")
                annotate_action = gr.Dropdown(action_choices, value="Highlight", label="Action")
            annotate_btn = gr.Button("Annotate PDF")
            annotate_output = gr.File(label="Annotated PDF")
            annotate_status = gr.Textbox(label="Status")

            annotate_btn.click(
                annotate_pdf_ui,
                inputs=[annotate_file, annotate_pattern, annotate_action],
                outputs=[annotate_output, annotate_status],
            )

        with gr.Tab("Sensitive PDF (OCR + Presidio)"):
            gr.Markdown(
                "For scanned PDFs, EasyOCR extracts text and Presidio highlights PII. "
                "Leave entities blank to use the default preset."
            )
            with gr.Row():
                sensitive_file = gr.File(label="PDF upload", file_types=[".pdf"])
                sensitive_action = gr.Dropdown(action_choices, value="Highlight", label="Action")
            sensitive_entities = gr.Textbox(
                label="Presidio entities (comma-separated, optional)",
                placeholder="EMAIL_ADDRESS,PHONE_NUMBER,US_SSN,CREDIT_CARD,PERSON",
            )
            with gr.Row():
                sensitive_force_ocr = gr.Checkbox(label="Force OCR on all pages", value=False)
                sensitive_text_layer = gr.Checkbox(label="Add searchable text layer", value=True)
            sensitive_btn = gr.Button("Detect and annotate sensitive data")
            sensitive_output = gr.File(label="Processed PDF")
            sensitive_report = gr.Textbox(label="Findings report", lines=12)

            sensitive_btn.click(
                detect_sensitive_ui,
                inputs=[
                    sensitive_file,
                    sensitive_action,
                    sensitive_entities,
                    sensitive_force_ocr,
                    sensitive_text_layer,
                ],
                outputs=[sensitive_output, sensitive_report],
            )

        with gr.Tab("PDF structure (LLM)"):
            gr.Markdown(
                "Convert scanned or unstructured PDFs into a curated digital PDF. "
                "Requires `DOCINTEL_LLM_API_KEY` on the API server (default model: `gpt-4o-mini`). "
                "Get a key: [platform.openai.com/api-keys](https://platform.openai.com/api-keys) "
                "| [setup guide](https://platform.openai.com/docs/quickstart)."
            )
            with gr.Row():
                structure_file = gr.File(label="PDF upload", file_types=[".pdf"])
                structure_mode = gr.Dropdown(
                    ["curate", "searchable"],
                    value="curate",
                    label="Output mode",
                )
            structure_force_ocr = gr.Checkbox(label="Force OCR on all pages", value=False)
            structure_btn = gr.Button("Structure PDF")
            structure_output = gr.File(label="Structured PDF")
            structure_report = gr.Textbox(label="Structure report", lines=8)

            structure_btn.click(
                structure_pdf_ui,
                inputs=[structure_file, structure_mode, structure_force_ocr],
                outputs=[structure_output, structure_report],
            )

        with gr.Tab("Text summarization"):
            source_text = gr.Textbox(label="Source text", lines=10)
            sentence_count = gr.Slider(1, 10, value=3, step=1, label="Sentences")
            summary_btn = gr.Button("Summarize")
            summary_output = gr.Textbox(label="Summary result", lines=10)
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
