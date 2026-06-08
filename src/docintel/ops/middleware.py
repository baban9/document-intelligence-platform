"""Request instrumentation hooks."""

from __future__ import annotations

import logging
import time

from flask import Flask, g, request

from docintel.ops.metrics import metrics_store

logger = logging.getLogger("docintel.request")


def register_request_hooks(app: Flask) -> None:
  """Attach timing, logging, and metrics collection to each request."""

  @app.before_request
  def _start_timer() -> None:
    g.request_start = time.perf_counter()

  @app.after_request
  def _record_request(response):
    start = getattr(g, "request_start", None)
    duration_ms = (time.perf_counter() - start) * 1000 if start is not None else 0.0
    endpoint = request.endpoint or request.path

    metrics_store.record(endpoint, response.status_code, duration_ms)

    logger.info(
      "request completed",
      extra={
        "method": request.method,
        "path": request.path,
        "endpoint": endpoint,
        "status_code": response.status_code,
        "duration_ms": round(duration_ms, 2),
      },
    )
    return response
