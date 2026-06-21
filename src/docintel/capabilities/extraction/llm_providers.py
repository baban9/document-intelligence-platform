"""LLM provider presets for OpenAI-compatible chat APIs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Iterable

SUPPORTED_PROVIDERS = ("groq", "gemini", "openai")

_PROVIDER_ALIASES = {
    "google": "gemini",
}


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    api_key: str
    model: str
    base_url: str | None


def _normalize_provider(raw: str) -> str:
    value = raw.strip().lower()
    value = _PROVIDER_ALIASES.get(value, value)
    if value not in SUPPORTED_PROVIDERS:
        supported = ", ".join(SUPPORTED_PROVIDERS)
        raise ValueError(f"Unknown LLM provider '{raw}'. Supported: {supported}")
    return value


def _first_env(names: Iterable[str]) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def resolve_llm_config() -> LLMConfig:
    """Resolve LLM settings from tenant context or DOCINTEL_LLM_* env vars."""
    from docintel.tenants.context import get_tenant_context

    tenant = get_tenant_context()
    if tenant and tenant.settings:
        settings = tenant.settings
        provider = _normalize_provider(settings.llm_provider or "groq")
        return _config_for_provider(
            provider,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            base_url=settings.llm_base_url,
        )

    provider = _normalize_provider(os.getenv("DOCINTEL_LLM_PROVIDER", "groq"))
    return _config_for_provider(provider)


def _config_for_provider(
    provider: str,
    *,
    api_key: str = "",
    model: str = "",
    base_url: str = "",
) -> LLMConfig:
    if provider == "groq":
        resolved_key = api_key or _first_env(("DOCINTEL_LLM_API_KEY", "GROQ_API_KEY"))
        if not resolved_key:
            raise RuntimeError(
                "Groq requires DOCINTEL_LLM_API_KEY or GROQ_API_KEY. "
                "Get a key at https://console.groq.com/keys"
            )
        resolved_model = model or os.getenv("DOCINTEL_LLM_MODEL", "llama-3.3-70b-versatile").strip()
        resolved_base = base_url or os.getenv("DOCINTEL_LLM_BASE_URL", "https://api.groq.com/openai/v1").strip()
        return LLMConfig(provider=provider, api_key=resolved_key, model=resolved_model, base_url=resolved_base or None)

    if provider == "gemini":
        resolved_key = api_key or _first_env(("DOCINTEL_LLM_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"))
        if not resolved_key:
            raise RuntimeError(
                "Gemini requires DOCINTEL_LLM_API_KEY, GEMINI_API_KEY, or GOOGLE_API_KEY. "
                "Get a key at https://aistudio.google.com/apikey"
            )
        resolved_model = model or os.getenv("DOCINTEL_LLM_MODEL", "gemini-2.0-flash").strip()
        resolved_base = base_url or os.getenv(
            "DOCINTEL_LLM_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta/openai/",
        ).strip()
        return LLMConfig(provider=provider, api_key=resolved_key, model=resolved_model, base_url=resolved_base or None)

    resolved_key = api_key or _first_env(("DOCINTEL_LLM_API_KEY", "OPENAI_API_KEY"))
    if not resolved_key:
        raise RuntimeError(
            "OpenAI requires DOCINTEL_LLM_API_KEY or OPENAI_API_KEY. "
            "Get a key at https://platform.openai.com/api-keys"
        )
    resolved_model = model or os.getenv("DOCINTEL_LLM_MODEL", "gpt-4o-mini").strip()
    resolved_base = base_url or os.getenv("DOCINTEL_LLM_BASE_URL", "").strip() or None
    return LLMConfig(provider=provider, api_key=resolved_key, model=resolved_model, base_url=resolved_base)


def resolve_llm_config_legacy_env_only() -> LLMConfig:
    """Backward-compatible env-only resolver (used in tests)."""
    provider = _normalize_provider(os.getenv("DOCINTEL_LLM_PROVIDER", "groq"))
    return _config_for_provider(provider)


def create_openai_client(config: LLMConfig):
    """Build an OpenAI SDK client for the resolved provider."""
    from openai import OpenAI

    client_kwargs: dict[str, Any] = {"api_key": config.api_key}
    if config.base_url:
        client_kwargs["base_url"] = config.base_url
    return OpenAI(**client_kwargs)


def chat_json_completion(
    client,
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.1,
) -> str:
    """Request a JSON object response, with a fallback for providers without response_format."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        response = client.chat.completions.create(
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=messages,
        )
    except Exception:
        response = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=messages,
        )
    return response.choices[0].message.content or "{}"
