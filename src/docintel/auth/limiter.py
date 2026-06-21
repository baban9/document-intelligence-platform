"""Redis-backed per-tenant rate limits."""

from __future__ import annotations

import os

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from docintel.auth.api_keys import extract_bearer_token
from docintel.ops.secrets import credential_fingerprint
from docintel.jobs.store import redis_url


def _rate_limit_key() -> str:
    token = extract_bearer_token()
    if token:
        return credential_fingerprint(token, prefix="rl")
    return get_remote_address()


def rate_limits_enabled() -> bool:
    return os.getenv("DOCINTEL_RATE_LIMIT_ENABLED", "true").lower() == "true"


def storage_uri() -> str:
    if rate_limits_enabled():
        return redis_url()
    return "memory://"


limiter = Limiter(
    key_func=_rate_limit_key,
    default_limits=[],
    storage_uri="memory://",
    strategy="fixed-window",
)


def init_limiter(app) -> None:
    app.config["RATELIMIT_STORAGE_URI"] = storage_uri()
    limiter.init_app(app)
