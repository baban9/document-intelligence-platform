export const INTEGRITY_CHECKS = [
  "placeholders",
  "broken_references",
  "name_drift",
  "number_mismatch",
  "structural_gaps",
] as const;

export type IntegrityCheck = (typeof INTEGRITY_CHECKS)[number];

export type IntegrityFinding = {
  severity?: string;
  category?: string;
  description?: string;
  suggested_fix?: string;
  evidence?: Array<{ quote?: string }>;
};

export type IntegrityResult = {
  finding_count?: number;
  checks_run?: string[];
  summary?: {
    by_severity?: Record<string, number>;
    by_category?: Record<string, number>;
  };
  findings?: IntegrityFinding[];
};

export function severityLabel(severity: string): string {
  const key = severity.trim().toLowerCase();
  if (key === "high" || key === "critical") {
    return `[!] ${severity.toUpperCase()}`;
  }
  if (key === "medium") {
    return `[~] ${severity.toUpperCase()}`;
  }
  if (key === "low") {
    return `[.] ${severity.toUpperCase()}`;
  }
  return severity.toUpperCase() || "UNKNOWN";
}

export function formatIntegritySummary(result: IntegrityResult): string {
  const summary = result.summary ?? {};
  const bySeverity = summary.by_severity ?? {};
  const byCategory = summary.by_category ?? {};
  const severityParts = Object.entries(bySeverity)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, value]) => `${severityLabel(key)}: ${value}`);
  const categoryParts = Object.entries(byCategory)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, value]) => `${key}: ${value}`);
  return [
    `Finding count: ${result.finding_count ?? 0}`,
    `Checks run: ${(result.checks_run ?? []).join(", ") || "none"}`,
    `By severity: ${severityParts.join(", ") || "none"}`,
    `By category: ${categoryParts.join(", ") || "none"}`,
  ].join("\n");
}
