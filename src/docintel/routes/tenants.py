"""Multi-tenant settings API."""

from __future__ import annotations

import os

import requests
from flask import Blueprint, g, jsonify, request

from docintel.auth.limiter import limiter
from docintel.capabilities.extraction.llm_providers import SUPPORTED_PROVIDERS
from docintel.db.tenants import get_tenant_settings, list_tenants, update_tenant_settings
from docintel.services.pdf.pii import list_supported_entities
from docintel.tenants.context import can_access_tenant
from docintel.tenants.middleware import multi_tenant_enabled

tenants_bp = Blueprint("tenants", __name__, url_prefix="/v1/tenants")


def _viewer_context():
    if not multi_tenant_enabled():
        return None
    return getattr(g, "tenant", None)


def _target_slug(raw: str | None = None) -> str | None:
    viewer = _viewer_context()
    if viewer is None:
        return raw
    requested = (raw or viewer.slug).strip()
    if not can_access_tenant(viewer, requested):
        return None
    return requested


@tenants_bp.get("")
@limiter.limit("120 per hour")
def list_tenant_records():
    """List tenants visible to the current tenant (admin sees all)."""
    if not multi_tenant_enabled():
        return jsonify({"error": "Multi-tenant mode is disabled."}), 503

    viewer = _viewer_context()
    if viewer is None:
        return jsonify({"error": "Tenant context is required."}), 400

    tenants = list_tenants(viewer_slug=viewer.slug)
    return jsonify(
        {
            "status": "ok",
            "current_tenant": viewer.slug,
            "is_admin": viewer.is_admin,
            "tenants": [tenant.to_dict() for tenant in tenants],
        }
    ), 200


@tenants_bp.get("/<slug>/settings")
@limiter.limit("120 per hour")
def get_settings(slug: str):
    """Return LLM and PII settings for a tenant."""
    if not multi_tenant_enabled():
        return jsonify({"error": "Multi-tenant mode is disabled."}), 503

    viewer = _viewer_context()
    if viewer is None:
        return jsonify({"error": "Tenant context is required."}), 400
    if not can_access_tenant(viewer, slug):
        return jsonify({"error": "Access denied for this tenant."}), 403

    settings = get_tenant_settings(slug)
    if settings is None:
        return jsonify({"error": "Tenant not found."}), 404

    return jsonify({"status": "ok", **settings.to_dict()}), 200


@tenants_bp.put("/<slug>/settings")
@limiter.limit("60 per hour")
def put_settings(slug: str):
    """Update LLM and PII settings for a tenant."""
    if not multi_tenant_enabled():
        return jsonify({"error": "Multi-tenant mode is disabled."}), 503

    viewer = _viewer_context()
    if viewer is None:
        return jsonify({"error": "Tenant context is required."}), 400
    if not can_access_tenant(viewer, slug):
        return jsonify({"error": "Access denied for this tenant."}), 403

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be JSON."}), 400

    provider = str(payload.get("llm_provider", "ollama")).strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        return jsonify({"error": f"Unsupported LLM provider '{provider}'."}), 400

    model = str(payload.get("llm_model", "")).strip()
    base_url = str(payload.get("llm_base_url", "")).strip()
    api_key_raw = payload.get("llm_api_key")
    api_key = str(api_key_raw).strip() if isinstance(api_key_raw, str) and api_key_raw.strip() else None

    entities_raw = payload.get("pii_entities", [])
    if not isinstance(entities_raw, list):
        return jsonify({"error": "Field 'pii_entities' must be a list."}), 400
    entities = [str(item).strip() for item in entities_raw if str(item).strip()]

    updated = update_tenant_settings(
        slug,
        llm_provider=provider,
        llm_model=model,
        llm_base_url=base_url,
        llm_api_key=api_key,
        pii_entities=entities,
    )
    if updated is None:
        return jsonify({"error": "Tenant not found."}), 404

    return jsonify({"status": "ok", **updated.to_dict()}), 200


@tenants_bp.get("/llm/models")
@limiter.limit("60 per hour")
def list_llm_models():
    """List models for a provider (Ollama lists live models when reachable)."""
    provider = request.args.get("provider", "ollama").strip().lower()
    base_url = request.args.get("base_url", "").strip()

    if provider != "ollama":
        defaults = {
            "groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
            "gemini": ["gemini-2.0-flash", "gemini-1.5-pro"],
            "openai": ["gpt-4o-mini", "gpt-4o"],
        }
        return jsonify(
            {
                "status": "ok",
                "provider": provider,
                "models": defaults.get(provider, []),
                "source": "defaults",
            }
        ), 200

    ollama_root = base_url.rstrip("/").removesuffix("/v1") or os.getenv(
        "DOCINTEL_LLM_BASE_URL", "http://127.0.0.1:11434/v1"
    ).removesuffix("/v1")
    try:
        response = requests.get(f"{ollama_root}/api/tags", timeout=5)
        response.raise_for_status()
        payload = response.json()
        models = [str(item.get("name", "")) for item in payload.get("models", []) if item.get("name")]
        return jsonify(
            {
                "status": "ok",
                "provider": provider,
                "models": sorted(models),
                "source": "ollama",
            }
        ), 200
    except Exception as exc:
        return jsonify(
            {
                "status": "ok",
                "provider": provider,
                "models": ["llama3.2", "llama3.1", "mistral"],
                "source": "fallback",
                "warning": str(exc),
            }
        ), 200


@tenants_bp.get("/pii/entities")
@limiter.limit("120 per hour")
def list_pii_entity_options():
    """Return supported Presidio entity types for settings UI."""
    return jsonify(
        {
            "status": "ok",
            "entities": sorted(list_supported_entities()),
        }
    ), 200
