"""Tests for API key authentication."""

import os

import pytest

from docintel.app import create_app


@pytest.fixture
def auth_env(monkeypatch):
    monkeypatch.setenv("DOCINTEL_API_KEYS", "test-secret-key")
    monkeypatch.setenv("DOCINTEL_AUTH_REQUIRED", "true")
    monkeypatch.setenv("DOCINTEL_RATE_LIMIT_ENABLED", "false")


def test_health_is_public_without_api_key(auth_env):
    app = create_app()
    with app.test_client() as client:
        response = client.get("/health")
    assert response.status_code == 200


def test_v1_route_requires_api_key(auth_env, tmp_path):
    app = create_app()
    app.config["UPLOAD_DIR"] = str(tmp_path / "uploads")

    with app.test_client() as client:
        response = client.post(
            "/v1/text/summarize",
            json={"text": "hello world", "sentences": 1},
        )

    assert response.status_code == 401


def test_v1_route_accepts_valid_api_key(auth_env, tmp_path):
    app = create_app()
    app.config["UPLOAD_DIR"] = str(tmp_path / "uploads")

    with app.test_client() as client:
        response = client.post(
            "/v1/text/summarize",
            json={"text": "One sentence here for summary.", "sentences": 1},
            headers={"Authorization": "Bearer test-secret-key"},
        )

    assert response.status_code == 200


def test_invalid_api_key_returns_401(auth_env):
    app = create_app()
    with app.test_client() as client:
        response = client.get(
            "/v1/pdf/entities",
            headers={"Authorization": "Bearer wrong-key"},
        )
    assert response.status_code == 401
