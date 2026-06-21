import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AppShell as App } from "./App";
import { TenantProvider } from "./context/TenantContext";
import "./styles/app.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <TenantProvider>
      <App />
    </TenantProvider>
  </StrictMode>,
);
