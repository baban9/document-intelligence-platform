import { useEffect, useState, type FormEvent } from "react";
import { downloadJobPdf, structurePdf, type ProgressUpdate } from "../api/client";
import { JsonResultView } from "./JsonResultView";
import { PdfOutputCard } from "./PdfOutputCard";
import { ProgressBanner } from "./ProgressBanner";

export function StructurePdfPanel() {
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState("curate");
  const [forceOcr, setForceOcr] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<ProgressUpdate | null>(null);
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pdfName, setPdfName] = useState("structured.pdf");

  useEffect(() => {
    return () => {
      if (pdfUrl) {
        URL.revokeObjectURL(pdfUrl);
      }
    };
  }, [pdfUrl]);

  function clearPdf() {
    if (pdfUrl) {
      URL.revokeObjectURL(pdfUrl);
    }
    setPdfUrl(null);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("Upload a PDF file.");
      return;
    }
    setLoading(true);
    setError(null);
    setReport(null);
    clearPdf();
    setProgress({ jobStatus: "queued", message: "Structuring PDF...", progress: 0 });
    try {
      const payload = await structurePdf(file, mode, forceOcr, setProgress);
      const downloaded = await downloadJobPdf(payload, "structured.pdf");
      setPdfUrl(downloaded.blobUrl);
      setPdfName(downloaded.filename);
      setReport({
        mode: payload.mode,
        document_title: payload.document_title,
        pages_processed: payload.pages_processed,
        ocr_pages: payload.ocr_pages,
      });
      setProgress({ jobStatus: "completed", message: "Structured PDF ready.", progress: 100 });
    } catch (err) {
      setError(err instanceof Error ? err.message : "PDF structuring failed.");
      setProgress(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel">
      <header className="panel-header">
        <h1>Structure PDF</h1>
        <p>
          Convert scanned PDFs into a curated digital PDF. Set DOCINTEL_LLM_PROVIDER on the API
          server (default: ollama).
        </p>
      </header>

      <form className="process-form" onSubmit={onSubmit}>
        <label className="field">
          <span>PDF upload</span>
          <input type="file" accept=".pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        </label>

        <div className="field-row">
          <label className="field">
            <span>Output mode</span>
            <select value={mode} onChange={(event) => setMode(event.target.value)}>
              <option value="curate">Curate</option>
              <option value="searchable">Searchable</option>
            </select>
          </label>
          <label className="field toggle-field">
            <span>Force OCR on all pages</span>
            <input
              type="checkbox"
              checked={forceOcr}
              onChange={(event) => setForceOcr(event.target.checked)}
            />
          </label>
        </div>

        <button type="submit" className="primary-button" disabled={loading}>
          {loading ? "Structuring..." : "Structure PDF"}
        </button>
      </form>

      {progress && loading ? <ProgressBanner progress={progress} /> : null}
      {error ? <p className="error-banner">{error}</p> : null}

      {pdfUrl ? (
        <div className="result-card">
          <PdfOutputCard
            downloadUrl={pdfUrl}
            filename={pdfName}
            status="Structured PDF ready."
            onClear={clearPdf}
          />
        </div>
      ) : null}

      {report ? (
        <div className="result-card">
          <JsonResultView value={report} />
        </div>
      ) : null}
    </section>
  );
}
