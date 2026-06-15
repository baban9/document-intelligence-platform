"""Batch async job submission."""

from __future__ import annotations

import uuid

from flask import Blueprint, jsonify, request

from docintel.auth.limiter import limiter
from docintel.capabilities.pipeline import ProcessOptions
from docintel.jobs.helpers import enqueue_async_response
from docintel.jobs.models import JobRecord, JobStatus, JobType
from docintel.jobs.store import save_job

batch_bp = Blueprint("batch", __name__, url_prefix="/v1/batch")

MAX_BATCH_ITEMS = 50
SUPPORTED_OPERATIONS = {"summarize", "classify", "detect_pii", "process"}


def _process_options_from_item(item: dict) -> ProcessOptions:
    entities_raw = item.get("entities")
    entities = None
    if isinstance(entities_raw, str) and entities_raw.strip():
        entities = [part.strip() for part in entities_raw.split(",") if part.strip()]
    elif isinstance(entities_raw, list):
        entities = [str(part).strip() for part in entities_raw if str(part).strip()]

    vertical = str(item.get("vertical", "")).strip()
    if vertical:
        from docintel.services.pdf import entities_for_vertical

        entities = list(entities_for_vertical(vertical))

    return ProcessOptions(
        sentences=int(item.get("sentences", 3)),
        include_summarize=bool(item.get("include_summarize", True)),
        include_pii=bool(item.get("include_pii", True)),
        include_text=bool(item.get("include_text", False)),
        entities=entities,
        min_score=float(item.get("min_score", 0.35)),
    )


def _enqueue_batch_item(
    *,
    operation: str,
    item: dict,
    callback_url: str | None,
) -> tuple[dict | None, tuple | None]:
    from docintel.jobs.queue import (
        enqueue_classify_job,
        enqueue_detect_pii_text_job,
        enqueue_document_process_text_job,
        enqueue_summarize_job,
    )

    job_id = uuid.uuid4().hex[:12]
    text = str(item.get("text", ""))

    if operation == "summarize":
        job_type = JobType.TEXT_SUMMARIZE
        enqueue_kwargs = {"text": text, "sentences": int(item.get("sentences", 3))}
        enqueue_fn = enqueue_summarize_job
    elif operation == "classify":
        job_type = JobType.TEXT_CLASSIFY
        enqueue_kwargs = {"text": text}
        enqueue_fn = enqueue_classify_job
    elif operation == "detect_pii":
        job_type = JobType.TEXT_DETECT_PII
        options = _process_options_from_item(item)
        enqueue_kwargs = {
            "text": text,
            "entities": options.entities,
            "min_score": options.min_score,
        }
        enqueue_fn = enqueue_detect_pii_text_job
    elif operation == "process":
        job_type = JobType.DOCUMENT_PROCESS
        options = _process_options_from_item(item)
        enqueue_kwargs = {"text": text, "options": options.to_dict()}
        enqueue_fn = enqueue_document_process_text_job
    else:
        return None, None

    accepted, status_code = enqueue_async_response(
        job_id=job_id,
        job_type=job_type,
        callback_url=callback_url,
    )
    if status_code != 202:
        return None, accepted

    enqueue_fn(job_id=job_id, **enqueue_kwargs)
    accepted_payload = accepted.get_json()
    return {
        "operation": operation,
        "job_id": job_id,
        "poll_url": accepted_payload.get("poll_url"),
    }, None


@batch_bp.post("")
@limiter.limit("20 per hour")
def create_batch():
    """Queue multiple text document jobs in one request."""
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

        if not str(item.get("text", "")).strip():
            return jsonify({"error": f"Item {index} requires non-empty field 'text'."}), 400

        queued, error_response = _enqueue_batch_item(
            operation=operation,
            item=item,
            callback_url=callback_url,
        )
        if error_response is not None:
            return error_response

        queued_items.append({"index": index, **queued})

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
