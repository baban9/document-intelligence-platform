"""Signed JWT tokens for local user sessions."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from docintel.auth.api_keys import AuthContext
from docintel.db.users import UserRecord, get_user_by_id


def _jwt_secret() -> str:
    secret = (
        os.getenv("DOCINTEL_JWT_SECRET", "").strip()
        or os.getenv("DOCINTEL_SETTINGS_ENCRYPTION_KEY", "").strip()
    )
    if not secret:
        raise RuntimeError(
            "Set DOCINTEL_JWT_SECRET or DOCINTEL_SETTINGS_ENCRYPTION_KEY for local user login."
        )
    return secret


def _jwt_module():
    try:
        import jwt
    except ImportError as exc:
        raise RuntimeError(
            "Local user auth requires PyJWT. Run: pip install -e '.[auth]'"
        ) from exc
    return jwt


def local_token_ttl_hours() -> int:
    raw = os.getenv("DOCINTEL_JWT_TTL_HOURS", "24").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 24


def issue_local_token(user: UserRecord) -> str:
    jwt = _jwt_module()
    now = datetime.now(timezone.utc)
    payload = {
        "typ": "local",
        "sub": user.id,
        "email": user.email,
        "given_name": user.first_name,
        "family_name": user.last_name,
        "mcp": user.must_change_password,
        "adm": user.is_admin,
        "iat": now,
        "exp": now + timedelta(hours=local_token_ttl_hours()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm="HS256")


def validate_local_token(token: str) -> AuthContext | None:
    if token.count(".") != 2:
        return None
    jwt = _jwt_module()
    try:
        claims = jwt.decode(
            token,
            _jwt_secret(),
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "typ"]},
        )
    except Exception:
        return None

    if str(claims.get("typ", "")) != "local":
        return None

    user_id = str(claims.get("sub", "")).strip()
    if not user_id:
        return None

    user = get_user_by_id(user_id)
    if user is None or not user.is_active:
        return None

    return AuthContext(
        method="local",
        subject=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        must_change_password=user.must_change_password,
        is_admin=user.is_admin,
    )
