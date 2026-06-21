const STORAGE_KEY = "docintel.tenant.slug";
export const DEFAULT_TENANT_SLUG = "acme-corp";

export function loadTenantSlug(): string {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    if (value?.trim()) {
      return value.trim();
    }
  } catch {
    // ignore storage errors
  }
  return DEFAULT_TENANT_SLUG;
}

export function saveTenantSlug(slug: string): void {
  try {
    localStorage.setItem(STORAGE_KEY, slug.trim());
  } catch {
    // ignore storage errors
  }
}

export const TENANT_HEADER = "X-Tenant-Slug";
