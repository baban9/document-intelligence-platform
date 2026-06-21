"""Resolve tenant-scoped storage prefixes."""

from __future__ import annotations

from docintel.tenants.context import current_tenant_slug
from docintel.tenants.middleware import multi_tenant_enabled


def resolve_storage_tenant_slug(explicit: str | None = None) -> str | None:
    """Return the tenant slug used for upload paths, if any."""
    if explicit:
        return explicit
    if not multi_tenant_enabled():
        return None
    return current_tenant_slug()
