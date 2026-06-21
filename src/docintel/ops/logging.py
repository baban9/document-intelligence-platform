"""Structured JSON logging for the API."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from docintel.ops.secrets import redact_text


class SecretRedactionFilter(logging.Filter):
    """Strip API keys and tokens from log messages and exception text."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg)
        if record.args:
            record.args = tuple(
                redact_text(arg) if isinstance(arg, str) else arg for arg in record.args
            )
        return True


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    _STRUCTURED_FIELDS = (
        "method",
        "path",
        "status_code",
        "duration_ms",
        "endpoint",
        "event",
        "job_id",
        "job_type",
        "job_status",
        "progress",
        "progress_message",
        "pages_done",
        "pages_total",
        "document_filename",
        "finding_count",
        "classification",
        "error",
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in self._STRUCTURED_FIELDS:
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = redact_text(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging with JSON output to stdout."""
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level.upper())

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(SecretRedactionFilter())
    root.addHandler(handler)

    logging.getLogger("werkzeug").setLevel(logging.WARNING)
