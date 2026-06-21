"""Tenant and settings persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from docintel.db.connection import database_enabled, get_connection


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
    pii_entities: list[str]

    def to_dict(self, *, include_secrets: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tenant_id": self.tenant_id,
            "tenant_slug": self.tenant_slug,
            "tenant_name": self.tenant_name,
            "is_admin": self.is_admin,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "llm_base_url": self.llm_base_url,
            "pii_entities": self.pii_entities,
        }
        if include_secrets:
            payload["llm_api_key"] = self.llm_api_key
        else:
            payload["llm_api_key_set"] = bool(self.llm_api_key)
        return payload


def _row_to_tenant(row) -> TenantRecord:
    return TenantRecord(
        id=str(row[0]),
        slug=str(row[1]),
        name=str(row[2]),
        is_admin=bool(row[3]),
    )


def _row_to_settings(row) -> TenantSettingsRecord:
    entities_raw = row[7]
    if isinstance(entities_raw, str):
        entities = json.loads(entities_raw)
    elif isinstance(entities_raw, list):
        entities = entities_raw
    else:
        entities = []
    return TenantSettingsRecord(
        tenant_id=str(row[0]),
        tenant_slug=str(row[1]),
        tenant_name=str(row[2]),
        is_admin=bool(row[3]),
        llm_provider=str(row[4] or "ollama"),
        llm_model=str(row[5] or ""),
        llm_base_url=str(row[6] or ""),
        llm_api_key=str(row[8] or ""),
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
    s.llm_api_key
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
) -> TenantSettingsRecord | None:
    if not database_enabled():
        return None

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM tenants WHERE slug = %s", (slug,))
            row = cur.fetchone()
            if not row:
                return None
            tenant_id = row[0]

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
                cur.execute(
                    """
                    UPDATE tenant_settings
                    SET llm_provider = %s,
                        llm_model = %s,
                        llm_base_url = %s,
                        llm_api_key = %s,
                        pii_entities = %s::jsonb,
                        updated_at = NOW()
                    WHERE tenant_id = %s
                    """,
                    (
                        llm_provider,
                        llm_model,
                        llm_base_url,
                        llm_api_key,
                        json.dumps(pii_entities),
                        tenant_id,
                    ),
                )

    return get_tenant_settings(slug)
