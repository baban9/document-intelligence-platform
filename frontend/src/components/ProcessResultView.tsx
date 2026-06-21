import { useEffect, useMemo, useState } from "react";
import type { ProcessResult } from "../api/client";
import { formatEntityLabel } from "../lib/entityLabels";
import {
  findingKey,
  findingsForPage,
  processDefaultNavigablePage,
  processNavigablePages,
  processPageCount,
  processPageLabel,
  processPiiFindings,
  processSegments,
  RESULT_TABS,
  segmentForPage,
  snapNavigablePage,
  type ResultTab,
} from "../lib/processResults";
import { downloadPiiCsv } from "../lib/exportPiiCsv";
import { ProcessPagePager } from "./ProcessPagePager";

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

type HighlightPart = { kind: "plain" | "hit"; value: string; title?: string };

function highlightPiiText(text: string, pageFindings: ReturnType<typeof findingsForPage>): HighlightPart[] {
  if (!pageFindings.length) {
    return [{ kind: "plain", value: text }];
  }
  const snippets = [...new Set(pageFindings.map((f) => String(f.text ?? "")).filter(Boolean))].sort(
    (a, b) => b.length - a.length,
  );
  const parts: HighlightPart[] = [];
  let cursor = 0;
  while (cursor < text.length) {
    let matchAt = -1;
    let matchSnippet = "";
    let matchTitle = "";
    for (const snippet of snippets) {
      const idx = text.indexOf(snippet, cursor);
      if (idx !== -1 && (matchAt === -1 || idx < matchAt)) {
        matchAt = idx;
        matchSnippet = snippet;
        const finding = pageFindings.find((item) => String(item.text ?? "") === snippet);
        matchTitle = finding
          ? `${formatEntityLabel(String(finding.entity_type ?? ""))} (${percent(finding.score)})`
          : snippet;
      }
    }
    if (matchAt === -1) {
      parts.push({ kind: "plain", value: text.slice(cursor) });
      break;
    }
    if (matchAt > cursor) {
      parts.push({ kind: "plain", value: text.slice(cursor, matchAt) });
    }
    parts.push({ kind: "hit", value: matchSnippet, title: matchTitle });
    cursor = matchAt + matchSnippet.length;
  }
  return parts;
}

type ProcessResultViewProps = {
  result: ProcessResult;
};

export function ProcessResultView({ result }: ProcessResultViewProps) {
  const [activeTab, setActiveTab] = useState<ResultTab>("summary");
  const [pageIndex, setPageIndex] = useState(() => processDefaultNavigablePage(result));
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());

  const extraction = asRecord(result.extraction);
  const classification = asRecord(result.classification);
  const summary = asRecord(result.summary);
  const pii = asRecord(result.pii);
  const findings = processPiiFindings(result);
  const segments = processSegments(result);
  const navigable = processNavigablePages(result);
  const pageCount = processPageCount(result);
  const currentPage = snapNavigablePage(result, pageIndex);

  useEffect(() => {
    setActiveTab("summary");
    setPageIndex(processDefaultNavigablePage(result));
    setSelectedKeys(new Set());
  }, [result]);

  const filename = String(result.filename || "Document");
  const category = String(classification?.category || "unknown");
  const confidence = percent(classification?.confidence);
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

  const pageFindings = useMemo(
    () => findingsForPage(findings, currentPage),
    [findings, currentPage],
  );
  const segment = segmentForPage(segments, currentPage);
  const needsPagination = activeTab === "pii" || activeTab === "text";

  function toggleFinding(key: string) {
    setSelectedKeys((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  function toggleAllOnPage(checked: boolean) {
    setSelectedKeys((current) => {
      const next = new Set(current);
      pageFindings.forEach((finding, index) => {
        const key = findingKey(finding, index);
        if (checked) {
          next.add(key);
        } else {
          next.delete(key);
        }
      });
      return next;
    });
  }

  const allOnPageSelected =
    pageFindings.length > 0 &&
    pageFindings.every((finding, index) => selectedKeys.has(findingKey(finding, index)));

  function exportSelectedCsv() {
    if (!selectedKeys.size) {
      return;
    }
    const base = filename.replace(/\.[^.]+$/, "") || "document";
    downloadPiiCsv(findings, selectedKeys, `${base}-pii-selected.csv`);
  }

  return (
    <div className="process-result">
      <header className="result-header">
        <h2>Results</h2>
        <p className="result-muted">
          {filename} ({pageCount} pages, {navigable.length} with results)
        </p>
      </header>

      <div className="result-tabs" role="tablist" aria-label="Process results">
        {RESULT_TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            className={`result-tab ${activeTab === tab.id ? "result-tab-active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {needsPagination ? (
        <ProcessPagePager result={result} pageIndex={pageIndex} onPageChange={setPageIndex} />
      ) : null}

      <div className="result-tab-panel" role="tabpanel">
        {activeTab === "summary" ? (
          <div className="process-result-summary">
            <header className="result-header">
              <h3>{filename}</h3>
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
              <h3>Document summary</h3>
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
          </div>
        ) : null}

        {activeTab === "pii" ? (
          <div className="process-result-pii">
            <div className="result-section-heading">
              <h3>{processPageLabel(currentPage)}</h3>
              <span className="result-chip">{pageFindings.length} finding(s) on this page</span>
              {selectedKeys.size ? (
                <>
                  <span className="result-chip">{selectedKeys.size} selected overall</span>
                  <button type="button" className="secondary-button" onClick={exportSelectedCsv}>
                    Export selected CSV
                  </button>
                </>
              ) : null}
            </div>
            {!pii ? (
              <p className="result-muted">PII scan was not requested for this run.</p>
            ) : pageFindings.length ? (
              <>
                <label className="pii-select-all">
                  <input
                    type="checkbox"
                    checked={allOnPageSelected}
                    onChange={(event) => toggleAllOnPage(event.target.checked)}
                  />
                  Select all findings on this page
                </label>
                <table className="result-table pii-check-table">
                  <thead>
                    <tr>
                      <th>Select</th>
                      <th>Entity</th>
                      <th>Value</th>
                      <th>Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pageFindings.map((item, index) => {
                      const key = findingKey(item, index);
                      const selected = selectedKeys.has(key);
                      return (
                        <tr key={key} className={selected ? "pii-row-selected" : undefined}>
                          <td>
                            <input
                              type="checkbox"
                              checked={selected}
                              aria-label={`Select ${String(item.text ?? "finding")}`}
                              onChange={() => toggleFinding(key)}
                            />
                          </td>
                          <td>{formatEntityLabel(String(item.entity_type || ""))}</td>
                          <td>{String(item.text || "")}</td>
                          <td>{percent(item.score)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </>
            ) : (
              <p className="result-muted">No PII detected on this page.</p>
            )}
            {segment?.text ? (
              <section className="result-section">
                <h3>Page preview with highlights</h3>
                <pre className="result-text-preview process-highlight-preview">
                  {highlightPiiText(String(segment.text), pageFindings).map((part, index) =>
                    part.kind === "plain" ? (
                      <span key={`${part.value}-${index}`}>{part.value}</span>
                    ) : (
                      <mark key={`${part.value}-${index}`} className="pii-highlight" title={part.title}>
                        {part.value}
                      </mark>
                    ),
                  )}
                </pre>
              </section>
            ) : (
              <p className="result-muted">
                Enable Include extracted text for page previews when segments are not returned.
              </p>
            )}
          </div>
        ) : null}

        {activeTab === "classification" ? (
          <div className="process-result-classification">
            <div className="result-stats result-stats-two">
              <div className="result-stat">
                <div className="result-stat-value">{titleCase(category)}</div>
                <div className="result-stat-label">Primary category</div>
              </div>
              <div className="result-stat">
                <div className="result-stat-value">{percentPrecise(classification?.confidence)}</div>
                <div className="result-stat-label">Confidence</div>
              </div>
            </div>
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
            ) : (
              <p className="result-muted">No category scores returned.</p>
            )}
          </div>
        ) : null}

        {activeTab === "text" ? (
          <div className="process-result-text">
            <div className="result-section-heading">
              <h3>{processPageLabel(currentPage)}</h3>
              <span className="result-chip">
                {segment?.text ? `${String(segment.text).length} characters` : "No segment loaded"}
              </span>
            </div>
            {segment?.text ? (
              <pre className="result-text-preview process-highlight-preview">
                {highlightPiiText(String(segment.text), pageFindings).map((part, index) =>
                  part.kind === "plain" ? (
                    <span key={`${part.value}-${index}`}>{part.value}</span>
                  ) : (
                    <mark key={`${part.value}-${index}`} className="pii-highlight" title={part.title}>
                      {part.value}
                    </mark>
                  ),
                )}
              </pre>
            ) : (
              <p className="result-muted">
                Page text appears here when Include extracted text is enabled on the left.
              </p>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
