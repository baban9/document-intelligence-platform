"""Audit log persistence for tenant actions."""

from __future__ import annotations

import json
from typing import Any

from docintel.db.connection import database_enabled, get_connection


def record_audit_event(
    *,
    tenant_slug: str,
    action: str,
    actor: str = "",
    resource_type: str = "",
    resource_id: str = "",
    details: dict[str, Any] | None = None,
) -> None:
    """Append one audit row when PostgreSQL is enabled."""
    if not database_enabled():
        return

    payload = details or {}
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM tenants WHERE slug = %s", (tenant_slug,))
            row = cur.fetchone()
            tenant_id = row[0] if row else None
            cur.execute(
                """
                INSERT INTO audit_log (
                    tenant_id,
                    tenant_slug,
                    action,
                    actor,
                    resource_type,
                    resource_id,
                    details
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    tenant_id,
                    tenant_slug,
                    action,
                    actor,
                    resource_type,
                    resource_id,
                    json.dumps(payload),
                ),
            )
