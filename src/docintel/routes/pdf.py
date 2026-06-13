"""PDF annotation API routes."""

from __future__ import annotations

import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file
from werkzeug.utils import secure_filename

from docintel.auth.limiter import limiter
from docintel.capabilities.extraction.formats import identify_document
from docintel.routes.document_upload import is_pdf_upload, pdf_required_message, read_upload
from docintel.services.pdf import (
    Action,
    DEFAULT_PII_ENTITIES,
    StructureMode,
    annotate_pdf,
    detect_sensitive_pdf,
    entities_for_vertical,
    list_supported_entities,
    list_vertical_presets,
    structure_pdf,
)

pdf_bp = Blueprint("pdf", __name__, url_prefix="/v1/pdf")


def _storage():
    from docintel.storage import get_storage

    return get_storage()


def _job_dir(job_id: str) -> Path:
    return _storage().job_dir(job_id)


def _parse_pages(raw_pages: str | None) -> list[int] | None:
    if not raw_pages or not raw_pages.strip():
        return None
    return [int(page.strip()) for page in raw_pages.split(",") if page.strip()]


def _prepare_pdf_upload(work_dir: Path):
    """Save upload and verify it is a PDF. Returns (saved_path, filename) or (None, error_response)."""
    upload = read_upload(request, "file")
    if upload is None:
        return None, (jsonify({"error": "Missing PDF file in form field 'file'."}), 400)

    filename = secure_filename(upload.filename)
    work_dir.mkdir(parents=True, exist_ok=True)
    input_path = work_dir / filename
    upload.save(input_path)

    identification = identify_document(
        input_path,
        filename=filename,
        content_type=upload.content_type,
    )
    if not is_pdf_upload(identification):
        input_path.unlink(missing_ok=True)
        return None, (jsonify(pdf_required_message(identification)), 415)

    return (input_path, filename), None


@pdf_bp.post("/annotate")
@limiter.limit("60 per hour")
def annotate():
    """Search a PDF and apply highlight, redact, or other annotation actions."""
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
    work_dir = _job_dir(job_id)
    prepared, upload_error = _prepare_pdf_upload(work_dir)
    if upload_error is not None:
        response, status = upload_error
        return response, status
    input_path, filename = prepared
    output_path = work_dir / f"annotated_{filename}"

    callback_url = request.form.get("callback_url", "").strip() or None
    run_async = _parse_async_flag()

    if run_async:
        return _enqueue_annotate_job(
            job_id=job_id,
            input_path=input_path,
            output_path=output_path,
            pattern=pattern,
            action=action,
            pages=pages,
            callback_url=callback_url,
        )

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

    _storage().sync_file(job_id, output_path.name)

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


def _parse_entities(raw_entities: str | None) -> list[str] | None:
    if not raw_entities or not raw_entities.strip():
        return None
    return [item.strip() for item in raw_entities.split(",") if item.strip()]


def _resolve_entities(raw_entities: str | None, vertical: str | None) -> list[str] | None:
    if vertical and vertical.strip():
        return list(entities_for_vertical(vertical))
    return _parse_entities(raw_entities)


@pdf_bp.get("/entities")
@limiter.limit("120 per hour")
def supported_entities():
    """List Presidio entity types available for sensitive detection."""
    try:
        entities = list_supported_entities()
    except Exception as exc:
        return jsonify({"error": str(exc)}), 503

    return jsonify(
        {
            "status": "ok",
            "default_entities": list(DEFAULT_PII_ENTITIES),
            "supported_entities": entities,
            "vertical_presets": list(list_vertical_presets()),
        }
    )


@pdf_bp.get("/presets")
@limiter.limit("120 per hour")
def vertical_presets():
    """List vertical entity packs for sensitive detection."""
    return jsonify(
        {
            "status": "ok",
            "presets": list_vertical_presets(),
        }
    )


@pdf_bp.post("/detect-sensitive")
@limiter.limit("30 per hour")
def detect_sensitive():
    """
    Detect PII with Presidio and annotate the PDF.

    Auto-falls back to EasyOCR when native PDF text is empty (scanned documents).
    """
    action_raw = request.form.get("action", Action.HIGHLIGHT.value)
    try:
        action = Action.from_value(action_raw)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if action == Action.REMOVE:
        return jsonify({"error": "Action 'Remove' is not supported for sensitive detection."}), 400

    entities = _parse_entities(request.form.get("entities"))
    vertical = request.form.get("vertical", "").strip() or None
    try:
        entities = _resolve_entities(request.form.get("entities"), vertical)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    pattern = request.form.get("pattern", "").strip() or None
    force_ocr = request.form.get("force_ocr", "false").lower() == "true"
    add_text_layer = request.form.get("add_text_layer", "true").lower() == "true"

    try:
        min_score = float(request.form.get("min_score", "0.35"))
    except ValueError:
        return jsonify({"error": "Field 'min_score' must be a number."}), 400

    callback_url = request.form.get("callback_url", "").strip() or None
    run_async = _parse_async_flag()

    job_id = uuid.uuid4().hex[:12]
    work_dir = _job_dir(job_id)
    prepared, upload_error = _prepare_pdf_upload(work_dir)
    if upload_error is not None:
        response, status = upload_error
        return response, status
    input_path, filename = prepared
    output_path = work_dir / f"sensitive_{filename}"

    if run_async:
        return _enqueue_detect_sensitive_job(
            job_id=job_id,
            input_path=input_path,
            output_path=output_path,
            action=action,
            entities=entities,
            pattern=pattern,
            force_ocr=force_ocr,
            add_text_layer=add_text_layer,
            min_score=min_score,
            callback_url=callback_url,
        )

    try:
        result = detect_sensitive_pdf(
            input_file=input_path,
            output_file=output_path,
            entities=entities,
            action=action,
            force_ocr=force_ocr,
            add_text_layer=add_text_layer,
            pattern=pattern,
            min_score=min_score,
        )
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    _storage().sync_file(job_id, output_path.name)

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
    response.headers["X-Docintel-OCR-Pages"] = ",".join(str(page) for page in result.ocr_pages)
    response.headers["X-Docintel-Action"] = result.action.value
    return response


def _parse_async_flag() -> bool:
    raw = request.args.get("async", request.form.get("async", "false"))
    return str(raw).lower() == "true"


@pdf_bp.post("/structure")
@limiter.limit("20 per hour")
def structure():
    """
    Structure an unstructured or scanned PDF with OCR and an LLM.

    Returns a curated typeset PDF (curate) or the original with a searchable
    invisible text layer (searchable).

    Use ``async=true`` to queue the job and poll ``GET /v1/jobs/<job_id>``.
    """
    mode_raw = request.form.get("mode", StructureMode.CURATE.value)
    try:
        mode = StructureMode.from_value(mode_raw)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    force_ocr = request.form.get("force_ocr", "false").lower() == "true"
    redact_before_llm = request.form.get("redact_before_llm", "false").lower() == "true"
    callback_url = request.form.get("callback_url", "").strip() or None
    run_async = _parse_async_flag()

    job_id = uuid.uuid4().hex[:12]
    work_dir = _job_dir(job_id)
    prepared, upload_error = _prepare_pdf_upload(work_dir)
    if upload_error is not None:
        response, status = upload_error
        return response, status
    input_path, filename = prepared
    output_path = work_dir / f"structured_{filename}"

    if run_async:
        return _enqueue_structure_job(
            job_id=job_id,
            input_path=input_path,
            output_path=output_path,
            mode=mode,
            force_ocr=force_ocr,
            redact_before_llm=redact_before_llm,
            callback_url=callback_url,
        )

    try:
        result = structure_pdf(
            input_file=input_path,
            output_file=output_path,
            mode=mode,
            force_ocr=force_ocr,
            redact_before_llm=redact_before_llm,
        )
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    _storage().sync_file(job_id, output_path.name)

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
    response.headers["X-Docintel-Pages-Processed"] = str(result.pages_processed)
    response.headers["X-Docintel-OCR-Pages"] = ",".join(str(page) for page in result.ocr_pages)
    response.headers["X-Docintel-Mode"] = result.mode.value
    response.headers["X-Docintel-Document-Title"] = result.document_title
    return response


def _enqueue_structure_job(
    *,
    job_id: str,
    input_path: Path,
    output_path: Path,
    mode: StructureMode,
    force_ocr: bool,
    redact_before_llm: bool,
    callback_url: str | None,
):
    from docintel.jobs.helpers import enqueue_async_response
    from docintel.jobs.models import JobType
    from docintel.jobs.queue import enqueue_structure_job

    accepted = enqueue_async_response(
        job_id=job_id,
        job_type=JobType.PDF_STRUCTURE,
        callback_url=callback_url,
    )
    if accepted[1] != 202:
        return accepted

    enqueue_structure_job(
        job_id=job_id,
        input_path=str(input_path),
        output_path=str(output_path),
        mode=mode.value,
        force_ocr=force_ocr,
        output_filename=output_path.name,
        redact_before_llm=redact_before_llm,
    )
    return accepted


def _enqueue_detect_sensitive_job(
    *,
    job_id: str,
    input_path: Path,
    output_path: Path,
    action: Action,
    entities: list[str] | None,
    pattern: str | None,
    force_ocr: bool,
    add_text_layer: bool,
    min_score: float,
    callback_url: str | None,
):
    from docintel.jobs.helpers import enqueue_async_response
    from docintel.jobs.models import JobType
    from docintel.jobs.queue import enqueue_detect_sensitive_job

    accepted = enqueue_async_response(
        job_id=job_id,
        job_type=JobType.PDF_DETECT_SENSITIVE,
        callback_url=callback_url,
    )
    if accepted[1] != 202:
        return accepted

    enqueue_detect_sensitive_job(
        job_id=job_id,
        input_path=str(input_path),
        output_path=str(output_path),
        output_filename=output_path.name,
        action=action.value,
        force_ocr=force_ocr,
        add_text_layer=add_text_layer,
        min_score=min_score,
        entities=entities,
        pattern=pattern,
    )
    return accepted


def _enqueue_annotate_job(
    *,
    job_id: str,
    input_path: Path,
    output_path: Path,
    pattern: str,
    action: Action,
    pages: list[int] | None,
    callback_url: str | None,
):
    from docintel.jobs.helpers import enqueue_async_response
    from docintel.jobs.models import JobType
    from docintel.jobs.queue import enqueue_annotate_job

    accepted = enqueue_async_response(
        job_id=job_id,
        job_type=JobType.PDF_ANNOTATE,
        callback_url=callback_url,
    )
    if accepted[1] != 202:
        return accepted

    enqueue_annotate_job(
        job_id=job_id,
        input_path=str(input_path),
        output_path=str(output_path),
        output_filename=output_path.name,
        pattern=pattern,
        action=action.value,
        pages=pages,
    )
    return accepted


@pdf_bp.get("/files/<job_id>/<filename>")
@limiter.limit("200 per hour")
def download_file(job_id: str, filename: str):
    """Download a previously generated PDF when using JSON response mode."""
    safe_job = secure_filename(job_id)
    safe_name = secure_filename(filename)

    try:
        file_path = _storage().resolve_download(safe_job, safe_name)
    except FileNotFoundError:
        return jsonify({"error": "Annotated PDF not found."}), 404

    return send_file(
        file_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=safe_name,
    )
