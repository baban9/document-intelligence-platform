import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  applyPdfEditorEdit,
  createPdfEditorSession,
  downloadEditorPdf,
  fetchPdfEditorPage,
  type PdfEditorPageState,
  type PdfEditorSession,
} from "../api/client";
import { PdfOutputCard } from "./PdfOutputCard";

export function PdfEditorPanel() {
  const [file, setFile] = useState<File | null>(null);
  const [session, setSession] = useState<PdfEditorSession | null>(null);
  const [pageIndex, setPageIndex] = useState(0);
  const [pageState, setPageState] = useState<PdfEditorPageState | null>(null);
  const [instruction, setInstruction] = useState("");
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastChange, setLastChange] = useState<string | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pdfName, setPdfName] = useState("edited.pdf");
  const [previewNonce, setPreviewNonce] = useState(0);

  const previewSrc = useMemo(() => {
    if (!pageState?.preview_url) {
      return null;
    }
    const base = import.meta.env.VITE_API_BASE ?? "";
    return `${base}${pageState.preview_url}?t=${previewNonce}`;
  }, [pageState?.preview_url, previewNonce]);

  useEffect(() => {
    return () => {
      if (pdfUrl) {
        URL.revokeObjectURL(pdfUrl);
      }
    };
  }, [pdfUrl]);

  async function loadPage(nextSession: PdfEditorSession, nextPage: number) {
    setPageLoading(true);
    setError(null);
    try {
      const payload = await fetchPdfEditorPage(nextSession.session_id, nextPage);
      setPageState(payload);
      setPageIndex(nextPage);
      setPreviewNonce(Date.now());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load page preview.");
    } finally {
      setPageLoading(false);
    }
  }

  async function onStartSession(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("Upload a PDF to start editing.");
      return;
    }
    setLoading(true);
    setError(null);
    setSession(null);
    setPageState(null);
    setLastChange(null);
    if (pdfUrl) {
      URL.revokeObjectURL(pdfUrl);
      setPdfUrl(null);
    }
    try {
      const created = await createPdfEditorSession(file);
      setSession(created);
      await loadPage(created, 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start PDF editor session.");
    } finally {
      setLoading(false);
    }
  }

  async function onApplyEdit(event: FormEvent) {
    event.preventDefault();
    if (!session || !instruction.trim()) {
      setError("Describe the edit you want on this page.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const payload = await applyPdfEditorEdit(session.session_id, pageIndex, instruction.trim());
      setPageState(payload);
      setLastChange(String(payload.changes_summary ?? "Page updated."));
      setInstruction("");
      setPreviewNonce(Date.now());
      setSession({
        ...session,
        pages_edited: Array.isArray(payload.pages_edited)
          ? payload.pages_edited.map(Number)
          : session.pages_edited,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Page edit failed.");
    } finally {
      setLoading(false);
    }
  }

  async function onDownload() {
    if (!session) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const downloaded = await downloadEditorPdf(session);
      if (pdfUrl) {
        URL.revokeObjectURL(pdfUrl);
      }
      setPdfUrl(downloaded.blobUrl);
      setPdfName(downloaded.filename);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Download failed.");
    } finally {
      setLoading(false);
    }
  }

  function goToPage(nextPage: number) {
    if (!session) {
      return;
    }
    void loadPage(session, nextPage);
  }

  const pageCount = session?.page_count ?? 0;
  const pagesEdited = session?.pages_edited ?? [];

  return (
    <section className="panel pdf-editor-panel">
      <header className="panel-header">
        <h1>AI PDF editor</h1>
        <p>
          Preview each page, describe edits in plain language, and download the updated PDF. Requires
          an LLM provider on the API server.
        </p>
      </header>

      {!session ? (
        <form className="process-form" onSubmit={onStartSession}>
          <label className="field">
            <span>PDF upload</span>
            <input type="file" accept=".pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          </label>
          <button type="submit" className="primary-button" disabled={loading}>
            {loading ? "Starting session..." : "Open PDF editor"}
          </button>
        </form>
      ) : (
        <div className="pdf-editor-layout">
          <div className="pdf-editor-preview-pane">
            <div className="pdf-editor-toolbar">
              <button
                type="button"
                className="secondary-button"
                disabled={pageLoading || pageIndex <= 0}
                onClick={() => goToPage(pageIndex - 1)}
              >
                Previous page
              </button>
              <strong>
                Page {pageIndex + 1} of {pageCount}
              </strong>
              <button
                type="button"
                className="secondary-button"
                disabled={pageLoading || pageIndex >= pageCount - 1}
                onClick={() => goToPage(pageIndex + 1)}
              >
                Next page
              </button>
            </div>

            <div className="pdf-editor-preview-frame">
              {pageLoading ? <p className="result-muted">Loading preview...</p> : null}
              {!pageLoading && previewSrc ? (
                <img src={previewSrc} alt={`Page ${pageIndex + 1} preview`} className="pdf-editor-preview-image" />
              ) : null}
            </div>

            {pageState?.edit_history?.length ? (
              <details className="pdf-editor-text-details" open>
                <summary>Edit history ({pageState.edit_history.length})</summary>
                <ol className="pdf-editor-history-list">
                  {pageState.edit_history.map((entry, index) => (
                    <li key={`${index}-${entry.instruction}`}>
                      <strong>{entry.instruction}</strong>
                      <span className="result-muted"> {entry.changes_summary}</span>
                    </li>
                  ))}
                </ol>
              </details>
            ) : null}

            {pageState?.text ? (
              <details className="pdf-editor-text-details">
                <summary>Page text</summary>
                <pre className="result-text-preview">{pageState.text}</pre>
              </details>
            ) : null}
          </div>

          <div className="pdf-editor-controls">
            <p className="result-muted">
              Edited pages: {pagesEdited.length ? pagesEdited.map((page) => page + 1).join(", ") : "none yet"}
            </p>

            <form className="process-form" onSubmit={onApplyEdit}>
              <label className="field">
                <span>What should change on this page?</span>
                <textarea
                  className="text-area"
                  rows={5}
                  value={instruction}
                  onChange={(event) => setInstruction(event.target.value)}
                  placeholder='Example: Change the invoice date to 15 March 2026 and fix the typo in the customer name.'
                />
              </label>
              <button type="submit" className="primary-button" disabled={loading || pageLoading}>
                {loading ? "Applying edit..." : "Apply edit to this page"}
              </button>
            </form>

            {lastChange ? <p className="success-banner">{lastChange}</p> : null}

            <button type="button" className="secondary-button" disabled={loading} onClick={() => void onDownload()}>
              Download edited PDF
            </button>
          </div>
        </div>
      )}

      {error ? <p className="error-banner">{error}</p> : null}

      {pdfUrl ? (
        <div className="result-card">
          <PdfOutputCard
            downloadUrl={pdfUrl}
            filename={pdfName}
            status="Edited PDF ready."
            onClear={() => {
              URL.revokeObjectURL(pdfUrl);
              setPdfUrl(null);
            }}
          />
        </div>
      ) : null}
    </section>
  );
}
