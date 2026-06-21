"""Tests for lightweight OIDC auth routes."""

import pytest

from docintel.app import create_app


@pytest.fixture
def oidc_env(monkeypatch):
    monkeypatch.setenv("DOCINTEL_AUTH_REQUIRED", "false")
    monkeypatch.setenv("DOCINTEL_API_KEYS", "")
    monkeypatch.setenv("DOCINTEL_OIDC_ISSUER", "https://issuer.example.com")
    monkeypatch.setenv("DOCINTEL_OIDC_CLIENT_ID", "docintel-ui")
    monkeypatch.setenv("DOCINTEL_OIDC_CLIENT_SECRET", "secret")
    monkeypatch.setenv("DOCINTEL_OIDC_AUDIENCE", "docintel-api")
    monkeypatch.setenv("DOCINTEL_OIDC_JWKS_URL", "https://issuer.example.com/jwks.json")
    return create_app()


def test_auth_config_reports_oidc(oidc_env):
    with oidc_env.test_client() as client:
        response = client.get("/v1/auth/config")
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["oidc_enabled"] is True
    assert payload["oidc_client_id"] == "docintel-ui"


def test_auth_me_without_token(oidc_env):
    with oidc_env.test_client() as client:
        response = client.get("/v1/auth/me")
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["authenticated"] is False


def test_auth_me_with_api_key(monkeypatch):
    monkeypatch.setenv("DOCINTEL_AUTH_REQUIRED", "false")
    monkeypatch.setenv("DOCINTEL_API_KEYS", "dev-key")
    app = create_app()
    with app.test_client() as client:
        response = client.get(
            "/v1/auth/me",
            headers={"Authorization": "Bearer dev-key"},
        )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["authenticated"] is True
    assert payload["method"] == "api_key"


def test_oidc_token_exchange(oidc_env, monkeypatch):
    monkeypatch.setattr(
        "docintel.auth.routes.exchange_authorization_code",
        lambda config, code, redirect_uri: {"access_token": "aaa.bbb.ccc", "token_type": "Bearer"},
    )
    monkeypatch.setattr(
        "docintel.auth.routes.validate_oidc_token",
        lambda token: __import__("docintel.auth.api_keys", fromlist=["AuthContext"]).AuthContext(
            method="oidc",
            subject="user-123",
            email="user@example.com",
        ),
    )

    with oidc_env.test_client() as client:
        response = client.post(
            "/v1/auth/oidc/token",
            json={"code": "auth-code", "redirect_uri": "http://127.0.0.1:8080/"},
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["access_token"] == "aaa.bbb.ccc"
    assert payload["subject"] == "user-123"
    assert payload["email"] == "user@example.com"


def test_oidc_login_redirect(oidc_env, monkeypatch):
    monkeypatch.setattr(
        "docintel.auth.routes.build_authorize_url",
        lambda config, redirect_uri, state: "https://issuer.example.com/authorize?state=abc",
    )
    with oidc_env.test_client() as client:
        response = client.get(
            "/v1/auth/oidc/login?redirect_uri=http://127.0.0.1:8080/&state=abc",
            follow_redirects=False,
        )
    assert response.status_code == 302
    assert "issuer.example.com/authorize" in response.headers["Location"]
