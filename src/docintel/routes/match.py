"""Resume matching API routes."""

from flask import Blueprint, jsonify, request

from docintel.services.matching import match_resume_to_job

match_bp = Blueprint("match", __name__, url_prefix="/v1/match")


@match_bp.post("/resume")
def match_resume():
    """Score how well a resume matches a job description."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be JSON."}), 400

    resume = payload.get("resume", "")
    job_description = payload.get("job_description", "")
    top_keywords = payload.get("top_keywords", 25)

    if not isinstance(resume, str) or not isinstance(job_description, str):
        return jsonify({"error": "Fields 'resume' and 'job_description' must be strings."}), 400

    try:
        top_keywords = int(top_keywords)
    except (TypeError, ValueError):
        return jsonify({"error": "Field 'top_keywords' must be an integer."}), 400

    if top_keywords < 1 or top_keywords > 100:
        return jsonify({"error": "Field 'top_keywords' must be between 1 and 100."}), 400

    try:
        result = match_resume_to_job(
            resume=resume,
            job_description=job_description,
            top_keywords=top_keywords,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"status": "ok", **result.to_dict()}), 200
