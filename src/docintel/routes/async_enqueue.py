"""Shared helpers for queueing async document jobs."""

from __future__ import annotations

import uuid

from docintel.jobs.helpers import enqueue_async_response
from docintel.jobs.models import JobType


def enqueue_background_job(
    *,
    job_type: JobType,
    callback_url: str | None,
    enqueue_fn,
    job_id: str | None = None,
    **enqueue_kwargs,
):
    resolved_job_id = job_id or uuid.uuid4().hex[:12]
    accepted = enqueue_async_response(
        job_id=resolved_job_id,
        job_type=job_type,
        callback_url=callback_url,
    )
    if accepted[1] != 202:
        return accepted

    enqueue_fn(job_id=resolved_job_id, **enqueue_kwargs)
    return accepted
