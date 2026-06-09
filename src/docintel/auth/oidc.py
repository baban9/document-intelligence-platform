"""Optional OIDC bearer token validation (Session 5 hook, no-op when unset)."""

from __future__ import annotations

import os

from docintel.auth.api_keys import AuthContext


def oidc_enabled() -> bool:
    return bool(os.getenv("DOCINTEL_OIDC_ISSUER", "").strip())


def validate_oidc_token(token: str) -> AuthContext | None:
    if not oidc_enabled():
        return None
    if token.count(".") != 2:
        return None

    issuer = os.getenv("DOCINTEL_OIDC_ISSUER", "").strip()
    audience = os.getenv("DOCINTEL_OIDC_AUDIENCE", "").strip() or None
    jwks_url = os.getenv("DOCINTEL_OIDC_JWKS_URL", "").strip()
    if not jwks_url and issuer:
        jwks_url = issuer.rstrip("/") + "/.well-known/jwks.json"

    try:
        import jwt
        from jwt import PyJWKClient
    except ImportError as exc:
        raise RuntimeError(
            "OIDC auth requires PyJWT. Run: pip install -e '.[auth]'"
        ) from exc

    client = PyJWKClient(jwks_url)
    signing_key = client.get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256", "ES256"],
        audience=audience,
        issuer=issuer,
        options={"verify_aud": audience is not None},
    )
    subject = str(claims.get("sub") or claims.get("email") or "oidc-user")
    return AuthContext(method="oidc", subject=subject)
