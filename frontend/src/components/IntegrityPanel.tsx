import { useEffect, useState, type FormEvent } from "react";
import {
  analyzeIntegrity,
  type ProgressUpdate,
} from "../api/client";
import { INTEGRITY_CHECKS } from "../lib/integrity";
import { IntegrityResultView } from "./IntegrityResultView";
import { ProgressBanner } from "./ProgressBanner";

const OFFICE_TYPES = ".pdf,.docx,.xlsx,.pptx,.csv,.txt,.md,.json";

export function IntegrityPanel() {
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [checks, setChecks] = useState<string[]>([...INTEGRITY_CHECKS]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<ProgressUpdate | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  function toggleCheck(check: string) {
    setChecks((current) =>
      current.includes(check) ? current.filter((item) => item !== check) : [...current, check],
    );
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file && !text.trim()) {
      setError("Upload a document or paste text to analyze.");
      return;
    }
    if (!checks.length) {
      setError("Select at least one integrity check.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    setProgress({ jobStatus: "queued", message: "Submitting analysis...", progress: 0 });
    try {
      const payload = await analyzeIntegrity(
        { file: file ?? undefined, text: text.trim(), checks },
        setProgress,
      );
      setResult(payload);
      setProgress({ jobStatus: "completed", message: "Results ready.", progress: 100 });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Integrity analysis failed.");
      setProgress(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (file) {
      setText("");
    }
  }, [file]);

  return (
    <section className="panel">
      <header className="panel-header">
        <h1>Integrity analysis</h1>
        <p>
          Find placeholders, broken references, naming drift, number mismatches, and thin sections.
          Severity labels: [!] high, [~] medium, [.] low.
        </p>
      </header>

      <form className="process-form" onSubmit={onSubmit}>
        <label className="field">
          <span>Document upload</span>
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
            disabled={Boolean(file)}
            placeholder="Paste policy or contract text if you are not uploading a file."
            onChange={(event) => setText(event.target.value)}
          />
        </label>

        <fieldset className="check-fieldset">
          <legend>Checks to run</legend>
          <div className="toggle-row">
            {INTEGRITY_CHECKS.map((check) => (
              <label key={check}>
                <input
                  type="checkbox"
                  checked={checks.includes(check)}
                  onChange={() => toggleCheck(check)}
                />
                {check.replace(/_/g, " ")}
              </label>
            ))}
          </div>
        </fieldset>

        <button type="submit" className="primary-button" disabled={loading}>
          {loading ? "Analyzing..." : "Analyze integrity"}
        </button>
      </form>

      {progress && loading ? <ProgressBanner progress={progress} /> : null}
      {error ? <p className="error-banner">{error}</p> : null}

      {result ? (
        <div className="result-card">
          <IntegrityResultView result={result} />
        </div>
      ) : null}
    </section>
  );
}
