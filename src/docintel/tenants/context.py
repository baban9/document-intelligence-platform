"""Request-scoped tenant context."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from docintel.db.tenants import TenantSettingsRecord, get_tenant_by_slug, get_tenant_settings

_tenant_settings: ContextVar["TenantContext | None"] = ContextVar("tenant_settings", default=None)


@dataclass(frozen=True)
class TenantContext:
    slug: str
    name: str
    is_admin: bool
    settings: TenantSettingsRecord | None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "slug": self.slug,
            "name": self.name,
            "is_admin": self.is_admin,
        }
        if self.settings is not None:
            payload["settings"] = self.settings.to_dict()
        return payload


def set_tenant_context(context: TenantContext | None) -> None:
    _tenant_settings.set(context)


def get_tenant_context() -> TenantContext | None:
    return _tenant_settings.get()


def resolve_tenant_context(slug: str) -> TenantContext | None:
    tenant = get_tenant_by_slug(slug)
    if tenant is None:
        return None
    settings = get_tenant_settings(slug)
    return TenantContext(
        slug=tenant.slug,
        name=tenant.name,
        is_admin=tenant.is_admin,
        settings=settings,
    )


def can_access_tenant(viewer: TenantContext, target_slug: str) -> bool:
    if viewer.slug == target_slug:
        return True
    return viewer.is_admin
