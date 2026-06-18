#!/usr/bin/env python3
"""Offline evaluation for summarization, classification, process, and PII quality."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from docintel.capabilities.pipeline import ProcessOptions, process_text
from docintel.capabilities.understanding.classify import classify_text
from docintel.services.summary import summarize_text

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REPORTS = Path(__file__).resolve().parent / "reports"


def _load(name: str) -> list[dict]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _presidio_available() -> bool:
    try:
        from docintel.services.pdf.pii import detect_pii_in_text

        detect_pii_in_text(
            "Contact john@example.com for help.",
            entities=["EMAIL_ADDRESS"],
            min_score=0.35,
        )
        return True
    except Exception:
        return False


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


def eval_classify() -> dict:
    cases = _load("classify_cases.json")
    results = []
    passed = 0
    for case in cases:
        outcome = classify_text(case["text"])
        ok = outcome.category == case["expected_category"]
        passed += int(ok)
        results.append(
            {
                "name": case["name"],
                "category": outcome.category,
                "expected_category": case["expected_category"],
                "passed": ok,
            }
        )
    return {
        "suite": "classification",
        "passed": passed,
        "total": len(cases),
        "cases": results,
    }


def eval_process() -> dict:
    cases = _load("process_cases.json")
    results = []
    passed = 0
    for case in cases:
        options = ProcessOptions.from_dict(case.get("options", {}))
        outcome = process_text(case["text"], options=options)
        payload = outcome.to_dict()
        category_ok = payload["classification"]["category"] == case["expected_category"]
        summary_ok = True
        if options.include_summarize:
            summary_ok = len(payload.get("summary", {}).get("sentences", [])) >= case.get(
                "min_summary_sentences", 1
            )
        ok = category_ok and summary_ok
        passed += int(ok)
        results.append(
            {
                "name": case["name"],
                "category": payload["classification"]["category"],
                "expected_category": case["expected_category"],
                "summary_sentences": len(payload.get("summary", {}).get("sentences", [])),
                "passed": ok,
            }
        )
    return {
        "suite": "process",
        "passed": passed,
        "total": len(cases),
        "cases": results,
    }


def eval_pii() -> dict:
    if not _presidio_available():
        return {
            "suite": "pii",
            "passed": 0,
            "total": 0,
            "skipped": True,
            "reason": "Presidio not installed. Run: pip install -e '.[ocr]'",
            "cases": [],
        }

    from docintel.services.pdf.pii import detect_pii_in_text

    cases = _load("pii_cases.json")
    results = []
    passed = 0
    for case in cases:
        entities = case.get("entities")
        hits = detect_pii_in_text(
            case["text"],
            entities=entities,
            min_score=case.get("min_score", 0.35),
        )
        found_types = {hit.entity_type for hit in hits}
        expected_types = set(case.get("expected_entity_types", []))
        count_ok = len(hits) >= case.get("min_findings", 1)
        types_ok = expected_types.issubset(found_types) if expected_types else True
        ok = count_ok and types_ok
        passed += int(ok)
        results.append(
            {
                "name": case["name"],
                "finding_count": len(hits),
                "entity_types": sorted(found_types),
                "passed": ok,
            }
        )
    return {
        "suite": "pii",
        "passed": passed,
        "total": len(cases),
        "skipped": False,
        "cases": results,
    }


def main() -> int:
    suites = [
        eval_summaries(),
        eval_classify(),
        eval_process(),
        eval_pii(),
    ]
    passed = sum(suite["passed"] for suite in suites)
    total = sum(suite["total"] for suite in suites)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "suites": suites,
        "passed": passed,
        "total": total,
    }

    REPORTS.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS / "eval_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nReport written to {out_path}")
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
