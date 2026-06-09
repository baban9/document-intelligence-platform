"""Async job status API."""

from __future__ import annotations

from flask import Blueprint, jsonify

from docintel.jobs.store import get_job

jobs_bp = Blueprint("jobs", __name__, url_prefix="/v1/jobs")


@jobs_bp.get("/<job_id>")
def job_status(job_id: str):
    """Poll async job status and download URL when complete."""
    record = get_job(job_id)
    if record is None:
        return jsonify({"error": f"Job not found: {job_id}"}), 404

    payload = {
        "status": "ok",
        **record.to_dict(),
        "poll_url": f"/v1/jobs/{job_id}",
    }
    return jsonify(payload), 200
