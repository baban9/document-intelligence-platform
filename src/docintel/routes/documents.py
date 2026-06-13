"""Document intelligence routes (classification and comparison)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from docintel.auth.limiter import limiter
from docintel.capabilities.understanding.classify import classify_text
from docintel.capabilities.understanding.compare import compare_texts

documents_bp = Blueprint("documents", __name__, url_prefix="/v1/documents")


@documents_bp.post("/classify")
@limiter.limit("120 per hour")
def classify_document():
    """Classify free text into enterprise function categories."""
    payload = request.get_json(silent=True) or {}
    text = payload.get("text", "")
    if not isinstance(text, str):
        return jsonify({"error": "Field 'text' must be a string."}), 400

    try:
        result = classify_text(text)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"status": "ok", **result.to_dict()})
