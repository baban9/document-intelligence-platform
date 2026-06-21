"""Lightweight OIDC and session auth routes."""

from __future__ import annotations

import secrets

from flask import Blueprint, g, jsonify, redirect, request

from docintel.auth.api_keys import auth_required
from docintel.auth.context import get_auth_context
from docintel.auth.limiter import limiter
from docintel.auth.oidc import validate_oidc_token
from docintel.auth.oidc_config import load_oidc_config
from docintel.auth.oidc_flow import build_authorize_url, exchange_authorization_code

auth_bp = Blueprint("auth", __name__, url_prefix="/v1/auth")


@auth_bp.get("/config")
@limiter.limit("120 per hour")
def auth_config():
    """Public auth settings for the web UI."""
    oidc = load_oidc_config()
    return jsonify(
        {
            "status": "ok",
            "auth_required": auth_required(),
            "oidc_enabled": oidc is not None,
            "oidc_client_id": oidc.client_id if oidc else "",
            "oidc_scopes": oidc.scopes if oidc else "",
        }
    ), 200


@auth_bp.get("/me")
@limiter.limit("120 per hour")
def auth_me():
    """Return the current bearer identity when a token is present."""
    context = get_auth_context()
    if context is None:
        if auth_required():
            return jsonify({"error": "Authentication required."}), 401
        return jsonify({"status": "ok", "authenticated": False}), 200

    payload = {
        "status": "ok",
        "authenticated": True,
        "method": context.method,
        "subject": context.subject,
    }
    if context.email:
        payload["email"] = context.email
    return jsonify(payload), 200


@auth_bp.get("/oidc/login")
@limiter.limit("60 per hour")
def oidc_login():
    """Redirect the browser to the OIDC provider login page."""
    config = load_oidc_config()
    if config is None:
        return jsonify({"error": "OIDC is not configured on this server."}), 503

    redirect_uri = request.args.get("redirect_uri", "").strip()
    if not redirect_uri:
        return jsonify({"error": "Query parameter 'redirect_uri' is required."}), 400

    state = request.args.get("state", "").strip() or secrets.token_urlsafe(16)
    try:
        authorize_url = build_authorize_url(config, redirect_uri=redirect_uri, state=state)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502

    return redirect(authorize_url)


@auth_bp.post("/oidc/token")
@limiter.limit("30 per hour")
def oidc_token_exchange():
    """Exchange an authorization code for tokens (BFF; keeps client secret server-side)."""
    config = load_oidc_config()
    if config is None:
        return jsonify({"error": "OIDC is not configured on this server."}), 503

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be JSON."}), 400

    code = str(payload.get("code", "")).strip()
    redirect_uri = str(payload.get("redirect_uri", "")).strip()
    if not code or not redirect_uri:
        return jsonify({"error": "Fields 'code' and 'redirect_uri' are required."}), 400

    try:
        token_payload = exchange_authorization_code(
            config,
            code=code,
            redirect_uri=redirect_uri,
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502

    access_token = str(token_payload.get("access_token", "")).strip()
    if not access_token:
        return jsonify({"error": "OIDC provider did not return an access_token."}), 502

    context = validate_oidc_token(access_token)
    if context is None:
        return jsonify({"error": "OIDC access token failed validation."}), 401

    g.auth_context = context
    response_payload = {
        "status": "ok",
        "access_token": access_token,
        "token_type": str(token_payload.get("token_type", "Bearer")),
        "expires_in": token_payload.get("expires_in"),
        "subject": context.subject,
    }
    if context.email:
        response_payload["email"] = context.email
    return jsonify(response_payload), 200
