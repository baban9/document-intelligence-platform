"""Document intelligence routes (classification and comparison)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from flask import Blueprint, jsonify, request

from docintel.auth.limiter import limiter
from docintel.capabilities.extraction.formats import (
    extract_document_text,
    list_supported_types,
)
from docintel.capabilities.understanding.classify import classify_text
from docintel.capabilities.understanding.compare import compare_texts
from docintel.services.pdf import entities_for_vertical
from docintel.services.pdf.pii import detect_pii_in_text
from docintel.services.summary import summarize_text
from docintel.services.summary.textrank import DEFAULT_SENTENCE_COUNT, MAX_SENTENCE_COUNT
from docintel.routes.document_upload import read_upload, save_upload

documents_bp = Blueprint("documents", __name__, url_prefix="/v1/documents")


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


@documents_bp.get("/types")
@limiter.limit("120 per hour")
def supported_document_types():
    """List supported MIME types, extensions, and capabilities."""
    return jsonify({"status": "ok", "types": list_supported_types()})


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


@documents_bp.post("/classify")
@limiter.limit("120 per hour")
def classify_document():
    """Classify text or an uploaded document into enterprise function categories."""
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
