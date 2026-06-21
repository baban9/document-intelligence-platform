"""Lightweight OIDC, local user auth, and session routes."""

from __future__ import annotations

import secrets

from flask import Blueprint, g, jsonify, redirect, request

from docintel.auth.api_keys import auth_required
from docintel.auth.context import get_auth_context
from docintel.auth.limiter import limiter
from docintel.auth.api_keys import AuthContext
from docintel.auth.local_tokens import issue_local_token
from docintel.auth.oidc import validate_oidc_token
from docintel.auth.oidc_config import load_oidc_config
from docintel.auth.oidc_flow import build_authorize_url, exchange_authorization_code
from docintel.db.users import (
    count_users,
    create_user,
    generate_temporary_password,
    get_user_by_email,
    get_user_by_id,
    list_login_events,
    list_users,
    local_auth_enabled,
    record_login_event,
    touch_user_login,
    update_user_password,
    verify_user_password,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/v1/auth")


def _request_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return (request.remote_addr or "")[:64]


def _request_user_agent() -> str:
    return (request.headers.get("User-Agent") or "")[:512]


def _auth_me_payload(context) -> dict:
    payload = {
        "status": "ok",
        "authenticated": True,
        "method": context.method,
        "subject": context.subject,
    }
    if context.email:
        payload["email"] = context.email
    if context.first_name:
        payload["first_name"] = context.first_name
    if context.last_name:
        payload["last_name"] = context.last_name
    if context.method == "local":
        payload["must_change_password"] = context.must_change_password
        payload["is_admin"] = context.is_admin
    return payload


def _can_manage_users() -> tuple[bool, str]:
    if not local_auth_enabled():
        return False, "Local user accounts require PostgreSQL."

    if count_users() == 0:
        return True, ""

    tenant = getattr(g, "tenant", None)
    if tenant is not None and tenant.is_admin:
        return True, ""

    context = get_auth_context()
    if context is not None and context.method == "local" and context.is_admin:
        return True, ""

    return False, "Admin access is required to manage users."


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
            "local_auth_enabled": local_auth_enabled(),
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

    return jsonify(_auth_me_payload(context)), 200


@auth_bp.post("/login")
@limiter.limit("30 per hour")
def local_login():
    """Sign in with email and password."""
    if not local_auth_enabled():
        return jsonify({"error": "Local user login requires PostgreSQL."}), 503

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be JSON."}), 400

    email = str(payload.get("email", "")).strip()
    password = str(payload.get("password", ""))
    if not email or not password:
        return jsonify({"error": "Fields 'email' and 'password' are required."}), 400

    user = verify_user_password(email, password)
    if user is None:
        record_login_event(
            email=email,
            method="local",
            ip_address=_request_ip(),
            user_agent=_request_user_agent(),
            success=False,
            failure_reason="invalid_credentials",
        )
        return jsonify({"error": "Invalid email or password."}), 401

    touch_user_login(user.id)
    record_login_event(
        user_id=user.id,
        email=user.email,
        method="local",
        ip_address=_request_ip(),
        user_agent=_request_user_agent(),
        success=True,
    )

    token = issue_local_token(user)
    g.auth_context = AuthContext(
        method="local",
        subject=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        must_change_password=user.must_change_password,
        is_admin=user.is_admin,
    )
    return jsonify(
        {
            "status": "ok",
            "access_token": token,
            "token_type": "Bearer",
            "must_change_password": user.must_change_password,
            "user": user.to_dict(),
        }
    ), 200


@auth_bp.post("/change-password")
@limiter.limit("20 per hour")
def change_password():
    """Change the password for the signed-in local user."""
    if not local_auth_enabled():
        return jsonify({"error": "Local user login requires PostgreSQL."}), 503

    context = get_auth_context()
    if context is None or context.method != "local":
        return jsonify({"error": "Local user authentication is required."}), 401

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be JSON."}), 400

    current_password = str(payload.get("current_password", ""))
    new_password = str(payload.get("new_password", ""))
    if not current_password or not new_password:
        return jsonify({"error": "Fields 'current_password' and 'new_password' are required."}), 400
    if len(new_password) < 8:
        return jsonify({"error": "New password must be at least 8 characters."}), 400
    if current_password == new_password:
        return jsonify({"error": "New password must differ from the current password."}), 400

    user = verify_user_password(context.email, current_password)
    if user is None or user.id != context.subject:
        return jsonify({"error": "Current password is incorrect."}), 403

    update_user_password(user.id, new_password, clear_must_change=True)
    refreshed = get_user_by_id(user.id)
    if refreshed is None:
        return jsonify({"error": "User account was not found."}), 404

    token = issue_local_token(refreshed)
    return jsonify(
        {
            "status": "ok",
            "access_token": token,
            "token_type": "Bearer",
            "must_change_password": False,
            "user": refreshed.to_dict(),
        }
    ), 200


@auth_bp.post("/users/onboard")
@limiter.limit("30 per hour")
def onboard_user():
    """Create a user with a temporary password (admin or first bootstrap)."""
    allowed, reason = _can_manage_users()
    if not allowed:
        return jsonify({"error": reason}), 403

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be JSON."}), 400

    first_name = str(payload.get("first_name", "")).strip()
    last_name = str(payload.get("last_name", "")).strip()
    email = str(payload.get("email", "")).strip()
    if not first_name or not last_name or not email:
        return jsonify({"error": "Fields 'first_name', 'last_name', and 'email' are required."}), 400

    if get_user_by_email(email) is not None:
        return jsonify({"error": "A user with this email already exists."}), 409

    temporary_password = generate_temporary_password()
    bootstrap = count_users() == 0
    try:
        user = create_user(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=temporary_password,
            must_change_password=True,
            is_admin=bootstrap,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(
        {
            "status": "ok",
            "user": user.to_dict(),
            "temporary_password": temporary_password,
            "message": "Share this temporary password securely. The user must change it on first login.",
        }
    ), 201


@auth_bp.get("/users")
@limiter.limit("60 per hour")
def list_user_accounts():
    """List onboarded users (admin only)."""
    allowed, reason = _can_manage_users()
    if not allowed:
        return jsonify({"error": reason}), 403
    if count_users() == 0:
        return jsonify({"status": "ok", "users": []}), 200

    users = list_users()
    return jsonify({"status": "ok", "users": [user.to_dict() for user in users]}), 200


@auth_bp.get("/login-events")
@limiter.limit("60 per hour")
def login_events():
    """Return recent login activity for the current user or all users (admin)."""
    if not local_auth_enabled():
        return jsonify({"error": "Login activity requires PostgreSQL."}), 503

    context = get_auth_context()
    allowed, reason = _can_manage_users()
    if allowed and context is None:
        events = list_login_events()
    elif allowed and context is not None and context.method == "local" and context.is_admin:
        target_user_id = request.args.get("user_id", "").strip() or None
        events = list_login_events(user_id=target_user_id)
    elif context is not None and context.method == "local":
        events = list_login_events(user_id=context.subject)
    else:
        return jsonify({"error": reason or "Authentication required."}), 403

    return jsonify({"status": "ok", "events": [event.to_dict() for event in events]}), 200


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
    if local_auth_enabled() and context.email:
        record_login_event(
            email=context.email,
            method="oidc",
            ip_address=_request_ip(),
            user_agent=_request_user_agent(),
            success=True,
        )

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
