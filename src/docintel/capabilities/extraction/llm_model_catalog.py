"""Fetch live model lists from LLM provider APIs."""

from __future__ import annotations

import os

import requests

from docintel.capabilities.extraction.llm_providers import SUPPORTED_PROVIDERS, _first_env

_DEFAULT_MODELS: dict[str, list[str]] = {
    "groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
    "gemini": ["gemini-2.0-flash", "gemini-1.5-pro"],
    "openai": ["gpt-4o-mini", "gpt-4o"],
    "ollama": ["llama3.2", "llama3.1", "mistral"],
}

_ENV_KEYS: dict[str, tuple[str, ...]] = {
    "groq": ("DOCINTEL_LLM_API_KEY", "GROQ_API_KEY"),
    "gemini": ("DOCINTEL_LLM_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "openai": ("DOCINTEL_LLM_API_KEY", "OPENAI_API_KEY"),
    "ollama": ("DOCINTEL_LLM_API_KEY", "OLLAMA_API_KEY"),
}


def resolve_models_api_key(provider: str, explicit_key: str = "", tenant_key: str = "") -> str:
    """Resolve an API key for model catalog requests."""
    if explicit_key.strip():
        return explicit_key.strip()
    if tenant_key.strip():
        return tenant_key.strip()
    return _first_env(_ENV_KEYS.get(provider, ()))


def fetch_provider_models(
    provider: str,
    *,
    api_key: str = "",
    base_url: str = "",
) -> tuple[list[str], str, str | None]:
    """Return sorted model ids, source label, and optional warning."""
    normalized = provider.strip().lower()
    if normalized not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider '{provider}'.")

    if normalized == "ollama":
        return _fetch_ollama_models(base_url)
    if normalized == "groq":
        return _fetch_openai_compatible_models(
            api_key,
            base_url or "https://api.groq.com/openai/v1",
            provider="groq",
        )
    if normalized == "openai":
        return _fetch_openai_compatible_models(
            api_key,
            base_url or "https://api.openai.com/v1",
            provider="openai",
        )
    if normalized == "gemini":
        return _fetch_gemini_models(api_key)

    return _fallback(normalized, "No fetch handler for provider.")


def _fallback(provider: str, warning: str) -> tuple[list[str], str, str | None]:
    return sorted(_DEFAULT_MODELS.get(provider, [])), "fallback", warning


def _fetch_ollama_models(base_url: str) -> tuple[list[str], str, str | None]:
    ollama_root = base_url.rstrip("/").removesuffix("/v1") or os.getenv(
        "DOCINTEL_LLM_BASE_URL", "http://127.0.0.1:11434/v1"
    ).removesuffix("/v1")
    try:
        response = requests.get(f"{ollama_root}/api/tags", timeout=8)
        response.raise_for_status()
        payload = response.json()
        models = [
            str(item.get("name", ""))
            for item in payload.get("models", [])
            if item.get("name")
        ]
        if not models:
            return _fallback("ollama", "Ollama returned no models.")
        return sorted(models), "ollama", None
    except Exception as exc:
        return _fallback("ollama", str(exc))


def _fetch_openai_compatible_models(
    api_key: str,
    base_url: str,
    *,
    provider: str,
) -> tuple[list[str], str, str | None]:
    if not api_key:
        return _fallback(provider, f"{provider} API key is required to list live models.")

    root = base_url.rstrip("/")
    try:
        response = requests.get(
            f"{root}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        models = [
            str(item.get("id", ""))
            for item in payload.get("data", [])
            if item.get("id")
        ]
        if not models:
            return _fallback(provider, f"{provider} returned no models.")
        return sorted(models), provider, None
    except Exception as exc:
        return _fallback(provider, str(exc))


def _fetch_gemini_models(api_key: str) -> tuple[list[str], str, str | None]:
    if not api_key:
        return _fallback("gemini", "Gemini API key is required to list live models.")

    try:
        response = requests.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": api_key},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        models: list[str] = []
        for item in payload.get("models", []):
            raw_name = str(item.get("name", ""))
            if raw_name.startswith("models/"):
                raw_name = raw_name[len("models/") :]
            if not raw_name:
                continue
            methods = item.get("supportedGenerationMethods") or []
            if any(str(method).lower() == "generatecontent" for method in methods):
                models.append(raw_name)
        if not models:
            return _fallback("gemini", "Gemini returned no generateContent models.")
        return sorted(models), "gemini", None
    except Exception as exc:
        return _fallback("gemini", str(exc))
