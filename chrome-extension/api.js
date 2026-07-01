/** Shared API helpers for the Chrome extension (also used in popup and options). */

const DEFAULT_CONFIG = {
  apiBase: "http://127.0.0.1:5000",
  apiKey: "",
  tenantSlug: "admin",
  vertical: "general",
};

export function loadConfig() {
  return new Promise((resolve) => {
    chrome.storage.sync.get(DEFAULT_CONFIG, (stored) => {
      resolve({
        apiBase: String(stored.apiBase || DEFAULT_CONFIG.apiBase).replace(/\/$/, ""),
        apiKey: String(stored.apiKey || ""),
        tenantSlug: String(stored.tenantSlug || DEFAULT_CONFIG.tenantSlug),
        vertical: String(stored.vertical || DEFAULT_CONFIG.vertical),
      });
    });
  });
}

export function saveConfig(config) {
  return new Promise((resolve) => {
    chrome.storage.sync.set(config, resolve);
  });
}

export async function apiRequest(config, path, { method = "GET", body } = {}) {
  const headers = {
    "X-Tenant-Slug": config.tenantSlug,
  };
  if (config.apiKey) {
    headers.Authorization = `Bearer ${config.apiKey}`;
  }
  const init = { method, headers };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  const response = await fetch(`${config.apiBase}${path}`, init);
  let payload = {};
  try {
    payload = await response.json();
  } catch {
    payload = {};
  }
  if (!response.ok) {
    throw new Error(payload.error || response.statusText || "Request failed");
  }
  return payload;
}

export async function checkHealth(config) {
  return apiRequest(config, "/health");
}

export async function detectPii(config, text) {
  return apiRequest(config, "/v1/documents/detect-pii", {
    method: "POST",
    body: {
      text,
      vertical: config.vertical,
    },
  });
}

export async function analyzeIntegrity(config, text) {
  return apiRequest(config, "/v1/documents/analyze-integrity", {
    method: "POST",
    body: { text },
  });
}

export function formatEntityLabel(entityId) {
  const cleaned = String(entityId || "").trim();
  if (!cleaned) {
    return "";
  }
  const parts = cleaned.split("_").filter(Boolean);
  const phrase = parts.map((word) => word.toLowerCase()).join(" ");
  return phrase ? phrase[0].toUpperCase() + phrase.slice(1) : "";
}

export function severityClass(severity) {
  const key = String(severity || "").toLowerCase();
  if (key === "high" || key === "critical") {
    return "severity-high";
  }
  if (key === "medium") {
    return "severity-medium";
  }
  return "severity-low";
}
