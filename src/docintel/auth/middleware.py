"""Authentication middleware for protected API routes."""

from __future__ import annotations

from flask import Flask, g, jsonify, request

from docintel.auth.api_keys import auth_required, extract_bearer_token, validate_credentials

PUBLIC_PREFIXES = (
    "/health",
    "/docs",
    "/openapi.json",
    "/metrics",
    "/v1/auth/config",
    "/v1/auth/me",
    "/v1/auth/login",
    "/v1/auth/users/onboard",
    "/v1/auth/oidc/login",
    "/v1/auth/oidc/token",
)


def register_auth(app: Flask) -> None:
    @app.before_request
    def _attach_optional_auth():
        """Parse Bearer tokens when present so /v1/auth/me and settings can identify users."""
        if getattr(g, "auth_context", None) is not None:
            return None

        token = extract_bearer_token()
        if not token:
            return None

        context = validate_credentials(token)
        if context is not None:
            g.auth_context = context
        return None

    @app.before_request
    def _enforce_api_auth():
        if not auth_required():
            return None

        path = request.path or ""
        if any(path == prefix or path.startswith(prefix + "/") for prefix in PUBLIC_PREFIXES):
            return None

        if not path.startswith("/v1/"):
            return None

        token = extract_bearer_token()
        if not token:
            return jsonify({"error": "Missing Authorization: Bearer <token> header."}), 401

        context = validate_credentials(token)
        if context is None:
            return jsonify({"error": "Invalid API credentials."}), 401

        g.auth_context = context
        return None
