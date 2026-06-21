"""Tests for LLM provider configuration."""

import pytest

from docintel.capabilities.extraction.llm_providers import resolve_llm_config


def test_default_provider_is_groq_requires_api_key(monkeypatch):
    monkeypatch.delenv("DOCINTEL_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("DOCINTEL_LLM_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("DOCINTEL_LLM_MODEL", raising=False)
    monkeypatch.delenv("DOCINTEL_LLM_BASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="Groq requires"):
        resolve_llm_config()


def test_groq_provider_uses_groq_api_key(monkeypatch):
    monkeypatch.setenv("DOCINTEL_LLM_PROVIDER", "groq")
    monkeypatch.delenv("DOCINTEL_LLM_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.delenv("DOCINTEL_LLM_MODEL", raising=False)
    monkeypatch.delenv("DOCINTEL_LLM_BASE_URL", raising=False)

    config = resolve_llm_config()

    assert config.provider == "groq"
    assert config.api_key == "gsk-test"
    assert config.model == "llama-3.3-70b-versatile"
    assert config.base_url == "https://api.groq.com/openai/v1"


def test_gemini_provider_uses_google_api_key(monkeypatch):
    monkeypatch.setenv("DOCINTEL_LLM_PROVIDER", "gemini")
    monkeypatch.delenv("DOCINTEL_LLM_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test")
    monkeypatch.delenv("DOCINTEL_LLM_MODEL", raising=False)
    monkeypatch.delenv("DOCINTEL_LLM_BASE_URL", raising=False)

    config = resolve_llm_config()

    assert config.provider == "gemini"
    assert config.api_key == "google-test"
    assert config.model == "gemini-2.0-flash"
    assert config.base_url == "https://generativelanguage.googleapis.com/v1beta/openai/"


def test_openai_provider_requires_api_key(monkeypatch):
    monkeypatch.setenv("DOCINTEL_LLM_PROVIDER", "openai")
    monkeypatch.delenv("DOCINTEL_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OpenAI requires"):
        resolve_llm_config()


def test_openai_provider_uses_openai_api_key(monkeypatch):
    monkeypatch.setenv("DOCINTEL_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("DOCINTEL_LLM_MODEL", raising=False)
    monkeypatch.delenv("DOCINTEL_LLM_BASE_URL", raising=False)

    config = resolve_llm_config()

    assert config.provider == "openai"
    assert config.api_key == "sk-test"
    assert config.model == "gpt-4o-mini"
    assert config.base_url is None


def test_docintel_llm_api_key_overrides_provider_key(monkeypatch):
    monkeypatch.setenv("DOCINTEL_LLM_PROVIDER", "groq")
    monkeypatch.setenv("DOCINTEL_LLM_API_KEY", "shared-key")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-other")

    config = resolve_llm_config()

    assert config.api_key == "shared-key"


def test_custom_model_and_base_url_override(monkeypatch):
    monkeypatch.setenv("DOCINTEL_LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("DOCINTEL_LLM_MODEL", "llama-3.1-8b-instant")
    monkeypatch.setenv("DOCINTEL_LLM_BASE_URL", "https://api.groq.com/openai/v1")

    config = resolve_llm_config()

    assert config.model == "llama-3.1-8b-instant"
    assert config.base_url == "https://api.groq.com/openai/v1"


def test_groq_ignores_stale_openai_base_url(monkeypatch):
    from docintel.capabilities.extraction.llm_providers import (
        _config_for_provider,
        resolve_base_url,
        sanitize_stored_base_url,
    )

    assert resolve_base_url("groq", "https://api.openai.com/v1") == "https://api.groq.com/openai/v1"
    assert sanitize_stored_base_url("groq", "https://api.openai.com/v1") == ""

    config = _config_for_provider(
        "groq",
        api_key="gsk-test",
        base_url="https://api.openai.com/v1",
    )
    assert config.base_url == "https://api.groq.com/openai/v1"


def test_chat_json_completion_falls_back_without_response_format(monkeypatch):
    class FakeMessage:
        content = '{"ok": true}'

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    class FakeCompletions:
        def __init__(self):
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            if "response_format" in kwargs:
                raise RuntimeError("response_format not supported")
            return FakeResponse()

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    from docintel.capabilities.extraction.llm_providers import chat_json_completion

    client = FakeClient()
    content = chat_json_completion(
        client,
        model="llama-3.3-70b-versatile",
        system_prompt="system",
        user_prompt="user",
    )

    assert content == '{"ok": true}'
    assert client.chat.completions.calls == 2
