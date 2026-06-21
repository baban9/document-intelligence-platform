import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  detectSensitivePdf,
  downloadJobPdf,
  fetchPiiEntities,
  type ProgressUpdate,
} from "../api/client";
import { toEntityOptions } from "../lib/entityLabels";
import { EntityChipPicker, summarizeSelection } from "./EntityChipPicker";
import { JsonResultView } from "./JsonResultView";
import { PdfOutputCard } from "./PdfOutputCard";
import { ProgressBanner } from "./ProgressBanner";

const PDF_ACTIONS = [
  "Highlight",
  "Redact",
  "Frame",
  "Underline",
  "Squiggly",
  "Strikeout",
];

export function SensitivePdfPanel() {
  const [file, setFile] = useState<File | null>(null);
  const [action, setAction] = useState("Highlight");
  const [forceOcr, setForceOcr] = useState(false);
  const [addTextLayer, setAddTextLayer] = useState(true);
  const [entityIds, setEntityIds] = useState<string[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<ProgressUpdate | null>(null);
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pdfName, setPdfName] = useState("sensitive.pdf");

  const options = useMemo(() => toEntityOptions(entityIds), [entityIds]);

  useEffect(() => {
    fetchPiiEntities()
      .then((ids) => {
        setEntityIds(ids);
        setSelectedIds(ids.slice(0, 8));
      })
      .catch((err: Error) => setError(err.message));
  }, []);

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
    setProgress({ jobStatus: "queued", message: "Scanning PDF...", progress: 0 });
    try {
      const payload = await detectSensitivePdf(
        file,
        { action, entities: selectedIds, forceOcr, addTextLayer },
        setProgress,
      );
      const downloaded = await downloadJobPdf(payload, "sensitive.pdf");
      setPdfUrl(downloaded.blobUrl);
      setPdfName(downloaded.filename);
      const findings = Array.isArray(payload.findings) ? payload.findings.slice(0, 20) : [];
      setReport({
        matches: payload.matches,
        finding_count: payload.finding_count,
        ocr_pages: payload.ocr_pages,
        findings,
      });
      setProgress({ jobStatus: "completed", message: "Sensitive PDF ready.", progress: 100 });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sensitive PDF scan failed.");
      setProgress(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel">
      <header className="panel-header">
        <h1>Sensitive PDF</h1>
        <p>OCR plus Presidio for scanned PDFs. Choose which PII types to scan for.</p>
      </header>

      <form className="process-form" onSubmit={onSubmit}>
        <label className="field">
          <span>PDF upload</span>
          <input type="file" accept=".pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        </label>

        <p className="selection-summary">{summarizeSelection(selectedIds, options)}</p>
        <EntityChipPicker options={options} selectedIds={selectedIds} onChange={setSelectedIds} />

        <div className="field-row">
          <label className="field">
            <span>Action</span>
            <select value={action} onChange={(event) => setAction(event.target.value)}>
              {PDF_ACTIONS.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="toggle-row">
          <label>
            <input
              type="checkbox"
              checked={forceOcr}
              onChange={(event) => setForceOcr(event.target.checked)}
            />
            Force OCR on all pages
          </label>
          <label>
            <input
              type="checkbox"
              checked={addTextLayer}
              onChange={(event) => setAddTextLayer(event.target.checked)}
            />
            Add searchable text layer
          </label>
        </div>

        <button type="submit" className="primary-button" disabled={loading}>
          {loading ? "Scanning..." : "Detect and annotate"}
        </button>
      </form>

      {progress && loading ? <ProgressBanner progress={progress} /> : null}
      {error ? <p className="error-banner">{error}</p> : null}

      {pdfUrl ? (
        <div className="result-card">
          <PdfOutputCard
            downloadUrl={pdfUrl}
            filename={pdfName}
            status={`Processed PDF ready. Findings: ${String(report?.finding_count ?? "?")}`}
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
