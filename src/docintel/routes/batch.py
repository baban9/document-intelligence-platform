"""Batch async job submission."""

from __future__ import annotations

import uuid

from flask import Blueprint, jsonify, request

from docintel.auth.limiter import limiter
from docintel.jobs.helpers import enqueue_async_response
from docintel.jobs.models import JobRecord, JobStatus, JobType
from docintel.jobs.store import save_job

batch_bp = Blueprint("batch", __name__, url_prefix="/v1/batch")

MAX_BATCH_ITEMS = 50
SUPPORTED_OPERATIONS = {"match_resume", "summarize"}


@batch_bp.post("")
@limiter.limit("20 per hour")
def create_batch():
    """Queue multiple text jobs in one request."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be JSON."}), 400

    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return jsonify({"error": "Field 'items' must be a non-empty list."}), 400
    if len(items) > MAX_BATCH_ITEMS:
        return jsonify({"error": f"Batch limit is {MAX_BATCH_ITEMS} items."}), 400

    callback_url = str(payload.get("callback_url", "") or "").strip() or None
    batch_id = uuid.uuid4().hex[:12]
    queued_items: list[dict] = []

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            return jsonify({"error": f"Item {index} must be an object."}), 400

        operation = str(item.get("operation", "")).strip()
        if operation not in SUPPORTED_OPERATIONS:
            return jsonify(
                {
                    "error": (
                        f"Unsupported operation '{operation}'. "
                        f"Supported: {', '.join(sorted(SUPPORTED_OPERATIONS))}"
                    )
                }
            ), 400

        job_id = uuid.uuid4().hex[:12]
        if operation == "match_resume":
            resume = item.get("resume", "")
            job_description = item.get("job_description", "")
            top_keywords = int(item.get("top_keywords", 25))
            job_type = JobType.MATCH_RESUME
            enqueue_kwargs = {
                "resume": resume,
                "job_description": job_description,
                "top_keywords": top_keywords,
            }
        else:
            text = item.get("text", "")
            sentences = int(item.get("sentences", 3))
            job_type = JobType.TEXT_SUMMARIZE
            enqueue_kwargs = {"text": text, "sentences": sentences}

        accepted, status_code = enqueue_async_response(
            job_id=job_id,
            job_type=job_type,
            callback_url=callback_url,
        )
        if status_code != 202:
            return accepted, status_code

        if operation == "match_resume":
            from docintel.jobs.queue import enqueue_match_job

            enqueue_match_job(job_id=job_id, **enqueue_kwargs)
        else:
            from docintel.jobs.queue import enqueue_summarize_job

            enqueue_summarize_job(job_id=job_id, **enqueue_kwargs)

        accepted_payload = accepted.get_json()
        queued_items.append(
            {
                "index": index,
                "operation": operation,
                "job_id": job_id,
                "poll_url": accepted_payload.get("poll_url"),
            }
        )

    save_job(
        JobRecord(
            job_id=batch_id,
            job_type=JobType.BATCH,
            status=JobStatus.QUEUED,
            progress=0,
            progress_message="Batch queued",
            callback_url=callback_url,
            result={"items": queued_items},
        )
    )

    return jsonify(
        {
            "status": "ok",
            "batch_id": batch_id,
            "poll_url": f"/v1/jobs/{batch_id}",
            "items": queued_items,
            "message": "Batch queued. Poll each job_id or the batch record.",
        }
    ), 202
