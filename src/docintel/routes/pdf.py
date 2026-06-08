"""PDF annotation API routes."""

from __future__ import annotations

import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file
from werkzeug.utils import secure_filename

from docintel.services.pdf import Action, annotate_pdf

pdf_bp = Blueprint("pdf", __name__, url_prefix="/v1/pdf")


def _upload_dir() -> Path:
    path = Path(current_app.config["UPLOAD_DIR"])
    path.mkdir(parents=True, exist_ok=True)
    return path


def _parse_pages(raw_pages: str | None) -> list[int] | None:
    if not raw_pages or not raw_pages.strip():
        return None
    return [int(page.strip()) for page in raw_pages.split(",") if page.strip()]


@pdf_bp.post("/annotate")
def annotate():
    """Search a PDF and apply highlight, redact, or other annotation actions."""
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return jsonify({"error": "Missing PDF file in form field 'file'."}), 400

    filename = secure_filename(upload.filename)
    if not filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported."}), 400

    action_raw = request.form.get("action", Action.HIGHLIGHT.value)
    try:
        action = Action.from_value(action_raw)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    pattern = request.form.get("pattern", "")
    if action != Action.REMOVE and not pattern.strip():
        return jsonify({"error": "Missing search pattern in form field 'pattern'."}), 400

    try:
        pages = _parse_pages(request.form.get("pages"))
    except ValueError:
        return jsonify({"error": "Invalid pages value. Use comma-separated page indexes."}), 400

    job_id = uuid.uuid4().hex[:12]
    work_dir = _upload_dir() / job_id
    work_dir.mkdir(parents=True, exist_ok=True)

    input_path = work_dir / filename
    output_path = work_dir / f"annotated_{filename}"
    upload.save(input_path)

    try:
        result = annotate_pdf(
            input_file=input_path,
            output_file=output_path,
            pattern=pattern,
            action=action,
            pages=pages,
        )
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    response_format = request.args.get("format", request.form.get("format", "file")).lower()

    if response_format == "json":
        payload = {
            "status": "ok",
            **result.to_dict(),
            "download_url": f"/v1/pdf/files/{job_id}/{output_path.name}",
        }
        return jsonify(payload), 200

    response = send_file(
        output_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=output_path.name,
    )
    response.headers["X-Docintel-Matches"] = str(result.matches)
    response.headers["X-Docintel-Pages-Processed"] = str(result.pages_processed)
    response.headers["X-Docintel-Action"] = result.action.value
    return response


@pdf_bp.get("/files/<job_id>/<filename>")
def download_file(job_id: str, filename: str):
    """Download a previously generated PDF when using JSON response mode."""
    safe_job = secure_filename(job_id)
    safe_name = secure_filename(filename)
    file_path = _upload_dir() / safe_job / safe_name

    if not file_path.is_file():
        return jsonify({"error": "Annotated PDF not found."}), 404

    return send_file(
        file_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=safe_name,
    )
