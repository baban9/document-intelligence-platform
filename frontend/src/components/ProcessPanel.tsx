import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  fetchPiiEntities,
  processDocument,
  type ProcessResult,
  type ProgressUpdate,
} from "../api/client";
import { EntityChipPicker, summarizeSelection } from "./EntityChipPicker";
import { ProcessResultView } from "./ProcessResultView";
import { ProgressBanner } from "./ProgressBanner";
import { toEntityOptions } from "../lib/entityLabels";

const VERTICAL_PRESETS = ["", "general", "financial", "healthcare", "legal"];

function titleCaseStatus(status: string): string {
  return status.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

export function ProcessPanel() {
  const [entityIds, setEntityIds] = useState<string[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [vertical, setVertical] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [sentences, setSentences] = useState(3);
  const [includeSummary, setIncludeSummary] = useState(true);
  const [includePii, setIncludePii] = useState(true);
  const [includeText, setIncludeText] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<ProgressUpdate | null>(null);
  const [result, setResult] = useState<ProcessResult | null>(null);

  const options = useMemo(() => toEntityOptions(entityIds), [entityIds]);
  const presetActive = Boolean(vertical.trim());

  useEffect(() => {
    fetchPiiEntities()
      .then((ids) => {
        setEntityIds(ids);
        setSelectedIds(ids.slice(0, 8));
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("Upload a document first.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    setProgress({ jobStatus: "queued", message: "Submitting document...", progress: 0 });
    try {
      const payload = await processDocument(
        file,
        {
          sentences,
          includeSummary,
          includePii,
          includeText,
          vertical: presetActive ? vertical : undefined,
          entities: presetActive ? undefined : selectedIds,
        },
        setProgress,
      );
      setResult(payload);
      setProgress({ jobStatus: "completed", message: "Results ready.", progress: 100 });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Processing failed.");
      setProgress(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel">
      <header className="panel-header">
        <h1>Process pipeline</h1>
        <p>Extract, classify, summarize, and scan for PII in one job.</p>
      </header>

      <form className="process-form" onSubmit={onSubmit}>
        <label className="field">
          <span>Document upload</span>
          <input
            type="file"
            accept=".pdf,.docx,.xlsx,.pptx,.csv,.txt,.md,.json"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>

        <div className="field-row">
          <label className="field">
            <span>Summary sentences ({sentences})</span>
            <input
              type="range"
              min={1}
              max={10}
              value={sentences}
              onChange={(event) => setSentences(Number(event.target.value))}
            />
          </label>

          <label className="field">
            <span>PII vertical preset</span>
            <select value={vertical} onChange={(event) => setVertical(event.target.value)}>
              {VERTICAL_PRESETS.map((preset) => (
                <option key={preset || "none"} value={preset}>
                  {preset ? titleCaseStatus(preset) : "None (manual selection)"}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="toggle-row">
          <label>
            <input
              type="checkbox"
              checked={includeSummary}
              onChange={(event) => setIncludeSummary(event.target.checked)}
            />
            Include summary
          </label>
          <label>
            <input
              type="checkbox"
              checked={includePii}
              onChange={(event) => setIncludePii(event.target.checked)}
            />
            Include PII scan
          </label>
          <label>
            <input
              type="checkbox"
              checked={includeText}
              onChange={(event) => setIncludeText(event.target.checked)}
            />
            Include extracted text
          </label>
        </div>

        <p className="selection-summary">
          {summarizeSelection(selectedIds, options, vertical)}
        </p>

        <EntityChipPicker
          options={options}
          selectedIds={selectedIds}
          disabled={presetActive}
          onChange={setSelectedIds}
        />

        <button type="submit" className="primary-button" disabled={loading}>
          {loading ? "Processing..." : "Process document"}
        </button>
      </form>

      {progress && loading ? <ProgressBanner progress={progress} /> : null}

      {error ? <p className="error-banner">{error}</p> : null}

      {result ? (
        <div className="result-card">
          <ProcessResultView result={result} />
        </div>
      ) : null}
    </section>
  );
}
