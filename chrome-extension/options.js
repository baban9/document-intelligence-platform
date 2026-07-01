import { checkHealth, loadConfig, saveConfig } from "./api.js";

const form = document.getElementById("options-form");
const statusEl = document.getElementById("options-status");

async function hydrate() {
  const config = await loadConfig();
  document.getElementById("api-base").value = config.apiBase;
  document.getElementById("api-key").value = config.apiKey;
  document.getElementById("tenant-slug").value = config.tenantSlug;
  document.getElementById("vertical").value = config.vertical;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const config = {
    apiBase: document.getElementById("api-base").value.trim().replace(/\/$/, ""),
    apiKey: document.getElementById("api-key").value.trim(),
    tenantSlug: document.getElementById("tenant-slug").value.trim() || "admin",
    vertical: document.getElementById("vertical").value,
  };
  await saveConfig(config);
  const origin = new URL(config.apiBase).origin;
  const granted = await chrome.permissions.request({
    origins: [`${origin}/*`],
  });
  setStatus(
    granted
      ? "Settings saved. API host permission granted."
      : "Settings saved. Grant host permission when Chrome prompts you.",
    granted ? "ok" : "warn",
  );
});

document.getElementById("test-connection").addEventListener("click", async () => {
  try {
    const config = {
      apiBase: document.getElementById("api-base").value.trim().replace(/\/$/, ""),
      apiKey: document.getElementById("api-key").value.trim(),
      tenantSlug: document.getElementById("tenant-slug").value.trim() || "admin",
      vertical: document.getElementById("vertical").value,
    };
    const health = await checkHealth(config);
    setStatus(`Connected. Service ${health.service} v${health.version}.`, "ok");
  } catch (error) {
    setStatus(String(error.message || error), "error");
  }
});

function setStatus(message, tone) {
  statusEl.textContent = message;
  statusEl.className = `status ${tone}`;
}

void hydrate();
