"""Authentication middleware for protected API routes."""

from __future__ import annotations

from flask import Flask, g, jsonify, request

from docintel.auth.api_keys import auth_required, extract_bearer_token, validate_credentials

PUBLIC_PREFIXES = ("/health", "/docs", "/openapi.json", "/metrics")


def register_auth(app: Flask) -> None:
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
            return jsonify({"error": "Missing Authorization: Bearer <api_key> header."}), 401

        context = validate_credentials(token)
        if context is None:
            return jsonify({"error": "Invalid API credentials."}), 401

        g.auth_context = context
        return None
