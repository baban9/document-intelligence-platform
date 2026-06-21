import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  exchangeOidcCode,
  fetchAuthConfig,
  fetchAuthMe,
  oidcLoginUrl,
  type AuthConfig,
  type AuthMe,
} from "../api/client";
import {
  clearAuthToken,
  clearOidcState,
  consumeOidcCallbackParams,
  loadOidcState,
  saveAuthToken,
  saveOidcState,
} from "../lib/authStorage";

type AuthContextValue = {
  config: AuthConfig | null;
  user: AuthMe | null;
  loading: boolean;
  error: string | null;
  loginWithOidc: () => void;
  logout: () => void;
  refreshAuth: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [user, setUser] = useState<AuthMe | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshAuth = useCallback(async () => {
    setError(null);
    try {
      const [nextConfig, nextUser] = await Promise.all([fetchAuthConfig(), fetchAuthMe()]);
      setConfig(nextConfig);
      setUser(nextUser);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load auth state.");
      setConfig(null);
      setUser(null);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      setLoading(true);
      try {
        const callback = consumeOidcCallbackParams();
        if (callback) {
          const expectedState = loadOidcState();
          if (expectedState && callback.state && expectedState !== callback.state) {
            throw new Error("OIDC state mismatch. Login was not completed.");
          }
          const token = await exchangeOidcCode(callback.code, window.location.origin + "/");
          saveAuthToken(token);
          clearOidcState();
        }
        if (!cancelled) {
          await refreshAuth();
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Authentication setup failed.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [refreshAuth]);

  const loginWithOidc = useCallback(() => {
    if (!config?.oidc_enabled) {
      setError("OIDC login is not enabled on this server.");
      return;
    }
    const state = crypto.randomUUID();
    saveOidcState(state);
    window.location.href = oidcLoginUrl(window.location.origin + "/", state);
  }, [config]);

  const logout = useCallback(() => {
    clearAuthToken();
    clearOidcState();
    setUser({ authenticated: false });
  }, []);

  const value = useMemo(
    () => ({
      config,
      user,
      loading,
      error,
      loginWithOidc,
      logout,
      refreshAuth,
    }),
    [config, user, loading, error, loginWithOidc, logout, refreshAuth],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider.");
  }
  return context;
}
