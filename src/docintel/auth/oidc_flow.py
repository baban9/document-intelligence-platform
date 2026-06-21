"""Lightweight OIDC authorization code helpers."""

from __future__ import annotations

from urllib.parse import urlencode

import requests

from docintel.auth.oidc_config import OidcConfig, fetch_oidc_discovery


def build_authorize_url(
    config: OidcConfig,
    *,
    redirect_uri: str,
    state: str,
) -> str:
    discovery = fetch_oidc_discovery(config.issuer)
    endpoint = str(discovery.get("authorization_endpoint", "")).strip()
    if not endpoint:
        raise RuntimeError("OIDC discovery document missing authorization_endpoint.")

    params = {
        "client_id": config.client_id,
        "response_type": "code",
        "scope": config.scopes,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"{endpoint}?{urlencode(params)}"


def exchange_authorization_code(
    config: OidcConfig,
    *,
    code: str,
    redirect_uri: str,
) -> dict:
    discovery = fetch_oidc_discovery(config.issuer)
    endpoint = str(discovery.get("token_endpoint", "")).strip()
    if not endpoint:
        raise RuntimeError("OIDC discovery document missing token_endpoint.")

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": config.client_id,
    }
    if config.client_secret:
        payload["client_secret"] = config.client_secret

    response = requests.post(endpoint, data=payload, timeout=10)
    response.raise_for_status()
    token_payload = response.json()
    if not isinstance(token_payload, dict):
        raise ValueError("Invalid token response from OIDC provider.")
    return token_payload
