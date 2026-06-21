type JsonRecord = Record<string, unknown>;

function asRecord(value: unknown): JsonRecord | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as JsonRecord) : null;
}

function percent(value: unknown): string {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "n/a";
}

function titleCaseCategory(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

export function UnderstandResultView({ result }: { result: JsonRecord }) {
  const classification = asRecord(result.classification);
  const summary = asRecord(result.summary);
  const pii = asRecord(result.pii);
  const summaryText = typeof summary?.summary === "string" ? summary.summary : "";
  const summarySentences = Array.isArray(summary?.sentences) ? summary.sentences.map(String) : [];
  const findingCount = typeof pii?.finding_count === "number" ? pii.finding_count : 0;
  const entityTypes = Array.isArray(pii?.entity_types) ? pii.entity_types.map(String) : [];

  return (
    <div className="understand-result">
      <div className="understand-stats">
        {typeof result.filename === "string" ? (
          <p>
            <strong>File:</strong> {result.filename}
          </p>
        ) : null}
        <p>
          <strong>Words:</strong> {String(result.word_count ?? "n/a")} |{" "}
          <strong>Reading time:</strong> ~{String(result.reading_minutes ?? "n/a")} min
        </p>
      </div>

      {classification ? (
        <section className="understand-section">
          <h3>Document type</h3>
          <p className="understand-category">
            {titleCaseCategory(String(classification.category ?? "unknown"))}{" "}
            <span className="result-muted">({percent(classification.confidence)} confidence)</span>
          </p>
        </section>
      ) : null}

      {summary ? (
        <section className="understand-section">
          <h3>Summary</h3>
          {summaryText ? <p>{summaryText}</p> : null}
          {summarySentences.length ? (
            <ul className="understand-summary-list">
              {summarySentences.map((sentence) => (
                <li key={sentence}>{sentence}</li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}

      {pii ? (
        <section className="understand-section">
          <h3>PII snapshot</h3>
          <p>
            <strong>{findingCount}</strong> finding{findingCount === 1 ? "" : "s"}
            {entityTypes.length ? (
              <>
                {" "}
                across {entityTypes.join(", ")}
              </>
            ) : null}
          </p>
        </section>
      ) : null}
    </div>
  );
}
