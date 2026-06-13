"""Resume matching API routes."""

from __future__ import annotations

import uuid

from flask import Blueprint, jsonify, request

from docintel.auth.limiter import limiter
from docintel.services.matching import match_resume_to_job

match_bp = Blueprint("match", __name__, url_prefix="/v1/match")


def _parse_async_flag() -> bool:
    raw = request.args.get("async", "false")
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        if "async" in payload:
            raw = payload.get("async", raw)
    return str(raw).lower() == "true"


@match_bp.post("/resume")
@limiter.limit("100 per hour")
def match_resume():
    """Score how well a resume matches a job description."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be JSON."}), 400

    resume = payload.get("resume", "")
    job_description = payload.get("job_description", "")
    top_keywords = payload.get("top_keywords", 25)
    callback_url = str(payload.get("callback_url", "") or "").strip() or None
    run_async = _parse_async_flag()

    if not isinstance(resume, str) or not isinstance(job_description, str):
        return jsonify({"error": "Fields 'resume' and 'job_description' must be strings."}), 400

    try:
        top_keywords = int(top_keywords)
    except (TypeError, ValueError):
        return jsonify({"error": "Field 'top_keywords' must be an integer."}), 400

    if top_keywords < 1 or top_keywords > 100:
        return jsonify({"error": "Field 'top_keywords' must be between 1 and 100."}), 400

    if run_async:
        return _enqueue_match_job(
            resume=resume,
            job_description=job_description,
            top_keywords=top_keywords,
            callback_url=callback_url,
        )

    try:
        result = match_resume_to_job(
            resume=resume,
            job_description=job_description,
            top_keywords=top_keywords,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"status": "ok", **result.to_dict()}), 200


def _enqueue_match_job(
    *,
    resume: str,
    job_description: str,
    top_keywords: int,
    callback_url: str | None,
):
    from docintel.jobs.helpers import enqueue_async_response
    from docintel.jobs.models import JobType
    from docintel.jobs.queue import enqueue_match_job

    job_id = uuid.uuid4().hex[:12]
    accepted = enqueue_async_response(
        job_id=job_id,
        job_type=JobType.MATCH_RESUME,
        callback_url=callback_url,
    )
    if accepted[1] != 202:
        return accepted

    enqueue_match_job(
        job_id=job_id,
        resume=resume,
        job_description=job_description,
        top_keywords=top_keywords,
    )
    return accepted
