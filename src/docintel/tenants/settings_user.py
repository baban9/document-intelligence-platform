"""Settings user identity helpers (browser-scoped owner for API keys)."""

from __future__ import annotations

from flask import request

SETTINGS_USER_HEADER = "X-Settings-User-Id"


def settings_user_id_from_request() -> str:
    raw = request.headers.get(SETTINGS_USER_HEADER, "")
    return raw.strip() if isinstance(raw, str) else ""
