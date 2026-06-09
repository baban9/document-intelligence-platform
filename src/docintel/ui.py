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
            f"{API_BASE}/v1/pdf/annotate",
            files={"file": (path.name, handle, "application/pdf")},
            data={"pattern": pattern, "action": action},
            timeout=120,
        )

    if not response.ok:
        return None, _api_error(response)

    output = tempfile.NamedTemporaryFile(delete=False, suffix="_annotated.pdf")
    output.write(response.content)
    output.close()
    matches = response.headers.get("X-Docintel-Matches", "?")
    return output.name, f"Annotated PDF ready. Matches: {matches}"


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
            f"{API_BASE}/v1/pdf/detect-sensitive?format=json",
            files={"file": (path.name, handle, "application/pdf")},
            data=data,
            timeout=300,
        )

    if not response.ok:
        return None, _api_error(response)

    payload = response.json()
    download = requests.get(f"{API_BASE}{payload['download_url']}", timeout=120)
    if not download.ok:
        return None, "Processed PDF could not be downloaded."

    output = tempfile.NamedTemporaryFile(delete=False, suffix="_sensitive.pdf")
    output.write(download.content)
    output.close()

    summary = {
        "matches": payload.get("matches"),
        "finding_count": payload.get("finding_count"),
        "ocr_pages": payload.get("ocr_pages"),
        "findings": payload.get("findings", [])[:20],
    }
    return output.name, json.dumps(summary, indent=2)


def match_resume_ui(resume: str, job_description: str, top_keywords: int) -> str:
    if not resume.strip() or not job_description.strip():
        return "Provide both resume and job description text."

    response = requests.post(
        f"{API_BASE}/v1/match/resume",
        json={
            "resume": resume,
            "job_description": job_description,
            "top_keywords": int(top_keywords),
        },
        timeout=60,
    )
    if not response.ok:
        return _api_error(response)
    return json.dumps(response.json(), indent=2)


def structure_pdf_ui(pdf_file: Any, mode: str, force_ocr: bool) -> tuple[Any, str]:
    path = resolve_upload_path(pdf_file)
    if path is None:
        return None, "Upload a PDF file."

    with path.open("rb") as handle:
        response = requests.post(
            f"{API_BASE}/v1/pdf/structure?async=true",
            files={"file": (path.name, handle, "application/pdf")},
            data={"mode": mode, "force_ocr": str(force_ocr).lower()},
            timeout=120,
        )

    if response.status_code == 202:
        payload = response.json()
        poll_url = payload.get("poll_url")
        if not poll_url:
            return None, "Async job started but poll_url is missing."
        for _ in range(300):
            poll = requests.get(f"{API_BASE}{poll_url}", timeout=30)
            if not poll.ok:
                return None, _api_error(poll)
            job_payload = poll.json()
            job_status = job_payload.get("job_status")
            if job_status == "completed":
                payload = job_payload
                break
            if job_status == "failed":
                return None, job_payload.get("error", "Structure job failed.")
            time.sleep(2)
        else:
            return None, "Structure job timed out while polling."
    elif response.ok:
        payload = response.json()
    else:
        return None, _api_error(response)

    download_url = payload.get("download_url")
    if not download_url:
        return None, "Structured PDF is not ready yet."

    download = requests.get(f"{API_BASE}{download_url}", timeout=120)
    if not download.ok:
        return None, "Structured PDF could not be downloaded."

    output = tempfile.NamedTemporaryFile(delete=False, suffix="_structured.pdf")
    output.write(download.content)
    output.close()

    result = payload.get("result") or payload
    summary = {
        "job_status": payload.get("job_status"),
        "mode": result.get("mode"),
        "document_title": result.get("document_title"),
        "pages_processed": result.get("pages_processed"),
        "ocr_pages": result.get("ocr_pages"),
    }
    return output.name, json.dumps(summary, indent=2)


def summarize_text_ui(text: str, sentences: int) -> str:
    if not text.strip():
        return "Provide text to summarize."

    response = requests.post(
        f"{API_BASE}/v1/text/summarize",
        json={"text": text, "sentences": int(sentences)},
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
            "Upload documents, detect sensitive data, match resumes, and summarize text. "
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

        with gr.Tab("Resume matching"):
            resume_text = gr.Textbox(label="Resume", lines=8)
            job_text = gr.Textbox(label="Job description", lines=8)
            top_kw = gr.Slider(5, 50, value=15, step=1, label="Top keywords")
            match_btn = gr.Button("Score match")
            match_output = gr.Textbox(label="Match result", lines=12)
            match_btn.click(match_resume_ui, inputs=[resume_text, job_text, top_kw], outputs=match_output)

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
