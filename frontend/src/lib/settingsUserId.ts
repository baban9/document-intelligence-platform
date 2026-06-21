const STORAGE_KEY = "docintel.settings.user_id";

export const SETTINGS_USER_HEADER = "X-Settings-User-Id";

export function loadSettingsUserId(): string {
  try {
    const existing = localStorage.getItem(STORAGE_KEY);
    if (existing?.trim()) {
      return existing.trim();
    }
    const created = crypto.randomUUID();
    localStorage.setItem(STORAGE_KEY, created);
    return created;
  } catch {
    return "anonymous-settings-user";
  }
}
