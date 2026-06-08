"""In-process request metrics (per worker in multi-process deployments)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetricsStore:
    """Thread-safe counters for HTTP request observability."""

    total_requests: int = 0
    total_errors: int = 0
    total_latency_ms: float = 0.0
    requests_by_endpoint: dict[str, int] = field(default_factory=dict)
    requests_by_status: dict[str, int] = field(default_factory=dict)
    latency_by_endpoint_ms: dict[str, float] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(self, endpoint: str, status_code: int, duration_ms: float) -> None:
        key = endpoint or "unknown"
        status = str(status_code)
        with self._lock:
            self.total_requests += 1
            if status_code >= 400:
                self.total_errors += 1
            self.total_latency_ms += duration_ms
            self.requests_by_endpoint[key] = self.requests_by_endpoint.get(key, 0) + 1
            self.requests_by_status[status] = self.requests_by_status.get(status, 0) + 1
            self.latency_by_endpoint_ms[key] = (
                self.latency_by_endpoint_ms.get(key, 0.0) + duration_ms
            )

    def snapshot(self) -> dict[str, Any]:
        uptime_seconds = max(time.time() - self.started_at, 0.001)
        with self._lock:
            total = self.total_requests
            avg_latency = self.total_latency_ms / total if total else 0.0
            return {
                "total_requests": total,
                "total_errors": self.total_errors,
                "avg_latency_ms": round(avg_latency, 2),
                "requests_per_second": round(total / uptime_seconds, 4),
                "uptime_seconds": round(uptime_seconds, 2),
                "requests_by_endpoint": dict(self.requests_by_endpoint),
                "requests_by_status": dict(self.requests_by_status),
                "latency_by_endpoint_ms": {
                    key: round(value, 2) for key, value in self.latency_by_endpoint_ms.items()
                },
            }


metrics_store = MetricsStore()
