#!/usr/bin/env python3
"""Offline evaluation for matching and summarization quality."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from docintel.services.matching import match_resume_to_job
from docintel.services.summary import summarize_text

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REPORTS = Path(__file__).resolve().parent / "reports"


def _load(name: str) -> list[dict]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def eval_matching() -> dict:
    cases = _load("match_cases.json")
    results = []
    passed = 0
    for case in cases:
        outcome = match_resume_to_job(
            resume=case["resume"],
            job_description=case["job_description"],
            top_keywords=10,
        )
        score = outcome.score
        ok = score >= case.get("min_score", 0.0)
        if "max_score" in case:
            ok = ok and score <= case["max_score"]
        passed += int(ok)
        results.append(
            {
                "name": case["name"],
                "score": score,
                "passed": ok,
                "matched_keywords": outcome.matched_keywords[:5],
            }
        )
    return {
        "suite": "matching",
        "passed": passed,
        "total": len(cases),
        "cases": results,
    }


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
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "suites": [eval_matching(), eval_summaries()],
    }
    report["passed"] = sum(suite["passed"] for suite in report["suites"])
    report["total"] = sum(suite["total"] for suite in report["suites"])

    REPORTS.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS / "eval_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nReport written to {out_path}")
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
