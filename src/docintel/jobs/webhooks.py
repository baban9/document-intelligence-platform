"""Webhook delivery when async jobs finish."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("docintel.webhooks")


def deliver_job_webhook(callback_url: str, payload: dict[str, Any]) -> bool:
    """POST job result to the caller webhook URL. Returns True on HTTP 2xx."""
    if not callback_url or not callback_url.strip():
        return False

    try:
        import requests
    except ImportError:
        logger.warning("requests not installed; webhook not delivered")
        return False

    try:
        response = requests.post(callback_url.strip(), json=payload, timeout=30)
        if response.ok:
            return True
        logger.warning(
            "webhook delivery failed",
            extra={"status_code": response.status_code, "callback_url": callback_url},
        )
    except Exception as exc:
        logger.warning("webhook delivery error: %s", exc)
    return False
