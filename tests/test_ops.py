"""Tests for logging, metrics, and operations endpoints."""

import json
import logging

from docintel.app import create_app
from docintel.ops.logging import JsonFormatter, configure_logging
from docintel.ops.metrics import MetricsStore


def test_metrics_endpoint_tracks_requests():
  app = create_app()
  with app.test_client() as client:
    client.get("/health")
    client.get("/health")
    response = client.get("/metrics")

  payload = response.get_json()
  assert response.status_code == 200
  assert payload["status"] == "ok"
  assert payload["total_requests"] >= 2
  assert "health" in payload["requests_by_endpoint"]
  assert payload["avg_latency_ms"] >= 0


def test_metrics_prometheus_format():
  app = create_app()
  with app.test_client() as client:
    client.get("/health")
    response = client.get("/metrics?format=prometheus")

  assert response.status_code == 200
  assert b"docintel_http_requests_total" in response.data


def test_metrics_store_counts_errors():
  store = MetricsStore()
  store.record("health", 200, 12.5)
  store.record("pdf.annotate", 400, 4.2)

  snapshot = store.snapshot()
  assert snapshot["total_requests"] == 2
  assert snapshot["total_errors"] == 1
  assert snapshot["requests_by_status"]["400"] == 1


def test_json_formatter_outputs_valid_json():
  configure_logging("INFO")
  formatter = JsonFormatter()
  record = logging.LogRecord(
    name="docintel.request",
    level=logging.INFO,
    pathname=__file__,
    lineno=1,
    msg="request completed",
    args=(),
    exc_info=None,
  )
  record.method = "GET"
  record.path = "/health"
  record.status_code = 200
  record.duration_ms = 1.23
  record.endpoint = "health"

  payload = json.loads(formatter.format(record))
  assert payload["message"] == "request completed"
  assert payload["method"] == "GET"
  assert payload["status_code"] == 200
