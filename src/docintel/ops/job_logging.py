"""Structured logs for background job lifecycle and processing progress."""

from __future__ import annotations

import logging
import time
from typing import Any

from docintel.jobs.models import JobRecord, JobStatus

logger = logging.getLogger("docintel.job")

_JOB_STARTED_AT: dict[str, float] = {}

_STRUCTURED_JOB_FIELDS = (
    "event",
    "job_id",
    "job_type",
    "job_status",
    "progress",
    "progress_message",
    "pages_done",
    "pages_total",
    "duration_ms",
    "document_filename",
    "finding_count",
    "classification",
    "error",
)


def job_log_extra(**fields: Any) -> dict[str, Any]:
    """Build logging ``extra`` with only supported structured keys."""
    payload: dict[str, Any] = {}
    for key, value in fields.items():
        if key in _STRUCTURED_JOB_FIELDS and value is not None:
            payload[key] = value
    return payload


def log_job_event(message: str, **fields: Any) -> None:
    logger.info(message, extra=job_log_extra(event=message, **fields))


def _mark_job_running(job_id: str) -> None:
    _JOB_STARTED_AT[job_id] = time.perf_counter()


def _pop_job_duration_ms(job_id: str) -> float | None:
    started = _JOB_STARTED_AT.pop(job_id, None)
    if started is None:
        return None
    return round((time.perf_counter() - started) * 1000, 2)


def _result_summary(result: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    summary: dict[str, Any] = {}
    filename = result.get("filename")
    if isinstance(filename, str) and filename.strip():
        summary["document_filename"] = filename
    classification = result.get("classification")
    if isinstance(classification, dict):
        category = classification.get("category")
        if category is not None:
            summary["classification"] = str(category)
    pii = result.get("pii")
    if isinstance(pii, dict) and pii.get("finding_count") is not None:
        summary["finding_count"] = int(pii["finding_count"])
    return summary


def emit_job_store_log(previous: JobRecord | None, updated: JobRecord, changes: dict[str, Any]) -> None:
    """Emit JSON logs when job metadata changes in Redis."""
    base = {
        "job_id": updated.job_id,
        "job_type": updated.job_type.value,
        "job_status": updated.status.value,
        "progress": updated.progress,
        "progress_message": updated.progress_message,
        "pages_done": updated.pages_done,
        "pages_total": updated.pages_total,
    }

    if previous is None:
        log_job_event("job queued", **base)
        return

    if previous.status != updated.status:
        fields = dict(base)
        if updated.status == JobStatus.RUNNING:
            _mark_job_running(updated.job_id)
            log_job_event("job running", **fields)
            return

        duration_ms = _pop_job_duration_ms(updated.job_id)
        if duration_ms is not None:
            fields["duration_ms"] = duration_ms

        if updated.status == JobStatus.COMPLETED:
            fields.update(_result_summary(updated.result))
            log_job_event("job completed", **fields)
            return

        if updated.status == JobStatus.FAILED:
            if updated.error:
                fields["error"] = str(updated.error)
            log_job_event("job failed", **fields)
            return

        log_job_event(f"job {updated.status.value}", **fields)
        return

    if updated.status != JobStatus.RUNNING:
        return

    pages_changed = (
        changes.get("pages_done") is not None and updated.pages_done != previous.pages_done
    )
    if pages_changed and updated.pages_total > 0:
        log_job_event("job page progress", **base)
        return

    message_changed = (
        changes.get("progress_message") is not None
        and updated.progress_message != previous.progress_message
    )
    if message_changed:
        log_job_event("job progress", **base)


def reset_job_logging_state_for_tests() -> None:
    _JOB_STARTED_AT.clear()
