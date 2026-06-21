import { useEffect, useMemo, useState } from "react";
import {
  classifyDocument,
  compareDocuments,
  detectPiiDocument,
  extractDocumentText,
  fetchPiiEntities,
  identifyDocument,
  summarizeDocument,
  type ProgressUpdate,
} from "../api/client";
import { toEntityOptions } from "../lib/entityLabels";
import { EntityChipPicker } from "./EntityChipPicker";
import { JsonResultView } from "./JsonResultView";
import { ProgressBanner } from "./ProgressBanner";

const OFFICE_TYPES = ".pdf,.docx,.xlsx,.pptx,.csv,.txt,.md,.json";

type ToolAction =
  | "identify"
  | "extract"
  | "classify"
  | "summarize"
  | "detect-pii"
  | "compare";

export function DocumentToolsPanel() {
  const [file, setFile] = useState<File | null>(null);
  const [compareA, setCompareA] = useState<File | null>(null);
  const [compareB, setCompareB] = useState<File | null>(null);
  const [sentences, setSentences] = useState(3);
  const [entityIds, setEntityIds] = useState<string[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeAction, setActiveAction] = useState<ToolAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<ProgressUpdate | null>(null);
  const [result, setResult] = useState<unknown>(null);

  const options = useMemo(() => toEntityOptions(entityIds), [entityIds]);

  useEffect(() => {
    fetchPiiEntities()
      .then((ids) => {
        setEntityIds(ids);
        setSelectedIds(ids.slice(0, 8));
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  async function runAction(action: ToolAction) {
    setActiveAction(action);
    setLoading(true);
    setError(null);
    setResult(null);
    setProgress({ jobStatus: "queued", message: "Running tool...", progress: 0 });
    try {
      let payload: unknown;
      switch (action) {
        case "identify":
          if (!file) throw new Error("Upload a document first.");
          payload = await identifyDocument(file);
          break;
        case "extract":
          if (!file) throw new Error("Upload a document first.");
          payload = await extractDocumentText(file, setProgress);
          break;
        case "classify":
          if (!file) throw new Error("Upload a document first.");
          payload = await classifyDocument(file, setProgress);
          break;
        case "summarize":
          if (!file) throw new Error("Upload a document first.");
          payload = await summarizeDocument(file, sentences, setProgress);
          break;
        case "detect-pii":
          if (!file) throw new Error("Upload a document first.");
          payload = await detectPiiDocument(file, selectedIds, setProgress);
          break;
        case "compare":
          if (!compareA || !compareB) throw new Error("Upload two documents to compare.");
          payload = await compareDocuments(compareA, compareB, setProgress);
          break;
      }
      setResult(payload);
      setProgress({ jobStatus: "completed", message: "Results ready.", progress: 100 });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tool request failed.");
      setProgress(null);
    } finally {
      setLoading(false);
      setActiveAction(null);
    }
  }

  return (
    <section className="panel">
      <header className="panel-header">
        <h1>Document tools</h1>
        <p>Identify, extract, classify, summarize, scan for PII, and compare documents.</p>
      </header>

      <div className="process-form">
        <label className="field">
          <span>Document upload</span>
          <input
            type="file"
            accept={OFFICE_TYPES}
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>

        <div className="field-row">
          <label className="field">
            <span>Compare document A</span>
            <input
              type="file"
              accept={OFFICE_TYPES}
              onChange={(event) => setCompareA(event.target.files?.[0] ?? null)}
            />
          </label>
          <label className="field">
            <span>Compare document B</span>
            <input
              type="file"
              accept={OFFICE_TYPES}
              onChange={(event) => setCompareB(event.target.files?.[0] ?? null)}
            />
          </label>
        </div>

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

        <EntityChipPicker options={options} selectedIds={selectedIds} onChange={setSelectedIds} />

        <div className="tool-button-row">
          <button type="button" className="secondary-button" disabled={loading} onClick={() => runAction("identify")}>
            Identify
          </button>
          <button type="button" className="secondary-button" disabled={loading} onClick={() => runAction("extract")}>
            Extract text
          </button>
          <button type="button" className="secondary-button" disabled={loading} onClick={() => runAction("classify")}>
            Classify
          </button>
          <button type="button" className="secondary-button" disabled={loading} onClick={() => runAction("summarize")}>
            Summarize file
          </button>
          <button type="button" className="secondary-button" disabled={loading} onClick={() => runAction("detect-pii")}>
            Detect PII
          </button>
          <button type="button" className="secondary-button" disabled={loading} onClick={() => runAction("compare")}>
            Compare files
          </button>
        </div>
      </div>

      {progress && loading ? (
        <ProgressBanner
          progress={{
            ...progress,
            message: activeAction ? `${progress.message} (${activeAction})` : progress.message,
          }}
        />
      ) : null}
      {error ? <p className="error-banner">{error}</p> : null}

      {result !== null ? (
        <div className="result-card">
          <JsonResultView value={result} />
        </div>
      ) : null}
    </section>
  );
}
