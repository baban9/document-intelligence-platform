"""Tenant and settings persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from docintel.db.audit import record_audit_event
from docintel.db.connection import database_enabled, get_connection
from docintel.db.secrets import decrypt_secret, decrypt_user_secret, encrypt_user_secret


@dataclass(frozen=True)
class TenantRecord:
    id: str
    slug: str
    name: str
    is_admin: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "is_admin": self.is_admin,
        }


@dataclass(frozen=True)
class TenantSettingsRecord:
    tenant_id: str
    tenant_slug: str
    tenant_name: str
    is_admin: bool
    llm_provider: str
    llm_model: str
    llm_base_url: str
    llm_api_key: str
    llm_api_key_owner: str
    llm_api_key_stored: bool
    pii_entities: list[str]

    def to_dict(
        self,
        *,
        include_secrets: bool = False,
        settings_user_id: str = "",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tenant_id": self.tenant_id,
            "tenant_slug": self.tenant_slug,
            "tenant_name": self.tenant_name,
            "is_admin": self.is_admin,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "llm_base_url": self.llm_base_url,
            "pii_entities": self.pii_entities,
            "llm_api_key_set": self.llm_api_key_stored,
            "llm_api_key_owner_match": bool(
                self.llm_api_key_owner and settings_user_id == self.llm_api_key_owner
            ),
        }
        if self.llm_api_key_stored and self.llm_api_key_owner and not payload["llm_api_key_owner_match"]:
            payload["llm_api_key_locked"] = True
        if include_secrets:
            payload["llm_api_key"] = self.llm_api_key
        return payload


def _row_to_tenant(row) -> TenantRecord:
    return TenantRecord(
        id=str(row[0]),
        slug=str(row[1]),
        name=str(row[2]),
        is_admin=bool(row[3]),
    )


def _decrypt_settings_api_key(stored: str, owner: str) -> str:
    if not stored:
        return ""
    try:
        if stored.startswith("enc:u1:"):
            return decrypt_user_secret(stored, owner_id=owner)
        return decrypt_secret(stored)
    except Exception:
        return ""


def _row_to_settings(row) -> TenantSettingsRecord:
    entities_raw = row[7]
    if isinstance(entities_raw, str):
        entities = json.loads(entities_raw)
    elif isinstance(entities_raw, list):
        entities = entities_raw
    else:
        entities = []
    owner = str(row[9] or "")
    stored_key = str(row[8] or "")
    return TenantSettingsRecord(
        tenant_id=str(row[0]),
        tenant_slug=str(row[1]),
        tenant_name=str(row[2]),
        is_admin=bool(row[3]),
        llm_provider=str(row[4] or "ollama"),
        llm_model=str(row[5] or ""),
        llm_base_url=str(row[6] or ""),
        llm_api_key=_decrypt_settings_api_key(stored_key, owner),
        llm_api_key_owner=owner,
        llm_api_key_stored=bool(stored_key),
        pii_entities=[str(item) for item in entities],
    )


_SETTINGS_SELECT = """
SELECT
    t.id,
    t.slug,
    t.name,
    t.is_admin,
    s.llm_provider,
    s.llm_model,
    s.llm_base_url,
    s.pii_entities,
    s.llm_api_key,
    s.llm_api_key_owner
FROM tenants t
JOIN tenant_settings s ON s.tenant_id = t.id
"""


def list_tenants(*, viewer_slug: str | None = None) -> list[TenantRecord]:
    if not database_enabled():
        return []

    with get_connection() as conn:
        with conn.cursor() as cur:
            if viewer_slug:
                cur.execute(
                    "SELECT id, slug, name, is_admin FROM tenants WHERE slug = %s",
                    (viewer_slug,),
                )
                viewer = cur.fetchone()
                if not viewer:
                    return []
                if viewer[3]:
                    cur.execute("SELECT id, slug, name, is_admin FROM tenants ORDER BY slug")
                else:
                    return [_row_to_tenant(viewer)]
            else:
                cur.execute("SELECT id, slug, name, is_admin FROM tenants ORDER BY slug")
            return [_row_to_tenant(row) for row in cur.fetchall()]


def get_tenant_by_slug(slug: str) -> TenantRecord | None:
    if not database_enabled():
        return None

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, slug, name, is_admin FROM tenants WHERE slug = %s",
                (slug,),
            )
            row = cur.fetchone()
            return _row_to_tenant(row) if row else None


def get_tenant_settings(slug: str) -> TenantSettingsRecord | None:
    if not database_enabled():
        return None

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"{_SETTINGS_SELECT} WHERE t.slug = %s", (slug,))
            row = cur.fetchone()
            return _row_to_settings(row) if row else None


def update_tenant_settings(
    slug: str,
    *,
    llm_provider: str,
    llm_model: str,
    llm_base_url: str,
    llm_api_key: str | None,
    pii_entities: list[str],
    actor: str = "",
    settings_user_id: str = "",
) -> TenantSettingsRecord | None:
    if not database_enabled():
        return None

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.id, s.llm_api_key, s.llm_api_key_owner
                FROM tenants t
                JOIN tenant_settings s ON s.tenant_id = t.id
                WHERE t.slug = %s
                """,
                (slug,),
            )
            row = cur.fetchone()
            if not row:
                return None
            tenant_id = row[0]
            existing_key = str(row[1] or "")
            existing_owner = str(row[2] or "")

            if llm_api_key is None:
                cur.execute(
                    """
                    UPDATE tenant_settings
                    SET llm_provider = %s,
                        llm_model = %s,
                        llm_base_url = %s,
                        pii_entities = %s::jsonb,
                        updated_at = NOW()
                    WHERE tenant_id = %s
                    """,
                    (
                        llm_provider,
                        llm_model,
                        llm_base_url,
                        json.dumps(pii_entities),
                        tenant_id,
                    ),
                )
            else:
                owner_id = settings_user_id.strip()
                if not owner_id:
                    raise ValueError("X-Settings-User-Id is required when saving an API key.")
                if existing_key and existing_owner and existing_owner != owner_id:
                    raise PermissionError(
                        "Only the user who saved this API key can replace it."
                    )
                cur.execute(
                    """
                    UPDATE tenant_settings
                    SET llm_provider = %s,
                        llm_model = %s,
                        llm_base_url = %s,
                        llm_api_key = %s,
                        llm_api_key_owner = %s,
                        pii_entities = %s::jsonb,
                        updated_at = NOW()
                    WHERE tenant_id = %s
                    """,
                    (
                        llm_provider,
                        llm_model,
                        llm_base_url,
                        encrypt_user_secret(llm_api_key, owner_id),
                        owner_id,
                        json.dumps(pii_entities),
                        tenant_id,
                    ),
                )

    record_audit_event(
        tenant_slug=slug,
        action="tenant_settings.update",
        actor=actor,
        resource_type="tenant_settings",
        resource_id=slug,
        details={
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "llm_api_key_updated": llm_api_key is not None,
            "settings_user_id": settings_user_id.strip() if llm_api_key is not None else "",
            "pii_entity_count": len(pii_entities),
        },
    )
    return get_tenant_settings(slug)
