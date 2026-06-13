"""Webhook delivery when async jobs finish."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from typing import Any

logger = logging.getLogger("docintel.webhooks")

SIGNATURE_HEADER = "X-Docintel-Signature"
TIMESTAMP_HEADER = "X-Docintel-Timestamp"


def webhook_secret() -> str:
    return os.getenv("DOCINTEL_WEBHOOK_SECRET", "").strip()


def sign_webhook_payload(body_bytes: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def deliver_job_webhook(callback_url: str, payload: dict[str, Any]) -> bool:
    """POST job result to the caller webhook URL. Returns True on HTTP 2xx."""
    if not callback_url or not callback_url.strip():
        return False

    try:
        import requests
    except ImportError:
        logger.warning("requests not installed; webhook not delivered")
        return False

    body_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    headers: dict[str, str] = {"Content-Type": "application/json"}
    secret = webhook_secret()
    if secret:
        headers[SIGNATURE_HEADER] = sign_webhook_payload(body_bytes, secret)

    try:
        response = requests.post(
            callback_url.strip(),
            data=body_bytes,
            headers=headers,
            timeout=30,
        )
        if response.ok:
            return True
        logger.warning(
            "webhook delivery failed",
            extra={"status_code": response.status_code, "callback_url": callback_url},
        )
    except Exception as exc:
        logger.warning("webhook delivery error: %s", exc)
    return False
