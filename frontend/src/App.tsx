import { useEffect, useState } from "react";
import { fetchHealth } from "./api/client";
import { AnnotatePanel } from "./components/AnnotatePanel";
import { DocumentToolsPanel } from "./components/DocumentToolsPanel";
import { IntegrityPanel } from "./components/IntegrityPanel";
import { PdfEditorPanel } from "./components/PdfEditorPanel";
import { ProcessPanel } from "./components/ProcessPanel";
import { SensitivePdfPanel } from "./components/SensitivePdfPanel";
import { StructurePdfPanel } from "./components/StructurePdfPanel";
import { SettingsPanel } from "./components/SettingsPanel";
import { SummarizePanel } from "./components/SummarizePanel";
import { TenantSelector } from "./components/TenantSelector";
import { UnderstandPanel } from "./components/UnderstandPanel";
import { useAuth } from "./context/AuthContext";

type NavId =
  | "process"
  | "integrity"
  | "tools"
  | "annotate"
  | "sensitive"
  | "structure"
  | "editor"
  | "summarize"
  | "understand"
  | "settings";

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
      { id: "editor", label: "AI PDF editor" },
    ],
  },
  {
    title: "Text",
    items: [
      { id: "understand", label: "Understand document" },
      { id: "summarize", label: "Summarize text" },
    ],
  },
  {
    title: "Platform",
    items: [{ id: "settings", label: "Settings" }],
  },
];

export function AppShell() {
  const [health, setHealth] = useState("checking");
  const [activeNav, setActiveNav] = useState<NavId>("process");
  const { config, user, loading: authLoading, loginWithOidc, logout } = useAuth();

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
      case "editor":
        return <PdfEditorPanel />;
      case "summarize":
        return <SummarizePanel />;
      case "understand":
        return <UnderstandPanel />;
      case "settings":
        return <SettingsPanel />;
      default:
        return <ProcessPanel />;
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">Document Intelligence</div>
        <TenantSelector />
        <div className="auth-panel">
          {authLoading ? <p className="result-muted">Auth...</p> : null}
          {!authLoading && user?.authenticated ? (
            <p className="auth-user">
              Signed in{user.email ? `: ${user.email}` : user.subject ? `: ${user.subject}` : ""}
            </p>
          ) : null}
          {!authLoading && config?.oidc_enabled && !user?.authenticated ? (
            <button type="button" className="secondary-button auth-login-button" onClick={loginWithOidc}>
              Sign in with OIDC
            </button>
          ) : null}
          {!authLoading && user?.authenticated && config?.oidc_enabled ? (
            <button type="button" className="secondary-button auth-login-button" onClick={logout}>
              Sign out
            </button>
          ) : null}
        </div>
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
