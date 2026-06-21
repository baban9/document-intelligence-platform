"""Tests for LLM provider configuration."""

import pytest

from docintel.capabilities.extraction.llm_providers import resolve_llm_config


def test_default_provider_is_ollama(monkeypatch):
    monkeypatch.delenv("DOCINTEL_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("DOCINTEL_LLM_API_KEY", raising=False)
    monkeypatch.delenv("DOCINTEL_LLM_MODEL", raising=False)
    monkeypatch.delenv("DOCINTEL_LLM_BASE_URL", raising=False)

    config = resolve_llm_config()

    assert config.provider == "ollama"
    assert config.api_key == "ollama"
    assert config.model == "llama3.2"
    assert config.base_url == "http://127.0.0.1:11434/v1"


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
    monkeypatch.setenv("DOCINTEL_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("DOCINTEL_LLM_MODEL", "mistral")
    monkeypatch.setenv("DOCINTEL_LLM_BASE_URL", "http://localhost:11434/v1")

    config = resolve_llm_config()

    assert config.model == "mistral"
    assert config.base_url == "http://localhost:11434/v1"


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
        model="llama3.2",
        system_prompt="system",
        user_prompt="user",
    )

    assert content == '{"ok": true}'
    assert client.chat.completions.calls == 2
