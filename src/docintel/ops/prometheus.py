"""Prometheus metrics export."""

from __future__ import annotations

import os

_PROMETHEUS = None


def _metrics():
    global _PROMETHEUS
    if _PROMETHEUS is None:
        from prometheus_client import Counter, Gauge, Histogram

        _PROMETHEUS = {
            "requests": Counter(
                "docintel_http_requests_total",
                "Total HTTP requests",
                ["endpoint", "status"],
            ),
            "latency": Histogram(
                "docintel_http_request_duration_seconds",
                "HTTP request latency in seconds",
                ["endpoint"],
                buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
            ),
            "queue_depth": Gauge(
                "docintel_rq_queue_depth",
                "RQ jobs waiting in queue",
            ),
        }
    return _PROMETHEUS


def prometheus_enabled() -> bool:
    return os.getenv("DOCINTEL_PROMETHEUS_ENABLED", "true").lower() == "true"


def record_prometheus(endpoint: str, status_code: int, duration_seconds: float) -> None:
    if not prometheus_enabled():
        return
    metrics = _metrics()
    key = endpoint or "unknown"
    metrics["requests"].labels(endpoint=key, status=str(status_code)).inc()
    metrics["latency"].labels(endpoint=key).observe(duration_seconds)


def refresh_queue_depth() -> None:
    if not prometheus_enabled():
        return
    from docintel.jobs.queue import queue_depth

    depth = queue_depth()
    if depth is not None:
        _metrics()["queue_depth"].set(depth)


def render_prometheus() -> bytes:
    from prometheus_client import generate_latest

    refresh_queue_depth()
    return generate_latest()
