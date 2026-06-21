type AnnotatePlanViewProps = {
  report: Record<string, unknown>;
};

export function AnnotatePlanView({ report }: AnnotatePlanViewProps) {
  const rationale = typeof report.rationale === "string" ? report.rationale : "";
  const patterns = Array.isArray(report.patterns) ? report.patterns.map(String) : [];
  const phrases = Array.isArray(report.phrases) ? report.phrases.map(String) : [];
  const searchPatterns = Array.isArray(report.search_patterns)
    ? report.search_patterns.map(String)
    : [];
  const requirements =
    typeof report.requirements === "string" ? report.requirements : "";

  if (!requirements && !patterns.length && !phrases.length && !searchPatterns.length) {
    return null;
  }

  return (
    <div className="annotate-plan">
      {requirements ? (
        <section className="result-section">
          <h3>Requirements</h3>
          <p className="result-muted">{requirements}</p>
        </section>
      ) : null}

      {rationale ? (
        <section className="result-section">
          <h3>LLM plan</h3>
          <p className="result-muted">{rationale}</p>
        </section>
      ) : null}

      {patterns.length ? (
        <section className="result-section">
          <h3>Generated regex patterns</h3>
          <ul className="result-list">
            {patterns.map((item) => (
              <li key={item}>
                <code>{item}</code>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {phrases.length ? (
        <section className="result-section">
          <h3>Generated phrases</h3>
          <ul className="result-list">
            {phrases.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {searchPatterns.length ? (
        <section className="result-section">
          <h3>Patterns applied</h3>
          <ul className="result-list">
            {searchPatterns.map((item) => (
              <li key={item}>
                <code>{item}</code>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
