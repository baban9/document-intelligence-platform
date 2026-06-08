"""Operations endpoints (metrics)."""

from flask import Blueprint, jsonify

from docintel import __version__
from docintel.ops.metrics import metrics_store

ops_bp = Blueprint("ops", __name__)


@ops_bp.get("/metrics")
def metrics():
  """Return in-process request counters and latency aggregates."""
  payload = metrics_store.snapshot()
  return jsonify(
    {
      "status": "ok",
      "service": "document-intelligence-platform",
      "version": __version__,
      **payload,
    }
  )
