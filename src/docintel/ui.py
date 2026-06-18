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


def detect_pii_document_ui(upload_file: Any) -> str:
    path = resolve_upload_path(upload_file)
    if path is None:
        return "Upload a document."
    return _post_document_file("/v1/documents/detect-pii", path)


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
    elif entities.strip():
        data["entities"] = entities.strip()

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

        office_types = [".pdf", ".docx", ".xlsx", ".csv", ".txt", ".md", ".json"]
        with gr.Tab("Document process"):
            gr.Markdown(
                "Run extract, classify, summarize, and PII detection in one async job. "
                "Requires Redis and a worker (`make run-worker` or docker-compose worker). "
                "Word and Excel need `pip install -e '.[documents]'` on the API server."
            )
            from docintel.capabilities.compliance.presets import list_vertical_presets

            vertical_choices = [""] + sorted(list_vertical_presets().keys())
            with gr.Row():
                process_file = gr.File(label="Document upload", file_types=office_types)
                process_sentences = gr.Slider(1, 10, value=3, step=1, label="Summary sentences")
            with gr.Row():
                process_include_summary = gr.Checkbox(label="Include summary", value=True)
                process_include_pii = gr.Checkbox(label="Include PII scan", value=True)
                process_include_text = gr.Checkbox(label="Include extracted text", value=False)
            with gr.Row():
                process_vertical = gr.Dropdown(
                    vertical_choices,
                    value="",
                    label="PII vertical preset (optional)",
                )
                process_entities = gr.Textbox(
                    label="PII entities override (comma-separated, optional)",
                    placeholder="EMAIL_ADDRESS,PHONE_NUMBER,US_SSN",
                )
            process_btn = gr.Button("Process document", variant="primary")
            process_output = gr.Textbox(label="Process report", lines=18)

            process_btn.click(
                process_document_ui,
                inputs=[
                    process_file,
                    process_sentences,
                    process_include_summary,
                    process_include_pii,
                    process_include_text,
                    process_vertical,
                    process_entities,
                ],
                outputs=process_output,
            )

        with gr.Tab("Document tools"):
            gr.Markdown(
                "Identify, extract, classify, summarize, scan for PII, and compare office documents. "
                "Requires `pip install -e '.[documents]'` for Word and Excel."
            )
            with gr.Row():
                doc_file = gr.File(label="Document upload", file_types=office_types)
                compare_file_a = gr.File(label="Compare document A", file_types=office_types)
                compare_file_b = gr.File(label="Compare document B", file_types=office_types)
            doc_sentences = gr.Slider(1, 10, value=3, step=1, label="Summary sentences")
            with gr.Row():
                identify_btn = gr.Button("Identify")
                extract_btn = gr.Button("Extract text")
                classify_btn = gr.Button("Classify")
            with gr.Row():
                summarize_doc_btn = gr.Button("Summarize file")
                detect_pii_btn = gr.Button("Detect PII")
                compare_btn = gr.Button("Compare files")
            doc_output = gr.Textbox(label="Document tools result", lines=14)

            identify_btn.click(identify_document_ui, inputs=[doc_file], outputs=doc_output)
            extract_btn.click(extract_document_text_ui, inputs=[doc_file], outputs=doc_output)
            classify_btn.click(classify_document_ui, inputs=[doc_file], outputs=doc_output)
            summarize_doc_btn.click(
                summarize_document_ui,
                inputs=[doc_file, doc_sentences],
                outputs=doc_output,
            )
            detect_pii_btn.click(detect_pii_document_ui, inputs=[doc_file], outputs=doc_output)
            compare_btn.click(
                compare_documents_ui,
                inputs=[compare_file_a, compare_file_b],
                outputs=doc_output,
            )

    return demo


def launch_ui() -> None:
    demo = build_ui()
    demo.launch(server_name=GRADIO_HOST, server_port=GRADIO_PORT, share=False)


if __name__ == "__main__":
    launch_ui()
