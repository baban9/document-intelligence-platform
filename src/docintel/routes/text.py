"""Text summarization API routes."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from docintel.auth.limiter import limiter
from docintel.routes.async_enqueue import enqueue_background_job
from docintel.routes.document_upload import parse_async_flag
from docintel.services.summary import summarize_text
from docintel.services.summary.textrank import DEFAULT_SENTENCE_COUNT, MAX_SENTENCE_COUNT

text_bp = Blueprint("text", __name__, url_prefix="/v1/text")


def _callback_url(payload: dict) -> str | None:
    raw = payload.get("callback_url", "")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


@text_bp.post("/summarize")
@limiter.limit("100 per hour")
def summarize():
    """Extractively summarize plain text using TextRank sentence ranking."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be JSON."}), 400

    text = payload.get("text", "")
    sentences = payload.get("sentences", DEFAULT_SENTENCE_COUNT)

    if not isinstance(text, str):
        return jsonify({"error": "Field 'text' must be a string."}), 400

    try:
        sentences = int(sentences)
    except (TypeError, ValueError):
        return jsonify({"error": "Field 'sentences' must be an integer."}), 400

    if sentences < 1 or sentences > MAX_SENTENCE_COUNT:
        return jsonify(
            {"error": f"Field 'sentences' must be between 1 and {MAX_SENTENCE_COUNT}."}
        ), 400

    if parse_async_flag():
        from docintel.jobs.models import JobType
        from docintel.jobs.queue import enqueue_summarize_job

        return enqueue_background_job(
            job_type=JobType.TEXT_SUMMARIZE,
            callback_url=_callback_url(payload),
            enqueue_fn=enqueue_summarize_job,
            text=text,
            sentences=sentences,
        )

    try:
        result = summarize_text(text=text, sentence_count=sentences)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"status": "ok", **result.to_dict()}), 200
