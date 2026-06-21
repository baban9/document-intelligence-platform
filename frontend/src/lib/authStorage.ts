const TOKEN_KEY = "docintel.auth.token";

export function loadAuthToken(): string {
  try {
    const stored = sessionStorage.getItem(TOKEN_KEY);
    if (stored?.trim()) {
      return stored.trim();
    }
  } catch {
    // ignore storage errors
  }
  const envToken = import.meta.env.VITE_DOCINTEL_API_KEY;
  return typeof envToken === "string" ? envToken.trim() : "";
}

export function saveAuthToken(token: string): void {
  try {
    sessionStorage.setItem(TOKEN_KEY, token.trim());
  } catch {
    // ignore storage errors
  }
}

export function clearAuthToken(): void {
  try {
    sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // ignore storage errors
  }
}

const STATE_KEY = "docintel.oidc.state";

export function saveOidcState(state: string): void {
  try {
    sessionStorage.setItem(STATE_KEY, state);
  } catch {
    // ignore storage errors
  }
}

export function loadOidcState(): string {
  try {
    return sessionStorage.getItem(STATE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function clearOidcState(): void {
  try {
    sessionStorage.removeItem(STATE_KEY);
  } catch {
    // ignore storage errors
  }
}

export function consumeOidcCallbackParams(): { code: string; state: string } | null {
  const params = new URLSearchParams(window.location.search);
  const code = params.get("code")?.trim() ?? "";
  const state = params.get("state")?.trim() ?? "";
  if (!code) {
    return null;
  }
  const cleaned = new URL(window.location.href);
  cleaned.searchParams.delete("code");
  cleaned.searchParams.delete("state");
  window.history.replaceState({}, "", cleaned.pathname + cleaned.search + cleaned.hash);
  return { code, state };
}
