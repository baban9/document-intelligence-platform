import type { ProcessResult } from "../api/client";
import { formatEntityLabel } from "../lib/entityLabels";

type PiiFinding = {
  entity_type?: string;
  text?: string;
  score?: number;
  page?: number;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function percent(value: unknown): string {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "n/a";
}

function percentPrecise(value: unknown): string {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "n/a";
}

function titleCase(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function ProcessResultView({ result }: { result: ProcessResult }) {
  const extraction = asRecord(result.extraction);
  const classification = asRecord(result.classification);
  const summary = asRecord(result.summary);
  const pii = asRecord(result.pii);
  const findings = Array.isArray(pii?.findings) ? (pii.findings as PiiFinding[]) : [];

  const filename = String(result.filename || "Document");
  const category = String(classification?.category || "unknown");
  const confidence = percent(classification?.confidence);
  const metadata = asRecord(extraction?.metadata);
  const pageCount =
    Number(metadata?.page_count ?? 0) ||
    (Array.isArray(extraction?.segments) ? extraction.segments.length : 0) ||
    1;
  const piiCount = Number(pii?.finding_count ?? findings.length);
  const mimeType = String(extraction?.mime_type || "");

  const summarySentences = Array.isArray(summary?.sentences)
    ? summary.sentences.map(String)
    : summary?.summary
      ? [String(summary.summary)]
      : [];

  const scores = asRecord(classification?.scores);
  const scoreRows = scores
    ? Object.entries(scores).sort((a, b) => Number(b[1]) - Number(a[1]))
    : [];

  const textPreview =
    typeof extraction?.text_preview === "string"
      ? extraction.text_preview
      : typeof extraction?.analysis_sample === "string"
        ? extraction.analysis_sample
        : "";

  return (
    <div className="process-result">
      <header className="result-header">
        <h2>{filename}</h2>
        <div className="result-chips">
          <span className="result-chip">{titleCase(category)}</span>
          {mimeType ? <span className="result-chip">{mimeType}</span> : null}
        </div>
      </header>

      <div className="result-stats">
        <div className="result-stat">
          <div className="result-stat-value">{pageCount}</div>
          <div className="result-stat-label">Pages</div>
        </div>
        <div className="result-stat">
          <div className="result-stat-value">{piiCount}</div>
          <div className="result-stat-label">PII findings</div>
        </div>
        <div className="result-stat">
          <div className="result-stat-value">{confidence}</div>
          <div className="result-stat-label">Classification confidence</div>
        </div>
      </div>

      <section className="result-section">
        <h3>Summary</h3>
        {summarySentences.length ? (
          <ul className="result-list">
            {summarySentences.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        ) : (
          <p className="result-muted">Summary was not requested for this run.</p>
        )}
      </section>

      <section className="result-section">
        <h3>Classification</h3>
        <p>
          Primary category: <strong>{titleCase(category)}</strong> ({confidence} confidence)
        </p>
        {scoreRows.length ? (
          <table className="result-table">
            <thead>
              <tr>
                <th>Category</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              {scoreRows.map(([label, value]) => (
                <tr key={label}>
                  <td>{titleCase(label)}</td>
                  <td>{percentPrecise(value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </section>

      <section className="result-section">
        <h3>PII detected</h3>
        {findings.length ? (
          <table className="result-table">
            <thead>
              <tr>
                <th>Entity</th>
                <th>Value</th>
                <th>Score</th>
                <th>Page</th>
              </tr>
            </thead>
            <tbody>
              {findings.map((item, index) => (
                <tr key={`${item.entity_type}-${item.text}-${index}`}>
                  <td>{formatEntityLabel(String(item.entity_type || ""))}</td>
                  <td>{String(item.text || "")}</td>
                  <td>{percent(item.score)}</td>
                  <td>{typeof item.page === "number" ? item.page + 1 : "n/a"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="result-muted">
            {pii ? "No PII detected in this document." : "PII scan was not requested for this run."}
          </p>
        )}
      </section>

      {textPreview ? (
        <section className="result-section">
          <h3>Text preview</h3>
          <pre className="result-text-preview">{textPreview}</pre>
        </section>
      ) : null}
    </div>
  );
}
