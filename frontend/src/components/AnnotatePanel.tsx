import { useEffect, useState, type FormEvent } from "react";
import { annotatePdf, downloadJobPdf, type ProgressUpdate } from "../api/client";
import { AnnotatePlanView } from "./AnnotatePlanView";
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

type InputMode = "requirements" | "manual";

export function AnnotatePanel() {
  const [file, setFile] = useState<File | null>(null);
  const [inputMode, setInputMode] = useState<InputMode>("requirements");
  const [requirements, setRequirements] = useState("");
  const [pattern, setPattern] = useState("");
  const [action, setAction] = useState("Highlight");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<ProgressUpdate | null>(null);
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pdfName, setPdfName] = useState("annotated.pdf");

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
    if (inputMode === "requirements" && !requirements.trim()) {
      setError("Describe what to find or redact in the requirements box.");
      return;
    }
    if (inputMode === "manual" && !pattern.trim()) {
      setError("Enter a manual regex pattern.");
      return;
    }

    setLoading(true);
    setError(null);
    setReport(null);
    clearPdf();
    setProgress({
      jobStatus: "queued",
      message:
        inputMode === "requirements"
          ? "Planning patterns with LLM..."
          : "Annotating PDF...",
      progress: 0,
    });

    try {
      const payload = await annotatePdf(
        file,
        {
          action,
          requirements: inputMode === "requirements" ? requirements.trim() : undefined,
          pattern: inputMode === "manual" ? pattern.trim() : undefined,
        },
        setProgress,
      );
      const downloaded = await downloadJobPdf(payload, "annotated.pdf");
      setPdfUrl(downloaded.blobUrl);
      setPdfName(downloaded.filename);
      setReport(payload);
      setProgress({ jobStatus: "completed", message: "Annotated PDF ready.", progress: 100 });
    } catch (err) {
      setError(err instanceof Error ? err.message : "PDF annotation failed.");
      setProgress(null);
    } finally {
      setLoading(false);
    }
  }

  const matches = report?.matches;

  return (
    <section className="panel">
      <header className="panel-header">
        <h1>PDF annotate</h1>
        <p>
          Describe what to highlight or redact in plain language. The LLM reads your PDF sample,
          builds search patterns, then runs annotation on the uploaded file. You can still use a
          manual regex pattern in advanced mode.
        </p>
      </header>

      <form className="process-form" onSubmit={onSubmit}>
        <label className="field">
          <span>PDF upload</span>
          <input type="file" accept=".pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        </label>

        <div className="toggle-row">
          <label>
            <input
              type="radio"
              name="annotate-input-mode"
              checked={inputMode === "requirements"}
              onChange={() => setInputMode("requirements")}
            />
            AI requirements
          </label>
          <label>
            <input
              type="radio"
              name="annotate-input-mode"
              checked={inputMode === "manual"}
              onChange={() => setInputMode("manual")}
            />
            Manual regex
          </label>
        </div>

        {inputMode === "requirements" ? (
          <label className="field">
            <span>Annotation requirements</span>
            <textarea
              className="text-area"
              rows={6}
              value={requirements}
              placeholder="Example: Highlight every invoice number and redact customer IDs that look like XYZ followed by three digits."
              onChange={(event) => setRequirements(event.target.value)}
            />
          </label>
        ) : (
          <label className="field">
            <span>Regex pattern</span>
            <input
              type="text"
              value={pattern}
              placeholder="ABC123|CONFIDENTIAL"
              onChange={(event) => setPattern(event.target.value)}
            />
          </label>
        )}

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

        <button type="submit" className="primary-button" disabled={loading}>
          {loading
            ? inputMode === "requirements"
              ? "Planning and annotating..."
              : "Annotating..."
            : "Annotate PDF"}
        </button>
      </form>

      {progress && loading ? <ProgressBanner progress={progress} /> : null}
      {error ? <p className="error-banner">{error}</p> : null}

      {pdfUrl ? (
        <div className="result-card">
          <PdfOutputCard
            downloadUrl={pdfUrl}
            filename={pdfName}
            status={`Annotated PDF ready. Matches: ${String(matches ?? "?")}`}
            onClear={clearPdf}
          />
        </div>
      ) : null}

      {report ? (
        <div className="result-card">
          <AnnotatePlanView report={report} />
          <JsonResultView value={report} />
        </div>
      ) : null}
    </section>
  );
}
