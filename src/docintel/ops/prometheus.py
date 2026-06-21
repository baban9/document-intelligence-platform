"""Prometheus metrics export."""

from __future__ import annotations

import os
import threading
import time
from typing import Any

_JOB_STARTS: dict[str, tuple[float, str]] = {}
_LOCK = threading.Lock()
_PROMETHEUS: dict[str, Any] | None = None


def _metrics() -> dict[str, Any]:
    global _PROMETHEUS
    if _PROMETHEUS is None:
        from prometheus_client import Counter, Gauge, Histogram, Info

        _PROMETHEUS = {
            "requests": Counter(
                "docintel_http_requests_total",
                "Total HTTP requests",
                ["endpoint", "status"],
            ),
            "errors": Counter(
                "docintel_http_errors_total",
                "HTTP requests that returned 4xx or 5xx",
                ["endpoint", "status"],
            ),
            "latency": Histogram(
                "docintel_http_request_duration_seconds",
                "HTTP request latency in seconds",
                ["endpoint"],
                buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
            ),
            "in_flight": Gauge(
                "docintel_http_requests_in_flight",
                "HTTP requests currently being processed",
                ["endpoint"],
            ),
            "queue_depth": Gauge(
                "docintel_rq_queue_depth",
                "RQ jobs waiting in queue",
            ),
            "jobs_queued": Counter(
                "docintel_jobs_queued_total",
                "Background jobs queued",
                ["job_type"],
            ),
            "jobs_finished": Counter(
                "docintel_jobs_finished_total",
                "Background jobs completed or failed",
                ["job_type", "status"],
            ),
            "jobs_running": Gauge(
                "docintel_jobs_running",
                "Background jobs currently running",
                ["job_type"],
            ),
            "job_duration": Histogram(
                "docintel_job_duration_seconds",
                "Background job wall time in seconds",
                ["job_type", "status"],
                buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1800.0),
            ),
            "redis_up": Gauge(
                "docintel_redis_up",
                "Whether Redis is reachable (1 = up, 0 = down)",
            ),
            "build_info": Info(
                "docintel_build",
                "Document intelligence platform build metadata",
            ),
        }
        from docintel import __version__

        _PROMETHEUS["build_info"].info(
            {
                "version": __version__,
                "service": "document-intelligence-platform",
            }
        )
    return _PROMETHEUS


def prometheus_enabled() -> bool:
    return os.getenv("DOCINTEL_PROMETHEUS_ENABLED", "true").lower() == "true"


def record_prometheus(endpoint: str, status_code: int, duration_seconds: float) -> None:
    if not prometheus_enabled():
        return
    metrics = _metrics()
    key = endpoint or "unknown"
    status = str(status_code)
    metrics["requests"].labels(endpoint=key, status=status).inc()
    metrics["latency"].labels(endpoint=key).observe(duration_seconds)
    if status_code >= 400:
        metrics["errors"].labels(endpoint=key, status=status).inc()


def record_http_in_flight(endpoint: str, delta: int) -> None:
    if not prometheus_enabled():
        return
    key = endpoint or "unknown"
    if delta > 0:
        _metrics()["in_flight"].labels(endpoint=key).inc(delta)
    else:
        _metrics()["in_flight"].labels(endpoint=key).dec(abs(delta))


def record_job_queued(job_type: str) -> None:
    if not prometheus_enabled():
        return
    _metrics()["jobs_queued"].labels(job_type=job_type or "unknown").inc()


def record_job_status_change(
    job_id: str,
    job_type: str,
    old_status: str,
    new_status: str,
) -> None:
    """Track job lifecycle transitions for queue, running, and duration metrics."""
    if not prometheus_enabled() or old_status == new_status:
        return

    key = job_type or "unknown"
    metrics = _metrics()
    old = old_status.strip().lower()
    new = new_status.strip().lower()

    if new == "running" and old in {"queued", ""}:
        with _LOCK:
            _JOB_STARTS[job_id] = (time.monotonic(), key)
        metrics["jobs_running"].labels(job_type=key).inc()

    if new in {"completed", "failed"} and old == "running":
        metrics["jobs_running"].labels(job_type=key).dec()
        metrics["jobs_finished"].labels(job_type=key, status=new).inc()
        with _LOCK:
            started = _JOB_STARTS.pop(job_id, None)
        if started is not None:
            duration = max(time.monotonic() - started[0], 0.0)
            metrics["job_duration"].labels(job_type=key, status=new).observe(duration)


def refresh_queue_depth() -> None:
    if not prometheus_enabled():
        return
    from docintel.jobs.queue import queue_depth

    depth = queue_depth()
    if depth is not None:
        _metrics()["queue_depth"].set(depth)


def refresh_redis_up() -> None:
    if not prometheus_enabled():
        return
    from docintel.jobs.store import ping_redis

    _metrics()["redis_up"].set(1 if ping_redis() else 0)


def render_prometheus() -> bytes:
    from prometheus_client import generate_latest

    refresh_queue_depth()
    refresh_redis_up()
    return generate_latest()


def reset_prometheus_state_for_tests() -> None:
    """Clear in-memory job timing state and unregister metrics between tests."""
    global _PROMETHEUS
    with _LOCK:
        _JOB_STARTS.clear()
    if _PROMETHEUS is not None:
        from prometheus_client import REGISTRY

        for metric in _PROMETHEUS.values():
            try:
                REGISTRY.unregister(metric)
            except KeyError:
                pass
    _PROMETHEUS = None
