import type { PiiFinding } from "./processResults";
import { findingKey } from "./processResults";

function csvEscape(value: string): string {
  if (/[",\n\r]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

function groupFindingsByPage(findings: PiiFinding[]): Map<number, PiiFinding[]> {
  const grouped = new Map<number, PiiFinding[]>();
  for (const finding of findings) {
    const page = Number(finding.page ?? 0);
    const bucket = grouped.get(page) ?? [];
    bucket.push(finding);
    grouped.set(page, bucket);
  }
  return grouped;
}

export function selectedPiiRows(
  findings: PiiFinding[],
  selectedKeys: Set<string>,
): Array<{ page: number; entity_type: string; text: string; score: string }> {
  const rows: Array<{ page: number; entity_type: string; text: string; score: string }> = [];
  const grouped = groupFindingsByPage(findings);

  for (const [page, pageFindings] of [...grouped.entries()].sort((a, b) => a[0] - b[0])) {
    pageFindings.forEach((finding, index) => {
      if (!selectedKeys.has(findingKey(finding, index))) {
        return;
      }
      rows.push({
        page: page + 1,
        entity_type: String(finding.entity_type ?? ""),
        text: String(finding.text ?? ""),
        score:
          typeof finding.score === "number" ? `${Math.round(finding.score * 100)}%` : "",
      });
    });
  }

  return rows;
}

export function buildPiiCsv(
  findings: PiiFinding[],
  selectedKeys: Set<string>,
): string {
  const header = ["page", "entity_type", "text", "score"];
  const rows = selectedPiiRows(findings, selectedKeys);
  const lines = [header.join(",")];
  for (const row of rows) {
    lines.push(
      [row.page, row.entity_type, row.text, row.score]
        .map((value) => csvEscape(String(value)))
        .join(","),
    );
  }
  return lines.join("\n");
}

export function downloadPiiCsv(
  findings: PiiFinding[],
  selectedKeys: Set<string>,
  filename: string,
): number {
  const rows = selectedPiiRows(findings, selectedKeys);
  if (!rows.length) {
    return 0;
  }
  const blob = new Blob([buildPiiCsv(findings, selectedKeys)], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename.endsWith(".csv") ? filename : `${filename}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
  return rows.length;
}
