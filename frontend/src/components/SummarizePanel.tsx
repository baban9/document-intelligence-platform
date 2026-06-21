import { useState, type FormEvent } from "react";
import { summarizeText } from "../api/client";
import { JsonResultView } from "./JsonResultView";

export function SummarizePanel() {
  const [text, setText] = useState("");
  const [sentences, setSentences] = useState(3);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<unknown>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!text.trim()) {
      setError("Provide text to summarize.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const payload = await summarizeText(text.trim(), sentences);
      setResult(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Summarization failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel">
      <header className="panel-header">
        <h1>Summarize text</h1>
        <p>Extractive summary from pasted plain text.</p>
      </header>

      <form className="process-form" onSubmit={onSubmit}>
        <label className="field">
          <span>Source text</span>
          <textarea
            className="text-area"
            rows={10}
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
        </label>

        <label className="field">
          <span>Sentences ({sentences})</span>
          <input
            type="range"
            min={1}
            max={10}
            value={sentences}
            onChange={(event) => setSentences(Number(event.target.value))}
          />
        </label>

        <button type="submit" className="primary-button" disabled={loading}>
          {loading ? "Summarizing..." : "Summarize"}
        </button>
      </form>

      {error ? <p className="error-banner">{error}</p> : null}

      {result !== null ? (
        <div className="result-card">
          <JsonResultView value={result} />
        </div>
      ) : null}
    </section>
  );
}
