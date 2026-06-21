"""API key authentication."""

from __future__ import annotations

import os
from dataclasses import dataclass

from docintel.ops.secrets import credential_fingerprint


@dataclass(frozen=True)
class AuthContext:
    method: str
    subject: str
    email: str = ""
    first_name: str = ""
    last_name: str = ""
    must_change_password: bool = False
    is_admin: bool = False


def _configured_keys() -> set[str]:
    raw = os.getenv("DOCINTEL_API_KEYS", "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def auth_required() -> bool:
    if os.getenv("DOCINTEL_AUTH_REQUIRED", "false").lower() == "true":
        return True
    return bool(_configured_keys())


def extract_bearer_token() -> str | None:
    from flask import request

    header = request.headers.get("Authorization", "").strip()
    if not header.lower().startswith("bearer "):
        return None
    token = header[7:].strip()
    return token or None


def validate_api_key(token: str) -> AuthContext | None:
    if token in _configured_keys():
        return AuthContext(method="api_key", subject=credential_fingerprint(token, prefix="key"))
    return None


def validate_credentials(token: str) -> AuthContext | None:
    from docintel.auth.local_tokens import validate_local_token
    from docintel.auth.oidc import validate_oidc_token

    api_match = validate_api_key(token)
    if api_match is not None:
        return api_match
    local_match = validate_local_token(token)
    if local_match is not None:
        return local_match
    return validate_oidc_token(token)
