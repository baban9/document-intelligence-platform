"""Multi-tenant settings API."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from docintel.auth.limiter import limiter
from docintel.capabilities.extraction.llm_model_catalog import (
    fetch_provider_models,
    resolve_models_api_key,
)
from docintel.capabilities.extraction.llm_providers import SUPPORTED_PROVIDERS
from docintel.db.tenants import get_tenant_settings, list_tenants, update_tenant_settings
from docintel.services.pdf.pii import list_supported_entities
from docintel.tenants.context import can_access_tenant
from docintel.tenants.middleware import multi_tenant_enabled
from docintel.tenants.settings_user import resolve_settings_user_id

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

    return jsonify(
        {
            "status": "ok",
            **settings.to_dict(settings_user_id=resolve_settings_user_id()),
        }
    ), 200


@tenants_bp.get("/<slug>/settings/api-key")
@limiter.limit("30 per hour")
def reveal_settings_api_key(slug: str):
    """Return the stored LLM API key only to the browser user who saved it."""
    if not multi_tenant_enabled():
        return jsonify({"error": "Multi-tenant mode is disabled."}), 503

    viewer = _viewer_context()
    if viewer is None:
        return jsonify({"error": "Tenant context is required."}), 400
    if not can_access_tenant(viewer, slug):
        return jsonify({"error": "Access denied for this tenant."}), 403

    settings_user_id = resolve_settings_user_id()
    if not settings_user_id:
        return jsonify({"error": "X-Settings-User-Id header is required."}), 400

    settings = get_tenant_settings(slug)
    if settings is None:
        return jsonify({"error": "Tenant not found."}), 404
    if not settings.llm_api_key_stored:
        return jsonify({"error": "No API key is stored for this tenant."}), 404
    if not settings.llm_api_key_owner or settings.llm_api_key_owner != settings_user_id:
        return jsonify({"error": "Only the user who saved this API key can view it."}), 403
    if not settings.llm_api_key:
        return jsonify({"error": "Stored API key could not be decrypted on this server."}), 503

    return jsonify({"status": "ok", "llm_api_key": settings.llm_api_key}), 200


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

    provider = str(payload.get("llm_provider", "groq")).strip().lower()
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

    try:
        updated = update_tenant_settings(
            slug,
            llm_provider=provider,
            llm_model=model,
            llm_base_url=base_url,
            llm_api_key=api_key,
            pii_entities=entities,
            actor=viewer.slug,
            settings_user_id=resolve_settings_user_id(),
        )
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if updated is None:
        return jsonify({"error": "Tenant not found."}), 404

    return jsonify(
        {
            "status": "ok",
            **updated.to_dict(settings_user_id=resolve_settings_user_id()),
        }
    ), 200


@tenants_bp.get("/llm/models")
@limiter.limit("60 per hour")
def list_llm_models():
    """List models for a provider from the live provider API when possible."""
    provider = request.args.get("provider", "groq").strip().lower()
    base_url = request.args.get("base_url", "").strip()
    explicit_key = request.args.get("api_key", "").strip()
    tenant_slug = request.args.get("tenant_slug", "").strip()

    if provider not in SUPPORTED_PROVIDERS:
        return jsonify({"error": f"Unsupported LLM provider '{provider}'."}), 400

    tenant_key = ""
    viewer = _viewer_context()
    resolved_slug = tenant_slug or (viewer.slug if viewer else "")
    settings_user_id = resolve_settings_user_id()
    if resolved_slug:
        if viewer and not can_access_tenant(viewer, resolved_slug):
            return jsonify({"error": "Access denied for this tenant."}), 403
        settings = get_tenant_settings(resolved_slug)
        if settings is not None:
            owner_match = bool(
                settings.llm_api_key_owner and settings_user_id == settings.llm_api_key_owner
            )
            if owner_match or not settings.llm_api_key_owner:
                tenant_key = settings.llm_api_key or ""

    api_key = resolve_models_api_key(provider, explicit_key, tenant_key)
    models, source, warning = fetch_provider_models(provider, api_key=api_key, base_url=base_url)

    payload: dict[str, object] = {
        "status": "ok",
        "provider": provider,
        "models": models,
        "source": source,
    }
    if warning:
        payload["warning"] = warning
    return jsonify(payload), 200


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
