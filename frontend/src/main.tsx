import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AppShell as App } from "./App";
import "./styles/app.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
