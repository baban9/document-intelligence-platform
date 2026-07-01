import {
  analyzeIntegrity,
  detectPii,
  loadConfig,
} from "./api.js";

const MENU_PAGE = "docintel-scan-page";
const MENU_SELECTION = "docintel-scan-selection";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: MENU_PAGE,
    title: "Scan page for issues and sensitive data",
    contexts: ["page"],
  });
  chrome.contextMenus.create({
    id: MENU_SELECTION,
    title: "Scan selection for issues and sensitive data",
    contexts: ["selection"],
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (!tab?.id) {
    return;
  }
  const mode = info.menuItemId === MENU_SELECTION ? "selection" : "page";
  await chrome.storage.session.set({ pendingScan: { tabId: tab.id, mode } });
  chrome.action.openPopup();
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "scan-text") {
    scanText(message.text)
      .then((result) => sendResponse({ ok: true, result }))
      .catch((error) => sendResponse({ ok: false, error: String(error.message || error) }));
    return true;
  }
  if (message.type === "get-page-text") {
    getPageText(message.tabId, message.mode)
      .then((text) => sendResponse({ ok: true, text }))
      .catch((error) => sendResponse({ ok: false, error: String(error.message || error) }));
    return true;
  }
  return false;
});

async function getPageText(tabId, mode) {
  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId },
    func: (scanMode) => {
      if (scanMode === "selection") {
        const selected = window.getSelection()?.toString().trim();
        return selected || "";
      }
      const clone = document.body?.cloneNode(true);
      if (!clone) {
        return document.title || "";
      }
      clone.querySelectorAll("script, style, noscript, nav, footer, iframe").forEach((node) => {
        node.remove();
      });
      return (clone.textContent || "").replace(/\s+/g, " ").trim();
    },
    args: [mode],
  });
  return String(result || "");
}

async function scanText(text) {
  const cleaned = String(text || "").trim();
  if (!cleaned) {
    throw new Error("No text found to scan.");
  }
  const config = await loadConfig();
  const maxChars = 120000;
  const payload = cleaned.length > maxChars ? cleaned.slice(0, maxChars) : cleaned;
  const truncated = cleaned.length > maxChars;

  const [pii, integrity] = await Promise.all([
    detectPii(config, payload),
    analyzeIntegrity(config, payload),
  ]);

  return {
    truncated,
    scannedChars: payload.length,
    pii,
    integrity,
  };
}
