"""Redis-backed job metadata store."""

from __future__ import annotations

import json
import os
from functools import lru_cache

from docintel.jobs.models import JobRecord

JOB_KEY_PREFIX = "docintel:job:"
DEFAULT_JOB_TTL_SECONDS = 60 * 60 * 24 * 7


def job_ttl_seconds() -> int:
    raw = os.getenv("DOCINTEL_JOB_TTL_SECONDS", str(DEFAULT_JOB_TTL_SECONDS)).strip()
    try:
        ttl = int(raw)
    except ValueError:
        return DEFAULT_JOB_TTL_SECONDS
    return max(ttl, 60)


def redis_url() -> str:
    return os.getenv("DOCINTEL_REDIS_URL", "redis://localhost:6379/0").strip()


def jobs_enabled() -> bool:
    return os.getenv("DOCINTEL_JOBS_ENABLED", "true").lower() == "true"


@lru_cache(maxsize=1)
def _redis_client():
    import redis

    return redis.Redis.from_url(redis_url(), decode_responses=True)


def reset_redis_client_cache() -> None:
    """Clear cached Redis client (used in tests)."""
    if hasattr(_redis_client, "cache_clear"):
        _redis_client.cache_clear()


def _job_key(job_id: str) -> str:
    return f"{JOB_KEY_PREFIX}{job_id}"


def save_job(record: JobRecord, ttl_seconds: int | None = None) -> None:
    client = _redis_client()
    resolved_ttl = ttl_seconds if ttl_seconds is not None else job_ttl_seconds()
    client.set(_job_key(record.job_id), json.dumps(record.to_dict()), ex=resolved_ttl)


def get_job(job_id: str) -> JobRecord | None:
    client = _redis_client()
    raw = client.get(_job_key(job_id))
    if not raw:
        return None
    return JobRecord.from_dict(json.loads(raw))


def update_job(job_id: str, **changes) -> JobRecord:
    from docintel.jobs.models import JobStatus

    record = get_job(job_id)
    if record is None:
        raise KeyError(f"Job not found: {job_id}")

    status_value = changes.get("job_status", record.status.value)
    updated = JobRecord(
        job_id=record.job_id,
        job_type=record.job_type,
        status=JobStatus(status_value),
        progress=int(changes.get("progress", record.progress)),
        progress_message=str(changes.get("progress_message", record.progress_message)),
        pages_done=int(changes.get("pages_done", record.pages_done)),
        pages_total=int(changes.get("pages_total", record.pages_total)),
        callback_url=changes.get("callback_url", record.callback_url),
        download_url=changes.get("download_url", record.download_url),
        error=changes.get("error", record.error),
        result=changes.get("result", record.result),
    )
    save_job(updated)
    return updated


def ping_redis() -> bool:
    try:
        return bool(_redis_client().ping())
    except Exception:
        return False
