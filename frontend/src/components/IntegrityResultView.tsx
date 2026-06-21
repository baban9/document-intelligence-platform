import {
  formatIntegritySummary,
  severityLabel,
  type IntegrityResult,
} from "../lib/integrity";

type IntegrityResultViewProps = {
  result: IntegrityResult;
};

export function IntegrityResultView({ result }: IntegrityResultViewProps) {
  const findings = result.findings ?? [];

  return (
    <div className="integrity-result">
      <pre className="integrity-summary">{formatIntegritySummary(result)}</pre>
      {findings.length ? (
        <table className="result-table findings-table">
          <thead>
            <tr>
              <th>Severity</th>
              <th>Category</th>
              <th>Description</th>
              <th>Evidence</th>
              <th>Suggested fix</th>
            </tr>
          </thead>
          <tbody>
            {findings.map((finding, index) => {
              const quote =
                finding.evidence?.[0] && typeof finding.evidence[0] === "object"
                  ? String(finding.evidence[0].quote ?? "")
                  : "";
              return (
                <tr key={`${finding.category}-${index}`}>
                  <td>{severityLabel(String(finding.severity ?? ""))}</td>
                  <td>{String(finding.category ?? "")}</td>
                  <td>{String(finding.description ?? "")}</td>
                  <td>{quote}</td>
                  <td>{String(finding.suggested_fix ?? "")}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : (
        <p className="result-muted">No integrity findings reported.</p>
      )}
    </div>
  );
}
