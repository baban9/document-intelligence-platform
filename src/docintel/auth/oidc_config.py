"""OIDC provider settings and discovery."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

import requests


@dataclass(frozen=True)
class OidcConfig:
    issuer: str
    audience: str | None
    jwks_url: str
    client_id: str
    client_secret: str
    scopes: str

    @property
    def enabled(self) -> bool:
        return bool(self.issuer and self.client_id)


def load_oidc_config() -> OidcConfig | None:
    issuer = os.getenv("DOCINTEL_OIDC_ISSUER", "").strip()
    client_id = os.getenv("DOCINTEL_OIDC_CLIENT_ID", "").strip()
    if not issuer or not client_id:
        return None
    audience = os.getenv("DOCINTEL_OIDC_AUDIENCE", "").strip() or None
    jwks_url = os.getenv("DOCINTEL_OIDC_JWKS_URL", "").strip()
    if not jwks_url:
        jwks_url = issuer.rstrip("/") + "/.well-known/jwks.json"
    client_secret = os.getenv("DOCINTEL_OIDC_CLIENT_SECRET", "").strip()
    scopes = os.getenv("DOCINTEL_OIDC_SCOPES", "openid profile email").strip()
    return OidcConfig(
        issuer=issuer,
        audience=audience,
        jwks_url=jwks_url,
        client_id=client_id,
        client_secret=client_secret,
        scopes=scopes,
    )


@lru_cache(maxsize=4)
def fetch_oidc_discovery(issuer: str) -> dict:
    """Load OpenID Provider metadata (cached)."""
    url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    response = requests.get(url, timeout=8)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Invalid OIDC discovery document.")
    return payload
