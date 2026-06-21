import type { ProcessResult } from "../api/client";
import {
  pageStatusLabel,
  pageWindowChoices,
  processPageCount,
  processNavigablePages,
  snapNavigablePage,
  shiftNavigableBlock,
  stepNavigablePage,
  PAGE_WINDOW_SIZE,
} from "../lib/processResults";

type ProcessPagePagerProps = {
  result: ProcessResult;
  pageIndex: number;
  onPageChange: (pageIndex: number) => void;
};

export function ProcessPagePager({ result, pageIndex, onPageChange }: ProcessPagePagerProps) {
  const pageCount = processPageCount(result);
  const navigable = processNavigablePages(result);
  const current = snapNavigablePage(result, pageIndex);
  const position = navigable.indexOf(current);
  const windowOptions = pageWindowChoices(navigable, current);
  const atFirstResult = position <= 0;
  const atLastResult = position >= navigable.length - 1;
  const atFirstBlock = position < PAGE_WINDOW_SIZE;
  const atLastBlock =
    position >= Math.floor((Math.max(navigable.length, 1) - 1) / PAGE_WINDOW_SIZE) * PAGE_WINDOW_SIZE;

  return (
    <div className="process-page-pager">
      <div className="process-page-pager-row">
        <button
          type="button"
          className="secondary-button"
          disabled={atFirstBlock || navigable.length === 0}
          onClick={() => onPageChange(shiftNavigableBlock(result, current, -1))}
        >
          Previous 10 pages
        </button>
        <button
          type="button"
          className="secondary-button"
          disabled={atFirstResult || navigable.length === 0}
          onClick={() => onPageChange(stepNavigablePage(result, current, -1))}
        >
          Previous page
        </button>
        <strong className="process-page-status">{pageStatusLabel(current, pageCount, navigable)}</strong>
        <button
          type="button"
          className="secondary-button"
          disabled={atLastResult || navigable.length === 0}
          onClick={() => onPageChange(stepNavigablePage(result, current, 1))}
        >
          Next page
        </button>
        <button
          type="button"
          className="secondary-button"
          disabled={atLastBlock || navigable.length === 0}
          onClick={() => onPageChange(shiftNavigableBlock(result, current, 1))}
        >
          Next 10 pages
        </button>
      </div>
      <div className="process-page-pager-row">
        <label className="process-page-jump">
          <span>Jump to page with results (10 per group)</span>
          <select
            value={String(current)}
            onChange={(event) => onPageChange(Number(event.target.value))}
          >
            {windowOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <p className="result-muted process-page-hint">
          Empty pages are skipped. {navigable.length} of {pageCount} pages have results in this view.
        </p>
      </div>
    </div>
  );
}
