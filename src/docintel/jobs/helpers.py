"""Shared helpers for async job enqueue from HTTP routes."""

from __future__ import annotations

from flask import jsonify

from docintel.jobs.models import JobType
from docintel.jobs.store import jobs_enabled, ping_redis
from docintel.jobs.tasks import create_queued_job
from docintel.tenants.context import current_tenant_slug


def enqueue_async_response(
    *,
    job_id: str,
    job_type: JobType,
    callback_url: str | None,
    tenant_slug: str | None = None,
):
    """Validate Redis and return a standard 202 async job payload."""
    if not jobs_enabled():
        return jsonify({"error": "Async jobs are disabled on this server."}), 503
    if not ping_redis():
        return jsonify(
            {
                "error": "Redis is not reachable. Start Redis or set DOCINTEL_REDIS_URL.",
                "hint": "Use async=false for synchronous processing without a queue.",
            }
        ), 503

    create_queued_job(
        job_id,
        job_type=job_type,
        callback_url=callback_url,
        tenant_slug=tenant_slug or current_tenant_slug(),
    )
    payload = {
        "status": "ok",
        "job_id": job_id,
        "job_type": job_type.value,
        "job_status": "queued",
        "poll_url": f"/v1/jobs/{job_id}",
        "message": "Job queued. Poll poll_url until job_status is completed.",
    }
    return jsonify(payload), 202
