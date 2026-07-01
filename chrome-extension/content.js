/** Highlights sensitive spans returned from a popup scan on the live page. */

const MARK_CLASS = "docintel-sensitive-mark";
const STYLE_ID = "docintel-highlight-style";

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "highlight-pii") {
    clearHighlights();
    const count = highlightFindings(message.findings || []);
    sendResponse({ ok: true, count });
    return false;
  }
  if (message.type === "clear-highlights") {
    clearHighlights();
    sendResponse({ ok: true });
    return false;
  }
  return false;
});

function ensureStyle() {
  if (document.getElementById(STYLE_ID)) {
    return;
  }
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    mark.${MARK_CLASS} {
      background: #fde68a;
      color: inherit;
      border-radius: 2px;
      padding: 0 1px;
    }
  `;
  document.head.appendChild(style);
}

function clearHighlights() {
  document.querySelectorAll(`mark.${MARK_CLASS}`).forEach((node) => {
    const parent = node.parentNode;
    if (!parent) {
      return;
    }
    parent.replaceChild(document.createTextNode(node.textContent || ""), node);
    parent.normalize();
  });
}

function highlightFindings(findings) {
  ensureStyle();
  let highlighted = 0;
  const seen = new Set();
  for (const finding of findings) {
    const text = String(finding.text || "").trim();
    if (!text || text.length < 3 || seen.has(text)) {
      continue;
    }
    seen.add(text);
    if (wrapFirstMatch(text)) {
      highlighted += 1;
    }
  }
  return highlighted;
}

function wrapFirstMatch(needle) {
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node = walker.nextNode();
  while (node) {
    const content = node.textContent || "";
    const index = content.indexOf(needle);
    if (index >= 0 && node.parentElement && !node.parentElement.closest(`mark.${MARK_CLASS}`)) {
      const before = content.slice(0, index);
      const match = content.slice(index, index + needle.length);
      const after = content.slice(index + needle.length);
      const parent = node.parentNode;
      if (!parent) {
        return false;
      }
      const mark = document.createElement("mark");
      mark.className = MARK_CLASS;
      mark.textContent = match;
      const fragment = document.createDocumentFragment();
      if (before) {
        fragment.appendChild(document.createTextNode(before));
      }
      fragment.appendChild(mark);
      if (after) {
        fragment.appendChild(document.createTextNode(after));
      }
      parent.replaceChild(fragment, node);
      return true;
    }
    node = walker.nextNode();
  }
  return false;
}
