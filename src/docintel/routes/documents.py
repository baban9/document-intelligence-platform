"""Document intelligence routes (classification and comparison)."""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

from flask import Blueprint, jsonify, request

from docintel.auth.limiter import limiter
from docintel.capabilities.pipeline import ProcessOptions, process_document
from docintel.capabilities.extraction.formats import (
    extract_document_text,
    list_supported_types,
)
from docintel.capabilities.understanding.classify import classify_text
from docintel.capabilities.understanding.compare import compare_texts
from docintel.capabilities.understanding.understand import understand_document, understand_text
from docintel.services.pdf import entities_for_vertical
from docintel.services.integrity import V1_CHECKS, analyze_document_integrity
from docintel.services.pdf.pii import detect_pii_in_text
from docintel.services.summary import summarize_text
from docintel.services.summary.textrank import DEFAULT_SENTENCE_COUNT, MAX_SENTENCE_COUNT
from docintel.routes.document_upload import job_dir, parse_async_flag, read_upload, save_upload
from docintel.routes.async_enqueue import enqueue_background_job

documents_bp = Blueprint("documents", __name__, url_prefix="/v1/documents")

UNDERSTAND_ASYNC_BYTES = int(os.getenv("DOCINTEL_UNDERSTAND_ASYNC_BYTES", "524288"))


def _callback_url() -> str | None:
    payload = request.get_json(silent=True) or {}
    raw = payload.get("callback_url", request.form.get("callback_url", ""))
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def _text_from_request(field_name: str = "text") -> str | None:
    payload = request.get_json(silent=True) or {}
    if field_name in payload and isinstance(payload[field_name], str):
        return payload[field_name]
    form_value = request.form.get(field_name)
    if isinstance(form_value, str) and form_value.strip():
        return form_value
    return None


def _resolve_text_from_upload_or_body(field_name: str = "text") -> tuple[str | None, dict | None, int | None]:
    upload = read_upload(request, "file")
    if upload is not None:
        with tempfile.TemporaryDirectory(prefix="docintel-identify-") as temp_dir:
            saved = save_upload(upload, Path(temp_dir))
            try:
                extraction = extract_document_text(
                    saved.path,
                    filename=saved.filename,
                    content_type=saved.content_type,
                    identification=saved.identification,
                )
            except ValueError as exc:
                return None, {"error": str(exc)}, 400
            except RuntimeError as exc:
                return None, {"error": str(exc)}, 503
            return extraction.text, None, None

    text = _text_from_request(field_name)
    if text is None:
        return None, {"error": f"Provide JSON/form field '{field_name}' or upload a file."}, 400
    return text, None, None


def _resolve_compare_text(field_name: str, file_field: str) -> tuple[str | None, dict | None, int | None]:
    payload = request.get_json(silent=True) or {}
    value = payload.get(field_name)
    if isinstance(value, str) and value.strip():
        return value, None, None

    form_value = request.form.get(field_name)
    if isinstance(form_value, str) and form_value.strip():
        return form_value, None, None

    upload = read_upload(request, file_field)
    if upload is None:
        return None, None, None

    with tempfile.TemporaryDirectory(prefix="docintel-compare-") as temp_dir:
        saved = save_upload(upload, Path(temp_dir))
        try:
            extraction = extract_document_text(
                saved.path,
                filename=saved.filename,
                content_type=saved.content_type,
                identification=saved.identification,
            )
        except ValueError as exc:
            return None, {"error": str(exc), "field": file_field}, 415
        except RuntimeError as exc:
            return None, {"error": str(exc), "field": file_field}, 503
        return extraction.text, None, None


def _parse_sentence_count() -> tuple[int | None, dict | None, int | None]:
    payload = request.get_json(silent=True) or {}
    raw = payload.get("sentences", request.form.get("sentences", DEFAULT_SENTENCE_COUNT))
    try:
        sentences = int(raw)
    except (TypeError, ValueError):
        return None, {"error": "Field 'sentences' must be an integer."}, 400
    if sentences < 1 or sentences > MAX_SENTENCE_COUNT:
        return None, {
            "error": f"Field 'sentences' must be between 1 and {MAX_SENTENCE_COUNT}."
        }, 400
    return sentences, None, None


def _parse_entities(raw_entities: str | None) -> list[str] | None:
    if not raw_entities or not str(raw_entities).strip():
        return None
    return [item.strip() for item in str(raw_entities).split(",") if item.strip()]


def _resolve_entities(raw_entities: str | None, vertical: str | None) -> list[str] | None:
    if vertical and vertical.strip():
        return list(entities_for_vertical(vertical))
    return _parse_entities(raw_entities)


def _parse_min_score(default: float = 0.35) -> tuple[float | None, dict | None, int | None]:
    payload = request.get_json(silent=True) or {}
    raw = payload.get("min_score", request.form.get("min_score", default))
    try:
        return float(raw), None, None
    except (TypeError, ValueError):
        return None, {"error": "Field 'min_score' must be a number."}, 400


def _parse_bool_field(name: str, default: bool) -> bool:
    payload = request.get_json(silent=True) or {}
    if name in payload:
        value = payload[name]
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
    raw = request.form.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _parse_process_options() -> tuple[ProcessOptions | None, dict | None, int | None]:
    sentences, sentence_error, sentence_status = _parse_sentence_count()
    if sentence_error is not None:
        return None, sentence_error, sentence_status

    payload = request.get_json(silent=True) or {}
    vertical = payload.get("vertical", request.form.get("vertical", ""))
    vertical = vertical.strip() if isinstance(vertical, str) else ""
    entities_raw = payload.get("entities", request.form.get("entities"))
    try:
        entities = _resolve_entities(
            entities_raw if isinstance(entities_raw, str) else None,
            vertical or None,
        )
    except ValueError as exc:
        return None, {"error": str(exc)}, 400

    min_score, min_score_error, min_score_status = _parse_min_score()
    if min_score_error is not None:
        return None, min_score_error, min_score_status

    return (
        ProcessOptions(
            sentences=sentences or DEFAULT_SENTENCE_COUNT,
            include_summarize=_parse_bool_field("include_summarize", True),
            include_pii=_parse_bool_field("include_pii", True),
            include_text=_parse_bool_field("include_text", False),
            entities=entities,
            min_score=min_score or 0.35,
        ),
        None,
        None,
    )


def _parse_process_options_from_dict(
    payload: dict,
) -> tuple[ProcessOptions | None, dict | None, int | None]:
    raw_sentences = payload.get("sentences", DEFAULT_SENTENCE_COUNT)
    try:
        sentences = int(raw_sentences)
    except (TypeError, ValueError):
        return None, {"error": "Field 'sentences' must be an integer."}, 400
    if sentences < 1 or sentences > MAX_SENTENCE_COUNT:
        return None, {
            "error": f"Field 'sentences' must be between 1 and {MAX_SENTENCE_COUNT}."
        }, 400

    vertical = payload.get("vertical", "")
    vertical = vertical.strip() if isinstance(vertical, str) else ""
    entities_raw = payload.get("entities")
    try:
        entities = _resolve_entities(
            entities_raw if isinstance(entities_raw, str) else None,
            vertical or None,
        )
    except ValueError as exc:
        return None, {"error": str(exc)}, 400

    raw_min_score = payload.get("min_score", 0.35)
    try:
        min_score = float(raw_min_score)
    except (TypeError, ValueError):
        return None, {"error": "Field 'min_score' must be a number."}, 400

    def _bool_value(name: str, default: bool) -> bool:
        if name not in payload:
            return default
        value = payload[name]
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return default

    return (
        ProcessOptions(
            sentences=sentences,
            include_summarize=_bool_value("include_summarize", True),
            include_pii=_bool_value("include_pii", True),
            include_text=_bool_value("include_text", False),
            entities=entities,
            min_score=min_score,
        ),
        None,
        None,
    )


@documents_bp.get("/types")
@limiter.limit("120 per hour")
def supported_document_types():
    """List supported MIME types, extensions, and capabilities."""
    return jsonify({"status": "ok", "types": list_supported_types()})


@documents_bp.post("/ingest")
@limiter.limit("20 per hour")
def ingest_document():
    """Queue unified document processing for an object already stored in S3."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be JSON."}), 400

    operation = str(payload.get("operation", "process")).strip().lower()
    if operation != "process":
        return jsonify({"error": "Only operation 'process' is supported."}), 400

    from docintel.storage.s3_ingest import resolve_s3_location

    try:
        bucket, key = resolve_s3_location(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    options, option_error, option_status = _parse_process_options_from_dict(payload)
    if option_error is not None:
        return jsonify(option_error), option_status

    callback_raw = payload.get("callback_url", "")
    callback_url = callback_raw.strip() if isinstance(callback_raw, str) and callback_raw.strip() else None

    from docintel.jobs.models import JobType
    from docintel.jobs.queue import enqueue_s3_document_process_job

    job_id = uuid.uuid4().hex[:12]
    return enqueue_background_job(
        job_type=JobType.DOCUMENT_S3_PROCESS,
        callback_url=callback_url,
        enqueue_fn=enqueue_s3_document_process_job,
        job_id=job_id,
        bucket=bucket,
        key=key,
        options=options.to_dict() if options else {},
    )


@documents_bp.post("/identify")
@limiter.limit("120 per hour")
def identify_upload():
    """Detect document kind from an uploaded file."""
    upload = read_upload(request, "file")
    if upload is None:
        return jsonify({"error": "Missing file in form field 'file'."}), 400

    with tempfile.TemporaryDirectory(prefix="docintel-identify-") as temp_dir:
        saved = save_upload(upload, Path(temp_dir))
        return jsonify({"status": "ok", **saved.identification.to_dict()})


@documents_bp.post("/extract-text")
@limiter.limit("60 per hour")
def extract_text_upload():
    """Extract plain text from PDF, Word, Excel, CSV, JSON, or plain text uploads."""
    upload = read_upload(request, "file")
    if upload is None:
        return jsonify({"error": "Missing file in form field 'file'."}), 400

    if parse_async_flag():
        job_id = uuid.uuid4().hex[:12]
        saved = save_upload(upload, job_dir(job_id))
        from docintel.jobs.models import JobType
        from docintel.jobs.queue import enqueue_extract_text_job

        return enqueue_background_job(
            job_type=JobType.DOCUMENT_EXTRACT_TEXT,
            callback_url=_callback_url(),
            enqueue_fn=enqueue_extract_text_job,
            job_id=job_id,
            input_path=str(saved.path),
            filename=saved.filename,
            content_type=saved.content_type,
        )

    with tempfile.TemporaryDirectory(prefix="docintel-extract-") as temp_dir:
        saved = save_upload(upload, Path(temp_dir))
        try:
            result = extract_document_text(
                saved.path,
                filename=saved.filename,
                content_type=saved.content_type,
                identification=saved.identification,
            )
        except ValueError as exc:
            return jsonify({"error": str(exc), "detected": saved.identification.to_dict()}), 415
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 503

        return jsonify({"status": "ok", "filename": saved.filename, **result.to_dict()})


@documents_bp.post("/process")
@limiter.limit("30 per hour")
def process_upload():
    """Run extract, classify, summarize, and PII detection on one upload."""
    upload = read_upload(request, "file")
    if upload is None:
        return jsonify({"error": "Missing file in form field 'file'."}), 400

    options, option_error, option_status = _parse_process_options()
    if option_error is not None:
        return jsonify(option_error), option_status

    callback_url = _callback_url()
    run_async = parse_async_flag()

    if run_async:
        job_id = uuid.uuid4().hex[:12]
        work_dir = job_dir(job_id)
        saved = save_upload(upload, work_dir)
        return _enqueue_document_process_job(
            job_id=job_id,
            input_path=saved.path,
            filename=saved.filename,
            content_type=saved.content_type,
            options=options.to_dict() if options else {},
            callback_url=callback_url,
        )

    with tempfile.TemporaryDirectory(prefix="docintel-process-") as temp_dir:
        saved = save_upload(upload, Path(temp_dir))
        try:
            result = process_document(
                saved.path,
                filename=saved.filename,
                content_type=saved.content_type,
                options=options,
            )
        except ValueError as exc:
            return jsonify(
                {"error": str(exc), "detected": saved.identification.to_dict()}
            ), 415
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 503

        return jsonify({"status": "ok", **result.to_dict()})


def _enqueue_document_process_job(
    *,
    job_id: str,
    input_path: Path,
    filename: str,
    content_type: str | None,
    options: dict,
    callback_url: str | None,
):
    from docintel.jobs.models import JobType
    from docintel.jobs.queue import enqueue_document_process_job

    return enqueue_background_job(
        job_type=JobType.DOCUMENT_PROCESS,
        callback_url=callback_url,
        enqueue_fn=enqueue_document_process_job,
        job_id=job_id,
        input_path=str(input_path),
        filename=filename,
        content_type=content_type,
        options=options,
    )


@documents_bp.post("/classify")
@limiter.limit("120 per hour")
def classify_document():
    """Classify text or an uploaded document into enterprise function categories."""
    run_async = parse_async_flag()
    callback_url = _callback_url()
    upload = read_upload(request, "file")

    if run_async:
        from docintel.jobs.models import JobType
        from docintel.jobs.queue import enqueue_classify_document_job, enqueue_classify_job

        if upload is not None:
            job_id = uuid.uuid4().hex[:12]
            saved = save_upload(upload, job_dir(job_id))
            return enqueue_background_job(
                job_type=JobType.DOCUMENT_CLASSIFY,
                callback_url=callback_url,
                enqueue_fn=enqueue_classify_document_job,
                job_id=job_id,
                input_path=str(saved.path),
                filename=saved.filename,
                content_type=saved.content_type,
            )

        text = _text_from_request("text")
        if text is None:
            return jsonify({"error": "Provide JSON/form field 'text' or upload a file."}), 400
        return enqueue_background_job(
            job_type=JobType.TEXT_CLASSIFY,
            callback_url=callback_url,
            enqueue_fn=enqueue_classify_job,
            text=text,
        )

    text, error_payload, status_code = _resolve_text_from_upload_or_body("text")
    if error_payload is not None:
        return jsonify(error_payload), status_code

    try:
        result = classify_text(text or "")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"status": "ok", **result.to_dict()})


@documents_bp.post("/summarize")
@limiter.limit("100 per hour")
def summarize_document():
    """Summarize text or an uploaded document using extractive TextRank."""
    run_async = parse_async_flag()
    callback_url = _callback_url()
    upload = read_upload(request, "file")

    sentences, sentence_error, sentence_status = _parse_sentence_count()
    if sentence_error is not None:
        return jsonify(sentence_error), sentence_status

    if run_async:
        from docintel.jobs.models import JobType
        from docintel.jobs.queue import enqueue_summarize_document_job, enqueue_summarize_job

        if upload is not None:
            job_id = uuid.uuid4().hex[:12]
            saved = save_upload(upload, job_dir(job_id))
            return enqueue_background_job(
                job_type=JobType.DOCUMENT_SUMMARIZE,
                callback_url=callback_url,
                enqueue_fn=enqueue_summarize_document_job,
                job_id=job_id,
                input_path=str(saved.path),
                filename=saved.filename,
                content_type=saved.content_type,
                sentences=sentences or DEFAULT_SENTENCE_COUNT,
            )

        text = _text_from_request("text")
        if text is None:
            return jsonify({"error": "Provide JSON/form field 'text' or upload a file."}), 400
        return enqueue_background_job(
            job_type=JobType.TEXT_SUMMARIZE,
            callback_url=callback_url,
            enqueue_fn=enqueue_summarize_job,
            text=text,
            sentences=sentences or DEFAULT_SENTENCE_COUNT,
        )

    text, error_payload, status_code = _resolve_text_from_upload_or_body("text")
    if error_payload is not None:
        return jsonify(error_payload), status_code

    sentences, sentence_error, sentence_status = _parse_sentence_count()
    if sentence_error is not None:
        return jsonify(sentence_error), sentence_status

    try:
        result = summarize_text(text=text or "", sentence_count=sentences or DEFAULT_SENTENCE_COUNT)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"status": "ok", **result.to_dict()})


@documents_bp.post("/detect-pii")
@limiter.limit("60 per hour")
def detect_pii_document():
    """Detect Presidio PII in text or an uploaded document without PDF annotation."""
    run_async = parse_async_flag()
    callback_url = _callback_url()
    upload = read_upload(request, "file")

    payload = request.get_json(silent=True) or {}
    vertical = payload.get("vertical", request.form.get("vertical", ""))
    vertical = vertical.strip() if isinstance(vertical, str) else ""
    entities_raw = payload.get("entities", request.form.get("entities"))
    try:
        entities = _resolve_entities(
            entities_raw if isinstance(entities_raw, str) else None,
            vertical or None,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    min_score, min_score_error, min_score_status = _parse_min_score()
    if min_score_error is not None:
        return jsonify(min_score_error), min_score_status

    if run_async:
        from docintel.jobs.models import JobType
        from docintel.jobs.queue import enqueue_detect_pii_document_job, enqueue_detect_pii_text_job

        if upload is not None:
            job_id = uuid.uuid4().hex[:12]
            saved = save_upload(upload, job_dir(job_id))
            return enqueue_background_job(
                job_type=JobType.DOCUMENT_DETECT_PII,
                callback_url=callback_url,
                enqueue_fn=enqueue_detect_pii_document_job,
                job_id=job_id,
                input_path=str(saved.path),
                filename=saved.filename,
                content_type=saved.content_type,
                entities=entities,
                min_score=min_score or 0.35,
            )

        text = _text_from_request("text")
        if text is None:
            return jsonify({"error": "Provide JSON/form field 'text' or upload a file."}), 400
        return enqueue_background_job(
            job_type=JobType.TEXT_DETECT_PII,
            callback_url=callback_url,
            enqueue_fn=enqueue_detect_pii_text_job,
            text=text,
            entities=entities,
            min_score=min_score or 0.35,
        )

    text, error_payload, status_code = _resolve_text_from_upload_or_body("text")
    if error_payload is not None:
        return jsonify(error_payload), status_code

    payload = request.get_json(silent=True) or {}
    vertical = payload.get("vertical", request.form.get("vertical", ""))
    vertical = vertical.strip() if isinstance(vertical, str) else ""
    entities_raw = payload.get("entities", request.form.get("entities"))
    try:
        entities = _resolve_entities(
            entities_raw if isinstance(entities_raw, str) else None,
            vertical or None,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    min_score, min_score_error, min_score_status = _parse_min_score()
    if min_score_error is not None:
        return jsonify(min_score_error), min_score_status

    try:
        hits = detect_pii_in_text(text or "", entities=entities, min_score=min_score or 0.35)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503

    findings = [hit.to_dict() for hit in hits]
    return jsonify(
        {
            "status": "ok",
            "finding_count": len(findings),
            "findings": findings,
        }
    )


@documents_bp.post("/compare")
@limiter.limit("120 per hour")
def compare_documents():
    """Compare two policy or contract texts for overlap."""
    run_async = parse_async_flag()
    callback_url = _callback_url()

    if run_async:
        from docintel.jobs.models import JobType
        from docintel.jobs.queue import enqueue_compare_job

        upload_a = read_upload(request, "file_a")
        upload_b = read_upload(request, "file_b")
        if upload_a is not None or upload_b is not None:
            if upload_a is None or upload_b is None:
                return jsonify({"error": "Provide both file_a and file_b for file comparison."}), 400
            job_id = uuid.uuid4().hex[:12]
            work_dir = job_dir(job_id)
            saved_a = save_upload(upload_a, work_dir)
            saved_b = save_upload(upload_b, work_dir)
            return enqueue_background_job(
                job_type=JobType.DOCUMENT_COMPARE,
                callback_url=callback_url,
                enqueue_fn=enqueue_compare_job,
                job_id=job_id,
                path_a=str(saved_a.path),
                path_b=str(saved_b.path),
                filename_a=saved_a.filename,
                filename_b=saved_b.filename,
                content_type_a=saved_a.content_type,
                content_type_b=saved_b.content_type,
            )

        payload = request.get_json(silent=True) or {}
        text_a = payload.get("text_a", request.form.get("text_a", ""))
        text_b = payload.get("text_b", request.form.get("text_b", ""))
        if not isinstance(text_a, str) or not text_a.strip():
            return jsonify({"error": "Provide text_a/file_a for the first document."}), 400
        if not isinstance(text_b, str) or not text_b.strip():
            return jsonify({"error": "Provide text_b/file_b for the second document."}), 400
        return enqueue_background_job(
            job_type=JobType.DOCUMENT_COMPARE,
            callback_url=callback_url,
            enqueue_fn=enqueue_compare_job,
            text_a=text_a,
            text_b=text_b,
        )

    text_a, error_a, status_a = _resolve_compare_text("text_a", "file_a")
    if error_a is not None:
        return jsonify(error_a), status_a
    text_b, error_b, status_b = _resolve_compare_text("text_b", "file_b")
    if error_b is not None:
        return jsonify(error_b), status_b

    if not text_a:
        return jsonify({"error": "Provide text_a/file_a for the first document."}), 400
    if not text_b:
        return jsonify({"error": "Provide text_b/file_b for the second document."}), 400

    try:
        result = compare_texts(text_a, text_b)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"status": "ok", **result.to_dict()})


def _parse_integrity_checks() -> tuple[list[str] | None, dict | None, int | None]:
    payload = request.get_json(silent=True) or {}
    raw_checks = payload.get("checks", request.form.get("checks"))
    if raw_checks is None or raw_checks == "":
        return None, None, None
    if isinstance(raw_checks, list):
        checks = [str(item).strip() for item in raw_checks if str(item).strip()]
    else:
        checks = [part.strip() for part in str(raw_checks).split(",") if part.strip()]
    if not checks:
        return None, {"error": "checks must include at least one integrity check."}, 400
    unknown = sorted(set(checks) - set(V1_CHECKS))
    if unknown:
        return (
            None,
            {"error": f"Unknown integrity checks: {', '.join(unknown)}", "supported_checks": list(V1_CHECKS)},
            400,
        )
    return checks, None, None


@documents_bp.post("/analyze-integrity")
@limiter.limit("60 per hour")
def analyze_integrity_document():
    """Run document integrity analysis on text or an uploaded document."""
    run_async = parse_async_flag()
    callback_url = _callback_url()
    upload = read_upload(request, "file")
    checks, checks_error, checks_status = _parse_integrity_checks()
    if checks_error is not None:
        return jsonify(checks_error), checks_status

    if run_async:
        from docintel.jobs.models import JobType
        from docintel.jobs.queue import enqueue_integrity_document_job, enqueue_integrity_text_job

        if upload is not None:
            job_id = uuid.uuid4().hex[:12]
            saved = save_upload(upload, job_dir(job_id))
            return enqueue_background_job(
                job_type=JobType.DOCUMENT_INTEGRITY,
                callback_url=callback_url,
                enqueue_fn=enqueue_integrity_document_job,
                job_id=job_id,
                input_path=str(saved.path),
                filename=saved.filename,
                content_type=saved.content_type,
                checks=checks,
            )

        text = _text_from_request("text")
        if text is None:
            return jsonify({"error": "Provide JSON/form field 'text' or upload a file."}), 400
        return enqueue_background_job(
            job_type=JobType.TEXT_INTEGRITY,
            callback_url=callback_url,
            enqueue_fn=enqueue_integrity_text_job,
            text=text,
            checks=checks,
        )

    text, error_payload, status_code = _resolve_text_from_upload_or_body("text")
    if error_payload is not None:
        return jsonify(error_payload), status_code

    try:
        result = analyze_document_integrity(text or "", checks=checks)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"status": "ok", **result.to_dict()})


def _understand_options_from_request() -> tuple[dict, dict | None, int | None]:
    payload = request.get_json(silent=True) or {}
    sentences_raw = payload.get("sentences", request.form.get("sentences", DEFAULT_SENTENCE_COUNT))
    include_summary_raw = payload.get("include_summary", request.form.get("include_summary", "true"))
    include_pii_raw = payload.get("include_pii", request.form.get("include_pii", "true"))
    min_score_raw = payload.get("min_score", request.form.get("min_score", "0.35"))
    entities_raw = payload.get("entities", request.form.get("entities", ""))

    try:
        sentences = int(sentences_raw)
    except (TypeError, ValueError):
        return {}, {"error": "Field 'sentences' must be an integer."}, 400

    if sentences < 1 or sentences > MAX_SENTENCE_COUNT:
        return {}, {"error": f"Field 'sentences' must be between 1 and {MAX_SENTENCE_COUNT}."}, 400

    include_summary = str(include_summary_raw).lower() not in {"0", "false", "no"}
    include_pii = str(include_pii_raw).lower() not in {"0", "false", "no"}

    entities = None
    if isinstance(entities_raw, list):
        entities = [str(item) for item in entities_raw if str(item).strip()]
    elif isinstance(entities_raw, str) and entities_raw.strip():
        entities = [part.strip() for part in entities_raw.split(",") if part.strip()]

    try:
        min_score = float(min_score_raw)
    except (TypeError, ValueError):
        return {}, {"error": "Field 'min_score' must be a number."}, 400

    return {
        "sentences": sentences,
        "include_summary": include_summary,
        "include_pii": include_pii,
        "entities": entities,
        "min_score": min_score,
    }, None, None


@documents_bp.post("/understand")
@limiter.limit("60 per hour")
def understand_document_route():
    """Extract, classify, summarize, and scan an uploaded document for comprehension."""
    options, options_error, options_status = _understand_options_from_request()
    if options_error is not None:
        return jsonify(options_error), options_status

    callback_url = _callback_url()
    upload = read_upload(request, "file")
    if upload is not None:
        job_id = uuid.uuid4().hex[:12]
        saved = save_upload(upload, job_dir(job_id))
        file_size = saved.path.stat().st_size
        run_async = parse_async_flag() or file_size >= UNDERSTAND_ASYNC_BYTES

        if run_async:
            from docintel.jobs.models import JobType
            from docintel.jobs.queue import enqueue_understand_document_job

            return enqueue_background_job(
                job_type=JobType.DOCUMENT_UNDERSTAND,
                callback_url=callback_url,
                enqueue_fn=enqueue_understand_document_job,
                job_id=job_id,
                input_path=str(saved.path),
                filename=saved.filename,
                content_type=saved.content_type,
                **options,
            )

        try:
            result = understand_document(
                saved.path,
                filename=saved.filename,
                content_type=saved.content_type,
                **options,
            )
        except (ValueError, FileNotFoundError) as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(result.to_dict()), 200

    text = _text_from_request("text")
    if text is None:
        return jsonify({"error": "Provide JSON/form field 'text' or upload a file."}), 400

    try:
        result = understand_text(text, **options)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(result.to_dict()), 200
