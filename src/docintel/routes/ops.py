"""Operations endpoints (metrics)."""

from flask import Blueprint, jsonify, request, Response

from docintel import __version__
from docintel.ops.metrics import metrics_store
from docintel.ops.prometheus import prometheus_enabled, render_prometheus

ops_bp = Blueprint("ops", __name__)


@ops_bp.get("/metrics")
def metrics():
    """Return JSON metrics or Prometheus text when format=prometheus."""
    if prometheus_enabled() and request.args.get("format") == "prometheus":
        return Response(render_prometheus(), mimetype="text/plain; version=0.0.4; charset=utf-8")

    payload = metrics_store.snapshot()
    from docintel.jobs.queue import queue_depth

    depth = queue_depth()
    if depth is not None:
        payload["rq_queue_depth"] = depth

    return jsonify(
        {
            "status": "ok",
            "service": "document-intelligence-platform",
            "version": __version__,
            **payload,
        }
    )
