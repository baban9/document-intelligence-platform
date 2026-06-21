import { useState, type FormEvent } from "react";
import { understandDocument, understandText } from "../api/client";
import { UnderstandResultView } from "./UnderstandResultView";

const OFFICE_TYPES = ".pdf,.docx,.xlsx,.pptx,.csv,.txt,.md,.json";

export function UnderstandPanel() {
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [sentences, setSentences] = useState(3);
  const [includeSummary, setIncludeSummary] = useState(true);
  const [includePii, setIncludePii] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file && !text.trim()) {
      setError("Upload a document or paste text to understand.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const options = { sentences, includeSummary, includePii };
      const payload = file
        ? await understandDocument(file, options)
        : await understandText(text.trim(), options);
      setResult(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Document understanding failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel">
      <header className="panel-header">
        <h1>Understand the document</h1>
        <p>Quick comprehension report: document type, summary, and PII snapshot.</p>
      </header>

      <form className="process-form" onSubmit={onSubmit}>
        <label className="field">
          <span>Document upload (optional)</span>
          <input
            type="file"
            accept={OFFICE_TYPES}
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>

        <label className="field">
          <span>Or paste text</span>
          <textarea
            className="text-area"
            rows={8}
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Paste policy text, email content, or meeting notes..."
          />
        </label>

        <label className="field">
          <span>Summary sentences ({sentences})</span>
          <input
            type="range"
            min={1}
            max={8}
            value={sentences}
            onChange={(event) => setSentences(Number(event.target.value))}
          />
        </label>

        <div className="field-row">
          <label className="field toggle-field">
            <span>Include summary</span>
            <input
              type="checkbox"
              checked={includeSummary}
              onChange={(event) => setIncludeSummary(event.target.checked)}
            />
          </label>
          <label className="field toggle-field">
            <span>Include PII snapshot</span>
            <input
              type="checkbox"
              checked={includePii}
              onChange={(event) => setIncludePii(event.target.checked)}
            />
          </label>
        </div>

        <button type="submit" className="primary-button" disabled={loading}>
          {loading ? "Analyzing..." : "Understand document"}
        </button>
      </form>

      {error ? <p className="error-banner">{error}</p> : null}

      {result ? (
        <div className="result-card">
          <UnderstandResultView result={result} />
        </div>
      ) : null}
    </section>
  );
}
