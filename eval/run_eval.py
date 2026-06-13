#!/usr/bin/env python3
"""Offline evaluation for summarization quality."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from docintel.services.summary import summarize_text

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REPORTS = Path(__file__).resolve().parent / "reports"


def _load(name: str) -> list[dict]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def eval_summaries() -> dict:
    cases = _load("summary_cases.json")
    results = []
    passed = 0
    for case in cases:
        outcome = summarize_text(case["text"], sentence_count=case["sentences"])
        count = len(outcome.sentences)
        ok = count >= case.get("min_sentences", 1)
        passed += int(ok)
        results.append(
            {
                "name": case["name"],
                "sentence_count": count,
                "passed": ok,
                "summary": outcome.sentences,
            }
        )
    return {
        "suite": "summarization",
        "passed": passed,
        "total": len(cases),
        "cases": results,
    }


def main() -> int:
    suite = eval_summaries()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "suites": [suite],
        "passed": suite["passed"],
        "total": suite["total"],
    }

    REPORTS.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS / "eval_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nReport written to {out_path}")
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
