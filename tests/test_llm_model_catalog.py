"""Tests for live LLM model catalog fetching."""

from unittest.mock import MagicMock

from docintel.capabilities.extraction.llm_model_catalog import (
    fetch_provider_models,
    resolve_models_api_key,
)


def test_resolve_models_api_key_prefers_explicit():
    assert resolve_models_api_key("groq", explicit_key="explicit", tenant_key="tenant") == "explicit"


def test_resolve_models_api_key_uses_tenant(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("DOCINTEL_LLM_API_KEY", raising=False)
    assert resolve_models_api_key("groq", tenant_key="tenant-key") == "tenant-key"


def test_fetch_groq_models_live(monkeypatch):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "data": [{"id": "llama-3.3-70b-versatile"}, {"id": "llama-3.1-8b-instant"}],
    }
    monkeypatch.setattr(
        "docintel.capabilities.extraction.llm_model_catalog.requests.get",
        lambda *args, **kwargs: response,
    )

    models, source, warning = fetch_provider_models(
        "groq",
        api_key="gsk-test",
        base_url="https://api.groq.com/openai/v1",
    )
    assert models == ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"]
    assert source == "groq"
    assert warning is None


def test_fetch_groq_models_fallback_without_key():
    models, source, warning = fetch_provider_models("groq", api_key="")
    assert source == "fallback"
    assert warning
    assert "llama-3.3-70b-versatile" in models


def test_fetch_gemini_models_live(monkeypatch):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "models": [
            {
                "name": "models/gemini-2.0-flash",
                "supportedGenerationMethods": ["generateContent"],
            },
            {
                "name": "models/embedding-001",
                "supportedGenerationMethods": ["embedContent"],
            },
        ]
    }
    monkeypatch.setattr(
        "docintel.capabilities.extraction.llm_model_catalog.requests.get",
        lambda *args, **kwargs: response,
    )

    models, source, warning = fetch_provider_models("gemini", api_key="gemini-test")
    assert models == ["gemini-2.0-flash"]
    assert source == "gemini"
    assert warning is None


def test_list_llm_models_route_groq(seeded_postgres_app, monkeypatch):
    monkeypatch.setattr(
        "docintel.routes.tenants.fetch_provider_models",
        lambda provider, api_key="", base_url="": (
            ["llama-3.3-70b-versatile"],
            "groq",
            None,
        ),
    )
    with seeded_postgres_app.test_client() as client:
        response = client.get(
            "/v1/tenants/llm/models?provider=groq",
            headers={"X-Tenant-Slug": "admin"},
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["source"] == "groq"
    assert payload["models"] == ["llama-3.3-70b-versatile"]
