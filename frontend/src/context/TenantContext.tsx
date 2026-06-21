import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { fetchTenants, type TenantRecord } from "../api/client";
import { DEFAULT_TENANT_SLUG, loadTenantSlug, saveTenantSlug } from "../lib/tenantStorage";

type TenantContextValue = {
  tenantSlug: string;
  tenants: TenantRecord[];
  isAdmin: boolean;
  loading: boolean;
  error: string | null;
  setTenantSlug: (slug: string) => void;
  refreshTenants: () => Promise<void>;
};

const TenantContext = createContext<TenantContextValue | null>(null);

export function TenantProvider({ children }: { children: ReactNode }) {
  const [tenantSlug, setTenantSlugState] = useState(loadTenantSlug);
  const [tenants, setTenants] = useState<TenantRecord[]>([]);
  const [isAdmin, setIsAdmin] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshTenants = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = await fetchTenants(tenantSlug);
      setTenants(payload.tenants);
      setIsAdmin(payload.is_admin);
      const known = payload.tenants.some((tenant) => tenant.slug === tenantSlug);
      if (!known && payload.tenants.length) {
        const fallback = payload.current_tenant || payload.tenants[0].slug;
        setTenantSlugState(fallback);
        saveTenantSlug(fallback);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load tenants.");
      setTenants([]);
      setIsAdmin(false);
    } finally {
      setLoading(false);
    }
  }, [tenantSlug]);

  useEffect(() => {
    void refreshTenants();
  }, [refreshTenants]);

  const setTenantSlug = useCallback((slug: string) => {
    const cleaned = slug.trim() || DEFAULT_TENANT_SLUG;
    setTenantSlugState(cleaned);
    saveTenantSlug(cleaned);
  }, []);

  const value = useMemo(
    () => ({
      tenantSlug,
      tenants,
      isAdmin,
      loading,
      error,
      setTenantSlug,
      refreshTenants,
    }),
    [tenantSlug, tenants, isAdmin, loading, error, setTenantSlug, refreshTenants],
  );

  return <TenantContext.Provider value={value}>{children}</TenantContext.Provider>;
}

export function useTenant(): TenantContextValue {
  const context = useContext(TenantContext);
  if (!context) {
    throw new Error("useTenant must be used within TenantProvider.");
  }
  return context;
}
