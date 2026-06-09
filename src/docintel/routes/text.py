"""Text summarization API routes."""

from flask import Blueprint, jsonify, request

from docintel.auth.limiter import limiter
from docintel.services.summary import summarize_text
from docintel.services.summary.textrank import DEFAULT_SENTENCE_COUNT, MAX_SENTENCE_COUNT

text_bp = Blueprint("text", __name__, url_prefix="/v1/text")


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

    try:
        result = summarize_text(text=text, sentence_count=sentences)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"status": "ok", **result.to_dict()}), 200
