"""Unit tests for tenant access rules."""

from docintel.tenants.context import TenantContext, can_access_tenant


def _ctx(slug: str, is_admin: bool) -> TenantContext:
    return TenantContext(slug=slug, name=slug, is_admin=is_admin, settings=None)


def test_tenant_can_access_self():
    viewer = _ctx("acme-corp", False)
    assert can_access_tenant(viewer, "acme-corp") is True


def test_regular_tenant_cannot_access_other():
    viewer = _ctx("acme-corp", False)
    assert can_access_tenant(viewer, "finance-hub") is False


def test_admin_can_access_other_tenants():
    viewer = _ctx("admin", True)
    assert can_access_tenant(viewer, "finance-hub") is True
