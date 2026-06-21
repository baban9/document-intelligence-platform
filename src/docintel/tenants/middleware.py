"""Tenant isolation middleware."""

from __future__ import annotations

import os

from flask import g, jsonify, request

from docintel.db.connection import database_enabled
from docintel.tenants.context import resolve_tenant_context, set_tenant_context

TENANT_HEADER = "X-Tenant-Slug"
DEFAULT_TENANT_SLUG = "admin"


def multi_tenant_enabled() -> bool:
    if not database_enabled():
        return False
    return os.getenv("DOCINTEL_MULTI_TENANT", "false").lower() == "true"


def register_tenant_middleware(app) -> None:
    @app.before_request
    def _attach_tenant_context():
        if request.path in {"/health", "/metrics"} or request.path.startswith("/docs"):
            return None

        if not multi_tenant_enabled():
            return None

        slug = request.headers.get(TENANT_HEADER, "").strip() or DEFAULT_TENANT_SLUG
        context = resolve_tenant_context(slug)
        if context is None:
            return jsonify({"error": f"Unknown tenant '{slug}'."}), 404

        set_tenant_context(context)
        g.tenant = context
        return None

    @app.teardown_request
    def _clear_tenant_context(_exc):
        set_tenant_context(None)
