"""Request-scoped authentication helpers."""

from __future__ import annotations

from flask import g

from docintel.auth.api_keys import AuthContext


def get_auth_context() -> AuthContext | None:
    return getattr(g, "auth_context", None)
