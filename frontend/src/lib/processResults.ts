import type { ProcessResult } from "../api/client";

export type ResultTab = "summary" | "pii" | "classification" | "text";

export const RESULT_TABS: { id: ResultTab; label: string }[] = [
  { id: "summary", label: "Summary" },
  { id: "pii", label: "PII detected" },
  { id: "classification", label: "Classification" },
  { id: "text", label: "Extracted text" },
];

export const PAGE_WINDOW_SIZE = 10;

export type PiiFinding = {
  entity_type?: string;
  text?: string;
  score?: number;
  page?: number;
  start?: number;
};

export type PageSegment = {
  page?: number;
  text?: string;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

export function processPageLabel(pageIndex: number): string {
  return `Page ${pageIndex + 1}`;
}

export function processPageCount(result: ProcessResult): number {
  const extraction = asRecord(result.extraction);
  if (!extraction) {
    return 1;
  }
  const metadata = asRecord(extraction.metadata);
  const raw = metadata?.page_count;
  if (typeof raw === "number" && raw > 0) {
    return raw;
  }
  const segments = processSegments(result);
  if (segments.length) {
    return Math.max(...segments.map((s) => Number(s.page ?? 0))) + 1;
  }
  return 1;
}

export function processSegments(result: ProcessResult): PageSegment[] {
  const extraction = asRecord(result.extraction);
  if (!extraction) {
    return [];
  }
  const segments = extraction.segments;
  if (Array.isArray(segments) && segments.length) {
    return segments.filter((item) => item && typeof item === "object") as PageSegment[];
  }
  const text =
    typeof extraction.text === "string"
      ? extraction.text
      : typeof extraction.text_preview === "string"
        ? extraction.text_preview
        : "";
  if (text.trim()) {
    return [{ page: 0, text }];
  }
  return [];
}

export function processPiiFindings(result: ProcessResult): PiiFinding[] {
  const pii = asRecord(result.pii);
  if (!pii || !Array.isArray(pii.findings)) {
    return [];
  }
  return pii.findings as PiiFinding[];
}

export function processPiiPagesWithFindings(result: ProcessResult): number[] {
  return [...new Set(processPiiFindings(result).map((f) => Number(f.page ?? 0)))].sort(
    (a, b) => a - b,
  );
}

export function processPagesWithText(result: ProcessResult): number[] {
  return processSegments(result)
    .filter((segment) => String(segment.text ?? "").trim())
    .map((segment) => Number(segment.page ?? 0))
    .sort((a, b) => a - b);
}

export function processNavigablePages(result: ProcessResult): number[] {
  const pii = asRecord(result.pii);
  if (pii?.findings) {
    const piiPages = processPiiPagesWithFindings(result);
    if (piiPages.length) {
      return piiPages;
    }
  }
  const textPages = processPagesWithText(result);
  if (textPages.length) {
    return textPages;
  }
  return Array.from({ length: processPageCount(result) }, (_, index) => index);
}

export function processDefaultNavigablePage(result: ProcessResult): number {
  const navigable = processNavigablePages(result);
  return navigable[0] ?? 0;
}

export function snapNavigablePage(result: ProcessResult, pageIndex: number): number {
  const navigable = processNavigablePages(result);
  const pageCount = processPageCount(result);
  const clamped = Math.min(Math.max(pageIndex, 0), Math.max(pageCount - 1, 0));
  if (!navigable.length) {
    return clamped;
  }
  if (navigable.includes(clamped)) {
    return clamped;
  }
  for (const page of navigable) {
    if (page >= clamped) {
      return page;
    }
  }
  return navigable[navigable.length - 1];
}

export function stepNavigablePage(
  result: ProcessResult,
  pageIndex: number,
  delta: number,
): number {
  const navigable = processNavigablePages(result);
  if (!navigable.length) {
    const pageCount = processPageCount(result);
    return Math.min(Math.max(pageIndex + delta, 0), Math.max(pageCount - 1, 0));
  }
  const current = snapNavigablePage(result, pageIndex);
  const position = navigable.indexOf(current);
  const nextPosition = Math.min(Math.max(position + delta, 0), navigable.length - 1);
  return navigable[nextPosition];
}

export function shiftNavigableBlock(
  result: ProcessResult,
  pageIndex: number,
  blockDelta: number,
): number {
  const navigable = processNavigablePages(result);
  if (!navigable.length) {
    return stepNavigablePage(result, pageIndex, blockDelta * PAGE_WINDOW_SIZE);
  }
  const current = snapNavigablePage(result, pageIndex);
  const position = navigable.indexOf(current);
  const nextPosition = Math.min(
    Math.max(position + blockDelta * PAGE_WINDOW_SIZE, 0),
    navigable.length - 1,
  );
  return navigable[nextPosition];
}

export function pageWindowChoices(
  navigable: number[],
  pageIndex: number,
): { value: string; label: string }[] {
  if (!navigable.length) {
    return [{ value: "0", label: processPageLabel(0) }];
  }
  const current = navigable.includes(pageIndex)
    ? pageIndex
    : snapNavigablePageFromList(navigable, pageIndex);
  const position = navigable.indexOf(current);
  const windowStart = Math.floor(position / PAGE_WINDOW_SIZE) * PAGE_WINDOW_SIZE;
  return navigable.slice(windowStart, windowStart + PAGE_WINDOW_SIZE).map((page) => ({
    value: String(page),
    label: processPageLabel(page),
  }));
}

function snapNavigablePageFromList(navigable: number[], pageIndex: number): number {
  if (!navigable.length) {
    return Math.max(pageIndex, 0);
  }
  if (navigable.includes(pageIndex)) {
    return pageIndex;
  }
  for (const page of navigable) {
    if (page >= pageIndex) {
      return page;
    }
  }
  return navigable[navigable.length - 1];
}

export function pageStatusLabel(
  pageIndex: number,
  pageCount: number,
  navigable: number[],
): string {
  const current = navigable.includes(pageIndex)
    ? pageIndex
    : snapNavigablePageFromList(navigable, pageIndex);
  const base = `${processPageLabel(current)} of ${pageCount}`;
  if (!navigable.length) {
    return base;
  }
  const resultIndex = navigable.indexOf(current) + 1;
  let label = `${base} (result ${resultIndex} of ${navigable.length})`;
  const position = navigable.indexOf(current);
  const windowStart = Math.floor(position / PAGE_WINDOW_SIZE) * PAGE_WINDOW_SIZE;
  const windowPages = navigable.slice(windowStart, windowStart + PAGE_WINDOW_SIZE);
  if (windowPages.length > 0 && navigable.length > PAGE_WINDOW_SIZE) {
    label += ` (showing ${processPageLabel(windowPages[0])}-${processPageLabel(windowPages[windowPages.length - 1])})`;
  }
  return label;
}

export function findingsForPage(findings: PiiFinding[], pageIndex: number): PiiFinding[] {
  return findings.filter((finding) => Number(finding.page ?? 0) === pageIndex);
}

export function segmentForPage(
  segments: PageSegment[],
  pageIndex: number,
): PageSegment | undefined {
  return segments.find((segment) => Number(segment.page ?? 0) === pageIndex);
}

export function findingKey(finding: PiiFinding, index: number): string {
  return `${finding.page ?? 0}:${finding.entity_type ?? ""}:${finding.text ?? ""}:${index}`;
}
