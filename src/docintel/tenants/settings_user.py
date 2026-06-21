"""Settings user identity helpers (OIDC subject or browser-scoped fallback)."""

from __future__ import annotations

from flask import request

from docintel.auth.context import get_auth_context

SETTINGS_USER_HEADER = "X-Settings-User-Id"


def settings_user_id_from_request() -> str:
    raw = request.headers.get(SETTINGS_USER_HEADER, "")
    return raw.strip() if isinstance(raw, str) else ""


def resolve_settings_user_id() -> str:
    """Prefer authenticated OIDC/API subject; fall back to browser settings user id."""
    auth = get_auth_context()
    if auth is not None and auth.subject:
        return auth.subject
    return settings_user_id_from_request()
