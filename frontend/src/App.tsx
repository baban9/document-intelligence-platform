import { useEffect, useState } from "react";
import { fetchHealth } from "./api/client";
import { ProcessPanel } from "./components/ProcessPanel";

const NAV_ITEMS = [
  { id: "process", label: "Process pipeline", active: true },
  { id: "integrity", label: "Integrity analysis", active: false },
  { id: "tools", label: "Document tools", active: false },
  { id: "annotate", label: "PDF annotate", active: false },
  { id: "sensitive", label: "Sensitive PDF", active: false },
  { id: "structure", label: "Structure PDF", active: false },
  { id: "summarize", label: "Summarize text", active: false },
];

export function AppShell() {
  const [health, setHealth] = useState("checking");

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealth("offline"));
  }, []);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">Document Intelligence</div>
        <p className="status">API health: {health}</p>
        <nav>
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`nav-button ${item.active ? "nav-button-active" : ""}`}
              disabled={!item.active}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <p className="sidebar-note">Other panels will migrate from Gradio next.</p>
      </aside>
      <main className="main-panel">
        <ProcessPanel />
      </main>
    </div>
  );
}
