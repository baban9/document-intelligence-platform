import { useTenant } from "../context/TenantContext";

export function TenantSelector() {
  const { tenantSlug, tenants, isAdmin, loading, error, setTenantSlug } = useTenant();

  if (loading && !tenants.length) {
    return (
      <label className="tenant-selector">
        <span>Tenant</span>
        <select disabled>
          <option>Loading...</option>
        </select>
      </label>
    );
  }

  if (error && !tenants.length) {
    return (
      <div className="tenant-selector">
        <span>Tenant</span>
        <p className="sidebar-note">{error}</p>
      </div>
    );
  }

  return (
    <label className="tenant-selector">
      <span>Tenant{isAdmin ? " (admin)" : ""}</span>
      <select value={tenantSlug} onChange={(event) => setTenantSlug(event.target.value)}>
        {tenants.map((tenant) => (
          <option key={tenant.slug} value={tenant.slug}>
            {tenant.name}
          </option>
        ))}
      </select>
    </label>
  );
}
