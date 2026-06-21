import { useEffect, useState } from "react";
import { fetchHealth } from "./api/client";
import { AnnotatePanel } from "./components/AnnotatePanel";
import { DocumentToolsPanel } from "./components/DocumentToolsPanel";
import { IntegrityPanel } from "./components/IntegrityPanel";
import { ProcessPanel } from "./components/ProcessPanel";
import { SensitivePdfPanel } from "./components/SensitivePdfPanel";
import { StructurePdfPanel } from "./components/StructurePdfPanel";
import { SummarizePanel } from "./components/SummarizePanel";

type NavId =
  | "process"
  | "integrity"
  | "tools"
  | "annotate"
  | "sensitive"
  | "structure"
  | "summarize";

const NAV_SECTIONS: { title: string; items: { id: NavId; label: string }[] }[] = [
  {
    title: "Documents",
    items: [
      { id: "process", label: "Process pipeline" },
      { id: "integrity", label: "Integrity analysis" },
      { id: "tools", label: "Document tools" },
    ],
  },
  {
    title: "PDF",
    items: [
      { id: "annotate", label: "PDF annotate" },
      { id: "sensitive", label: "Sensitive PDF" },
      { id: "structure", label: "Structure PDF" },
    ],
  },
  {
    title: "Text",
    items: [{ id: "summarize", label: "Summarize text" }],
  },
];

export function AppShell() {
  const [health, setHealth] = useState("checking");
  const [activeNav, setActiveNav] = useState<NavId>("process");

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealth("offline"));
  }, []);

  function renderPanel() {
    switch (activeNav) {
      case "process":
        return <ProcessPanel />;
      case "integrity":
        return <IntegrityPanel />;
      case "tools":
        return <DocumentToolsPanel />;
      case "annotate":
        return <AnnotatePanel />;
      case "sensitive":
        return <SensitivePdfPanel />;
      case "structure":
        return <StructurePdfPanel />;
      case "summarize":
        return <SummarizePanel />;
      default:
        return <ProcessPanel />;
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">Document Intelligence</div>
        <p className="status">API health: {health}</p>
        <nav>
          {NAV_SECTIONS.map((section) => (
            <div key={section.title} className="nav-section">
              <p className="nav-section-title">{section.title}</p>
              {section.items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`nav-button ${activeNav === item.id ? "nav-button-active" : ""}`}
                  aria-current={activeNav === item.id ? "page" : undefined}
                  onClick={() => setActiveNav(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          ))}
        </nav>
      </aside>
      <main className="main-panel">{renderPanel()}</main>
    </div>
  );
}
