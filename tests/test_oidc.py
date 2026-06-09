"""Tests for optional OIDC bearer token authentication."""

import pytest

from docintel.auth.api_keys import validate_credentials
from docintel.auth.oidc import validate_oidc_token


def test_validate_oidc_token_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DOCINTEL_OIDC_ISSUER", raising=False)
    assert validate_oidc_token("header.payload.sig") is None


def test_validate_oidc_token_accepts_valid_jwt(monkeypatch):
    monkeypatch.setenv("DOCINTEL_OIDC_ISSUER", "https://issuer.example.com")
    monkeypatch.setenv("DOCINTEL_OIDC_AUDIENCE", "docintel-api")
    monkeypatch.setenv("DOCINTEL_OIDC_JWKS_URL", "https://issuer.example.com/jwks.json")

    class FakeSigningKey:
        key = "secret"

    class FakeJWKClient:
        def __init__(self, jwks_url):
            self.jwks_url = jwks_url

        def get_signing_key_from_jwt(self, token):
            return FakeSigningKey()

    def fake_decode(token, key, algorithms, audience, issuer, options):
        return {"sub": "user-123", "email": "user@example.com"}

    import jwt as jwt_module

    monkeypatch.setattr(jwt_module, "PyJWKClient", FakeJWKClient)
    monkeypatch.setattr(jwt_module, "decode", fake_decode)

    context = validate_oidc_token("aaa.bbb.ccc")
    assert context is not None
    assert context.method == "oidc"
    assert context.subject == "user-123"


def test_validate_credentials_prefers_api_key(monkeypatch):
    monkeypatch.setenv("DOCINTEL_API_KEYS", "my-api-key")
    monkeypatch.setenv("DOCINTEL_OIDC_ISSUER", "https://issuer.example.com")

    context = validate_credentials("my-api-key")
    assert context is not None
    assert context.method == "api_key"
