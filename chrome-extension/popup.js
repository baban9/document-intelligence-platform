import { formatEntityLabel, loadConfig, severityClass } from "./api.js";

const statusEl = document.getElementById("status");
const summaryEl = document.getElementById("summary");
const integritySection = document.getElementById("integrity-section");
const integrityList = document.getElementById("integrity-list");
const piiSection = document.getElementById("pii-section");
const piiList = document.getElementById("pii-list");

let lastPiiFindings = [];

document.getElementById("scan-page").addEventListener("click", () => runScan("page"));
document.getElementById("scan-selection").addEventListener("click", () => runScan("selection"));
document.getElementById("highlight-pii").addEventListener("click", highlightOnPage);
document.getElementById("open-options").addEventListener("click", (event) => {
  event.preventDefault();
  chrome.runtime.openOptionsPage();
});

chrome.storage.session.get("pendingScan", async (stored) => {
  if (stored.pendingScan?.mode) {
    await chrome.storage.session.remove("pendingScan");
    await runScan(stored.pendingScan.mode);
  } else {
    await showConnectionStatus();
  }
});

async function showConnectionStatus() {
  try {
    const config = await loadConfig();
    if (!config.apiKey) {
      setStatus("Set your API key in Settings to start scanning.", "warn");
      return;
    }
    setStatus(`API: ${config.apiBase}`, "muted");
  } catch (error) {
    setStatus(String(error.message || error), "error");
  }
}

async function runScan(mode) {
  setStatus(mode === "selection" ? "Reading selection..." : "Reading page text...", "muted");
  clearResults();
  disableButtons(true);

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) {
      throw new Error("No active tab found.");
    }

    const textResponse = await chrome.runtime.sendMessage({
      type: "get-page-text",
      tabId: tab.id,
      mode,
    });
    if (!textResponse?.ok) {
      throw new Error(textResponse?.error || "Could not read page text.");
    }
    if (!textResponse.text?.trim()) {
      throw new Error(mode === "selection" ? "Select some text first." : "This page has no readable text.");
    }

    setStatus("Scanning for inconsistencies and sensitive data...", "muted");
    const scanResponse = await chrome.runtime.sendMessage({
      type: "scan-text",
      text: textResponse.text,
    });
    if (!scanResponse?.ok) {
      throw new Error(scanResponse?.error || "Scan failed.");
    }

    renderResults(scanResponse.result);
    const note = scanResponse.result.truncated ? " (first 120k characters scanned)" : "";
    setStatus(`Scan complete${note}.`, "ok");
  } catch (error) {
    setStatus(String(error.message || error), "error");
  } finally {
    disableButtons(false);
  }
}

function renderResults(result) {
  const integrityFindings = result.integrity?.findings || [];
  const piiFindings = result.pii?.findings || [];
  lastPiiFindings = piiFindings;

  summaryEl.classList.remove("hidden");
  summaryEl.innerHTML = `
    <div class="summary-grid">
      <div class="summary-card">
        <span class="summary-value">${integrityFindings.length}</span>
        <span class="summary-label">Inconsistencies</span>
      </div>
      <div class="summary-card">
        <span class="summary-value">${piiFindings.length}</span>
        <span class="summary-label">Sensitive items</span>
      </div>
    </div>
  `;

  integritySection.classList.remove("hidden");
  if (!integrityFindings.length) {
    integrityList.innerHTML = `<p class="muted">No inconsistencies found.</p>`;
  } else {
    integrityList.innerHTML = integrityFindings
      .map((finding) => {
        const evidence =
          finding.evidence?.[0] && typeof finding.evidence[0] === "object"
            ? String(finding.evidence[0].quote || "")
            : "";
        return `
          <article class="finding ${severityClass(finding.severity)}">
            <div class="finding-top">
              <span class="badge">${String(finding.severity || "info").toUpperCase()}</span>
              <span class="category">${String(finding.category || "").replace(/_/g, " ")}</span>
            </div>
            <p class="finding-text">${escapeHtml(String(finding.description || ""))}</p>
            ${evidence ? `<p class="evidence">"${escapeHtml(evidence)}"</p>` : ""}
            ${
              finding.suggested_fix
                ? `<p class="fix">Fix: ${escapeHtml(String(finding.suggested_fix))}</p>`
                : ""
            }
          </article>
        `;
      })
      .join("");
  }

  piiSection.classList.remove("hidden");
  if (!piiFindings.length) {
    piiList.innerHTML = `<p class="muted">No sensitive information detected.</p>`;
  } else {
    piiList.innerHTML = piiFindings
      .map((finding) => {
        const label = formatEntityLabel(finding.entity_type);
        const score = Number(finding.score || 0).toFixed(2);
        return `
          <article class="finding severity-medium">
            <div class="finding-top">
              <span class="badge">${escapeHtml(label)}</span>
              <span class="category">score ${score}</span>
            </div>
            <p class="finding-text">"${escapeHtml(String(finding.text || ""))}"</p>
          </article>
        `;
      })
      .join("");
  }
}

async function highlightOnPage() {
  if (!lastPiiFindings.length) {
    setStatus("No sensitive items to highlight.", "warn");
    return;
  }
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) {
    return;
  }
  const response = await chrome.tabs.sendMessage(tab.id, {
    type: "highlight-pii",
    findings: lastPiiFindings,
  });
  if (response?.ok) {
    setStatus(`Highlighted ${response.count} sensitive span(s) on the page.`, "ok");
  }
}

function clearResults() {
  summaryEl.classList.add("hidden");
  integritySection.classList.add("hidden");
  piiSection.classList.add("hidden");
  integrityList.innerHTML = "";
  piiList.innerHTML = "";
  lastPiiFindings = [];
}

function disableButtons(disabled) {
  document.getElementById("scan-page").disabled = disabled;
  document.getElementById("scan-selection").disabled = disabled;
}

function setStatus(message, tone) {
  statusEl.textContent = message;
  statusEl.className = `status ${tone}`;
}

function escapeHtml(value) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
